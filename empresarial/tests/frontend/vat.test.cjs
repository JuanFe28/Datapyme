const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
test('cart displays tax from each product instead of assuming 19 percent', () => {
  const elements = new Map();
  for (const id of ['sale-subtotal-display','sale-vat-display','sale-total-display']) elements.set(id, {textContent:''});
  const context = vm.createContext({Intl, console, structuredClone,
    window:{location:{pathname:'/dashboard'}},
    document:{addEventListener(){}, getElementById:id=>elements.get(id), querySelectorAll:()=>[]},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/js/app.js'),'utf8'), context);
  vm.runInContext(`dashboardData={products:[
    {id:'a',sale_price:'100',vat_rate:'19',stock_qty:10},
    {id:'b',sale_price:'100',vat_rate:'5',stock_qty:10},
    {id:'c',sale_price:'100',vat_rate:'0',stock_qty:10}]};
    cartLines=['a','b','c'].map(product_id=>({product_id,quantity:1})); calculateCartTotals();`, context);
  assert.equal(elements.get('sale-vat-display').textContent.replace(/\D/g,''),'24');
  assert.equal(elements.get('sale-total-display').textContent.replace(/\D/g,''),'324');
});
test('receipt profit subtracts discount and excludes collected VAT', async () => {
  const elements = new Map(['sale-detail-profit','sale-detail-margin-pct'].map(id=>[id,{textContent:''}]));
  const context = vm.createContext({Intl, console,
    window:{location:{pathname:'/dashboard'}},
    document:{addEventListener(){}, getElementById:id=>elements.get(id)},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/js/app.js'),'utf8'), context);
  await vm.runInContext(`dashboardData={recent_sales:[{id:'sale',items:[],subtotal:'115000',
    discount_total:'15000',vat_total:'19000',total:'119000',cogs_total:'78000'}]};
    openSaleDetailDrawer('sale');`, context);
  assert.equal(elements.get('sale-detail-profit').textContent.replace(/\D/g,''),'22000');
  assert.equal(elements.get('sale-detail-margin-pct').textContent,'22.0 %');
});
