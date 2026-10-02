"""CRM business logic. Routers stay thin; every rule lives here."""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app import events
from app.agencies.models import AgencyMember
from app.audit import service as audit
from app.auth.deps import Principal
from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.crm import policies
from app.crm.models import (
    MANUAL_ACTIVITY_KINDS,
    ActivityKind,
    Appointment,
    AppointmentStatus,
    Conversation,
    CoreStatus,
    CrmTask,
    Customer,
    Inquiry,
    Lead,
    LeadActivity,
    LeadSource,
    LeadStatus,
    Message,
)
from app.crm.schemas import (
    ActivityIn,
    ActivityOut,
    AppointmentCreate,
    AppointmentOut,
    AppointmentUpdate,
    CrmDashboard,
    CustomerOut,
    CustomerUpdate,
    InquiryCreate,
    LeadCreate,
    LeadOut,
    LeadUpdate,
    PersonRef,
    PropertyRef,
    StatusCount,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    check_budget,
)
from app.policies import membership
from app.properties.models import Property
from app.properties.service import manages
from app.rbac.catalog import Permission
from app.users.models import User


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- lookups


def get_lead_or_404(db: Session, principal: Principal, lead_id: uuid.UUID) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None or not policies.can_see_lead(db, principal, lead):
        raise NotFoundError("Lead not found", code="LEAD_NOT_FOUND")
    return lead


def ensure_manage(db: Session, principal: Principal, lead: Lead) -> None:
    if not policies.can_manage_lead(db, principal, lead):
        raise PermissionDeniedError("You cannot change this lead")


def active_status(db: Session, code: str) -> LeadStatus:
    status = db.get(LeadStatus, code)
    if status is None or not status.is_active:
        raise AppError("Unknown or inactive status", code="INVALID_STATUS", status_code=422)
    return status


def people_refs(db: Session, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, PersonRef]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(wanted))).all()
    return {r.id: PersonRef(id=r.id, full_name=r.full_name) for r in rows}


def _lead_counts(db: Session, customer_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]:
    ids = set(customer_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(Lead.customer_id, func.count())
        .where(Lead.customer_id.in_(ids))
        .group_by(Lead.customer_id)
    ).all()
    return {r[0]: r[1] for r in rows}


def customer_out(c: Customer, lead_count: int = 0) -> CustomerOut:
    return CustomerOut(
        id=c.id,
        full_name=c.full_name,
        phone=c.phone,
        email=c.email,
        notes=c.notes,
        source=c.source,
        is_platform_user=c.user_id is not None,
        agency_id=c.agency_id,
        created_at=c.created_at,
        lead_count=lead_count,
    )


def leads_out(db: Session, principal: Principal, leads: Sequence[Lead]) -> list[LeadOut]:
    """Batch-load related rows: a constant number of queries for any page size."""
    if not leads:
        return []
    customers = {
        c.id: c
        for c in db.execute(
            select(Customer).where(Customer.id.in_({lead.customer_id for lead in leads}))
        ).scalars()
    }
    prop_ids = {lead.property_id for lead in leads if lead.property_id}
    props = (
        {p.id: p for p in db.execute(select(Property).where(Property.id.in_(prop_ids))).scalars()}
        if prop_ids
        else {}
    )
    people = people_refs(
        db, [x for lead in leads for x in (lead.owner_user_id, lead.assigned_to_id)]
    )
    counts = _lead_counts(db, customers)
    owned_agency = policies.owned_agency_id(db, principal)
    manage = principal.has(Permission.LEADS_MANAGE)
    read_any = principal.has(Permission.LEADS_READ_ANY)
    out = []
    for lead in leads:
        prop = props.get(lead.property_id) if lead.property_id else None
        can_assign = manage and (
            read_any or (lead.agency_id is not None and lead.agency_id == owned_agency)
        )
        out.append(
            LeadOut(
                id=lead.id,
                status_code=lead.status_code,
                source=lead.source,
                priority=lead.priority,
                customer=customer_out(customers[lead.customer_id], counts.get(lead.customer_id, 0)),
                property=PropertyRef(
                    id=prop.id,
                    reference_code=prop.reference_code,
                    title_ar=prop.title_ar,
                    title_en=prop.title_en,
                    status=prop.status,
                )
                if prop
                else None,
                agency_id=lead.agency_id,
                owner=people.get(lead.owner_user_id),
                assigned_to=people.get(lead.assigned_to_id) if lead.assigned_to_id else None,
                budget_min=lead.budget_min,
                budget_max=lead.budget_max,
                budget_currency=lead.budget_currency,
                next_follow_up_at=lead.next_follow_up_at,
                last_activity_at=lead.last_activity_at,
                closed_at=lead.closed_at,
                lost_reason=lead.lost_reason,
                created_at=lead.created_at,
                updated_at=lead.updated_at,
                can_manage=manage,  # rows are already scoped to what the caller can see
                can_assign=can_assign,
            )
        )
    return out


def _activity(
    db: Session,
    lead: Lead,
    kind: ActivityKind,
    actor_id: uuid.UUID | None,
    body: str | None = None,
    data: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> LeadActivity:
    entry = LeadActivity(
        lead_id=lead.id,
        actor_id=actor_id,
        kind=kind,
        body=body,
        data=data,
        occurred_at=occurred_at or _now(),
    )
    db.add(entry)
    lead.last_activity_at = _now()
    return entry


# --------------------------------------------------------------------------- inquiries


def _scope_for_property(prop: Property) -> tuple[uuid.UUID | None, uuid.UUID, uuid.UUID]:
    """(agency_id, accountable owner, assignee) for leads about ``prop``."""
    responsible = prop.agent_id or prop.lister_id
    return prop.agency_id, responsible, responsible


def _find_or_create_customer(
    db: Session,
    *,
    agency_id: uuid.UUID | None,
    owner_user_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    full_name: str,
    phone: str | None,
    email: str | None,
    source: str,
) -> Customer:
    if user_id is not None:
        stmt = select(Customer).where(Customer.user_id == user_id)
        stmt = (
            stmt.where(Customer.agency_id == agency_id)
            if agency_id
            else stmt.where(Customer.agency_id.is_(None), Customer.owner_user_id == owner_user_id)
        )
        existing = db.execute(stmt).scalar_one_or_none()
        if existing is not None:
            existing.phone = existing.phone or phone
            existing.email = existing.email or email
            return existing
    customer = Customer(
        agency_id=agency_id,
        owner_user_id=None if agency_id else owner_user_id,
        user_id=user_id,
        full_name=full_name,
        phone=phone,
        email=email,
        source=source,
    )
    db.add(customer)
    db.flush()
    return customer


def create_inquiry(
    db: Session, principal: Principal, prop: Property, data: InquiryCreate
) -> Inquiry:
    if not prop.is_public:
        raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")
    if principal.id in (prop.lister_id, prop.agent_id) or manages(db, principal, prop):
        raise AppError(
            "You cannot send an inquiry about your own listing",
            code="OWN_LISTING",
            status_code=422,
        )
    agency_id, owner_id, assignee_id = _scope_for_property(prop)
    customer = _find_or_create_customer(
        db,
        agency_id=agency_id,
        owner_user_id=owner_id,
        user_id=principal.id,
        full_name=data.name.strip(),
        phone=data.phone,
        email=str(data.email) if data.email else None,
        source=LeadSource.INQUIRY,
    )
    # Reuse the customer's open lead on this listing instead of duplicating it.
    lead = db.execute(
        select(Lead)
        .join(LeadStatus, LeadStatus.code == Lead.status_code)
        .where(
            Lead.customer_id == customer.id,
            Lead.property_id == prop.id,
            LeadStatus.is_terminal.is_(False),
        )
        .limit(1)
    ).scalar_one_or_none()
    created = lead is None
    if lead is None:
        lead = Lead(
            customer_id=customer.id,
            property_id=prop.id,
            agency_id=agency_id,
            owner_user_id=owner_id,
            assigned_to_id=assignee_id,
            status_code=CoreStatus.NEW,
            source=LeadSource.INQUIRY,
            priority="NORMAL",
            created_by_id=principal.id,
        )
        db.add(lead)
        db.flush()
    inquiry = Inquiry(
        property_id=prop.id,
        sender_id=principal.id,
        lead_id=lead.id,
        name=data.name.strip(),
        phone=data.phone,
        email=str(data.email) if data.email else None,
        message=data.message.strip(),
        preferred_contact=data.preferred_contact,
    )
    db.add(inquiry)
    db.flush()
    _activity(
        db,
        lead,
        ActivityKind.INQUIRY,
        principal.id,
        body=inquiry.message,
        data={"inquiry_id": str(inquiry.id), "preferred_contact": inquiry.preferred_contact},
    )
    conversation = _conversation_for(db, principal.id, prop, lead, assignee_id)
    _post_message(db, conversation, principal.id, inquiry.message, log_on_lead=False)
    audit.record(
        db,
        "inquiry.created",
        actor_id=principal.id,
        resource_type="inquiry",
        resource_id=inquiry.id,
        data={"property_id": str(prop.id), "lead_id": str(lead.id), "new_lead": created},
    )
    payload = {
        "lead_id": str(lead.id),
        "property_id": str(prop.id),
        "inquiry_id": str(inquiry.id),
        "assigned_to_id": str(assignee_id),
        "agency_id": str(agency_id) if agency_id else None,
    }
    events.emit(db, "inquiry.created", payload)
    if created:
        events.emit(db, "lead.created", payload)
    db.commit()
    return inquiry


def my_inquiries(db: Session, principal: Principal, *, offset: int, limit: int):
    stmt = select(Inquiry).where(Inquiry.sender_id == principal.id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(stmt.order_by(Inquiry.created_at.desc()).offset(offset).limit(limit)).scalars()
    )
    props = (
        {
            p.id: p
            for p in db.execute(
                select(Property).where(Property.id.in_({r.property_id for r in rows}))
            ).scalars()
        }
        if rows
        else {}
    )
    return rows, props, total


# --------------------------------------------------------------------------- leads


def _caller_scope(db: Session, principal: Principal) -> tuple[uuid.UUID | None, uuid.UUID]:
    """(agency_id, owner) for records the caller creates by hand."""
    m = membership(db, principal.id)
    return (m.agency_id if m else None), principal.id


def list_leads(
    db: Session,
    principal: Principal,
    *,
    status: str | None,
    assigned_to_id: uuid.UUID | None,
    property_id: uuid.UUID | None,
    q: str | None,
    overdue: bool,
    open_only: bool,
    offset: int,
    limit: int,
) -> tuple[list[Lead], int]:
    stmt = select(Lead).where(policies.lead_scope(db, principal))
    if status:
        stmt = stmt.where(Lead.status_code == status)
    if assigned_to_id:
        stmt = stmt.where(Lead.assigned_to_id == assigned_to_id)
    if property_id:
        stmt = stmt.where(Lead.property_id == property_id)
    if overdue:
        stmt = stmt.where(Lead.next_follow_up_at < _now(), Lead.closed_at.is_(None))
    if open_only:
        stmt = stmt.where(Lead.closed_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.join(Customer, Customer.id == Lead.customer_id).where(
            or_(
                Customer.full_name.ilike(like),
                Customer.phone.ilike(like),
                Customer.email.ilike(like),
            )
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(Lead.next_follow_up_at.asc().nulls_last(), Lead.updated_at.desc(), Lead.id)
        .offset(offset)
        .limit(limit)
    ).scalars()
    return list(rows), total


def create_lead(db: Session, principal: Principal, data: LeadCreate) -> Lead:
    agency_id, owner_id = _caller_scope(db, principal)
    prop: Property | None = None
    if data.property_id:
        prop = db.get(Property, data.property_id)
        if prop is None or prop.deleted_at is not None or not manages(db, principal, prop):
            raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")
        agency_id = prop.agency_id
    if data.customer_id:
        customer = db.execute(
            select(Customer).where(
                Customer.id == data.customer_id, policies.customer_scope(db, principal)
            )
        ).scalar_one_or_none()
        if customer is None:
            raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")
    else:
        assert data.customer is not None  # noqa: S101 - enforced by the schema
        customer = _find_or_create_customer(
            db,
            agency_id=agency_id,
            owner_user_id=owner_id,
            user_id=None,
            full_name=data.customer.full_name.strip(),
            phone=data.customer.phone,
            email=str(data.customer.email) if data.customer.email else None,
            source=data.source,
        )
        customer.notes = data.customer.notes
    lead = Lead(
        customer_id=customer.id,
        property_id=prop.id if prop else None,
        agency_id=agency_id,
        owner_user_id=owner_id,
        assigned_to_id=principal.id,
        status_code=CoreStatus.NEW,
        source=data.source,
        priority=data.priority,
        budget_min=data.budget_min,
        budget_max=data.budget_max,
        budget_currency=data.budget_currency,
        next_follow_up_at=data.next_follow_up_at,
        created_by_id=principal.id,
    )
    db.add(lead)
    db.flush()
    if data.note:
        _activity(db, lead, ActivityKind.NOTE, principal.id, body=data.note)
    audit.record(
        db, "lead.created", actor_id=principal.id, resource_type="lead", resource_id=lead.id
    )
    events.emit(
        db,
        "lead.created",
        {"lead_id": str(lead.id), "assigned_to_id": str(principal.id), "source": lead.source},
    )
    db.commit()
    return lead


def _validate_assignee(db: Session, lead: Lead, assignee_id: uuid.UUID) -> None:
    if lead.agency_id is not None:
        member = db.execute(
            select(AgencyMember).where(
                AgencyMember.agency_id == lead.agency_id, AgencyMember.user_id == assignee_id
            )
        ).scalar_one_or_none()
        if member is None:
            raise AppError(
                "The assignee must belong to the lead's agency",
                code="INVALID_ASSIGNEE",
                status_code=422,
            )
    elif assignee_id != lead.owner_user_id:
        raise AppError(
            "Independent leads can only be assigned to their owner",
            code="INVALID_ASSIGNEE",
            status_code=422,
        )


def update_lead(db: Session, principal: Principal, lead: Lead, data: LeadUpdate) -> Lead:
    ensure_manage(db, principal, lead)
    fields = data.model_fields_set
    if "assigned_to_id" in fields and data.assigned_to_id != lead.assigned_to_id:
        if not policies.can_assign_lead(db, principal, lead):
            raise PermissionDeniedError("Only the agency owner can reassign leads")
        if data.assigned_to_id is None:
            raise AppError("A lead must stay assigned", code="INVALID_ASSIGNEE", status_code=422)
        _validate_assignee(db, lead, data.assigned_to_id)
        previous = lead.assigned_to_id
        lead.assigned_to_id = data.assigned_to_id
        _activity(
            db,
            lead,
            ActivityKind.ASSIGNMENT,
            principal.id,
            data={"from": str(previous) if previous else None, "to": str(data.assigned_to_id)},
        )
        events.emit(
            db,
            "lead.assigned",
            {"lead_id": str(lead.id), "assigned_to_id": str(data.assigned_to_id)},
        )
    if data.status_code is not None and data.status_code != lead.status_code:
        status = active_status(db, data.status_code)
        if status.code == CoreStatus.LOST and not (data.lost_reason or "").strip():
            raise AppError(
                "A reason is required when a lead is lost",
                code="LOST_REASON_REQUIRED",
                status_code=422,
            )
        previous_status = lead.status_code
        lead.status_code = status.code
        lead.closed_at = _now() if status.is_terminal else None
        lost = status.code == CoreStatus.LOST and data.lost_reason
        lead.lost_reason = data.lost_reason.strip() if lost and data.lost_reason else None
        _activity(
            db,
            lead,
            ActivityKind.STATUS_CHANGE,
            principal.id,
            body=lead.lost_reason,
            data={"from": previous_status, "to": status.code},
        )
        events.emit(
            db,
            "lead.status_changed",
            {"lead_id": str(lead.id), "from": previous_status, "to": status.code},
        )
    if "priority" in fields and data.priority is not None:
        lead.priority = data.priority
    budget_fields = {"budget_min", "budget_max", "budget_currency"} & fields
    if budget_fields:
        lo = data.budget_min if "budget_min" in fields else lead.budget_min
        hi = data.budget_max if "budget_max" in fields else lead.budget_max
        cur = data.budget_currency if "budget_currency" in fields else lead.budget_currency
        try:
            check_budget(lo, hi, cur)
        except ValueError as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=422) from exc
        lead.budget_min, lead.budget_max, lead.budget_currency = lo, hi, cur
    if "next_follow_up_at" in fields:
        lead.next_follow_up_at = data.next_follow_up_at
    audit.record(
        db,
        "lead.updated",
        actor_id=principal.id,
        resource_type="lead",
        resource_id=lead.id,
        data={"fields": ",".join(sorted(fields))},
    )
    db.commit()
    db.refresh(lead)
    return lead


def add_activity(db: Session, principal: Principal, lead: Lead, data: ActivityIn) -> LeadActivity:
    ensure_manage(db, principal, lead)
    if data.kind not in MANUAL_ACTIVITY_KINDS:
        raise AppError(
            "This activity type is recorded automatically",
            code="INVALID_ACTIVITY",
            status_code=422,
        )
    if data.occurred_at and data.occurred_at > _now() + timedelta(minutes=5):
        raise AppError(
            "Activities cannot be in the future", code="INVALID_ACTIVITY", status_code=422
        )
    entry = _activity(
        db, lead, data.kind, principal.id, body=data.body.strip(), occurred_at=data.occurred_at
    )
    if lead.status_code == CoreStatus.NEW and data.kind != ActivityKind.NOTE:
        # First real contact moves a new lead forward automatically.
        lead.status_code = CoreStatus.CONTACTED
        _activity(
            db,
            lead,
            ActivityKind.STATUS_CHANGE,
            None,
            data={"from": CoreStatus.NEW.value, "to": CoreStatus.CONTACTED.value, "auto": True},
        )
    db.commit()
    db.refresh(entry)
    return entry


def activities(db: Session, lead: Lead) -> list[ActivityOut]:
    rows = list(
        db.execute(
            select(LeadActivity)
            .where(LeadActivity.lead_id == lead.id)
            .order_by(LeadActivity.occurred_at.desc(), LeadActivity.created_at.desc())
            .limit(500)
        ).scalars()
    )
    people = people_refs(db, [r.actor_id for r in rows])
    return [
        ActivityOut(
            id=r.id,
            kind=r.kind,
            body=r.body,
            data=r.data,
            actor=people.get(r.actor_id) if r.actor_id else None,
            occurred_at=r.occurred_at,
        )
        for r in rows
    ]


# --------------------------------------------------------------------------- customers


def list_customers(
    db: Session, principal: Principal, *, q: str | None, offset: int, limit: int
) -> tuple[list[CustomerOut], int]:
    visible_via_leads = select(Lead.customer_id).where(policies.lead_scope(db, principal))
    stmt = select(Customer).where(
        or_(policies.customer_scope(db, principal), Customer.id.in_(visible_via_leads))
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Customer.full_name.ilike(like),
                Customer.phone.ilike(like),
                Customer.email.ilike(like),
            )
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(stmt.order_by(Customer.created_at.desc()).offset(offset).limit(limit)).scalars()
    )
    counts = _lead_counts(db, [c.id for c in rows])
    return [customer_out(c, counts.get(c.id, 0)) for c in rows], total


def get_customer_or_404(db: Session, principal: Principal, customer_id: uuid.UUID) -> Customer:
    visible_via_leads = select(Lead.customer_id).where(policies.lead_scope(db, principal))
    customer = db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            or_(policies.customer_scope(db, principal), Customer.id.in_(visible_via_leads)),
        )
    ).scalar_one_or_none()
    if customer is None:
        raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")
    return customer


def update_customer(
    db: Session, principal: Principal, customer: Customer, data: CustomerUpdate
) -> Customer:
    if not principal.has(Permission.LEADS_MANAGE):
        raise PermissionDeniedError("You cannot change customers")
    for field in data.model_fields_set:
        value = getattr(data, field)
        if field == "full_name" and value is None:
            continue
        setattr(customer, field, str(value) if field == "email" and value is not None else value)
    audit.record(
        db,
        "customer.updated",
        actor_id=principal.id,
        resource_type="customer",
        resource_id=customer.id,
    )
    db.commit()
    db.refresh(customer)
    return customer


# --------------------------------------------------------------------------- tasks


def _task_scope(db: Session, principal: Principal) -> Any:
    if principal.has(Permission.LEADS_READ_ANY):
        return CrmTask.id.is_not(None)
    conditions: list[Any] = [
        CrmTask.assigned_to_id == principal.id,
        CrmTask.created_by_id == principal.id,
        CrmTask.owner_user_id == principal.id,
    ]
    agency_id = policies.owned_agency_id(db, principal)
    if agency_id is not None:
        conditions.append(CrmTask.agency_id == agency_id)
    return or_(*conditions)


def task_out(task: CrmTask, people: dict[uuid.UUID, PersonRef]) -> TaskOut:
    now = _now()
    return TaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        lead_id=task.lead_id,
        assigned_to=people.get(task.assigned_to_id) if task.assigned_to_id else None,
        due_at=task.due_at,
        completed_at=task.completed_at,
        priority=task.priority,
        overdue=task.completed_at is None and task.due_at is not None and task.due_at < now,
        created_at=task.created_at,
    )


def tasks_out(db: Session, tasks: Sequence[CrmTask]) -> list[TaskOut]:
    people = people_refs(db, [t.assigned_to_id for t in tasks])
    return [task_out(t, people) for t in tasks]


def list_tasks(
    db: Session,
    principal: Principal,
    *,
    status: str,
    lead_id: uuid.UUID | None,
    offset: int,
    limit: int,
) -> tuple[list[CrmTask], int]:
    stmt = select(CrmTask).where(_task_scope(db, principal))
    if lead_id:
        lead = get_lead_or_404(db, principal, lead_id)
        stmt = select(CrmTask).where(CrmTask.lead_id == lead.id)
    now = _now()
    if status == "open":
        stmt = stmt.where(CrmTask.completed_at.is_(None))
    elif status == "done":
        stmt = stmt.where(CrmTask.completed_at.is_not(None))
    elif status == "overdue":
        stmt = stmt.where(CrmTask.completed_at.is_(None), CrmTask.due_at < now)
    elif status == "today":
        end = now.replace(hour=23, minute=59, second=59)
        stmt = stmt.where(CrmTask.completed_at.is_(None), CrmTask.due_at <= end)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(CrmTask.due_at.asc().nulls_last(), CrmTask.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars()
    return list(rows), total


def create_task(db: Session, principal: Principal, data: TaskCreate) -> CrmTask:
    if not principal.has(Permission.LEADS_MANAGE):
        raise PermissionDeniedError("You cannot create tasks")
    lead: Lead | None = None
    if data.lead_id:
        lead = get_lead_or_404(db, principal, data.lead_id)
        ensure_manage(db, principal, lead)
        agency_id, owner_id = lead.agency_id, lead.owner_user_id
    else:
        agency_id, owner_id = _caller_scope(db, principal)
    assignee = data.assigned_to_id or principal.id
    if assignee != principal.id:
        if lead is None or not policies.can_assign_lead(db, principal, lead):
            raise PermissionDeniedError("You can only assign tasks to yourself")
        _validate_assignee(db, lead, assignee)
    task = CrmTask(
        lead_id=lead.id if lead else None,
        agency_id=agency_id,
        owner_user_id=owner_id,
        assigned_to_id=assignee,
        created_by_id=principal.id,
        title=data.title.strip(),
        description=data.description,
        due_at=data.due_at,
        priority=data.priority,
    )
    db.add(task)
    db.flush()
    if lead is not None:
        _activity(
            db,
            lead,
            ActivityKind.TASK,
            principal.id,
            body=task.title,
            data={"task_id": str(task.id), "action": "created"},
        )
    db.commit()
    db.refresh(task)
    return task


def get_task_or_404(db: Session, principal: Principal, task_id: uuid.UUID) -> CrmTask:
    task = db.execute(
        select(CrmTask).where(CrmTask.id == task_id, _task_scope(db, principal))
    ).scalar_one_or_none()
    if task is None and principal.has(Permission.LEADS_READ_OWN):
        # Tasks on leads the caller can see are visible too.
        candidate = db.get(CrmTask, task_id)
        if candidate and candidate.lead_id:
            lead = db.get(Lead, candidate.lead_id)
            if lead and policies.can_see_lead(db, principal, lead):
                task = candidate
    if task is None:
        raise NotFoundError("Task not found", code="TASK_NOT_FOUND")
    return task


def update_task(db: Session, principal: Principal, task: CrmTask, data: TaskUpdate) -> CrmTask:
    if not principal.has(Permission.LEADS_MANAGE):
        raise PermissionDeniedError("You cannot change tasks")
    fields = data.model_fields_set
    if "assigned_to_id" in fields and data.assigned_to_id not in (None, task.assigned_to_id):
        lead = db.get(Lead, task.lead_id) if task.lead_id else None
        if lead is None or not policies.can_assign_lead(db, principal, lead):
            raise PermissionDeniedError("You cannot reassign this task")
        _validate_assignee(db, lead, data.assigned_to_id)
        task.assigned_to_id = data.assigned_to_id
    for field in ("title", "description", "due_at", "priority"):
        if field in fields and (field != "title" or data.title):
            setattr(task, field, getattr(data, field))
    if data.completed is not None:
        was_done = task.completed_at is not None
        task.completed_at = _now() if data.completed else None
        if data.completed and not was_done and task.lead_id:
            lead = db.get(Lead, task.lead_id)
            if lead is not None:
                _activity(
                    db,
                    lead,
                    ActivityKind.TASK,
                    principal.id,
                    body=task.title,
                    data={"task_id": str(task.id), "action": "completed"},
                )
    db.commit()
    db.refresh(task)
    return task


# --------------------------------------------------------------------------- appointments


def create_appointment(
    db: Session, principal: Principal, lead: Lead, data: AppointmentCreate
) -> Appointment:
    ensure_manage(db, principal, lead)
    property_id = data.property_id or lead.property_id
    if data.property_id and data.property_id != lead.property_id:
        prop = db.get(Property, data.property_id)
        if prop is None or not manages(db, principal, prop):
            raise NotFoundError("Property not found", code="PROPERTY_NOT_FOUND")
    appointment = Appointment(
        lead_id=lead.id,
        property_id=property_id,
        organizer_id=principal.id,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        location_text=data.location_text,
        status=AppointmentStatus.SCHEDULED,
        notes=data.notes,
    )
    db.add(appointment)
    db.flush()
    _activity(
        db,
        lead,
        ActivityKind.APPOINTMENT,
        principal.id,
        data={
            "appointment_id": str(appointment.id),
            "starts_at": data.starts_at.isoformat(),
            "action": "scheduled",
        },
    )
    if lead.status_code in (CoreStatus.NEW, CoreStatus.CONTACTED, CoreStatus.QUALIFIED):
        previous = lead.status_code
        lead.status_code = CoreStatus.VIEWING
        _activity(
            db,
            lead,
            ActivityKind.STATUS_CHANGE,
            None,
            data={"from": previous, "to": CoreStatus.VIEWING.value, "auto": True},
        )
    events.emit(
        db,
        "appointment.scheduled",
        {"lead_id": str(lead.id), "appointment_id": str(appointment.id)},
    )
    db.commit()
    db.refresh(appointment)
    return appointment


def get_appointment_or_404(
    db: Session, principal: Principal, appointment_id: uuid.UUID
) -> tuple[Appointment, Lead]:
    appointment = db.get(Appointment, appointment_id)
    lead = db.get(Lead, appointment.lead_id) if appointment else None
    if appointment is None or lead is None or not policies.can_see_lead(db, principal, lead):
        raise NotFoundError("Appointment not found", code="APPOINTMENT_NOT_FOUND")
    return appointment, lead


def update_appointment(
    db: Session, principal: Principal, appointment: Appointment, lead: Lead, data: AppointmentUpdate
) -> Appointment:
    ensure_manage(db, principal, lead)
    fields = data.model_fields_set
    starts = data.starts_at if "starts_at" in fields and data.starts_at else appointment.starts_at
    ends = data.ends_at if "ends_at" in fields else appointment.ends_at
    if ends is not None and ends <= starts:
        raise AppError("ends_at must be after starts_at", code="VALIDATION_ERROR", status_code=422)
    appointment.starts_at, appointment.ends_at = starts, ends
    for field in ("location_text", "notes"):
        if field in fields:
            setattr(appointment, field, getattr(data, field))
    if data.status is not None and data.status != appointment.status:
        appointment.status = data.status
        _activity(
            db,
            lead,
            ActivityKind.APPOINTMENT,
            principal.id,
            data={"appointment_id": str(appointment.id), "action": data.status.value.lower()},
        )
    db.commit()
    db.refresh(appointment)
    return appointment


def list_appointments(
    db: Session, principal: Principal, *, start: datetime | None, end: datetime | None
) -> list[Appointment]:
    stmt = (
        select(Appointment)
        .join(Lead, Lead.id == Appointment.lead_id)
        .where(policies.lead_scope(db, principal))
    )
    if start:
        stmt = stmt.where(Appointment.starts_at >= start)
    if end:
        stmt = stmt.where(Appointment.starts_at <= end)
    return list(db.execute(stmt.order_by(Appointment.starts_at).limit(500)).scalars())


# --------------------------------------------------------------------------- conversations


def _conversation_for(
    db: Session,
    customer_id: uuid.UUID,
    prop: Property,
    lead: Lead,
    lister_id: uuid.UUID,
) -> Conversation:
    conv = db.execute(
        select(Conversation).where(
            Conversation.customer_user_id == customer_id, Conversation.property_id == prop.id
        )
    ).scalar_one_or_none()
    if conv is None:
        conv = Conversation(
            property_id=prop.id,
            lead_id=lead.id,
            customer_user_id=customer_id,
            lister_user_id=lister_id,
        )
        db.add(conv)
        db.flush()
    else:
        conv.lead_id = lead.id
    return conv


def _post_message(
    db: Session, conv: Conversation, sender_id: uuid.UUID, body: str, *, log_on_lead: bool
) -> Message:
    message = Message(conversation_id=conv.id, sender_id=sender_id, body=body)
    db.add(message)
    conv.last_message_at = _now()
    if log_on_lead and conv.lead_id:
        lead = db.get(Lead, conv.lead_id)
        if lead is not None:
            _activity(
                db,
                lead,
                ActivityKind.MESSAGE,
                sender_id,
                body=body,
                data={"conversation_id": str(conv.id)},
            )
    db.flush()
    return message


def can_access_conversation(db: Session, principal: Principal, conv: Conversation) -> bool:
    if conv.customer_user_id == principal.id or conv.lister_user_id == principal.id:
        return True
    if conv.lead_id:
        lead = db.get(Lead, conv.lead_id)
        return lead is not None and policies.can_see_lead(db, principal, lead)
    return False


def get_conversation_or_404(
    db: Session, principal: Principal, conversation_id: uuid.UUID
) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or not can_access_conversation(db, principal, conv):
        raise NotFoundError("Conversation not found", code="CONVERSATION_NOT_FOUND")
    return conv


def conversation_scope(db: Session, principal: Principal) -> Any:
    visible_leads = select(Lead.id).where(policies.lead_scope(db, principal))
    return or_(
        Conversation.customer_user_id == principal.id,
        Conversation.lister_user_id == principal.id,
        and_(Conversation.lead_id.is_not(None), Conversation.lead_id.in_(visible_leads)),
    )


def post_message(db: Session, principal: Principal, conv: Conversation, body: str) -> Message:
    is_customer = conv.customer_user_id == principal.id
    if not is_customer and not principal.has(Permission.LEADS_MANAGE):
        raise PermissionDeniedError("You cannot reply in this conversation")
    message = _post_message(db, conv, principal.id, body.strip(), log_on_lead=True)
    events.emit(
        db,
        "message.created",
        {
            "conversation_id": str(conv.id),
            "message_id": str(message.id),
            "sender_id": str(principal.id),
            "recipient_side": "lister" if is_customer else "customer",
            "customer_user_id": str(conv.customer_user_id),
            "lister_user_id": str(conv.lister_user_id) if conv.lister_user_id else None,
        },
    )
    db.commit()
    db.refresh(message)
    return message


def mark_read(db: Session, principal: Principal, conv: Conversation) -> None:
    """Mark the other side's messages as read."""
    now = _now()
    for message in db.execute(
        select(Message).where(
            Message.conversation_id == conv.id,
            Message.read_at.is_(None),
            Message.sender_id != principal.id,
        )
    ).scalars():
        message.read_at = now
    db.commit()


# --------------------------------------------------------------------------- dashboard


def dashboard(db: Session, principal: Principal) -> CrmDashboard:
    scope = policies.lead_scope(db, principal)
    now = _now()
    by_status = db.execute(
        select(Lead.status_code, func.count()).where(scope).group_by(Lead.status_code)
    ).all()
    counts = {code: n for code, n in by_status}
    terminal = {
        s.code: s for s in db.execute(select(LeadStatus).where(LeadStatus.is_terminal)).scalars()
    }
    won = sum(n for code, n in counts.items() if code in terminal and terminal[code].is_won)
    lost = sum(n for code, n in counts.items() if code in terminal and not terminal[code].is_won)
    total_open = sum(n for code, n in counts.items() if code not in terminal)
    new_7 = db.execute(
        select(func.count()).where(scope, Lead.created_at >= now - timedelta(days=7))
    ).scalar_one()
    overdue = db.execute(
        select(func.count()).where(scope, Lead.closed_at.is_(None), Lead.next_follow_up_at < now)
    ).scalar_one()
    task_scope = _task_scope(db, principal)
    end_of_day = now.replace(hour=23, minute=59, second=59)
    tasks_today = db.execute(
        select(func.count()).where(
            task_scope,
            CrmTask.completed_at.is_(None),
            CrmTask.due_at >= now,
            CrmTask.due_at <= end_of_day,
        )
    ).scalar_one()
    tasks_overdue = db.execute(
        select(func.count()).where(task_scope, CrmTask.completed_at.is_(None), CrmTask.due_at < now)
    ).scalar_one()
    upcoming = list_appointments(db, principal, start=now, end=now + timedelta(days=7))
    statuses = db.execute(select(LeadStatus).order_by(LeadStatus.sort_order)).scalars()
    return CrmDashboard(
        total_open=total_open,
        new_last_7_days=new_7,
        by_status=[StatusCount(code=s.code, count=counts.get(s.code, 0)) for s in statuses],
        overdue_follow_ups=overdue,
        tasks_due_today=tasks_today,
        tasks_overdue=tasks_overdue,
        upcoming_appointments=[AppointmentOut.model_validate(a) for a in upcoming[:10]],
        won=won,
        lost=lost,
        conversion_rate=round(won / (won + lost), 4) if won + lost else None,
    )
