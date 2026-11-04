document.addEventListener('DOMContentLoaded', () => {
  window.lucide?.createIcons();
  const menu=document.getElementById('menuToggle'), sidebar=document.getElementById('sidebar'), shade=document.getElementById('shade');
  function closeMenu(){ sidebar?.classList.remove('open'); shade?.classList.remove('open'); menu?.setAttribute('aria-expanded','false'); }
  menu?.setAttribute('aria-controls','sidebar'); menu?.setAttribute('aria-expanded','false');
  menu?.addEventListener('click',()=>{const open=sidebar.classList.toggle('open'); shade?.classList.toggle('open',open); menu.setAttribute('aria-expanded',String(open));});
  shade?.addEventListener('click',closeMenu);
  document.addEventListener('keydown',event=>{if(event.key==='Escape') closeMenu();});
  document.querySelectorAll('.nav-link.selected').forEach(link=>link.setAttribute('aria-current','page'));
  document.querySelectorAll('.notice-close').forEach(b=>b.addEventListener('click',()=>b.closest('.notice')?.remove()));
  document.querySelectorAll('[data-go-back]').forEach(b=>b.addEventListener('click',()=>history.back()));
  document.querySelectorAll('form[data-confirm]').forEach(form=>form.addEventListener('submit',event=>{if(!confirm(form.dataset.confirm))event.preventDefault();}));
  document.querySelectorAll('[data-table-search]').forEach(input=>input.addEventListener('input',()=>{
    const term=input.value.toLocaleLowerCase('es');
    document.querySelectorAll('table[data-searchable] tbody tr').forEach(row=>row.hidden=!row.textContent.toLocaleLowerCase('es').includes(term));
  }));

  const survey=document.getElementById('surveyForm');
  if(survey){
    // Evitar bloqueos silenciosos del navegador por controles invisibles/opacos
    survey.setAttribute('novalidate', 'true');
    const questions=[...survey.querySelectorAll('[data-question]')];
    const getValue=name=>survey.elements.namedItem(name)?.value||'';

    function condition(code){
      if(code==='M14')return getValue('M13')==='Sí';
      if(code==='M20')return ['Suscripción mensual','Suscripción anual'].includes(getValue('M19'));
      if(code==='V11')return getValue('V10')==='Sí';
      return true;
    }

    const exclusive={
      'M07':['No hay registro organizado'],
      'M08':['No lleva control sistemático'],
      'M10':['No enfrenta dificultades relevantes'],
      'M15':['Ninguno']
    };

    function updateMultiQuestion(question){
      const code = question.dataset.question;
      const grid = question.querySelector('.option-grid');
      if(!grid) return;
      const max = Number(grid.dataset.max || 100);
      const checkboxes = [...question.querySelectorAll('input[type="checkbox"]')];
      const checkedBoxes = checkboxes.filter(cb => cb.checked);
      const isExclusiveChecked = checkedBoxes.some(cb => (exclusive[code]||[]).includes(cb.value));

      let badge = question.querySelector('.badge-counter');
      if(!badge){
        badge = document.createElement('span');
        badge.className = 'badge-counter';
        question.querySelector('.question-label')?.appendChild(badge);
      }

      if(isExclusiveChecked){
        checkboxes.forEach(cb => {
          const isThisExclusive = (exclusive[code]||[]).includes(cb.value);
          if(!isThisExclusive){
            cb.disabled = true;
            cb.checked = false;
            cb.closest('.option-tile')?.classList.add('disabled-tile');
          } else {
            cb.disabled = false;
            cb.closest('.option-tile')?.classList.remove('disabled-tile');
          }
        });
        badge.textContent = 'Opción única seleccionada';
        badge.classList.add('badge-counter-full');
      } else if(max < 100){
        if(checkedBoxes.length >= max){
          // Límite alcanzado: deshabilitar todas las opciones no seleccionadas
          checkboxes.forEach(cb => {
            if(!cb.checked){
              cb.disabled = true;
              cb.closest('.option-tile')?.classList.add('disabled-tile');
            } else {
              cb.disabled = false;
              cb.closest('.option-tile')?.classList.remove('disabled-tile');
            }
          });
          badge.textContent = `✓ Límite de ${max} alcanzado (${checkedBoxes.length} de ${max})`;
          badge.classList.add('badge-counter-full');
        } else {
          // Menos del máximo: rehabilitar todas
          checkboxes.forEach(cb => {
            cb.disabled = false;
            cb.closest('.option-tile')?.classList.remove('disabled-tile');
          });
          badge.textContent = `${checkedBoxes.length} de ${max} seleccionadas (máximo ${max})`;
          badge.classList.remove('badge-counter-full');
        }
      } else {
        checkboxes.forEach(cb => {
          cb.disabled = false;
          cb.closest('.option-tile')?.classList.remove('disabled-tile');
        });
        badge.textContent = checkedBoxes.length ? `${checkedBoxes.length} seleccionada(s)` : 'Selección múltiple';
        badge.classList.remove('badge-counter-full');
      }
    }

    function getQuestionError(question){
      if(question.hidden) return null;
      const code = question.dataset.question;
      const kind = question.dataset.kind;
      if(!condition(code)) return null;
      const required = question.dataset.required === 'yes' || code === 'M14' || code === 'V11';

      if(kind === 'select'){
        const val = question.querySelector('select')?.value?.trim() || '';
        if(required && !val) return 'Por favor seleccione una opción de la lista.';
      } else if(kind === 'scale'){
        const checked = question.querySelector('input[type="radio"]:checked');
        if(required && !checked) return 'Por favor seleccione una calificación del 1 al 5.';
      } else if(kind === 'multi'){
        const checked = question.querySelectorAll('input[type="checkbox"]:checked');
        if(required && checked.length === 0) return 'Por favor seleccione al menos una opción.';
      } else if(kind === 'number'){
        const num = question.querySelector('input[type="number"]')?.value?.trim();
        if(required && !num) return 'Por favor ingrese un valor numérico.';
      } else if(kind === 'textarea' || kind === 'text'){
        const txt = question.querySelector('textarea, input')?.value?.trim();
        if(required && !txt) return 'Por favor complete este campo.';
      }
      return null;
    }

    function clearQuestionError(question){
      question.classList.remove('question-error', 'pulse-highlight');
      const alert = question.querySelector('.live-error-alert');
      if(alert) alert.remove();
    }

    function showQuestionError(question, msg){
      question.classList.remove('question-ok');
      question.classList.add('question-error');
      let alert = question.querySelector('.live-error-alert');
      if(!alert){
        alert = document.createElement('div');
        alert.className = 'live-error-alert';
        question.appendChild(alert);
      }
      alert.innerHTML = `<i data-lucide="alert-circle" style="width:16px;height:16px;flex-shrink:0;"></i> <span>${msg}</span>`;
      window.lucide?.createIcons();
    }

    function update(){
      let total = 2; // base + consent
      let answered = 0;
      if(getValue('company_id')) answered++;
      if(survey.querySelector('[name=consent]')?.checked) answered++;

      for(const question of questions){
        const code = question.dataset.question;
        const visible = condition(code);
        question.hidden = !visible;
        const inputs = [...question.querySelectorAll('input,textarea,select')];
        inputs.forEach(input => {
          if(!visible) input.disabled = true;
        });

        if(!visible) continue;

        if(question.dataset.kind === 'multi'){
          updateMultiQuestion(question);
        }

        const selected = inputs.filter(input => input.checked);
        const filled = ['multi', 'scale'].includes(question.dataset.kind)
          ? selected.length > 0
          : inputs.some(input => input.value.trim() !== '');

        const required = question.dataset.required === 'yes' || code === 'M14' || code === 'V11';
        if(required){
          total++;
          if(filled){
            answered++;
            clearQuestionError(question);
            question.classList.add('question-ok');
          } else {
            question.classList.remove('question-ok');
          }
        }
      }

      const percent = Math.min(100, Math.round((100 * answered) / Math.max(1, total)));
      const progress = document.getElementById('surveyProgress');
      if(progress) progress.value = percent;
      const text = document.getElementById('progressText');
      if(text) text.textContent = `${answered} de ${total} respuestas completadas · ${percent} %`;
    }

    survey.addEventListener('change', event => {
      const target = event.target;
      if(target && target.type === 'checkbox'){
        const question = target.closest('[data-question]');
        if(question && question.dataset.kind === 'multi'){
          const code = question.dataset.question;
          const isExclusive = (exclusive[code]||[]).includes(target.value);
          const checkboxes = [...question.querySelectorAll('input[type="checkbox"]')];

          if(isExclusive && target.checked){
            checkboxes.forEach(cb => {
              if(cb !== target) cb.checked = false;
            });
          } else if(!isExclusive && target.checked){
            checkboxes.forEach(cb => {
              if((exclusive[code]||[]).includes(cb.value)) cb.checked = false;
            });
          }
        }
      }
      update();
    });

    survey.addEventListener('input', update);

    // Validación al enviar: muestra errores en rojo y hace scroll suave al primer error
    survey.addEventListener('submit', event => {
      let firstInvalid = null;
      let invalidCount = 0;

      // 1. Consentimiento
      const consentBox = survey.querySelector('[name=consent]');
      const consentLabel = document.getElementById('consent') || consentBox?.closest('.consent-field');
      if(consentBox && !consentBox.checked){
        invalidCount++;
        if(consentLabel){
          consentLabel.style.border = '2px solid #ef4444';
          consentLabel.style.background = '#fff5f5';
          if(!firstInvalid) firstInvalid = consentLabel;
        }
      } else if(consentLabel){
        consentLabel.style.border = '';
        consentLabel.style.background = '';
      }

      // 2. Cada pregunta
      for(const question of questions){
        const errorMsg = getQuestionError(question);
        if(errorMsg){
          invalidCount++;
          showQuestionError(question, errorMsg);
          if(!firstInvalid){
            firstInvalid = question;
          }
        } else {
          clearQuestionError(question);
        }
      }

      // 3. Si hay errores, detener y llevar la pantalla al primer error
      if(invalidCount > 0){
        event.preventDefault();
        event.stopPropagation();

        if(firstInvalid){
          firstInvalid.classList.add('pulse-highlight');
          firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
          const focusable = firstInvalid.querySelector('select, input:not([type=hidden]):not([disabled]), textarea');
          if(focusable){
            try { focusable.focus(); } catch(_) {}
          }
        }

        let submitNotice = document.getElementById('submitNotice');
        if(!submitNotice){
          submitNotice = document.createElement('div');
          submitNotice.id = 'submitNotice';
          submitNotice.className = 'notice notice-error';
          submitNotice.style.marginTop = '18px';
          submitNotice.style.textAlign = 'left';
          submitNotice.style.animation = 'shakeAlert 0.4s ease';
          const submitArea = survey.querySelector('.btn-primary')?.closest('div');
          if(submitArea) submitArea.appendChild(submitNotice);
        }
        submitNotice.innerHTML = `
          <i data-lucide="alert-triangle" style="width:20px;height:20px;flex-shrink:0;"></i>
          <span><strong>Faltan ${invalidCount} pregunta(s) por responder.</strong> Te hemos llevado a la primera pregunta marcada en rojo para que puedas completarla.</span>
        `;
        window.lucide?.createIcons();
        return false;
      }

      const submitBtn = survey.querySelector('button[type="submit"]');
      if(submitBtn){
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<span style="display:inline-flex;align-items:center;gap:8px;">Guardando respuestas... ⏳</span>`;
      }
    });

    update();
  }

  const analysisElement=document.getElementById('analysisData');
  if(analysisElement){
    const analysis=JSON.parse(analysisElement.textContent);
    document.querySelectorAll('[data-distribution]').forEach(canvas=>{
      const dist=analysis.distributions[canvas.dataset.distribution];
      if(!dist?.n)return;
      if(!window.Chart){canvas.hidden=true;return;}
      const wrap=label=>label.match(/.{1,35}(?:\s|$)|\S{1,35}/g)?.map(s=>s.trim())||label;
      new Chart(canvas,{type:'bar',data:{labels:dist.rows.map(r=>wrap(r.label)),datasets:[{label:'% de '+dist.unit,data:dist.rows.map(r=>r.percent),backgroundColor:'#159d8a',borderRadius:5,maxBarThickness:28}]},options:{indexAxis:'y',maintainAspectRatio:false,animation:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:context=>`${dist.rows[context.dataIndex].count} de ${dist.n} · ${context.raw} %`}}},scales:{x:{beginAtZero:true,max:100,ticks:{callback:value=>value+' %',font:{size:11}},grid:{color:'#edf2f4'}},y:{grid:{display:false},ticks:{color:'#385466',font:{size:11}}}}}});
    });
  }
  const financeElement=document.getElementById('financeData');
  if(financeElement&&window.Chart){const result=JSON.parse(financeElement.textContent);new Chart(document.getElementById('financeChart'),{type:'line',data:{labels:result.cash_flow.map(r=>'Mes '+r.month),datasets:[{label:'Flujo neto proyectado COP',data:result.cash_flow.map(r=>Number(r.net)),borderColor:'#159d8a',backgroundColor:'#159d8a18',fill:true,tension:0.15}]},options:{maintainAspectRatio:false,animation:false,scales:{y:{ticks:{callback:v=>new Intl.NumberFormat('es-CO',{notation:'compact'}).format(v)}}}}});}
});
