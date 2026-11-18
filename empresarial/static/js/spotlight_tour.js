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
      selector: '#weekly-action-plan h3',
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
      desc: 'Abrimos el panel de "+ Nuevo Producto" y cargamos un producto de ejemplo listo para probar con un código disponible.',
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
      openDrawer: 'drawer-product',
      prefillProduct: true,
      title: 'Stock Inicial, Mínimo y Guardar',
      desc: 'Define con cuántas unidades inicias, el mínimo para recibir alertas y pulsa "Guardar Producto" (o continúa con Siguiente).',
    },
    {
      stepLabel: 'Paso 3.1 de 5 · Registrar Venta',
      selector: '#sale-cart-items .cart-item-row',
      fallbackSelector: '#sale-cart-items',
      openDrawer: 'drawer-sale',
      title: 'Selección de Producto y Cantidad',
      desc: 'En "+ Registrar Venta" eliges el producto del carrito y la cantidad vendida (unidades o peso). Esta práctica no afecta tus indicadores reales.',
    },
    {
      stepLabel: 'Paso 3.2 de 5 · Registrar Venta',
      selector: '#btn-submit-sale',
      openDrawer: 'drawer-sale',
      title: 'Confirmar Venta',
      desc: 'Revisa el total y pulsa "Confirmar Venta" para registrar una venta y descontar únicamente stock de práctica.',
    },
    {
      stepLabel: 'Paso 4 de 5 · Importar Excel',
      selector: '[data-open-drawer="drawer-import"]',
      openDrawer: null,
      title: 'Carga rápida desde Excel',
      desc: 'Cuando tengas tu catálogo o ventas en Excel o CSV, usa "Importar Excel" para detectarlos automáticamente en un solo paso.',
    },
    {
      stepLabel: 'Paso 5 de 5',
      selector: null,
      openDrawer: null,
      title: 'Entrenamiento completado',
      desc: 'Puedes conservar los productos y ventas de práctica o borrarlos. Las operaciones reales se conservan.',
      isFinalModal: true,
    },
  ];

  let currentStepIdx = 0;
  let layerEl = null;
  let completing = false;
  let tourScope;
  const usedPracticeSkus = new Set();

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
          window.openDrawer(step.openDrawer, { focus: false });
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
    if (sku && !sku.value) {
      let number = 1;
      let candidate;
      do {
        candidate = 'PRUEBA-' + String(number++).padStart(2, '0');
      } while (usedPracticeSkus.has(candidate));
      sku.value = candidate;
    }
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
        '<div id="tour-empty-cart-hint" style="padding: 12px; border-radius: 8px; background: #F8FAFC; border: 1px dashed #CBD5E1; font-size: 12px; color: #475569;">Para probar una venta, vuelve al paso 2 y guarda un producto de práctica.</div>';
    }
  }

  function destroyLayer() {
    layerEl?.remove();
    layerEl = null;
    window.removeEventListener('resize', repositionActive);
    window.removeEventListener('scroll', repositionActive, true);
    window.visualViewport?.removeEventListener('resize', repositionActive);
    window.visualViewport?.removeEventListener('scroll', repositionActive);
    document.removeEventListener('click', guardInteraction, true);
    document.removeEventListener('focusin', guardInteraction, true);
  }

  function guardInteraction(event) {
    const step = STEPS[currentStepIdx];
    const drawer = step.openDrawer && document.getElementById(step.openDrawer);
    if (layerEl.contains(event.target)) return;
    if (drawer && drawer.contains(event.target) && !event.target.closest('[data-close-drawer]')) return;

    if (event.type === 'click') {
      event.preventDefault();
      event.stopImmediatePropagation();
    } else {
      layerEl.querySelector('[role="dialog"]')?.focus({ preventScroll: true });
    }
  }

  function findVisibleTarget(step) {
    for (const selector of [step.selector, step.fallbackSelector].filter(Boolean)) {
      for (const candidate of document.querySelectorAll(selector)) {
        const { width, height } = candidate.getBoundingClientRect();
        if (width > 0 && height > 0 && getComputedStyle(candidate).visibility === 'visible') return candidate;
      }
    }
    return null;
  }

  function repositionActive(animate = false) {
    if (!layerEl || STEPS[currentStepIdx].isFinalModal) return;
    const step = STEPS[currentStepIdx];
    const highlight = layerEl.querySelector('.dp-spotlight-highlight');
    const card = layerEl.querySelector('.dp-spotlight-popover');
    if (!card || !highlight) return;

    const visual = window.visualViewport;
    const viewport = {
      left: visual?.offsetLeft ?? 0,
      top: visual?.offsetTop ?? 0,
      width: visual?.width ?? window.innerWidth,
      height: visual?.height ?? window.innerHeight,
    };
    const pad = 12;
    const right = viewport.left + viewport.width;
    const bottom = viewport.top + viewport.height;
    card.style.maxHeight = Math.max(100, Math.floor(viewport.height * 0.45)) + 'px';
    const size = card.getBoundingClientRect();
    const rect = findVisibleTarget(step)?.getBoundingClientRect();
    highlight.classList.toggle('is-moving', animate === true);
    highlight.hidden = !rect || rect.bottom <= viewport.top || rect.top >= bottom;
    let left = viewport.left + (viewport.width - size.width) / 2;
    let top = bottom - size.height - pad;

    if (!highlight.hidden) {
      const focusLeft = Math.max(viewport.left, rect.left - 6);
      const focusTop = Math.max(viewport.top, rect.top - 6);
      highlight.style.left = focusLeft + 'px';
      highlight.style.top = focusTop + 'px';
      highlight.style.width = Math.max(0, Math.min(right, rect.right + 6) - focusLeft) + 'px';
      highlight.style.height = Math.min(bottom, rect.bottom + 6) - focusTop + 'px';

      if (step.openDrawer && rect.left - size.width - pad >= viewport.left + pad) {
        left = rect.left - size.width - pad;
        top = rect.top;
      } else {
        const above = rect.top - size.height - pad;
        const below = rect.bottom + pad;
        left = rect.left;
        top = below + size.height <= bottom - pad || above < viewport.top + pad ? below : above;
      }
    }

    card.style.left = Math.max(viewport.left + pad, Math.min(left, right - size.width - pad)) + 'px';
    card.style.top = Math.max(viewport.top + pad, Math.min(top, bottom - size.height - pad)) + 'px';
    card.classList.add('is-positioned');
  }

  async function completeTour(action) {
    if (completing || window.hasPendingCommercialWrite?.()) return;
    completing = true;
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
    } finally {
      completing = false;
    }
    clearState();
    destroyLayer();
    window.location.reload();
  }

  async function renderStep(idx) {
    if (completing || window.hasPendingCommercialWrite?.()) return;
    currentStepIdx = Math.max(0, Math.min(STEPS.length - 1, idx));
    const step = STEPS[currentStepIdx];
    window.__SPOTLIGHT_TRAINING_ACTIVE__ = true;
    saveState({ active: true, step: currentStepIdx, scope: tourScope });
    if (currentStepIdx === 0) window.switchModuleSection?.('section-home', { animate: false });
    syncDrawersForStep(step);

    if (!layerEl) {
      layerEl = document.createElement('div');
      layerEl.className = 'dp-spotlight-layer';
      layerEl.innerHTML = `
        <div class="dp-spotlight-backdrop"></div>
        <div class="dp-spotlight-highlight" hidden></div>
        <div class="dp-spotlight-content"></div>
      `;
      document.body.appendChild(layerEl);
      window.addEventListener('resize', repositionActive);
      window.addEventListener('scroll', repositionActive, true);
      window.visualViewport?.addEventListener('resize', repositionActive);
      window.visualViewport?.addEventListener('scroll', repositionActive);
      document.addEventListener('click', guardInteraction, true);
      document.addEventListener('focusin', guardInteraction, true);
    }

    const content = layerEl.querySelector('.dp-spotlight-content');
    const heading = `
      <div class="dp-spotlight-step-tag">${step.stepLabel}</div>
      <h3 id="spotlight-title" class="dp-spotlight-title">${step.title}</h3>
      <p id="spotlight-description" class="dp-spotlight-desc">${step.desc}</p>
    `;
    if (step.isFinalModal) {
      layerEl.querySelector('.dp-spotlight-highlight').hidden = true;
      content.innerHTML = `
        <div class="dp-spotlight-modal-card" role="dialog" aria-modal="true"
             aria-labelledby="spotlight-title" aria-describedby="spotlight-description" tabindex="-1">
          ${heading}
          <div class="dp-spotlight-final-actions">
            <button type="button" id="btn-tour-purge-training" class="btn btn-primary dp-spotlight-final-btn">
              Borrar datos de práctica (Dejar mi cuenta 100% en limpio)
            </button>
            <button type="button" id="btn-tour-keep-training" class="btn btn-secondary dp-spotlight-final-btn">
              Conservar datos de práctica
            </button>
            <button type="button" id="btn-tour-prev" class="btn btn-ghost">Anterior</button>
          </div>
        </div>
      `;
      content.querySelector('[role="dialog"]').focus({ preventScroll: true });
      content.querySelector('#btn-tour-purge-training').addEventListener('click', () => completeTour('purge_training'));
      content.querySelector('#btn-tour-keep-training').addEventListener('click', () => completeTour('keep_training'));
      content.querySelector('#btn-tour-prev').addEventListener('click', () => renderStep(currentStepIdx - 1));
      return;
    }

    content.innerHTML = `
      <div class="dp-spotlight-popover" role="dialog" tabindex="-1"
           aria-labelledby="spotlight-title" aria-describedby="spotlight-description">
        ${heading}
        <div class="dp-spotlight-actions">
          <button type="button" id="btn-tour-skip" class="btn btn-ghost">Omitir tutorial</button>
          <div class="dp-spotlight-navigation">
            <button type="button" id="btn-tour-prev" class="btn btn-secondary" ${currentStepIdx === 0 ? 'disabled' : ''}>Anterior</button>
            <button type="button" id="btn-tour-next" class="btn btn-primary">Siguiente</button>
          </div>
        </div>
      </div>
    `;
    const card = content.querySelector('.dp-spotlight-popover');
    content.querySelector('#btn-tour-skip').addEventListener('click', () => completeTour('keep_training'));
    content.querySelector('#btn-tour-prev').addEventListener('click', () => renderStep(currentStepIdx - 1));
    content.querySelector('#btn-tour-next').addEventListener('click', () => renderStep(currentStepIdx + 1));

    if (step.openDrawer) {
      const panel = document.getElementById(step.openDrawer)?.querySelector('.drawer-panel');
      const transitions = panel?.getAnimations()
        .filter((animation) => animation.transitionProperty === 'transform') || [];
      if (transitions.length) await Promise.allSettled(transitions.map((animation) => animation.finished));
    }
    if (!card.isConnected) return;
    findVisibleTarget(step)?.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'nearest' });
    repositionActive(true);
    card.focus({ preventScroll: true });
  }

  document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('btn-start-spotlight-tour');
    if (startBtn) {
      startBtn.addEventListener('click', () => renderStep(0));
    }

    const dataEl = document.getElementById('dashboard-data');
    if (!dataEl) return;
    try {
      const dash = JSON.parse(dataEl.textContent);
      tourScope = dash.tour_scope;
      for (const sku of dash.practice_skus || []) usedPracticeSkus.add(sku.toUpperCase());
      const saved = readState();
      if (tourScope && saved?.scope === tourScope && saved.active && Number.isInteger(saved.step)) {
        renderStep(saved.step);
      } else if (dash.initial_section !== 'section-sales' && dash.onboarding_tour_completed === false && dash.products?.length === 0) {
        renderStep(0);
      }
    } catch (error) {
      console.error('No se pudo iniciar el recorrido:', error);
    }
  });

  window.startSpotlightTour = () => renderStep(0);
  window.advanceSpotlightTour = (drawerId, usedSku) => {
    if (usedSku) usedPracticeSkus.add(usedSku.toUpperCase());
    if (STEPS[currentStepIdx].openDrawer === drawerId) {
      const next = STEPS.findIndex((step, index) => index > currentStepIdx && step.openDrawer !== drawerId);
      if (next !== -1) renderStep(next);
    }
  };
})();
