"""Modelos relacionales Multi-Tenant para Datapyme Empresarial (F-DC-124)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=new_uuid)
    legal_name = Column(String(180), nullable=False)
    trade_name = Column(String(180), nullable=True)
    nit = Column(String(20), nullable=True, unique=True)
    subsector = Column(String(40), nullable=False)
    size = Column(String(20), nullable=False, default="pequena")
    municipality = Column(String(60), nullable=False, default="Bucaramanga")
    research_stats_opt_in = Column(Boolean, nullable=False, default=False)
    status = Column(String(24), nullable=False, default="active")
    deletion_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    anonymized_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    ui_preference = relationship(
        "CompanyUIPreference", uselist=False, back_populates="tenant", cascade="all, delete-orphan"
    )


class CompanyTaxChange(Base):
    __tablename__ = "company_tax_changes"
    id = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    status = Column(String(24), nullable=False)
    reason = Column(String(280), nullable=False)
    changed_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("tenant_id", "revision", name="uq_company_tax_revision"),
        CheckConstraint(
            "status IN ('responsible','not_responsible','pending')", name="ck_company_tax_status"
        ),
    )


class SaleTaxSnapshot(Base):
    __tablename__ = "sale_tax_snapshots"
    sale_id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    revision = Column(Integer, nullable=False)
    status = Column(String(24), nullable=False)
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "sale_id"], ["sales.tenant_id", "sales.id"]),)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    email = Column(String(254), nullable=False, unique=True)
    full_name = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="owner")
    is_active = Column(Boolean, nullable=False, default=True)
    failed_logins = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "(role = 'superadmin' AND tenant_id IS NULL) OR (role != 'superadmin' AND tenant_id IS NOT NULL)",
            name="ck_user_superadmin_tenant_isolation",
        ),
    )


class SessionToken(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    csrf_secret = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    ip_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class LegalConsent(Base):
    """Registro inmutable de consentimiento Ley 1581 de 2012 y Decreto 1377 de 2013."""

    __tablename__ = "legal_consents"

    id = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    document_type = Column(String(40), nullable=False)
    document_version = Column(String(20), nullable=False)
    document_sha256 = Column(String(64), nullable=False)
    action = Column(String(16), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    ip_hash = Column(String(64), nullable=False)
    user_agent_hash = Column(String(64), nullable=False)
    prev_hash = Column(String(64), nullable=False)
    row_hash = Column(String(64), nullable=False, unique=True)


class CompanyUIPreference(Base):
    """Preferencias del Motor de Interfaz Adaptativa Basado en Encuesta (map-v1)."""

    __tablename__ = "company_ui_preferences"

    id = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, unique=True, index=True)
    source = Column(String(24), nullable=False, default="onboarding_quiz")
    diagnosis_answers = Column(JSON, nullable=False)
    mapping_version = Column(String(20), nullable=False, default="map-v1")
    priority_weights = Column(JSON, nullable=False)
    weight_sales = Column(Numeric(5, 3), nullable=False)
    weight_inventory = Column(Numeric(5, 3), nullable=False)
    weight_predictive = Column(Numeric(5, 3), nullable=False)
    primary_focus = Column(String(20), nullable=False)
    secondary_focus = Column(String(20), nullable=True)
    preferred_chart_density = Column(String(16), nullable=False)
    diagnosed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    tenant = relationship("Tenant", back_populates="ui_preference")


class UserViewSetting(Base):
    """Sobreescritura manual de vista por usuario (personalized vs general)."""

    __tablename__ = "user_view_settings"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    view_mode = Column(String(20), nullable=False, default="personalized")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    sku = Column(String(64), nullable=False)
    name = Column(String(180), nullable=False)
    category = Column(String(90), nullable=False)
    unit = Column(String(20), nullable=False, default="und")
    cost_price = Column(Numeric(14, 2), nullable=False)
    sale_price = Column(Numeric(14, 2), nullable=False)
    vat_rate = Column(Numeric(5, 2), nullable=False, default=19.00)
    stock_qty = Column(Numeric(14, 3), nullable=False, default=0)
    min_stock = Column(Numeric(14, 3), nullable=False, default=0)
    image_url = Column(String(512), nullable=True, default=None)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_tenant_product_sku"),
        UniqueConstraint("tenant_id", "id", name="uq_tenant_product_id"),
    )


class InventoryMovement(Base):
    """Kardex inmutable (append-only) de movimientos de inventario por tenant."""

    __tablename__ = "inventory_movements"

    id = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    product_id = Column(String(36), nullable=False, index=True)
    movement_type = Column(String(24), nullable=False)
    quantity = Column(Numeric(14, 3), nullable=False)
    unit_cost = Column(Numeric(14, 2), nullable=True)
    reason = Column(String(200), nullable=False)
    sale_id = Column(String(36), nullable=True, index=True)
    import_job_id = Column(String(36), nullable=True, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_movement_tenant_product",
        ),
        CheckConstraint("quantity != 0", name="ck_movement_nonzero_qty"),
    )


class Sale(Base):
    """Transacción de venta operativa o histórica aislada por tenant_id."""

    __tablename__ = "sales"

    id = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    sale_number = Column(Integer, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    customer_label = Column(String(80), nullable=True)
    payment_method = Column(String(20), nullable=False, default="cash")
    subtotal = Column(Numeric(14, 2), nullable=False)
    discount_total = Column(Numeric(14, 2), nullable=False, default=0)
    vat_total = Column(Numeric(14, 2), nullable=False)
    total = Column(Numeric(14, 2), nullable=False)
    cogs_total = Column(Numeric(14, 2), nullable=False)
    status = Column(String(20), nullable=False, default="completed")
    source = Column(String(20), nullable=False, default="manual")
    import_job_id = Column(String(36), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    tax_snapshot = relationship("SaleTaxSnapshot", uselist=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "sale_number", name="uq_tenant_sale_number"),
        UniqueConstraint("tenant_id", "id", name="uq_tenant_sale_id"),
    )


class SaleItem(Base):
    """Línea de detalle de una venta con snapshot de costo para margen bruto exacto."""

    __tablename__ = "sale_items"

    id = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    sale_id = Column(String(36), nullable=False, index=True)
    product_id = Column(String(36), nullable=False, index=True)
    quantity = Column(Numeric(14, 3), nullable=False)
    unit_price = Column(Numeric(14, 2), nullable=False)
    unit_cost_snapshot = Column(Numeric(14, 2), nullable=False)
    vat_rate = Column(Numeric(5, 2), nullable=False)
    discount = Column(Numeric(14, 2), nullable=False, default=0)
    line_total = Column(Numeric(14, 2), nullable=False)

    sale = relationship("Sale", back_populates="items")
    product = relationship(
        "Product",
        foreign_keys=[tenant_id, product_id],
        primaryjoin="and_(SaleItem.tenant_id == Product.tenant_id, SaleItem.product_id == Product.id)",
        overlaps="items,sale",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "sale_id"],
            ["sales.tenant_id", "sales.id"],
            name="fk_saleitem_tenant_sale",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_saleitem_tenant_product",
        ),
        CheckConstraint("quantity > 0", name="ck_saleitem_positive_qty"),
    )


class ImportJob(Base):
    """Registro de auditoría de cargas masivas CSV / Excel (.xlsx)."""

    __tablename__ = "import_jobs"

    id = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    filename_safe = Column(String(180), nullable=False)
    sha256 = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False)
    rows_total = Column(Integer, nullable=False, default=0)
    rows_ok = Column(Integer, nullable=False, default=0)
    rows_rejected = Column(Integer, nullable=False, default=0)
    errors = Column(JSON, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class UsageEvent(Base):
    """Eventos operativos para cálculo agregado de impacto (solo leídos por el agregador)."""

    __tablename__ = "usage_events"

    id = Column(String(36), primary_key=True, default=new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    event_type = Column(String(40), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PlatformImpactTelemetry(Base):
    """Telemetría agregada y seudonimizada (SIN tenant_id ni PII) para el Informe F-DC-125."""

    __tablename__ = "platform_impact_telemetry"

    id = Column(String(36), primary_key=True, default=new_uuid)
    snapshot_date = Column(Date, nullable=False, index=True)
    scope = Column(String(20), nullable=False, default="global")
    subsector = Column(String(40), nullable=True)
    k_threshold = Column(Integer, nullable=False, default=3)
    active_tenants = Column(Integer, nullable=False, default=0)
    sales_count = Column(Integer, nullable=True)
    sales_amount_cop = Column(Numeric(18, 0), nullable=True)
    products_managed = Column(Integer, nullable=True)
    stockout_risk_alerts = Column(Integer, nullable=True)
    alerts_resolved_in_time = Column(Integer, nullable=True)
    overstock_flags = Column(Integer, nullable=True)
    forecasts_generated = Column(Integer, nullable=True)
    reports_generated = Column(Integer, nullable=True)
    est_minutes_saved = Column(Numeric(14, 0), nullable=True)
    baseline_ref = Column(String(120), nullable=True)
    focus_sales_n = Column(Integer, nullable=True)
    focus_inventory_n = Column(Integer, nullable=True)
    focus_predictive_n = Column(Integer, nullable=True)
    focus_balanced_n = Column(Integer, nullable=True)
    is_suppressed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


_PG_IMMUTABLE_FN = """
CREATE OR REPLACE FUNCTION datapyme_prevent_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Tabla inmutable por auditoria (Ley 1581 de 2012 / Kardex F-DC-124): UPDATE y DELETE prohibidos';
END;
$$ LANGUAGE plpgsql
"""


def _install_pg_immutability(connection, table: str) -> None:
    """Instala en PostgreSQL el equivalente de los triggers de inmutabilidad de SQLite."""
    connection.exec_driver_sql(_PG_IMMUTABLE_FN)
    trigger = f"trg_pg_{table}_immutable"
    connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    connection.exec_driver_sql(
        f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION datapyme_prevent_mutation()"
    )


@event.listens_for(LegalConsent.__table__, "after_create")
def _create_immutability_triggers(target, connection, **kwargs):
    dialect = connection.dialect.name
    if dialect == "postgresql":
        _install_pg_immutability(connection, "legal_consents")
    if dialect == "sqlite":
        connection.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_legal_consents_no_update
            BEFORE UPDATE ON legal_consents
            BEGIN
                SELECT RAISE(ABORT, 'legal_consents es inmutable: prohibido UPDATE (Ley 1581 de 2012)');
            END;
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_legal_consents_no_delete
            BEFORE DELETE ON legal_consents
            BEGIN
                SELECT RAISE(ABORT, 'legal_consents es inmutable: prohibido DELETE (Ley 1581 de 2012)');
            END;
            """
        )


@event.listens_for(InventoryMovement.__table__, "after_create")
def _create_kardex_immutability_triggers(target, connection, **kwargs):
    dialect = connection.dialect.name
    if dialect == "postgresql":
        _install_pg_immutability(connection, "inventory_movements")
    if dialect == "sqlite":
        connection.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_inventory_movements_no_update
            BEFORE UPDATE ON inventory_movements
            BEGIN
                SELECT RAISE(ABORT, 'inventory_movements es append-only: prohibido UPDATE en Kardex');
            END;
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_inventory_movements_no_delete
            BEFORE DELETE ON inventory_movements
            BEGIN
                SELECT RAISE(ABORT, 'inventory_movements es append-only: prohibido DELETE en Kardex');
            END;
            """
        )
