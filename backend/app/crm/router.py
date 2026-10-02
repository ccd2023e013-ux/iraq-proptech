"""/api/v1 CRM: inquiries, leads, pipeline, customers, tasks, appointments, conversations."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.auth.deps import (
    Principal,
    get_principal,
    require_any_permission,
    require_permission,
    require_verified_email,
)
from app.core.errors import AppError, PermissionDeniedError
from app.core.pagination import Page, PageParams, page_params
from app.core.rate_limit import limit_identifier, rate_limit
from app.crm import service
from app.crm.models import Conversation, CoreStatus, Lead, LeadStatus, Message
from app.crm.schemas import (
    ActivityIn,
    ActivityOut,
    AppointmentCreate,
    AppointmentOut,
    AppointmentUpdate,
    ConversationOut,
    CrmDashboard,
    CustomerOut,
    CustomerUpdate,
    InquiryCreate,
    InquiryOut,
    LeadCreate,
    LeadOut,
    LeadStatusOut,
    LeadStatusUpsert,
    LeadUpdate,
    MessageIn,
    MessageOut,
    MyInquiryOut,
    PersonRef,
    PropertyRef,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from app.db.session import get_db
from app.properties.models import Property
from app.properties.service import get_property_or_404
from app.rbac.catalog import Permission

router = APIRouter(tags=["crm"])

_crm_reader = require_any_permission(
    Permission.LEADS_READ_OWN, Permission.LEADS_READ_AGENCY, Permission.LEADS_READ_ANY
)
_crm_manager = require_permission(Permission.LEADS_MANAGE)

# Core stages whose meaning the system relies on; they can be renamed/reordered only.
_LOCKED_ACTIVE = {CoreStatus.NEW.value, CoreStatus.WON.value, CoreStatus.LOST.value}


# --------------------------------------------------------------------------- inquiries


@router.post(
    "/properties/{property_id}/inquiries",
    response_model=InquiryOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("inquiry", limit=20, window=3600))],
)
def send_inquiry(
    property_id: uuid.UUID,
    body: InquiryCreate,
    principal: Principal = Depends(require_verified_email),
    db: Session = Depends(get_db),
) -> InquiryOut:
    if not principal.has(Permission.INQUIRIES_CREATE):
        raise PermissionDeniedError("You cannot send inquiries")
    limit_identifier("inquiry-user", str(principal.id), limit=10, window=3600)
    prop = get_property_or_404(db, property_id)
    inquiry = service.create_inquiry(db, principal, prop, body)
    return InquiryOut.model_validate(inquiry)


@router.get("/me/inquiries", response_model=Page[MyInquiryOut])
def my_inquiries(
    params: PageParams = Depends(page_params),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> Page[MyInquiryOut]:
    rows, props, total = service.my_inquiries(
        db, principal, offset=params.offset, limit=params.page_size
    )
    items = []
    for r in rows:
        prop = props.get(r.property_id)
        out = MyInquiryOut.model_validate(r)
        if prop is not None:
            out.property_title_ar = prop.title_ar
            out.property_title_en = prop.title_en
            out.property_reference = prop.reference_code
        items.append(out)
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)


# --------------------------------------------------------------------------- statuses


@router.get("/crm/statuses", response_model=list[LeadStatusOut])
def statuses(
    _: Principal = Depends(_crm_reader), db: Session = Depends(get_db)
) -> list[LeadStatusOut]:
    rows = db.execute(select(LeadStatus).order_by(LeadStatus.sort_order, LeadStatus.code))
    return [LeadStatusOut.model_validate(s) for s in rows.scalars()]


@router.put("/admin/crm/statuses/{code}", response_model=LeadStatusOut)
def upsert_status(
    code: str,
    body: LeadStatusUpsert,
    principal: Principal = Depends(require_permission(Permission.LEADS_CONFIGURE)),
    db: Session = Depends(get_db),
) -> LeadStatusOut:
    code = code.strip().upper()
    if not code.replace("_", "").isalnum() or len(code) > 24:
        raise AppError("Status codes are A–Z, 0–9 and _", code="VALIDATION_ERROR", status_code=422)
    status_row = db.get(LeadStatus, code)
    if status_row is None:
        status_row = LeadStatus(
            code=code,
            is_system=False,
            is_terminal=body.is_terminal,
            is_won=body.is_won and body.is_terminal,
        )
        db.add(status_row)
    elif status_row.is_system:
        if not body.is_active and code in _LOCKED_ACTIVE:
            raise AppError(
                "This core stage cannot be deactivated", code="STATUS_LOCKED", status_code=422
            )
    else:
        status_row.is_terminal = body.is_terminal
        status_row.is_won = body.is_won and body.is_terminal
    if not body.is_active:
        in_use = db.execute(
            select(func.count()).where(Lead.status_code == code, Lead.closed_at.is_(None))
        ).scalar_one()
        if in_use:
            raise AppError(
                "Open leads still use this stage; move them first",
                code="STATUS_IN_USE",
                status_code=409,
            )
    status_row.name_ar = body.name_ar.strip()
    status_row.name_en = body.name_en.strip()
    status_row.sort_order = body.sort_order
    status_row.is_active = body.is_active
    audit.record(
        db,
        "crm.status_configured",
        actor_id=principal.id,
        resource_type="lead_status",
        resource_id=code,
        data={"active": body.is_active},
    )
    db.commit()
    db.refresh(status_row)
    return LeadStatusOut.model_validate(status_row)


# --------------------------------------------------------------------------- leads


@router.get("/crm/leads", response_model=Page[LeadOut])
def list_leads(
    status_code: str | None = Query(default=None, alias="status", max_length=24),
    assigned_to_id: uuid.UUID | None = None,
    property_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, max_length=100),
    overdue: bool = False,
    open_only: bool = False,
    params: PageParams = Depends(page_params),
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> Page[LeadOut]:
    rows, total = service.list_leads(
        db,
        principal,
        status=status_code,
        assigned_to_id=assigned_to_id,
        property_id=property_id,
        q=q,
        overdue=overdue,
        open_only=open_only,
        offset=params.offset,
        limit=params.page_size,
    )
    return Page(
        items=service.leads_out(db, principal, rows),
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/crm/leads", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(
    body: LeadCreate, principal: Principal = Depends(_crm_manager), db: Session = Depends(get_db)
) -> LeadOut:
    lead = service.create_lead(db, principal, body)
    return service.leads_out(db, principal, [lead])[0]


@router.get("/crm/leads/{lead_id}", response_model=LeadOut)
def get_lead(
    lead_id: uuid.UUID, principal: Principal = Depends(_crm_reader), db: Session = Depends(get_db)
) -> LeadOut:
    lead = service.get_lead_or_404(db, principal, lead_id)
    return service.leads_out(db, principal, [lead])[0]


@router.patch("/crm/leads/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: uuid.UUID,
    body: LeadUpdate,
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> LeadOut:
    lead = service.get_lead_or_404(db, principal, lead_id)
    lead = service.update_lead(db, principal, lead, body)
    return service.leads_out(db, principal, [lead])[0]


@router.get("/crm/leads/{lead_id}/activities", response_model=list[ActivityOut])
def lead_activities(
    lead_id: uuid.UUID, principal: Principal = Depends(_crm_reader), db: Session = Depends(get_db)
) -> list[ActivityOut]:
    return service.activities(db, service.get_lead_or_404(db, principal, lead_id))


@router.post(
    "/crm/leads/{lead_id}/activities",
    response_model=ActivityOut,
    status_code=status.HTTP_201_CREATED,
)
def add_activity(
    lead_id: uuid.UUID,
    body: ActivityIn,
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> ActivityOut:
    lead = service.get_lead_or_404(db, principal, lead_id)
    entry = service.add_activity(db, principal, lead, body)
    return ActivityOut(
        id=entry.id,
        kind=entry.kind,
        body=entry.body,
        data=entry.data,
        actor=PersonRef(id=principal.id, full_name=principal.user.full_name),
        occurred_at=entry.occurred_at,
    )


@router.post(
    "/crm/leads/{lead_id}/appointments",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_appointment(
    lead_id: uuid.UUID,
    body: AppointmentCreate,
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    lead = service.get_lead_or_404(db, principal, lead_id)
    return AppointmentOut.model_validate(service.create_appointment(db, principal, lead, body))


# --------------------------------------------------------------------------- appointments


@router.get("/crm/appointments", response_model=list[AppointmentOut])
def list_appointments(
    start: datetime | None = None,
    end: datetime | None = None,
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> list[AppointmentOut]:
    rows = service.list_appointments(db, principal, start=start, end=end)
    return [AppointmentOut.model_validate(a) for a in rows]


@router.patch("/crm/appointments/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: uuid.UUID,
    body: AppointmentUpdate,
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> AppointmentOut:
    appointment, lead = service.get_appointment_or_404(db, principal, appointment_id)
    updated = service.update_appointment(db, principal, appointment, lead, body)
    return AppointmentOut.model_validate(updated)


# --------------------------------------------------------------------------- tasks


@router.get("/crm/tasks", response_model=Page[TaskOut])
def list_tasks(
    task_status: Literal["open", "done", "overdue", "today", "all"] = Query(
        default="open", alias="status"
    ),
    lead_id: uuid.UUID | None = None,
    params: PageParams = Depends(page_params),
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> Page[TaskOut]:
    rows, total = service.list_tasks(
        db,
        principal,
        status=task_status,
        lead_id=lead_id,
        offset=params.offset,
        limit=params.page_size,
    )
    return Page(
        items=service.tasks_out(db, rows), total=total, page=params.page, page_size=params.page_size
    )


@router.post("/crm/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    body: TaskCreate, principal: Principal = Depends(_crm_reader), db: Session = Depends(get_db)
) -> TaskOut:
    return service.tasks_out(db, [service.create_task(db, principal, body)])[0]


@router.patch("/crm/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> TaskOut:
    task = service.get_task_or_404(db, principal, task_id)
    return service.tasks_out(db, [service.update_task(db, principal, task, body)])[0]


# --------------------------------------------------------------------------- customers


@router.get("/crm/customers", response_model=Page[CustomerOut])
def list_customers(
    q: str | None = Query(default=None, max_length=100),
    params: PageParams = Depends(page_params),
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> Page[CustomerOut]:
    items, total = service.list_customers(
        db, principal, q=q, offset=params.offset, limit=params.page_size
    )
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)


@router.get("/crm/customers/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: uuid.UUID,
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> CustomerOut:
    customer = service.get_customer_or_404(db, principal, customer_id)
    count = db.execute(select(func.count()).where(Lead.customer_id == customer.id)).scalar_one()
    return service.customer_out(customer, count)


@router.patch("/crm/customers/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    principal: Principal = Depends(_crm_reader),
    db: Session = Depends(get_db),
) -> CustomerOut:
    customer = service.get_customer_or_404(db, principal, customer_id)
    return service.customer_out(service.update_customer(db, principal, customer, body))


# --------------------------------------------------------------------------- dashboard


@router.get("/crm/dashboard", response_model=CrmDashboard)
def dashboard(
    principal: Principal = Depends(_crm_reader), db: Session = Depends(get_db)
) -> CrmDashboard:
    return service.dashboard(db, principal)


# --------------------------------------------------------------------------- conversations


def _conversation_out(
    db: Session, principal: Principal, convs: list[Conversation]
) -> list[ConversationOut]:
    if not convs:
        return []
    ids = [c.id for c in convs]
    last = {
        row.conversation_id: row.body
        for row in db.execute(
            select(Message.conversation_id, Message.body)
            .distinct(Message.conversation_id)
            .where(Message.conversation_id.in_(ids))
            .order_by(Message.conversation_id, Message.created_at.desc())
        )
    }
    unread = dict(
        db.execute(
            select(Message.conversation_id, func.count())
            .where(
                Message.conversation_id.in_(ids),
                Message.read_at.is_(None),
                Message.sender_id != principal.id,
            )
            .group_by(Message.conversation_id)
        ).all()
    )
    prop_ids = {c.property_id for c in convs if c.property_id}
    props = (
        {p.id: p for p in db.execute(select(Property).where(Property.id.in_(prop_ids))).scalars()}
        if prop_ids
        else {}
    )
    people = service.people_refs(
        db, [x for c in convs for x in (c.customer_user_id, c.lister_user_id)]
    )
    out = []
    for c in convs:
        prop = props.get(c.property_id) if c.property_id else None
        out.append(
            ConversationOut(
                id=c.id,
                property=PropertyRef(
                    id=prop.id,
                    reference_code=prop.reference_code,
                    title_ar=prop.title_ar,
                    title_en=prop.title_en,
                    status=prop.status,
                )
                if prop
                else None,
                lead_id=c.lead_id if c.customer_user_id != principal.id else None,
                customer=people.get(c.customer_user_id),
                lister=people.get(c.lister_user_id) if c.lister_user_id else None,
                last_message_at=c.last_message_at,
                last_message=last.get(c.id),
                unread=unread.get(c.id, 0),
                role="customer" if c.customer_user_id == principal.id else "lister",
            )
        )
    return out


@router.get("/me/conversations", response_model=list[ConversationOut])
def my_conversations(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[ConversationOut]:
    convs = list(
        db.execute(
            select(Conversation)
            .where(service.conversation_scope(db, principal))
            .order_by(Conversation.last_message_at.desc().nulls_last())
            .limit(200)
        ).scalars()
    )
    return _conversation_out(db, principal, convs)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def conversation_messages(
    conversation_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    conv = service.get_conversation_or_404(db, principal, conversation_id)
    rows = list(
        db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at, Message.id)
            .limit(1000)
        ).scalars()
    )
    people = service.people_refs(db, [m.sender_id for m in rows])
    out = [
        MessageOut(
            id=m.id,
            sender=people.get(m.sender_id) if m.sender_id else None,
            body=m.body,
            created_at=m.created_at,
            read_at=m.read_at,
            mine=m.sender_id == principal.id,
        )
        for m in rows
    ]
    service.mark_read(db, principal, conv)
    return out


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("message", limit=60, window=600))],
)
def send_message(
    conversation_id: uuid.UUID,
    body: MessageIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> MessageOut:
    conv = service.get_conversation_or_404(db, principal, conversation_id)
    message = service.post_message(db, principal, conv, body.body)
    return MessageOut(
        id=message.id,
        sender=PersonRef(id=principal.id, full_name=principal.user.full_name),
        body=message.body,
        created_at=message.created_at,
        read_at=None,
        mine=True,
    )
