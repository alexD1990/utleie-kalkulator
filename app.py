import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from finance import InputsLite, build_model

import streamlit as st
import streamlit_authenticator as stauth

# --- Build credentials dict from Secrets (keeps your current TOML structure) ---
# secrets.toml must have:
# [credentials.usernames.alex]
# name = "Alex"
# password = "$2b$12$...bcrypt..."
# ...
# [cookie]
# name = "utleie_kalkulator_cookie"
# key = "A_LONG_RANDOM_SECRET"   # <-- we read this, but pass as cookie_key below
# expiry_days = 30

users = st.secrets["credentials"]["usernames"]  # {"alex": {"name": "...", "password": "..."} , ...}
creds = {"usernames": {u: {"name": users[u]["name"], "password": users[u]["password"]} for u in users}}

authenticator = stauth.Authenticate(
    credentials=creds,
    cookie_name=st.secrets["cookie"]["name"],
    cookie_key=st.secrets["cookie"]["key"],               # <-- important: param is cookie_key; value comes from ["key"]
    cookie_expiry_days=int(st.secrets["cookie"]["expiry_days"]),
)

name, auth_status, username = authenticator.login(
    location="main",
    fields={
        "Form name": "Logg inn",
        "Username": "Brukernavn",
        "Password": "Passord",
        "Login": "Logg inn",
    },
)

if auth_status is False:
    st.error("Feil brukernavn/passord"); st.stop()
elif auth_status is None:
    st.stop()  # user hasn't submitted yet

with st.sidebar:
    authenticator.logout("Logg ut", "sidebar")

st.set_page_config(page_title="Utleie kalkulator", page_icon="🏠", layout="wide")
st.title("🏠 Utleie kalkulator")

with st.sidebar:
    st.header("Kjøp & Lån")
    price = st.number_input("Kjøpesum (NOK)", min_value=0.0, value=5_000_000.0, step=50_000.0)
    dp_mode = st.selectbox("Egenkapital", ["% av pris", "NOK"], index=0)
    dp_val = st.number_input("Verdi", min_value=0.0, value=20.0 if dp_mode=="% av pris" else 1_000_000.0, step=1.0)
    loan_type = st.selectbox("Lånetype", ["annuity", "serial"], index=0)
    rate = st.number_input("Nominell rente p.a. (%)", min_value=0.0, value=6.0, step=0.1)/100.0
    years = st.number_input("Nedbetalingstid (år)", min_value=1, value=25, step=1)
    ppy = st.number_input("Betalinger per år", min_value=1, value=12, step=1)

    st.header("Månedlige kostnader (måned 1)")
    felles = st.number_input("Felleskostnader", min_value=0.0, value=1500.0, step=100.0)
    komm = st.number_input("Kommunale avgifter", min_value=0.0, value=600.0, step=50.0)
    eiendom = st.number_input("Eiendomsskatt", min_value=0.0, value=0.0, step=50.0)
    vedl = st.number_input("Vedlikehold", min_value=0.0, value=800.0, step=50.0)
    fors = st.number_input("Forsikring", min_value=0.0, value=400.0, step=50.0)
    annet = st.number_input("Annet", min_value=0.0, value=0.0, step=50.0)

    st.header("Inntekt (vanlig utleie)")
    rent_m = st.number_input("Bruttoleie per måned", min_value=0.0, value=25_000.0, step=500.0)

    st.header("Inflasjon / Vekst")
    rent_infl = st.number_input("Årlig leievekst (%)", min_value=0.0, value=2.5, step=0.1)/100.0
    cost_infl = st.number_input("Årlig kostnadsvekst (%)", min_value=0.0, value=2.0, step=0.1)/100.0
    value_growth = st.number_input("Årlig verdiøkning eiendom (%)", min_value=0.0, value=3.0, step=0.1)/100.0

    st.header("Benchmark-linjer for EK-graf")
    bench1_use_costinfl = st.checkbox("Benchmark A bruker kostnadsvekst (%)", value=True)
    bench1_name = st.text_input("Benchmark A navn", value="Inflasjon")
    bench1_rate = st.number_input("Benchmark A årlig avkastning (%)", min_value=0.0, value=2.0, step=0.1)/100.0
    bench2_name = st.text_input("Benchmark B navn", value="Indeks 10 %")
    bench2_rate = st.number_input("Benchmark B årlig avkastning (%)", min_value=0.0, value=10.0, step=0.1)/100.0

    st.header("Airbnb-utleie (valgfritt)")
    airbnb_enabled = st.toggle("Aktiver Airbnb-modus", value=False)
    airbnb_months = st.slider("Antall måneder pr. år på Airbnb (erstatter vanlig leie i disse månedene)", min_value=0, max_value=12, value=0, step=1)
    airbnb_price = st.number_input("Døgnpris (NOK)", min_value=0.0, value=3000.0, step=100.0)
    airbnb_occ = st.number_input("Dekningsgrad (% av døgn per måned)", min_value=0.0, max_value=100.0, value=75.0, step=1.0)/100.0
    airbnb_infl = st.toggle("La døgnpris følge leievekst", value=False)

inp = InputsLite(
    purchase_price=price,
    down_value=dp_val/100.0 if dp_mode=="% av pris" else dp_val,
    down_is_percent=(dp_mode=="% av pris"),
    annual_rate=rate,
    years=int(years),
    ppy=int(ppy),
    felleskost=felles,
    kommunale=komm,
    eiendomsskatt=eiendom,
    vedlikehold=vedl,
    forsikring=fors,
    annet=annet,
    monthly_rent=rent_m,
    annual_rent_inflation=rent_infl,
    annual_cost_inflation=cost_infl,
    annual_value_growth=value_growth,
    loan_type=loan_type,
    airbnb_enabled=airbnb_enabled,
    airbnb_months_per_year=int(airbnb_months),
    airbnb_nightly_price=airbnb_price,
    airbnb_occupancy=airbnb_occ,
    airbnb_apply_rent_inflation=airbnb_infl
)

out = build_model(inp)
amort = out["amortization"]
monthly = out["monthly"]
yearly = out["yearly"]
m = out["metrics"]

# Baseline uten Airbnb for sammenligning
out_no_airbnb = None
if airbnb_enabled:
    tmp = InputsLite(**{**inp.__dict__, "airbnb_enabled": False, "airbnb_months_per_year": 0, "airbnb_nightly_price": 0.0, "airbnb_occupancy": 0.0, "airbnb_apply_rent_inflation": False})
    out_no_airbnb = build_model(tmp)

# ---------------- KPI-er ----------------
st.subheader("Nøkkeltall")
DSCR_ADVARSEL = 1.20
c1, c2, c3, c4 = st.columns(4)
c1.metric("Kontantstrøm (måned 1)", f"NOK {m['month1_cash_flow']:.0f}", delta=m['month1_cash_flow'])
c2.metric("Avkastning på eiendom (år 1)", f"{m['cap_rate_y1']*100:.2f}%")
c3.metric("Gjeldsdekningsgrad (år 1)", f"{m['dscr_y1']:.2f}", delta=m['dscr_y1']-DSCR_ADVARSEL)
c4.metric("Belåningsgrad ved kjøp", f"{m['ltv_at_purchase']*100:.2f}%")

if m['dscr_y1'] < 1.0:
    st.error("Gjeldsdekningsgrad < 1,0: Netto driftsinntekt dekker ikke lånebetalingene.")
elif m['dscr_y1'] < DSCR_ADVARSEL:
    st.warning(f"Gjeldsdekningsgrad < {DSCR_ADVARSEL:.2f}: Dekningen er tynn.")

if m['month1_cash_flow'] < 0:
    st.error("Negativ kontantstrøm i måned 1.")

neg_years = out["yearly"].loc[out["yearly"]["cash_flow"] < 0, "year"].tolist()
if neg_years:
    st.warning(f"År med negativ kontantstrøm: {', '.join(map(str, neg_years))}.")
    
st.divider()

# ---------------- Grafer ----------------
st.subheader("Egenkapital – sammenligning (tilpassbare benchmarks)")
initial_equity = out["down_payment"]
år = (out_no_airbnb["yearly"]["year"] if (airbnb_enabled and out_no_airbnb) else yearly["year"]).to_numpy()

ek_eiendom_uten = (out_no_airbnb["yearly"]["equity"].to_numpy() if (airbnb_enabled and out_no_airbnb) else yearly["equity"].to_numpy())
ek_eiendom_med = (yearly["equity"].to_numpy() if airbnb_enabled else None)

rate_a = cost_infl if bench1_use_costinfl else bench1_rate
rate_b = bench2_rate
bench_a = initial_equity * np.power(1 + rate_a, år)
bench_b = initial_equity * np.power(1 + rate_b, år)

data = {"År": år, "Egenkapital (eiendom)": ek_eiendom_uten, bench1_name: bench_a, bench2_name: bench_b}
if airbnb_enabled and ek_eiendom_med is not None:
    data["Egenkapital (eiendom + Airbnb)"] = ek_eiendom_med

sammenlign_df = pd.DataFrame(data)
y_cols = ["Egenkapital (eiendom)", bench1_name, bench2_name]
if airbnb_enabled and "Egenkapital (eiendom + Airbnb)" in sammenlign_df.columns:
    y_cols.append("Egenkapital (eiendom + Airbnb)")

fig_compare = px.line(sammenlign_df, x="År", y=y_cols, markers=True, labels={"value":"Beløp (NOK)", "variable":"Scenario"})
st.plotly_chart(fig_compare, use_container_width=True)

st.subheader("Eiendomsverdi, restgjeld og egenkapital")
yearly_base = (out_no_airbnb["yearly"] if (airbnb_enabled and out_no_airbnb) else yearly)
eq_df = yearly_base[["year","property_value","loan_balance","equity"]].rename(columns={"year":"År","property_value":"Eiendomsverdi","loan_balance":"Restgjeld","equity":"Egenkapital"})
fig2 = px.line(eq_df, x="År", y=["Eiendomsverdi","Restgjeld","Egenkapital"], markers=True, labels={"value":"Beløp (NOK)", "variable":"Serie"})
if airbnb_enabled and out_no_airbnb:
    ek_med = yearly.rename(columns={"year":"År"})[["År","equity"]].rename(columns={"equity":"Egenkapital (med Airbnb)"})
    fig2.add_scatter(x=ek_med["År"], y=ek_med["Egenkapital (med Airbnb)"], mode="lines+markers", name="Egenkapital (med Airbnb)")
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Kontantstrøm (årlig)")
if airbnb_enabled and out_no_airbnb:
    cf_df = pd.DataFrame({"År": out_no_airbnb["yearly"]["year"], "Kontantstrøm (uten Airbnb)": out_no_airbnb["yearly"]["cash_flow"], "Kontantstrøm (med Airbnb)": yearly["cash_flow"]})
    cf_melt = cf_df.melt(id_vars="År", var_name="Serie", value_name="Kontantstrøm")
    fig3 = px.bar(cf_melt, x="År", y="Kontantstrøm", color="Serie", barmode="group")
else:
    fig3 = px.bar(yearly.rename(columns={"year":"År","cash_flow":"Kontantstrøm"}), x="År", y="Kontantstrøm", labels={"År":"År","Kontantstrøm":"Årlig kontantstrøm (NOK)"})
st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ---------------- Tabeller ----------------
st.subheader("Tabeller")
amort_no = amort.rename(columns={"period":"Måned","year":"År","payment":"Betaling","interest":"Rente","principal":"Avdrag","balance":"Restgjeld"})
monthly_no = monthly.rename(columns={"month":"Måned","year":"År","rent":"Leieinntekt","operating_costs":"Driftskostnader","NOI":"Netto driftsinntekt","debt_service":"Gjeldsbetjening","cash_flow":"Kontantstrøm","loan_balance":"Restgjeld","property_value":"Eiendomsverdi","equity":"Egenkapital"})
yearly_no = yearly.rename(columns={"year":"År","rent":"Leieinntekt","operating_costs":"Driftskostnader","NOI":"Netto driftsinntekt","debt_service":"Gjeldsbetjening","cash_flow":"Kontantstrøm","loan_balance":"Restgjeld","property_value":"Eiendomsverdi","equity":"Egenkapital"})
t1, t2, t3 = st.tabs(["Amortisering (måned)", "Resultat (måned)", "Resultat (år)"])
with t1:
    st.dataframe(amort_no, use_container_width=True, height=300)
    st.download_button("Last ned amortisering (CSV)", data=amort_no.to_csv(index=False).encode("utf-8"), file_name="amortisering.csv", mime="text/csv")
with t2:
    st.dataframe(monthly_no, use_container_width=True, height=380)
    st.download_button("Last ned månedstabell (CSV)", data=monthly_no.to_csv(index=False).encode("utf-8"), file_name="maaned.csv", mime="text/csv")
with t3:
    st.dataframe(yearly_no, use_container_width=True, height=320)
    st.download_button("Last ned årstabell (CSV)", data=yearly_no.to_csv(index=False).encode("utf-8"), file_name="aar.csv", mime="text/csv")

st.caption("På norsk, med justerbare benchmarks og Airbnb-sammenligning (kun når aktivert).")