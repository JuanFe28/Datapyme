const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
function context(){
 const charts=[]; function Chart(element,config){charts.push(config);}
 const ctx=vm.createContext({Intl,structuredClone,Chart,window:{Chart,location:{pathname:'/dashboard'}},document:{addEventListener(){},getElementById(){return {};}}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/js/app.js'),'utf8'),ctx);
 return {ctx,charts};
}
test('insufficient history never draws fabricated example sales',()=>{
 const {ctx,charts}=context();
 vm.runInContext("dashboardData={forecast:{status:'insufficient_data',observed_periods:0}};initForecastChart();initForecastModuleChart();",ctx);
 assert.equal(charts.length,0);
});
test('a valid zero forecast is preserved instead of replacing it with growth',()=>{
 const {ctx,charts}=context();
 vm.runInContext("dashboardData={forecast:{status:'ok',next_period_ols:0,audit_table:[{period_label:'Jul',observed_y:3},{period_label:'Ago',observed_y:2},{period_label:'Sep',observed_y:1}]}};initForecastChart();initForecastModuleChart();",ctx);
 assert.equal(charts.length,2);
 for(const chart of charts)assert.equal(chart.data.datasets[0].data.at(-1),0);
});
