from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="ENSO Agricultural Risk Dashboard", layout="wide")

BASE_DIR = Path(__file__).resolve().parent
RISK_FILE = BASE_DIR / "data" / "output" / "risk_report.csv"
PHASE_FILE = BASE_DIR / "data" / "output" / "phase_summary.csv"


@st.cache_data
def load_data():
    if not RISK_FILE.exists():
        raise FileNotFoundError(
            f"Missing file: {RISK_FILE}\n"
            f"Make sure risk_report.csv is committed to GitHub at data/output/risk_report.csv"
        )

    risk_df = pd.read_csv(RISK_FILE)

    if PHASE_FILE.exists():
        phase_df = pd.read_csv(PHASE_FILE)
    else:
        phase_df = pd.DataFrame(columns=["Phase", "MeanYield", "MedianYield", "ObsCount"])

    risk_df.columns = [c.strip() for c in risk_df.columns]
    phase_df.columns = [c.strip() for c in phase_df.columns]

    numeric_cols = [
        "Meantha", "Variance", "StdDev", "Mintha", "Maxtha",
        "ObsCount", "NeutralMean", "RiskPct"
    ]
    for col in numeric_cols:
        if col in risk_df.columns:
            risk_df[col] = pd.to_numeric(risk_df[col], errors="coerce")

    for col in ["Country", "Crop", "Phase"]:
        if col in risk_df.columns:
            risk_df[col] = risk_df[col].astype(str).str.strip()

    if "Phase" in phase_df.columns:
        phase_df["Phase"] = phase_df["Phase"].astype(str).str.strip()

    return risk_df, phase_df


try:
    risk_df, phase_df = load_data()
except Exception as e:
    st.error("App startup failed.")
    st.exception(e)
    st.stop()

st.title("ENSO Agricultural Risk Dashboard")
st.caption("FAOSTAT yield-based risk report by ENSO phase")

with st.sidebar:
    st.header("Filters")

    countries = sorted(risk_df["Country"].dropna().unique().tolist()) if "Country" in risk_df.columns else []
    crops = sorted(risk_df["Crop"].dropna().unique().tolist()) if "Crop" in risk_df.columns else []
    phases = sorted(risk_df["Phase"].dropna().unique().tolist()) if "Phase" in risk_df.columns else []

    selected_countries = st.multiselect("Country", countries)
    selected_crops = st.multiselect("Crop", crops)
    selected_phases = st.multiselect("Phase", phases, default=phases)

    max_obs = int(risk_df["ObsCount"].fillna(1).max()) if "ObsCount" in risk_df.columns and not risk_df.empty else 1
    min_obs = st.slider("Minimum ObsCount", min_value=1, max_value=max_obs, value=1)

filtered = risk_df.copy()

if selected_countries:
    filtered = filtered[filtered["Country"].isin(selected_countries)]

if selected_crops:
    filtered = filtered[filtered["Crop"].isin(selected_crops)]

if selected_phases:
    filtered = filtered[filtered["Phase"].isin(selected_phases)]

if "ObsCount" in filtered.columns:
    filtered = filtered[filtered["ObsCount"].fillna(0) >= min_obs]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", f"{len(filtered):,}")
c2.metric("Countries", f"{filtered['Country'].nunique():,}" if "Country" in filtered.columns else "0")
c3.metric("Crops", f"{filtered['Crop'].nunique():,}" if "Crop" in filtered.columns else "0")
c4.metric(
    "Average RiskPct",
    f"{filtered['RiskPct'].mean():.2f}%" if "RiskPct" in filtered.columns and not filtered.empty else "N/A"
)

tab1, tab2, tab3 = st.tabs(["Risk Table", "Charts", "Phase Summary"])

with tab1:
    st.subheader("Risk Report")

    show_cols = [
        "Country", "Crop", "Phase", "Meantha", "Variance", "StdDev",
        "Mintha", "Maxtha", "ObsCount", "NeutralMean", "RiskPct"
    ]
    available_cols = [c for c in show_cols if c in filtered.columns]
    display_df = filtered[available_cols].sort_values(
        by=[c for c in ["Country", "Crop", "Phase"] if c in available_cols]
    )

    st.dataframe(display_df, use_container_width=True, height=500)

    csv_bytes = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered risk report",
        data=csv_bytes,
        file_name="filtered_risk_report.csv",
        mime="text/csv"
    )

with tab2:
    st.subheader("Charts")

    if filtered.empty:
        st.warning("No data available for the selected filters.")
    else:
        metric_options = [c for c in ["Meantha", "RiskPct", "StdDev", "Variance"] if c in filtered.columns]
        chart_metric = st.selectbox("Select metric", metric_options)

        top_n = st.slider("Top rows for chart", min_value=5, max_value=50, value=15)

        chart_df = filtered.copy().sort_values(chart_metric, ascending=False).head(top_n)
        chart_df["Label"] = (
            chart_df["Country"].astype(str) + " | " +
            chart_df["Crop"].astype(str) + " | " +
            chart_df["Phase"].astype(str)
        )
        chart_df = chart_df.set_index("Label")

        st.bar_chart(chart_df[chart_metric])

        if all(col in filtered.columns for col in ["Country", "Crop", "Phase", "Meantha"]):
            pivot_df = filtered.pivot_table(
                index=["Country", "Crop"],
                columns="Phase",
                values="Meantha",
                aggfunc="mean"
            ).reset_index()

            st.subheader("Mean Yield by Phase")
            st.dataframe(pivot_df, use_container_width=True, height=400)

with tab3:
    st.subheader("Phase Summary")

    if phase_df.empty:
        st.info("phase_summary.csv not found.")
    else:
        st.dataframe(phase_df, use_container_width=True)

        if "Phase" in phase_df.columns and "MeanYield" in phase_df.columns:
            st.bar_chart(phase_df.set_index("Phase")["MeanYield"])

st.subheader("Quick Search")

with st.form("quick_search_form"):
    country_text = st.text_input("Country contains")
    crop_text = st.text_input("Crop contains")
    submitted = st.form_submit_button("Search")

if submitted:
    search_df = risk_df.copy()

    if country_text.strip() and "Country" in search_df.columns:
        search_df = search_df[
            search_df["Country"].str.contains(country_text.strip(), case=False, na=False)
        ]

    if crop_text.strip() and "Crop" in search_df.columns:
        search_df = search_df[
            search_df["Crop"].str.contains(crop_text.strip(), case=False, na=False)
        ]

    st.dataframe(search_df, use_container_width=True, height=400)
