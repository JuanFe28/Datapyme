/**
 * Tour Interactivo "Spotlight" con Modo Entrenamiento Autolimpiable (is_training_data).
 * Vanilla JS 100% compatible con CSP.
 */
(function () {
  const STATE_KEY = 'dp_spotlight_state_v1';

  const STEPS = [
    {
      selector: '#weekly-action-plan',
      title: 'Tu Plan de Acción Comercial',
      desc: 'Aquí verás cada semana qué productos están por agotarse, cuánto efectivo puedes liberar de productos estancados y el avance hacia tu meta mensual.',
    },
    {
      selector: '[data-open-drawer="drawer-product"]',
      title: 'Práctica 1 · Crea tu primer producto',
      desc: 'Haz clic en "+ Nuevo Producto" para agregar un producto de prueba (marcado automáticamente como entrenamiento para poder borrarlo al finalizar).',
      actionLabel: 'Abrir formulario de producto',
      practiceType: 'product',
    },
    {
      selector: '[data-open-drawer="drawer-sale"]',
      title: 'Práctica 2 · Registra tu primera venta',
      desc: 'Ahora haz clic en "+ Registrar Venta" para vender 1 unidad de prueba y ver cómo cobran vida tus KPIs, gráficas y márgenes en vivo.',
      actionLabel: 'Abrir caja de venta',
      practiceType: 'sale',
    },
    {
      selector: '[data-open-drawer="drawer-import"]',
      title: 'Carga rápida desde Excel y Ranking',
      desc: 'Cuando tengas tu catálogo en Excel o CSV, usa "Importar Excel" para cargar cientos de productos en segundos, o revisa en tablas qué se vende más.',
    },
    {
      selector: null,
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

  function destroyLayer() {
    if (layerEl) {
      layerEl.remove();
      layerEl = null;
    }
    window.removeEventListener('resize', repositionActive);
    window.removeEventListener('scroll', repositionActive, true);
  }

  function findVisibleTarget(selector) {
    if (!selector) return null;
    const candidates = document.querySelectorAll(selector);
    for (const el of candidates) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) return el;
    }
    return candidates[0] || null;
  }

  function positionPopoverNearRect(popover, rect) {
    const pad = 12;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const popRect = popover.getBoundingClientRect();

    let top = rect.bottom + 12;
    if (top + popRect.height > vh - pad) {
      top = Math.max(pad, rect.top - popRect.height - 12);
    }
    let left = Math.min(Math.max(pad, rect.left), Math.max(pad, vw - popRect.width - pad));
    popover.style.top = `${top}px`;
    popover.style.left = `${left}px`;
  }

  function repositionActive() {
    if (!layerEl) return;
    const step = STEPS[currentStepIdx];
    if (!step || step.isFinalModal) return;
    const target = findVisibleTarget(step.selector);
    const hl = layerEl.querySelector('.dp-spotlight-highlight');
    const pop = layerEl.querySelector('.dp-spotlight-popover');
    if (!target || !hl || !pop) return;
    const rect = target.getBoundingClientRect();
    hl.style.top = `${Math.max(4, rect.top - 6)}px`;
    hl.style.left = `${Math.max(4, rect.left - 6)}px`;
    hl.style.width = `${rect.width + 12}px`;
    hl.style.height = `${rect.height + 12}px`;
    positionPopoverNearRect(pop, rect);
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
      await fetch(`${rootPath}/api/onboarding/complete-tour`, {
        method: 'POST',
        headers,
        credentials: 'same-origin',
        body: JSON.stringify({ action }),
      });
    } catch (err) {
      console.error('Error al cerrar recorrido:', err);
    }
    clearState();
    destroyLayer();
    window.location.reload();
  }

  function triggerPractice(practiceType) {
    window.__SPOTLIGHT_TRAINING_ACTIVE__ = true;
    if (practiceType === 'product') {
      saveState({ active: true, step: 2, training: true });
      destroyLayer();
      if (typeof window.openDrawer === 'function') window.openDrawer('drawer-product');
      const sku = document.getElementById('prod-sku');
      const name = document.getElementById('prod-name');
      const cost = document.getElementById('prod-cost');
      const price = document.getElementById('prod-price');
      const stock = document.getElementById('prod-initial-stock');
      if (sku && !sku.value) sku.value = 'PRUEBA-01';
      if (name && !name.value) name.value = 'Producto de Entrenamiento';
      if (cost && !cost.value) cost.value = '10000';
      if (price && !price.value) price.value = '18000';
      if (stock && !stock.value) stock.value = '10';
    } else if (practiceType === 'sale') {
      saveState({ active: true, step: 3, training: true });
      destroyLayer();
      if (typeof window.openDrawer === 'function') window.openDrawer('drawer-sale');
    }
  }

  function renderStep(idx) {
    destroyLayer();
    currentStepIdx = Math.max(0, Math.min(STEPS.length - 1, idx));
    const step = STEPS[currentStepIdx];
    window.__SPOTLIGHT_TRAINING_ACTIVE__ = true;
    saveState({ active: true, step: currentStepIdx, training: true });

    layerEl = document.createElement('div');
    layerEl.className = 'dp-spotlight-layer';

    if (step.isFinalModal) {
      layerEl.innerHTML = `
        <div class="dp-spotlight-backdrop"></div>
        <div class="dp-spotlight-modal-card" role="dialog" aria-modal="true">
          <div class="dp-spotlight-step-tag">Paso ${currentStepIdx + 1} de ${STEPS.length}</div>
          <h3 class="dp-spotlight-title">${step.title}</h3>
          <p class="dp-spotlight-desc">${step.desc}</p>
          <div style="display: flex; flex-direction: column; gap: 10px;">
            <button type="button" id="btn-tour-purge-training" class="btn btn-primary" style="width: 100%; min-height: 44px;">
              Borrar producto y venta de prueba (Empezar mi cuenta 100% en limpio)
            </button>
            <button type="button" id="btn-tour-keep-training" class="btn btn-secondary" style="width: 100%; min-height: 44px;">
              Conservar estos datos en mi cuenta
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

    const target = findVisibleTarget(step.selector);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    const practiceHtml = step.practiceType
      ? `<button type="button" id="btn-tour-practice" class="btn btn-secondary" style="font-size: 12px; width: 100%; margin-bottom: 10px;">${step.actionLabel}</button>`
      : '';

    layerEl.innerHTML = `
      <div class="dp-spotlight-highlight"></div>
      <div class="dp-spotlight-popover" role="dialog" aria-modal="true">
        <div class="dp-spotlight-step-tag">Paso ${currentStepIdx + 1} de ${STEPS.length}</div>
        <h3 class="dp-spotlight-title">${step.title}</h3>
        <p class="dp-spotlight-desc">${step.desc}</p>
        ${practiceHtml}
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
    setTimeout(repositionActive, 240);
    window.addEventListener('resize', repositionActive);
    window.addEventListener('scroll', repositionActive, true);

    layerEl.querySelector('#btn-tour-skip').addEventListener('click', () => completeTour('keep_training'));
    layerEl.querySelector('#btn-tour-prev').addEventListener('click', () => {
      if (currentStepIdx > 0) renderStep(currentStepIdx - 1);
    });
    layerEl.querySelector('#btn-tour-next').addEventListener('click', () => renderStep(currentStepIdx + 1));
    const pracBtn = layerEl.querySelector('#btn-tour-practice');
    if (pracBtn) {
      pracBtn.addEventListener('click', () => triggerPractice(step.practiceType));
    }
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
