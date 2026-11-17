"""Esquemas Pydantic para validación y serialización de peticiones en Datapyme Empresarial."""

from typing import Literal

from pydantic import BaseModel, Field


class DiagnosisPayload(BaseModel):
    M10: list[str] = Field(default_factory=list)
    M12: list[str] = Field(default_factory=list)
    M17: str = ""
    M07: list[str] = Field(default_factory=list)
    M08: list[str] = Field(default_factory=list)
    M13: str = "No"
    M15: list[str] = Field(default_factory=list)


class RegisterRequest(BaseModel):
    tax_status: Literal["responsible", "not_responsible", "pending"] = "pending"
    legal_name: str
    subsector: str
    size: str = "pequena"
    email: str
    phone: str | None = None
    full_name: str
    password: str
    accept_data_policy: bool
    accept_terms_mvp: bool
    accept_aggregate_stats: bool = False
    diagnosis: DiagnosisPayload


class LoginRequest(BaseModel):
    email: str
    password: str
    totp_code: str | None = None


class MfaConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class TourCompleteRequest(BaseModel):
    action: Literal["purge_training", "keep_training"]


class ViewModeUpdate(BaseModel):
    view_mode: Literal["personalized", "general"]


class ProductCreateRequest(BaseModel):
    sku: str
    name: str
    category: str = "General"
    unit: str = "und"
    cost_price: str | float | int
    sale_price: str | float | int
    vat_rate: str | float | int = "19.00"
    initial_stock: str | float | int = "0"
    min_stock: str | float | int = "0"
    image_url: str | None = None
    is_training_data: bool = False


class ProductUpdateRequest(BaseModel):
    vat_rate: str | float | int | None = None
    sku: str | None = None
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    cost_price: str | float | int | None = None
    sale_price: str | float | int | None = None
    min_stock: str | float | int | None = None
    image_url: str | None = None
    is_active: bool | None = None


class InventoryMovementRequest(BaseModel):
    product_id: str
    movement_type: Literal["purchase_in", "return_in", "adjustment_in", "adjustment_out"]
    quantity: str | float | int
    unit_cost: str | float | int | None = None
    reason: str


class SaleItemRequest(BaseModel):
    product_id: str
    quantity: str | float | int
    unit_price: str | float | int | None = None
    discount: str | float | int = "0.00"


class SaleCreateRequest(BaseModel):
    tax_revision: int | None = Field(default=None, ge=0)
    customer_label: str | None = "Cliente Mostrador"
    payment_method: Literal["cash", "card", "transfer", "credit", "other"] = "cash"
    items: list[SaleItemRequest]
    is_training_data: bool = False


class DeletionRequestPayload(BaseModel):
    reason: str = Field(min_length=5, max_length=280)


class ProvisionTenantRequest(BaseModel):
    trade_name: str = Field(min_length=2, max_length=180)
    legal_name: str | None = Field(default=None, max_length=180)
    subsector: str = Field(default="general", min_length=2, max_length=40)
    size: Literal["micro", "pequena", "mediana"] = "micro"
    municipality: str = Field(default="Bucaramanga", min_length=2, max_length=60)
    owner_full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    phone: str | None = Field(default=None, max_length=24)
    temporary_password: str | None = Field(default=None, min_length=10, max_length=128)
    priority_focus: Literal["sales", "inventory", "predictive", "balanced"] = "balanced"
    density: Literal["simple", "standard", "detailed"] = "standard"
    tax_status: Literal["responsible", "not_responsible", "pending"] = "pending"
    starter_catalog: bool = False
