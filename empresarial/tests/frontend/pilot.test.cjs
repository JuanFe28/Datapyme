const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname,'../../static/js/app.js'),'utf8');

test('receipt treats imported product names and image attributes as data, not HTML',async()=>{
  const body={rows:[],appendChild(row){this.rows.push(row);}};
  const ctx=vm.createContext({Intl,window:{location:{pathname:'/dashboard'}},document:{addEventListener(){},getElementById:id=>id==='sale-detail-items-tbody'?body:null,createElement:()=>({innerHTML:''})}});
  vm.runInContext(script,ctx);
  vm.runInContext(`dashboardData={products:[],recent_sales:[{id:'s',items:[{product_name:'<img src=x onerror=alert(1)>',product_sku:'<script>x</script>',product_unit:'kg',product_image_url:'/x" onerror="alert(1)',quantity:'1',unit_price:'100',unit_cost_snapshot:'60',line_total:'100'}]}]}`,ctx);
  await vm.runInContext("openSaleDetailDrawer('s')",ctx);
  assert.doesNotMatch(body.rows[0].innerHTML,/<script>|<img src=x|" onerror="/);
  assert.match(body.rows[0].innerHTML,/&lt;img/);
});

test('opening a drawer exposes its content to assistive technology and closing hides it', () => {
  const attrs = new Map([['aria-hidden','true']]);
  const element={classList:{add(){},remove(){}},querySelector(){return null;},setAttribute(k,v){attrs.set(k,v);}};
  const ctx=vm.createContext({Intl,window:{location:{pathname:'/dashboard'}},document:{addEventListener(){},getElementById(){return element;}}});
  vm.runInContext(script,ctx);
  vm.runInContext("openDrawer('drawer-sale-detail')",ctx);
  assert.equal(attrs.get('aria-hidden'),'false');
  vm.runInContext("closeDrawer('drawer-sale-detail')",ctx);
  assert.equal(attrs.get('aria-hidden'),'true');
});

test('COP presentation preserves cents used in the persisted total', () => {
  const ctx = vm.createContext({Intl, window:{location:{pathname:'/dashboard'}},
    document:{addEventListener(){},getElementById(){return null;}}});
  vm.runInContext(script,ctx);
  assert.match(vm.runInContext('formatCOP(119.57)',ctx),/119,57/);
});

test('fractional quantity rounds the taxable base exactly like the server',()=>{
  const elements=new Map(['sale-subtotal-display','sale-vat-display','sale-total-display'].map(id=>[id,{textContent:''}]));
  const ctx=vm.createContext({Intl,window:{location:{pathname:'/dashboard'}},document:{addEventListener(){},getElementById:id=>elements.get(id),querySelectorAll:()=>[]}});
  vm.runInContext(script,ctx);
  vm.runInContext("dashboardData={company_tax:{status:'responsible'},products:[{id:'p',sale_price:'1.00',vat_rate:'19',stock_qty:'5'}]};cartLines=[{product_id:'p',quantity:1.005}];calculateCartTotals();",ctx);
  assert.match(elements.get('sale-subtotal-display').textContent,/1,01/);
  assert.equal(Number(elements.get('sale-total-display').textContent.replace(/[^\d,]/g,'').replace(',','.')),1.20);
});

test('the cart accepts a quarter kilogram instead of truncating it to one unit',()=>{
  const nodes=[];
  const create=()=>({children:[],style:{},setAttribute(){},appendChild(child){this.children.push(child);},addEventListener(type,fn){this[type]=fn;}});
  const container=create();
  const ctx=vm.createContext({Intl,window:{location:{pathname:'/dashboard'}},document:{addEventListener(){},getElementById:id=>id==='sale-cart-items'?container:null,querySelectorAll:()=>[],createElement(){const e=create();nodes.push(e);return e;}}});
  vm.runInContext(script,ctx);
  vm.runInContext("dashboardData={company_tax:{status:'not_responsible'},products:[{id:'p',sku:'KG',name:'Granel',sale_price:'100',vat_rate:'19',stock_qty:'5'}]};addCartLine();",ctx);
  const input=nodes.find(e=>e.className==='form-input cart-quantity-input');
  input.input({target:{value:'0.25'}});
  assert.equal(vm.runInContext('cartLines[0].quantity',ctx),0.25);
  assert.equal(input.step,'0.001');
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
