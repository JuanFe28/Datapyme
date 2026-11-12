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
    legal_name: str
    subsector: str
    size: str = "pequena"
    email: str
    full_name: str
    password: str
    accept_data_policy: bool
    accept_terms_mvp: bool
    accept_aggregate_stats: bool = False
    diagnosis: DiagnosisPayload


class LoginRequest(BaseModel):
    email: str
    password: str


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


class ProductUpdateRequest(BaseModel):
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
    customer_label: str | None = "Cliente Mostrador"
    payment_method: Literal["cash", "card", "transfer", "credit", "other"] = "cash"
    items: list[SaleItemRequest]


class DeletionRequestPayload(BaseModel):
    reason: str = Field(min_length=5, max_length=280)
