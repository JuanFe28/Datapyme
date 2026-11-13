"""
Generador y Limpiador de Empresas Demo Contrastantes para Validación F-DC-124 / F-DC-125.

Crea:
- Empresa A (`[DEMO-FDC125] Ferretería Cabecera S.A.S.`): Enfoque prioritario `inventory` y densidad `simplified`. 12 productos, 14 ventas.
- Empresa B (`[DEMO-FDC125] Boutique San Pío S.A.S.`): Enfoque prioritario `sales` y densidad `detailed`. 12 productos, 14 ventas.
- Empresa C (`[DEMO-FDC125] Minimercado Real de Minas S.A.S.`): Enfoque prioritario `predictive`. 12 productos, 14 ventas.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.commercial_service import create_product_with_initial_stock, create_sale_atomic
from app.core.config import ROOT
from app.core.models import (
    CompanyUIPreference,
    ImportJob,
    InventoryMovement,
    Product,
    Sale,
    SaleItem,
    SessionToken,
    Tenant,
    UsageEvent,
    User,
    UserViewSetting,
    utcnow,
)
from app.core.security import generate_session_token, hash_password, sha256_hex
from app.core.svg_assets import ensure_demo_svg_assets
from app.ui.ui_personalization_service import (
    DiagnosisInput,
    build_layout_config,
    compute_priority_weights,
)

DEMO_TAG = "[DEMO-FDC125]"

SKU_TO_IMAGE = {
    "CEM-ARG-50": "/static/img/products/cemento.svg",
    "TAL-BOS-650": "/static/img/products/taladro.svg",
    "MAR-EST-16": "/static/img/products/martillo.svg",
    "PIN-VIN-05": "/static/img/products/pintura.svg",
    "ALI-UNI-08": "/static/img/products/herramienta.svg",
    "CLA-ACE-25": "/static/img/products/herramienta.svg",
    "TUB-PVC-02": "/static/img/products/herramienta.svg",
    "DIS-COR-45": "/static/img/products/herramienta.svg",
    "GUA-SEG-01": "/static/img/products/seguridad.svg",
    "BOT-SEG-42": "/static/img/products/seguridad.svg",
    "CIE-MAN-12": "/static/img/products/herramienta.svg",
    "CJE-REP-01": "/static/img/products/herramienta.svg",
    "CHA-LIN-M": "/static/img/products/chaqueta.svg",
    "BOL-CUE-01": "/static/img/products/bolso.svg",
    "CAM-OXF-AZ": "/static/img/products/camisa.svg",
    "PAN-CHI-BE": "/static/img/products/camisa.svg",
    "VES-SED-FL": "/static/img/products/vestido.svg",
    "CAL-CUE-41": "/static/img/products/calzado.svg",
    "CIN-CUE-NE": "/static/img/products/bolso.svg",
    "BLU-MOD-BL": "/static/img/products/camisa.svg",
    "FAL-PLI-NE": "/static/img/products/vestido.svg",
    "BOM-JAC-VE": "/static/img/products/chaqueta.svg",
    "MOC-DUR-38": "/static/img/products/calzado.svg",
    "CAR-TAR-01": "/static/img/products/bolso.svg",
    "HUE-AA-30": "/static/img/products/alimento.svg",
    "PAN-RED-500": "/static/img/products/alimento.svg",
    "FRI-CAR-100": "/static/img/products/granos.svg",
    "AZU-BLA-100": "/static/img/products/alimento.svg",
    "CHO-TRD-500": "/static/img/products/alimento.svg",
    "QUE-CAM-500": "/static/img/products/lacteos.svg",
    "ATU-ACE-170": "/static/img/products/alimento.svg",
    "PAS-ESP-500": "/static/img/products/granos.svg",
}


def seed_contrast_demo_tenants(db: Session) -> dict[str, Any]:
    """
    Siembra las empresas de demostración contrastantes etiquetadas con `[DEMO-FDC125]`
    y un usuario `superadmin` de auditoría para pruebas E2E y sustentación F-DC-125.
    """
    ensure_demo_svg_assets(ROOT / "static")
    clear_contrast_demo_tenants(db)

    specs = [
        {
            "key": "empresa_a_inventario",
            "legal_name": f"{DEMO_TAG} Ferretería Cabecera S.A.S.",
            "nit": "900842119-4",
            "subsector": "Ferretería y Construcción (CIIU G4752)",
            "email": "demo.ferreteria@datapyme.co",
            "full_name": "Carlos Mantilla (Ferretería Cabecera)",
            "diagnosis": DiagnosisInput(
                M10=[
                    "Diferencias en inventario",
                    "No identifica fácilmente la rotación",
                ],
                M12=["Existencias y alertas", "Rotación de productos"],
                M17="Inventarios y existencias",
                M07=["Cuaderno o apuntes manuales"],
                M08=["Manual en cuaderno"],
                M13="No",
                M15=["Falta de conocimientos tecnológicos"],
            ),
            "products": [
                {
                    "sku": "CEM-ARG-50",
                    "name": "Cemento Gris Uso General 50kg",
                    "category": "Obra Gris",
                    "unit": "bulto",
                    "cost_price": Decimal("24500.00"),
                    "sale_price": Decimal("32000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("150.000"),
                    "min_stock": Decimal("25.000"),
                },
                {
                    "sku": "TAL-BOS-650",
                    "name": "Taladro Percutor Industrial 650W",
                    "category": "Herramienta Eléctrica",
                    "unit": "und",
                    "cost_price": Decimal("165000.00"),
                    "sale_price": Decimal("230000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("50.000"),
                    "min_stock": Decimal("4.000"),
                },
                {
                    "sku": "MAR-EST-16",
                    "name": "Martillo Uña Curva 16oz Mango Fibra",
                    "category": "Herramientas Manuales",
                    "unit": "und",
                    "cost_price": Decimal("18000.00"),
                    "sale_price": Decimal("28000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("24.000"),
                    "min_stock": Decimal("6.000"),
                },
                {
                    "sku": "PIN-VIN-05",
                    "name": "Pintura Vinilo Tipo 1 Blanco Galón",
                    "category": "Pinturas",
                    "unit": "galon",
                    "cost_price": Decimal("42000.00"),
                    "sale_price": Decimal("59000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("20.000"),
                    "min_stock": Decimal("5.000"),
                },
                {
                    "sku": "ALI-UNI-08",
                    "name": "Alicate Universal 8 Pulgadas Pro",
                    "category": "Herramientas Manuales",
                    "unit": "und",
                    "cost_price": Decimal("14000.00"),
                    "sale_price": Decimal("22500.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("18.000"),
                    "min_stock": Decimal("5.000"),
                },
                {
                    "sku": "CLA-ACE-25",
                    "name": "Clavo Acero Templado 2.5 pulg 1kg",
                    "category": "Fijaciones",
                    "unit": "kg",
                    "cost_price": Decimal("8500.00"),
                    "sale_price": Decimal("13000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("45.000"),
                    "min_stock": Decimal("10.000"),
                },
                {
                    "sku": "TUB-PVC-02",
                    "name": "Tubo Sanitario PVC 2 pulg x 3m",
                    "category": "Fontanería",
                    "unit": "tubo",
                    "cost_price": Decimal("16500.00"),
                    "sale_price": Decimal("25000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("35.000"),
                    "min_stock": Decimal("8.000"),
                },
                {
                    "sku": "DIS-COR-45",
                    "name": "Disco Corte Metal 4.5 pulg Extra Fino",
                    "category": "Abrasivos",
                    "unit": "und",
                    "cost_price": Decimal("3200.00"),
                    "sale_price": Decimal("5500.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("80.000"),
                    "min_stock": Decimal("15.000"),
                },
                {
                    "sku": "GUA-SEG-01",
                    "name": "Guante Carnaza Reforzado Seguridad",
                    "category": "Seguridad",
                    "unit": "par",
                    "cost_price": Decimal("6500.00"),
                    "sale_price": Decimal("11000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("40.000"),
                    "min_stock": Decimal("10.000"),
                },
                {
                    "sku": "BOT-SEG-42",
                    "name": "Bota Seguridad Dieléctrica Talla 42",
                    "category": "Seguridad",
                    "unit": "par",
                    "cost_price": Decimal("78000.00"),
                    "sale_price": Decimal("115000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("12.000"),
                    "min_stock": Decimal("3.000"),
                },
                {
                    "sku": "CIE-MAN-12",
                    "name": "Marco Segueta 12 pulg Alta Tensión",
                    "category": "Herramientas Manuales",
                    "unit": "und",
                    "cost_price": Decimal("21000.00"),
                    "sale_price": Decimal("32000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("14.000"),
                    "min_stock": Decimal("4.000"),
                },
                {
                    "sku": "CJE-REP-01",
                    "name": "Cerradura Sobreponer Doble Cilindro",
                    "category": "Cerrajería",
                    "unit": "und",
                    "cost_price": Decimal("39000.00"),
                    "sale_price": Decimal("62000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("16.000"),
                    "min_stock": Decimal("4.000"),
                },
            ],
            "monthly_quantities": [
                Decimal("1.000"),
                Decimal("2.000"),
                Decimal("2.000"),
                Decimal("3.000"),
                Decimal("3.000"),
                Decimal("4.000"),
                Decimal("4.000"),
                Decimal("5.000"),
                Decimal("5.000"),
                Decimal("6.000"),
                Decimal("6.000"),
                Decimal("7.000"),
                Decimal("8.000"),
                Decimal("9.000"),
            ],
        },
        {
            "key": "empresa_b_ventas",
            "legal_name": f"{DEMO_TAG} Boutique San Pío S.A.S.",
            "nit": "901224810-1",
            "subsector": "Prendas de Vestir y Calzado (CIIU G4771)",
            "email": "demo.boutique@datapyme.co",
            "full_name": "Laura Serrano (Boutique San Pío)",
            "diagnosis": DiagnosisInput(
                M10=[
                    "Dificultad para analizar ventas",
                    "Demora preparando informes",
                ],
                M12=[
                    "Ventas por periodo",
                    "Comparación entre periodos",
                    "Productos más y menos vendidos",
                ],
                M17="Consulta de ventas e indicadores",
                M07=["Facturación / punto de venta", "Software administrativo / ERP"],
                M08=["Hojas de cálculo"],
                M13="Sí",
                M15=["Diariamente"],
            ),
            "products": [
                {
                    "sku": "CHA-LIN-M",
                    "name": "Chaqueta Lino Santander Talla M",
                    "category": "Colección Ejecutiva",
                    "unit": "und",
                    "cost_price": Decimal("85000.00"),
                    "sale_price": Decimal("160000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("120.000"),
                    "min_stock": Decimal("5.000"),
                },
                {
                    "sku": "BOL-CUE-01",
                    "name": "Bolso Cuero Artesanal Bucaramanga",
                    "category": "Marroquinería",
                    "unit": "und",
                    "cost_price": Decimal("92000.00"),
                    "sale_price": Decimal("175000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("60.000"),
                    "min_stock": Decimal("3.000"),
                },
                {
                    "sku": "CAM-OXF-AZ",
                    "name": "Camisa Oxford Manga Larga Azul L",
                    "category": "Camisería",
                    "unit": "und",
                    "cost_price": Decimal("45000.00"),
                    "sale_price": Decimal("89000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("35.000"),
                    "min_stock": Decimal("8.000"),
                },
                {
                    "sku": "PAN-CHI-BE",
                    "name": "Pantalón Chino Slim Fit Beige 32",
                    "category": "Pantalones",
                    "unit": "und",
                    "cost_price": Decimal("52000.00"),
                    "sale_price": Decimal("98000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("30.000"),
                    "min_stock": Decimal("6.000"),
                },
                {
                    "sku": "VES-SED-FL",
                    "name": "Vestido Seda Estampado Floral S",
                    "category": "Vestidos",
                    "unit": "und",
                    "cost_price": Decimal("68000.00"),
                    "sale_price": Decimal("135000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("22.000"),
                    "min_stock": Decimal("4.000"),
                },
                {
                    "sku": "CAL-CUE-41",
                    "name": "Calzado Formal Cuero Café Talla 41",
                    "category": "Calzado",
                    "unit": "par",
                    "cost_price": Decimal("110000.00"),
                    "sale_price": Decimal("195000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("18.000"),
                    "min_stock": Decimal("3.000"),
                },
                {
                    "sku": "CIN-CUE-NE",
                    "name": "Cinturón Reversible Cuero Genuino",
                    "category": "Accesorios",
                    "unit": "und",
                    "cost_price": Decimal("26000.00"),
                    "sale_price": Decimal("49000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("40.000"),
                    "min_stock": Decimal("8.000"),
                },
                {
                    "sku": "BLU-MOD-BL",
                    "name": "Blusa Modal Cuello V Blanca M",
                    "category": "Blusas",
                    "unit": "und",
                    "cost_price": Decimal("32000.00"),
                    "sale_price": Decimal("62000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("28.000"),
                    "min_stock": Decimal("6.000"),
                },
                {
                    "sku": "FAL-PLI-NE",
                    "name": "Falda Plisada Midi Negra M",
                    "category": "Faldas",
                    "unit": "und",
                    "cost_price": Decimal("41000.00"),
                    "sale_price": Decimal("79000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("20.000"),
                    "min_stock": Decimal("4.000"),
                },
                {
                    "sku": "BOM-JAC-VE",
                    "name": "Chaqueta Bomber Urbana Verde L",
                    "category": "Chaquetas",
                    "unit": "und",
                    "cost_price": Decimal("75000.00"),
                    "sale_price": Decimal("145000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("16.000"),
                    "min_stock": Decimal("3.000"),
                },
                {
                    "sku": "MOC-DUR-38",
                    "name": "Mocasín Casual Gamuza Talla 38",
                    "category": "Calzado",
                    "unit": "par",
                    "cost_price": Decimal("88000.00"),
                    "sale_price": Decimal("158000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("15.000"),
                    "min_stock": Decimal("3.000"),
                },
                {
                    "sku": "CAR-TAR-01",
                    "name": "Billetera Minimalista Cuero Café",
                    "category": "Marroquinería",
                    "unit": "und",
                    "cost_price": Decimal("28000.00"),
                    "sale_price": Decimal("52000.00"),
                    "vat_rate": Decimal("19.00"),
                    "initial_stock": Decimal("30.000"),
                    "min_stock": Decimal("6.000"),
                },
            ],
            "monthly_quantities": [
                Decimal("1.000"),
                Decimal("1.000"),
                Decimal("2.000"),
                Decimal("2.000"),
                Decimal("3.000"),
                Decimal("3.000"),
                Decimal("4.000"),
                Decimal("4.000"),
                Decimal("5.000"),
                Decimal("5.000"),
                Decimal("6.000"),
                Decimal("6.000"),
                Decimal("7.000"),
                Decimal("8.000"),
            ],
        },
        {
            "key": "empresa_c_predictivo",
            "legal_name": f"{DEMO_TAG} Minimercado Real de Minas S.A.S.",
            "nit": "900511309-8",
            "subsector": "Minimercados y Víveres (CIIU G4711)",
            "email": "demo.minimercado@datapyme.co",
            "full_name": "Andrés Rueda (Minimercado Real de Minas)",
            "diagnosis": DiagnosisInput(
                M10=[],
                M12=["Tendencias o estimaciones"],
                M17="Tendencias o estimaciones",
                M07=["Hojas de cálculo"],
                M08=["Hojas de cálculo"],
                M13="Sí",
                M15=["Semanalmente"],
            ),
            "products": [
                {
                    "sku": "CAF-SAN-500",
                    "name": "Café Mesa de los Santos 500g",
                    "category": "Abarrotes",
                    "unit": "paq",
                    "cost_price": Decimal("14000.00"),
                    "sale_price": Decimal("21000.00"),
                    "vat_rate": Decimal("5.00"),
                    "initial_stock": Decimal("180.000"),
                    "min_stock": Decimal("10.000"),
                },
                {
                    "sku": "ARR-PRE-100",
                    "name": "Arroz Premium Extra Grano 1kg",
                    "category": "Granos",
                    "unit": "kg",
                    "cost_price": Decimal("3600.00"),
                    "sale_price": Decimal("5200.00"),
                    "vat_rate": Decimal("0.00"),
                    "initial_stock": Decimal("250.000"),
                    "min_stock": Decimal("20.000"),
                },
                {
                    "sku": "ACE-GIR-900",
                    "name": "Aceite Vegetal Girasol 900ml",
                    "category": "Aceites",
                    "unit": "botella",
                    "cost_price": Decimal("8900.00"),
                    "sale_price": Decimal("13200.00"),
                    "vat_rate": Decimal("0.00"),
                    "initial_stock": Decimal("50.000"),
                    "min_stock": Decimal("10.000"),
                },
                {
                    "sku": "LEC-ENT-100",
                    "name": "Leche Entera Larga Vida 1000ml",
                    "category": "Lácteos",
                    "unit": "bolsa",
                    "cost_price": Decimal("3400.00"),
                    "sale_price": Decimal("4800.00"),
                    "vat_rate": Decimal("0.00"),
                    "initial_stock": Decimal("80.000"),
                    "min_stock": Decimal("15.000"),
                },
                {
                    "sku": "HUE-AA-30",
                    "name": "Huevos Rojos Tipo AA Cubeta x30",
                    "category": "Granja",
                    "unit": "cubeta",
                    "cost_price": Decimal("15500.00"),
                    "sale_price": Decimal("21500.00"),
                    "vat_rate": Decimal("0.00"),
                    "initial_stock": Decimal("40.000"),
                    "min_stock": Decimal("8.000"),
                },
                {
                    "sku": "PAN-RED-500",
                    "name": "Panela Tradicional Redonda 500g",
                    "category": "Endulzantes",
                    "unit": "und",
                    "cost_price": Decimal("2400.00"),
                    "sale_price": Decimal("3600.00"),
                    "vat_rate": Decimal("0.00"),
                    "initial_stock": Decimal("70.000"),
                    "min_stock": Decimal("12.000"),
                },
                {
                    "sku": "FRI-CAR-100",
                    "name": "Fríjol Cargamanto Rojo 1000g",
                    "category": "Granos",
                    "unit": "kg",
                    "cost_price": Decimal("7500.00"),
                    "sale_price": Decimal("11200.00"),
                    "vat_rate": Decimal("0.00"),
                    "initial_stock": Decimal("45.000"),
                    "min_stock": Decimal("10.000"),
                },
                {
                    "sku": "AZU-BLA-100",
                    "name": "Azúcar Blanco Refinado 1000g",
                    "category": "Abarrotes",
                    "unit": "kg",
                    "cost_price": Decimal("3800.00"),
                    "sale_price": Decimal("5400.00"),
                    "vat_rate": Decimal("5.00"),
                    "initial_stock": Decimal("65.000"),
                    "min_stock": Decimal("15.000"),
                },
                {
                    "sku": "CHO-TRD-500",
                    "name": "Chocolate Santandereano 500g",
                    "category": "Bebidas",
                    "unit": "paq",
                    "cost_price": Decimal("6200.00"),
                    "sale_price": Decimal("9100.00"),
                    "vat_rate": Decimal("5.00"),
                    "initial_stock": Decimal("50.000"),
                    "min_stock": Decimal("10.000"),
                },
                {
                    "sku": "QUE-CAM-500",
                    "name": "Queso Campesino Fresco 500g",
                    "category": "Lácteos",
                    "unit": "bloque",
                    "cost_price": Decimal("8500.00"),
                    "sale_price": Decimal("12800.00"),
                    "vat_rate": Decimal("0.00"),
                    "initial_stock": Decimal("30.000"),
                    "min_stock": Decimal("6.000"),
                },
                {
                    "sku": "ATU-ACE-170",
                    "name": "Atún Lomitos en Aceite 170g",
                    "category": "Enlatados",
                    "unit": "lata",
                    "cost_price": Decimal("4800.00"),
                    "sale_price": Decimal("7200.00"),
                    "vat_rate": Decimal("5.00"),
                    "initial_stock": Decimal("60.000"),
                    "min_stock": Decimal("12.000"),
                },
                {
                    "sku": "PAS-ESP-500",
                    "name": "Pasta Espagueti Tradicional 500g",
                    "category": "Granos",
                    "unit": "paq",
                    "cost_price": Decimal("2600.00"),
                    "sale_price": Decimal("3900.00"),
                    "vat_rate": Decimal("5.00"),
                    "initial_stock": Decimal("75.000"),
                    "min_stock": Decimal("15.000"),
                },
            ],
            "monthly_quantities": [
                Decimal("2.000"),
                Decimal("2.000"),
                Decimal("3.000"),
                Decimal("4.000"),
                Decimal("4.000"),
                Decimal("5.000"),
                Decimal("6.000"),
                Decimal("6.000"),
                Decimal("7.000"),
                Decimal("8.000"),
                Decimal("8.000"),
                Decimal("9.000"),
                Decimal("10.000"),
                Decimal("12.000"),
            ],
        },
    ]

    created_summary: dict[str, Any] = {}
    now = utcnow()

    sales_plan = [
        (330, Decimal("2.000")),
        (270, Decimal("3.000")),
        (210, Decimal("4.000")),
        (150, Decimal("5.000")),
        (90, Decimal("6.000")),
        (50, Decimal("7.000")),
        (25, Decimal("3.000")),
        (20, Decimal("3.000")),
        (14, Decimal("3.000")),
        (6, Decimal("2.000")),
        (4, Decimal("2.000")),
        (3, Decimal("2.000")),
        (2, Decimal("2.000")),
        (1, Decimal("3.000")),
    ]

    for spec in specs:
        spec_password = {
            "empresa_a_inventario": "DemoFerreteria2026!",
            "empresa_b_ventas": "DemoBoutique2026!",
            "empresa_c_predictivo": "DemoMinimercado2026!",
        }.get(spec["key"], "DemoDatapyme2026!")

        tenant = Tenant(
            legal_name=spec["legal_name"],
            nit=spec["nit"],
            subsector=spec["subsector"],
            size="pequena",
            municipality="Bucaramanga",
            research_stats_opt_in=True,
            status="active",
        )
        db.add(tenant)
        db.flush()

        user = User(
            tenant_id=tenant.id,
            email=spec["email"],
            full_name=spec["full_name"],
            password_hash=hash_password(spec_password),
            role="owner",
        )
        db.add(user)
        db.flush()

        from app.core.models import CompanyTaxChange

        db.add(
            CompanyTaxChange(
                tenant_id=tenant.id,
                revision=1,
                status="responsible",
                reason="Supuesto sintético del generador demo",
                changed_by=user.id,
            )
        )

        profile = compute_priority_weights(spec["diagnosis"])
        ui_pref = CompanyUIPreference(
            tenant_id=tenant.id,
            source="market_study_survey",
            diagnosis_answers=spec["diagnosis"].to_dict(),
            mapping_version=profile.mapping_version,
            priority_weights={
                "weight_sales": profile.weight_sales,
                "weight_inventory": profile.weight_inventory,
                "weight_predictive": profile.weight_predictive,
            },
            weight_sales=Decimal(str(profile.weight_sales)),
            weight_inventory=Decimal(str(profile.weight_inventory)),
            weight_predictive=Decimal(str(profile.weight_predictive)),
            primary_focus=profile.primary_focus,
            secondary_focus=profile.secondary_focus,
            preferred_chart_density=profile.preferred_chart_density,
        )
        db.add(ui_pref)

        user_setting = UserViewSetting(
            user_id=user.id,
            tenant_id=tenant.id,
            view_mode="personalized",
        )
        db.add(user_setting)

        raw_token, tok_hash = generate_session_token()
        db.add(
            SessionToken(
                user_id=user.id,
                token_hash=tok_hash,
                csrf_secret=sha256_hex(raw_token + "|csrf"),
                expires_at=utcnow() + timedelta(days=7),
                ip_hash=sha256_hex("127.0.0.1"),
            )
        )

        created_products: list[Product] = []
        for p_info in spec["products"]:
            p_data = dict(p_info)
            if p_data.get("sku") in SKU_TO_IMAGE:
                p_data["image_url"] = SKU_TO_IMAGE[p_data["sku"]]
            prod = create_product_with_initial_stock(
                db=db,
                tenant_id=tenant.id,
                user_id=user.id,
                **p_data,
            )
            created_products.append(prod)

        primary_prod = created_products[0]

        for idx, (days_ago, qty) in enumerate(sales_plan):
            occurred = now - timedelta(days=days_ago)
            items_input = [
                {
                    "product_id": primary_prod.id,
                    "quantity": qty,
                    "unit_price": primary_prod.sale_price,
                    "discount": Decimal("0.00"),
                }
            ]
            sale = create_sale_atomic(
                db=db,
                tenant_id=tenant.id,
                user_id=user.id,
                customer_label=f"Cliente Comercial #{idx + 1}",
                payment_method="cash" if idx % 2 == 0 else "card",
                items_input=items_input,
                source="manual",
            )
            sale.occurred_at = occurred

        created_summary[spec["key"]] = {
            "tenant_id": tenant.id,
            "legal_name": tenant.legal_name,
            "email": spec["email"],
            "password": spec_password,
            "access_token": raw_token,
            "primary_focus": profile.primary_focus,
            "preferred_chart_density": profile.preferred_chart_density,
            "layout_config": build_layout_config(profile, view_mode="personalized"),
        }

    # Crear o actualizar cuenta SuperAdmin de auditoría F-DC-125
    admin_email = "superadmin.demo@datapyme.co"
    admin_password = "SuperAdmin2026!"
    existing_admin = db.query(User).filter_by(email=admin_email).first()
    if not existing_admin:
        existing_admin = User(
            tenant_id=None,
            email=admin_email,
            full_name=f"{DEMO_TAG} Auditor SuperAdmin F-DC-125",
            password_hash=hash_password(admin_password),
            role="superadmin",
        )
        db.add(existing_admin)
        db.flush()
    else:
        existing_admin.password_hash = hash_password(admin_password)
        existing_admin.failed_logins = 0
        existing_admin.locked_until = None

    admin_token, admin_tok_hash = generate_session_token()
    db.add(
        SessionToken(
            user_id=existing_admin.id,
            token_hash=admin_tok_hash,
            csrf_secret=sha256_hex(admin_token + "|csrf"),
            expires_at=utcnow() + timedelta(days=7),
            ip_hash=sha256_hex("127.0.0.1"),
        )
    )
    db.commit()

    created_summary["superadmin"] = {
        "user_id": existing_admin.id,
        "email": admin_email,
        "password": admin_password,
        "access_token": admin_token,
    }
    return created_summary


def clear_contrast_demo_tenants(db: Session) -> dict[str, int]:
    """
    Elimina exclusivamente las empresas etiquetadas con `[DEMO-FDC125]` y sus datos operativos,
    sin afectar en absoluto a empresas reales registradas en el sistema.
    """
    demo_tenants = db.query(Tenant).filter(Tenant.legal_name.like(f"{DEMO_TAG}%")).all()
    deleted_count = len(demo_tenants)
    demo_tids = [t.id for t in demo_tenants]

    if demo_tids:
        dialect = db.bind.dialect.name if db.bind else "sqlite"
        if dialect == "sqlite":
            db.execute(text("DROP TRIGGER IF EXISTS trg_inventory_movements_no_delete"))
            db.query(InventoryMovement).filter(InventoryMovement.tenant_id.in_(demo_tids)).delete(
                synchronize_session=False
            )
            db.execute(
                text(
                    """
                    CREATE TRIGGER IF NOT EXISTS trg_inventory_movements_no_delete
                    BEFORE DELETE ON inventory_movements
                    BEGIN
                        SELECT RAISE(ABORT, 'inventory_movements es append-only: prohibido DELETE en Kardex');
                    END;
                    """
                )
            )
        elif dialect == "postgresql":
            guard = "ALTER TABLE inventory_movements {} TRIGGER trg_pg_inventory_movements_immutable"
            db.execute(text(guard.format("DISABLE")))
            db.query(InventoryMovement).filter(InventoryMovement.tenant_id.in_(demo_tids)).delete(
                synchronize_session=False
            )
            db.execute(text(guard.format("ENABLE")))
        from app.core.models import CompanyTaxChange, SaleTaxSnapshot

        db.query(SaleTaxSnapshot).filter(SaleTaxSnapshot.tenant_id.in_(demo_tids)).delete(
            synchronize_session=False
        )
        db.query(CompanyTaxChange).filter(CompanyTaxChange.tenant_id.in_(demo_tids)).delete(
            synchronize_session=False
        )
        db.query(SaleItem).filter(SaleItem.tenant_id.in_(demo_tids)).delete(synchronize_session=False)
        db.query(Sale).filter(Sale.tenant_id.in_(demo_tids)).delete(synchronize_session=False)
        db.query(Product).filter(Product.tenant_id.in_(demo_tids)).delete(synchronize_session=False)
        db.query(ImportJob).filter(ImportJob.tenant_id.in_(demo_tids)).delete(synchronize_session=False)
        db.query(UsageEvent).filter(UsageEvent.tenant_id.in_(demo_tids)).delete(
            synchronize_session=False
        )
        db.query(UserViewSetting).filter(UserViewSetting.tenant_id.in_(demo_tids)).delete(
            synchronize_session=False
        )
        db.query(CompanyUIPreference).filter(CompanyUIPreference.tenant_id.in_(demo_tids)).delete(
            synchronize_session=False
        )

        demo_users = db.query(User).filter(User.tenant_id.in_(demo_tids)).all()
        demo_uids = [u.id for u in demo_users]
        if demo_uids:
            db.query(SessionToken).filter(SessionToken.user_id.in_(demo_uids)).delete(
                synchronize_session=False
            )
            db.query(User).filter(User.id.in_(demo_uids)).delete(synchronize_session=False)

        db.query(Tenant).filter(Tenant.id.in_(demo_tids)).delete(synchronize_session=False)
        db.commit()

    return {"demo_tenants_removed": deleted_count}
