
from __future__ import annotations
from typing import Any
import math

def _f(v:Any,d:float=0.0)->float:
    try:return float(v)
    except (TypeError,ValueError):return d

def npv(rate:float,cashflows:list[float])->float:
    total=0.0
    base=1.0+rate
    if base<=0:return float("nan")
    discount=1.0
    for i,cf in enumerate(cashflows):
        if i==0:
            total+=cf
        else:
            discount*=base
            if not math.isfinite(discount) or discount==0:
                break
            total+=cf/discount
    return total

def irr(cashflows:list[float])->float|None:
    points=[-0.95,-0.8,-0.5,-0.25,0,0.01,0.03,0.05,0.08,0.1,0.2,0.5,1,2,5]
    vals=[]
    for p in points:
        v=npv(p,cashflows)
        if math.isfinite(v):
            vals.append((p,v))
    for (a,fa),(b,fb) in zip(vals,vals[1:]):
        if fa==0:return a
        if fa*fb<0:
            low,high=a,b
            for _ in range(160):
                mid=(low+high)/2
                fm=npv(mid,cashflows)
                fl=npv(low,cashflows)
                if abs(fm)<1e-6:return mid
                if fl*fm<=0:high=mid
                else:low=mid
            return (low+high)/2
    return None

def calculate_business_cashflow(project:dict[str,Any],settings:dict[str,Any])->dict[str,Any]:
    outputs=project.get("module_outputs",{})
    m5=outputs.get("module5") or {}
    m7=outputs.get("module7") or {}
    include_m7=bool(settings.get("include_module7_costs",True))

    if not m5:
        raise ValueError("Module 5 output is required.")
    if include_m7 and not m7:
        raise ValueError("Module 7 output is required when renewal costs are included.")

    common=project.get("common",{})
    building=common.get("building") or {}
    m5_summary=m5.get("summary") or m5.get("result") or {}
    currency=str(m5.get("currency",m7.get("currency","JPY")))

    initial=_f(
        m5_summary.get("tax_included_construction_cost"),
        _f(
            m5_summary.get("total_construction_cost"),
            _f(m5_summary.get("tax_excluded_construction_cost"))
        )
    )
    if initial<=0:
        initial=_f(m5.get("total_construction_cost"))

    initial+=_f(settings.get("other_initial_cost_JPY"))

    gfa=_f(
        common.get("scale_gfa_m2"),
        _f(building.get("gross_floor_area_m2"))
    )
    annual_rent_per_m2=_f(settings.get("annual_rent_JPY_per_m2"),30000)
    year1_gross=max(gfa,0.0)*max(annual_rent_per_m2,0.0)

    years=max(int(_f(settings.get("analysis_years"),200)),1)
    rent_growth=_f(settings.get("rent_growth_percent"),1)/100
    vacancy=max(min(_f(settings.get("vacancy_rate_percent"),5)/100,1),0)
    opex=max(_f(settings.get("operating_expense_percent"),20)/100,0)
    property_tax_rate=max(_f(settings.get("property_tax_percent_of_initial_cost"),1.4)/100,0)
    insurance_rate=max(_f(settings.get("insurance_percent_of_initial_cost"),.15)/100,0)
    discount=_f(settings.get("discount_rate_percent"),4)/100
    terminal_cap=max(_f(settings.get("terminal_cap_rate_percent"),5)/100,.0001)
    sale_cost=max(_f(settings.get("terminal_sale_cost_percent"),3)/100,0)
    repair_escalation=_f(settings.get("repair_cost_escalation_percent"),1)/100
    income_tax_rate=max(_f(settings.get("income_tax_percent"),0)/100,0)
    include_terminal=bool(settings.get("include_terminal_value",True))

    m7annual={
        int(_f(r.get("year"))):_f(r.get("annual_cost"))
        for r in m7.get("annual_cost_timeline",[])
    }

    rows=[];cashflows=[-initial];cum=-initial;cum_disc=-initial
    simple=None;disc_payback=None;terminal_value=0.0
    for year in range(1,years+1):
        gross=year1_gross*((1+rent_growth)**(year-1))
        effective=gross*(1-vacancy)
        operating=effective*opex
        property_tax=initial*property_tax_rate
        insurance=initial*insurance_rate
        m7cost=m7annual.get(year,0.0)*((1+repair_escalation)**(year-1)) if include_m7 else 0.0
        pretax=effective-operating-property_tax-insurance-m7cost
        income_tax=max(pretax,0)*income_tax_rate
        net=pretax-income_tax
        terminal_net=0.0
        if year==years and include_terminal:
            ng=year1_gross*((1+rent_growth)**year)
            ne=ng*(1-vacancy)
            nnoi=ne-ne*opex-initial*property_tax_rate-initial*insurance_rate
            terminal_value=max(nnoi/terminal_cap,0)
            terminal_net=terminal_value*(1-sale_cost)
            net+=terminal_net
        discount_base=1.0+discount
        if discount_base<=0.0:
            raise ValueError("Discount rate must be greater than -100%.")
        discount_factor=discount_base**year
        discounted=0.0 if not math.isfinite(discount_factor) else net/discount_factor
        cum+=net;cum_disc+=discounted
        if simple is None and cum>=0:simple=year
        if disc_payback is None and cum_disc>=0:disc_payback=year
        rows.append({
            "year":year,
            "gross_rent":gross,
            "effective_rent":effective,
            "operating_expense":operating,
            "property_tax":property_tax,
            "insurance":insurance,
            "module7_cost":m7cost,
            "income_tax":income_tax,
            "terminal_sale_proceeds":terminal_net,
            "net_cashflow":net,
            "discounted_cashflow":discounted,
            "cumulative_net_cashflow":cum,
            "cumulative_discounted_cashflow":cum_disc,
        })
        cashflows.append(net)

    project_irr=irr(cashflows)
    first100_cashflows=cashflows[:min(len(cashflows),101)]
    first100_rows=rows[:100]
    irr100=irr(first100_cashflows)
    summary={
        "initial_investment":initial,
        "gross_floor_area_m2":gfa,
        "annual_rent_JPY_per_m2":annual_rent_per_m2,
        "year1_gross_rent":year1_gross,
        "total_gross_rent":sum(r["gross_rent"] for r in rows),
        "total_effective_rent":sum(r["effective_rent"] for r in rows),
        "total_operating_expense":sum(r["operating_expense"] for r in rows),
        "total_property_tax":sum(r["property_tax"] for r in rows),
        "total_insurance":sum(r["insurance"] for r in rows),
        "total_module7_cost":sum(r["module7_cost"] for r in rows),
        "total_income_tax":sum(r["income_tax"] for r in rows),
        "terminal_sale_value":terminal_value,
        "net_cashflow_total":sum(cashflows),
        "npv":npv(discount,cashflows),
        "irr_percent":project_irr*100 if project_irr is not None else None,
        "simple_payback_year":simple,
        "discounted_payback_year":disc_payback,
        "npv_100_year":npv(discount,first100_cashflows),
        "irr_100_year_percent":irr100*100 if irr100 is not None else None,
        "net_cashflow_100_year":sum(first100_cashflows),
        "gross_rent_100_year":sum(r["gross_rent"] for r in first100_rows),
    }
    return {
        "version":"9.8",
        "module":"module8",
        "currency":currency,
        "analysis_years":years,
        "settings":settings,
        "cashflow":rows,
        "summary":summary,
        "status":"provisional_planning_comparison",
        "source_modules":["module5","module7"],
    }
