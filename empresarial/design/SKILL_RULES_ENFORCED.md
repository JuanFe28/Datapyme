# REGLAS DE DISEÑO OBLIGATORIAS: IMPECCABLE + APPLE HIG + LINEAR / POLARIS
*Compendio normativo de diseño frontend para Datapyme Empresarial. Lectura y cumplimiento estricto obligatorio para Antigravity y sub-agentes (OpenCode / DeepSeek V4.1 Flash Max).*

---

## 1. PRINCIPIOS FUNDAMENTALES Y ANTI-PATRONES PROHIBIDOS (ANTI-AI SLOP)

### PROHIBICIÓN 1: "Cards nested in cards"
- **NUNCA** incrustar una tarjeta con borde (`border`, `border-radius`, `box-shadow`) dentro de otra tarjeta con borde.
- Si un contenedor ya tiene superficie blanca y borde sutil, sus elementos internos deben diferenciarse mediante **espacio en blanco, tipografía, divisores verticales sutiles o filas de lista limpias**, jamás con cajitas adicionales.

### PROHIBICIÓN 2: "Wrapping everything in a card"
- **NUNCA** envolver cada etiqueta, número o botón dentro de un recuadro individual.
- Usa alineación, jerarquía tipográfica y espacio en blanco (`24px` a `32px`) para separar bloques. Un simple divisor horizontal o vertical `1px solid rgba(15, 23, 42, 0.06)` es siempre superior a un recuadro cerrado.

### PROHIBICIÓN 3: Cero párrafos explicativos dentro de tarjetas
- Un comerciante entra a operar, no a leer manuales.
- **PROHIBIDO** incluir descripciones didácticas largas, subtítulos de relleno, o jerga algorítmica interna (`Laplace`, `M10`, `M17`, `weight_sales`, `map-v1`, `tenant_id`).
- La única excepción formal es el aviso metodológico del **F-DC-124** en el tab de Proyección Predictiva, mostrado en una franja discreta y sobria.

### REGLA DE LOS 3 ELEMENTOS POR KPI (Métricas sin ruido)
Cada indicador o tarjeta de KPI contiene **exclusivamente 3 elementos**:
1. **Etiqueta:** 2 a 4 palabras (`font-size: 13px; font-weight: 500; color: #64748B;`).
2. **Cifra Principal:** Formato grande y limpio (`font-size: 28px–32px; font-weight: 600; font-variant-numeric: tabular-nums; color: #0F172A; line-height: 1.15;`).
3. **Badge Compacto:** Variación o estado contextual (`+12.4% vs mes anterior` o `3 críticos` con fondo suave y texto semántico).

---

## 2. ARQUITECTURA DE PANTALLA: LOS 3 BLOQUES LIMPIOS (ESTILO LINEAR / SHOPIFY POLARIS)

### BLOQUE 1: Top Header & Segmented Control (Estilo macOS / iOS)
- **Barra de navegación:** Superficie translúcida (`backdrop-filter: blur(12px) saturate(180%); background: rgba(255, 255, 255, 0.85); border-bottom: 1px solid rgba(15, 23, 42, 0.06);`).
- **Lado Izquierdo:** Nombre comercial de la empresa (`font-size: 15px; font-weight: 600; color: #0F172A;`) y badge de ciudad/sector.
- **Lado Derecho:**
  1. **Segmented Pill (Control Segmentado estilo Apple):** Selector redondeado compacto con estados activos suaves para alternar entre `Vista Adaptada` y `Vista General`.
  2. **Acciones Primarias y Secundarias:**
     - Botón Primario: `+ Registrar Venta` (`background: #0D7A6F; color: #FFFFFF; font-weight: 500; border-radius: 8px;`).
     - Botón Secundario: `Importar Excel` (`background: #FFFFFF; border: 1px solid rgba(15, 23, 42, 0.12); color: #0F172A;`).
     - Botón Ajuste/Stock: `+ Nuevo Producto`.

### BLOQUE 2: Franja Unificada de Métricas + Bloque Hero Interactivo
1. **Franja Unificada de Métricas (Unified Metric Strip):**
   - Una sola banda horizontal limpia en superficie `#FFFFFF` con borde suave `1px solid rgba(15, 23, 42, 0.06)` y sombra multicapa suave.
   - Contiene 4 KPIs principales en línea horizontal, separados por divisores verticales tenues (`border-right: 1px solid rgba(15, 23, 42, 0.06);`).
   - Sin recuadros aislados ni marcos redundantes.
2. **Bloque Hero Interactivo con Pestañas (Tabs) y Filtros de Tiempo:**
   - Contenedor amplio, limpio y respirable.
   - Barra de Pestañas estilo Apple/Linear:
     - `Evolución de Ventas`
     - `Estado de Inventario`
     - `Proyección Estadística (Act. 3.5)`
   - Selector de Horizonte / Rango temporal a la derecha: pills segmentadas `7D` | `30D` | `90D` | `12M`.
   - **Personalización basada en encuesta:** La pestaña activa por defecto coincide con el foco de la PyME (`primary_focus` = `inventory` abre `Estado de Inventario`, `sales` abre `Evolución de Ventas`, `predictive` abre `Proyección Estadística`).

### BLOQUE 3: Tabla Operativa Interactiva & Slide-Over Drawers (Shopify Polaris)
1. **Tabla de Operaciones:**
   - Cabeceras en mayúsculas sobrias (`font-size: 11px; letter-spacing: 0.05em; color: #64748B; background: #F8FAFC; border-bottom: 1px solid rgba(15, 23, 42, 0.06);`).
   - Filas amplias (`min-height: 52px;`) con transición `:hover` sutil (`background: #F8FAFC;`).
   - Barra de progreso de stock compacta (`height: 6px; border-radius: 3px; background: #E2E8F0;`) con relleno semántico (verde para óptimo, ámbar para riesgo, rojo para agotado).
   - Botones de acción rápida por fila (Ver, Editar, Ajustar) discretos y revelados sutilmente al pasar el cursor.
2. **Paneles Deslizantes (Slide-Over Drawers) y Modales:**
   - **PROHIBIDO** incrustar formularios largos fijos en medio de la pantalla de visualización.
   - Los flujos operativos (`Registrar Venta`, `Nuevo Producto / Ajuste`, `Importar Archivo CSV/XLSX`) se despliegan en un **Slide-Over Drawer lateral derecho** (`width: 440px; background: #FFFFFF; box-shadow: -8px 0 32px rgba(15, 23, 42, 0.08);`) con fondo oscurecido y difuminado (`backdrop-filter: blur(8px); background: rgba(15, 23, 42, 0.25);`).

---

## 3. MICRO-INTERACCIONES, SOMBRAS Y POLISH (EMIL-DESIGN-ENG)

### Sombras Multicapa Ópticas:
```css
/* Sombra base sutil para tarjetas y bandas */
box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.05), 0 2px 6px rgba(15, 23, 42, 0.03);

/* Sombra elevada para drawers, popovers y modales */
box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.06), 0 16px 32px -4px rgba(15, 23, 42, 0.10);
```

### Feedback Táctil en Botones:
```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  border-radius: 8px;
  padding: 8px 16px;
  cursor: pointer;
  transition: all 180ms cubic-bezier(0.16, 1, 0.3, 1);
}
.btn:active {
  transform: scale(0.98);
  transition: transform 100ms ease-out;
}
```

### Gráficas en Chart.js (Estilo Apple):
- `tension: 0.35` (curvas orgánicas suaves).
- Sin cuadrículas verticales; líneas horizontales punteadas tenues `#F1F5F9`.
- Relleno de área con gradiente vertical sutil desde el color de acento (`rgba(13, 122, 111, 0.12)`) hacia transparente (`rgba(13, 122, 111, 0.00)`).
- Tooltips personalizados con fondo oscuro (#0F172A), esquinas redondeadas (8px), padding equilibrado (8px 12px) y números tabulares.

---

## 4. CHECKLIST DE VERIFICACIÓN ANTES DE CADA ENTREGA
- [ ] ¿Hay alguna tarjeta metida dentro de otra tarjeta con borde? Si sí: **ELIMINAR EL BORDE INTERNO**.
- [ ] ¿Hay texto largo explicativo que un comerciante no necesite? Si sí: **ELIMINARLO**.
- [ ] ¿Cada cifra numérica tiene `font-variant-numeric: tabular-nums`?
- [ ] ¿Los botones tienen efecto `:active { transform: scale(0.98); }`?
- [ ] ¿Los formularios se abren en drawers o modales sin estorbar la lectura analítica?
- [ ] ¿Las 24 pruebas de `pytest` pasan limpiamente?
