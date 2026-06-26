# ============================================================
# WORLD CUP 2026 PREDICTION APP
# Stack: Streamlit + Supabase/PostgreSQL
# Database input: Supabase via DATABASE_URL
# ============================================================

import os
import hmac
import hashlib
import base64
import mimetypes
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Engine
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import streamlit as st
import plotly.express as px
from streamlit_extras.stylable_container import stylable_container
import secrets
from streamlit_cookies_controller import CookieController


# ============================================================
# 1. CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = st.secrets["DATABASE_URL"]

APP_NAME = "World Cup 2026 Prediction Arena"
APP_SHORT_NAME = "WC 2026"
APP_TAGLINE = "Dự đoán tỉ số, tích điểm và leo bảng xếp hạng cùng bạn bè."
COOKIE_NAME = "wc_session_token"
SESSION_DAYS = 30

# ============================================================
# TODO LINK AREA
# ============================================================

APP_LOGO_URL = "data/static/app-logo.png"

HERO_BACKGROUND_URL = "data/static/hero-background.jpeg"

HERO_TROPHY_IMAGE_URL = "data/static/trophy-render.png"

SIDEBAR_DECORATION_URL = "data/static/sidebar.png"

FOOTER_PROJECT_URL = ""
# TODO LINK 5:
# Gắn link GitHub repo / portfolio / project page của bạn.
# Có thể để trống.
# FOOTER_PROJECT_URL = "https://github.com/yourname/worldcup-prediction-app"


def resolve_asset_src(asset_path: str) -> str:
    """
    Nhận link ảnh online hoặc đường dẫn ảnh local, rồi trả về src dùng được trong HTML/CSS.

    Cách dùng local khuyên dùng:
    - Đặt ảnh trong folder static/ cùng cấp với app.py
    - Ví dụ: static/app-logo.png

    Function này sẽ tự chuyển ảnh local thành base64 data URI, vì vậy bạn KHÔNG cần
    bắt buộc phải tạo .streamlit/config.toml để test giao diện local.
    """
    if not asset_path:
        return ""

    asset_path = str(asset_path).strip()

    if asset_path.startswith(("http://", "https://", "data:", "/app/static/")):
        return asset_path

    normalized_path = asset_path.replace("\\", "/")

    candidate_paths = []

    raw_path = Path(normalized_path)

    if raw_path.is_absolute():
        candidate_paths.append(raw_path)
    else:
        candidate_paths.append(BASE_DIR / raw_path)

        # Nếu trước đó bạn lỡ ghi data/static/..., app vẫn thử hiểu lại thành static/...
        if normalized_path.startswith("data/static/"):
            candidate_paths.append(BASE_DIR / normalized_path.replace("data/static/", "static/", 1))

        # Nếu notebook/app đang chạy trong folder data, ảnh thường nằm ở BASE_DIR/static/
        candidate_paths.append(BASE_DIR / "static" / raw_path.name)

    for candidate_path in candidate_paths:
        if candidate_path.exists() and candidate_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(candidate_path))
            mime_type = mime_type or "image/png"

            encoded = base64.b64encode(candidate_path.read_bytes()).decode("utf-8")
            return f"data:{mime_type};base64,{encoded}"

    # Fallback để dễ debug nếu file không tồn tại
    return asset_path


st.set_page_config(
    page_title=APP_NAME,
    page_icon="⚽",
    layout="wide"
)

cookie_controller = CookieController()


# ============================================================
# 2. THEME + UI HELPERS
# ============================================================

def inject_worldcup_theme():
    hero_background_src = resolve_asset_src(HERO_BACKGROUND_URL)

    if hero_background_src:
        hero_background_css = f"""
            background-image:
                linear-gradient(90deg, rgba(7, 17, 31, 0.96), rgba(11, 31, 58, 0.88), rgba(18, 60, 105, 0.70)),
                url("{hero_background_src}");
            background-size: cover;
            background-position: center;
        """
    else:
        hero_background_css = """
            background:
                radial-gradient(circle at 12% 18%, rgba(0, 180, 216, 0.32), transparent 24%),
                radial-gradient(circle at 82% 16%, rgba(245, 197, 66, 0.30), transparent 22%),
                linear-gradient(135deg, #07111F 0%, #0B1F3A 52%, #123C69 100%);
        """

    st.markdown(
        f"""
        <style>
        :root {{
            --wc-midnight: #07111F;
            --wc-deep-blue: #0B1F3A;
            --wc-royal-blue: #123C69;
            --wc-sky: #00B4D8;
            --wc-gold: #F5C542;
            --wc-red: #E63946;
            --wc-green: #16A34A;
            --wc-orange: #F59E0B;
            --wc-slate: #64748B;
            --wc-paper: #F8FAFC;
            --wc-card: rgba(255, 255, 255, 0.94);
            --wc-ink: #07111F;
            --wc-muted: #64748B;
        }}

        .stApp {{
            background:
                radial-gradient(circle at top left, rgba(0, 180, 216, 0.14), transparent 28%),
                radial-gradient(circle at top right, rgba(245, 197, 66, 0.18), transparent 24%),
                linear-gradient(180deg, #F8FAFC 0%, #EEF4FA 100%);
            color: var(--wc-ink);
        }}

        .block-container {{
            padding-top: 1.6rem;
            padding-bottom: 2.4rem;
            max-width: 1440px;
        }}

        section[data-testid="stSidebar"] {{
            background:
                radial-gradient(circle at 30% 15%, rgba(0, 180, 216, 0.20), transparent 24%),
                linear-gradient(180deg, #07111F 0%, #0B1F3A 66%, #04101F 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }}

        section[data-testid="stSidebar"] * {{
            color: #F8FAFC;
        }}

        section[data-testid="stSidebar"] .stRadio > div {{
            gap: 8px;
        }}

        section[data-testid="stSidebar"] label[data-baseweb="radio"] {{
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 10px 12px;
            margin-bottom: 6px;
        }}

        section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {{
            background: linear-gradient(90deg, rgba(245,197,66,0.28), rgba(0,180,216,0.14));
            border: 1px solid rgba(245,197,66,0.66);
        }}

        .wc-sidebar-brand {{
            padding: 18px 8px 22px 8px;
            margin-bottom: 12px;
        }}

        .wc-logo-row {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .wc-logo-fallback {{
            width: 54px;
            height: 54px;
            border-radius: 18px;
            background:
                radial-gradient(circle at 32% 28%, #F5C542 0%, #F5C542 22%, transparent 23%),
                linear-gradient(135deg, #123C69, #00B4D8);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 900;
            font-size: 15px;
            line-height: 1.05;
            box-shadow: 0 10px 24px rgba(0, 180, 216, 0.24);
        }}

        .wc-logo-img {{
            width: 58px;
            height: 58px;
            object-fit: contain;
            border-radius: 16px;
        }}

        .wc-brand-title {{
            font-weight: 900;
            font-size: 19px;
            letter-spacing: -0.02em;
            line-height: 1.05;
        }}

        .wc-brand-subtitle {{
            color: #CBD5E1;
            font-size: 12px;
            margin-top: 3px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}

        .wc-sidebar-footer {{
            margin-top: 36px;
            padding: 14px;
            border-radius: 18px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.10);
            color: #CBD5E1;
            font-size: 13px;
        }}

        .wc-sidebar-decoration {{
            width: 100%;
            border-radius: 18px;
            margin-top: 12px;
            opacity: 0.86;
        }}

        .wc-hero {{
            {hero_background_css}
            border-radius: 28px;
            padding: 30px 34px;
            color: white;
            margin-bottom: 22px;
            box-shadow: 0 20px 48px rgba(7, 17, 31, 0.22);
            border: 1px solid rgba(255,255,255,0.20);
            overflow: hidden;
            position: relative;
        }}

        .wc-hero::after {{
            content: "";
            position: absolute;
            right: -80px;
            bottom: -90px;
            width: 320px;
            height: 320px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(245,197,66,0.26), transparent 62%);
            pointer-events: none;
        }}

        .wc-hero-grid {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 24px;
            align-items: center;
            position: relative;
            z-index: 1;
        }}

        .wc-eyebrow {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 7px 12px;
            border-radius: 999px;
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.20);
            color: #E2E8F0;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 14px;
        }}

        .wc-hero-title {{
            font-size: clamp(34px, 4vw, 58px);
            font-weight: 950;
            letter-spacing: -0.055em;
            line-height: 0.95;
            margin-bottom: 12px;
        }}

        .wc-gold {{
            color: var(--wc-gold);
        }}

        .wc-hero-subtitle {{
            color: #CBD5E1;
            font-size: 17px;
            max-width: 760px;
            line-height: 1.6;
        }}

        .wc-hero-actions {{
            display: flex;
            gap: 10px;
            margin-top: 22px;
            flex-wrap: wrap;
        }}

        .wc-pill {{
            padding: 9px 13px;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.18);
            background: rgba(255,255,255,0.08);
            color: #E2E8F0;
            font-size: 13px;
            font-weight: 700;
        }}

        .wc-hero-orb {{
            width: 142px;
            height: 142px;
            border-radius: 36px;
            background:
                radial-gradient(circle at 35% 25%, #FFF7CC, #F5C542 38%, #B45309 100%);
            color: #07111F;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 950;
            font-size: 32px;
            box-shadow: 0 18px 38px rgba(245,197,66,0.24);
            transform: rotate(-6deg);
        }}

        .wc-hero-img {{
            width: 150px;
            max-height: 170px;
            object-fit: contain;
            filter: drop-shadow(0 16px 32px rgba(0,0,0,0.34));
        }}

        .wc-page-title {{
            margin: 10px 0 18px 0;
        }}

        .wc-page-title h2 {{
            font-size: 26px;
            margin-bottom: 4px;
            letter-spacing: -0.03em;
        }}

        .wc-page-title p {{
            color: var(--wc-muted);
            margin: 0;
        }}

        .wc-filter-shell {{
            background: rgba(255,255,255,0.90);
            border: 1px solid rgba(15,23,42,0.08);
            border-radius: 22px;
            padding: 18px;
            box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
            margin-bottom: 18px;
        }}

        .wc-section-card {{
            background: rgba(255,255,255,0.92);
            border: 1px solid rgba(15,23,42,0.08);
            border-radius: 22px;
            padding: 18px;
            box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
            margin-bottom: 18px;
        }}

        .wc-kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 14px;
            margin-bottom: 18px;
        }}

        .wc-kpi-tile {{
            border-radius: 20px;
            padding: 16px 17px;
            background: rgba(255,255,255,0.92);
            border: 1px solid rgba(15,23,42,0.08);
            box-shadow: 0 10px 26px rgba(15,23,42,0.06);
        }}

        .wc-kpi-label {{
            color: #64748B;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 8px;
        }}

        .wc-kpi-value {{
            font-size: 28px;
            font-weight: 950;
            color: #07111F;
            letter-spacing: -0.04em;
        }}

        .wc-kpi-note {{
            color: #94A3B8;
            font-size: 12px;
            margin-top: 3px;
        }}

        .wc-status-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 8px 0 18px 0;
        }}

        .wc-legend-item {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 11px;
            border-radius: 999px;
            background: rgba(255,255,255,0.82);
            border: 1px solid rgba(15,23,42,0.08);
            font-size: 13px;
            color: #334155;
            font-weight: 700;
        }}

        .wc-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }}

        div[data-testid="stMetric"] {{
            background: rgba(255,255,255,0.76);
            border: 1px solid rgba(15,23,42,0.08);
            padding: 12px 14px;
            border-radius: 16px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
        }}

        div[data-testid="stMetricLabel"] {{
            color: #64748B;
            font-weight: 800;
        }}

        div[data-testid="stMetricValue"] {{
            color: #07111F;
            font-weight: 950;
        }}

        .stButton > button {{
            border-radius: 999px;
            font-weight: 850;
            border: 1px solid rgba(18, 60, 105, 0.22);
            box-shadow: 0 7px 18px rgba(18, 60, 105, 0.12);
            transition: 0.18s ease;
        }}

        .stButton > button:hover {{
            border-color: #F5C542;
            color: #07111F;
            transform: translateY(-1px);
        }}

        /* Fix nút Đăng xuất trong sidebar: nền trắng nhưng chữ không bị trắng theo sidebar */
        section[data-testid="stSidebar"] .stButton > button {{
            background: rgba(255, 255, 255, 0.96) !important;
            color: #07111F !important;
            border: 1px solid rgba(245, 197, 66, 0.35) !important;
        }}

        section[data-testid="stSidebar"] .stButton > button * {{
            color: #07111F !important;
        }}

        section[data-testid="stSidebar"] .stButton > button:hover {{
            background: #F5C542 !important;
            color: #07111F !important;
            border-color: #F5C542 !important;
        }}

        .stSelectbox div[data-baseweb="select"] > div,
        .stNumberInput input,
        .stTextInput input {{
            border-radius: 13px;
        }}

        .wc-footer {{
            text-align: center;
            color: #64748B;
            font-size: 13px;
            margin-top: 28px;
            padding: 18px 0 10px 0;
        }}

        .wc-footer a {{
            color: #123C69;
            font-weight: 800;
            text-decoration: none;
        }}

        @media (max-width: 900px) {{
            .wc-hero-grid {{
                grid-template-columns: 1fr;
            }}

            .wc-hero-orb,
            .wc-hero-img {{
                display: none;
            }}

            .wc-kpi-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True
    )


inject_worldcup_theme()


def render_sidebar_brand():
    app_logo_src = resolve_asset_src(APP_LOGO_URL)

    if app_logo_src:
        logo_html = f'<img class="wc-logo-img" src="{app_logo_src}" alt="App logo">'
    else:
        logo_html = '<div class="wc-logo-fallback">WC<br>26</div>'

    st.markdown(
        f"""
        <div class="wc-sidebar-brand">
            <div class="wc-logo-row">
                {logo_html}
                <div>
                    <div class="wc-brand-title">{APP_SHORT_NAME}</div>
                    <div class="wc-brand-subtitle">Prediction Arena</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_sidebar_footer():
    project_link_html = ""

    if FOOTER_PROJECT_URL:
        project_link_html = f"""
        <div style="margin-top:10px;">
            <a href="{FOOTER_PROJECT_URL}" target="_blank">Xem project ↗</a>
        </div>
        """

    image_html = ""

    sidebar_decoration_src = resolve_asset_src(SIDEBAR_DECORATION_URL)

    if sidebar_decoration_src:
        image_html = f"""
        <img class="wc-sidebar-decoration" src="{sidebar_decoration_src}" alt="Sidebar decoration">
        """

    st.markdown(
        f"""
        <div class="wc-sidebar-footer">
            <strong>One World. One Game.</strong>
            <div style="margin-top:6px;color:#CBD5E1;">
                Developed by JungKookHuang.
            </div>
            {project_link_html}
            {image_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_app_hero():
    hero_trophy_src = resolve_asset_src(HERO_TROPHY_IMAGE_URL)

    if hero_trophy_src:
        hero_visual = f'<img class="wc-hero-img" src="{hero_trophy_src}" alt="Hero visual">'
    else:
        hero_visual = '<div class="wc-hero-orb">2026</div>'

    st.markdown(
        f"""
        <div class="wc-hero">
            <div class="wc-hero-grid">
                <div>
                    <div class="wc-eyebrow">⚽ Tournament Prediction Hub</div>
                    <div class="wc-hero-title">
                        World Cup <span class="wc-gold">2026</span><br>
                        Prediction Arena
                    </div>
                    <div class="wc-hero-subtitle">
                        {APP_TAGLINE}
                    </div>
                    <div class="wc-hero-actions">
                        <div class="wc-pill">Leaderboard</div>
                        <div class="wc-pill">Exact score challenge</div>
                        <div class="wc-pill">North America 2026</div>
                    </div>
                </div>
                <div>
                    {hero_visual}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_page_title(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="wc-page-title">
            <h2>{title}</h2>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_status_legend():
    st.markdown(
        """
        <div class="wc-status-legend">
            <div class="wc-legend-item"><span class="wc-dot" style="background:#2563EB;"></span>Đang mở dự đoán</div>
            <div class="wc-legend-item"><span class="wc-dot" style="background:#F59E0B;"></span>Đã khóa</div>
            <div class="wc-legend-item"><span class="wc-dot" style="background:#16A34A;"></span>Đã có kết quả</div>
            <div class="wc-legend-item"><span class="wc-dot" style="background:#9CA3AF;"></span>Chưa xác định đội</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_kpi_tiles(matches: pd.DataFrame):
    total_matches = len(matches)

    finished_matches = int(matches["is_finished"].apply(to_bool).sum())
    unknown_matches = int(
        matches.apply(
            lambda row: is_unknown_team(row.get("home_team_name")) or is_unknown_team(row.get("away_team_name")),
            axis=1
        ).sum()
    )

    now_utc = pd.Timestamp.now(tz="UTC")

    open_matches = int(
        (
            (matches["kickoff_time_utc_dt"] > now_utc)
            & (~matches["is_finished"].apply(to_bool))
        ).sum()
    )

    locked_matches = int(
        (
            (matches["kickoff_time_utc_dt"] <= now_utc)
            & (~matches["is_finished"].apply(to_bool))
        ).sum()
    )

    st.markdown(
        f"""
        <div class="wc-kpi-grid">
            <div class="wc-kpi-tile">
                <div class="wc-kpi-label">Tổng số trận</div>
                <div class="wc-kpi-value">{total_matches}</div>
            </div>
            <div class="wc-kpi-tile">
                <div class="wc-kpi-label">Đang mở dự đoán</div>
                <div class="wc-kpi-value" style="color:#2563EB;">{open_matches}</div>
            </div>
            <div class="wc-kpi-tile">
                <div class="wc-kpi-label">Đã có kết quả</div>
                <div class="wc-kpi-value" style="color:#16A34A;">{finished_matches}</div>
            </div>
            <div class="wc-kpi-tile">
                <div class="wc-kpi-label">Chưa xác định đội</div>
                <div class="wc-kpi-value" style="color:#64748B;">{unknown_matches}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# 3. BASIC UTILITIES
# ============================================================

@st.cache_resource
def get_engine() -> Engine:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True
    )
    return engine


def read_sql(query: str, params: dict | None = None) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql_query(
            text(query),
            conn,
            params=params or {}
        )


def fetch_one(query: str, params: dict | None = None):
    with get_engine().connect() as conn:
        row = conn.execute(
            text(query),
            params or {}
        ).mappings().fetchone()

    if row is None:
        return None

    return dict(row)


def execute_sql(query: str, params: dict | None = None):
    with get_engine().begin() as conn:
        conn.execute(
            text(query),
            params or {}
        )


def execute_many(query: str, rows: list[dict]):
    if not rows:
        return

    with get_engine().begin() as conn:
        conn.execute(
            text(query),
            rows
        )


def now_utc_iso():
    return datetime.now(timezone.utc).isoformat()


def today_vietnam_date():
    return pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").date()


def tomorrow_vietnam_date():
    return today_vietnam_date() + timedelta(days=1)


def format_filter_date(date_value):
    today = today_vietnam_date()
    tomorrow = tomorrow_vietnam_date()

    if date_value == today:
        return "Hôm nay"

    if date_value == tomorrow:
        return "Ngày mai"

    return date_value.strftime("%d/%m/%Y")


def to_bool(value) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    if pd.isna(value):
        return False

    if isinstance(value, (int, float)):
        return value == 1

    value_str = str(value).strip().lower()

    return value_str in ["true", "1", "yes", "y"]


def to_optional_int(value):
    if value is None:
        return None

    if pd.isna(value):
        return None

    return int(value)


def parse_utc_datetime(value):
    return pd.to_datetime(value, utc=True, errors="coerce")


def can_edit_prediction(kickoff_time_utc) -> bool:
    kickoff = parse_utc_datetime(kickoff_time_utc)

    if pd.isna(kickoff):
        return False

    now = pd.Timestamp.now(tz="UTC")

    return now < kickoff


def is_unknown_team(team_name) -> bool:
    if team_name is None or pd.isna(team_name):
        return True

    text = str(team_name).lower()

    unknown_keywords = [
        "tbd",
        "to be decided",
        "winner",
        "runner-up",
        "runner up",
        "2nd group",
        "3rd group",
        "1st group"
    ]

    return any(keyword in text for keyword in unknown_keywords)


def get_outcome(home_score, away_score):
    if home_score > away_score:
        return "HOME_WIN"

    if home_score < away_score:
        return "AWAY_WIN"

    return "DRAW"


def calculate_score_points(pred_home, pred_away, actual_home, actual_away) -> int:
    if pred_home is None or pred_away is None:
        return 0

    if actual_home is None or actual_away is None:
        return 0

    pred_home = int(pred_home)
    pred_away = int(pred_away)
    actual_home = int(actual_home)
    actual_away = int(actual_away)

    if pred_home == actual_home and pred_away == actual_away:
        return 3

    if get_outcome(pred_home, pred_away) == get_outcome(actual_home, actual_away):
        return 1

    return 0


def calculate_total_points(row) -> int:
    pred_home = to_optional_int(row.get("predicted_home_score"))
    pred_away = to_optional_int(row.get("predicted_away_score"))

    actual_home = to_optional_int(row.get("home_score_for_prediction"))
    actual_away = to_optional_int(row.get("away_score_for_prediction"))

    points = calculate_score_points(
        pred_home,
        pred_away,
        actual_home,
        actual_away
    )

    is_knockout = to_bool(row.get("is_knockout"))

    if is_knockout:
        predicted_winner_team_id = to_optional_int(row.get("predicted_winner_team_id"))
        actual_winner_team_id = to_optional_int(row.get("winner_team_id"))

        if (
            predicted_winner_team_id is not None
            and actual_winner_team_id is not None
            and predicted_winner_team_id == actual_winner_team_id
        ):
            points += 1

    return points


def get_prediction_result_info(
    pred_home,
    pred_away,
    actual_home,
    actual_away,
    is_finished
):
    """
    Trả về thông tin hiển thị kết quả dự đoán:
    - Đúng hoàn toàn tỉ số
    - Đúng kết quả
    - Sai

    Logic:
    - Đúng hoàn toàn tỉ số: dự đoán đúng chính xác tỉ số.
    - Đúng kết quả: không đúng tỉ số, nhưng đúng kết quả thắng/hòa/thua.
    - Sai: sai kết quả thắng/hòa/thua.
    """
    if not is_finished:
        return None

    if (
        pred_home is None
        or pred_away is None
        or actual_home is None
        or actual_away is None
    ):
        return None

    pred_home = int(pred_home)
    pred_away = int(pred_away)
    actual_home = int(actual_home)
    actual_away = int(actual_away)

    if pred_home == actual_home and pred_away == actual_away:
        return {
            "label": "Đúng hoàn toàn tỉ số",
            "text_color": "#166534",
            "bg_color": "#DCFCE7",
            "border_color": "#86EFAC"
        }

    if get_outcome(pred_home, pred_away) == get_outcome(actual_home, actual_away):
        return {
            "label": "Đúng kết quả",
            "text_color": "#0369A1",
            "bg_color": "#E0F2FE",
            "border_color": "#7DD3FC"
        }

    return {
        "label": "Sai",
        "text_color": "#B91C1C",
        "bg_color": "#FEE2E2",
        "border_color": "#FCA5A5"
    }


def render_prediction_result_line(result_info):
    if result_info is None:
        return

    st.markdown(
        f"""
        <div style="
            margin-top: 8px;
            margin-bottom: 8px;
            font-size: 15px;
            color: #07111F;
        ">
            Kết quả dự đoán:
            <span style="
                display: inline-block;
                margin-left: 6px;
                padding: 5px 11px;
                border-radius: 999px;
                background: {result_info["bg_color"]};
                color: {result_info["text_color"]};
                border: 1px solid {result_info["border_color"]};
                font-weight: 850;
                font-size: 14px;
            ">
                {result_info["label"]}
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )


def hash_password(password: str, salt: str | None = None):
    if salt is None:
        salt = os.urandom(16).hex()

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        150_000
    ).hex()

    return salt, password_hash


def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    _, password_hash = hash_password(password, salt)
    return hmac.compare_digest(password_hash, stored_hash)


def clear_filter_state():
    for key in [
        "filter_date",
        "filter_stage",
        "filter_status",
        "pending_prediction"
    ]:
        if key in st.session_state:
            del st.session_state[key]


def get_match_status_info(row):
    is_finished = to_bool(row.get("is_finished"))
    editable = can_edit_prediction(row.get("kickoff_time_utc"))

    home_name = row.get("home_team_name")
    away_name = row.get("away_team_name")

    if is_unknown_team(home_name) or is_unknown_team(away_name):
        return {
            "status_key": "unknown",
            "label": "Chưa xác định đội",
            "border_color": "#9CA3AF",
            "background": "linear-gradient(135deg, rgba(248,250,252,0.96), rgba(241,245,249,0.90))",
            "badge_bg": "#E5E7EB",
            "badge_text": "#374151"
        }

    if is_finished:
        return {
            "status_key": "finished",
            "label": "Đã có kết quả",
            "border_color": "#16A34A",
            "background": "linear-gradient(135deg, rgba(240,253,244,0.98), rgba(255,255,255,0.92))",
            "badge_bg": "#DCFCE7",
            "badge_text": "#166534"
        }

    if editable:
        return {
            "status_key": "open",
            "label": "Đang mở dự đoán",
            "border_color": "#2563EB",
            "background": "linear-gradient(135deg, rgba(239,246,255,0.98), rgba(255,255,255,0.94))",
            "badge_bg": "#DBEAFE",
            "badge_text": "#1D4ED8"
        }

    return {
        "status_key": "locked",
        "label": "Đã khóa dự đoán",
        "border_color": "#F59E0B",
        "background": "linear-gradient(135deg, rgba(255,251,235,0.98), rgba(255,255,255,0.94))",
        "badge_bg": "#FEF3C7",
        "badge_text": "#92400E"
    }


def get_match_card_css(status_info):
    return f"""
    {{
        border: 2px solid {status_info["border_color"]};
        border-radius: 20px;
        padding: 20px 20px 14px 20px;
        margin-bottom: 18px;
        background: {status_info["background"]};
        box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
    }}
    """


def render_status_badge(status_info):
    st.markdown(
        f"""
        <div style="
            display:inline-block;
            padding:7px 13px;
            border-radius:999px;
            background:{status_info["badge_bg"]};
            color:{status_info["badge_text"]};
            font-weight:850;
            font-size:13px;
            margin-bottom:8px;
            border:1px solid rgba(15,23,42,0.06);
        ">
            {status_info["label"]}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_match_status_box(status_info):
    """
    Thay cho st.metric khi hiển thị trạng thái dạng text.
    st.metric phù hợp với số, nhưng với text dài như "Đang mở dự đoán" thì font quá lớn và bị cắt.
    """
    st.markdown(
        f"""
        <div style="
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-left: 5px solid {status_info["border_color"]};
            border-radius: 16px;
            padding: 13px 15px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
            min-width: 180px;
        ">
            <div style="
                color: #64748B;
                font-size: 12px;
                font-weight: 800;
                margin-bottom: 5px;
            ">
                Trạng thái
            </div>
            <div style="
                color: {status_info["badge_text"]};
                font-size: 16px;
                font-weight: 900;
                line-height: 1.25;
                white-space: normal;
                overflow: visible;
                text-overflow: unset;
            ">
                {status_info["label"]}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# 4. DATABASE INIT
# ============================================================

def check_base_database():
    try:
        tables = read_sql(
            """
            SELECT table_name AS name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )
    except Exception as e:
        st.error("Không kết nối được Supabase database.")
        st.exception(e)
        st.stop()

    table_names = set(tables["name"].tolist())

    if "matches" not in table_names:
        st.error("Supabase database chưa có bảng `matches`. Hãy kiểm tra lại bước import dữ liệu.")
        st.stop()


def init_app_tables():
    execute_sql(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'player',
            created_at TEXT NOT NULL
        )
        """
    )

    execute_sql(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            prediction_id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            match_id INTEGER NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
            predicted_home_score INTEGER NOT NULL,
            predicted_away_score INTEGER NOT NULL,
            predicted_winner_team_id INTEGER,
            points INTEGER,
            submitted_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, match_id)
        )
        """
    )

    execute_sql(
        """
        CREATE TABLE IF NOT EXISTS prediction_history (
            history_id SERIAL PRIMARY KEY,
            prediction_id INTEGER NOT NULL REFERENCES predictions(prediction_id) ON DELETE CASCADE,
            old_home_score INTEGER,
            old_away_score INTEGER,
            old_winner_team_id INTEGER,
            new_home_score INTEGER NOT NULL,
            new_away_score INTEGER NOT NULL,
            new_winner_team_id INTEGER,
            changed_at TEXT NOT NULL
        )
        """
    )

    execute_sql(
        """
        CREATE TABLE IF NOT EXISTS login_sessions (
            session_id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL
        )
        """
    )

    execute_sql(
        """
        DELETE FROM login_sessions
        WHERE expires_at <= NOW()
        """
    )
    # Tạo unique index cho tên hiển thị nếu dữ liệu hiện tại chưa bị trùng.
    # Index này giúp chặn các biến thể như "Hoang", " hoang ", "HOANG".
    try:
        duplicate_display_names = read_sql(
            """
            SELECT LOWER(TRIM(display_name)) AS normalized_display_name,
                   COUNT(*) AS n
            FROM users
            GROUP BY LOWER(TRIM(display_name))
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )

        if duplicate_display_names.empty:
            execute_sql(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_display_name_unique_ci
                ON users (LOWER(TRIM(display_name)))
                """
            )

    except Exception:
        # Không chặn app khởi động nếu database đã có dữ liệu trùng hoặc index lỗi.
        # create_user() vẫn có kiểm tra app-level để ngăn tên hiển thị trùng về sau.
        pass


@st.cache_resource
def initialize_app_once():
    """
    Chạy kiểm tra/khoi tạo database một lần cho mỗi app process.

    Mục tiêu:
    - Không gọi check/create table ở mỗi lần rerun.
    - Giảm thời gian khởi động lại giao diện khi người dùng click/F5.
    - Không thay đổi logic dữ liệu hay logic chấm điểm.
    """
    check_base_database()
    init_app_tables()
    return True


def count_users() -> int:
    row = fetch_one(
        """
        SELECT COUNT(*) AS n
        FROM users
        """
    )

    return int(row["n"])

def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_login_session(user_id: int) -> str:
    token = secrets.token_urlsafe(48)
    token_hash = hash_session_token(token)

    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)

    execute_sql(
        """
        INSERT INTO login_sessions (
            user_id,
            token_hash,
            expires_at
        )
        VALUES (
            :user_id,
            :token_hash,
            :expires_at
        )
        """,
        {
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at
        }
    )

    return token


def get_user_by_session_token(token: str):
    if not token:
        return None

    token_hash = hash_session_token(token)

    return fetch_one(
        """
        SELECT
            u.user_id,
            u.username,
            u.display_name,
            u.role,
            u.created_at
        FROM login_sessions s
        JOIN users u
          ON s.user_id = u.user_id
        WHERE s.token_hash = :token_hash
          AND s.expires_at > NOW()
        """,
        {
            "token_hash": token_hash
        }
    )


def delete_login_session(token: str):
    if not token:
        return

    execute_sql(
        """
        DELETE FROM login_sessions
        WHERE token_hash = :token_hash
        """,
        {
            "token_hash": hash_session_token(token)
        }
    )


def restore_user_from_cookie():
    if "user" in st.session_state:
        return

    token = cookie_controller.get(COOKIE_NAME)

    if not token:
        cookies = cookie_controller.getAll()

        if isinstance(cookies, dict):
            token = cookies.get(COOKIE_NAME)

    if not token:
        return

    user = get_user_by_session_token(token)

    if user is None:
        cookie_controller.remove(COOKIE_NAME)
        return

    st.session_state["user"] = user


# ============================================================
# 5. AUTH FUNCTIONS
# ============================================================

def create_user(username: str, display_name: str, password: str):
    username = username.strip().lower()
    display_name = display_name.strip()

    if not username:
        raise ValueError("Username không được để trống.")

    if not display_name:
        raise ValueError("Tên hiển thị không được để trống.")

    if len(password) < 8:
        raise ValueError("Mật khẩu nên có ít nhất 8 ký tự.")

    existing_username = fetch_one(
        """
        SELECT user_id
        FROM users
        WHERE username = :username
        """,
        {
            "username": username
        }
    )

    if existing_username is not None:
        raise ValueError("Username này đã tồn tại.")

    existing_display_name = fetch_one(
        """
        SELECT user_id
        FROM users
        WHERE LOWER(TRIM(display_name)) = LOWER(TRIM(:display_name))
        """,
        {
            "display_name": display_name
        }
    )

    if existing_display_name is not None:
        raise ValueError("Tên hiển thị này đã được sử dụng. Hãy chọn tên khác.")

    salt, password_hash = hash_password(password)

    role = "admin" if count_users() == 0 else "player"

    try:
        execute_sql(
            """
            INSERT INTO users (
                username,
                display_name,
                password_salt,
                password_hash,
                role,
                created_at
            )
            VALUES (
                :username,
                :display_name,
                :password_salt,
                :password_hash,
                :role,
                :created_at
            )
            """,
            {
                "username": username,
                "display_name": display_name,
                "password_salt": salt,
                "password_hash": password_hash,
                "role": role,
                "created_at": now_utc_iso()
            }
        )

        clear_data_cache()

    except IntegrityError:
        raise ValueError("Username hoặc tên hiển thị đã tồn tại.")

    return role


def login_user(username: str, password: str):
    username = username.strip().lower()

    user = fetch_one(
        """
        SELECT *
        FROM users
        WHERE username = :username
        """,
        {
            "username": username
        }
    )

    if user is None:
        return None

    is_valid = verify_password(
        password=password,
        salt=user["password_salt"],
        stored_hash=user["password_hash"]
    )

    if not is_valid:
        return None

    return user


def logout_user():
    token = cookie_controller.get(COOKIE_NAME)

    if token:
        delete_login_session(token)
        cookie_controller.remove(COOKIE_NAME)

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.rerun()


# ============================================================
# 6. DATA LOADING
# ============================================================

@st.cache_data(ttl=30, show_spinner=False)
def load_matches() -> pd.DataFrame:
    df = read_sql(
        """
        SELECT *
        FROM matches
        ORDER BY kickoff_time_utc
        """
    )

    if df.empty:
        return df

    df["kickoff_time_utc_dt"] = pd.to_datetime(
        df["kickoff_time_utc"],
        utc=True,
        errors="coerce"
    )

    if "kickoff_date_vietnam" in df.columns:
        df["kickoff_date_filter"] = pd.to_datetime(
            df["kickoff_date_vietnam"],
            errors="coerce"
        ).dt.date
    else:
        df["kickoff_date_filter"] = df["kickoff_time_utc_dt"].dt.tz_convert(
            "Asia/Ho_Chi_Minh"
        ).dt.date

    return df


@st.cache_data(ttl=30, show_spinner=False)
def load_users() -> pd.DataFrame:
    return read_sql(
        """
        SELECT user_id, username, display_name, role, created_at
        FROM users
        """
    )


@st.cache_data(ttl=10, show_spinner=False)
def load_predictions() -> pd.DataFrame:
    return read_sql(
        """
        SELECT *
        FROM predictions
        """
    )


def clear_data_cache():
    """
    Xóa cache dữ liệu đọc từ Supabase sau khi có thao tác ghi dữ liệu.

    Các hàm load_* có TTL ngắn để app nhanh hơn, nhưng khi user lưu dự đoán
    hoặc admin cập nhật kết quả, cache cần được xóa ngay để màn hình tiếp theo
    đọc dữ liệu mới nhất.
    """
    load_matches.clear()
    load_users.clear()
    load_predictions.clear()


def get_user_prediction(user_id: int, match_id: int):
    return fetch_one(
        """
        SELECT *
        FROM predictions
        WHERE user_id = :user_id
          AND match_id = :match_id
        """,
        {
            "user_id": user_id,
            "match_id": match_id
        }
    )


def get_match_by_id(match_id: int):
    return fetch_one(
        """
        SELECT *
        FROM matches
        WHERE match_id = :match_id
        """,
        {
            "match_id": match_id
        }
    )


# ============================================================
# 7. PREDICTION SAVE + SCORING
# ============================================================

def save_prediction(
    user_id: int,
    match_id: int,
    predicted_home_score: int,
    predicted_away_score: int,
    predicted_winner_team_id: int | None
):
    match = get_match_by_id(match_id)

    if match is None:
        raise ValueError("Không tìm thấy trận đấu.")

    if not can_edit_prediction(match["kickoff_time_utc"]):
        raise ValueError("Trận đấu đã khóa dự đoán.")

    existing = get_user_prediction(user_id, match_id)
    now_text = now_utc_iso()

    with get_engine().begin() as conn:
        if existing is None:
            conn.execute(
                text(
                    """
                    INSERT INTO predictions (
                        user_id,
                        match_id,
                        predicted_home_score,
                        predicted_away_score,
                        predicted_winner_team_id,
                        points,
                        submitted_at,
                        updated_at
                    )
                    VALUES (
                        :user_id,
                        :match_id,
                        :predicted_home_score,
                        :predicted_away_score,
                        :predicted_winner_team_id,
                        NULL,
                        :submitted_at,
                        :updated_at
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "match_id": match_id,
                    "predicted_home_score": predicted_home_score,
                    "predicted_away_score": predicted_away_score,
                    "predicted_winner_team_id": predicted_winner_team_id,
                    "submitted_at": now_text,
                    "updated_at": now_text
                }
            )

        else:
            prediction_id = existing["prediction_id"]

            conn.execute(
                text(
                    """
                    INSERT INTO prediction_history (
                        prediction_id,
                        old_home_score,
                        old_away_score,
                        old_winner_team_id,
                        new_home_score,
                        new_away_score,
                        new_winner_team_id,
                        changed_at
                    )
                    VALUES (
                        :prediction_id,
                        :old_home_score,
                        :old_away_score,
                        :old_winner_team_id,
                        :new_home_score,
                        :new_away_score,
                        :new_winner_team_id,
                        :changed_at
                    )
                    """
                ),
                {
                    "prediction_id": prediction_id,
                    "old_home_score": existing["predicted_home_score"],
                    "old_away_score": existing["predicted_away_score"],
                    "old_winner_team_id": existing["predicted_winner_team_id"],
                    "new_home_score": predicted_home_score,
                    "new_away_score": predicted_away_score,
                    "new_winner_team_id": predicted_winner_team_id,
                    "changed_at": now_text
                }
            )

            conn.execute(
                text(
                    """
                    UPDATE predictions
                    SET
                        predicted_home_score = :predicted_home_score,
                        predicted_away_score = :predicted_away_score,
                        predicted_winner_team_id = :predicted_winner_team_id,
                        updated_at = :updated_at,
                        points = NULL
                    WHERE prediction_id = :prediction_id
                    """
                ),
                {
                    "predicted_home_score": predicted_home_score,
                    "predicted_away_score": predicted_away_score,
                    "predicted_winner_team_id": predicted_winner_team_id,
                    "updated_at": now_text,
                    "prediction_id": prediction_id
                }
            )

    clear_data_cache()

def score_all_predictions():
    matches = load_matches()
    predictions = load_predictions()

    if predictions.empty:
        return

    df = predictions.merge(
        matches,
        on="match_id",
        how="left"
    )

    scored_rows = []

    for _, row in df.iterrows():
        is_finished = to_bool(row.get("is_finished"))

        actual_home = to_optional_int(row.get("home_score_for_prediction"))
        actual_away = to_optional_int(row.get("away_score_for_prediction"))

        if not is_finished or actual_home is None or actual_away is None:
            continue

        points = calculate_total_points(row)

        scored_rows.append(
            {
                "points": points,
                "prediction_id": int(row["prediction_id"])
            }
        )

    if not scored_rows:
        return

    execute_many(
        """
        UPDATE predictions
        SET points = :points
        WHERE prediction_id = :prediction_id
        """,
        scored_rows
    )

    clear_data_cache()


def update_match_result(
    match_id: int,
    score_ft_home: int,
    score_ft_away: int,
    score_et_home: int | None,
    score_et_away: int | None,
    score_pen_home: int | None,
    score_pen_away: int | None,
    winner_team_id: int | None
):
    match = get_match_by_id(match_id)

    if match is None:
        raise ValueError("Không tìm thấy trận đấu.")

    is_knockout = to_bool(match.get("is_knockout"))

    home_team_id = to_optional_int(match.get("home_team_id"))
    away_team_id = to_optional_int(match.get("away_team_id"))

    home_team_name = match.get("home_team_name")
    away_team_name = match.get("away_team_name")

    if score_et_home is not None and score_et_away is not None:
        home_score_for_prediction = score_et_home
        away_score_for_prediction = score_et_away
    else:
        home_score_for_prediction = score_ft_home
        away_score_for_prediction = score_ft_away

    if not is_knockout:
        if home_score_for_prediction > away_score_for_prediction:
            winner_team_id = home_team_id
        elif away_score_for_prediction > home_score_for_prediction:
            winner_team_id = away_team_id
        else:
            winner_team_id = None

    if is_knockout:
        if home_score_for_prediction > away_score_for_prediction:
            winner_team_id = home_team_id
        elif away_score_for_prediction > home_score_for_prediction:
            winner_team_id = away_team_id
        else:
            if winner_team_id is None:
                raise ValueError(
                    "Trận knockout hòa sau thời gian thi đấu. "
                    "Bạn cần chọn đội đi tiếp."
                )

    winner_team_name = None

    if winner_team_id == home_team_id:
        winner_team_name = home_team_name
    elif winner_team_id == away_team_id:
        winner_team_name = away_team_name

    execute_sql(
        """
        UPDATE matches
        SET
            score_ft_home = :score_ft_home,
            score_ft_away = :score_ft_away,
            score_et_home = :score_et_home,
            score_et_away = :score_et_away,
            score_pen_home = :score_pen_home,
            score_pen_away = :score_pen_away,
            home_score_for_prediction = :home_score_for_prediction,
            away_score_for_prediction = :away_score_for_prediction,
            winner_team_id = :winner_team_id,
            winner_team_name = :winner_team_name,
            is_finished = TRUE
        WHERE match_id = :match_id
        """,
        {
            "score_ft_home": score_ft_home,
            "score_ft_away": score_ft_away,
            "score_et_home": score_et_home,
            "score_et_away": score_et_away,
            "score_pen_home": score_pen_home,
            "score_pen_away": score_pen_away,
            "home_score_for_prediction": home_score_for_prediction,
            "away_score_for_prediction": away_score_for_prediction,
            "winner_team_id": winner_team_id,
            "winner_team_name": winner_team_name,
            "match_id": match_id
        }
    )

    clear_data_cache()
    score_all_predictions()


# ============================================================
# 8. AUTH UI
# ============================================================

def render_auth_page():
    render_app_hero()

    with stylable_container(
        key="auth_card",
        css_styles="""
        {
            background: rgba(255,255,255,0.94);
            border: 1px solid rgba(15,23,42,0.08);
            border-radius: 24px;
            padding: 22px;
            box-shadow: 0 18px 42px rgba(15,23,42,0.10);
        }
        """
    ):
        render_page_title(
            "Đăng nhập",
            "Tạo tài khoản để lưu dự đoán, theo dõi điểm và cạnh tranh cùng bạn bè."
        )

        tab_login, tab_register = st.tabs(["Đăng nhập", "Đăng ký"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Mật khẩu", type="password")

                submitted = st.form_submit_button("Đăng nhập")

                if submitted:
                    user = login_user(username, password)

                    if user is None:
                        st.error("Sai username hoặc mật khẩu.")
                    else:
                        clear_filter_state()

                        session_token = create_login_session(user["user_id"])

                        cookie_controller.set(
                            COOKIE_NAME,
                            session_token,
                            max_age=SESSION_DAYS * 24 * 60 * 60
                        )

                        st.session_state["user"] = user
                        st.session_state["selected_page"] = "Lịch thi đấu & dự đoán"

                        st.success("Đăng nhập thành công.")

        with tab_register:
            st.info("Mật khẩu phải có ít nhất 8 ký tự.")

            with st.form("register_form"):
                username = st.text_input("Username", key="register_username")
                display_name = st.text_input("Tên hiển thị")
                password = st.text_input("Mật khẩu", type="password", key="register_password")
                password_confirm = st.text_input("Nhập lại mật khẩu", type="password")

                submitted = st.form_submit_button("Tạo tài khoản")

                if submitted:
                    if password != password_confirm:
                        st.error("Mật khẩu nhập lại không khớp.")
                    else:
                        try:
                            role = create_user(username, display_name, password)
                            st.success(f"Tạo tài khoản thành công. Role của bạn: {role}. Hãy đăng nhập.")
                        except ValueError as e:
                            st.error(str(e))


# ============================================================
# 9. MATCH CARD UI
# ============================================================

def render_inline_prediction_confirmation(match_id: int):
    pending = st.session_state.get("pending_prediction")

    if not pending:
        return

    if int(pending["match_id"]) != int(match_id):
        return

    match = get_match_by_id(match_id)

    if match is None:
        st.session_state["pending_prediction"] = None
        return

    home_name = match["home_team_name"]
    away_name = match["away_team_name"]

    with stylable_container(
        key=f"inline_confirm_box_{match_id}",
        css_styles="""
        {
            border: 2px solid #7C3AED;
            border-radius: 18px;
            padding: 18px;
            margin-top: 14px;
            margin-bottom: 8px;
            background:
                radial-gradient(circle at top right, rgba(245,197,66,0.22), transparent 32%),
                linear-gradient(135deg, #F5F3FF, #FFFFFF);
            box-shadow: 0 12px 30px rgba(124, 58, 237, 0.14);
        }
        """
    ):
        st.markdown("#### 🎯 Xác nhận dự đoán")

        st.markdown(
            f"""
            Bạn đang lưu dự đoán:

            **{home_name} {pending['predicted_home_score']} - {pending['predicted_away_score']} {away_name}**
            """
        )

        if pending.get("predicted_winner_team_name"):
            st.markdown(f"Đội đi tiếp: **{pending['predicted_winner_team_name']}**")

        st.caption("Bạn vẫn có thể chỉnh sửa dự đoán cho đến trước giờ bóng lăn.")

        col_confirm, col_cancel = st.columns([1, 1])

        with col_confirm:
            if st.button(
                "✅ Xác nhận lưu",
                use_container_width=True,
                key=f"confirm_prediction_{match_id}"
            ):
                try:
                    save_prediction(
                        user_id=st.session_state["user"]["user_id"],
                        match_id=pending["match_id"],
                        predicted_home_score=pending["predicted_home_score"],
                        predicted_away_score=pending["predicted_away_score"],
                        predicted_winner_team_id=pending["predicted_winner_team_id"]
                    )

                    st.session_state["pending_prediction"] = None
                    st.success("Đã lưu dự đoán.")
                    st.rerun()

                except ValueError as e:
                    st.error(str(e))

        with col_cancel:
            if st.button(
                "❌ Hủy",
                use_container_width=True,
                key=f"cancel_prediction_{match_id}"
            ):
                st.session_state["pending_prediction"] = None
                st.rerun()


def render_match_card(row, user_id: int):
    match_id = int(row["match_id"])

    home_team_id = to_optional_int(row.get("home_team_id"))
    away_team_id = to_optional_int(row.get("away_team_id"))

    home_name = row.get("home_team_name")
    away_name = row.get("away_team_name")

    is_knockout = to_bool(row.get("is_knockout"))
    is_finished = to_bool(row.get("is_finished"))

    editable = can_edit_prediction(row.get("kickoff_time_utc"))

    existing = get_user_prediction(user_id, match_id)

    status_info = get_match_status_info(row)
    card_css = get_match_card_css(status_info)

    with stylable_container(
        key=f"match_card_{match_id}",
        css_styles=card_css
    ):
        render_status_badge(status_info)

        top_left, top_right = st.columns([3, 1])

        with top_left:
            st.subheader(f"{home_name} vs {away_name}")

            st.caption(
                f"{row.get('round_name')} | "
                f"{row.get('kickoff_weekday_vietnam', '')} "
                f"{row.get('kickoff_date_display_vietnam', row.get('kickoff_date_vietnam', ''))} "
                f"lúc {row.get('kickoff_time_vietnam', '')}"
            )

            venue = row.get("venue")
            city = row.get("city")

            if venue or city:
                st.caption(f"🏟️ {venue or ''} {city or ''}")

        with top_right:
            actual_home = to_optional_int(row.get("home_score_for_prediction"))
            actual_away = to_optional_int(row.get("away_score_for_prediction"))

            if is_finished and actual_home is not None and actual_away is not None:
                st.metric("Kết quả", f"{actual_home} - {actual_away}")

                winner_name = row.get("winner_team_name")

                winner_name_is_valid = (
                    winner_name is not None
                    and not pd.isna(winner_name)
                    and str(winner_name).strip().lower() not in ["", "nan", "none"]
                )

                if winner_name_is_valid:
                    st.caption(f"Đi tiếp/thắng: {str(winner_name).strip()}")

                elif not is_knockout and actual_home == actual_away:
                    st.caption("Đi tiếp/thắng: 2 đội hòa nhau")

                elif is_knockout and actual_home == actual_away:
                    st.caption("Đi tiếp/thắng: Chưa xác định đội đi tiếp")

                elif actual_home > actual_away:
                    st.caption(f"Đi tiếp/thắng: {home_name}")

                elif actual_away > actual_home:
                    st.caption(f"Đi tiếp/thắng: {away_name}")

            else:
                render_match_status_box(status_info)

        if is_unknown_team(home_name) or is_unknown_team(away_name):
            st.info("Chưa xác định đủ đội, tạm thời chưa mở dự đoán.")
            render_inline_prediction_confirmation(match_id)
            return

        if existing:
            pred_home = int(existing["predicted_home_score"])
            pred_away = int(existing["predicted_away_score"])
            pred_winner_team_id = existing["predicted_winner_team_id"]

            st.markdown(
                f"Dự đoán hiện tại của bạn: "
                f"**{home_name} {pred_home} - {pred_away} {away_name}**"
            )

            actual_home_for_result = to_optional_int(row.get("home_score_for_prediction"))
            actual_away_for_result = to_optional_int(row.get("away_score_for_prediction"))

            prediction_result_info = get_prediction_result_info(
                pred_home=pred_home,
                pred_away=pred_away,
                actual_home=actual_home_for_result,
                actual_away=actual_away_for_result,
                is_finished=is_finished
            )

            render_prediction_result_line(prediction_result_info)

            if existing.get("points") is not None:
                st.markdown(f"Điểm: **{existing['points']}**")

        else:
            pred_home = 0
            pred_away = 0
            pred_winner_team_id = None
            st.caption("Bạn chưa dự đoán trận này.")

        if not editable:
            render_inline_prediction_confirmation(match_id)
            return

        with st.form(f"prediction_form_{match_id}"):
            col_home, col_mid, col_away = st.columns([2, 1, 2])

            with col_home:
                input_home = st.number_input(
                    home_name,
                    min_value=0,
                    max_value=20,
                    value=pred_home,
                    step=1,
                    key=f"home_score_{match_id}"
                )

            with col_mid:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("### -")

            with col_away:
                input_away = st.number_input(
                    away_name,
                    min_value=0,
                    max_value=20,
                    value=pred_away,
                    step=1,
                    key=f"away_score_{match_id}"
                )

            predicted_winner_team_id = None
            predicted_winner_team_name = None

            if is_knockout:
                if input_home > input_away:
                    predicted_winner_team_id = home_team_id
                    predicted_winner_team_name = home_name
                    st.info(f"Đội đi tiếp tự động: {home_name}")

                elif input_away > input_home:
                    predicted_winner_team_id = away_team_id
                    predicted_winner_team_name = away_name
                    st.info(f"Đội đi tiếp tự động: {away_name}")

                else:
                    winner_options = {
                        home_name: home_team_id,
                        away_name: away_team_id
                    }

                    default_index = 0

                    if pred_winner_team_id == away_team_id:
                        default_index = 1

                    selected_winner_name = st.radio(
                        "Dự đoán hòa ở knockout. Chọn đội đi tiếp:",
                        options=list(winner_options.keys()),
                        index=default_index,
                        horizontal=True,
                        key=f"winner_{match_id}"
                    )

                    predicted_winner_team_id = winner_options[selected_winner_name]
                    predicted_winner_team_name = selected_winner_name

            submitted = st.form_submit_button("Lưu / cập nhật dự đoán")

            if submitted:
                st.session_state["pending_prediction"] = {
                    "match_id": match_id,
                    "predicted_home_score": int(input_home),
                    "predicted_away_score": int(input_away),
                    "predicted_winner_team_id": predicted_winner_team_id,
                    "predicted_winner_team_name": predicted_winner_team_name
                }
                st.rerun()

        render_inline_prediction_confirmation(match_id)


# ============================================================
# 10. PAGES
# ============================================================

def page_matches():
    render_app_hero()

    render_page_title(
        "Lịch thi đấu & dự đoán",
        "Chọn ngày, vòng đấu và trạng thái để nhập dự đoán cho từng trận."
    )

    matches = load_matches()

    if matches.empty:
        st.warning("Chưa có dữ liệu trận đấu.")
        return

    render_kpi_tiles(matches)
    render_status_legend()

    available_dates = sorted(matches["kickoff_date_filter"].dropna().unique())

    today_vn = today_vietnam_date()
    tomorrow_vn = tomorrow_vietnam_date()

    date_options_set = set(available_dates)
    date_options_set.add(today_vn)
    date_options_set.add(tomorrow_vn)

    date_options = sorted(date_options_set)

    if "filter_date" not in st.session_state:
        st.session_state["filter_date"] = today_vn

    if "filter_stage" not in st.session_state:
        st.session_state["filter_stage"] = "Tất cả"

    if "filter_status" not in st.session_state:
        st.session_state["filter_status"] = "Tất cả"

    stage_options = ["Tất cả"] + sorted(matches["stage_type"].dropna().unique().tolist())
    status_options = ["Tất cả", "Sắp diễn ra", "Đã khóa", "Đã có kết quả"]

    if st.session_state["filter_date"] not in date_options:
        st.session_state["filter_date"] = today_vn

    if st.session_state["filter_stage"] not in stage_options:
        st.session_state["filter_stage"] = "Tất cả"

    if st.session_state["filter_status"] not in status_options:
        st.session_state["filter_status"] = "Tất cả"

    with stylable_container(
        key="match_filter_panel",
        css_styles="""
        {
            background: rgba(255,255,255,0.94);
            border: 1px solid rgba(15,23,42,0.08);
            border-radius: 22px;
            padding: 12px 26px 10px 26px;
            box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
            margin: 4px 0 24px 0;
            width: 100%;
        min-height: 96px;
            box-sizing: border-box;
        }

        div[data-testid="stSelectbox"] {
            margin-bottom: 0 !important;
        }

        div[data-testid="stSelectbox"] label {
            margin-bottom: 4px !important;
        }
        """
    ):
        col_filter_1, col_filter_2, col_filter_3 = st.columns([2, 2, 2])

        with col_filter_1:
            selected_date = st.selectbox(
                "Ngày thi đấu",
                options=date_options,
                index=date_options.index(st.session_state["filter_date"]),
                format_func=format_filter_date,
                key="filter_date"
            )

        with col_filter_2:
            selected_stage = st.selectbox(
                "Vòng đấu",
                options=stage_options,
                index=stage_options.index(st.session_state["filter_stage"]),
                key="filter_stage"
            )

        with col_filter_3:
            status_filter = st.selectbox(
                "Trạng thái",
                options=status_options,
                index=status_options.index(st.session_state["filter_status"]),
                key="filter_status"
            )

    filtered = matches.copy()

    filtered = filtered[filtered["kickoff_date_filter"] == selected_date]

    if selected_stage != "Tất cả":
        filtered = filtered[filtered["stage_type"] == selected_stage]

    now_utc = pd.Timestamp.now(tz="UTC")

    if status_filter == "Sắp diễn ra":
        filtered = filtered[
            (filtered["kickoff_time_utc_dt"] > now_utc)
            & (~filtered["is_finished"].apply(to_bool))
        ]

    elif status_filter == "Đã khóa":
        filtered = filtered[
            (filtered["kickoff_time_utc_dt"] <= now_utc)
            & (~filtered["is_finished"].apply(to_bool))
        ]

    elif status_filter == "Đã có kết quả":
        filtered = filtered[
            filtered["is_finished"].apply(to_bool)
        ]

    filtered = filtered.sort_values("kickoff_time_utc_dt")

    if filtered.empty:
        st.info("Không có trận nào phù hợp với bộ lọc hiện tại.")
        return

    user_id = st.session_state["user"]["user_id"]

    for match_date, group_df in filtered.groupby("kickoff_date_filter"):
        st.markdown("---")
        st.header(format_filter_date(match_date))

        group_df = group_df.sort_values("kickoff_time_utc_dt")

        for _, row in group_df.iterrows():
            render_match_card(row, user_id)


def page_my_predictions():
    render_page_title(
        "Dự đoán của tôi",
        "Theo dõi toàn bộ dự đoán đã lưu và điểm số từng trận."
    )

    user_id = st.session_state["user"]["user_id"]

    matches = load_matches()
    predictions = load_predictions()

    if predictions.empty:
        st.info("Bạn chưa có dự đoán nào.")
        return

    my_predictions = predictions[predictions["user_id"] == user_id].copy()

    if my_predictions.empty:
        st.info("Bạn chưa có dự đoán nào.")
        return

    df = my_predictions.merge(
        matches,
        on="match_id",
        how="left"
    )

    df = df.sort_values("kickoff_time_utc_dt")

    display_df = pd.DataFrame({
        "Ngày": df.get("kickoff_date_display_vietnam", df.get("kickoff_date_vietnam")),
        "Giờ": df.get("kickoff_time_vietnam"),
        "Vòng": df.get("round_name"),
        "Trận": df["home_team_name"] + " vs " + df["away_team_name"],
        "Dự đoán": (
            df["predicted_home_score"].astype(str)
            + " - "
            + df["predicted_away_score"].astype(str)
        ),
        "Kết quả": df.apply(
            lambda row: (
                ""
                if pd.isna(row.get("home_score_for_prediction"))
                or pd.isna(row.get("away_score_for_prediction"))
                else f"{int(row['home_score_for_prediction'])} - {int(row['away_score_for_prediction'])}"
            ),
            axis=1
        ),
        "Điểm": df["points"].apply(
            lambda x: "" if pd.isna(x) else str(int(round(float(x))))
        )
    })

    with stylable_container(
        key="my_predictions_table",
        css_styles="""
        {
            background: rgba(255,255,255,0.94);
            border: 1px solid rgba(15,23,42,0.08);
            border-radius: 22px;
            padding: 18px;
            box-shadow: 0 14px 34px rgba(15,23,42,0.08);
        }
        """
    ):
        st.dataframe(display_df, use_container_width=True, hide_index=True)


def build_leaderboard_df():
    users = load_users()
    predictions = load_predictions()
    matches = load_matches()

    if users.empty:
        return pd.DataFrame()

    if predictions.empty:
        result = users.copy()
        result["total_points"] = 0
        result["num_predictions"] = 0
        result["num_scored"] = 0
        result["exact_score_count"] = 0
        result["correct_outcome_count"] = 0
        result["knockout_winner_checkable"] = 0
        result["knockout_winner_correct"] = 0
        result["exact_score_rate"] = 0.0
        result["outcome_rate"] = 0.0
        result["knockout_winner_rate"] = 0.0
        result = result.sort_values("display_name").reset_index(drop=True)
        result["rank"] = range(1, len(result) + 1)
        return result

    df = predictions.merge(users, on="user_id", how="left")
    df = df.merge(matches, on="match_id", how="left")

    metrics = []

    for _, row in df.iterrows():
        pred_home = to_optional_int(row.get("predicted_home_score"))
        pred_away = to_optional_int(row.get("predicted_away_score"))

        actual_home = to_optional_int(row.get("home_score_for_prediction"))
        actual_away = to_optional_int(row.get("away_score_for_prediction"))

        is_scored = (
            pred_home is not None
            and pred_away is not None
            and actual_home is not None
            and actual_away is not None
            and to_bool(row.get("is_finished"))
        )

        exact = False
        correct_outcome = False

        if is_scored:
            exact = pred_home == actual_home and pred_away == actual_away
            correct_outcome = (
                get_outcome(pred_home, pred_away)
                == get_outcome(actual_home, actual_away)
            )

        is_knockout = to_bool(row.get("is_knockout"))

        knockout_winner_checkable = (
            is_scored
            and is_knockout
            and to_optional_int(row.get("winner_team_id")) is not None
        )

        knockout_winner_correct = False

        if knockout_winner_checkable:
            knockout_winner_correct = (
                to_optional_int(row.get("predicted_winner_team_id"))
                == to_optional_int(row.get("winner_team_id"))
            )

        metrics.append({
            "is_scored": is_scored,
            "exact_score": exact,
            "correct_outcome": correct_outcome,
            "knockout_winner_checkable": knockout_winner_checkable,
            "knockout_winner_correct": knockout_winner_correct
        })

    metrics_df = pd.DataFrame(metrics)

    df = pd.concat(
        [
            df.reset_index(drop=True),
            metrics_df.reset_index(drop=True)
        ],
        axis=1
    )

    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0)

    summary = (
        df
        .groupby(["user_id", "username", "display_name", "role"], as_index=False)
        .agg(
            total_points=("points", "sum"),
            num_predictions=("prediction_id", "count"),
            num_scored=("is_scored", "sum"),
            exact_score_count=("exact_score", "sum"),
            correct_outcome_count=("correct_outcome", "sum"),
            knockout_winner_checkable=("knockout_winner_checkable", "sum"),
            knockout_winner_correct=("knockout_winner_correct", "sum")
        )
    )

    numeric_cols = [
        "total_points",
        "num_predictions",
        "num_scored",
        "exact_score_count",
        "correct_outcome_count",
        "knockout_winner_checkable",
        "knockout_winner_correct"
    ]

    for col in numeric_cols:
        summary[col] = summary[col].fillna(0).astype(int)

    summary["exact_score_rate"] = summary.apply(
        lambda row: row["exact_score_count"] / row["num_scored"]
        if row["num_scored"] else 0,
        axis=1
    )

    # Gộp logic:
    # - correct_outcome_count: số lần đoán đúng thắng/hòa/thua
    # - knockout_winner_correct: số lần đoán đúng đội đi tiếp ở knockout
    # => result_prediction_rate là % Đoán đúng kết quả tổng hợp
    summary["result_prediction_checkable"] = (
        summary["num_scored"] + summary["knockout_winner_checkable"]
    )

    summary["result_prediction_correct"] = (
        summary["correct_outcome_count"] + summary["knockout_winner_correct"]
    )

    summary["result_prediction_rate"] = summary.apply(
        lambda row: row["result_prediction_correct"] / row["result_prediction_checkable"]
        if row["result_prediction_checkable"] else 0,
        axis=1
    )

    summary = summary.sort_values(
        ["total_points", "exact_score_count", "correct_outcome_count"],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    summary["rank"] = range(1, len(summary) + 1)

    return summary


def page_leaderboard():
    render_page_title(
        "Bảng xếp hạng",
        "Xem ai đang dẫn đầu cuộc đua dự đoán."
    )

    score_all_predictions()

    leaderboard = build_leaderboard_df()

    if leaderboard.empty:
        st.info("Chưa có dữ liệu người chơi.")
        return

    display_df = leaderboard[
        [
            "rank",
            "display_name",
            "total_points",
            "num_predictions",
            "num_scored",
            "exact_score_count",
            "correct_outcome_count",
            "exact_score_rate",
            "result_prediction_rate"
        ]
    ].copy()

    display_df = display_df.rename(columns={
        "rank": "Hạng",
        "display_name": "Người chơi",
        "total_points": "Điểm",
        "num_predictions": "Số dự đoán",
        "num_scored": "Số trận đã chấm",
        "exact_score_count": "Đúng tỉ số",
        "correct_outcome_count": "Đúng kết quả",
        "exact_score_rate": "% Đoán đúng hoàn toàn tỉ số",
        "result_prediction_rate": "% Đoán đúng kết quả"
    })

    percent_cols = [
        "% Đoán đúng hoàn toàn tỉ số",
        "% Đoán đúng kết quả"
    ]

    for col in percent_cols:
        display_df[col] = display_df[col].apply(lambda x: f"{x * 100:.0f}%")

    with stylable_container(
        key="leaderboard_table_card",
        css_styles="""
        {
            background: rgba(255,255,255,0.94);
            border: 1px solid rgba(15,23,42,0.08);
            border-radius: 22px;
            padding: 18px;
            box-shadow: 0 14px 34px rgba(15,23,42,0.08);
        }
        """
    ):
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )


def page_dashboard():
    render_page_title(
        "Dashboard phân tích",
        "Tổng quan hiệu suất dự đoán, điểm số và độ chính xác."
    )

    score_all_predictions()

    leaderboard = build_leaderboard_df()
    predictions = load_predictions()
    matches = load_matches()

    if leaderboard.empty or predictions.empty:
        st.info("Chưa đủ dữ liệu để vẽ dashboard.")
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Số người chơi", len(leaderboard))

    with col2:
        st.metric("Tổng dự đoán", len(predictions))

    with col3:
        st.metric("Trận đã có kết quả", int(matches["is_finished"].apply(to_bool).sum()))

    with col4:
        st.metric("Điểm cao nhất", int(leaderboard["total_points"].max()))

    st.markdown("---")

    top_points = leaderboard.sort_values("total_points", ascending=False)

    fig_points = px.bar(
        top_points,
        x="display_name",
        y="total_points",
        title="Tổng điểm theo người chơi",
        labels={
            "display_name": "Người chơi",
            "total_points": "Điểm"
        },
        color="total_points",
        color_continuous_scale=["#123C69", "#00B4D8", "#F5C542"]
    )

    fig_points.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#07111F")
    )

    st.plotly_chart(fig_points, use_container_width=True)

    fig_accuracy = px.scatter(
        leaderboard,
        x="result_prediction_rate",
        y="exact_score_rate",
        size="total_points",
        hover_name="display_name",
        title="Độ chính xác kết quả vs độ chính xác tỉ số",
        labels={
            "result_prediction_rate": "% Đoán đúng kết quả",
            "exact_score_rate": "% Đoán đúng hoàn toàn tỉ số",
            "total_points": "Điểm"
        },
        color="total_points",
        color_continuous_scale=["#E63946", "#00B4D8", "#F5C542"]
    )

    fig_accuracy.update_xaxes(tickformat=".1%")
    fig_accuracy.update_yaxes(tickformat=".1%")

    fig_accuracy.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#07111F")
    )

    st.plotly_chart(fig_accuracy, use_container_width=True)


def page_admin():
    render_page_title(
        "Admin",
        "Cập nhật kết quả trận đấu và chấm điểm lại toàn bộ dự đoán."
    )

    user = st.session_state["user"]

    if user["role"] != "admin":
        st.error("Bạn không có quyền truy cập trang này.")
        return

    matches = load_matches()
    users = load_users()
    predictions = load_predictions()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Matches", len(matches))

    with col2:
        st.metric("Users", len(users))

    with col3:
        st.metric("Predictions", len(predictions))

    st.markdown("---")

    with stylable_container(
        key="admin_update_card",
        css_styles="""
        {
            background: rgba(255,255,255,0.94);
            border: 1px solid rgba(15,23,42,0.08);
            border-radius: 22px;
            padding: 20px;
            box-shadow: 0 14px 34px rgba(15,23,42,0.08);
        }
        """
    ):
        st.subheader("Cập nhật kết quả trận đấu")

        if matches.empty:
            st.warning("Chưa có dữ liệu trận đấu.")
            return

        matches = matches.sort_values("kickoff_time_utc_dt")

        matches["match_label"] = matches.apply(
            lambda row: (
                f"#{row['match_id']} | "
                f"{row.get('kickoff_date_display_vietnam', row.get('kickoff_date_vietnam', ''))} "
                f"{row.get('kickoff_time_vietnam', '')} | "
                f"{row['home_team_name']} vs {row['away_team_name']} | "
                f"{row['round_name']}"
            ),
            axis=1
        )

        selected_label = st.selectbox(
            "Chọn trận cần cập nhật kết quả",
            matches["match_label"].tolist()
        )

        selected_match = matches[matches["match_label"] == selected_label].iloc[0]

        match_id = int(selected_match["match_id"])

        home_name = selected_match["home_team_name"]
        away_name = selected_match["away_team_name"]

        home_team_id = to_optional_int(selected_match.get("home_team_id"))
        away_team_id = to_optional_int(selected_match.get("away_team_id"))

        is_knockout = to_bool(selected_match.get("is_knockout"))

        st.markdown(f"### {home_name} vs {away_name}")

        st.caption(
            f"{selected_match.get('round_name')} | "
            f"{selected_match.get('kickoff_date_display_vietnam', selected_match.get('kickoff_date_vietnam', ''))} "
            f"{selected_match.get('kickoff_time_vietnam', '')}"
        )

        current_ft_home = to_optional_int(selected_match.get("score_ft_home"))
        current_ft_away = to_optional_int(selected_match.get("score_ft_away"))

        current_et_home = to_optional_int(selected_match.get("score_et_home"))
        current_et_away = to_optional_int(selected_match.get("score_et_away"))

        current_pen_home = to_optional_int(selected_match.get("score_pen_home"))
        current_pen_away = to_optional_int(selected_match.get("score_pen_away"))

        with st.form("update_match_result_form"):
            st.markdown("#### Tỉ số full-time")

            col_ft_home, col_ft_away = st.columns(2)

            with col_ft_home:
                score_ft_home = st.number_input(
                    f"FT - {home_name}",
                    min_value=0,
                    max_value=30,
                    value=current_ft_home if current_ft_home is not None else 0,
                    step=1
                )

            with col_ft_away:
                score_ft_away = st.number_input(
                    f"FT - {away_name}",
                    min_value=0,
                    max_value=30,
                    value=current_ft_away if current_ft_away is not None else 0,
                    step=1
                )

            score_et_home = None
            score_et_away = None
            score_pen_home = None
            score_pen_away = None
            winner_team_id = None

            if is_knockout:
                st.markdown("#### Knockout options")

                use_extra_time = st.checkbox(
                    "Trận có hiệp phụ",
                    value=current_et_home is not None and current_et_away is not None
                )

                if use_extra_time:
                    col_et_home, col_et_away = st.columns(2)

                    with col_et_home:
                        score_et_home = st.number_input(
                            f"ET - {home_name}",
                            min_value=0,
                            max_value=30,
                            value=current_et_home if current_et_home is not None else int(score_ft_home),
                            step=1
                        )

                    with col_et_away:
                        score_et_away = st.number_input(
                            f"ET - {away_name}",
                            min_value=0,
                            max_value=30,
                            value=current_et_away if current_et_away is not None else int(score_ft_away),
                            step=1
                        )

                final_home_for_game = score_et_home if score_et_home is not None else score_ft_home
                final_away_for_game = score_et_away if score_et_away is not None else score_ft_away

                if final_home_for_game == final_away_for_game:
                    use_penalties = st.checkbox(
                        "Trận phân định bằng penalty",
                        value=current_pen_home is not None and current_pen_away is not None
                    )

                    if use_penalties:
                        col_pen_home, col_pen_away = st.columns(2)

                        with col_pen_home:
                            score_pen_home = st.number_input(
                                f"Penalty - {home_name}",
                                min_value=0,
                                max_value=30,
                                value=current_pen_home if current_pen_home is not None else 0,
                                step=1
                            )

                        with col_pen_away:
                            score_pen_away = st.number_input(
                                f"Penalty - {away_name}",
                                min_value=0,
                                max_value=30,
                                value=current_pen_away if current_pen_away is not None else 0,
                                step=1
                            )

                    winner_options = {
                        home_name: home_team_id,
                        away_name: away_team_id
                    }

                    current_winner_team_id = to_optional_int(selected_match.get("winner_team_id"))
                    default_index = 0

                    if current_winner_team_id == away_team_id:
                        default_index = 1

                    selected_winner = st.radio(
                        "Chọn đội đi tiếp",
                        options=list(winner_options.keys()),
                        index=default_index,
                        horizontal=True
                    )

                    winner_team_id = winner_options[selected_winner]

            submitted = st.form_submit_button("Lưu kết quả và chấm điểm")

            if submitted:
                try:
                    update_match_result(
                        match_id=match_id,
                        score_ft_home=int(score_ft_home),
                        score_ft_away=int(score_ft_away),
                        score_et_home=int(score_et_home) if score_et_home is not None else None,
                        score_et_away=int(score_et_away) if score_et_away is not None else None,
                        score_pen_home=int(score_pen_home) if score_pen_home is not None else None,
                        score_pen_away=int(score_pen_away) if score_pen_away is not None else None,
                        winner_team_id=winner_team_id
                    )

                    st.success("Đã cập nhật kết quả và chấm điểm lại dự đoán.")
                    st.rerun()

                except ValueError as e:
                    st.error(str(e))

    st.markdown("---")

    if st.button("Chấm điểm lại toàn bộ dự đoán", use_container_width=True):
        score_all_predictions()
        st.success("Đã chấm điểm lại toàn bộ dự đoán.")


def render_footer():
    if FOOTER_PROJECT_URL:
        footer_link = f'<a href="{FOOTER_PROJECT_URL}" target="_blank">Project repo / portfolio</a>'
    else:
        footer_link = "World Cup Prediction Arena"

    st.markdown(
        f"""
        <div class="wc-footer">
            © 2026 Prediction Arena. {footer_link}
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# 11. MAIN APP
# ============================================================

def main():
    initialize_app_once()
    restore_user_from_cookie()

    # Nếu chưa đăng nhập, hiển thị trang đăng nhập.
    # Sau khi đăng nhập thành công, render_auth_page() sẽ set st.session_state["user"].
    # Khi đó app không stop nữa mà render tiếp màn hình chính trong cùng lượt chạy.
    if "user" not in st.session_state:
        render_auth_page()

        if "user" not in st.session_state:
            render_footer()
            st.stop()

    user = st.session_state["user"]

    with st.sidebar:
        render_sidebar_brand()

        st.markdown(f"Xin chào, **{user['display_name']}**")
        st.caption(f"Role: {user['role']}")

        if st.button("Đăng xuất", use_container_width=True):
            logout_user()

        st.markdown("---")

        pages = [
            "Lịch thi đấu & dự đoán",
            "Dự đoán của tôi",
            "Bảng xếp hạng",
            "Dashboard"
        ]

        if user["role"] == "admin":
            pages.append("Admin")

        if "selected_page" not in st.session_state:
            st.session_state["selected_page"] = "Lịch thi đấu & dự đoán"

        if st.session_state["selected_page"] not in pages:
            st.session_state["selected_page"] = "Lịch thi đấu & dự đoán"

        selected_page = st.radio(
            "Menu",
            pages,
            key="selected_page"
        )

        render_sidebar_footer()

    if selected_page == "Lịch thi đấu & dự đoán":
        page_matches()

    elif selected_page == "Dự đoán của tôi":
        page_my_predictions()

    elif selected_page == "Bảng xếp hạng":
        page_leaderboard()

    elif selected_page == "Dashboard":
        page_dashboard()

    elif selected_page == "Admin":
        page_admin()

    render_footer()

if __name__ == "__main__":
    main()
