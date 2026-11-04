from decimal import Decimal,InvalidOperation,ROUND_CEILING,ROUND_HALF_UP,localcontext
from fastapi import HTTPException

MONEY_FIELDS=('initial_investment','monthly_fixed','unit_price','unit_variable')
INPUT_LABELS={'initial_investment':'Inversión inicial empresarial COP','monthly_fixed':'Costos fijos mensuales COP','unit_price':'Precio mensual por cliente COP','unit_variable':'Costo variable mensual por cliente COP','initial_customers':'Clientes iniciales','monthly_growth':'Crecimiento mensual de clientes %','months':'Horizonte de meses'}
FORMULA_LABELS={'contribution':'Contribución por cliente','break_even':'Punto de equilibrio mensual','customers':'Clientes proyectados por mes','balance':'Saldo de caja acumulado'}
def parse_inputs(form):
    result={}
    for key in (*MONEY_FIELDS,'monthly_growth','initial_customers','months'):
        try:
            value=Decimal(str(form.get(key,'')))
            if not value.is_finite(): raise InvalidOperation()
        except (InvalidOperation,ValueError): raise HTTPException(422,'Completa valores numéricos válidos, sin separadores de miles.')
        if key=='monthly_growth':
            if not Decimal('-100')<=value<=Decimal('100'): raise HTTPException(422,'El crecimiento mensual debe estar entre -100 y 100 %.')
        elif value<0 or value>Decimal('1000000000000'): raise HTTPException(422,'Los valores deben estar entre cero y un billón de COP.')
        if key in ('initial_customers','months') and value!=value.to_integral_value(): raise HTTPException(422,'Clientes y meses deben ser enteros.')
        result[key]=str(value)
    if not 1<=int(result['months'])<=60: raise HTTPException(422,'Proyecta entre 1 y 60 meses.')
    if int(result['initial_customers'])>1_000_000: raise HTTPException(422,'Máximo un millón de clientes iniciales por escenario.')
    return result

def money(value): return str(value.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))
def calculate_scenario(inputs):
    with localcontext() as context:
        context.prec=80
        return _calculate_scenario(inputs)

def _calculate_scenario(inputs):
    p={k:Decimal(v) for k,v in inputs.items()}
    contribution=p['unit_price']-p['unit_variable']
    equilibrium=int((p['monthly_fixed']/contribution).to_integral_value(rounding=ROUND_CEILING)) if contribution>0 else None
    balance=-p['initial_investment']; cash=[]
    for index in range(int(p['months'])):
        customers=(p['initial_customers']*(1+p['monthly_growth']/100)**index).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
        revenue=customers*p['unit_price']; variable=customers*p['unit_variable']; net=revenue-variable-p['monthly_fixed']; balance+=net
        cash.append({'month':index+1,'customers':int(customers),'revenue':money(revenue),'variable':money(variable),'fixed':money(p['monthly_fixed']),'net':money(net),'balance':money(balance)})
    return {'contribution':money(contribution),'break_even_customers':equilibrium,'cash_flow':cash,'initial_investment':money(p['initial_investment']),'formulas':{'contribution':'Precio mensual − costo variable por cliente','break_even':'Techo(costos fijos mensuales / contribución); no existe equilibrio si contribución ≤ 0','customers':'Redondeo(clientes iniciales × (1 + crecimiento mensual / 100)^(mes − 1))','balance':'−Inversión inicial + suma de flujos netos hasta el mes'},'limitations':'Proyección basada en supuestos explícitos; no demuestra viabilidad. No incluye impuestos, financiación, inflación ni tasas de descuento. El presupuesto académico de $9.559.000 se registra por separado de la inversión empresarial.'}
