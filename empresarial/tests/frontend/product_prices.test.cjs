const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function fixture() {
  const elements = new Map();
  const ctx = vm.createContext({Intl, console,
    window:{location:{pathname:'/dashboard'}},
    document:{addEventListener(){},getElementById:id=>elements.get(id),querySelectorAll:()=>[]},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/js/app.js'),'utf8'),ctx);
  for(const prefix of ['prod','edit-prod']) {
    elements.set(prefix+'-price',{value:'10000'});
    elements.set(prefix+'-vat-rate',{value:'19'});
    elements.set(prefix+'-final-price',{textContent:''});
  }
  return {elements,ctx};
}

test('product forms preview base plus effective VAT before saving',()=>{
  const {elements,ctx}=fixture();
  vm.runInContext(`dashboardData={company_tax:{status:'responsible'}}; updateProductPricePreviews();`,ctx);
  for(const prefix of ['prod','edit-prod']) {
    assert.match(elements.get(prefix+'-final-price').textContent,/11[.\s]?900/);
    assert.match(elements.get(prefix+'-final-price').textContent,/1[.\s]?900/);
    assert.equal(elements.get(prefix+'-price').value,'10000');
  }
  elements.get('prod-price').value='11900';
  vm.runInContext('updateProductPricePreviews();',ctx);
  assert.match(elements.get('prod-final-price').textContent,/14[.\s]?161/);
  vm.runInContext(`dashboardData.company_tax.status='not_responsible'; updateProductPricePreviews();`,ctx);
  assert.match(elements.get('prod-final-price').textContent,/11[.\s]?900/);
  assert.match(elements.get('prod-final-price').textContent,/IVA.*0/);
  vm.runInContext(`dashboardData.company_tax.status='pending'; updateProductPricePreviews();`,ctx);
  assert.match(elements.get('prod-final-price').textContent,/Confirma.*IVA/);
  assert.doesNotMatch(elements.get('prod-final-price').textContent,/14[.\s]?161/);
});

test('product price preview follows 0 and 5 percent and cent rounding',()=>{
  const {elements,ctx}=fixture();
  elements.get('prod-price').value='0.10';
  elements.get('prod-vat-rate').value='5';
  vm.runInContext(`dashboardData={company_tax:{status:'responsible'}}; updateProductPricePreviews();`,ctx);
  assert.match(elements.get('prod-final-price').textContent,/0,11/);
  elements.get('prod-vat-rate').value='0';
  vm.runInContext('updateProductPricePreviews();',ctx);
  assert.match(elements.get('prod-final-price').textContent,/Final a cobrar por unidad:.*0,1 COP/);
});

test('import review button never claims it will save while preview is selected',()=>{
  const {elements,ctx}=fixture();
  elements.set('import-mode',{value:'preview'});
  const button={textContent:''}; elements.set('btn-submit-import',button);
  vm.runInContext('updateImportButton();',ctx);
  assert.match(button.textContent,/Revisar.*sin guardar/);
  elements.get('import-mode').value='commit';
  vm.runInContext('updateImportButton();',ctx);
  assert.match(button.textContent,/Confirmar.*guardar/);
});
