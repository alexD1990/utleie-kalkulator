from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass
class InputsLite:
    purchase_price: float
    down_value: float
    down_is_percent: bool
    annual_rate: float
    years: int
    ppy: int

    # Månedlige kostnader
    felleskost: float
    kommunale: float
    eiendomsskatt: float
    vedlikehold: float
    forsikring: float
    annet: float

    # Inntekt
    monthly_rent: float

    # Vekst
    annual_rent_inflation: float
    annual_cost_inflation: float
    annual_value_growth: float

    # Lånetype
    loan_type: str  # "annuity" | "serial"

    # Airbnb
    airbnb_enabled: bool = False
    airbnb_months_per_year: int = 0
    airbnb_nightly_price: float = 0.0
    airbnb_occupancy: float = 0.0     # 0-1
    airbnb_apply_rent_inflation: bool = False

def annuity_payment(P: float, r: float, n: int) -> float:
    if n <= 0:
        return 0.0
    if r == 0:
        return P / n
    return P * r / (1 - (1 + r)**(-n))

def amortization(principal: float, annual_rate: float, years: int, ppy: int, loan_type: str) -> pd.DataFrame:
    n = int(years * ppy)
    r = annual_rate / ppy
    rows = []
    bal = float(principal)
    if loan_type == "annuity":
        pmt = annuity_payment(principal, r, n)
        for t in range(1, n+1):
            interest = bal * r
            prin = pmt - interest
            if t == n:
                prin = bal
                pmt = prin + interest
            bal -= prin
            rows.append({"period": t, "payment": pmt, "interest": interest, "principal": prin, "balance": max(bal,0.0)})
    else:
        prin_fixed = principal / n
        for t in range(1, n+1):
            interest = bal * r
            pmt = prin_fixed + interest
            if t == n:
                prin = bal
                pmt = prin + interest
                bal = 0.0
            else:
                prin = prin_fixed
                bal -= prin
            rows.append({"period": t, "payment": pmt, "interest": interest, "principal": prin, "balance": max(bal,0.0)})
    df = pd.DataFrame(rows)
    df["year"] = ((df["period"] - 1) // ppy) + 1
    return df

def build_model(inp: InputsLite):
    down = inp.down_value * inp.purchase_price if inp.down_is_percent else inp.down_value
    loan_amt = max(0.0, inp.purchase_price - down)
    amort = amortization(loan_amt, inp.annual_rate, inp.years, inp.ppy, inp.loan_type)

    n = len(amort)
    months = np.arange(1, n+1)
    years_idx = ((months - 1) // inp.ppy) + 1

    rent_r = (1 + inp.annual_rent_inflation)**(1/12) - 1
    cost_r = (1 + inp.annual_cost_inflation)**(1/12) - 1

    rent_series = np.array([inp.monthly_rent * ((1 + rent_r)**(m-1)) for m in months])

    if inp.airbnb_enabled and inp.airbnb_months_per_year > 0:
        months_per_year = inp.ppy
        airbnb_months = min(max(int(inp.airbnb_months_per_year), 0), months_per_year)
        if inp.airbnb_apply_rent_inflation:
            nightly_series = np.array([inp.airbnb_nightly_price * ((1 + rent_r)**(m-1)) for m in months])
        else:
            nightly_series = np.full(n, inp.airbnb_nightly_price, dtype=float)
        booked_nights = 30.0 * float(inp.airbnb_occupancy)
        airbnb_month_income = nightly_series * booked_nights
        for m_idx in range(n):
            pos_in_year = (m_idx % months_per_year) + 1
            if pos_in_year <= airbnb_months:
                rent_series[m_idx] = airbnb_month_income[m_idx]

    base_cost = inp.felleskost + inp.kommunale + inp.eiendomsskatt + inp.vedlikehold + inp.forsikring + inp.annet
    cost_series = np.array([base_cost * ((1 + cost_r)**(m-1)) for m in months])

    noi_month = rent_series - cost_series
    ds_month = amort["payment"].values
    cf_month = noi_month - ds_month

    value_year = inp.purchase_price * ((1 + inp.annual_value_growth) ** (years_idx - 1))

    monthly = pd.DataFrame({
        "month": months,
        "year": years_idx,
        "rent": rent_series,
        "operating_costs": cost_series,
        "NOI": noi_month,
        "debt_service": ds_month,
        "cash_flow": cf_month,
        "loan_balance": amort["balance"].values,
        "property_value": value_year,
        "equity": value_year - amort["balance"].values
    })

    yearly = monthly.groupby("year", as_index=False).agg({
        "rent": "sum",
        "operating_costs": "sum",
        "NOI": "sum",
        "debt_service": "sum",
        "cash_flow": "sum",
        "loan_balance": "last",
        "property_value": "last",
        "equity": "last"
    })

    metrics = {
        "month1_cash_flow": float(monthly.loc[monthly["month"]==1, "cash_flow"].iloc[0]),
        "year1_noi": float(yearly.loc[yearly["year"]==1, "NOI"].iloc[0]),
        "year1_debt_service": float(yearly.loc[yearly["year"]==1, "debt_service"].iloc[0]),
        "dscr_y1": float(yearly.loc[yearly["year"]==1, "NOI"].iloc[0] / max(1e-9, yearly.loc[yearly["year"]==1, "debt_service"].iloc[0])),
        "cap_rate_y1": float((yearly.loc[yearly["year"]==1, "NOI"].iloc[0]) / max(1e-9, inp.purchase_price)),
        "ltv_at_purchase": loan_amt / max(1e-9, inp.purchase_price),
    }

    return {
        "amortization": amort,
        "monthly": monthly,
        "yearly": yearly,
        "metrics": metrics,
        "loan_amount": loan_amt,
        "down_payment": down
    }