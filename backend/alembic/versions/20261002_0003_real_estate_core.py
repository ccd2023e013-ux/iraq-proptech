"""Real-estate core: locations, agencies, properties, media, documents.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02

Seeds *reference* data valid in every environment: Iraq's 19 governorates
and the main cities, with approximate city-centre points (public knowledge,
labelled as approximate — not boundaries). Property types and amenities
use Iraqi market terminology. Demo listings are NOT created here; see
`python -m app.cli seed-demo`.
"""

import uuid
from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPROX = "Approximate city centre (public knowledge); not a boundary"

# code, slug, name_ar, name_en, capital (slug, ar, en, lon, lat)
GOVERNORATES = [
    ("BGD", "baghdad", "بغداد", "Baghdad", ("baghdad", "بغداد", "Baghdad", 44.3661, 33.3152)),
    ("BSR", "basra", "البصرة", "Basra", ("basra", "البصرة", "Basra", 47.7804, 30.5085)),
    ("NIN", "nineveh", "نينوى", "Nineveh", ("mosul", "الموصل", "Mosul", 43.1189, 36.3456)),
    ("EBL", "erbil", "أربيل", "Erbil", ("erbil", "أربيل", "Erbil", 44.0092, 36.1911)),
    (
        "SUL",
        "sulaymaniyah",
        "السليمانية",
        "Sulaymaniyah",
        ("sulaymaniyah", "السليمانية", "Sulaymaniyah", 45.4329, 35.5613),
    ),
    ("DHK", "duhok", "دهوك", "Duhok", ("duhok", "دهوك", "Duhok", 42.9469, 36.8669)),
    ("HLB", "halabja", "حلبجة", "Halabja", ("halabja", "حلبجة", "Halabja", 45.9860, 35.1779)),
    ("KRK", "kirkuk", "كركوك", "Kirkuk", ("kirkuk", "كركوك", "Kirkuk", 44.3922, 35.4681)),
    ("NJF", "najaf", "النجف", "Najaf", ("najaf", "النجف", "Najaf", 44.3360, 32.0259)),
    ("KRB", "karbala", "كربلاء", "Karbala", ("karbala", "كربلاء", "Karbala", 44.0249, 32.6160)),
    ("BBL", "babil", "بابل", "Babil", ("hillah", "الحلة", "Hillah", 44.4217, 32.4807)),
    ("ANB", "anbar", "الأنبار", "Anbar", ("ramadi", "الرمادي", "Ramadi", 43.3017, 33.4258)),
    ("DYL", "diyala", "ديالى", "Diyala", ("baqubah", "بعقوبة", "Baqubah", 44.6511, 33.7466)),
    ("SLD", "saladin", "صلاح الدين", "Saladin", ("tikrit", "تكريت", "Tikrit", 43.6765, 34.6077)),
    ("WST", "wasit", "واسط", "Wasit", ("kut", "الكوت", "Kut", 45.8222, 32.5128)),
    ("MYS", "maysan", "ميسان", "Maysan", ("amarah", "العمارة", "Amarah", 47.1586, 31.8356)),
    (
        "DQR",
        "dhi-qar",
        "ذي قار",
        "Dhi Qar",
        ("nasiriyah", "الناصرية", "Nasiriyah", 46.2600, 31.0439),
    ),
    ("MTH", "muthanna", "المثنى", "Muthanna", ("samawah", "السماوة", "Samawah", 45.2803, 31.3099)),
    (
        "QAD",
        "qadisiyyah",
        "القادسية",
        "Al-Qadisiyyah",
        ("diwaniyah", "الديوانية", "Diwaniyah", 44.9254, 31.9929),
    ),
]

# Additional cities: governorate code, slug, ar, en, lon, lat
EXTRA_CITIES = [
    ("BSR", "zubair", "الزبير", "Az Zubayr", 47.7044, 30.3892),
    ("BSR", "abu-al-khasib", "أبو الخصيب", "Abu Al-Khasib", 47.9667, 30.4500),
    ("BSR", "qurnah", "القرنة", "Al-Qurnah", 47.4300, 31.0100),
    ("BSR", "umm-qasr", "أم قصر", "Umm Qasr", 47.9479, 30.0362),
    ("BSR", "shatt-al-arab", "شط العرب", "Shatt Al-Arab", 47.8500, 30.5600),
    ("NJF", "kufa", "الكوفة", "Kufa", 44.4000, 32.0300),
    ("BGD", "abu-ghraib", "أبو غريب", "Abu Ghraib", 44.0600, 33.2900),
    ("EBL", "shaqlawa", "شقلاوة", "Shaqlawa", 44.3400, 36.4000),
    ("SUL", "ranya", "رانية", "Ranya", 44.8800, 36.2500),
]

PROPERTY_TYPES = [
    ("APARTMENT", "RESIDENTIAL", "شقة", "Apartment"),
    ("HOUSE", "RESIDENTIAL", "بيت", "House"),
    ("VILLA", "RESIDENTIAL", "فيلا", "Villa"),
    ("LAND", "LAND", "قطعة أرض", "Land plot"),
    ("BUILDING", "COMMERCIAL", "بناية", "Building"),
    ("SHOP", "COMMERCIAL", "محل تجاري", "Shop"),
    ("OFFICE", "COMMERCIAL", "مكتب", "Office"),
    ("WAREHOUSE", "INDUSTRIAL", "مخزن", "Warehouse"),
    ("FACTORY", "INDUSTRIAL", "معمل", "Factory"),
    ("FARM", "AGRICULTURAL", "بستان / مزرعة", "Farm / orchard"),
    ("OTHER", "OTHER", "أخرى", "Other"),
]

AMENITIES = [
    ("NATIONAL_GRID", "UTILITIES", "كهرباء وطنية", "National grid power"),
    (
        "GENERATOR_SUBSCRIPTION",
        "UTILITIES",
        "اشتراك مولدة أهلية",
        "Neighbourhood generator subscription",
    ),
    ("PRIVATE_GENERATOR", "UTILITIES", "مولدة خاصة", "Private generator"),
    ("SOLAR_PANELS", "UTILITIES", "طاقة شمسية", "Solar panels"),
    ("WATER_TANK", "UTILITIES", "خزان ماء", "Water tank"),
    ("SEWAGE_CONNECTED", "UTILITIES", "مربوط بالمجاري", "Connected to sewage"),
    ("INTERNET_FIBER", "UTILITIES", "إنترنت ضوئي", "Fibre internet"),
    ("CENTRAL_AC", "COMFORT", "تكييف مركزي", "Central air conditioning"),
    ("SPLIT_AC", "COMFORT", "مكيفات سبلت", "Split air conditioners"),
    ("HEATING", "COMFORT", "تدفئة", "Heating"),
    ("KITCHEN_EQUIPPED", "COMFORT", "مطبخ مجهز", "Equipped kitchen"),
    ("GUEST_ROOM", "COMFORT", "غرفة ضيوف (ديوانية)", "Guest room (diwaniya)"),
    ("MAID_ROOM", "COMFORT", "غرفة خدم", "Maid's room"),
    ("STORAGE_ROOM", "COMFORT", "مخزن", "Storage room"),
    ("ELEVATOR", "BUILDING", "مصعد", "Elevator"),
    ("PARKING", "BUILDING", "موقف سيارات", "Parking"),
    ("GARAGE", "BUILDING", "كراج", "Garage"),
    ("ROOF_ACCESS", "BUILDING", "سطح", "Roof access"),
    ("GARDEN", "OUTDOOR", "حديقة", "Garden"),
    ("BALCONY", "OUTDOOR", "شرفة", "Balcony"),
    ("SWIMMING_POOL", "OUTDOOR", "مسبح", "Swimming pool"),
    ("CORNER_PLOT", "OUTDOOR", "ركن (على شارعين)", "Corner plot"),
    ("PAVED_STREET", "OUTDOOR", "شارع مبلط", "Paved street"),
    ("SECURITY_GUARD", "SECURITY", "حراسة", "Security guard"),
    ("CCTV", "SECURITY", "كاميرات مراقبة", "CCTV"),
    ("GATED_COMMUNITY", "SECURITY", "مجمع سكني مغلق", "Gated community"),
]


def _point() -> geoalchemy2.Geometry:
    return geoalchemy2.Geometry(geometry_type="POINT", srid=4326, spatial_index=False)


def _area() -> geoalchemy2.Geometry:
    return geoalchemy2.Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False)


def _ts(name: str, *, nullable: bool = False, default: bool = True) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.func.now() if default else None,
        nullable=nullable,
    )


def _uuid_pk() -> sa.Column:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _place_columns() -> list[sa.Column]:
    return [
        _uuid_pk(),
        sa.Column("name_ar", sa.String(120), nullable=False),
        sa.Column("name_en", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("centroid", _point(), nullable=True),
        sa.Column("boundary", _area(), nullable=True),
        sa.Column("geometry_source", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
    ]


def _fk(table: str, col: str, ref: str, ondelete: str) -> sa.ForeignKeyConstraint:
    ref_table = ref.split(".")[0]
    return sa.ForeignKeyConstraint(
        [col], [ref], name=op.f(f"fk_{table}_{col}_{ref_table}"), ondelete=ondelete
    )


def upgrade() -> None:
    # ------------------------------------------------------------------ locations
    op.create_table(
        "governorates",
        *_place_columns(),
        sa.Column("code", sa.String(8), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_governorates")),
        sa.UniqueConstraint("slug", name="uq_governorates_slug"),
        sa.UniqueConstraint("code", name=op.f("uq_governorates_code")),
    )
    op.create_index(
        "ix_governorates_boundary", "governorates", ["boundary"], postgresql_using="gist"
    )

    op.create_table(
        "cities",
        *_place_columns(),
        sa.Column("governorate_id", sa.UUID(), nullable=False),
        _fk("cities", "governorate_id", "governorates.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cities")),
        sa.UniqueConstraint("governorate_id", "slug", name="uq_cities_governorate_slug"),
    )
    op.create_index("ix_cities_boundary", "cities", ["boundary"], postgresql_using="gist")
    op.create_index(op.f("ix_cities_governorate_id"), "cities", ["governorate_id"])

    op.create_table(
        "districts",
        *_place_columns(),
        sa.Column("city_id", sa.UUID(), nullable=False),
        _fk("districts", "city_id", "cities.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_districts")),
        sa.UniqueConstraint("city_id", "slug", name="uq_districts_city_slug"),
    )
    op.create_index("ix_districts_boundary", "districts", ["boundary"], postgresql_using="gist")
    op.create_index(op.f("ix_districts_city_id"), "districts", ["city_id"])

    op.create_table(
        "neighborhoods",
        *_place_columns(),
        sa.Column("district_id", sa.UUID(), nullable=False),
        _fk("neighborhoods", "district_id", "districts.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_neighborhoods")),
        sa.UniqueConstraint("district_id", "slug", name="uq_neighborhoods_district_slug"),
    )
    op.create_index(
        "ix_neighborhoods_boundary", "neighborhoods", ["boundary"], postgresql_using="gist"
    )
    op.create_index(op.f("ix_neighborhoods_district_id"), "neighborhoods", ["district_id"])

    conn = op.get_bind()
    gov_ids: dict[str, str] = {}
    template = (
        "INSERT INTO {table} (id, name_ar, name_en, slug, centroid, geometry_source, is_active{extra_cols}) "
        "VALUES (:id, :ar, :en, :slug, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :src, true{extra_vals})"
    )
    for code, slug, ar, en, (c_slug, c_ar, c_en, lon, lat) in GOVERNORATES:
        gid = str(uuid.uuid4())
        gov_ids[code] = gid
        conn.execute(
            sa.text(
                template.format(table="governorates", extra_cols=", code", extra_vals=", :code")
            ),
            {
                "id": gid,
                "ar": ar,
                "en": en,
                "slug": slug,
                "lon": lon,
                "lat": lat,
                "src": APPROX,
                "code": code,
            },
        )
        conn.execute(
            sa.text(
                template.format(table="cities", extra_cols=", governorate_id", extra_vals=", :gid")
            ),
            {
                "id": str(uuid.uuid4()),
                "ar": c_ar,
                "en": c_en,
                "slug": c_slug,
                "lon": lon,
                "lat": lat,
                "src": APPROX,
                "gid": gid,
            },
        )
    for code, c_slug, c_ar, c_en, lon, lat in EXTRA_CITIES:
        conn.execute(
            sa.text(
                template.format(table="cities", extra_cols=", governorate_id", extra_vals=", :gid")
            ),
            {
                "id": str(uuid.uuid4()),
                "ar": c_ar,
                "en": c_en,
                "slug": c_slug,
                "lon": lon,
                "lat": lat,
                "src": APPROX,
                "gid": gov_ids[code],
            },
        )

    # ------------------------------------------------------------------ reference data
    types = op.create_table(
        "property_types",
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("name_ar", sa.String(80), nullable=False),
        sa.Column("name_en", sa.String(80), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "category IN ('RESIDENTIAL','COMMERCIAL','LAND','AGRICULTURAL','INDUSTRIAL','OTHER')",
            name=op.f("ck_property_types_category_valid"),
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_property_types")),
    )
    op.bulk_insert(
        types,
        [
            {
                "code": c,
                "category": cat,
                "name_ar": ar,
                "name_en": en,
                "sort_order": i,
                "is_active": True,
            }
            for i, (c, cat, ar, en) in enumerate(PROPERTY_TYPES)
        ],
    )
    amenities = op.create_table(
        "amenities",
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("name_ar", sa.String(80), nullable=False),
        sa.Column("name_en", sa.String(80), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_amenities")),
    )
    op.bulk_insert(
        amenities,
        [
            {
                "code": c,
                "category": cat,
                "name_ar": ar,
                "name_en": en,
                "sort_order": i,
                "is_active": True,
            }
            for i, (c, cat, ar, en) in enumerate(AMENITIES)
        ],
    )

    # ------------------------------------------------------------------ agencies
    op.create_table(
        "agencies",
        _uuid_pk(),
        sa.Column("name_ar", sa.String(150), nullable=False),
        sa.Column("name_en", sa.String(150), nullable=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("whatsapp", sa.String(20), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("website", sa.String(300), nullable=True),
        sa.Column("license_number", sa.String(100), nullable=True),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("city_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        _ts("verified_at", nullable=True, default=False),
        sa.Column("verified_by_id", sa.UUID(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("deleted_at", nullable=True, default=False),
        sa.CheckConstraint(
            "status IN ('PENDING_VERIFICATION','VERIFIED','REJECTED','SUSPENDED')",
            name=op.f("ck_agencies_status_valid"),
        ),
        _fk("agencies", "city_id", "cities.id", "SET NULL"),
        _fk("agencies", "verified_by_id", "users.id", "SET NULL"),
        _fk("agencies", "created_by_id", "users.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agencies")),
        sa.UniqueConstraint("slug", name=op.f("uq_agencies_slug")),
    )
    op.create_index(op.f("ix_agencies_city_id"), "agencies", ["city_id"])
    op.create_index(op.f("ix_agencies_status"), "agencies", ["status"])

    op.create_table(
        "agency_members",
        sa.Column("agency_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("title", sa.String(100), nullable=True),
        _ts("joined_at"),
        sa.CheckConstraint("role IN ('OWNER','AGENT')", name=op.f("ck_agency_members_role_valid")),
        _fk("agency_members", "agency_id", "agencies.id", "CASCADE"),
        _fk("agency_members", "user_id", "users.id", "CASCADE"),
        sa.PrimaryKeyConstraint("agency_id", "user_id", name=op.f("pk_agency_members")),
        sa.UniqueConstraint("user_id", name="uq_agency_members_user_id"),
    )

    op.create_table(
        "agency_invitations",
        _uuid_pk(),
        sa.Column("agency_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("invited_by_id", sa.UUID(), nullable=False),
        _ts("created_at"),
        _ts("expires_at", default=False),
        _ts("accepted_at", nullable=True, default=False),
        _ts("revoked_at", nullable=True, default=False),
        _fk("agency_invitations", "agency_id", "agencies.id", "CASCADE"),
        _fk("agency_invitations", "invited_by_id", "users.id", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agency_invitations")),
    )
    op.create_index("ix_agency_invitations_email", "agency_invitations", ["email"])

    op.create_table(
        "agent_profiles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("license_number", sa.String(100), nullable=True),
        sa.Column("public_phone", sa.String(20), nullable=True),
        sa.Column("whatsapp", sa.String(20), nullable=True),
        sa.Column("years_experience", sa.SmallInteger(), nullable=True),
        sa.Column("languages", sa.String(100), nullable=True),
        _ts("verified_at", nullable=True, default=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            "years_experience BETWEEN 0 AND 80", name=op.f("ck_agent_profiles_experience_range")
        ),
        _fk("agent_profiles", "user_id", "users.id", "CASCADE"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_agent_profiles")),
    )

    # ------------------------------------------------------------------ properties
    op.execute("CREATE SEQUENCE IF NOT EXISTS property_reference_seq START 1000")
    statuses = "'DRAFT','PENDING_REVIEW','APPROVED','REJECTED','SUSPENDED','ARCHIVED','SOLD','RENTED','EXPIRED'"
    op.create_table(
        "properties",
        _uuid_pk(),
        sa.Column("reference_code", sa.String(24), nullable=False),
        sa.Column("title_ar", sa.String(200), nullable=False),
        sa.Column("title_en", sa.String(200), nullable=True),
        sa.Column("description_ar", sa.Text(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("property_type_code", sa.String(32), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("rent_period", sa.String(10), nullable=True),
        sa.Column("price_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("price_on_request", sa.Boolean(), nullable=False),
        sa.Column("negotiable", sa.Boolean(), nullable=False),
        sa.Column("area_m2", sa.Numeric(12, 2), nullable=True),
        sa.Column("land_area_m2", sa.Numeric(12, 2), nullable=True),
        sa.Column("bedrooms", sa.SmallInteger(), nullable=True),
        sa.Column("bathrooms", sa.SmallInteger(), nullable=True),
        sa.Column("floors", sa.SmallInteger(), nullable=True),
        sa.Column("floor_number", sa.SmallInteger(), nullable=True),
        sa.Column("year_built", sa.SmallInteger(), nullable=True),
        sa.Column("condition", sa.String(24), nullable=True),
        sa.Column("furnishing", sa.String(16), nullable=True),
        sa.Column("ownership_document", sa.String(16), nullable=False),
        sa.Column("governorate_id", sa.UUID(), nullable=False),
        sa.Column("city_id", sa.UUID(), nullable=False),
        sa.Column("district_id", sa.UUID(), nullable=True),
        sa.Column("neighborhood_id", sa.UUID(), nullable=True),
        sa.Column("street", sa.String(200), nullable=True),
        sa.Column("address_text", sa.String(300), nullable=True),
        sa.Column("location", _point(), nullable=True),
        sa.Column("display_location", _point(), nullable=True),
        sa.Column("location_privacy", sa.String(12), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        _ts("published_at", nullable=True, default=False),
        _ts("expires_at", nullable=True, default=False),
        _ts("verified_at", nullable=True, default=False),
        sa.Column("lister_id", sa.UUID(), nullable=False),
        sa.Column("agency_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("show_phone", sa.Boolean(), nullable=False),
        sa.Column("allow_whatsapp", sa.Boolean(), nullable=False),
        sa.Column("virtual_tour_url", sa.String(500), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("deleted_at", nullable=True, default=False),
        sa.CheckConstraint(
            "purpose IN ('SALE','RENT','LEASE','RAHN','MUSATAHA','EXCHANGE')",
            name=op.f("ck_properties_purpose_valid"),
        ),
        sa.CheckConstraint(f"status IN ({statuses})", name=op.f("ck_properties_status_valid")),
        sa.CheckConstraint("currency IN ('IQD','USD')", name=op.f("ck_properties_currency_valid")),
        sa.CheckConstraint(
            "rent_period IS NULL OR rent_period IN ('DAILY','MONTHLY','YEARLY')",
            name=op.f("ck_properties_rent_period_valid"),
        ),
        sa.CheckConstraint(
            "condition IS NULL OR condition IN ('NEW','EXCELLENT','GOOD','NEEDS_RENOVATION','UNDER_CONSTRUCTION')",
            name=op.f("ck_properties_condition_valid"),
        ),
        sa.CheckConstraint(
            "furnishing IS NULL OR furnishing IN ('UNFURNISHED','SEMI_FURNISHED','FURNISHED')",
            name=op.f("ck_properties_furnishing_valid"),
        ),
        sa.CheckConstraint(
            "ownership_document IN ('TAPU','AGRICULTURAL','HUJJA','INVESTMENT','MUSATAHA','SHARED','OTHER','UNKNOWN')",
            name=op.f("ck_properties_ownership_valid"),
        ),
        sa.CheckConstraint(
            "location_privacy IN ('EXACT','APPROXIMATE','HIDDEN')",
            name=op.f("ck_properties_location_privacy_valid"),
        ),
        sa.CheckConstraint(
            "(price_on_request AND price_amount IS NULL) OR "
            "(NOT price_on_request AND price_amount IS NOT NULL AND price_amount > 0)",
            name=op.f("ck_properties_price_present"),
        ),
        sa.CheckConstraint(
            "purpose NOT IN ('RENT','LEASE') OR rent_period IS NOT NULL",
            name=op.f("ck_properties_rent_needs_period"),
        ),
        sa.CheckConstraint(
            "area_m2 IS NULL OR area_m2 > 0", name=op.f("ck_properties_area_positive")
        ),
        sa.CheckConstraint(
            "land_area_m2 IS NULL OR land_area_m2 > 0",
            name=op.f("ck_properties_land_area_positive"),
        ),
        sa.CheckConstraint(
            "bedrooms IS NULL OR bedrooms BETWEEN 0 AND 100",
            name=op.f("ck_properties_bedrooms_range"),
        ),
        sa.CheckConstraint(
            "bathrooms IS NULL OR bathrooms BETWEEN 0 AND 100",
            name=op.f("ck_properties_bathrooms_range"),
        ),
        sa.CheckConstraint(
            "floors IS NULL OR floors BETWEEN 0 AND 200", name=op.f("ck_properties_floors_range")
        ),
        sa.CheckConstraint(
            "floor_number IS NULL OR floor_number BETWEEN -5 AND 200",
            name=op.f("ck_properties_floor_number_range"),
        ),
        sa.CheckConstraint(
            "year_built IS NULL OR year_built BETWEEN 1800 AND 2100",
            name=op.f("ck_properties_year_built_range"),
        ),
        _fk("properties", "property_type_code", "property_types.code", "RESTRICT"),
        _fk("properties", "governorate_id", "governorates.id", "RESTRICT"),
        _fk("properties", "city_id", "cities.id", "RESTRICT"),
        _fk("properties", "district_id", "districts.id", "SET NULL"),
        _fk("properties", "neighborhood_id", "neighborhoods.id", "SET NULL"),
        _fk("properties", "lister_id", "users.id", "RESTRICT"),
        _fk("properties", "agency_id", "agencies.id", "SET NULL"),
        _fk("properties", "agent_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_properties")),
        sa.UniqueConstraint("reference_code", name=op.f("uq_properties_reference_code")),
    )
    op.create_index("ix_properties_location", "properties", ["location"], postgresql_using="gist")
    op.create_index(
        "ix_properties_display_location",
        "properties",
        ["display_location"],
        postgresql_using="gist",
    )
    op.create_index("ix_properties_status_published", "properties", ["status", "published_at"])
    op.create_index(
        "ix_properties_city_purpose_type",
        "properties",
        ["city_id", "purpose", "property_type_code"],
    )
    for col in ("district_id", "neighborhood_id", "lister_id", "agency_id", "agent_id"):
        op.create_index(op.f(f"ix_properties_{col}"), "properties", [col])

    op.create_table(
        "property_amenities",
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("amenity_code", sa.String(32), nullable=False),
        _fk("property_amenities", "property_id", "properties.id", "CASCADE"),
        _fk("property_amenities", "amenity_code", "amenities.code", "RESTRICT"),
        sa.PrimaryKeyConstraint("property_id", "amenity_code", name=op.f("pk_property_amenities")),
    )
    op.create_index(
        op.f("ix_property_amenities_amenity_code"), "property_amenities", ["amenity_code"]
    )

    op.create_table(
        "property_media",
        _uuid_pk(),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("storage_key", sa.String(300), nullable=False),
        sa.Column("thumbnail_key", sa.String(300), nullable=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("caption", sa.String(200), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("perceptual_hash", sa.BigInteger(), nullable=True),
        sa.Column("moderation", sa.String(10), nullable=False),
        sa.Column("uploaded_by_id", sa.UUID(), nullable=True),
        _ts("created_at"),
        _ts("deleted_at", nullable=True, default=False),
        sa.CheckConstraint(
            "kind IN ('IMAGE','FLOOR_PLAN','VIDEO')", name=op.f("ck_property_media_kind_valid")
        ),
        sa.CheckConstraint(
            "moderation IN ('APPROVED','REJECTED')", name=op.f("ck_property_media_moderation_valid")
        ),
        _fk("property_media", "property_id", "properties.id", "CASCADE"),
        _fk("property_media", "uploaded_by_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_property_media")),
    )
    op.create_index(
        "ix_property_media_property_order", "property_media", ["property_id", "sort_order"]
    )
    op.create_index("ix_property_media_sha256", "property_media", ["sha256"])

    op.create_table(
        "property_documents",
        _uuid_pk(),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("doc_type", sa.String(20), nullable=False),
        sa.Column("storage_key", sa.String(300), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_by_id", sa.UUID(), nullable=True),
        _ts("created_at"),
        _ts("deleted_at", nullable=True, default=False),
        sa.CheckConstraint(
            "doc_type IN ('TITLE_DEED','ID_DOCUMENT','POWER_OF_ATTORNEY','CONTRACT','PERMIT','OTHER')",
            name=op.f("ck_property_documents_doc_type_valid"),
        ),
        _fk("property_documents", "property_id", "properties.id", "CASCADE"),
        _fk("property_documents", "uploaded_by_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_property_documents")),
    )
    op.create_index(
        op.f("ix_property_documents_property_id"), "property_documents", ["property_id"]
    )

    op.create_table(
        "property_price_history",
        _uuid_pk(),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("price_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("price_on_request", sa.Boolean(), nullable=False),
        _ts("changed_at"),
        sa.Column("changed_by_id", sa.UUID(), nullable=True),
        _fk("property_price_history", "property_id", "properties.id", "CASCADE"),
        _fk("property_price_history", "changed_by_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_property_price_history")),
    )
    op.create_index(
        "ix_property_price_history_property",
        "property_price_history",
        ["property_id", "changed_at"],
    )

    op.create_table(
        "property_status_history",
        _uuid_pk(),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        _ts("changed_at"),
        sa.Column("changed_by_id", sa.UUID(), nullable=True),
        _fk("property_status_history", "property_id", "properties.id", "CASCADE"),
        _fk("property_status_history", "changed_by_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_property_status_history")),
    )
    op.create_index(
        "ix_property_status_history_property",
        "property_status_history",
        ["property_id", "changed_at"],
    )

    op.create_table(
        "property_verifications",
        _uuid_pk(),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("result", sa.String(8), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("verified_by_id", sa.UUID(), nullable=True),
        _ts("created_at"),
        sa.CheckConstraint(
            "kind IN ('IDENTITY','DOCUMENT','OWNERSHIP','LOCATION','PHONE','AGENCY','SITE_VISIT')",
            name=op.f("ck_property_verifications_kind_valid"),
        ),
        sa.CheckConstraint(
            "result IN ('PASSED','FAILED')", name=op.f("ck_property_verifications_result_valid")
        ),
        _fk("property_verifications", "property_id", "properties.id", "CASCADE"),
        _fk("property_verifications", "document_id", "property_documents.id", "SET NULL"),
        _fk("property_verifications", "verified_by_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_property_verifications")),
    )
    op.create_index(
        op.f("ix_property_verifications_property_id"), "property_verifications", ["property_id"]
    )


def downgrade() -> None:
    for table in (
        "property_verifications",
        "property_status_history",
        "property_price_history",
        "property_documents",
        "property_media",
        "property_amenities",
        "properties",
        "agent_profiles",
        "agency_invitations",
        "agency_members",
        "agencies",
        "amenities",
        "property_types",
        "neighborhoods",
        "districts",
        "cities",
        "governorates",
    ):
        op.drop_table(table)
    op.execute("DROP SEQUENCE IF EXISTS property_reference_seq")
