"""Reports, moderation and verification queues, admin overview, system status,
error log and runtime settings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import events
from app.agencies.models import Agency, AgencyStatus
from app.ai.models import AIGeneration
from app.ai.service import quality_report
from app.audit import service as audit
from app.auth.deps import Principal, require_permission
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.core.rate_limit import rate_limit
from app.crm.models import Lead
from app.db.session import get_db
from app.moderation.models import ErrorEvent, Report, ReportReason, ReportStatus, ReportTarget
from app.properties import service as property_service
from app.properties.models import Property, PropertyVerification
from app.rbac.catalog import Permission
from app.system import settings_service
from app.users import service as user_service
from app.users.models import User, UserStatus

router = APIRouter(tags=["moderation"])

AUTO_FLAG_THRESHOLD = 3  # open reports that put a live listing back in the review queue


def _now() -> datetime:
    return datetime.now(UTC)


# --- schemas


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: ReportTarget
    target_id: uuid.UUID
    reason: ReportReason
    details: str | None = Field(default=None, max_length=2000)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    reason: str
    details: str | None
    status: str
    resolution_note: str | None
    created_at: datetime
    resolved_at: datetime | None


class AdminReportOut(ReportOut):
    reporter_id: uuid.UUID | None
    assigned_to_id: uuid.UUID | None
    target_label: str | None = None
    open_reports_on_target: int = 0


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["RESOLVED", "DISMISSED"]
    note: str = Field(min_length=3, max_length=2000)
    action: Literal["NONE", "SUSPEND_LISTING", "SUSPEND_USER"] = "NONE"
    resolve_all_for_target: bool = True


class QueueItem(BaseModel):
    property_id: uuid.UUID
    reference_code: str
    title_ar: str
    status: str
    needs_review: bool
    lister_id: uuid.UUID
    is_demo: bool
    submitted_at: datetime
    open_reports: int
    quality_score: int


class VerificationQueue(BaseModel):
    listings: list[QueueItem]
    agencies: list[dict[str, Any]]


class AdminStats(BaseModel):
    users_total: int
    users_by_status: dict[str, int]
    users_new_7d: int
    listings_by_status: dict[str, int]
    listings_demo: int
    pending_review: int
    agencies_by_status: dict[str, int]
    reports_open: int
    leads_total: int
    inquiries_7d: int
    ai_calls_24h: int
    ai_fallbacks_24h: int
    errors_24h: int


class SettingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Any


# --- reports (users)


def _validate_target(db: Session, principal: Principal, body: ReportIn) -> None:
    if body.target_type == ReportTarget.PROPERTY:
        prop = db.get(Property, body.target_id)
        if prop is None or not prop.is_public:
            raise NotFoundError("Listing not found", code="PROPERTY_NOT_FOUND")
        if principal.id in (prop.lister_id, prop.agent_id):
            raise AppError("You cannot report your own listing", code="OWN_TARGET", status_code=422)
    elif body.target_type == ReportTarget.USER:
        user = db.get(User, body.target_id)
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User not found", code="USER_NOT_FOUND")
        if user.id == principal.id:
            raise AppError("You cannot report yourself", code="OWN_TARGET", status_code=422)
    else:
        agency = db.get(Agency, body.target_id)
        if agency is None or agency.deleted_at is not None:
            raise NotFoundError("Agency not found", code="AGENCY_NOT_FOUND")


@router.post(
    "/reports",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("report", limit=20, window=3600))],
)
def create_report(
    body: ReportIn,
    principal: Principal = Depends(require_permission(Permission.REPORTS_CREATE)),
    db: Session = Depends(get_db),
) -> ReportOut:
    _validate_target(db, principal, body)
    report = Report(
        target_type=body.target_type,
        target_id=body.target_id,
        reason=body.reason,
        details=(body.details or "").strip() or None,
        reporter_id=principal.id,
        status=ReportStatus.OPEN,
    )
    db.add(report)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "You already reported this; it is being reviewed", code="ALREADY_REPORTED"
        ) from exc
    if body.target_type == ReportTarget.PROPERTY:
        open_count = db.execute(
            select(func.count()).where(
                Report.target_type == ReportTarget.PROPERTY,
                Report.target_id == body.target_id,
                Report.status.in_([ReportStatus.OPEN, ReportStatus.IN_REVIEW]),
            )
        ).scalar_one()
        if open_count >= AUTO_FLAG_THRESHOLD:
            prop = db.get(Property, body.target_id)
            if prop is not None and not prop.needs_review:
                prop.needs_review = True  # back into the moderation queue; stays published
    audit.record(
        db,
        "report.created",
        actor_id=principal.id,
        resource_type="report",
        resource_id=report.id,
        data={
            "target_type": body.target_type.value,
            "target_id": str(body.target_id),
            "reason": body.reason.value,
        },
    )
    events.emit(
        db,
        "listing.reported" if body.target_type == ReportTarget.PROPERTY else "report.created",
        {
            "report_id": str(report.id),
            "target_type": body.target_type.value,
            "target_id": str(body.target_id),
            "reason": body.reason.value,
        },
    )
    db.commit()
    db.refresh(report)
    return ReportOut.model_validate(report)


@router.get("/me/reports", response_model=list[ReportOut])
def my_reports(
    principal: Principal = Depends(require_permission(Permission.REPORTS_CREATE)),
    db: Session = Depends(get_db),
) -> list[ReportOut]:
    rows = db.execute(
        select(Report).where(Report.reporter_id == principal.id).order_by(Report.created_at.desc())
    ).scalars()
    return [ReportOut.model_validate(r) for r in rows]


# --- reports (moderators)

_reviewer = require_permission(Permission.REPORTS_REVIEW)


def _labels(db: Session, reports: list[Report]) -> dict[tuple[str, uuid.UUID], str]:
    labels: dict[tuple[str, uuid.UUID], str] = {}
    by_type: dict[str, set[uuid.UUID]] = {}
    for r in reports:
        by_type.setdefault(r.target_type, set()).add(r.target_id)
    if ids := by_type.get(ReportTarget.PROPERTY):
        for p in db.execute(
            select(Property.id, Property.reference_code, Property.title_ar).where(
                Property.id.in_(ids)
            )
        ):
            labels[(ReportTarget.PROPERTY, p.id)] = f"{p.reference_code} · {p.title_ar}"
    if ids := by_type.get(ReportTarget.USER):
        for u in db.execute(select(User.id, User.full_name).where(User.id.in_(ids))):
            labels[(ReportTarget.USER, u.id)] = u.full_name
    if ids := by_type.get(ReportTarget.AGENCY):
        for a in db.execute(select(Agency.id, Agency.name_ar).where(Agency.id.in_(ids))):
            labels[(ReportTarget.AGENCY, a.id)] = a.name_ar
    return labels


@router.get("/admin/reports", response_model=Page[AdminReportOut])
def admin_reports(
    report_status: str | None = Query(default="OPEN", alias="status", max_length=10),
    target_type: ReportTarget | None = None,
    params: PageParams = Depends(page_params),
    _: Principal = Depends(_reviewer),
    db: Session = Depends(get_db),
) -> Page[AdminReportOut]:
    stmt = select(Report)
    if report_status and report_status != "ALL":
        stmt = stmt.where(Report.status == report_status)
    if target_type:
        stmt = stmt.where(Report.target_type == target_type)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(Report.created_at).offset(params.offset).limit(params.page_size)
        ).scalars()
    )
    labels = _labels(db, rows)
    open_counts = (
        dict(
            (tuple(row[:2]), int(row[2]))
            for row in db.execute(
                select(Report.target_type, Report.target_id, func.count())
                .where(
                    Report.target_id.in_({r.target_id for r in rows}),
                    Report.status.in_([ReportStatus.OPEN, ReportStatus.IN_REVIEW]),
                )
                .group_by(Report.target_type, Report.target_id)
            ).all()
        )
        if rows
        else {}
    )
    items = []
    for r in rows:
        out = AdminReportOut.model_validate(r, from_attributes=True)
        out.target_label = labels.get((r.target_type, r.target_id))
        out.open_reports_on_target = open_counts.get((r.target_type, r.target_id), 0)
        items.append(out)
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)


def _get_report(db: Session, report_id: uuid.UUID) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report not found", code="REPORT_NOT_FOUND")
    return report


@router.post("/admin/reports/{report_id}/assign", response_model=AdminReportOut)
def assign_report(
    report_id: uuid.UUID, principal: Principal = Depends(_reviewer), db: Session = Depends(get_db)
) -> AdminReportOut:
    report = _get_report(db, report_id)
    if report.status not in (ReportStatus.OPEN, ReportStatus.IN_REVIEW):
        raise AppError("Report is closed", code="REPORT_CLOSED", status_code=409)
    report.status = ReportStatus.IN_REVIEW
    report.assigned_to_id = principal.id
    audit.record(
        db, "report.assigned", actor_id=principal.id, resource_type="report", resource_id=report.id
    )
    db.commit()
    db.refresh(report)
    return AdminReportOut.model_validate(report, from_attributes=True)


@router.post("/admin/reports/{report_id}/resolve", response_model=AdminReportOut)
def resolve_report(
    report_id: uuid.UUID,
    body: ResolveIn,
    principal: Principal = Depends(_reviewer),
    db: Session = Depends(get_db),
) -> AdminReportOut:
    report = _get_report(db, report_id)
    if report.status not in (ReportStatus.OPEN, ReportStatus.IN_REVIEW):
        raise AppError("Report is closed", code="REPORT_CLOSED", status_code=409)
    if body.outcome == "RESOLVED" and body.action == "SUSPEND_LISTING":
        if report.target_type != ReportTarget.PROPERTY:
            raise AppError("Not a listing report", code="INVALID_ACTION", status_code=422)
        prop = property_service.get_property_or_404(db, report.target_id, lock=True)
        if prop.status != "SUSPENDED":
            property_service.moderate(db, principal, prop, "SUSPEND", body.note, "REPORTED")
    elif body.outcome == "RESOLVED" and body.action == "SUSPEND_USER":
        if report.target_type != ReportTarget.USER:
            raise AppError("Not a user report", code="INVALID_ACTION", status_code=422)
        if not principal.has(Permission.USERS_SUSPEND):
            raise AppError("You cannot suspend users", code="PERMISSION_DENIED", status_code=403)
        target = user_service.get_user_or_404(db, report.target_id)
        if target.status != UserStatus.SUSPENDED:
            user_service.suspend_user(db, principal, target, body.note)
    targets = [report]
    if body.resolve_all_for_target:
        targets = list(
            db.execute(
                select(Report).where(
                    Report.target_type == report.target_type,
                    Report.target_id == report.target_id,
                    Report.status.in_([ReportStatus.OPEN, ReportStatus.IN_REVIEW]),
                )
            ).scalars()
        )
    now = _now()
    for r in targets:
        r.status = body.outcome
        r.resolution_note = body.note.strip()
        r.resolved_by_id = principal.id
        r.resolved_at = now
    if report.target_type == ReportTarget.PROPERTY and body.outcome == "DISMISSED":
        flagged = db.get(Property, report.target_id)
        if flagged is not None and flagged.status == "APPROVED":
            flagged.needs_review = False
    audit.record(
        db,
        f"report.{body.outcome.lower()}",
        actor_id=principal.id,
        resource_type="report",
        resource_id=report.id,
        data={"action": body.action, "closed": len(targets)},
    )
    events.emit(
        db,
        "report.resolved",
        {
            "report_id": str(report.id),
            "outcome": body.outcome,
            "action": body.action,
            "reporter_ids": [str(r.reporter_id) for r in targets if r.reporter_id],
        },
    )
    db.commit()
    db.refresh(report)
    return AdminReportOut.model_validate(report, from_attributes=True)


# --- queues

_moderator = require_permission(Permission.PROPERTIES_MODERATE)


def _queue_items(db: Session, props: list[Property]) -> list[QueueItem]:
    if not props:
        return []
    reports = dict(
        (row[0], int(row[1]))
        for row in db.execute(
            select(Report.target_id, func.count())
            .where(
                Report.target_type == ReportTarget.PROPERTY,
                Report.target_id.in_([p.id for p in props]),
                Report.status.in_([ReportStatus.OPEN, ReportStatus.IN_REVIEW]),
            )
            .group_by(Report.target_id)
        ).all()
    )
    return [
        QueueItem(
            property_id=p.id,
            reference_code=p.reference_code,
            title_ar=p.title_ar,
            status=p.status,
            needs_review=p.needs_review,
            lister_id=p.lister_id,
            is_demo=p.is_demo,
            submitted_at=p.updated_at,
            open_reports=reports.get(p.id, 0),
            quality_score=int(quality_report(p)["score"]),
        )
        for p in props
    ]


@router.get("/admin/moderation/queue", response_model=Page[QueueItem])
def moderation_queue(
    params: PageParams = Depends(page_params),
    _: Principal = Depends(_moderator),
    db: Session = Depends(get_db),
) -> Page[QueueItem]:
    """Listings awaiting review, plus live listings flagged by edits or reports. Oldest first."""
    stmt = select(Property).where(
        Property.deleted_at.is_(None),
        or_(
            Property.status == "PENDING_REVIEW",
            (Property.status == "APPROVED") & Property.needs_review.is_(True),
        ),
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(Property.updated_at, Property.id)
            .offset(params.offset)
            .limit(params.page_size)
        ).scalars()
    )
    return Page(
        items=_queue_items(db, rows), total=total, page=params.page, page_size=params.page_size
    )


@router.get("/admin/verification/queue", response_model=VerificationQueue)
def verification_queue(
    principal: Principal = Depends(require_permission(Permission.PROPERTIES_VERIFY)),
    db: Session = Depends(get_db),
) -> VerificationQueue:
    verified = select(PropertyVerification.property_id)
    listings = list(
        db.execute(
            select(Property)
            .where(
                Property.status == "APPROVED",
                Property.deleted_at.is_(None),
                Property.verified_at.is_(None),
                Property.is_demo.is_(False),
                Property.id.not_in(verified),
            )
            .order_by(Property.published_at)
            .limit(50)
        ).scalars()
    )
    agencies = []
    if principal.has(Permission.AGENCIES_VERIFY):
        agencies = [
            {"id": str(a.id), "name_ar": a.name_ar, "created_at": a.created_at.isoformat()}
            for a in db.execute(
                select(Agency)
                .where(
                    Agency.status == AgencyStatus.PENDING_VERIFICATION, Agency.deleted_at.is_(None)
                )
                .order_by(Agency.created_at)
                .limit(50)
            ).scalars()
        ]
    return VerificationQueue(listings=_queue_items(db, listings), agencies=agencies)


# --- overview, system, errors, settings

_admin = require_permission(Permission.ANALYTICS_ALL)


def _grouped(db: Session, column: Any, *where: Any) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).where(*where).group_by(column)).all()
    return {str(k): int(v) for k, v in rows}


@router.get("/admin/stats", response_model=AdminStats)
def admin_stats(_: Principal = Depends(_admin), db: Session = Depends(get_db)) -> AdminStats:
    now = _now()
    day, week = now - timedelta(days=1), now - timedelta(days=7)
    from app.crm.models import Inquiry

    def count(*where: Any, model: Any = None) -> int:
        stmt = select(func.count())
        if model is not None:
            stmt = stmt.select_from(model)
        return int(db.execute(stmt.where(*where)).scalar_one())

    listings = _grouped(db, Property.status, Property.deleted_at.is_(None))
    return AdminStats(
        users_total=count(User.deleted_at.is_(None), model=User),
        users_by_status=_grouped(db, User.status, User.deleted_at.is_(None)),
        users_new_7d=count(User.created_at >= week, model=User),
        listings_by_status=listings,
        listings_demo=count(
            Property.is_demo.is_(True), Property.deleted_at.is_(None), model=Property
        ),
        pending_review=listings.get("PENDING_REVIEW", 0),
        agencies_by_status=_grouped(db, Agency.status, Agency.deleted_at.is_(None)),
        reports_open=count(Report.status.in_(["OPEN", "IN_REVIEW"]), model=Report),
        leads_total=count(model=Lead),
        inquiries_7d=count(Inquiry.created_at >= week, model=Inquiry),
        ai_calls_24h=count(AIGeneration.created_at >= day, model=AIGeneration),
        ai_fallbacks_24h=count(
            AIGeneration.created_at >= day, AIGeneration.status == "FALLBACK", model=AIGeneration
        ),
        errors_24h=count(ErrorEvent.created_at >= day, model=ErrorEvent),
    )


class ErrorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: str | None
    method: str | None
    path: str | None
    error_type: str
    created_at: datetime


@router.get("/admin/errors", response_model=Page[ErrorOut])
def admin_errors(
    params: PageParams = Depends(page_params),
    _: Principal = Depends(_admin),
    db: Session = Depends(get_db),
) -> Page[ErrorOut]:
    total = db.execute(select(func.count()).select_from(ErrorEvent)).scalar_one()
    rows = db.execute(
        select(ErrorEvent)
        .order_by(ErrorEvent.created_at.desc())
        .offset(params.offset)
        .limit(params.page_size)
    ).scalars()
    return Page(
        items=[ErrorOut.model_validate(r) for r in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/admin/system")
def admin_system(
    request: Request, _: Principal = Depends(_admin), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.core.client_ip import client_ip
    from app.core.config import get_settings

    settings = get_settings()
    info: dict[str, Any] = {"environment": settings.app_env, "ai_provider": settings.ai_provider}
    # Proxy chain as received, so operators can set TRUSTED_PROXY_HOPS correctly.
    info["request_network"] = {
        "peer": request.client.host if request.client else None,
        "x_forwarded_for": request.headers.get("x-forwarded-for"),
        "trusted_proxy_hops": settings.trusted_proxy_hops,
        "resolved_client_ip": client_ip(request),
    }
    try:
        db.execute(text("SELECT 1"))
        info["database"] = "ok"
        info["postgis"] = db.execute(text("SELECT postgis_lib_version()")).scalar_one()
        info["migration"] = db.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
    except Exception:
        info["database"] = "error"
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_timeout=2)
        client.ping()
        info["redis"] = "ok"
        queue_length: Any = client.llen("celery")
        info["queue_length"] = int(queue_length)
    except Exception:
        info["redis"] = "unavailable"
        info["queue_length"] = None
    return info


@router.get("/settings/public")
def public_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    return settings_service.all_settings(db, public_only=True)


@router.get("/admin/settings")
def get_settings_admin(
    _: Principal = Depends(require_permission(Permission.SETTINGS_MANAGE)),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    values = settings_service.all_settings(db)
    return [
        {
            "key": key,
            "value": values[key],
            "default": spec.default,
            "description": spec.description,
            "public": spec.public,
        }
        for key, spec in settings_service.SETTINGS.items()
    ]


@router.put("/admin/settings/{key}")
def put_setting(
    key: str,
    body: SettingIn,
    principal: Principal = Depends(require_permission(Permission.SETTINGS_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    value = settings_service.set_setting(db, key, body.value)
    audit.record(
        db,
        "settings.updated",
        actor_id=principal.id,
        resource_type="setting",
        resource_id=key,
        data={"value": str(value)[:200]},
    )
    db.commit()
    return {"key": key, "value": value}
