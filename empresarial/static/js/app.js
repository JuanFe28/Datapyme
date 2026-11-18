/**
 * Datapyme Empresarial — Frontend Controller (Apple HIG + Impeccable + Shopify Polaris)
 * Vanilla JS optimizado, 100% libre de violaciones CSP (cero scripts inline).
 */

const ROOT_PATH = window.__ROOT_PATH__ || (window.location.pathname.startsWith('/empresarial') ? '/empresarial' : '');

// Formateador estándar de Pesos Colombianos
const copFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 2,
});

function formatCOP(amount) {
  return copFormatter.format(amount || 0);
}

// 1. Notificaciones Toast Elegantes (Máximo 1 a la vez, auto-descarte en 2s)
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  // Limpiar toasts anteriores para evitar acumulación de recuadros
  container.innerHTML = '';

  const toast = document.createElement('div');
  toast.className = 'toast';
  if (type === 'error') {
    toast.style.background = '#991B1B';
    toast.style.borderColor = '#FECACA';
  } else if (type === 'success') {
    toast.style.background = '#065F46';
    toast.style.borderColor = '#A7F3D0';
  }
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    setTimeout(() => toast.remove(), 200);
  }, 2000); // 2 segundos exactos
}
window.showToast = showToast;

// 2. Control de Slide-Over Drawers
function openDrawer(drawerId) {
  const backdrop = document.getElementById(drawerId);
  if (backdrop) {
    backdrop.classList.add('open');
    backdrop.setAttribute('aria-hidden', 'false');
    if (drawerId === 'drawer-sale' && cartLines.length === 0) {
      addCartLine();
    }
    const firstInput = backdrop.querySelector('input:not([type=hidden]), select');
    if (firstInput) {
      setTimeout(() => firstInput.focus(), 150);
    }
  }
}
window.openDrawer = openDrawer;

function closeDrawer(drawerId) {
  const backdrop = document.getElementById(drawerId);
  if (backdrop) {
    backdrop.classList.remove('open');
    backdrop.setAttribute('aria-hidden', 'true');
  }
}
window.closeDrawer = closeDrawer;

// 3. Variables de Gráficas Chart.js
let salesChart = null;
let inventoryChart = null;
let forecastChart = null;
let forecastModuleChart = null;
let paymentMethodChart = null;
let activeHeroTab = 'inventory';
let dashboardData = {};
const profitabilityCache = {};

function escapeHtmlText(str) {
  return String(str ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatQtyValue(val) {
  const num = Number(val || 0);
  if (Number.isNaN(num)) return '0';
  return Number.isInteger(num) ? String(num) : num.toFixed(2);
}

// 4. Estado del Carrito Multi-Producto
let cartLines = [];

document.addEventListener('DOMContentLoaded', () => {
  // Inicializar Iconos Lucide
  if (window.lucide) {
    lucide.createIcons();
  }

  // Leer datos del Dashboard
  const dataEl = document.getElementById('dashboard-data');
  if (dataEl) {
    try {
      dashboardData = JSON.parse(dataEl.textContent);
      if (dashboardData.profitability) {
        profitabilityCache[30] = dashboardData.profitability;
      }
    } catch (e) {
      console.error('Error parseando dashboard-data:', e);
    }
  }

  // Configurar foco inicial del gráfico
  if (dashboardData.primary_focus) {
    activeHeroTab =
      dashboardData.primary_focus === 'sales'
        ? 'sales'
        : dashboardData.primary_focus === 'predictive'
        ? 'forecast'
        : 'inventory';
  }

  // Inicializar Gráficas
  initSalesChart('30D');
  initInventoryChart();
  initForecastChart();
  initForecastModuleChart();
  initPaymentMethodChart();

  // Conectar pestañas del Hero Chart
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const tabName = btn.getAttribute('data-tab');
      if (tabName) switchHeroTab(tabName);
    });
  });

  // Conectar filtros temporales 7D, 30D, 90D, 12M (solo del Hero Header)
  document.querySelectorAll('.hero-header .horizon-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const range = btn.textContent.trim();
      updateChartRange(range, btn);
    });
  });

  // Conectar Simulador de Liberación de Efectivo (10%, 15%, 20%)
  document.querySelectorAll('#cash-discount-pills .cash-disc-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#cash-discount-pills .cash-disc-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      const pct = btn.getAttribute('data-discount') || '15';
      const scenarios = dashboardData.action_plan?.cash_release_simulator?.scenarios || {};
      const sc = scenarios[pct];
      if (sc) {
        const amtEl = document.getElementById('cash-released-amount');
        const noteEl = document.getElementById('cash-retained-note');
        if (amtEl) amtEl.textContent = formatCOP(Number(sc.cash_released_cop || 0));
        if (noteEl) {
          noteEl.innerHTML = `Efectivo recuperable manteniendo ganancia de <strong class="price-cell">${formatCOP(Number(sc.retained_profit_cop || 0))}</strong> (protegido sobre costo).`;
        }
      }
    });
  });

  // Conectar activación de Verificación en Dos Pasos (2FA) desde Mis Datos
  const dashMfaBtn = document.getElementById('btn-dash-setup-mfa');
  const dashMfaConfirm = document.getElementById('btn-dash-confirm-mfa');
  if (dashMfaBtn) {
    dashMfaBtn.addEventListener('click', async () => {
      dashMfaBtn.disabled = true;
      try {
        const res = await fetch(`${ROOT_PATH}/api/auth/mfa/setup`, {
          method: 'POST',
          headers: getAuthHeaders(),
          credentials: 'same-origin',
        });
        const data = await res.json();
        if (res.ok) {
          const panel = document.getElementById('dash-mfa-setup-panel');
          const qr = document.getElementById('dash-mfa-qr');
          const back = document.getElementById('dash-mfa-backups');
          if (qr) qr.innerHTML = data.qr_svg || '';
          if (back) back.textContent = 'Códigos de respaldo (guárdalos): ' + (data.backup_codes || []).join('  |  ');
          if (panel) panel.style.display = 'block';
        }
      } finally {
        dashMfaBtn.disabled = false;
      }
    });
  }
  if (dashMfaConfirm) {
    dashMfaConfirm.addEventListener('click', async () => {
      const code = (document.getElementById('dash-mfa-code')?.value || '').trim();
      const statusEl = document.getElementById('dash-mfa-status');
      const res = await fetch(`${ROOT_PATH}/api/auth/mfa/confirm`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        credentials: 'same-origin',
        body: JSON.stringify({ code }),
      });
      const data = await res.json();
      if (res.ok) {
        const badge = document.getElementById('dash-mfa-badge');
        if (badge) {
          badge.className = 'badge-success';
          badge.textContent = '2FA Activo';
        }
        if (statusEl) {
          statusEl.style.color = '#059669';
          statusEl.textContent = 'Verificación 2FA activada correctamente.';
        }
        showToast('Verificación en dos pasos activada', 'success');
      } else if (statusEl) {
        statusEl.style.color = '#E11D48';
        statusEl.textContent = data.detail || 'Código inválido.';
      }
    });
  }

  // Conectar pestañas de Tablas Inferiores
  document.querySelectorAll('.table-tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const viewName = btn.getAttribute('data-table-view');
      if (viewName) switchTableTab(viewName, btn);
    });
  });

  // Conectar Control Segmentado de Rentabilidad (Qué se vende más vs Qué se vende menos)
  document.querySelectorAll('#ranking-segmented-control .segmented-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const view = btn.getAttribute('data-ranking-view');
      if (view) switchRankingView(view, btn);
    });
  });

  // Conectar Navegación del Menú Lateral
  document.querySelectorAll('.sidebar-nav-link').forEach((link) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = link.getAttribute('data-section');
      if (targetId) switchModuleSection(targetId, link);
    });
  });

  // Conectar Navegación de Barra Inferior Móvil (Bottom Tab Bar)
  document.querySelectorAll('.mobile-tab-item').forEach((tab) => {
    tab.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = tab.getAttribute('data-section');
      if (targetId) switchModuleSection(targetId, tab);
    });
  });

  // Conectar botones que abren drawers
  document.querySelectorAll('[data-open-drawer]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const drawerId = btn.getAttribute('data-open-drawer');
      if (drawerId) openDrawer(drawerId);
    });
  });

  // Conectar botones que cierran drawers
  document.querySelectorAll('[data-close-drawer]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const drawerId = btn.getAttribute('data-close-drawer');
      if (drawerId) closeDrawer(drawerId);
    });
  });

  // Cerrar al hacer click fuera del drawer (en el backdrop), bloqueado durante tour activo
  document.querySelectorAll('.drawer-backdrop').forEach((backdrop) => {
    backdrop.addEventListener('click', (e) => {
      if (window.__SPOTLIGHT_TRAINING_ACTIVE__ && document.querySelector('.dp-spotlight-layer')) {
        return;
      }
      if (e.target === backdrop) {
        backdrop.classList.remove('open');
      }
    });
  });

  // Cerrar al pulsar Escape, bloqueado durante tour activo
  document.addEventListener('keydown', (e) => {
    if (window.__SPOTLIGHT_TRAINING_ACTIVE__ && document.querySelector('.dp-spotlight-layer')) {
      return;
    }
    if (e.key === 'Escape') {
      document.querySelectorAll('.drawer-backdrop.open').forEach((el) => el.classList.remove('open'));
    }
  });

  // Conectar botones de venta rápida en la tabla (+ Vender)
  document.querySelectorAll('.btn-quick-sale').forEach((btn) => {
    btn.addEventListener('click', () => {
      const prodId = btn.getAttribute('data-prod-id');
      const price = btn.getAttribute('data-prod-price');
      quickSaleProduct(prodId, price);
    });
  });

  // Conectar botón para agregar líneas al carrito en el Drawer de Venta
  const btnAddCartLine = document.getElementById('btn-add-cart-line');
  if (btnAddCartLine) {
    btnAddCartLine.addEventListener('click', () => addCartLine());
  }

  // Envíos de Formularios Asíncronos
  const formSale = document.getElementById('form-sale');
  if (formSale) formSale.addEventListener('submit', handleSaleSubmit);

  const formProduct = document.getElementById('form-product');
  if (formProduct) formProduct.addEventListener('submit', handleProductSubmit);

  const formImport = document.getElementById('form-import');
  const taxForm = document.getElementById('company-tax-form');
  if (taxForm) taxForm.addEventListener('submit', handleCompanyTaxChange);
  if (formImport) formImport.addEventListener('submit', handleImportSubmit);

  // Subida con preview instantáneo de foto de producto
  const prodImgInput = document.getElementById('prod-image-file');
  if (prodImgInput) {
    prodImgInput.addEventListener('change', handleProductImageSelection);
  }

  // Inspección interactiva de archivo Excel/CSV
  const importFileInput = document.getElementById('import-file');
  if (importFileInput) {
    importFileInput.addEventListener('change', handleImportFileInspection);
  }

  const importSheetSelect = document.getElementById('import-sheet-select');
  if (importSheetSelect) {
    importSheetSelect.addEventListener('change', () =>
      handleImportFileInspection(null, importSheetSelect.value)
    );
  }

  // Conectar botones de edición de producto (Editar)
  document.querySelectorAll('.btn-edit-product').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const prodId = btn.getAttribute('data-prod-id');
      if (prodId) openEditProductDrawer(prodId);
    });
  });

  // Conectar botones de ver detalle de venta y links de número de venta
  document.querySelectorAll('.btn-view-sale, .sale-number-link').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const saleId = btn.getAttribute('data-sale-id');
      if (saleId) openSaleDetailDrawer(saleId);
    });
  });

  // Formulario de edición de producto
  const formEditProd = document.getElementById('form-edit-product');
  if (formEditProd) formEditProd.addEventListener('submit', handleEditProductSubmit);

  // Margen en vivo en edición de producto
  const editCostInput = document.getElementById('edit-prod-cost');
  const editPriceInput = document.getElementById('edit-prod-price');
  if (editCostInput) editCostInput.addEventListener('input', calculateEditProductMargin);
  if (editPriceInput) editPriceInput.addEventListener('input', calculateEditProductMargin);

  // Imagen en edición de producto
  const editImgFile = document.getElementById('edit-prod-image-file');
  if (editImgFile) editImgFile.addEventListener('change', handleEditProductImageSelection);

  // Toggle de ajuste de stock en edición
  const editStockToggle = document.getElementById('edit-stock-toggle');
  if (editStockToggle) {
    editStockToggle.addEventListener('change', () => {
      const adjFields = document.getElementById('edit-stock-adjustment-fields');
      if (adjFields) adjFields.style.display = editStockToggle.checked ? 'block' : 'none';
    });
  }
});

// --- LÓGICA DE NAVEGACIÓN ENTRE MÓDULOS (MENÚ LATERAL Y BARRA MÓVIL) ---
function switchModuleSection(sectionId, clickedLink) {
  // Actualizar clases activas en sidebar y barra inferior móvil
  document.querySelectorAll('.sidebar-nav-link').forEach((l) => l.classList.remove('active'));
  document.querySelectorAll('.mobile-tab-item').forEach((t) => t.classList.remove('active'));

  // Activar links correspondientes en ambos componentes
  document.querySelectorAll(`[data-section="${sectionId}"]`).forEach((el) => el.classList.add('active'));

  const sections = document.querySelectorAll('.dashboard-module-section');
  const targetSection = document.getElementById(sectionId);

  if (targetSection && sections.length > 0) {
    sections.forEach((s) => (s.style.display = 'none'));
    targetSection.style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else {
    const targetAnchor = document.getElementById(sectionId) || document.querySelector(`[data-anchor="${sectionId}"]`);
    if (targetAnchor) {
      targetAnchor.scrollIntoView({ behavior: 'smooth' });
    }
  }

  // Refrescar tamaño de gráficas si se muestran
  if (salesChart) salesChart.resize();
  if (inventoryChart) inventoryChart.resize();
  if (forecastChart) forecastChart.resize();
  if (forecastModuleChart) forecastModuleChart.resize();
}

// --- LÓGICA DE PESTAÑAS DEL HERO (VENTAS / INVENTARIO / PRONÓSTICO) ---
function switchHeroTab(tabName) {
  activeHeroTab = tabName;

  document.querySelectorAll('.tab-btn').forEach((b) => {
    b.classList.toggle('active', b.getAttribute('data-tab') === tabName);
  });

  document.querySelectorAll('.tab-panel').forEach((p) => {
    p.style.display = 'none';
  });

  const panel = document.getElementById(`tab-content-${tabName}`);
  if (panel) {
    panel.style.display = 'block';
  }

  setTimeout(() => {
    if (tabName === 'sales' && salesChart) salesChart.resize();
    if (tabName === 'inventory' && inventoryChart) inventoryChart.resize();
    if (tabName === 'forecast' && forecastChart) forecastChart.resize();
  }, 50);
}

function getRangeDays(rangeLabel) {
  if (rangeLabel === '7D') return 7;
  if (rangeLabel === '90D') return 90;
  if (rangeLabel === '12M') return 365;
  return 30;
}

function getSeriesFromPayload(payload) {
  const s = (payload && payload.series) || {};
  return {
    labels: Array.isArray(s.labels) ? s.labels.slice() : [],
    revenue: Array.isArray(s.revenue) ? s.revenue.map((v) => Number(v) || 0) : [],
    netProfit: Array.isArray(s.net_profit) ? s.net_profit.map((v) => Number(v) || 0) : [],
    lossesAndCosts: Array.isArray(s.losses_and_costs) ? s.losses_and_costs.map((v) => Number(v) || 0) : [],
  };
}

function switchRankingView(viewName, btn) {
  document.querySelectorAll('#ranking-segmented-control .segmented-btn').forEach((b) => {
    const active = b.getAttribute('data-ranking-view') === viewName;
    b.classList.toggle('active', active);
    b.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  if (btn) btn.classList.add('active');

  const topPanel = document.getElementById('ranking-panel-top');
  const leastPanel = document.getElementById('ranking-panel-least');
  if (topPanel) topPanel.style.display = viewName === 'top' ? 'block' : 'none';
  if (leastPanel) leastPanel.style.display = viewName === 'least' ? 'block' : 'none';
}

function buildThumbnailHtml(item) {
  if (item.image_url) {
    return `<img src="${escapeHtmlText(item.image_url)}" alt="${escapeHtmlText(item.name)}" style="width: 34px; height: 34px; object-fit: cover; border-radius: 6px; border: 1px solid rgba(15, 23, 42, 0.08); flex-shrink: 0;">`;
  }
  const initials = escapeHtmlText(String(item.name || '').slice(0, 2).toUpperCase());
  return `<div style="width: 34px; height: 34px; border-radius: 6px; background: var(--surface-subtle); display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; color: var(--ink-muted); flex-shrink: 0;">${initials}</div>`;
}

function applyProfitabilityPayload(payload, rangeLabel) {
  if (!payload) return;
  const pnl = payload.pnl || {};
  const series = getSeriesFromPayload(payload);

  if (salesChart) {
    salesChart.data.labels = series.labels;
    salesChart.data.datasets[0].data = series.revenue;
    if (salesChart.data.datasets[1]) salesChart.data.datasets[1].data = series.netProfit;
    if (salesChart.data.datasets[2]) salesChart.data.datasets[2].data = series.lossesAndCosts;
    salesChart.update();
  }

  const netRevEl = document.getElementById('pnl-net-revenue');
  const cogsEl = document.getElementById('pnl-cogs');
  const netProfitEl = document.getElementById('pnl-net-profit');
  const netMarginEl = document.getElementById('pnl-net-margin');
  const lossesEl = document.getElementById('pnl-total-losses');
  const breakdownEl = document.getElementById('pnl-breakdown-note');
  const periodLabelEl = document.getElementById('pnl-period-label');
  const rankingBadgeEl = document.getElementById('ranking-period-badge');
  const immEl = document.getElementById('pnl-immobilized-note');

  if (netRevEl) netRevEl.textContent = formatCOP(Number(pnl.net_revenue || 0));
  if (cogsEl) cogsEl.textContent = formatCOP(Number(pnl.cogs_total || 0));
  if (netProfitEl) netProfitEl.textContent = formatCOP(Number(pnl.net_profit_after_losses_cop || 0));
  if (netMarginEl) netMarginEl.textContent = `Margen neto: ${pnl.net_margin_after_losses_pct || '0.00'}%`;
  if (lossesEl) lossesEl.textContent = formatCOP(Number(pnl.total_losses_cop || 0));
  if (breakdownEl) {
    breakdownEl.textContent = `Mermas: ${formatCOP(Number(pnl.shrinkage_loss_cop || 0))} · Bajo costo: ${formatCOP(Number(pnl.below_cost_loss_cop || 0))}`;
  }
  if (periodLabelEl) periodLabelEl.textContent = rangeLabel;
  if (rankingBadgeEl) rankingBadgeEl.textContent = rangeLabel;
  if (immEl) {
    immEl.innerHTML = `Capital sin rotación (30D): <strong style="color: var(--ink-primary); font-variant-numeric: tabular-nums;">${formatCOP(Number(pnl.immobilized_capital_30d_cop || 0))}</strong>`;
  }

  const topItems = payload.top_selling_products || [];
  const leastItems = payload.least_selling_and_loss_products || [];

  const topBtn = document.querySelector('#ranking-segmented-control [data-ranking-view="top"]');
  const leastBtn = document.querySelector('#ranking-segmented-control [data-ranking-view="least"]');
  if (topBtn) topBtn.textContent = `Qué se vende más (${topItems.length})`;
  if (leastBtn) leastBtn.textContent = `Qué se vende menos y Pérdidas (${leastItems.length})`;

  const topBody = document.getElementById('top-products-tbody');
  if (topBody) {
    topBody.innerHTML = topItems.length
      ? topItems
          .map((item) => {
            const profitNum = Number(item.profit_cop || 0);
            const marginNum = Number(item.margin_pct || 0);
            const profitColor = profitNum < 0 ? '#E11D48' : '#059669';
            const badgeCls = marginNum >= 20 ? 'badge-success' : marginNum > 0 ? 'badge-warning' : 'badge-danger';
            return `<tr>
              <td data-label="Producto"><div style="display: flex; align-items: center; gap: 10px;">${buildThumbnailHtml(item)}<div><div style="font-weight: 600; color: var(--ink-primary);">${escapeHtmlText(item.name)}</div><div style="font-size: 11px; color: var(--ink-muted); font-family: var(--font-mono);">${escapeHtmlText(item.sku)}</div></div></div></td>
              <td data-label="Unidades" class="price-cell" style="text-align: right; font-weight: 600;">${formatQtyValue(item.units_sold)} <span style="font-size: 11px; color: var(--ink-muted); font-weight: 400;">${escapeHtmlText(item.unit)}</span></td>
              <td data-label="Participación"><div style="display: flex; align-items: center; gap: 8px; min-width: 110px;"><div class="share-bar-track"><div class="share-bar-fill" style="width: ${Number(item.revenue_share_pct || 0)}%;"></div></div><span class="price-cell" style="font-size: 11px; color: var(--ink-secondary);">${escapeHtmlText(item.revenue_share_pct)}%</span></div></td>
              <td data-label="Ingresos Netos" class="price-cell" style="text-align: right;">${formatCOP(Number(item.net_revenue || 0))}</td>
              <td data-label="Costo (COGS)" class="price-cell" style="text-align: right; color: var(--ink-muted);">${formatCOP(Number(item.cogs_total || 0))}</td>
              <td data-label="Ganancia Real" class="price-cell" style="text-align: right; font-weight: 600; color: ${profitColor};">${formatCOP(profitNum)}</td>
              <td data-label="Margen" class="price-cell" style="text-align: right;"><span class="${badgeCls}">${escapeHtmlText(item.margin_pct)}%</span></td>
            </tr>`;
          })
          .join('')
      : `<tr><td colspan="7" style="text-align: center; color: var(--ink-muted); padding: 28px;">Aún no se registran ventas confirmadas en este horizonte de tiempo.</td></tr>`;
  }

  const leastBody = document.getElementById('least-products-tbody');
  if (leastBody) {
    leastBody.innerHTML = leastItems.length
      ? leastItems
          .map((item) => {
            const totalLoss = Number(item.shrinkage_loss_cop || 0) + Number(item.below_cost_loss_cop || 0);
            const lossColor = totalLoss > 0 ? '#E11D48' : 'var(--ink-muted)';
            const diagCls =
              item.diagnosis_severity === 'danger'
                ? 'badge-danger'
                : item.diagnosis_severity === 'warning'
                ? 'badge-warning'
                : 'badge-info';
            return `<tr>
              <td data-label="Producto"><div style="display: flex; align-items: center; gap: 10px;">${buildThumbnailHtml(item)}<div><div style="font-weight: 600; color: var(--ink-primary);">${escapeHtmlText(item.name)}</div><div style="font-size: 11px; color: var(--ink-muted); font-family: var(--font-mono);">${escapeHtmlText(item.sku)}</div></div></div></td>
              <td data-label="Vendidas" class="price-cell" style="text-align: right; font-weight: 600;">${formatQtyValue(item.units_sold)}</td>
              <td data-label="Stock Actual" class="price-cell" style="text-align: right;">${formatQtyValue(item.stock_qty)} ${escapeHtmlText(item.unit)}</td>
              <td data-label="Dinero Estancado" class="price-cell" style="text-align: right; font-weight: 600; color: var(--ink-primary);">${formatCOP(Number(item.stock_value_cop || 0))}</td>
              <td data-label="Última Venta" style="font-size: 12px; color: var(--ink-secondary);">${escapeHtmlText(item.last_sale_label)}</td>
              <td data-label="Merma / Pérdida" class="price-cell" style="text-align: right; font-weight: 600; color: ${lossColor};">${formatCOP(totalLoss)}</td>
              <td data-label="Diagnóstico Automático"><span class="${diagCls}">${escapeHtmlText(item.diagnosis)}</span></td>
            </tr>`;
          })
          .join('')
      : `<tr><td colspan="7" style="text-align: center; color: var(--ink-muted); padding: 28px;">Todos los productos del catálogo registran rotación saludable sin alertas de pérdida.</td></tr>`;
  }

  // Actualizar barras por categoría y gráfico donut de métodos de pago
  const catBox = document.getElementById('category-bars-container');
  const cats = (payload.category_distribution || []).slice(0, 5);
  if (catBox) {
    catBox.innerHTML = cats.length
      ? cats
          .map(
            (c) => `<div class="cat-bar-row">
              <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
                <span style="font-weight: 600; color: var(--ink-primary);">${escapeHtmlText(c.category)}</span>
                <span class="price-cell" style="color: var(--ink-secondary);">${formatCOP(Number(c.net_revenue || 0))} (${escapeHtmlText(c.share_pct)}%)</span>
              </div>
              <div class="share-bar-track"><div class="share-bar-fill" style="width: ${Number(c.share_pct || 0)}%;"></div></div>
            </div>`
          )
          .join('')
      : `<p style="font-size: 12px; color: var(--ink-muted); margin: 12px 0 0;">Sin ventas por categoría registradas aún en el periodo.</p>`;
  }

  if (paymentMethodChart) {
    const pms = payload.payment_method_distribution || [];
    const hasData = pms.some((p) => Number(p.net_revenue || 0) > 0);
    paymentMethodChart.data.labels = hasData ? pms.map((p) => p.label) : ['Sin ventas'];
    paymentMethodChart.data.datasets[0].data = hasData ? pms.map((p) => Number(p.net_revenue || 0)) : [1];
    paymentMethodChart.data.datasets[0].backgroundColor = hasData
      ? ['#0D7A6F', '#059669', '#0284C7', '#D97706', '#64748B']
      : ['#E2E8F0'];
    paymentMethodChart.options.plugins.tooltip.enabled = hasData;
    paymentMethodChart.update();
  }
}

function initPaymentMethodChart() {
  const ctx = document.getElementById('paymentMethodChart');
  if (!ctx || !window.Chart) return;
  const pms = dashboardData.profitability?.payment_method_distribution || [];
  const hasData = pms.some((p) => Number(p.net_revenue || 0) > 0);
  const labels = hasData ? pms.map((p) => p.label) : ['Sin ventas'];
  const values = hasData ? pms.map((p) => Number(p.net_revenue || 0)) : [1];
  const palette = hasData
    ? ['#0D7A6F', '#059669', '#0284C7', '#D97706', '#64748B']
    : ['#E2E8F0'];

  paymentMethodChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: palette,
          borderWidth: 0,
          hoverOffset: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '66%',
      plugins: {
        legend: {
          position: 'right',
          labels: { boxWidth: 10, font: { family: 'Inter', size: 11 }, color: '#475569' },
        },
        tooltip: {
          enabled: hasData,
          callbacks: {
            label: (item) => ` ${item.label}: ${formatCOP(item.raw)}`,
          },
        },
      },
    },
  });
}

// --- FILTRADO TEMPORAL DINÁMICO REAL (7D, 30D, 90D, 12M) ---
async function updateChartRange(rangeLabel, btn) {
  document.querySelectorAll('.hero-header .horizon-btn').forEach((b) => b.classList.remove('active'));
  if (btn) btn.classList.add('active');

  const days = getRangeDays(rangeLabel);
  if (profitabilityCache[days]) {
    applyProfitabilityPayload(profitabilityCache[days], rangeLabel);
    return;
  }

  try {
    const res = await fetch(`${ROOT_PATH}/api/analytics/profitability?period_days=${days}`, {
      headers: getAuthHeaders(),
      credentials: 'same-origin',
    });
    if (!res.ok) return;
    const payload = await res.json();
    profitabilityCache[days] = payload;
    applyProfitabilityPayload(payload, rangeLabel);
  } catch (err) {
    console.error('Error actualizando horizonte de rentabilidad:', err);
  }
}

// --- PESTAÑAS DE TABLAS OPERATIVAS (SHOPIFY POLARIS) ---
function switchTableTab(viewName, btn) {
  document.querySelectorAll('.table-tab-btn').forEach((b) => b.classList.remove('active'));
  if (btn) btn.classList.add('active');

  const vInventory = document.getElementById('table-view-inventory');
  const vSales = document.getElementById('table-view-sales');
  const vPareto = document.getElementById('table-view-pareto');

  if (vInventory) vInventory.style.display = viewName === 'inventory' ? 'block' : 'none';
  if (vSales) vSales.style.display = viewName === 'sales' ? 'block' : 'none';
  if (vPareto) vPareto.style.display = viewName === 'pareto' ? 'block' : 'none';
}

// --- INICIALIZACIÓN DE GRÁFICAS (CHART.JS) ---
function initSalesChart(initialRange = '30D') {
  const ctx = document.getElementById('salesTrendChart');
  if (!ctx || !window.Chart) return;

  const days = getRangeDays(initialRange);
  const initialPayload = profitabilityCache[days] || dashboardData.profitability || {};
  const chartData = getSeriesFromPayload(initialPayload);

  salesChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: chartData.labels,
      datasets: [
        {
          label: 'Ingresos Netos ($)',
          data: chartData.revenue,
          borderColor: '#0D7A6F',
          backgroundColor: 'rgba(13, 122, 111, 0.08)',
          fill: true,
          tension: 0.3,
          borderWidth: 2.2,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: '#FFFFFF',
          pointBorderColor: '#0D7A6F',
          pointBorderWidth: 2,
        },
        {
          label: 'Ganancia Neta Real ($)',
          data: chartData.netProfit,
          borderColor: '#059669',
          backgroundColor: 'rgba(5, 150, 105, 0.04)',
          fill: false,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 3.5,
          pointHoverRadius: 5,
          pointBackgroundColor: '#FFFFFF',
          pointBorderColor: '#059669',
          pointBorderWidth: 2,
        },
        {
          label: 'Costos y Pérdidas ($)',
          data: chartData.lossesAndCosts,
          borderColor: '#E11D48',
          backgroundColor: 'rgba(225, 29, 72, 0.04)',
          borderDash: [5, 4],
          fill: false,
          tension: 0.3,
          borderWidth: 1.8,
          pointRadius: 3,
          pointHoverRadius: 5,
          pointBackgroundColor: '#FFFFFF',
          pointBorderColor: '#E11D48',
          pointBorderWidth: 1.8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            usePointStyle: true,
            boxWidth: 8,
            font: { family: 'Inter', size: 11, weight: '600' },
            color: '#475569',
          },
        },
        tooltip: {
          backgroundColor: '#0F172A',
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (item) => ` ${item.dataset.label}: ${formatCOP(item.raw)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { family: 'Inter', size: 11 }, color: '#64748B' },
        },
        y: {
          grid: { color: '#F1F5F9' },
          ticks: {
            font: { family: 'Inter', size: 11 },
            color: '#64748B',
            callback: (v) => formatCOP(v),
          },
        },
      },
    },
  });
}

function initInventoryChart() {
  const ctx = document.getElementById('inventoryStockChart');
  if (!ctx || !window.Chart) return;

  const prods = dashboardData.products || [];
  const topProds = prods.slice(0, 8);
  const labels = topProds.map((p) => p.sku || 'SKU');
  const stockData = topProds.map((p) => parseFloat(p.stock_qty) || 0);
  const minData = topProds.map((p) => parseFloat(p.min_stock) || 0);

  inventoryChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels.length ? labels : ['CEM-ARG-50', 'TAL-BOS-650', 'MAR-EST-16', 'PIN-VIN-05'],
      datasets: [
        {
          label: 'Stock Actual',
          data: stockData.length ? stockData : [30, 15, 24, 20],
          backgroundColor: '#0D7A6F',
          borderRadius: 6,
        },
        {
          label: 'Stock Mínimo',
          data: minData.length ? minData : [25, 4, 6, 5],
          backgroundColor: '#E2E8F0',
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { boxWidth: 12, font: { family: 'Inter', size: 12 } },
        },
        tooltip: {
          backgroundColor: '#0F172A',
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (item) => ` ${item.dataset.label}: ${item.raw} und`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { family: 'Inter', size: 11 }, color: '#64748B' },
        },
        y: {
          grid: { color: '#F1F5F9' },
          ticks: { font: { family: 'Inter', size: 11 }, color: '#64748B' },
        },
      },
    },
  });
}

function initForecastChart() {
  const ctx = document.getElementById('forecastOlsChart');
  if (!ctx || !window.Chart) return;

  const forecast = dashboardData.forecast || {};
  if (forecast.status !== 'ok') return;
  const audit = forecast.audit_table || [];
  let labels = [];
  let histData = [];

  if (audit.length >= 3) {
    labels = audit.map((r) => r.period_label || `P${r.period_index}`);
    histData = audit.map((r) => r.observed_y);
    labels.push('Proyección (t+1)');
    histData.push(forecast.next_period_ols ?? null);
  } else {
    return;
  }

  forecastChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Ajuste OLS e Histórico',
          data: histData,
          borderColor: '#1E3A8A',
          backgroundColor: 'rgba(30, 58, 138, 0.05)',
          borderWidth: 2.2,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: '#FFFFFF',
          pointBorderColor: '#1E3A8A',
          segment: {
            borderDash: (ctx) => (ctx.p1DataIndex === histData.length - 1 ? [6, 6] : undefined),
          },
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0F172A',
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (item) => ' ' + formatCOP(item.raw),
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { family: 'Inter', size: 11 }, color: '#64748B' },
        },
        y: {
          grid: { color: '#F1F5F9', borderDash: [4, 4] },
          ticks: {
            font: { family: 'Inter', size: 11 },
            color: '#64748B',
            callback: (v) => formatCOP(v),
          },
        },
      },
    },
  });
}

function initForecastModuleChart() {
  const ctx = document.getElementById('forecastModuleChart');
  if (!ctx || !window.Chart) return;

  const forecast = dashboardData.forecast || {};
  if (forecast.status !== 'ok') return;
  const audit = forecast.audit_table || [];
  let labels = [];
  let histData = [];

  if (audit.length >= 3) {
    labels = audit.map((r) => r.period_label || `P${r.period_index}`);
    histData = audit.map((r) => r.observed_y);
    labels.push('Proyección (t+1)');
    histData.push(forecast.next_period_ols ?? null);
  } else {
    return;
  }

  forecastModuleChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: structuredClone(labels),
      datasets: [
        {
          label: 'Ventas Reales y Proyección OLS',
          data: structuredClone(histData),
          borderColor: '#1E3A8A',
          backgroundColor: 'rgba(30, 58, 138, 0.05)',
          borderWidth: 2.4,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: '#FFFFFF',
          pointBorderColor: '#1E3A8A',
          segment: {
            borderDash: (ctx) => (ctx.p1DataIndex === histData.length - 1 ? [6, 6] : undefined),
          },
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0F172A',
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (item) => ' ' + formatCOP(item.raw),
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { family: 'Inter', size: 11 }, color: '#64748B' },
        },
        y: {
          grid: { color: '#F1F5F9', borderDash: [4, 4] },
          ticks: {
            font: { family: 'Inter', size: 11 },
            color: '#64748B',
            callback: (v) => formatCOP(v),
          },
        },
      },
    },
  });
}

// --- CARRITO MULTI-PRODUCTO EN "+ REGISTRAR VENTA" ---
function getProductsCatalog() {
  return dashboardData.products || [];
}

function renderCart() {
  const container = document.getElementById('sale-cart-items');
  if (!container) return;

  const prods = getProductsCatalog();
  container.innerHTML = '';

  cartLines.forEach((line, index) => {
    const row = document.createElement('div');
    row.className = 'cart-item-row';

    // Miniatura visual del producto
    const selectedProd = prods.find((p) => p.id === line.product_id) || prods[0];
    const thumbWrap = document.createElement('div');
    thumbWrap.style.flexShrink = '0';
    function updateThumb(p) {
      if (p && p.image_url) {
        thumbWrap.innerHTML = `<img src="${escapeHtmlText(ROOT_PATH+p.image_url)}" class="product-avatar-img" style="width: 36px; height: 36px; border-radius: 6px;">`;
      } else {
        const init = (p ? p.name : 'PR').slice(0, 2).toUpperCase();
        thumbWrap.innerHTML = `<div class="product-avatar-fallback" style="width: 36px; height: 36px; font-size: 11px; border-radius: 6px;">${escapeHtmlText(init)}</div>`;
      }
    }
    updateThumb(selectedProd);

    // 1. Selector de Producto
    const select = document.createElement('select');
    select.className = 'form-input cart-product-select';
    select.required = true;
    select.setAttribute('data-index', index);

    prods.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.sku} - ${p.name} (Stock: ${p.stock_qty} | ${formatCOP(p.sale_price)})`;
      opt.setAttribute('data-price', p.sale_price);
      opt.setAttribute('data-stock', p.stock_qty);
      if (p.id === line.product_id) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });

    select.addEventListener('change', (e) => {
      cartLines[index].product_id = e.target.value;
      const newProd = prods.find((p) => p.id === e.target.value);
      updateThumb(newProd);
      const selectedOpt = e.target.selectedOptions[0];
      if (selectedOpt) {
        cartLines[index].unit_price = parseFloat(selectedOpt.getAttribute('data-price')) || 0;
        cartLines[index].max_stock = parseFloat(selectedOpt.getAttribute('data-stock')) || 0;
      }
      calculateCartTotals();
    });

    // 2. Input de Cantidad
    const qtyWrap = document.createElement('div');
    const qtyInput = document.createElement('input');
    qtyInput.type = 'number';
    qtyInput.min = '0.001';
    qtyInput.step = '0.001';
    qtyInput.className = 'form-input cart-quantity-input';
    qtyInput.value = line.quantity || 1;
    qtyInput.setAttribute('data-index', index);

    qtyInput.addEventListener('input', (e) => {
      const val = Number(e.target.value);
      cartLines[index].quantity = Number.isFinite(val) && val > 0 ? val : 0;
      calculateCartTotals();
    });
    qtyWrap.appendChild(qtyInput);

    // 3. Subtotal de la línea
    const subtotalDisplay = document.createElement('div');
    subtotalDisplay.className = 'price-cell';
    subtotalDisplay.style.fontSize = '13px';
    subtotalDisplay.style.fontWeight = '600';
    subtotalDisplay.style.textAlign = 'right';
    subtotalDisplay.style.padding = '8px 0';
    const lineTotal = (line.quantity || 1) * (line.unit_price || 0);
    subtotalDisplay.textContent = formatCOP(lineTotal);

    // 4. Botón Quitar Línea
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'cart-btn-remove';
    removeBtn.title = 'Quitar este producto de la venta';
    removeBtn.textContent = 'X';
    if (cartLines.length <= 1) {
      removeBtn.style.opacity = '0.3';
      removeBtn.style.cursor = 'not-allowed';
      removeBtn.disabled = true;
    } else {
      removeBtn.addEventListener('click', () => {
        cartLines.splice(index, 1);
        renderCart();
        calculateCartTotals();
      });
    }

    row.appendChild(thumbWrap);
    row.appendChild(select);
    row.appendChild(qtyWrap);
    row.appendChild(subtotalDisplay);
    row.appendChild(removeBtn);
    container.appendChild(row);
  });
}

function addCartLine(defaultProdId = null) {
  const prods = getProductsCatalog();
  if (!prods.length) return;

  const targetProd = defaultProdId
    ? prods.find((p) => p.id === defaultProdId) || prods[0]
    : prods.find((p) => !cartLines.some((cl) => cl.product_id === p.id)) || prods[0];

  cartLines.push({
    product_id: targetProd.id,
    quantity: 1,
    unit_price: parseFloat(targetProd.sale_price) || 0,
    max_stock: parseFloat(targetProd.stock_qty) || 0,
  });

  renderCart();
  calculateCartTotals();
}

function scaledUnsigned(value, places) {
  const text = String(value ?? 0);
  if (!/^\d+(?:\.\d+)?$/.test(text)) return 0n;
  const [whole,fraction=''] = text.split('.');
  return BigInt(whole) * 10n ** BigInt(places) + BigInt(fraction.slice(0,places).padEnd(places,'0') || '0');
}

function lineAmounts(quantity, price, rate) {
  const baseCents=(scaledUnsigned(quantity,3)*scaledUnsigned(price,2)+500n)/1000n;
  const vatCents=(baseCents*scaledUnsigned(rate,2)+5000n)/10000n;
  return {base:Number(baseCents)/100,vat:Number(vatCents)/100};
}

function calculateCartTotals() {
  const prods = getProductsCatalog();
  let grossSum = 0;
  let vatTotal = 0;
  const rawTaxStatus = dashboardData.company_tax?.status || 'pending';
  const taxStatus = rawTaxStatus === 'pending' && window.__SPOTLIGHT_TRAINING_ACTIVE__ ? 'not_responsible' : rawTaxStatus;
  let hasStockExceeded = taxStatus === 'pending';
  let stockErrorMsg = hasStockExceeded ? 'Confirma la condición de IVA de la empresa antes de vender.' : '';

  cartLines.forEach((line) => {
    const prod = prods.find((p) => p.id === line.product_id);
    const price = prod ? parseFloat(prod.sale_price) || 0 : line.unit_price;
    const stock = prod ? parseFloat(prod.stock_qty) || 0 : line.max_stock;
    const qty = line.quantity || 0;

    line.unit_price = price;
    line.max_stock = stock;

    if (qty > stock) {
      hasStockExceeded = true;
      stockErrorMsg = `La cantidad para '${prod ? prod.name : 'un producto'}' (${qty} und) supera el stock disponible (${stock} und).`;
    }
    if (qty <= 0) {
      hasStockExceeded = true;
      stockErrorMsg = 'Ingrese una cantidad mayor a cero (hasta tres decimales).';
    }

    const rate = taxStatus === 'not_responsible' ? 0 : (prod ? Number(prod.vat_rate) : 0);
    const amounts=lineAmounts(qty,price,rate);
    grossSum += amounts.base;
    vatTotal += amounts.vat;
  });

  // Base e IVA por artículo; el servidor confirma los importes definitivos.
  const subtotal = grossSum;
  const total = subtotal + vatTotal;

  const subtotalEl = document.getElementById('sale-subtotal-display');
  const vatEl = document.getElementById('sale-vat-display');
  const totalEl = document.getElementById('sale-total-display');
  const warningEl = document.getElementById('cart-stock-warning');
  const warningText = document.getElementById('cart-stock-warning-text');
  const submitBtn = document.getElementById('btn-submit-sale');

  if (subtotalEl) subtotalEl.textContent = formatCOP(subtotal);
  if (vatEl) vatEl.textContent = taxStatus === 'pending' ? 'Por confirmar' : formatCOP(vatTotal);
  if (totalEl) totalEl.textContent = taxStatus === 'pending' ? 'Por confirmar' : formatCOP(total);

  if (warningEl) {
    if (hasStockExceeded) {
      warningEl.style.display = 'block';
      if (warningText) warningText.textContent = stockErrorMsg;
      if (submitBtn) submitBtn.disabled = true;
    } else {
      warningEl.style.display = 'none';
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  // Actualizar subtotales individuales de cada línea
  const rows = document.querySelectorAll('#sale-cart-items .cart-item-row');
  rows.forEach((row, idx) => {
    if (cartLines[idx]) {
      const lineTotal = (cartLines[idx].quantity || 1) * (cartLines[idx].unit_price || 0);
      const subtotalCol = row.querySelector('.price-cell');
      if (subtotalCol) subtotalCol.textContent = formatCOP(lineTotal);
    }
  });
}

function getAuthHeaders(extra = {}) {
  const h = { ...extra };
  if (dashboardData && dashboardData.token) {
    h['Authorization'] = `Bearer ${dashboardData.token}`;
  }
  return h;
}

function quickSaleProduct(prodId, price) {
  cartLines = [];
  addCartLine(prodId);
  openDrawer('drawer-sale');
}

async function handleSaleSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-submit-sale');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Procesando venta...';
  }

  const customer = document.getElementById('sale-customer').value || 'Cliente Mostrador';
  const payment = document.getElementById('sale-payment').value || 'cash';

  if (!cartLines.length) {
    showToast('Agregue al menos un producto a la venta', 'error');
    if (btn) btn.disabled = false;
    return;
  }

  const itemsPayload = cartLines.map((it) => ({
    product_id: it.product_id,
    quantity: it.quantity,
    unit_price: it.unit_price,
  }));

  try {
    const resp = await fetch(`${ROOT_PATH}/api/sales`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        tax_revision: dashboardData.company_tax?.revision,
        customer_label: customer,
        payment_method: payment,
        items: itemsPayload,
        is_training_data: Boolean(window.__SPOTLIGHT_TRAINING_ACTIVE__),
      }),
    });
    if (resp.ok) {
      showToast('Venta registrada con éxito. Kardex actualizado.', 'success');
      closeDrawer('drawer-sale');
      setTimeout(() => location.reload(), 700);
    } else {
      const err = await resp.json();
      showToast(err.detail || 'Error al registrar la venta', 'error');
    }
  } catch (err) {
    showToast('Error de conexión con el servidor', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Confirmar Venta';
    }
  }
}

async function handleProductImageSelection(e) {
  const file = e.target.files[0];
  const previewBox = document.getElementById('prod-img-preview-box');
  const statusEl = document.getElementById('prod-img-upload-status');
  const urlHidden = document.getElementById('prod-image-url');

  if (!file) {
    if (previewBox) {
      previewBox.innerHTML = '<i data-lucide="image" style="width: 22px; height: 22px; color: var(--ink-muted);"></i>';
      if (window.lucide) window.lucide.createIcons();
    }
    if (urlHidden) urlHidden.value = '';
    return;
  }

  if (file.size > 2 * 1024 * 1024) {
    showToast('La imagen supera el límite de 2 MB', 'error');
    e.target.value = '';
    return;
  }

  // Previsualización instantánea local
  const reader = new FileReader();
  reader.onload = (evt) => {
    if (previewBox) {
      previewBox.innerHTML = `<img src="${evt.target.result}" style="width: 100%; height: 100%; object-fit: cover;">`;
    }
  };
  reader.readAsDataURL(file);

  // Subida asíncrona al backend para obtener URL segura
  if (statusEl) statusEl.textContent = 'Subiendo imagen...';
  const formData = new FormData();
  formData.append('file', file);

  try {
    const resp = await fetch(`${ROOT_PATH}/api/products/upload-image`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    if (resp.ok) {
      const data = await resp.json();
      if (urlHidden) urlHidden.value = data.image_url;
      if (statusEl) {
        statusEl.innerHTML = '<span style="color: #059669; font-weight: 500;">Foto cargada exitosamente.</span>';
      }
    } else {
      const err = await resp.json();
      if (statusEl) {
        statusEl.innerHTML = `<span style="color: #DC2626;">Error: ${err.detail || 'Archivo rechazado'}</span>`;
      }
      if (urlHidden) urlHidden.value = '';
    }
  } catch (err) {
    if (statusEl) {
      statusEl.innerHTML = '<span style="color: #DC2626;">Error al conectar con el servidor.</span>';
    }
  }
}

let currentImportInspection = null;
let currentUnifiedAnalysis = null;

function renderUnifiedSummaryPanel(data) {
  const panel = document.getElementById('unified-import-summary-panel');
  const banner = document.getElementById('unified-analysis-banner');
  const prodWrap = document.getElementById('unified-products-preview-wrap');
  const prodTbody = document.getElementById('unified-products-tbody');
  const saleWrap = document.getElementById('unified-sales-preview-wrap');
  const saleTbody = document.getElementById('unified-sales-tbody');
  if (!panel || !banner) return;

  currentUnifiedAnalysis = data;
  panel.style.display = 'block';
  const prods = Array.isArray(data.products) ? data.products : [];
  const sales = Array.isArray(data.sales) ? data.sales : [];
  banner.textContent =
    data.summary_text ||
    `Análisis de tu archivo completado: Se encontraron ${prods.length} productos y ${sales.length} ventas registradas`;

  if (prodWrap && prodTbody) {
    prodTbody.innerHTML = '';
    if (prods.length) {
      prodWrap.style.display = 'block';
      prods.slice(0, 8).forEach((p) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="font-family: var(--font-mono);">${escapeHtmlText(p.sku)}</td>
          <td>${escapeHtmlText(p.name)}</td>
          <td>${escapeHtmlText(p.category)}</td>
          <td class="price-cell">${formatCOP(Number(p.cost_price || 0))}</td>
          <td class="price-cell">${formatCOP(Number(p.sale_price || 0))}</td>
          <td class="price-cell">${formatQtyValue(p.initial_stock)}</td>
        `;
        prodTbody.appendChild(tr);
      });
    } else {
      prodWrap.style.display = 'none';
    }
  }

  if (saleWrap && saleTbody) {
    saleTbody.innerHTML = '';
    if (sales.length) {
      saleWrap.style.display = 'block';
      sales.slice(0, 8).forEach((s) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="font-family: var(--font-mono);">${escapeHtmlText(s.sale_reference)}</td>
          <td>${escapeHtmlText(s.occurred_at || 'Actual')}</td>
          <td>${escapeHtmlText(s.product_name)}</td>
          <td class="price-cell">${formatQtyValue(s.quantity)}</td>
          <td class="price-cell">${formatCOP(Number(s.line_total || 0))}</td>
        `;
        saleTbody.appendChild(tr);
      });
    } else {
      saleWrap.style.display = 'none';
    }
  }
}

async function handleImportFileInspection(e, targetSheet = null) {
  const fileInput = document.getElementById('import-file');
  const mapperPanel = document.getElementById('smart-mapper-panel');
  const unifiedPanel = document.getElementById('unified-import-summary-panel');
  if (!fileInput || !fileInput.files.length) {
    if (mapperPanel) mapperPanel.style.display = 'none';
    if (unifiedPanel) unifiedPanel.style.display = 'none';
    return;
  }

  const file = fileInput.files[0];
  const type = document.getElementById('import-type').value;

  showToast('Analizando estructura de tu archivo...', 'info');

  if (type === 'unified' || type === 'products') {
    const uForm = new FormData();
    uForm.append('file', file);
    try {
      const uResp = await fetch(`${ROOT_PATH}/api/imports/unified?mode=preview`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: uForm,
      });
      if (uResp.ok) {
        const uData = await uResp.json();
        renderUnifiedSummaryPanel(uData);
      } else if (unifiedPanel) {
        unifiedPanel.style.display = 'none';
      }
    } catch (_) {
      if (unifiedPanel) unifiedPanel.style.display = 'none';
    }
  } else if (unifiedPanel) {
    unifiedPanel.style.display = 'none';
  }

  if (type !== 'products' && type !== 'unified') {
    if (mapperPanel) mapperPanel.style.display = 'none';
    return;
  }

  const formData = new FormData();
  formData.append('file', file);
  const qSheet = targetSheet ? `?sheet=${encodeURIComponent(targetSheet)}` : '';

  try {
    const resp = await fetch(`${ROOT_PATH}/api/imports/inspect${qSheet}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    if (!resp.ok) {
      const err = await resp.json();
      showToast(err.detail || 'No fue posible inspeccionar el archivo', 'error');
      if (mapperPanel) mapperPanel.style.display = 'none';
      return;
    }

    const data = await resp.json();
    currentImportInspection = data;

    if (mapperPanel) mapperPanel.style.display = 'block';

    // Badge de hoja
    const badge = document.getElementById('mapper-sheet-badge');
    if (badge) badge.textContent = data.selected_sheet || 'Hoja 1';

    // Selector de hoja si hay más de una
    const sheetGroup = document.getElementById('sheet-selector-group');
    const sheetSelect = document.getElementById('import-sheet-select');
    if (data.sheets && data.sheets.length > 1 && sheetGroup && sheetSelect) {
      sheetGroup.style.display = 'block';
      sheetSelect.innerHTML = '';
      data.sheets.forEach((sName) => {
        const opt = document.createElement('option');
        opt.value = sName;
        opt.textContent = sName;
        if (sName === data.selected_sheet) opt.selected = true;
        sheetSelect.appendChild(opt);
      });
    } else if (sheetGroup) {
      sheetGroup.style.display = 'none';
    }

    // Llenar los selects de mapeo
    const columns = data.columns || [];
    const suggested = data.suggested_mapping || {};

    const mappingFields = ['sku', 'name', 'category', 'cost_price', 'sale_price', 'initial_stock', 'unit', 'min_stock', 'vat_rate'];
    mappingFields.forEach((f) => {
      const sel = document.getElementById(`map-col-${f}`);
      if (!sel) return;
      sel.innerHTML = '<option value="">(Omitir / No aplica)</option>';
      columns.forEach((c) => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        if (suggested[f] === c) {
          opt.selected = true;
        }
        sel.appendChild(opt);
      });
    });

    // Renderizar previsualización
    renderMapperPreviewTable(data.sample_rows || [], columns);

    showToast(`Análisis completado (encabezados en fila ${data.header_row_index})`, 'success');
  } catch (err) {
    showToast('Error al inspeccionar columnas del archivo', 'error');
  }
}

function renderMapperPreviewTable(sampleRows, columns) {
  const thead = document.getElementById('mapper-preview-thead');
  const tbody = document.getElementById('mapper-preview-tbody');
  if (!thead || !tbody) return;

  thead.innerHTML = '';
  tbody.innerHTML = '';

  if (!sampleRows.length) {
    tbody.innerHTML = '<tr><td style="color: var(--ink-muted); text-align: center; padding: 12px;">Sin filas de datos para mostrar</td></tr>';
    return;
  }

  const trHead = document.createElement('tr');
  columns.forEach((col) => {
    const th = document.createElement('th');
    th.textContent = col;
    trHead.appendChild(th);
  });
  thead.appendChild(trHead);

  sampleRows.forEach((row) => {
    const tr = document.createElement('tr');
    columns.forEach((col) => {
      const td = document.createElement('td');
      td.textContent = row[col] || '-';
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

async function handleProductSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-submit-product');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Guardando...';
  }

  const payload = {
    sku: document.getElementById('prod-sku').value,
    name: document.getElementById('prod-name').value,
    category: document.getElementById('prod-category').value,
    unit: document.getElementById('prod-unit').value,
    cost_price: document.getElementById('prod-cost').value,
    sale_price: document.getElementById('prod-price').value,
    vat_rate: document.getElementById('prod-vat-rate').value,
    initial_stock: document.getElementById('prod-initial-stock').value,
    min_stock: document.getElementById('prod-min-stock').value,
    image_url: document.getElementById('prod-image-url')?.value || null,
    is_training_data: Boolean(window.__SPOTLIGHT_TRAINING_ACTIVE__),
  };

  try {
    const resp = await fetch(`${ROOT_PATH}/api/products`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    if (resp.ok) {
      showToast('Producto agregado al catálogo exitosamente', 'success');
      closeDrawer('drawer-product');
      setTimeout(() => location.reload(), 700);
    } else {
      const err = await resp.json();
      showToast(err.detail || 'Error al crear el producto', 'error');
    }
  } catch (err) {
    showToast('Error de conexión con el servidor', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Guardar Producto';
    }
  }
}

async function handleImportSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-submit-import');
  const fileInput = document.getElementById('import-file');
  const type = document.getElementById('import-type').value;
  const mode = document.getElementById('import-mode').value;
  if (!fileInput.files.length) {
    showToast('Seleccione un archivo para importar', 'error');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Procesando archivo...';
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  if (type === 'products' && currentImportInspection) {
    const mapping = {
      sku: document.getElementById('map-col-sku')?.value || '',
      name: document.getElementById('map-col-name')?.value || '',
      category: document.getElementById('map-col-category')?.value || '',
      cost_price: document.getElementById('map-col-cost_price')?.value || '',
      sale_price: document.getElementById('map-col-sale_price')?.value || '',
      initial_stock: document.getElementById('map-col-initial_stock')?.value || '',
      unit: document.getElementById('map-col-unit')?.value || '',
      min_stock: document.getElementById('map-col-min_stock')?.value || '',
      vat_rate: document.getElementById('map-col-vat_rate')?.value || '',
    };
    formData.append('mapping', JSON.stringify(mapping));
    const sheetSel = document.getElementById('import-sheet-select');
    if (sheetSel && sheetSel.value) {
      formData.append('sheet_name', sheetSel.value);
    }
    formData.append('header_row', currentImportInspection.header_row_index || 1);
  }

  const endpoint =
    type === 'unified'
      ? `/api/imports/unified?mode=${mode}`
      : type === 'products'
      ? `/api/imports/products?mode=${mode}`
      : type === 'historical_sales'
      ? `/api/imports/historical-sales?mode=${mode}`
      : `/api/imports/sales?mode=${mode}`;

  try {
    const resp = await fetch(`${ROOT_PATH}${endpoint}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    const data = await resp.json();
    const resDiv = document.getElementById('import-results');
    const detail = data.detail;
    const errorMessage = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((item) => item.msg || 'Dato inválido').join('; ')
      : 'Error en validación del archivo';
    if (resDiv) {
      resDiv.style.display = 'block';
      if (resp.ok && type === 'unified') {
        renderUnifiedSummaryPanel(data);
        resDiv.textContent =
          mode === 'preview'
            ? data.summary_text
            : `Guardado en tu cuenta: ${data.products_created} productos nuevos y ${data.sales_created} ventas registradas.`;
      } else {
        resDiv.textContent = resp.ok
          ? `Resultado: ${data.rows_ok} filas válidas, ${data.rows_rejected} rechazadas. ${mode === 'preview' ? 'Revisión sin guardar productos ni ventas.' : 'Importación guardada.'}`
          : errorMessage;
      }
      if (resp.ok && Array.isArray(data.errors)) {
        data.errors.forEach((item) => {
          const line = document.createElement('div');
          line.textContent = `Fila ${item.row}: ${item.message}`;
          resDiv.appendChild(line);
        });
      }
    }
    if (resp.ok) {
      showToast(mode === 'preview' ? 'Revisión completada sin guardar' : 'Importación completada', data.rows_rejected ? 'error' : 'success');
      if (mode === 'commit') {
        setTimeout(() => location.reload(), 900);
      }
    } else {
      showToast(errorMessage, 'error');
    }
  } catch (err) {
    showToast('Error de conexión al importar', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Confirmar y Guardar Todo en Mi Cuenta';
    }
  }
}

async function voidSale(saleId) {
  if (!confirm('¿Confirma la anulación? Una venta operativa devuelve stock; una venta histórica no modifica existencias.')) return;
  try {
    const resp = await fetch(`${ROOT_PATH}/api/sales/${saleId}/void`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (resp.ok) {
      showToast('Venta anulada. Existencias conservadas según el tipo de venta.', 'success');
      setTimeout(() => location.reload(), 600);
    } else {
      const err = await resp.json();
      showToast(err.detail || 'Error al anular venta', 'error');
    }
  } catch (err) {
    showToast('Error de conexión', 'error');
  }
}
window.voidSale = voidSale;

// --- EDICIÓN DE PRODUCTOS EN CATÁLOGO Y KARDEX (F-DC-124) ---
function calculateEditProductMargin() {
  const cost = parseFloat(document.getElementById('edit-prod-cost')?.value) || 0;
  const price = parseFloat(document.getElementById('edit-prod-price')?.value) || 0;
  const profit = price - cost;
  const marginPct = price > 0 ? (profit / price) * 100 : 0;

  const profitEl = document.getElementById('edit-profit-display');
  const marginEl = document.getElementById('edit-margin-pct-display');
  const boxEl = document.getElementById('edit-margin-live-box');

  if (profitEl) profitEl.textContent = `Ganancia: ${formatCOP(profit)} COP`;
  if (marginEl) marginEl.textContent = `${marginPct.toFixed(1)} %`;

  if (boxEl) {
    if (profit < 0) {
      boxEl.style.background = '#FEF2F2';
      boxEl.style.borderColor = '#FECACA';
      if (profitEl) profitEl.style.color = '#B91C1C';
      if (marginEl) marginEl.style.color = '#B91C1C';
    } else {
      boxEl.style.background = '#F0FDF4';
      boxEl.style.borderColor = '#BBF7D0';
      if (profitEl) profitEl.style.color = '#15803D';
      if (marginEl) marginEl.style.color = '#15803D';
    }
  }
}
window.calculateEditProductMargin = calculateEditProductMargin;

function openEditProductDrawer(productId) {
  const prod = (dashboardData.products || []).find((p) => p.id === productId);
  if (!prod) {
    showToast('Producto no encontrado en catálogo', 'error');
    return;
  }

  document.getElementById('edit-prod-id').value = prod.id;
  document.getElementById('edit-prod-sku').value = prod.sku || '';
  document.getElementById('edit-prod-name').value = prod.name || '';
  document.getElementById('edit-prod-category').value = prod.category || 'General';
  document.getElementById('edit-prod-unit').value = prod.unit || 'und';
  document.getElementById('edit-prod-cost').value = parseFloat(prod.cost_price) || 0;
  document.getElementById('edit-prod-price').value = parseFloat(prod.sale_price) || 0;
  const vatEl = document.getElementById('edit-prod-vat-rate');
  if (vatEl) {
    const normVat = String(Math.round(Number(prod.vat_rate) || 0));
    vatEl.value = ['0', '5', '19'].includes(normVat) ? normVat : '0';
  }
  document.getElementById('edit-prod-stock-display').value = `${prod.stock_qty || 0} ${prod.unit || 'und'}`;
  document.getElementById('edit-prod-min-stock').value = parseFloat(prod.min_stock) || 0;
  document.getElementById('edit-prod-image-url').value = prod.image_url || '';

  const fileInput = document.getElementById('edit-prod-image-file');
  if (fileInput) fileInput.value = '';
  const statusEl = document.getElementById('edit-prod-img-upload-status');
  if (statusEl) statusEl.textContent = prod.image_url ? 'Foto actual cargada. Selecciona otra para cambiarla.' : 'Sin imagen cargada.';

  const previewBox = document.getElementById('edit-prod-img-preview-box');
  if (previewBox) {
    if (prod.image_url) {
      previewBox.innerHTML = `<img src="${escapeHtmlText(ROOT_PATH+prod.image_url)}" alt="${escapeHtmlText(prod.name)}" style="width: 100%; height: 100%; object-fit: cover; border-radius: var(--radius-control);">`;
    } else {
      previewBox.innerHTML = `<i data-lucide="image" style="width: 22px; height: 22px; color: var(--ink-muted);"></i>`;
      if (window.lucide) lucide.createIcons();
    }
  }

  const toggle = document.getElementById('edit-stock-toggle');
  if (toggle) toggle.checked = false;
  const adjFields = document.getElementById('edit-stock-adjustment-fields');
  if (adjFields) adjFields.style.display = 'none';
  const adjQty = document.getElementById('edit-adj-qty');
  if (adjQty) adjQty.value = '';
  const adjReason = document.getElementById('edit-adj-reason');
  if (adjReason) adjReason.value = '';

  calculateEditProductMargin();
  openDrawer('drawer-edit-product');
}
window.openEditProductDrawer = openEditProductDrawer;

async function handleEditProductImageSelection(e) {
  const file = e.target.files[0];
  if (!file) return;

  const statusEl = document.getElementById('edit-prod-img-upload-status');
  const previewBox = document.getElementById('edit-prod-img-preview-box');
  const urlHidden = document.getElementById('edit-prod-image-url');

  if (statusEl) statusEl.textContent = 'Subiendo imagen...';

  const formData = new FormData();
  formData.append('file', file);

  try {
    const resp = await fetch(`${ROOT_PATH}/api/products/upload-image`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    if (resp.ok) {
      const data = await resp.json();
      if (urlHidden) urlHidden.value = data.image_url;
      if (previewBox) {
        previewBox.innerHTML = `<img src="${ROOT_PATH}${data.image_url}" alt="Preview" style="width: 100%; height: 100%; object-fit: cover; border-radius: var(--radius-control);">`;
      }
      if (statusEl) statusEl.textContent = 'Foto subida correctamente.';
      showToast('Foto cargada exitosamente', 'success');
    } else {
      const err = await resp.json();
      if (statusEl) statusEl.textContent = 'Error al subir la imagen.';
      showToast(err.detail || 'Error al subir la imagen', 'error');
    }
  } catch (err) {
    if (statusEl) statusEl.textContent = 'Error de conexión.';
    showToast('Error de conexión al subir la imagen', 'error');
  }
}

async function handleEditProductSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-submit-edit-product');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Guardando...';
  }

  const prodId = document.getElementById('edit-prod-id').value;
  const payload = {
    sku: document.getElementById('edit-prod-sku').value,
    name: document.getElementById('edit-prod-name').value,
    category: document.getElementById('edit-prod-category').value,
    unit: document.getElementById('edit-prod-unit').value,
    cost_price: document.getElementById('edit-prod-cost').value,
    sale_price: document.getElementById('edit-prod-price').value,
    vat_rate: document.getElementById('edit-prod-vat-rate').value,
    min_stock: document.getElementById('edit-prod-min-stock').value,
    image_url: document.getElementById('edit-prod-image-url')?.value || null,
  };

  try {
    const resp = await fetch(`${ROOT_PATH}/api/products/${prodId}`, {
      method: 'PUT',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const err = await resp.json();
      showToast(err.detail || 'Error al actualizar el producto', 'error');
      return;
    }

    const updatedProd = await resp.json();

    const adjustToggle = document.getElementById('edit-stock-toggle');
    const adjQtyVal = parseFloat(document.getElementById('edit-adj-qty')?.value);
    if (adjustToggle && adjustToggle.checked && adjQtyVal > 0) {
      const adjType = document.getElementById('edit-adj-type').value;
      const adjReason = document.getElementById('edit-adj-reason')?.value || 'Ajuste manual desde edición de producto';
      const movPayload = {
        product_id: prodId,
        movement_type: adjType,
        quantity: adjQtyVal,
        unit_cost: payload.cost_price,
        reason: adjReason,
      };
      const movementResponse = await fetch(`${ROOT_PATH}/api/inventory/movements`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(movPayload),
      });
      if (!movementResponse.ok) {
        const error = await movementResponse.json();
        showToast(`Datos del producto guardados. Ajuste de inventario NO aplicado: ${error.detail || 'Revise la cantidad y vuelva a intentar.'}`, 'error');
        return;
      }
    }

    showToast('Producto actualizado exitosamente', 'success');
    closeDrawer('drawer-edit-product');
    setTimeout(() => location.reload(), 700);
  } catch (err) {
    showToast('Error de conexión con el servidor', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Guardar Cambios';
    }
  }
}

// --- DETALLE Y COMPROBANTE DE VENTA (F-DC-124) ---
function formatDateEs(dateStr) {
  if (!dateStr) return '-';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const month = months[d.getMonth()];
    let hour = d.getHours();
    const minute = String(d.getMinutes()).padStart(2, '0');
    const ampm = hour < 12 ? 'a. m.' : 'p. m.';
    hour = hour % 12 || 12;
    return `${d.getDate()} ${month} ${d.getFullYear()} · ${hour}:${minute} ${ampm}`;
  } catch (e) {
    return dateStr;
  }
}

function formatPaymentLabel(method) {
  const map = {
    cash: 'Efectivo',
    card: 'Tarjeta Débito / Crédito',
    transfer: 'Transferencia Bancaria',
    credit: 'Crédito Comercial',
    other: 'Otro',
  };
  return map[method] || method || 'Efectivo';
}

async function openSaleDetailDrawer(saleId) {
  let sale = (dashboardData.recent_sales || []).find((s) => s.id === saleId);
  if (!sale || !sale.items) {
    try {
      const resp = await fetch(`${ROOT_PATH}/api/sales/${saleId}`, {
        headers: getAuthHeaders(),
      });
      if (resp.ok) {
        sale = await resp.json();
      }
    } catch (e) {
      console.error('Error fetching sale detail:', e);
    }
  }

  if (!sale) {
    showToast('No se encontró el detalle de la venta solicitada', 'error');
    return;
  }

  const numEl = document.getElementById('sale-detail-number');
  if (numEl) numEl.textContent = `#${sale.sale_number}`;

  const dateEl = document.getElementById('sale-detail-date');
  if (dateEl) dateEl.textContent = formatDateEs(sale.occurred_at);

  const custEl = document.getElementById('sale-detail-customer');
  if (custEl) custEl.textContent = sale.customer_label || 'Cliente Mostrador';

  const payEl = document.getElementById('sale-detail-payment');
  if (payEl) payEl.textContent = formatPaymentLabel(sale.payment_method);

  const badgeEl = document.getElementById('sale-detail-status-badge');
  if (badgeEl) {
    if (sale.status === 'voided') {
      badgeEl.className = 'badge-danger';
      badgeEl.textContent = 'Anulada';
    } else {
      badgeEl.className = 'badge-success';
      badgeEl.textContent = 'Confirmada';
    }
  }

  const itemsCountEl = document.getElementById('sale-detail-items-count');
  if (itemsCountEl) itemsCountEl.textContent = (sale.items || []).length;

  const tbody = document.getElementById('sale-detail-items-tbody');
  if (tbody) {
    tbody.innerHTML = '';
    (sale.items || []).forEach((item) => {
      const prod = (dashboardData.products || []).find((p) => p.id === item.product_id);
      const prodName = escapeHtmlText(item.product_name || (prod ? prod.name : 'Producto'));
      const prodSku = escapeHtmlText(item.product_sku || (prod ? prod.sku : '-'));
      const prodUnit = escapeHtmlText(item.product_unit || (prod ? prod.unit : 'und'));
      const imgUrl = item.product_image_url || (prod ? prod.image_url : null);

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>
          <div style="display: flex; align-items: center; gap: 10px;">
            ${
              imgUrl
                ? `<img src="${escapeHtmlText(ROOT_PATH+imgUrl)}" alt="${prodName}" class="product-avatar-img" style="width: 30px; height: 30px; border-radius: 6px; object-fit: cover;">`
                : `<div class="product-avatar-fallback" style="width: 30px; height: 30px; font-size: 11px; border-radius: 6px;" aria-hidden="true">${prodName.substring(0, 2).toUpperCase()}</div>`
            }
            <div>
              <div style="font-weight: 600; color: var(--ink-primary); line-height: 1.2;">${prodName}</div>
              <div style="font-size: 11px; color: var(--ink-muted); font-family: var(--font-mono);">${prodSku}</div>
            </div>
          </div>
        </td>
        <td style="text-align: center; font-weight: 600;">${item.quantity} ${prodUnit}</td>
        <td class="price-cell" style="text-align: right;">${formatCOP(item.unit_price)}</td>
        <td class="price-cell" style="text-align: right; color: var(--ink-muted);">${formatCOP(item.unit_cost_snapshot)}</td>
        <td class="price-cell" style="text-align: right; font-weight: 600;">${formatCOP(item.line_total)}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  const subtotalNum = parseFloat(sale.subtotal) || 0;
  const taxStatusEl = document.getElementById('sale-detail-tax-status');
  if (taxStatusEl) taxStatusEl.textContent = 'Condición al registrar: ' +
    ({responsible:'Responsable de IVA', not_responsible:'No responsable de IVA',
      historical:'Histórico importado: tarifa efectiva de origen',
      legacy:'Venta anterior a la configuración por empresa'}[sale.tax_status] || 'Sin registro histórico');
  const vatNum = parseFloat(sale.vat_total) || 0;
  const discountNum = parseFloat(sale.discount_total) || 0;
  const totalNum = parseFloat(sale.total) || 0;
  const cogsNum = parseFloat(sale.cogs_total) || 0;

  const subtotalEl = document.getElementById('sale-detail-subtotal');
  if (subtotalEl) subtotalEl.textContent = `${formatCOP(subtotalNum)} COP`;

  const discRow = document.getElementById('sale-detail-discount-row');
  const discEl = document.getElementById('sale-detail-discount');
  if (discRow && discEl) {
    if (discountNum > 0) {
      discRow.style.display = 'flex';
      discEl.textContent = `-${formatCOP(discountNum)} COP`;
    } else {
      discRow.style.display = 'none';
    }
  }

  const vatEl = document.getElementById('sale-detail-vat');
  if (vatEl) vatEl.textContent = `${formatCOP(vatNum)} COP`;

  const totalEl = document.getElementById('sale-detail-total');
  if (totalEl) totalEl.textContent = `${formatCOP(totalNum)} COP`;

  const netRevenue = subtotalNum - discountNum;
  const profitNum = netRevenue - cogsNum;
  const marginPct = netRevenue > 0 ? (profitNum / netRevenue) * 100 : 0;

  const profitEl = document.getElementById('sale-detail-profit');
  if (profitEl) profitEl.textContent = `${formatCOP(profitNum)} COP`;

  const marginEl = document.getElementById('sale-detail-margin-pct');
  if (marginEl) marginEl.textContent = `${marginPct.toFixed(1)} %`;

  const voidBtn = document.getElementById('btn-void-from-detail');
  if (voidBtn) {
    if (sale.status === 'voided') {
      voidBtn.style.display = 'none';
    } else {
      voidBtn.style.display = 'inline-flex';
      voidBtn.onclick = () => {
        closeDrawer('drawer-sale-detail');
        voidSale(sale.id);
      };
    }
  }

  openDrawer('drawer-sale-detail');
}
window.openSaleDetailDrawer = openSaleDetailDrawer;

async function handleCompanyTaxChange(event) {
  event.preventDefault();
  const button = document.getElementById('company-tax-save');
  const result = document.getElementById('company-tax-result');
  button.disabled = true;
  try {
    const response = await fetch(`${ROOT_PATH}/api/company/tax`, {
      method: 'PUT', headers: getAuthHeaders({'Content-Type':'application/json'}),
      body: JSON.stringify({status:document.getElementById('company-tax-status').value,
        reason:document.getElementById('company-tax-reason').value,
        expected_revision:dashboardData.company_tax.revision}),
    });
    const data = await response.json();
    if (!response.ok) {
      result.textContent = typeof data.detail === 'string' ? data.detail : 'Revisa la condición y el motivo del cambio.';
      return;
    }
    result.textContent = 'Condición guardada. Se actualizarán los totales de las operaciones nuevas.';
    location.reload();
  } catch (error) {
    result.textContent = 'No se pudo confirmar el cambio. Recarga para verificar el estado antes de reintentar.';
  } finally { button.disabled = false; }
}
async function submitDeletionRequest(event) {
  event.preventDefault();
  const reason = document.getElementById('deletion-reason').value.trim();
  const status = document.getElementById('deletion-status');
  const button = document.getElementById('btn-request-deletion');
  if (reason.length < 5) { status.textContent = 'Describa el motivo (mínimo 5 caracteres).'; return; }
  if (!confirm('Esta solicitud suspende el acceso de su empresa. ¿Desea registrarla?')) return;
  button.disabled = true;
  try {
    const response = await fetch(`${ROOT_PATH}/api/me/deletion-request`, {
      method: 'POST', headers: getAuthHeaders({'Content-Type':'application/json'}),
      body: JSON.stringify({reason}),
    });
    const result = await response.json();
    if (!response.ok) { status.textContent = result.detail || 'No se pudo registrar la solicitud.'; return; }
    status.textContent = result.message;
    window.location.assign(`${ROOT_PATH}/login`);
  } catch (_) { status.textContent = 'No se pudo confirmar la solicitud. Recargue antes de volver a intentarlo.'; }
  finally { button.disabled = false; }
}
