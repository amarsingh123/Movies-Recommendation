import os
import requests
import streamlit as st

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="ReelDeal", page_icon="🎬", layout="wide")

DEFAULT_API = os.getenv("API_BASE", "http://127.0.0.1:8001")
TMDB_IMG = "https://image.tmdb.org/t/p/w500"
PLACEHOLDER = "https://placehold.co/500x750/1f2433/8b93a7?text=No+Poster"

CATEGORIES = {
    "🔥 Trending": "trending",
    "⭐ Popular": "popular",
    "🏆 Top Rated": "top_rated",
    "🎟️ Upcoming": "upcoming",
    "🎞️ Now Playing": "now_playing",
}

SORT_OPTIONS = [
    "Default (API order)",
    "Rating: high to low",
    "Newest first",
    "Oldest first",
    "Title: A to Z",
]

MENU = ["🏠 Home", "🔍 Search", "🎯 Find Similar", "ℹ️ About"]

# =========================
# STYLE
# =========================
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; max-width: 1400px;}
    .hero {
        background: linear-gradient(120deg, #e50914 0%, #7a1fa2 55%, #1b2a6b 100%);
        padding: 1.6rem 2rem; border-radius: 18px; margin-bottom: 1.2rem; color: white;
    }
    .hero h1 {margin: 0; font-size: 2.2rem;}
    .hero p {margin: .3rem 0 0 0; opacity: .9;}
    .badge {
        display: inline-block; padding: 2px 10px; margin: 2px 4px 2px 0;
        border-radius: 999px; background: #262b3d; color: #e6e9f2; font-size: .8rem;
    }
    .rate {color: #ffc107; font-weight: 600;}
    .movie-title {font-weight: 600; line-height: 1.2; min-height: 2.4em; margin-top: .3rem;}
    div[data-testid="stImage"] img {border-radius: 12px; transition: transform .2s ease;}
    div[data-testid="stImage"] img:hover {transform: scale(1.03);}
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================
# VERSION-SAFE WIDGET HELPERS
# (Streamlit renamed these arguments across releases)
# =========================
def simage(url: str):
    for kw in (
        {"use_container_width": True},
        {"use_column_width": True},
        {"width": "stretch"},
    ):
        try:
            return st.image(url, **kw)
        except TypeError:
            continue
    return st.image(url)


def sbutton(label: str, **kwargs):
    for kw in ({"use_container_width": True}, {"width": "stretch"}):
        try:
            return st.button(label, **kw, **kwargs)
        except TypeError:
            continue
    return st.button(label, **kwargs)


# =========================
# STATE
# =========================
DEFAULTS = {
    "selected_id": None,
    "f_min_rating": 0.0,
    "f_years": (1950, 2027),
    "f_sort": SORT_OPTIONS[0],
    "f_limit": 24,
    "f_cols": 5,
    "f_text": "",
    "f_posters": False,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def open_movie(tmdb_id: int):
    st.session_state.selected_id = tmdb_id


def close_movie():
    st.session_state.selected_id = None


def reset_filters():
    for k, v in DEFAULTS.items():
        if k.startswith("f_"):
            st.session_state[k] = v


# =========================
# API
# =========================
API_BASE = DEFAULT_API  # overwritten from the sidebar below


@st.cache_data(show_spinner=False, ttl=300)
def _fetch(base: str, path: str, params: tuple):
    r = requests.get(f"{base}{path}", params=dict(params), timeout=60)
    r.raise_for_status()
    return r.json()


def api_get(path: str, **params):
    try:
        return _fetch(API_BASE, path, tuple(sorted(params.items())))
    except requests.HTTPError as e:
        resp = e.response
        code = resp.status_code if resp is not None else "?"
        st.error(f"API returned {code} for `{path}`")
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text if resp is not None else ""
        if detail:
            st.caption(f"Server says: {str(detail)[:300]}")
    except requests.RequestException:
        st.error(f"Cannot reach the API at {API_BASE}. Is the FastAPI server running?")
    return None


def to_card(m: dict) -> dict:
    """Normalise raw TMDB search results into the API's card shape."""
    poster = m.get("poster_path")
    return {
        "tmdb_id": m.get("id"),
        "title": m.get("title") or m.get("name") or "",
        "poster_url": f"{TMDB_IMG}{poster}" if poster else None,
        "release_date": m.get("release_date"),
        "vote_average": m.get("vote_average"),
    }


# =========================
# FILTERS + GRID
# =========================
def year_of(card: dict):
    d = card.get("release_date") or ""
    return int(d[:4]) if len(d) >= 4 and d[:4].isdigit() else None


def apply_filters(cards: list) -> list:
    """Returns ALL cards that pass the filters, sorted. (Max-results is applied later.)"""
    s = st.session_state
    lo, hi = s.f_years
    text = s.f_text.strip().lower()
    out = []
    for c in cards:
        if (c.get("vote_average") or 0) < s.f_min_rating:
            continue
        y = year_of(c)
        if y is not None and not (lo <= y <= hi):
            continue
        if text and text not in (c.get("title") or "").lower():
            continue
        if s.f_posters and not c.get("poster_url"):
            continue
        out.append(c)

    if s.f_sort == "Rating: high to low":
        out.sort(key=lambda c: c.get("vote_average") or 0, reverse=True)
    elif s.f_sort == "Newest first":
        out.sort(key=lambda c: c.get("release_date") or "", reverse=True)
    elif s.f_sort == "Oldest first":
        out.sort(key=lambda c: c.get("release_date") or "9999")
    elif s.f_sort == "Title: A to Z":
        out.sort(key=lambda c: (c.get("title") or "").lower())
    return out


def render_grid(cards: list, prefix: str):
    total = len(cards)
    matched = apply_filters(cards)
    shown = matched[: st.session_state.f_limit]

    if not shown:
        st.info(
            f"No movies match the current filters ({total} fetched, all filtered out). "
            "Loosen them in the sidebar or press Reset filters."
        )
        return

    hidden = total - len(matched)
    note = f" · {hidden} hidden by filters" if hidden else ""
    st.caption(f"Showing {len(shown)} of {total} movies{note}")

    cols_n = st.session_state.f_cols
    for row_start in range(0, len(shown), cols_n):
        cols = st.columns(cols_n)
        for col, card in zip(cols, shown[row_start : row_start + cols_n]):
            with col:
                simage(card.get("poster_url") or PLACEHOLDER)
                st.markdown(
                    f"<div class='movie-title'>{card['title']}</div>", unsafe_allow_html=True
                )
                rating = card.get("vote_average")
                year = year_of(card) or "—"
                rate = f"⭐ {rating:.1f}" if rating else "⭐ —"
                st.markdown(
                    f"<span class='rate'>{rate}</span> &nbsp;·&nbsp; {year}",
                    unsafe_allow_html=True,
                )
                sbutton(
                    "Details",
                    key=f"{prefix}_{card['tmdb_id']}_{row_start}",
                    on_click=open_movie,
                    args=(card["tmdb_id"],),
                )


# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown("## 🎬 ReelDeal")
    # Changing the menu always closes any open movie page
    page = st.radio("Menu", MENU, key="page", on_change=close_movie, label_visibility="collapsed")
    st.divider()

    st.markdown("### 🎛️ Filters")
    st.slider("Minimum rating", 0.0, 10.0, step=0.5, key="f_min_rating")
    st.slider("Release year", 1950, 2027, key="f_years")
    st.text_input("Title contains", key="f_text", placeholder="e.g. war, love, batman")
    st.selectbox("Sort by", SORT_OPTIONS, key="f_sort")
    st.slider("Max results", 6, 50, step=2, key="f_limit")
    st.select_slider("Grid columns", options=[3, 4, 5, 6], key="f_cols")
    st.checkbox("Only movies with posters", key="f_posters")
    sbutton("↺ Reset filters", on_click=reset_filters)

    st.divider()
    API_BASE = st.text_input("API base URL", value=DEFAULT_API).rstrip("/")

# =========================
# HERO
# =========================
st.markdown(
    """
    <div class="hero">
      <h1>🎬 ReelDeal</h1>
      <p>Discover trending movies, search any title, and get smart recommendations.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================
# DETAIL VIEW
# =========================
def show_details(tmdb_id: int):
    st.button("← Back", on_click=close_movie)
    d = api_get(f"/movie/id/{tmdb_id}")
    if not d:
        return

    if d.get("backdrop_url"):
        simage(d["backdrop_url"])

    left, right = st.columns([1, 2.2], gap="large")
    with left:
        simage(d.get("poster_url") or PLACEHOLDER)
    with right:
        year = (d.get("release_date") or "")[:4]
        st.markdown(f"## {d['title']} {f'({year})' if year else ''}")
        genres = "".join(f"<span class='badge'>{g['name']}</span>" for g in d.get("genres", []))
        st.markdown(genres, unsafe_allow_html=True)
        st.markdown("#### Overview")
        st.write(d.get("overview") or "No overview available.")

    st.divider()
    tab_tfidf, tab_genre = st.tabs(["🧠 Similar by content (TF-IDF)", "🎭 More from this genre"])

    with tab_tfidf:
        bundle = api_get("/movie/search", query=d["title"], tfidf_top_n=18)
        if bundle is not None:  # on failure, api_get already showed the real error
            recs = bundle.get("tfidf_recommendations", [])
            cards = [r["tmdb"] for r in recs if r.get("tmdb")]
            no_poster = [r["title"] for r in recs if not r.get("tmdb")]
            if cards:
                render_grid(cards, "tf")
                if no_poster:
                    st.caption("Also similar (no TMDB match found): " + ", ".join(no_poster))
            elif recs:
                st.info("Similar titles found, but TMDB posters could not be matched:")
                st.write(", ".join(no_poster))
            else:
                st.info(
                    "No content-based matches for this movie. Try the 'More from this genre' tab."
                )

    with tab_genre:
        cards = api_get("/recommend/genre", tmdb_id=tmdb_id, limit=30) or []
        render_grid(cards, "gn")


# =========================
# PAGES
# =========================
if st.session_state.selected_id:
    show_details(st.session_state.selected_id)

elif page == "🏠 Home":
    tabs = st.tabs(list(CATEGORIES.keys()))
    for tab, (label, cat) in zip(tabs, CATEGORIES.items()):
        with tab:
            cards = api_get("/home", category=cat, limit=50) or []
            render_grid(cards, f"home_{cat}")

elif page == "🔍 Search":
    q = st.text_input("Search movies", placeholder="Type a movie name…")
    if q:
        c1, c2 = st.columns([1, 5])
        page_no = c1.number_input("Page", 1, 10, 1)
        data = api_get("/tmdb/search", query=q, page=int(page_no))
        results = (data or {}).get("results", [])
        cards = [to_card(m) for m in results if m.get("id")]
        c2.caption(f"{(data or {}).get('total_results', 0)} total matches on TMDB")
        render_grid(cards, "search")
    else:
        st.info("Start typing to search for a movie.")

elif page == "🎯 Find Similar":
    st.subheader("Pick a movie and get recommendations")
    q = st.text_input("Movie name", placeholder="e.g. Inception")
    if q:
        data = api_get("/tmdb/search", query=q)
        results = (data or {}).get("results", [])[:10]
        if not results:
            st.warning("No movies found.")
        else:
            options = {
                f"{m.get('title')} ({(m.get('release_date') or '')[:4] or '—'})": m["id"]
                for m in results
            }
            choice = st.selectbox("Select the exact movie", list(options.keys()))
            st.button(
                "Get recommendations 🎯",
                on_click=open_movie,
                args=(options[choice],),
                type="primary",
            )

else:
    st.subheader("About")
    st.markdown(
        """
        **ReelDeal** is a Streamlit frontend for your FastAPI movie recommendation service.

        - **Browse** has one tab per TMDB category.
        - **Search** queries TMDB with pagination.
        - **Find Similar** opens a movie with content-based (TF-IDF) and same-genre recommendations.
        - Sidebar filters (rating, year, title text, sort, poster-only, grid size) apply to every grid.

        Filters run on the data the API returns, so a very strict filter on a short list can
        leave few or no results.
        """
    )