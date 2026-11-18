/**
 * Tour Interactivo "Spotlight" con Modo Entrenamiento Autolimpiable (is_training_data).
 * Sincroniza sub-pasos con Slide-Over Drawers y evita cierre accidental.
 * Vanilla JS 100% compatible con CSP.
 */
(function () {
  const STATE_KEY = 'dp_spotlight_state_v1';

  const STEPS = [
    {
      stepLabel: 'Paso 1 de 5',
      selector: '#weekly-action-plan',
      openDrawer: null,
      title: 'Tu Plan de Acción Comercial',
      desc: 'Aquí verás cada semana qué productos están por agotarse, cuánto efectivo puedes liberar de productos estancados y el avance hacia tu meta mensual.',
    },
    {
      stepLabel: 'Paso 2.1 de 5 · Nuevo Producto',
      selector: '#prod-code-name-row, #prod-sku',
      openDrawer: 'drawer-product',
      prefillProduct: true,
      title: 'Código y Nombre del Producto',
      desc: 'Abrimos el panel de "+ Nuevo Producto" y cargamos un producto de ejemplo listo para probar ("PRUEBA-01 · Producto de Entrenamiento").',
    },
    {
      stepLabel: 'Paso 2.2 de 5 · Nuevo Producto',
      selector: '#prod-pricing-row, #prod-cost',
      openDrawer: 'drawer-product',
      prefillProduct: true,
      title: 'Costo de Compra y Precio de Venta',
      desc: 'Con el costo de compra unitario y el precio de venta al público, el sistema calcula automáticamente tu ganancia real e IVA en cada venta.',
    },
    {
      stepLabel: 'Paso 2.3 de 5 · Nuevo Producto',
      selector: '#prod-stock-row, #prod-initial-stock',
      secondarySelector: '#btn-submit-product',
      openDrawer: 'drawer-product',
      prefillProduct: true,
      title: 'Stock Inicial, Mínimo y Guardar',
      desc: 'Define con cuántas unidades inicias, el mínimo para recibir alertas y pulsa "Guardar Producto" (o continúa con Siguiente).',
    },
    {
      stepLabel: 'Paso 3.1 de 5 · Registrar Venta',
      selector: '#sale-cart-items',
      fallbackSelector: '#drawer-sale .drawer-body',
      openDrawer: 'drawer-sale',
      title: 'Selección de Producto y Cantidad',
      desc: 'En "+ Registrar Venta" eliges el producto del carrito y la cantidad vendida (unidades o peso). Esta práctica no afecta tus indicadores reales.',
    },
    {
      stepLabel: 'Paso 3.2 de 5 · Registrar Venta',
      selector: '#btn-submit-sale',
      openDrawer: 'drawer-sale',
      title: 'Confirmar Venta',
      desc: 'Revisa el total a cobrar y pulsa "Confirmar Venta" para descontar el inventario automáticamente y generar el comprobante.',
    },
    {
      stepLabel: 'Paso 4 de 5 · Importar Excel',
      selector: '[data-open-drawer="drawer-import"]',
      openDrawer: null,
      title: 'Carga rápida desde Excel y Ranking',
      desc: 'Cuando tengas tu catálogo o ventas en Excel o CSV, usa "Importar Excel" para detectarlos automáticamente en un solo paso.',
    },
    {
      stepLabel: 'Paso 5 de 5',
      selector: null,
      openDrawer: null,
      title: 'Entrenamiento completado',
      desc: 'Ya conoces cómo registrar productos, facturar ventas e interpretar tu rentabilidad. ¿Cómo deseas dejar tu cuenta para empezar?',
      isFinalModal: true,
    },
  ];

  let currentStepIdx = 0;
  let layerEl = null;

  function readState() {
    try {
      const raw = sessionStorage.getItem(STATE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function saveState(state) {
    try {
      sessionStorage.setItem(STATE_KEY, JSON.stringify(state));
    } catch (_) {}
  }

  function clearState() {
    window.__SPOTLIGHT_TRAINING_ACTIVE__ = false;
    try {
      sessionStorage.removeItem(STATE_KEY);
    } catch (_) {}
  }

  function syncDrawersForStep(step) {
    const allDrawers = document.querySelectorAll('.drawer-backdrop.open');
    allDrawers.forEach((d) => {
      if (!step.openDrawer || d.id !== step.openDrawer) {
        if (typeof window.closeDrawer === 'function') {
          window.closeDrawer(d.id);
        } else if (d.classList) {
          d.classList.remove('open');
        }
      }
    });

    if (step.openDrawer) {
      const targetDrawer = document.getElementById(step.openDrawer);
      if (targetDrawer && targetDrawer.classList && !targetDrawer.classList.contains('open')) {
        if (typeof window.openDrawer === 'function') {
          window.openDrawer(step.openDrawer);
        } else {
          targetDrawer.classList.add('open');
        }
      }
      if (step.prefillProduct) {
        prefillPracticeProduct();
      }
      if (step.openDrawer === 'drawer-sale') {
        ensureSaleCartVisible();
      }
    }
  }

  function prefillPracticeProduct() {
    const sku = document.getElementById('prod-sku');
    const name = document.getElementById('prod-name');
    const cost = document.getElementById('prod-cost');
    const price = document.getElementById('prod-price');
    const stock = document.getElementById('prod-initial-stock');
    const minStock = document.getElementById('prod-min-stock');
    if (sku && !sku.value) sku.value = 'PRUEBA-01';
    if (name && !name.value) name.value = 'Producto de Entrenamiento';
    if (cost && !cost.value) cost.value = '10000';
    if (price && !price.value) price.value = '18000';
    if (stock && !stock.value) stock.value = '10';
    if (minStock && !minStock.value) minStock.value = '2';
  }

  function ensureSaleCartVisible() {
    const cart = document.getElementById('sale-cart-items');
    if (!cart || (cart.children && cart.children.length > 0)) return;
    if (typeof cart.innerHTML === 'string' && !cart.innerHTML.trim()) {
      cart.innerHTML =
        '<div id="tour-empty-cart-hint" style="padding: 12px; border-radius: 8px; background: #F8FAFC; border: 1px dashed #CBD5E1; font-size: 12px; color: #475569;">Guarda primero un producto de práctica (Paso 2) para seleccionarlo aquí en el carrito.</div>';
    }
  }

  function destroyLayer() {
    if (layerEl) {
      layerEl.remove();
      layerEl = null;
    }
    window.removeEventListener('resize', repositionActive);
    window.removeEventListener('scroll', repositionActive, true);
  }

  function findVisibleTarget(selector, fallbackSelector) {
    const tryList = [selector, fallbackSelector].filter(Boolean);
    for (const sel of tryList) {
      const candidates = document.querySelectorAll(sel);
      for (const el of candidates) {
        if (typeof el.getBoundingClientRect === 'function') {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) return el;
        }
      }
      if (candidates[0]) return candidates[0];
    }
    return null;
  }

  function computeTargetRect(step) {
    const primary = findVisibleTarget(step.selector, step.fallbackSelector);
    if (!primary || typeof primary.getBoundingClientRect !== 'function') return null;
    const r1 = primary.getBoundingClientRect();
    let left = r1.left;
    let top = r1.top;
    let right = r1.right;
    let bottom = r1.bottom;

    if (step.secondarySelector) {
      const secondary = findVisibleTarget(step.secondarySelector);
      if (secondary && typeof secondary.getBoundingClientRect === 'function') {
        const r2 = secondary.getBoundingClientRect();
        if (r2.width > 0 && r2.height > 0) {
          left = Math.min(left, r2.left);
          top = Math.min(top, r2.top);
          right = Math.max(right, r2.right);
          bottom = Math.max(bottom, r2.bottom);
        }
      }
    }

    return {
      left,
      top,
      right,
      bottom,
      width: Math.max(0, right - left),
      height: Math.max(0, bottom - top),
    };
  }

  function positionPopoverNearRect(popover, rect, step) {
    if (typeof popover.getBoundingClientRect !== 'function') return;
    const pad = 12;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const popRect = popover.getBoundingClientRect();

    // Si estamos guiando dentro de un drawer lateral derecho en escritorio, posicionar a la izquierda para no tapar los campos
    if (step && step.openDrawer && vw >= 820 && rect.left > popRect.width + 24) {
      const leftPos = Math.max(pad, rect.left - popRect.width - 20);
      const topPos = Math.min(Math.max(pad, rect.top), Math.max(pad, vh - popRect.height - pad));
      popover.style.top = `${topPos}px`;
      popover.style.left = `${leftPos}px`;
      return;
    }

    let top = rect.bottom + 12;
    if (top + popRect.height > vh - pad) {
      top = Math.max(pad, rect.top - popRect.height - 12);
    }
    const left = Math.min(Math.max(pad, rect.left), Math.max(pad, vw - popRect.width - pad));
    popover.style.top = `${top}px`;
    popover.style.left = `${left}px`;
  }

  function repositionActive() {
    if (!layerEl) return;
    const step = STEPS[currentStepIdx];
    if (!step || step.isFinalModal) return;
    const rect = computeTargetRect(step);
    const hl = layerEl.querySelector('.dp-spotlight-highlight');
    const pop = layerEl.querySelector('.dp-spotlight-popover');
    if (!rect || !hl || !pop) return;
    hl.style.top = `${Math.max(4, rect.top - 6)}px`;
    hl.style.left = `${Math.max(4, rect.left - 6)}px`;
    hl.style.width = `${rect.width + 12}px`;
    hl.style.height = `${rect.height + 12}px`;
    positionPopoverNearRect(pop, rect, step);
  }

  async function completeTour(action) {
    const headers = { 'Content-Type': 'application/json' };
    if (window.dashboardDataToken) {
      headers['Authorization'] = `Bearer ${window.dashboardDataToken}`;
    } else {
      const dataEl = document.getElementById('dashboard-data');
      if (dataEl) {
        try {
          const parsed = JSON.parse(dataEl.textContent);
          if (parsed.token) headers['Authorization'] = `Bearer ${parsed.token}`;
        } catch (_) {}
      }
    }

    const rootPath = window.__ROOT_PATH__ || (window.location.pathname.startsWith('/empresarial') ? '/empresarial' : '');
    try {
      const response = await fetch(`${rootPath}/api/onboarding/complete-tour`, {
        method: 'POST',
        headers,
        credentials: 'same-origin',
        body: JSON.stringify({ action }),
      });
      if (!response.ok) {
        const result = await response.json();
        alert(typeof result.detail === 'string' ? result.detail : 'No se pudo completar el recorrido. Se conservó la información.');
        return;
      }
    } catch (err) {
      console.error('Error al cerrar recorrido:', err);
      alert('No se pudo confirmar el cierre. No se borró la práctica; recarga antes de volver a intentarlo.');
      return;
    }
    clearState();
    destroyLayer();
    window.location.reload();
  }

  function renderStep(idx) {
    destroyLayer();
    currentStepIdx = Math.max(0, Math.min(STEPS.length - 1, idx));
    const step = STEPS[currentStepIdx];
    window.__SPOTLIGHT_TRAINING_ACTIVE__ = true;
    saveState({ active: true, step: currentStepIdx, training: true });

    syncDrawersForStep(step);

    layerEl = document.createElement('div');
    layerEl.className = 'dp-spotlight-layer';

    if (step.isFinalModal) {
      layerEl.innerHTML = `
        <div class="dp-spotlight-backdrop"></div>
        <div class="dp-spotlight-modal-card" role="dialog" aria-modal="true">
          <div class="dp-spotlight-step-tag">${step.stepLabel}</div>
          <h3 class="dp-spotlight-title">${step.title}</h3>
          <p class="dp-spotlight-desc">${step.desc}</p>
          <div style="display: flex; flex-direction: column; gap: 10px;">
            <button type="button" id="btn-tour-purge-training" class="btn btn-primary dp-spotlight-final-btn">
              Borrar datos de práctica (Dejar mi cuenta 100% en limpio)
            </button>
            <button type="button" id="btn-tour-keep-training" class="btn btn-secondary dp-spotlight-final-btn">
              Conservar estos datos como práctica
            </button>
            <button type="button" id="btn-tour-prev" class="btn btn-ghost" style="font-size: 12px;">
              Anterior
            </button>
          </div>
        </div>
      `;
      document.body.appendChild(layerEl);
      layerEl.querySelector('#btn-tour-purge-training').addEventListener('click', () => completeTour('purge_training'));
      layerEl.querySelector('#btn-tour-keep-training').addEventListener('click', () => completeTour('keep_training'));
      layerEl.querySelector('#btn-tour-prev').addEventListener('click', () => renderStep(currentStepIdx - 1));
      return;
    }

    const target = findVisibleTarget(step.selector, step.fallbackSelector);
    if (target && typeof target.scrollIntoView === 'function') {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    layerEl.innerHTML = `
      <div class="dp-spotlight-highlight"></div>
      <div class="dp-spotlight-popover" role="dialog" aria-modal="true">
        <div class="dp-spotlight-step-tag">${step.stepLabel}</div>
        <h3 class="dp-spotlight-title">${step.title}</h3>
        <p class="dp-spotlight-desc">${step.desc}</p>
        <div class="dp-spotlight-actions">
          <button type="button" id="btn-tour-skip" class="btn btn-ghost" style="font-size: 12px; padding: 6px 8px;">Omitir tutorial</button>
          <div style="display: flex; gap: 6px;">
            <button type="button" id="btn-tour-prev" class="btn btn-secondary" style="font-size: 12px; padding: 6px 12px;" ${currentStepIdx === 0 ? 'disabled' : ''}>Anterior</button>
            <button type="button" id="btn-tour-next" class="btn btn-primary" style="font-size: 12px; padding: 6px 12px;">Siguiente</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(layerEl);

    repositionActive();
    setTimeout(repositionActive, 60);
    setTimeout(repositionActive, 280);
    window.addEventListener('resize', repositionActive);
    window.addEventListener('scroll', repositionActive, true);

    layerEl.querySelector('#btn-tour-skip').addEventListener('click', () => completeTour('keep_training'));
    layerEl.querySelector('#btn-tour-prev').addEventListener('click', () => {
      if (currentStepIdx > 0) renderStep(currentStepIdx - 1);
    });
    layerEl.querySelector('#btn-tour-next').addEventListener('click', () => renderStep(currentStepIdx + 1));
  }

  document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('btn-start-spotlight-tour');
    if (startBtn) {
      startBtn.addEventListener('click', () => renderStep(0));
    }

    const saved = readState();
    if (saved && saved.active && typeof saved.step === 'number') {
      setTimeout(() => renderStep(saved.step), 250);
      return;
    }

    const dataEl = document.getElementById('dashboard-data');
    if (dataEl) {
      try {
        const dash = JSON.parse(dataEl.textContent);
        if (dash && dash.onboarding_tour_completed === false && Array.isArray(dash.products) && dash.products.length === 0) {
          setTimeout(() => renderStep(0), 400);
        }
      } catch (_) {}
    }
  });

  window.startSpotlightTour = () => renderStep(0);
})();
