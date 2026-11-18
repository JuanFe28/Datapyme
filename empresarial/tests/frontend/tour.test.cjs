const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');

test('a rejected cleanup keeps the tour and explains why instead of pretending it finished',async()=>{
  const buttons=new Map(); let reloads=0; const alerts=[];
  const storage=new Map();
  const button = (selector) => ({
    addEventListener(type, callback) { buttons.set(selector, callback); },
  });
  const highlight = { hidden: true, classList: { toggle() {} } };
  const card = {
    isConnected: true,
    style: {},
    classList: { add() {} },
    getBoundingClientRect: () => ({ width: 320, height: 210 }),
    focus() {},
  };
  const content = {
    querySelector(selector) { return selector.startsWith('#btn-') ? button(selector) : card; },
  };
  const ctx=vm.createContext({console,setTimeout(){},alert:message=>alerts.push(message),
    sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    window:{innerWidth:390,innerHeight:844,location:{pathname:'/dashboard',reload(){reloads++;}},addEventListener(){},removeEventListener(){}},
    document:{addEventListener(){},removeEventListener(){},getElementById(id){return id === 'dashboard-data' ? {textContent:JSON.stringify({token:'synthetic'})} : null;},
      querySelectorAll(){return [];},body:{appendChild(){}},
      createElement() {
        return {
          remove() {},
          querySelector(selector) {
            if (selector === '.dp-spotlight-content') return content;
            if (selector === '.dp-spotlight-highlight') return highlight;
            return card;
          },
        };
      },
    },
    fetch:async()=>({ok:false,json:async()=>({detail:'Hay operaciones reales relacionadas; se conservó todo.'})}),
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/js/spotlight_tour.js'),'utf8'),ctx);
  await ctx.window.startSpotlightTour();
  for (let i = 0; i < 7; i++) await buttons.get('#btn-tour-next')();
  await buttons.get('#btn-tour-purge-training')();
  assert.equal(reloads,0);
  assert.equal(ctx.window.__SPOTLIGHT_TRAINING_ACTIVE__,true);
  assert.match(alerts[0],/operaciones reales/);
});
