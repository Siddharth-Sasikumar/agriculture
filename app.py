from pathlib import Path
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
RISK_FILE = BASE_DIR / "data" / "output" / "risk_report.csv"
PHASE_FILE = BASE_DIR / "data" / "output" / "phase_summary.csv"


@st.cache_data
def load_data():
    risk_df = pd.read_csv(RISK_FILE)
    phase_df = pd.read_csv(PHASE_FILE) if PHASE_FILE.exists() else pd.DataFrame()

    risk_df.columns = [c.strip() for c in risk_df.columns]
    if not phase_df.empty:
        phase_df.columns = [c.strip() for c in phase_df.columns]

    for col in ["Meantha", "Variance", "StdDev", "Mintha", "Maxtha", "ObsCount", "NeutralMean", "RiskPct"]:
        if col in risk_df.columns:
            risk_df[col] = pd.to_numeric(risk_df[col], errors="coerce")

    for col in ["Country", "Crop", "Phase"]:
        if col in risk_df.columns:
            risk_df[col] = risk_df[col].astype(str).str.strip()

    return risk_df, phase_df

risk_df, phase_df = load_data()

st.title("ENSO Agricultural Risk Dashboard")
st.caption("FAOSTAT yield risk report by ENSO phase")

if risk_df.empty:
    st.error("risk_report.csv is empty or missing.")
    st.stop()

with st.sidebar:
    st.header("Filters")

    countries = sorted(risk_df["Country"].dropna().unique().tolist())
    crops = sorted(risk_df["Crop"].dropna().unique().tolist())
    phases = sorted(risk_df["Phase"].dropna().unique().tolist())

    selected_countries = st.multiselect("Country", countries, default=[])
    selected_crops = st.multiselect("Crop", crops, default=[])
    selected_phases = st.multiselect("Phase", phases, default=phases)
    min_obs = st.slider("Minimum ObsCount", min_value=1, max_value=int(risk_df["ObsCount"].fillna(1).max()), value=1)

filtered = risk_df.copy()

if selected_countries:
    filtered = filtered[filtered["Country"].isin(selected_countries)]

if selected_crops:
    filtered = filtered[filtered["Crop"].isin(selected_crops)]

if selected_phases:
    filtered = filtered[filtered["Phase"].isin(selected_phases)]

filtered = filtered[filtered["ObsCount"].fillna(0) >= min_obs]

st.subheader("Overview")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", f"{len(filtered):,}")
c2.metric("Countries", f"{filtered['Country'].nunique():,}")
c3.metric("Crops", f"{filtered['Crop'].nunique():,}")
c4.metric("Avg RiskPct", f"{filtered['RiskPct'].mean():.2f}%" if not filtered.empty else "N/A")

tab1, tab2, tab3 = st.tabs(["Risk table", "Charts", "Phase summary"])

with tab1:
    st.subheader("Risk report")
    show_cols = [
        "Country", "Crop", "Phase", "Meantha", "Variance", "StdDev",
        "Mintha", "Maxtha", "ObsCount", "NeutralMean", "RiskPct"
    ]

    available_cols = [c for c in show_cols if c in filtered.columns]
    display_df = filtered[available_cols].sort_values(["Country", "Crop", "Phase"])

    st.dataframe(display_df, use_container_width=True, height=500)

    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered risk report",
        data=csv,
        file_name="filtered_risk_report.csv",
        mime="text/csv"
    )

with tab2:
    st.subheader("Charts")

    if filtered.empty:
        st.warning("No data available for selected filters.")
    else:
        chart_metric = st.selectbox(
            "Select metric",
            ["Meantha", "RiskPct", "StdDev", "Variance"]
        )

        top_n = st.slider("Top rows for chart", min_value=5, max_value=50, value=15)

        chart_df = filtered.copy()

        if chart_metric == "RiskPct":
            chart_df = chart_df.sort_values(chart_metric, ascending=False)
        else:
            chart_df = chart_df.sort_values(chart_metric, ascending=False)

        chart_df = chart_df.head(top_n).copy()
        chart_df["Label"] = chart_df["Country"] + " | " + chart_df["Crop"] + " | " + chart_df["Phase"]
        chart_df = chart_df.set_index("Label")

        st.bar_chart(chart_df[chart_metric])

        if {"Country", "Crop"}.issubset(filtered.columns):
            pivot_df = filtered.pivot_table(
                index=["Country", "Crop"],
                columns="Phase",
                values="Meantha",
                aggfunc="mean"
            ).reset_index()

            st.subheader("Mean yield by phase")
            st.dataframe(pivot_df, use_container_width=True, height=400)

with tab3:
    st.subheader("Phase summary")

    if not phase_df.empty:
        st.dataframe(phase_df, use_container_width=True)
        if {"Phase", "MeanYield"}.issubset(phase_df.columns):
            st.bar_chart(phase_df.set_index("Phase")["MeanYield"])
    else:
        st.info("phase_summary.csv not found.")

st.subheader("Quick search")

with st.form("search_form"):
    country_in = st.text_input("Country contains")
    crop_in = st.text_input("Crop contains")
    submitted = st.form_submit_button("Search")

if submitted:
    search_df = risk_df.copy()

    if country_in.strip():
        search_df = search_df[search_df["Country"].str.contains(country_in.strip(), case=False, na=False)]

    if crop_in.strip():
        search_df = search_df[search_df["Crop"].str.contains(crop_in.strip(), case=False, na=False)]

    st.dataframe(search_df, use_container_width=True, height=400)
