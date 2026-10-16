import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Sri Lanka Tourism & Weather Explorer", layout="wide")

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
    fig = px.scatter_mapbox(
        summary, lat="lat", lon="lon", size="score", color="score",
        hover_name="place", hover_data=["avg_max_temp", "total_rain"],
        color_continuous_scale="RdYlGn", zoom=6.3, height=480,
    )
    fig.update_layout(mapbox_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Best places this week")
    st.dataframe(summary.sort_values("score", ascending=False)[["place", "score", "avg_max_temp", "total_rain"]],
                 hide_index=True, use_container_width=True)

st.subheader("Daily comparison")
metric = st.radio("Metric", ["tmax", "rain_mm", "score"], horizontal=True)
st.plotly_chart(px.line(df, x="date", y=metric, color="place", markers=True), use_container_width=True)
