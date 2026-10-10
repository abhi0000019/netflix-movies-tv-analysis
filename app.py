import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="Netflix Content Analysis", page_icon="🎬", layout="wide")

st.title("🎬 Netflix Movies & TV Shows Analysis")
st.caption("Interactive prototype for exploring the Netflix titles dataset.")

@st.cache_data
def load_csv(file_bytes=None):
    if file_bytes is not None:
        from io import BytesIO
        return pd.read_csv(BytesIO(file_bytes))
    local_file = Path(__file__).parent / "netflix_titles.csv"
    if local_file.exists():
        return pd.read_csv(local_file)
    return None

uploaded = st.sidebar.file_uploader("Upload netflix_titles.csv", type=["csv"])
try:
    df = load_csv(uploaded.getvalue() if uploaded else None)
except Exception as e:
    st.error(f"Could not read the CSV file: {e}")
    st.stop()

if df is None:
    st.info("To start, upload `netflix_titles.csv` in the sidebar, or place it in the same folder as `app.py`.")
    st.markdown("""
    **Dataset source:** [Netflix Movies and TV Shows on Kaggle](https://www.kaggle.com/datasets/shivamb/netflix-shows)

    **How to run**
    1. Download `netflix_titles.csv` from Kaggle.
    2. Put it beside `app.py`, or upload it using the sidebar.
    3. Run `python -m streamlit run app.py` in your terminal.
    """)
    st.stop()

# Standardize column names and handle optional columns
df.columns = [str(c).strip() for c in df.columns]
expected = ["show_id", "type", "title", "director", "cast", "country", "date_added",
            "release_year", "rating", "duration", "listed_in", "description"]
for col in expected:
    if col not in df.columns:
        df[col] = pd.NA

df["type"] = df["type"].fillna("Unknown").astype(str).str.strip()
df["title"] = df["title"].fillna("Untitled").astype(str)
df["release_year"] = pd.to_numeric(df["release_year"], errors="coerce")
df["date_added"] = pd.to_datetime(df["date_added"], errors="coerce")
df["listed_in"] = df["listed_in"].fillna("Unknown").astype(str)
df["country"] = df["country"].fillna("Unknown").astype(str)
df["rating"] = df["rating"].fillna("Not Rated").astype(str)
df["duration"] = df["duration"].fillna("").astype(str)

# Sidebar filters
st.sidebar.header("Filter titles")
types = sorted(df["type"].dropna().unique().tolist())
selected_types = st.sidebar.multiselect("Content type", types, default=types)
min_year = int(df["release_year"].min()) if df["release_year"].notna().any() else 1900
max_year = int(df["release_year"].max()) if df["release_year"].notna().any() else 2026
if min_year > max_year:
    min_year, max_year = max_year, min_year
year_range = st.sidebar.slider("Release year", min_value=min_year, max_value=max_year,
                               value=(min_year, max_year))
search_text = st.sidebar.text_input("Search title", placeholder="e.g. Stranger Things")

filtered = df[df["type"].isin(selected_types)].copy()
if filtered["release_year"].notna().any():
    filtered = filtered[
        filtered["release_year"].isna() |
        filtered["release_year"].between(year_range[0], year_range[1])
    ]
if search_text.strip():
    filtered = filtered[filtered["title"].str.contains(search_text.strip(), case=False, na=False)]

# KPI row
total = len(filtered)
movies = int((filtered["type"].str.lower() == "movie").sum())
shows = int((filtered["type"].str.lower() == "tv show").sum())
countries_count = filtered["country"].replace("Unknown", pd.NA).dropna().str.split(",").explode().str.strip().nunique()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Titles in selection", f"{total:,}")
k2.metric("Movies", f"{movies:,}")
k3.metric("TV Shows", f"{shows:,}")
k4.metric("Countries represented", f"{countries_count:,}")

if filtered.empty:
    st.warning("No titles match the selected filters. Change the filters and try again.")
    st.stop()

left, right = st.columns(2)
with left:
    type_counts = filtered["type"].value_counts().rename_axis("Content Type").reset_index(name="Titles")
    fig = px.bar(type_counts, x="Content Type", y="Titles", title="Movies vs TV Shows",
                 color="Content Type", text="Titles")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with right:
    years = filtered.dropna(subset=["release_year"]).groupby("release_year").size().reset_index(name="Titles")
    if not years.empty:
        years["release_year"] = years["release_year"].astype(int)
        fig = px.line(years, x="release_year", y="Titles", markers=True,
                      title="Titles by Release Year", labels={"release_year": "Release Year"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Release-year data is unavailable for this selection.")

def explode_labels(series):
    labels = series.fillna("Unknown").astype(str).str.split(",").explode().str.strip()
    labels = labels[(labels != "") & (labels.str.lower() != "unknown")]
    return labels

left2, right2 = st.columns(2)
with left2:
    genres = explode_labels(filtered["listed_in"]).value_counts().head(10).rename_axis("Genre").reset_index(name="Titles")
    if not genres.empty:
        fig = px.bar(genres.sort_values("Titles"), x="Titles", y="Genre", orientation="h",
                     title="Top 10 Listed Genres")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Genre data is unavailable.")

with right2:
    countries = explode_labels(filtered["country"]).value_counts().head(10).rename_axis("Country").reset_index(name="Titles")
    if not countries.empty:
        fig = px.bar(countries.sort_values("Titles"), x="Titles", y="Country", orientation="h",
                     title="Top 10 Countries")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Country data is unavailable.")

left3, right3 = st.columns(2)
with left3:
    ratings = filtered["rating"].value_counts().head(12).rename_axis("Rating").reset_index(name="Titles")
    fig = px.bar(ratings, x="Rating", y="Titles", title="Content Ratings")
    st.plotly_chart(fig, use_container_width=True)
with right3:
    movie_minutes = pd.to_numeric(filtered.loc[filtered["type"].str.lower() == "movie", "duration"]
                                  .str.extract(r"(\d+)")[0], errors="coerce").dropna()
    if not movie_minutes.empty:
        st.subheader("Movie Duration Summary")
        c1, c2, c3 = st.columns(3)
        c1.metric("Average (min)", f"{movie_minutes.mean():.1f}")
        c2.metric("Median (min)", f"{movie_minutes.median():.0f}")
        c3.metric("Longest (min)", f"{movie_minutes.max():.0f}")
        hist = pd.DataFrame({"Duration (minutes)": movie_minutes})
        fig = px.histogram(hist, x="Duration (minutes)", nbins=25, title="Distribution of Movie Durations")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No numeric movie-duration values found for this selection.")

st.subheader("Explore Titles")
display_cols = ["title", "type", "release_year", "director", "country", "rating", "duration", "listed_in"]
st.dataframe(filtered[display_cols].sort_values("title"), use_container_width=True, hide_index=True)

csv = filtered[display_cols].to_csv(index=False).encode("utf-8")
st.download_button("Download filtered results as CSV", data=csv,
                   file_name="netflix_filtered_titles.csv", mime="text/csv")

with st.expander("About this prototype"):
    st.write("This dashboard filters the selected dataset and calculates the displayed statistics from the data loaded at runtime. "
             "Missing values are labeled for display; genre and country labels are split on commas for frequency charts.")
    st.write("Dataset source: Kaggle — Netflix Movies and TV Shows (Shivam Bansal).")
