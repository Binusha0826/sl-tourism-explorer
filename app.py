import calendar
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Sri Lanka Tourism & Weather Explorer", layout="wide")

st.markdown(
    """
<style>
.stApp {
    background: linear-gradient(160deg, #0f766e 0%, #14b8a6 30%, #7dd3c0 60%, #fde68a 100%);
    background-attachment: fixed;
}
.stApp::before {
    content: "";
    position: fixed;
    left: 0; bottom: 0;
    width: 100%; height: 240px;
    background: url("data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 1440 320%27 preserveAspectRatio=%27none%27%3E%3Cpath fill=%27%23ffffff%27 fill-opacity=%270.28%27 d=%27M0,224L60,213C120,203,240,181,360,181C480,181,600,203,720,208C840,213,960,203,1080,181C1200,160,1320,128,1380,112L1440,96L1440,320L0,320Z%27/%3E%3C/svg%3E") no-repeat bottom / 100% 100%;
    pointer-events: none;
    z-index: 0;
}
[data-testid="stHeader"] { background: transparent; }
.block-container {
    position: relative;
    z-index: 1;
    max-width: 1300px;
    margin-top: 1.5rem;
    padding: 2rem 2.5rem 3rem 2.5rem !important;
    background: transparent;
    border-radius: 22px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
}
.block-container::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    border-radius: 22px;
    background: rgba(8, 20, 24, 0.80);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
}
h1 { color: #ffffff; letter-spacing: -0.5px; text-shadow: 0 2px 10px rgba(0,0,0,0.5); }
h2, h3 { color: #f1f5f9; text-shadow: 0 1px 8px rgba(0,0,0,0.5); }
[data-testid="stCaptionContainer"] { color: #cbd5e1; }
</style>
""",
    unsafe_allow_html=True,
)

# Optional rain video background: put a short mp4 at static/rain.mp4
VIDEO_PATH = Path(__file__).parent / "static" / "rain.mp4"
GLASS_OPACITY = 0.45  # 0 = fully transparent, 1 = solid dark. Tweak this!
if VIDEO_PATH.exists():
    st.markdown(
        """
<style>
.bg-video {
    position: fixed;
    top: 0; left: 0;
    width: 100vw; height: 100vh;
    object-fit: cover;
    z-index: -2;
    pointer-events: none;
}
.stApp::before { display: none; }
.block-container::before {
    background: rgba(8, 20, 24, __OPACITY__);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
}
</style>
<video class="bg-video" autoplay loop muted playsinline>
  <source src="app/static/rain.mp4" type="video/mp4">
</video>
""".replace("__OPACITY__", str(GLASS_OPACITY)),
        unsafe_allow_html=True,
    )

PLACES = {
    "Sigiriya": (7.957, 80.760),
    "Ella": (6.867, 81.046),
    "Galle": (6.053, 80.221),
    "Mirissa": (5.948, 80.457),
    "Nuwara Eliya": (6.949, 80.789),
    "Kandy": (7.291, 80.636),
    "Arugam Bay": (6.840, 81.836),
    "Jaffna": (9.661, 80.026),
    "Yala": (6.372, 81.516),
    "Trincomalee": (8.587, 81.215),
}


@st.cache_data(ttl=3600)
def get_forecast(name: str, lat: float, lon: float) -> pd.DataFrame:
    """Fetch 7-day forecast from Open-Meteo (no API key needed)."""
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "Asia/Colombo",
            "forecast_days": 7,
        },
        timeout=10,
    )
    r.raise_for_status()
    df = pd.DataFrame(r.json()["daily"])
    df.columns = ["date", "tmax", "tmin", "rain_mm"]
    df["place"] = name
    df["lat"], df["lon"] = lat, lon
    return df


@st.cache_data(ttl=86400)
def get_history(name: str, lat: float, lon: float) -> pd.DataFrame:
    """Average monthly rain and max temp for 2023-2025 (Open-Meteo archive)."""
    r = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": "2023-01-01",
            "end_date": "2025-12-31",
            "daily": "temperature_2m_max,precipitation_sum",
            "timezone": "Asia/Colombo",
        },
        timeout=30,
    )
    r.raise_for_status()
    df = pd.DataFrame(r.json()["daily"])
    df.columns = ["date", "tmax", "rain_mm"]
    df["date"] = pd.to_datetime(df["date"])
    df["year"], df["month"] = df["date"].dt.year, df["date"].dt.month
    monthly = df.groupby(["year", "month"], as_index=False).agg(
        rain=("rain_mm", "sum"), tmax=("tmax", "mean")
    )
    out = monthly.groupby("month", as_index=False).agg(
        avg_rain_mm=("rain", "mean"), avg_max_temp=("tmax", "mean")
    ).round(1)
    out["month_name"] = out["month"].apply(lambda m: calendar.month_abbr[m])
    return out


def travel_score(row) -> float:
    """Simple 0-100 score: less rain and ~29C is better. Tweak this!"""
    score = 100 - row.rain_mm * 4 - abs(row.tmax - 29) * 3
    return max(0, min(100, score))


st.title("🇱🇰 Sri Lanka Tourism & Weather Explorer")
st.caption("Data: Open-Meteo API | Built with Streamlit, Pandas, Plotly")

chosen = st.multiselect("Places", list(PLACES), default=list(PLACES)[:5])
if not chosen:
    st.info("Select at least one place.")
    st.stop()

try:
    df = pd.concat([get_forecast(p, *PLACES[p]) for p in chosen])
except requests.RequestException as e:
    st.error(f"Could not fetch weather data: {e}")
    st.stop()

df["score"] = df.apply(travel_score, axis=1)
summary = (
    df.groupby(["place", "lat", "lon"], as_index=False)
    .agg(avg_max_temp=("tmax", "mean"), total_rain=("rain_mm", "sum"), score=("score", "mean"))
    .round(1)
)

left, right = st.columns([3, 2])
with left:
    fig = px.scatter_geo(
        summary, lat="lat", lon="lon", size="score", color="score",
        hover_name="place", hover_data=["avg_max_temp", "total_rain"],
        color_continuous_scale="RdYlGn", height=480,
    )
    fig.update_geos(
        lonaxis_range=[79.4, 82.1],
        lataxis_range=[5.8, 9.95],
        resolution=50,
        showcountries=True,
        showland=True,
        landcolor="#2a4d43",
        showocean=True,
        oceancolor="#0c2f3a",
        coastlinecolor="#9ad1c5",
        countrycolor="#9ad1c5",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Best places this week")
    table = summary.sort_values("score", ascending=False)[["place", "score", "avg_max_temp", "total_rain"]]
    table = table.rename(columns={
        "place": "Place",
        "score": "Travel score",
        "avg_max_temp": "Avg max temp (°C)",
        "total_rain": "Total rain (7 days, mm)",
    })
    st.dataframe(table, hide_index=True, use_container_width=True)

st.subheader("Daily comparison")
metric = st.radio("Metric", ["tmax", "rain_mm", "score"], horizontal=True)
st.plotly_chart(px.line(df, x="date", y=metric, color="place", markers=True), use_container_width=True)


st.subheader("Best month to visit")
place = st.selectbox("Place", chosen)
try:
    hist_df = get_history(place, *PLACES[place])
    driest = hist_df.loc[hist_df["avg_rain_mm"].idxmin()]
    st.write(f"Driest month in {place}: **{driest['month_name']}** ({driest['avg_rain_mm']} mm average rain)")
    st.plotly_chart(
        px.bar(hist_df, x="month_name", y="avg_rain_mm",
               labels={"month_name": "Month", "avg_rain_mm": "Avg rain (mm)"}),
        use_container_width=True,
    )
except requests.RequestException as e:
    st.error(f"Could not fetch historical data: {e}")