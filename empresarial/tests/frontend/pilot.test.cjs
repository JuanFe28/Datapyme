const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname,'../../static/js/app.js'),'utf8');

test('COP presentation preserves cents used in the persisted total', () => {
  const ctx = vm.createContext({Intl, window:{location:{pathname:'/dashboard'}},
    document:{addEventListener(){},getElementById(){return null;}}});
  vm.runInContext(script,ctx);
  assert.match(vm.runInContext('formatCOP(119.57)',ctx),/119,57/);
});

test('privacy request sends authenticated JSON instead of a cookie-only form', async () => {
  let sent;
  const button={disabled:false}; const status={textContent:''};
  const ctx = vm.createContext({Intl, window:{location:{pathname:'/dashboard'}},
    document:{addEventListener(){},getElementById(id){return ({'deletion-reason':{value:'Solicitud sintética'},'btn-request-deletion':button,'deletion-status':status})[id]||null;}},
    fetch:async (url,options)=>{sent={url,...options};return {ok:false,json:async()=>({detail:'No se pudo registrar'})};},
    confirm:()=>true,
  });
  vm.runInContext(script,ctx);
  vm.runInContext("dashboardData={token:'synthetic-token'}",ctx);
  assert.equal(vm.runInContext('typeof submitDeletionRequest',ctx),'function');
  await vm.runInContext('submitDeletionRequest({preventDefault(){}})',ctx);
  assert.equal(sent.headers.Authorization,'Bearer synthetic-token');
  assert.equal(JSON.parse(sent.body).reason,'Solicitud sintética');
  assert.equal(status.textContent,'No se pudo registrar');
  assert.equal(button.disabled,false);
});
