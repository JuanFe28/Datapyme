const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');

test('a rejected cleanup keeps the tour and explains why instead of pretending it finished',async()=>{
  const buttons=new Map(); let reloads=0; const alerts=[];
  const storage=new Map();
  const ctx=vm.createContext({console,setTimeout(){},alert:message=>alerts.push(message),
    sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    window:{location:{pathname:'/dashboard',reload(){reloads++;}},addEventListener(){},removeEventListener(){}},
    document:{addEventListener(){},getElementById(){return {textContent:JSON.stringify({token:'synthetic'})};},
      querySelectorAll(){return [];},body:{appendChild(){}},
      createElement(){return {remove(){},querySelector(selector){return {addEventListener(type,callback){buttons.set(selector,callback);}};}};}},
    fetch:async()=>({ok:false,json:async()=>({detail:'Hay operaciones reales relacionadas; se conservó todo.'})}),
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/js/spotlight_tour.js'),'utf8'),ctx);
  ctx.window.startSpotlightTour();
  for(let i=0;i<4;i++)buttons.get('#btn-tour-next')();
  await buttons.get('#btn-tour-purge-training')();
  assert.equal(reloads,0);
  assert.equal(ctx.window.__SPOTLIGHT_TRAINING_ACTIVE__,true);
  assert.match(alerts[0],/operaciones reales/);
});
