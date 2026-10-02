"""Analytics recording (views, searches) and dashboard aggregation.

Everything reported here is *actual platform activity*. DEMO listings are
excluded unless explicitly requested, and AI estimates are never mixed in.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Any, Literal

from sqlalchemy import ColumnElement, and_, delete, func, or_, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.agencies.models import AgencyMember
from app.analytics.models import PropertyViewDaily, PropertyViewVisitor, SearchStatDaily
from app.core.config import get_settings
from app.crm.models import Inquiry, Lead, LeadActivity, LeadStatus
from app.favorites import Favorite
from app.geo.models import Governorate
from app.properties.models import Property
from app.search.schemas import SearchFilters
from app.users.models import User

log = logging.getLogger(__name__)

VISITOR_RETENTION_DAYS = 2
MAX_RANGE_DAYS = 366
Scope = Literal["me", "agency", "platform", "property"]


def local_tz() -> timezone:
    return timezone(timedelta(minutes=get_settings().analytics_utc_offset_minutes))


def today() -> date:
    return datetime.now(local_tz()).date()


def _visitor_hash(day: date, key: str) -> str:
    secret = get_settings().jwt_secret.encode()
    salt = hmac.new(secret, f"analytics:{day.isoformat()}".encode(), hashlib.sha256).digest()
    return hmac.new(salt, key.encode(), hashlib.sha256).hexdigest()


# --- recording ---------------------------------------------------------------


def record_view(db: Session, property_id: uuid.UUID, visitor_key: str) -> bool:
    """Count one unique visitor per listing per day. Returns True if counted."""
    day = today()
    inserted = db.execute(
        insert(PropertyViewVisitor)
        .values(day=day, property_id=property_id, visitor_hash=_visitor_hash(day, visitor_key))
        .on_conflict_do_nothing()
        .returning(PropertyViewVisitor.day)
    ).first()
    if inserted is None:
        return False
    stmt = insert(PropertyViewDaily).values(property_id=property_id, day=day, views=1)
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=[PropertyViewDaily.property_id, PropertyViewDaily.day],
            set_={"views": PropertyViewDaily.views + 1},
        )
    )
    return True


def record_search(db: Session, filters: SearchFilters, total: int) -> None:
    """Aggregate-only search statistics. Never raises into the search request."""
    try:
        with db.begin_nested():
            stmt = insert(SearchStatDaily).values(
                day=today(),
                governorate_id=str(filters.governorate_id) if filters.governorate_id else "",
                purpose=filters.purpose.value if filters.purpose else "",
                searches=1,
                zero_results=1 if total == 0 else 0,
            )
            db.execute(
                stmt.on_conflict_do_update(
                    index_elements=[
                        SearchStatDaily.day,
                        SearchStatDaily.governorate_id,
                        SearchStatDaily.purpose,
                    ],
                    set_={
                        "searches": SearchStatDaily.searches + 1,
                        "zero_results": SearchStatDaily.zero_results + stmt.excluded.zero_results,
                    },
                )
            )
        db.commit()
    except Exception:  # analytics must never break search
        log.warning("search statistics not recorded", exc_info=True)
        db.rollback()


def purge_visitors(db: Session) -> dict[str, Any]:
    cutoff = today() - timedelta(days=VISITOR_RETENTION_DAYS)
    result = db.execute(delete(PropertyViewVisitor).where(PropertyViewVisitor.day < cutoff))
    db.commit()
    return {"purged": int(getattr(result, "rowcount", 0) or 0)}


# --- aggregation -------------------------------------------------------------


@dataclass(frozen=True)
class Range:
    start: date
    end: date  # inclusive

    @property
    def start_at(self) -> datetime:
        return datetime.combine(self.start, time(), local_tz()).astimezone(UTC)

    @property
    def end_at(self) -> datetime:
        return datetime.combine(self.end + timedelta(days=1), time(), local_tz()).astimezone(UTC)

    def days(self) -> list[date]:
        return [self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1)]


@dataclass(frozen=True)
class ScopeSpec:
    kind: Scope
    user_id: uuid.UUID | None = None
    agency_id: uuid.UUID | None = None
    property_id: uuid.UUID | None = None
    include_demo: bool = False

    def properties(self) -> ColumnElement[bool]:
        base: ColumnElement[bool] = Property.deleted_at.is_(None)
        if not self.include_demo and self.kind != "property":
            base = and_(base, Property.is_demo.is_(False))
        if self.kind == "me":
            return and_(
                base, or_(Property.lister_id == self.user_id, Property.agent_id == self.user_id)
            )
        if self.kind == "agency":
            return and_(base, Property.agency_id == self.agency_id)
        if self.kind == "property":
            return Property.id == self.property_id
        return base

    def leads(self) -> ColumnElement[bool]:
        if self.kind == "me":
            return or_(Lead.owner_user_id == self.user_id, Lead.assigned_to_id == self.user_id)
        if self.kind == "agency":
            return Lead.agency_id == self.agency_id
        if self.kind == "property":
            return Lead.property_id == self.property_id
        return true()


def _local_day(column: Any) -> Any:
    offset = get_settings().analytics_utc_offset_minutes
    return func.date(func.timezone("UTC", column) + timedelta(minutes=offset))


def _series(rows: Any) -> dict[date, int]:
    return {d: int(n) for d, n in rows}


def overview(db: Session, scope: ScopeSpec, rng: Range) -> dict[str, Any]:
    props = scope.properties()
    leads_scope = scope.leads()

    views_by_day = _series(
        db.execute(
            select(PropertyViewDaily.day, func.sum(PropertyViewDaily.views))
            .join(Property, Property.id == PropertyViewDaily.property_id)
            .where(props, PropertyViewDaily.day.between(rng.start, rng.end))
            .group_by(PropertyViewDaily.day)
        ).all()
    )
    inquiry_day = _local_day(Inquiry.created_at)
    inquiries_by_day = _series(
        db.execute(
            select(inquiry_day, func.count())
            .join(Property, Property.id == Inquiry.property_id)
            .where(props, Inquiry.created_at >= rng.start_at, Inquiry.created_at < rng.end_at)
            .group_by(inquiry_day)
        ).all()
    )
    lead_day = _local_day(Lead.created_at)
    leads_by_day = _series(
        db.execute(
            select(lead_day, func.count())
            .where(leads_scope, Lead.created_at >= rng.start_at, Lead.created_at < rng.end_at)
            .group_by(lead_day)
        ).all()
    )
    favorites = db.execute(
        select(func.count())
        .select_from(Favorite)
        .join(Property, Property.id == Favorite.property_id)
        .where(props, Favorite.created_at >= rng.start_at, Favorite.created_at < rng.end_at)
    ).scalar_one()
    status_counts = {
        str(s): int(n)
        for s, n in db.execute(
            select(Property.status, func.count()).where(props).group_by(Property.status)
        ).all()
    }
    published = db.execute(
        select(func.count()).where(
            props, Property.published_at >= rng.start_at, Property.published_at < rng.end_at
        )
    ).scalar_one()
    won = db.execute(
        select(func.count())
        .select_from(Lead)
        .join(LeadStatus, LeadStatus.code == Lead.status_code)
        .where(
            leads_scope,
            LeadStatus.is_won.is_(True),
            Lead.closed_at >= rng.start_at,
            Lead.closed_at < rng.end_at,
        )
    ).scalar_one()
    leads_by_status = {
        str(s): int(n)
        for s, n in db.execute(
            select(Lead.status_code, func.count())
            .where(leads_scope, Lead.created_at >= rng.start_at, Lead.created_at < rng.end_at)
            .group_by(Lead.status_code)
        ).all()
    }

    views = sum(views_by_day.values())
    inquiries = sum(inquiries_by_day.values())
    leads = sum(leads_by_day.values())
    result: dict[str, Any] = {
        "scope": scope.kind,
        "date_from": rng.start.isoformat(),
        "date_to": rng.end.isoformat(),
        "include_demo": scope.include_demo,
        "summary": {
            "listings_active": status_counts.get("APPROVED", 0),
            "listings_published": int(published),
            "views": views,
            "favorites": int(favorites),
            "inquiries": inquiries,
            "leads": leads,
            "leads_won": int(won),
            "inquiry_rate": round(inquiries / views, 4) if views else None,
            "win_rate": round(int(won) / leads, 4) if leads else None,
        },
        "listings_by_status": status_counts,
        "leads_by_status": leads_by_status,
        "series": [
            {
                "day": d.isoformat(),
                "views": views_by_day.get(d, 0),
                "inquiries": inquiries_by_day.get(d, 0),
                "leads": leads_by_day.get(d, 0),
            }
            for d in rng.days()
        ],
        "data_notes": [
            "views = unique visitors per listing per day (local time)",
            "demo listings excluded" if not scope.include_demo else "demo listings included",
            "AI price estimates are not part of these figures",
        ],
    }
    if scope.kind != "property":
        result["top_listings"] = top_listings(db, props, rng)
    if scope.kind in ("agency", "platform"):
        result["agents"] = agent_activity(db, scope, rng)
    if scope.kind == "platform":
        result["platform"] = platform_extras(db, rng)
    return result


def top_listings(
    db: Session, props: ColumnElement[bool], rng: Range, limit: int = 10
) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Property.id, Property.title_ar, Property.title_en, func.sum(PropertyViewDaily.views))
        .join(PropertyViewDaily, PropertyViewDaily.property_id == Property.id)
        .where(props, PropertyViewDaily.day.between(rng.start, rng.end))
        .group_by(Property.id)
        .order_by(func.sum(PropertyViewDaily.views).desc(), Property.id)
        .limit(limit)
    ).all()
    ids = [r[0] for r in rows]
    if not ids:
        return []
    inquiries = dict(
        db.execute(
            select(Inquiry.property_id, func.count())
            .where(
                Inquiry.property_id.in_(ids),
                Inquiry.created_at >= rng.start_at,
                Inquiry.created_at < rng.end_at,
            )
            .group_by(Inquiry.property_id)
        )
        .tuples()
        .all()
    )
    favorites = dict(
        db.execute(
            select(Favorite.property_id, func.count())
            .where(
                Favorite.property_id.in_(ids),
                Favorite.created_at >= rng.start_at,
                Favorite.created_at < rng.end_at,
            )
            .group_by(Favorite.property_id)
        )
        .tuples()
        .all()
    )
    return [
        {
            "property_id": str(pid),
            "title_ar": title_ar,
            "title_en": title_en,
            "views": int(views),
            "inquiries": int(inquiries.get(pid, 0)),
            "favorites": int(favorites.get(pid, 0)),
        }
        for pid, title_ar, title_en, views in rows
    ]


def agent_activity(db: Session, scope: ScopeSpec, rng: Range) -> list[dict[str, Any]]:
    """Per-assignee lead handling (agency: its members; platform: top 20 assignees)."""
    in_range = and_(Lead.created_at >= rng.start_at, Lead.created_at < rng.end_at)
    assigned_q = (
        select(Lead.assigned_to_id, func.count())
        .where(scope.leads(), in_range, Lead.assigned_to_id.is_not(None))
        .group_by(Lead.assigned_to_id)
    )
    if scope.kind == "agency":
        member_ids = list(
            db.execute(
                select(AgencyMember.user_id).where(AgencyMember.agency_id == scope.agency_id)
            ).scalars()
        )
    else:
        member_ids = [
            uid
            for uid, _ in db.execute(assigned_q.order_by(func.count().desc()).limit(20))
            .tuples()
            .all()
            if uid is not None
        ]
    if not member_ids:
        return []
    assigned = dict(
        db.execute(assigned_q.where(Lead.assigned_to_id.in_(member_ids))).tuples().all()
    )
    won = dict(
        db.execute(
            select(Lead.assigned_to_id, func.count())
            .join(LeadStatus, LeadStatus.code == Lead.status_code)
            .where(
                scope.leads(),
                Lead.assigned_to_id.in_(member_ids),
                LeadStatus.is_won.is_(True),
                Lead.closed_at >= rng.start_at,
                Lead.closed_at < rng.end_at,
            )
            .group_by(Lead.assigned_to_id)
        )
        .tuples()
        .all()
    )
    activities = dict(
        db.execute(
            select(LeadActivity.actor_id, func.count())
            .join(Lead, Lead.id == LeadActivity.lead_id)
            .where(
                scope.leads(),
                LeadActivity.actor_id.in_(member_ids),
                LeadActivity.created_at >= rng.start_at,
                LeadActivity.created_at < rng.end_at,
            )
            .group_by(LeadActivity.actor_id)
        )
        .tuples()
        .all()
    )
    names = dict(
        db.execute(select(User.id, User.full_name).where(User.id.in_(member_ids))).tuples().all()
    )
    rows: list[dict[str, Any]] = [
        {
            "user_id": str(uid),
            "name": names.get(uid, ""),
            "leads_assigned": int(assigned.get(uid, 0)),
            "leads_won": int(won.get(uid, 0)),
            "activities": int(activities.get(uid, 0)),
        }
        for uid in member_ids
    ]
    rows.sort(key=lambda r: (-int(r["leads_assigned"]), -int(r["activities"]), str(r["name"])))
    return rows


def platform_extras(db: Session, rng: Range) -> dict[str, Any]:
    new_users = db.execute(
        select(func.count()).where(User.created_at >= rng.start_at, User.created_at < rng.end_at)
    ).scalar_one()
    in_range = SearchStatDaily.day.between(rng.start, rng.end)
    searches, zero = db.execute(
        select(
            func.coalesce(func.sum(SearchStatDaily.searches), 0),
            func.coalesce(func.sum(SearchStatDaily.zero_results), 0),
        ).where(in_range)
    ).one()
    by_gov = db.execute(
        select(SearchStatDaily.governorate_id, func.sum(SearchStatDaily.searches))
        .where(in_range, SearchStatDaily.governorate_id != "")
        .group_by(SearchStatDaily.governorate_id)
        .order_by(func.sum(SearchStatDaily.searches).desc())
        .limit(10)
    ).all()
    gov_ids: list[uuid.UUID] = []
    for gid, _ in by_gov:
        try:
            gov_ids.append(uuid.UUID(gid))
        except ValueError:
            continue
    gov_names = {
        str(g.id): (g.name_ar, g.name_en)
        for g in db.execute(select(Governorate).where(Governorate.id.in_(gov_ids))).scalars()
    }
    by_purpose = {
        (p or "ANY"): int(n)
        for p, n in db.execute(
            select(SearchStatDaily.purpose, func.sum(SearchStatDaily.searches))
            .where(in_range)
            .group_by(SearchStatDaily.purpose)
        ).all()
    }
    return {
        "new_users": int(new_users),
        "searches": int(searches),
        "zero_result_searches": int(zero),
        "zero_result_rate": round(int(zero) / int(searches), 4) if searches else None,
        "searches_by_governorate": [
            {
                "governorate_id": gid,
                "name_ar": gov_names.get(gid, ("", ""))[0],
                "name_en": gov_names.get(gid, ("", ""))[1],
                "searches": int(n),
            }
            for gid, n in by_gov
        ],
        "searches_by_purpose": by_purpose,
    }
