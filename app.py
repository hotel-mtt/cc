# =============================================================================
#  AI CC Reporting System  v5
#  Run  : streamlit run app.py
#  Setup: pip install -r requirements.txt  |  .streamlit/secrets.toml
# =============================================================================
import streamlit as st
import hmac, hashlib, time
import openai, gspread, json, base64, re, io, warnings, httpx
from google.oauth2.service_account import Credentials
# from login_guard import require_login
from datetime import datetime
from PIL import Image

try:
    import pypdfium2 as _pdfium
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CC Reporting",
    page_icon="💳",
    layout="centered",
    initial_sidebar_state="collapsed",
)
 
# ── helpers ──────────────────────────────────────────────────────────────────
 
def _get_password() -> str:
    """Ambil password dari secrets, fallback ke session state (manual input)."""
    try:
        p = st.secrets["auth"]["password"]
        if p and "GANTI" not in p:
            return p
    except Exception:
        pass
    return st.session_state.get("_auth_pw_override", "")
 
def _ttl_hours() -> float:
    try:
        return float(st.secrets["auth"].get("session_ttl_hours", 8))
    except Exception:
        return 8.0
 
def _check_pw(candidate: str) -> bool:
    correct = _get_password()
    if not correct:
        return False
    # Constant-time comparison untuk mencegah timing attack
    return hmac.compare_digest(
        hashlib.sha256(candidate.encode()).digest(),
        hashlib.sha256(correct.encode()).digest(),
    )
 
def _is_session_valid() -> bool:
    login_time = st.session_state.get("_auth_login_time", 0)
    ttl = _ttl_hours() * 3600
    return (time.time() - login_time) < ttl
 
# ── login wall ────────────────────────────────────────────────────────────────
 
def require_login():
    """
    Panggil fungsi ini di paling atas app.py.
    Jika belum login / sesi kedaluwarsa → tampilkan form login & st.stop().
    Jika sudah login → lanjut eksekusi app normal.
    """
    # Sudah login dan sesi masih valid → langsung lanjut
    if st.session_state.get("_auth_ok") and _is_session_valid():
        _render_logout_button()
        return
 
    # Reset flag jika sesi kedaluwarsa
    if st.session_state.get("_auth_ok") and not _is_session_valid():
        st.session_state["_auth_ok"] = False
        st.session_state["_auth_login_time"] = 0
 
    # Render halaman login
    _render_login_page()
    st.stop()
 
 
def _render_logout_button():
    """Tombol logout kecil di sidebar (tidak mengganggu layout utama)."""
    with st.sidebar:
        st.markdown("---")
        if st.button("🔒 Logout", use_container_width=True, key="_auth_logout_btn"):
            st.session_state["_auth_ok"] = False
            st.session_state["_auth_login_time"] = 0
            st.rerun()
 
 
def _render_login_page():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
html,body,[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],.main{
    background:#ededed !important;
    font-family:'Inter',system-ui,sans-serif !important}
.main .block-container{
    padding:60px 12px 80px !important;
    max-width:420px !important;margin:0 auto !important}
[data-testid="stSidebar"],#MainMenu,footer,header,
[data-testid="stDecoration"]{display:none !important}
 
.login-card{
    background:#fff;border:1.5px solid #ddd;border-radius:24px;
    padding:36px 28px 28px;text-align:center}
.lc-icon{
    width:64px;height:64px;border-radius:18px;background:#191d3a;
    display:flex;align-items:center;justify-content:center;
    font-size:28px;margin:0 auto 18px}
.lc-title{font-size:22px;font-weight:800;color:#191d3a;margin-bottom:4px}
.lc-sub  {font-size:13px;color:#9e9e9e;margin-bottom:24px}
 
.stTextInput input{
    border-radius:12px !important;border:1.5px solid #ddd !important;
    background:#f7f7f7 !important;font-size:15px !important;
    color:#191d3a !important;padding:0 14px !important;
    height:48px !important;line-height:48px !important;
    text-align:center !important}
.stTextInput input:focus{
    border-color:#6398c8 !important;background:#fff !important;
    box-shadow:0 0 0 3px rgba(99,152,200,.18) !important;outline:none !important}
label[data-testid="stWidgetLabel"]{display:none !important}
 
.stButton>button{
    width:100% !important;border-radius:13px !important;
    height:50px !important;font-size:15px !important;
    font-weight:700 !important;border:none !important;
    background:#ffc744 !important;color:#191d3a !important;
    box-shadow:0 3px 10px rgba(255,199,68,.3) !important}
.stButton>button:hover{
    background:#fddb32 !important;
    box-shadow:0 4px 14px rgba(255,199,68,.4) !important}
 
.err-box{
    background:#fff1f2;border:1px solid #fecdd3;color:#9f1239;
    border-radius:12px;padding:11px 14px;font-size:13px;
    font-weight:600;margin-top:12px}
.hint{font-size:12px;color:#bbb;margin-top:16px}
</style>
""", unsafe_allow_html=True)
 
    st.markdown("""
<div class="login-card">
  <div class="lc-icon">💳</div>
  <div class="lc-title">CC Reporting</div>
  <div class="lc-sub">Masukkan password untuk melanjutkan</div>
</div>
""", unsafe_allow_html=True)
 
    # Spacer agar input muncul di tengah card secara visual
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
 
    pw_input = st.text_input(
        "Password", type="password",
        placeholder="••••••••",
        key="_auth_pw_input",
        label_visibility="collapsed",
    )
 
    login_btn = st.button("Masuk →", type="primary", use_container_width=True, key="_auth_login_btn")
 
    if login_btn or (pw_input and st.session_state.get("_auth_enter_pressed")):
        if not _get_password():
            st.markdown(
                '<div class="err-box">⚠ Password belum dikonfigurasi di secrets.toml</div>',
                unsafe_allow_html=True)
        elif _check_pw(pw_input):
            st.session_state["_auth_ok"]         = True
            st.session_state["_auth_login_time"] = time.time()
            st.rerun()
        else:
            st.markdown(
                '<div class="err-box">✕ Password salah. Coba lagi.</div>',
                unsafe_allow_html=True)
 
    ttl = _ttl_hours()
    st.markdown(
        f'<div class="hint">Sesi aktif selama {int(ttl)} jam setelah login.</div>',
        unsafe_allow_html=True)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── reset ── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body,[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],.main{
    background:#ededed !important;
    font-family:'Inter',system-ui,sans-serif !important}
.main .block-container{
    padding:12px 12px 80px !important;
    max-width:600px !important;margin:0 auto !important}
[data-testid="stSidebar"],#MainMenu,footer,header,
[data-testid="stDecoration"]{display:none !important}
*{font-family:'Inter',system-ui,sans-serif !important}

/* ── app header ── */
.app-header{
    background:#191d3a;border-radius:20px;padding:16px 18px;
    display:flex;align-items:center;gap:13px;margin-bottom:12px}
.ah-icon{
    width:46px;height:46px;border-radius:13px;background:#fddb32;
    display:flex;align-items:center;justify-content:center;
    font-size:22px;flex-shrink:0}
.ah-title{font-size:18px;font-weight:800;color:#fff;line-height:1.2}
.ah-sub{font-size:12px;color:#9e9e9e;margin-top:1px}
.ah-live{
    margin-left:auto;font-size:10px;font-weight:700;letter-spacing:.5px;
    background:#0f2310;color:#4ade80;border:1px solid #1e4620;
    padding:5px 11px;border-radius:20px;
    display:flex;align-items:center;gap:5px;white-space:nowrap;flex-shrink:0}
.ah-live::before{
    content:'';width:6px;height:6px;border-radius:50%;
    background:#4ade80;display:block}

/* ── nav ── */
.nb-wrap div[data-testid="stHorizontalBlock"]{gap:8px !important}
.nb-wrap button{
    height:76px !important;border-radius:16px !important;
    border:1.5px solid #d8d8d8 !important;background:#fff !important;
    color:#616161 !important;font-size:11px !important;font-weight:600 !important;
    padding:0 4px !important;white-space:pre-line !important;
    line-height:1.7 !important;box-shadow:none !important;width:100% !important}
.nb-wrap button:hover{
    border-color:#6398c8 !important;background:#e8f0fe !important;color:#191d3a !important}
.nb-wrap button[kind="primary"]{
    background:#191d3a !important;border-color:#191d3a !important;
    color:#fddb32 !important;box-shadow:0 3px 10px rgba(0,0,0,.22) !important}
.nb-wrap button[kind="primary"]:hover{background:#333 !important;border-color:#333 !important}

/* ── section label ── */
.sec-lbl{
    font-size:11px;font-weight:700;text-transform:uppercase;
    letter-spacing:.9px;color:#9e9e9e;margin:16px 0 10px;
    padding-bottom:8px;border-bottom:1.5px solid #ddd}

/* ── form labels ── */
label[data-testid="stWidgetLabel"] p,
label[data-testid="stWidgetLabel"]{
    font-size:12px !important;font-weight:600 !important;
    color:#191d3a !important;text-transform:none !important;
    letter-spacing:0 !important;margin-bottom:4px !important}

/* ── inputs ── */
.stTextInput input,.stNumberInput input{
    border-radius:12px !important;border:1.5px solid #ddd !important;
    background:#fff !important;font-size:15px !important;
    color:#191d3a !important;padding:0 14px !important;
    height:48px !important;line-height:48px !important;
    box-sizing:border-box !important;width:100% !important}
.stTextInput input:focus,.stNumberInput input:focus{
    border-color:#6398c8 !important;background:#fff !important;
    box-shadow:0 0 0 3px rgba(99,152,200,.18) !important;outline:none !important}
[data-testid="stSelectbox"]>div>div{
    border-radius:12px !important;border:1.5px solid #ddd !important;
    background:#fff !important;font-size:15px !important;
    color:#191d3a !important;
    height:48px !important;min-height:48px !important;
    display:flex !important;align-items:center !important;
    box-sizing:border-box !important}

/* ── widget wrappers: no clipping, no extra padding ── */
.stTextInput,.stSelectbox,[data-testid="stSelectbox"]{
    width:100% !important;min-width:0 !important}
div[data-testid="stWidgetLabel"]{
    overflow:visible !important}

/* ── column layout — pixel-perfect equal split ── */
[data-testid="stHorizontalBlock"]{
    gap:12px !important;
    align-items:flex-start !important;
    flex-wrap:nowrap !important;
    overflow:visible !important}
[data-testid="stHorizontalBlock"]>[data-testid="column"]{
    flex:1 1 0% !important;
    min-width:0 !important;
    max-width:none !important;
    overflow:visible !important;
    padding-bottom:4px !important}

/* make inner stVerticalBlock never clip its children */
[data-testid="stHorizontalBlock"]>[data-testid="column"]>div,
[data-testid="stHorizontalBlock"]>[data-testid="column"] [data-testid="stVerticalBlock"]{
    overflow:visible !important;
    width:100% !important;min-width:0 !important}

/* ── global buttons ── */
.stButton>button{
    width:100% !important;border-radius:13px !important;
    height:50px !important;font-size:14px !important;
    font-weight:700 !important;border:none !important}
.stButton>button[kind="primary"]{
    background:#ffc744 !important;color:#191d3a !important;
    box-shadow:0 3px 10px rgba(255,199,68,.3) !important}
.stButton>button[kind="primary"]:hover{
    background:#fddb32 !important;box-shadow:0 4px 14px rgba(255,199,68,.4) !important}
.stButton>button[kind="secondary"]{
    background:#fff !important;border:1.5px solid #ddd !important;color:#616161 !important}
.stButton>button[kind="secondary"]:hover{
    border-color:#6398c8 !important;background:#e8f0fe !important;color:#191d3a !important}

/* ── bulk action buttons ── */
.bb-wrap div[data-testid="stHorizontalBlock"] button{
    height:52px !important;border-radius:13px !important;
    font-size:14px !important;font-weight:700 !important}
.bb-wrap div[data-testid="stHorizontalBlock"] button[kind="primary"]{
    background:#ffc744 !important;color:#191d3a !important;border:none !important;
    box-shadow:0 3px 10px rgba(255,199,68,.3) !important}
.bb-wrap div[data-testid="stHorizontalBlock"] button[kind="primary"]:hover{
    background:#fddb32 !important}
.bb-wrap div[data-testid="stHorizontalBlock"] button[kind="secondary"]{
    background:#fff !important;border:1.5px solid #ddd !important;
    color:#616161 !important;font-size:20px !important;font-weight:400 !important}

/* ── link button ── */
[data-testid="stLinkButton"] a{
    background:#6398c8 !important;color:#fff !important;
    border-radius:13px !important;height:52px !important;
    font-size:14px !important;font-weight:700 !important;border:none !important;
    display:flex !important;align-items:center !important;
    justify-content:center !important;text-decoration:none !important}

/* ── checkbox ── */
[data-testid="stCheckbox"] label{
    font-size:14px !important;color:#616161 !important;font-weight:500 !important}

/* ── notices ── */
.notice{border-radius:12px;padding:11px 14px;font-size:13px;line-height:1.5;
    display:flex;align-items:flex-start;gap:8px;margin-bottom:12px}
.nok  {background:#f0fdf4;border:1px solid #86efac;color:#166534}
.nerr {background:#fff1f2;border:1px solid #fecdd3;color:#9f1239}
.ninfo{background:#e8f0fe;border:1px solid #6398c8;color:#1e3a6e}
.nwarn{background:#fffbeb;border:1px solid #fde68a;color:#92400e}

/* ── expedia banner ── */
.expedia-banner{
    background:#fff;border:1.5px solid #ddd;border-bottom:none;
    border-radius:16px 16px 0 0;padding:13px 16px;
    display:flex;align-items:center;justify-content:space-between;margin-top:16px}
.expedia-banner img{height:24px;width:auto;object-fit:contain}
.taap-pill{
    font-size:11px;font-weight:700;letter-spacing:.3px;
    color:#1e3a6e;background:#e8f0fe;border:1px solid #6398c8;
    padding:4px 11px;border-radius:20px;white-space:nowrap}

/* ── file uploader ──
   Strategy: sembunyikan label via CSS lapis demi lapis,
   gunakan label="" + label_visibility="collapsed" di Python.
   Tombol "Browse files" tetap muncul normal (tidak perlu dihide). ── */

/* Sembunyikan widget label (teks di atas komponen) */
[data-testid="stFileUploader"] [data-testid="stWidgetLabel"],
[data-testid="stFileUploader"] [data-testid="stWidgetLabel"] *{
    display:none !important}

/* Sembunyikan label HTML yang mungkin muncul di berbagai versi Streamlit */
[data-testid="stFileUploaderDropzoneInput"] + label,
[data-testid="stFileUploader"] > section > label,
[data-testid="stFileUploader"] label[for]{
    display:none !important;visibility:hidden !important;
    height:0 !important;overflow:hidden !important}

/* ── file uploader zone: sambung ke bawah banner, 
   tampilkan konten default Streamlit (drag&drop text + browse button) ── */
[data-testid="stFileUploader"]{margin-top:0 !important}
[data-testid="stFileUploader"]>div:first-child,
[data-testid="stFileUploader"] section{
    border:1.5px dashed #b8cde0 !important;
    border-top:none !important;
    border-radius:0 0 16px 16px !important;
    background:#f5f8fc !important;
    margin-top:0 !important;
    padding:28px 20px !important;
    min-height:120px !important}
[data-testid="stFileUploader"]>div:first-child:hover,
[data-testid="stFileUploader"] section:hover{
    border-color:#6398c8 !important;background:#e8f0fe !important}

/* Style tombol Browse agar konsisten */
[data-testid="stFileUploader"] button{
    border-radius:10px !important;
    border:1.5px solid #ddd !important;
    background:#fff !important;
    color:#191d3a !important;
    font-size:13px !important;
    font-weight:600 !important;
    padding:8px 18px !important;
    height:auto !important}
[data-testid="stFileUploader"] button:hover{
    border-color:#6398c8 !important;
    background:#e8f0fe !important}

/* Teks drag & drop */
[data-testid="stFileUploaderDropInstructions"]{
    font-size:14px !important;
    font-weight:600 !important;
    color:#191d3a !important}
[data-testid="stFileUploaderDropInstructions"] small,
[data-testid="stFileUploaderDropInstructions"] span{
    font-size:12px !important;
    color:#9e9e9e !important;
    font-weight:400 !important}

/* ── stat cards ── */
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px}
.stat-card{background:#fff;border:1.5px solid #ddd;border-radius:18px;padding:16px 15px}
.stat-val{font-size:22px;font-weight:800;color:#191d3a;line-height:1.1}
.stat-lbl{font-size:11px;color:#9e9e9e;margin-top:5px;font-weight:500}

/* ── progress bar ── */
.bulk-prog{background:#ddd;border-radius:99px;height:5px;overflow:hidden;margin-bottom:6px}
.bulk-prog-f{height:100%;background:#6398c8;border-radius:99px;transition:width .3s}
.bulk-prog-lbl{font-size:12px;color:#9e9e9e;text-align:center;margin-bottom:14px;font-weight:500}

/* ── summary card ── */
.bulk-sum{background:#fff;border:1.5px solid #ddd;border-radius:18px;
    padding:18px 16px;margin-bottom:16px}
.bulk-sum-ttl{font-size:11px;font-weight:700;text-transform:uppercase;
    letter-spacing:.9px;color:#9e9e9e;margin-bottom:14px}
.bulk-stats{display:grid;grid-template-columns:repeat(4,1fr);
    gap:8px;text-align:center;margin-bottom:14px}
.bs-val{font-size:24px;font-weight:800;color:#191d3a;line-height:1}
.bs-lbl{font-size:10px;color:#9e9e9e;margin-top:4px;font-weight:500}
.bs-g{color:#1e9e5a}.bs-r{color:#e53935}.bs-y{color:#e68900}
.bulk-bar{background:#e8e8e8;border-radius:99px;height:5px;overflow:hidden}
.bulk-bar-f{height:100%;background:#1e9e5a;border-radius:99px}
.bulk-pct{font-size:11px;color:#9e9e9e;text-align:right;margin-top:5px}

/* ── file result cards ── */
.file-item{background:#fff;border:1.5px solid #ddd;border-radius:15px;
    padding:13px 15px;margin-bottom:8px}
.fi-success{border-color:#6ee7b7 !important;background:#f0fdf4 !important}
.fi-error  {border-color:#fca5a5 !important;background:#fff1f2 !important}
.fi-skipped{border-color:#fcd34d !important;background:#fffde7 !important}
.fi-top{display:flex;align-items:center;gap:10px}
.fi-icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;
    justify-content:center;font-size:17px;flex-shrink:0}
.ic-ok{background:#dcfce7}.ic-err{background:#ffe4e6}
.ic-skip{background:#fef9c3}.ic-n{background:#ededed}
.fi-name{font-size:13px;font-weight:600;color:#191d3a;flex:1;
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fi-badge{font-size:10px;font-weight:700;padding:4px 10px;border-radius:20px;white-space:nowrap}
.fb-ok{background:#dcfce7;color:#166534}
.fb-err{background:#ffe4e6;color:#9f1239}
.fb-sk{background:#fef9c3;color:#7a5c00}
.fi-grid{margin-top:10px;padding-top:9px;border-top:1.5px solid #ededed;
    display:grid;grid-template-columns:1fr 1fr;gap:6px 14px}
.fi-kv{display:flex;gap:5px;align-items:baseline}
.fi-k{font-size:10px;font-weight:700;color:#9e9e9e;min-width:52px;
    flex-shrink:0;text-transform:uppercase;letter-spacing:.3px}
.fi-v{font-size:12px;font-weight:500;color:#191d3a;
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* ── settings rows ── */
.st-row{display:flex;align-items:center;gap:12px;background:#fff;
    border:1.5px solid #ddd;border-radius:15px;padding:14px 15px;margin-bottom:10px}
.st-icon{width:38px;height:38px;border-radius:11px;display:flex;align-items:center;
    justify-content:center;font-size:18px;flex-shrink:0}
.si-g{background:#f0fdf4}.si-r{background:#fff1f2}
.si-b{background:#e8f0fe}.si-y{background:#fffde7}
.st-body{flex:1;min-width:0}
.st-title{font-size:14px;font-weight:700;color:#191d3a;line-height:1}
.st-sub{font-size:12px;color:#9e9e9e;margin-top:3px}
.st-badge{display:inline-flex;align-items:center;font-size:11px;
    font-weight:700;padding:4px 12px;border-radius:20px;flex-shrink:0}
.bg{background:#f0fdf4;color:#166534;border:1px solid #86efac}
.br{background:#fff1f2;color:#9f1239;border:1px solid #fecdd3}
.by{background:#fffde7;color:#7a5c00;border:1px solid #fcd34d}
.conn-list{background:#fff;border:1.5px solid #ddd;border-radius:15px;
    overflow:hidden;margin-bottom:16px}
.conn-item{display:flex;align-items:center;gap:9px;padding:11px 15px;
    border-bottom:1px solid #ededed;font-size:13px}
.conn-item:last-child{border-bottom:none}
.cdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.about-box{background:#fff;border:1.5px solid #ddd;border-radius:18px;padding:16px 18px}
.about-ttl{font-size:15px;font-weight:800;color:#191d3a;margin-bottom:13px}
.about-r{display:flex;gap:10px;margin-bottom:7px}
.about-k{font-size:12px;font-weight:700;color:#191d3a;width:70px;flex-shrink:0}
.about-v{font-size:12px;color:#616161;line-height:1.5}

/* ── dataframe ── */
[data-testid="stDataFrame"]{border-radius:15px !important;border:1.5px solid #ddd !important;
    overflow:hidden !important;box-shadow:none !important}
[data-testid="stDataFrame"] table{font-size:13px !important}
[data-testid="stDataFrame"] th{background:#f5f8fc !important;color:#616161 !important;
    font-size:11px !important;font-weight:700 !important;text-transform:uppercase !important;
    letter-spacing:.5px !important;border-bottom:1.5px solid #ddd !important;padding:11px 13px !important}
[data-testid="stDataFrame"] td{font-size:13px !important;color:#191d3a !important;
    padding:10px 13px !important;border-bottom:1px solid #ededed !important}
[data-testid="stDataFrame"] tr:hover td{background:#f5f8fc !important}

/* ── metric ── */
[data-testid="stMetric"]{background:#fff !important;border:1.5px solid #ddd !important;
    border-radius:15px !important;padding:14px !important;margin-bottom:0 !important}
[data-testid="stMetricLabel"]{font-size:11px !important;font-weight:700 !important;
    color:#9e9e9e !important;text-transform:uppercase !important;letter-spacing:.6px !important}
[data-testid="stMetricValue"]{font-size:15px !important;font-weight:800 !important;
    color:#191d3a !important}

/* ── misc ── */
.stSpinner>div{border-top-color:#6398c8 !important}
.stExpander{border:1.5px solid #ddd !important;border-radius:14px !important;
    background:#fff !important;margin-bottom:10px !important}
details>summary{font-size:13px !important;color:#616161 !important}

/* ── mobile ── */
@media(max-width:480px){
    .main .block-container{padding:8px 8px 80px !important}
    .app-header{border-radius:16px;padding:12px 14px}
    .ah-icon{width:40px;height:40px;font-size:20px}
    .ah-title{font-size:16px}
    .nb-wrap button{height:68px !important;font-size:10px !important}
    .bs-val{font-size:20px}
    .stat-val{font-size:18px}}
</style>
""", unsafe_allow_html=True)


# ─── Key helpers ──────────────────────────────────────────────────────────────
def oai_key() -> str:
    try:
        k = st.secrets["openai"]["api_key"]
        if k and len(k) > 20 and "GANTI" not in k and "PASTE" not in k:
            return k
    except Exception:
        pass
    return st.session_state.get("oai_key", "")

def sheet_id() -> str:
    try:
        s = st.secrets["google_sheets"]["sheet_id"]
        if s and "GANTI" not in s:
            return s
    except Exception:
        pass
    return st.session_state.get("sheet_id", "")


# ─── Google Sheets ────────────────────────────────────────────────────────────
COLS = [
    "Timestamp Input","Supplier","Booking ID","Booking Date",
    "Issued Date","Hotel","Check-in","Room x Night",
    "Total (Rp)","Check-out","Guest Name","Kartu Kredit",
    "Issuer","PIC","No. BC","Nama Kegiatan","Catatan",
]

@st.cache_resource(ttl=300)
def ws():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"],
    )
    s = gspread.authorize(creds).open_by_key(sheet_id()).sheet1
    try:
        if not s.row_values(1) or s.cell(1,1).value != COLS[0]:
            s.insert_row(COLS, 1)
    except Exception:
        s.insert_row(COLS, 1)
    return s

def save_row(d: dict):
    ws().append_row(
        [d.get(k,"") for k in [
            "timestamp_input","supplier","booking_id","booked_on",
            "issued_on","hotel","checkin","qty","room","checkout",
            "name","card","issuer","pic","no_bc","nama_kegiatan","notes",
        ]],
        value_input_option="USER_ENTERED",
    )

def load_rows() -> list:
    return ws().get_all_records()


# ─── Duplicate check ──────────────────────────────────────────────────────────
def _ns(v) -> str: return str(v or "").strip().lower()
def _ni(v) -> int:
    try: return int(float(str(v).replace(",","").replace(".","") or 0))
    except: return 0

def check_duplicate(new: dict, rows: list) -> tuple:
    bid = _ns(new.get("booking_id"))
    for r in rows:
        if bid and bid == _ns(r.get("Booking ID")):
            return True, "Booking ID sudah terdaftar", r
        sc = sum([
            _ns(new.get("hotel"))   == _ns(r.get("Hotel")),
            _ns(new.get("checkin")) == _ns(r.get("Check-in")),
            _ns(new.get("name"))    == _ns(r.get("Guest Name")),
            _ni(new.get("room"))    == _ni(r.get("Total (Rp)")),
        ])
        if sc >= 3:
            return True, "Kemungkinan duplikat (kesamaan tinggi)", r
    return False, "", None


# ─── PDF helpers ──────────────────────────────────────────────────────────────
def pdf_images(data: bytes) -> list:
    if not _PDF_OK: raise RuntimeError("pypdfium2 not installed")
    doc = _pdfium.PdfDocument(data)
    return [doc[i].render(scale=2.0).to_pil() for i in range(len(doc))]

def pdf_text(data: bytes) -> str:
    if not _PDF_OK or not data: return ""
    try:
        doc, parts = _pdfium.PdfDocument(data), []
        for i in range(len(doc)):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                parts.append(doc[i].get_textpage().get_text_bounded())
        return "\n".join(parts).strip()
    except: return ""

def to_b64(img: Image.Image) -> tuple:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"


# ─── AI parser ────────────────────────────────────────────────────────────────
_SYS = """You are a corporate hotel expense AI parser for credit card reporting.
Parse any document: Expedia TAAP receipt, Mitra Tours itinerary, hotel invoice
(IHG, Marriott, Hilton, etc.), screenshot, or free text.
Return ONLY a valid JSON object — no markdown, no explanation.

Keys:
- supplier   : string  — platform/OTA/hotel brand from document header
                         e.g. "Expedia TAAP", "Mitra Tours & Travel", "IHG", "Marriott"
- booking_id : string  — itinerary/booking/confirmation number
- booked_on  : string  — booking date YYYY-MM-DD
- issued_on  : string  — issued/receipt date YYYY-MM-DD
- hotel      : string  — full hotel name as written
- checkin    : string  — check-in date YYYY-MM-DD
- checkout   : string  — check-out date YYYY-MM-DD
- qty        : string  — rooms and nights e.g. "2 rooms x 2 nights"
- room       : integer — TOTAL amount charged to the credit card (IDR/Rp).
                         Priority order for finding this value:
                         1. "Subtotal paid to Expedia" line  → use that amount
                         2. Grand "Total" line (bottom of document)
                         3. Sum of all "Total Room 1" + "Total Room 2" + ... lines
                         4. Sum of all "Room 1" + "Room 2" + ... subtotal lines
                         NEVER use per-night rates, Miscellaneous Tax alone, or
                         resort fee alone — always use the final billed total.
- name       : string  — primary guest name (first traveller listed)
- card       : string  — e.g. "Visa •••• 0191" or "MasterCard •••• 4467", empty if absent
- notes      : string  — room type(s), number of rooms, tax details, confirmation #

Rules:
1. Dates: any format → YYYY-MM-DD.
   "Mon, 11 May 2026" → "2026-05-11"  |  "13 May 2026" → "2026-05-13"
2. Amounts: strip IDR/Rp/USD/$/commas → plain integer, no decimals.
   "IDR 24,007,312.00" → 24007312
3. room = the single final total the credit card was charged.
   For multi-room hotel invoices: use the grand Total at the bottom.
   For Expedia TAAP: use "Subtotal paid to Expedia" line.
4. qty: count distinct rooms × nights.
   "2 rooms x 2 nights" if 2 rooms checked in same dates.
5. Missing field → "" for strings, 0 for integers."""

def ai_parse(text: str = "", images: list = None) -> tuple:
    key = oai_key()
    if not key:
        raise ValueError("OpenAI API key belum diisi — buka tab Pengaturan.")
    content = []
    if images:
        for b64, mime in images:
            content.append({"type":"image_url",
                            "image_url":{"url":f"data:{mime};base64,{b64}","detail":"high"}})
    content.append({"type":"text",
                    "text": text if text else "Extract all structured data from this document."})
    _client = httpx.Client()
    resp = openai.OpenAI(api_key=key, http_client=_client).chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":_SYS},{"role":"user","content":content}],
        temperature=0.0, max_tokens=800,
    )
    raw = resp.choices[0].message.content
    m   = re.search(r"\{[\s\S]*\}", raw)
    if not m: raise ValueError("Format AI tidak valid — JSON tidak ditemukan.")
    return json.loads(m.group()), raw


# ─── UI utilities ─────────────────────────────────────────────────────────────
def fmt(v) -> str:
    try:    return "Rp {:,}".format(int(float(v or 0))).replace(",",".")
    except: return str(v) if v else "—"

def now_ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")

def notice(kind: str, msg: str):
    icons = {"ok":"✓","err":"✕","info":"ℹ","warn":"⚠"}
    cls   = {"ok":"nok","err":"nerr","info":"ninfo","warn":"nwarn"}
    st.markdown(
        f'<div class="notice {cls[kind]}"><b>{icons[kind]}</b>&ensp;{msg}</div>',
        unsafe_allow_html=True)


# ─── Session state ────────────────────────────────────────────────────────────
_DEF = {
    "tab":                "input",
    "bulk_results":       [],
    "bulk_saved_count":   0,
    "oai_key":            "",
    "sheet_id":           "1nvgMCmo1EJtbCAt0db_OizvPYDvaEzphKhwzBJ-3X_g",
    "last_issuer":        "",
    "last_pic":           "",
    "last_no_bc":         "",
    "last_nama_kegiatan": "",
}
for _k, _v in _DEF.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

def reset_bulk():
    st.session_state["bulk_results"]     = []
    st.session_state["bulk_saved_count"] = 0


# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <div class="ah-icon">💳</div>
  <div>
    <div class="ah-title">CC Reporting</div>
    <div class="ah-sub">AI Expense Manager</div>
  </div>
  <div class="ah-live">LIVE</div>
</div>
""", unsafe_allow_html=True)


# ─── Navigation ───────────────────────────────────────────────────────────────
_cur = st.session_state["tab"]
_NL  = "\n"

st.markdown('<div class="nb-wrap">', unsafe_allow_html=True)
_na, _nb, _nc, _nd = st.columns(4)
with _na:
    if st.button(f"⬆️{_NL}Input", key="nb_input", use_container_width=True,
                 type="primary" if _cur == "input" else "secondary"):
        st.session_state["tab"] = "input"; st.rerun()
with _nb:
    if st.button(f"📊{_NL}Dashboard", key="nb_dash", use_container_width=True,
                 type="primary" if _cur == "dashboard" else "secondary"):
        st.session_state["tab"] = "dashboard"; st.rerun()
with _nc:
    if st.button(f"🕐{_NL}Riwayat", key="nb_log", use_container_width=True,
                 type="primary" if _cur == "log" else "secondary"):
        st.session_state["tab"] = "log"; st.rerun()
with _nd:
    if st.button(f"⚙️{_NL}Pengaturan", key="nb_set", use_container_width=True,
                 type="primary" if _cur == "settings" else "secondary"):
        st.session_state["tab"] = "settings"; st.rerun()
st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — INPUT
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state["tab"] == "input":

    if not oai_key():
        notice("err", "OpenAI API key belum diisi — buka tab <b>Pengaturan</b>.")
        st.stop()
    if not _PDF_OK:
        notice("warn", "pypdfium2 belum terinstall — PDF nonaktif. "
               "Jalankan: <code>pip install pypdfium2==4.30.0</code>")

    # ── Issuer & PIC ──────────────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl">Issuer &amp; PIC</div>', unsafe_allow_html=True)

    _ISSUERS = [
        "","Ade Puspitasari","Farras Mahmud","Meijika",
        "Muhammad Geraldi Jagaddhita","Nur Anissa Firda Aulia",
        "Riega Wisudhantara","Rifyal Tumber","Selvy Anggraini",
        "Shaiful Baldy","Veronica Novi Heri","Rida Manora Nasution",
    ]
    _li = st.session_state.get("last_issuer","")
    _bi = _ISSUERS.index(_li) if _li in _ISSUERS else 0

    _ca, _cb = st.columns(2)
    bulk_issuer = _ca.selectbox(
        "Issuer *", options=_ISSUERS, index=_bi,
        format_func=lambda x: "— Pilih Issuer —" if x == "" else x,
        key="bulk_issuer")
    bulk_pic = _cb.text_input(
        "PIC *", value=st.session_state.get("last_pic",""),
        placeholder="Nama penanggung jawab", key="bulk_pic")

    _cc, _cd = st.columns(2)
    bulk_no_bc = _cc.text_input(
        "No. BC", value=st.session_state.get("last_no_bc",""),
        placeholder="Nomor BC (opsional)", key="bulk_no_bc")
    bulk_nama_kegiatan = _cd.text_input(
        "Nama Kegiatan", value=st.session_state.get("last_nama_kegiatan",""),
        placeholder="Nama kegiatan (opsional)", key="bulk_nama_kegiatan")

    # ── Expedia banner ────────────────────────────────────────────────────────
    st.markdown("""
<div class="expedia-banner">
  <img src="https://www.expedia.com/newsroom/wp-content/uploads/2023/07/BEX_Logo_Horizontal_CMYK_FullColorDarkBlue--1024x199.jpg"
    alt="Expedia TAAP" onerror="this.parentElement.style.display='none'">
  <span class="taap-pill">TAAP + Mitra Tours</span>
</div>
""", unsafe_allow_html=True)

    # ── File uploader ─────────────────────────────────────────────────────────
    # label="" + label_visibility="collapsed" adalah kombinasi paling aman.
    # Jangan beri teks pada label karena Streamlit bisa render teks itu
    # sebagai teks di dalam tombol "Browse files" pada versi tertentu.
    _ftypes = ["jpg","jpeg","png","webp"] + (["pdf"] if _PDF_OK else [])
    bulk_files = st.file_uploader(
        label="",
        type=_ftypes,
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="bulk_uf",
    )

    _n = len(bulk_files) if bulk_files else 0
    if _n:
        notice("info", f"<b>{_n} file</b> dipilih dan siap diproses.")

    skip_dup = st.checkbox(
        "Lewati duplikat — jangan simpan jika booking sudah ada",
        value=True, key="bulk_skip_dup")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Action buttons ────────────────────────────────────────────────────────
    st.markdown('<div class="bb-wrap">', unsafe_allow_html=True)
    _ba, _bb = st.columns([4, 1])
    _run   = _ba.button(
        "⚡  Proses & Simpan Semua", type="primary",
        use_container_width=True,
        disabled=(not _n or not bulk_issuer or not bulk_pic.strip()),
        key="bulk_run")
    _clear = _bb.button("🗑", type="secondary",
        use_container_width=True, key="bulk_clear")
    st.markdown('</div>', unsafe_allow_html=True)

    if _clear:
        reset_bulk(); st.rerun()

    # ── Process ───────────────────────────────────────────────────────────────
    if _run:
        if not bulk_issuer:
            notice("err", "Pilih Issuer terlebih dahulu.")
        elif not bulk_pic.strip():
            notice("err", "Isi PIC terlebih dahulu.")
        else:
            st.session_state["last_issuer"]        = bulk_issuer
            st.session_state["last_pic"]           = bulk_pic
            st.session_state["last_no_bc"]         = bulk_no_bc
            st.session_state["last_nama_kegiatan"] = bulk_nama_kegiatan
            reset_bulk()

            try:    _existing = load_rows()
            except: _existing = []

            _all_res, _saved_run = [], 0
            _slot = st.empty()

            for _idx, _uf in enumerate(bulk_files):
                _pct = int(_idx / _n * 100)
                _slot.markdown(
                    '<div class="bulk-prog">'
                    '<div class="bulk-prog-f" style="width:' + str(_pct) + '%"></div></div>'
                    '<div class="bulk-prog-lbl">Memproses '
                    + str(_idx+1) + ' / ' + str(_n)
                    + ' &nbsp;·&nbsp; ' + _uf.name + '</div>',
                    unsafe_allow_html=True)

                _res = {"file":_uf.name,"status":"error","parsed":{},"err":""}
                try:
                    _raw = _uf.read()
                    _imgs, _txt = [], ""
                    if _uf.name.lower().endswith(".pdf"):
                        if not _PDF_OK: raise RuntimeError("pypdfium2 tidak terinstall")
                        _pages = pdf_images(_raw)
                        _imgs  = [to_b64(pg) for pg in _pages]
                        _txt   = pdf_text(_raw)
                    else:
                        _io = Image.open(io.BytesIO(_raw)).convert("RGB")
                        _b, _m = to_b64(_io)
                        _imgs  = [(_b, _m)]

                    _comb = ("EXTRACTED PDF TEXT (authoritative):\n" + _txt) if _txt else ""
                    _parsed, _ = ai_parse(_comb, _imgs or None)
                    _parsed["timestamp_input"] = now_ts()

                    _is_dup, _why, _ = check_duplicate(
                        {"booking_id": _parsed.get("booking_id"),
                         "hotel":      _parsed.get("hotel"),
                         "checkin":    _parsed.get("checkin"),
                         "name":       _parsed.get("name"),
                         "room":       _parsed.get("room")},
                        _existing)

                    if _is_dup and skip_dup:
                        _res.update(status="skipped", parsed=_parsed, err=_why)
                    else:
                        save_row({
                            "timestamp_input": _parsed.get("timestamp_input",""),
                            "supplier":        _parsed.get("supplier",""),
                            "booking_id":      _parsed.get("booking_id",""),
                            "booked_on":       _parsed.get("booked_on",""),
                            "issued_on":       _parsed.get("issued_on",""),
                            "hotel":           _parsed.get("hotel",""),
                            "checkin":         _parsed.get("checkin",""),
                            "qty":             _parsed.get("qty",""),
                            "room":            _parsed.get("room",0),
                            "checkout":        _parsed.get("checkout",""),
                            "name":            _parsed.get("name",""),
                            "card":            _parsed.get("card",""),
                            "issuer":          bulk_issuer,
                            "pic":             bulk_pic,
                            "no_bc":           bulk_no_bc.strip() or _parsed.get("no_bc",""),
                            "nama_kegiatan":   bulk_nama_kegiatan.strip() or _parsed.get("nama_kegiatan",""),
                            "notes":           _parsed.get("notes",""),
                        })
                        _res.update(status="success", parsed=_parsed)
                        _saved_run += 1
                        _existing.append({
                            "Booking ID": _parsed.get("booking_id",""),
                            "Hotel":      _parsed.get("hotel",""),
                            "Check-in":   _parsed.get("checkin",""),
                            "Guest Name": _parsed.get("name",""),
                            "Total (Rp)": _parsed.get("room",0),
                        })
                except Exception as _exc:
                    _res.update(err=str(_exc)[:140])
                _all_res.append(_res)

            _slot.empty()
            st.session_state["bulk_results"]     = _all_res
            st.session_state["bulk_saved_count"] = _saved_run
            st.rerun()

    # ── Results ───────────────────────────────────────────────────────────────
    _results = st.session_state.get("bulk_results", [])

    if _results:
        _ok   = sum(1 for r in _results if r["status"] == "success")
        _err  = sum(1 for r in _results if r["status"] == "error")
        _skip = sum(1 for r in _results if r["status"] == "skipped")
        _tot  = len(_results)
        _pct  = int(_ok / _tot * 100) if _tot else 0

        st.markdown(
            '<div class="bulk-sum"><div class="bulk-sum-ttl">Hasil Proses Batch</div>'
            '<div class="bulk-stats">'
            + f'<div><div class="bs-val">{_tot}</div><div class="bs-lbl">Total</div></div>'
            + f'<div><div class="bs-val bs-g">{_ok}</div><div class="bs-lbl">Tersimpan</div></div>'
            + f'<div><div class="bs-val bs-r">{_err}</div><div class="bs-lbl">Gagal</div></div>'
            + f'<div><div class="bs-val bs-y">{_skip}</div><div class="bs-lbl">Duplikat</div></div>'
            + '</div>'
            + f'<div class="bulk-bar"><div class="bulk-bar-f" style="width:{_pct}%"></div></div>'
            + f'<div class="bulk-pct">{_pct}% berhasil tersimpan</div></div>',
            unsafe_allow_html=True)

        st.markdown('<div class="sec-lbl">Detail per file</div>', unsafe_allow_html=True)

        for _r in _results:
            _s, _p = _r["status"], _r.get("parsed", {})
            _fn = _r["file"]
            _fi = "&#128196;" if _fn.lower().endswith(".pdf") else "&#128247;"
            _ic = {"success":"ic-ok","error":"ic-err","skipped":"ic-skip"}.get(_s,"ic-n")
            _bc = {"success":"fb-ok","error":"fb-err","skipped":"fb-sk"}.get(_s,"fb-ok")
            _sy = {"success":"&#10003;","error":"&#10005;","skipped":"&#9888;"}.get(_s,"")
            _lb = {"success":"Tersimpan","error":"Gagal","skipped":"Duplikat"}.get(_s,_s)
            _wc = {"success":"fi-success","error":"fi-error","skipped":"fi-skipped"}.get(_s,"")

            if _p and _s in ("success","skipped"):
                _dw = (
                    '<div style="margin-top:8px;font-size:12px;color:#7a5c00;'
                    'background:#fef9c3;padding:6px 10px;border-radius:9px">&#9888; '
                    + _r.get("err","Duplikat") + '</div>'
                ) if _s == "skipped" else ""
                _det = (
                    '<div class="fi-grid">'
                    + '<div class="fi-kv"><span class="fi-k">Hotel</span><span class="fi-v">'      + (_p.get("hotel")       or "—") + '</span></div>'
                    + '<div class="fi-kv"><span class="fi-k">Total</span><span class="fi-v">'      + fmt(_p.get("room",0))          + '</span></div>'
                    + '<div class="fi-kv"><span class="fi-k">Tamu</span><span class="fi-v">'       + (_p.get("name")        or "—") + '</span></div>'
                    + '<div class="fi-kv"><span class="fi-k">Booking ID</span><span class="fi-v">' + (_p.get("booking_id")  or "—") + '</span></div>'
                    + '<div class="fi-kv"><span class="fi-k">Check-in</span><span class="fi-v">'   + (_p.get("checkin")     or "—") + '</span></div>'
                    + '<div class="fi-kv"><span class="fi-k">Supplier</span><span class="fi-v">'   + (_p.get("supplier")    or "—") + '</span></div>'
                    + '</div>' + _dw)
            elif _r.get("err"):
                _det = (
                    '<div class="fi-grid" style="grid-template-columns:1fr">'
                    '<div class="fi-kv"><span class="fi-k">Error</span>'
                    '<span class="fi-v" style="color:#e53935;white-space:normal">'
                    + _r["err"] + '</span></div></div>')
            else:
                _det = ""

            st.markdown(
                '<div class="file-item ' + _wc + '">'
                '<div class="fi-top">'
                '<div class="fi-icon ' + _ic + '">' + _fi + '</div>'
                '<div class="fi-name">' + _fn + '</div>'
                '<span class="fi-badge ' + _bc + '">' + _sy + ' ' + _lb + '</span>'
                '</div>' + _det + '</div>',
                unsafe_allow_html=True)

        _sid = sheet_id()
        if _sid and _ok:
            st.link_button(
                f"📊  Buka Google Sheets ({_ok} baris baru tersimpan)",
                f"https://docs.google.com/spreadsheets/d/{_sid}",
                use_container_width=True)
        if _err:
            notice("warn", f"{_err} file gagal. Periksa kualitas file dan coba lagi.")


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["tab"] == "dashboard":
    import pandas as pd

    _cr, _cb2 = st.columns([3,1])
    _cr.markdown('<div class="sec-lbl" style="margin-top:6px">Ringkasan</div>',
                 unsafe_allow_html=True)
    if _cb2.button("↻ Refresh", type="secondary", use_container_width=True, key="dash_ref"):
        st.cache_resource.clear(); st.rerun()

    try:
        with st.spinner("Memuat data..."):
            rows = load_rows()

        if not rows:
            notice("info","Belum ada transaksi. Tambahkan melalui tab Input.")
        else:
            df = pd.DataFrame(rows)
            if "Total (Rp)" in df.columns:
                df["Total (Rp)"] = pd.to_numeric(df["Total (Rp)"],errors="coerce").fillna(0)

            tn  = len(df)
            tr  = df["Total (Rp)"].sum() if "Total (Rp)" in df.columns else 0
            avg = tr / tn if tn else 0
            tds = datetime.now().strftime("%d/%m/%Y")
            tdc = int(df["Timestamp Input"].astype(str).str.startswith(tds).sum()) \
                  if "Timestamp Input" in df.columns else 0

            st.markdown(
                '<div class="stat-grid">'
                f'<div class="stat-card"><div class="stat-val">{tn}</div><div class="stat-lbl">Total transaksi</div></div>'
                f'<div class="stat-card"><div class="stat-val" style="font-size:17px">{fmt(tr)}</div><div class="stat-lbl">Total pengeluaran</div></div>'
                f'<div class="stat-card"><div class="stat-val" style="font-size:17px">{fmt(avg)}</div><div class="stat-lbl">Rata-rata</div></div>'
                f'<div class="stat-card"><div class="stat-val">{tdc}</div><div class="stat-lbl">Input hari ini</div></div>'
                '</div>',
                unsafe_allow_html=True)

            if "Kartu Kredit" in df.columns and "Total (Rp)" in df.columns:
                _cc = df[df["Kartu Kredit"].astype(str).str.strip().ne("")]
                if not _cc.empty:
                    st.markdown('<div class="sec-lbl">Kartu Kredit</div>', unsafe_allow_html=True)
                    _grp = (_cc.groupby("Kartu Kredit")["Total (Rp)"]
                            .sum().sort_values(ascending=False).reset_index())
                    _grp.columns = ["label","val"]
                    _tot = _grp["val"].sum()
                    _cnt = _cc.groupby("Kartu Kredit").size()
                    _h = ""
                    for _, _row in _grp.iterrows():
                        _p = _row["val"]/_tot*100 if _tot else 0
                        _a = "Rp {:,.0f}".format(_row["val"]).replace(",",".")
                        _c = int(_cnt.get(_row["label"],0))
                        _h += (
                            f'<div style="padding:12px 0;border-bottom:1.5px solid #ededed">'
                            f'<div style="display:flex;justify-content:space-between;margin-bottom:6px">'
                            f'<span style="font-size:14px;font-weight:600;color:#191d3a">{_row["label"]}</span>'
                            f'<span style="font-size:14px;font-weight:700;color:#191d3a">{_a}</span></div>'
                            f'<div style="display:flex;align-items:center;gap:10px">'
                            f'<div style="flex:1;background:#e8e8e8;border-radius:4px;height:4px">'
                            f'<div style="width:{int(_p)}%;background:#6398c8;border-radius:4px;height:4px"></div></div>'
                            f'<span style="font-size:12px;color:#9e9e9e;white-space:nowrap">'
                            f'{_p:.1f}% · {_c} transaksi</span></div></div>')
                    st.markdown(
                        f'<div style="background:#fff;border:1.5px solid #ddd;'
                        f'border-radius:18px;padding:4px 16px">{_h}</div>',
                        unsafe_allow_html=True)

            st.markdown('<div class="sec-lbl">Data transaksi</div>', unsafe_allow_html=True)

            srch = st.text_input("",placeholder="🔍  Cari hotel / tamu / booking ID...",
                                  label_visibility="collapsed", key="srch")
            if srch:
                df = df[df.apply(
                    lambda r: r.astype(str).str.contains(srch,case=False,na=False).any(),axis=1)]

            _disp = df.iloc[::-1].reset_index(drop=True).copy()
            if "Booking ID" in _disp.columns:
                _disp["Booking ID"] = _disp["Booking ID"].astype(str)
            _cfg = {}
            if "Booking ID"      in _disp.columns: _cfg["Booking ID"]      = st.column_config.TextColumn("Booking ID")
            if "Total (Rp)"      in _disp.columns: _cfg["Total (Rp)"]      = st.column_config.NumberColumn("Total (Rp)", format="Rp %d")
            if "Room x Night"    in _disp.columns: _cfg["Room x Night"]    = st.column_config.TextColumn("Room × Night")
            if "Timestamp Input" in _disp.columns: _cfg["Timestamp Input"] = st.column_config.TextColumn("Timestamp")
            st.dataframe(_disp, use_container_width=True, height=360,
                         column_config=_cfg, hide_index=True)

    except Exception as e:
        notice("err", str(e))
        notice("info","Konfigurasi Google Sheets di tab Pengaturan.")


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — RIWAYAT
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["tab"] == "log":
    try:
        with st.spinner("Memuat data..."):
            rows = load_rows()
        if not rows:
            notice("info","Belum ada data transaksi.")
        else:
            import pandas as pd
            df_log = pd.DataFrame(rows)
            def _pts(v):
                try:    return pd.to_datetime(str(v), dayfirst=True)
                except: return pd.NaT
            df_log["_ts"] = df_log["Timestamp Input"].apply(_pts)
            df_log = df_log.sort_values("_ts", ascending=False).reset_index(drop=True)
            st.markdown(
                f'<div class="sec-lbl" style="margin-top:6px">Riwayat — {len(df_log)} transaksi</div>',
                unsafe_allow_html=True)
            _log = df_log[["Timestamp Input","Booking ID","Issuer"]].copy()
            _log["Booking ID"] = _log["Booking ID"].astype(str)
            st.dataframe(_log, use_container_width=True, hide_index=True,
                column_config={
                    "Timestamp Input": st.column_config.TextColumn("Timestamp", width="medium"),
                    "Booking ID":      st.column_config.TextColumn("Booking ID", width="medium"),
                    "Issuer":          st.column_config.TextColumn("Issuer", width="medium"),
                })
    except Exception as e:
        notice("err", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — PENGATURAN
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["tab"] == "settings":

    oai_ok = False
    try:
        k = st.secrets["openai"]["api_key"]
        if k and len(k) > 20 and "GANTI" not in k and "PASTE" not in k:
            oai_ok = True
    except: pass

    st.markdown('<div class="sec-lbl" style="margin-top:6px">Cek Koneksi</div>',
                unsafe_allow_html=True)

    if st.button("🔍  Cek Koneksi", type="primary", use_container_width=True):
        _rl = []
        _ol = bool(oai_key())
        _rl.append((_ol,"OpenAI gpt-4o-mini","Terhubung" if _ol else "Key tidak ditemukan"))
        _sc = False
        try:
            if st.secrets["google_sheets"]["sheet_id"] and \
               st.secrets["gcp_service_account"]["client_email"]: _sc = True
        except: pass
        if _sc:
            try: ws(); _rl.append((True,"Google Sheets","Terhubung"))
            except Exception as e: _rl.append((False,"Google Sheets",str(e)[:55]))
        else:
            _rl.append((False,"Google Sheets","Belum dikonfigurasi"))
        _rl.append((_PDF_OK,"PDF Upload","pypdfium2 aktif" if _PDF_OK else "pypdfium2 tidak terinstall"))

        _it = ""
        for _ok2,_sv,_ms in _rl:
            _cl = "#1e9e5a" if _ok2 else "#e53935"
            _it += (f'<div class="conn-item">'
                    f'<div class="cdot" style="background:{_cl}"></div>'
                    f'<span style="font-weight:700;color:{_cl}">{"✓" if _ok2 else "✕"} {_sv}</span>'
                    f'&ensp;<span style="color:#9e9e9e">{_ms}</span></div>')
        st.markdown(f'<div class="conn-list">{_it}</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-lbl">Status Sistem</div>', unsafe_allow_html=True)

    if oai_ok:
        st.markdown("""<div class="st-row"><div class="st-icon si-g">🤖</div>
<div class="st-body"><div class="st-title">OpenAI gpt-4o-mini</div>
<div class="st-sub">API key dikonfigurasi via secrets.toml</div></div>
<span class="st-badge bg">✓ Aktif</span></div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="st-row"><div class="st-icon si-y">🤖</div>
<div class="st-body"><div class="st-title">OpenAI gpt-4o-mini</div>
<div class="st-sub">API key belum dikonfigurasi</div></div>
<span class="st-badge by">⚠ Belum</span></div>""", unsafe_allow_html=True)
        nk = st.text_input("OpenAI API Key",
            value=st.session_state.get("oai_key",""), type="password",
            placeholder="sk-proj-...", label_visibility="collapsed")
        if nk != st.session_state.get("oai_key",""):
            st.session_state["oai_key"] = nk; st.rerun()
        if st.session_state.get("oai_key",""):
            notice("ok","Key aktif untuk sesi ini.")

    sh_ok = False
    try:
        if st.secrets["google_sheets"]["sheet_id"] and \
           st.secrets["gcp_service_account"]["client_email"]: sh_ok = True
    except: pass

    if sh_ok:
        st.markdown("""<div class="st-row"><div class="st-icon si-g">📊</div>
<div class="st-body"><div class="st-title">Google Sheets</div>
<div class="st-sub">Terhubung via secrets.toml</div></div>
<span class="st-badge bg">✓ Aktif</span></div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="st-row"><div class="st-icon si-y">📊</div>
<div class="st-body"><div class="st-title">Google Sheets</div>
<div class="st-sub">Belum dikonfigurasi</div></div>
<span class="st-badge by">⚠ Belum</span></div>""", unsafe_allow_html=True)
        notice("warn","Isi <code>.streamlit/secrets.toml</code> sesuai README.")
        ns = st.text_input("Sheet ID", value=st.session_state.get("sheet_id",""),
            label_visibility="collapsed", placeholder="1nvgMCmo...")
        if ns != st.session_state.get("sheet_id",""):
            st.session_state["sheet_id"] = ns

    if _PDF_OK:
        st.markdown("""<div class="st-row"><div class="st-icon si-b">📄</div>
<div class="st-body"><div class="st-title">PDF Upload</div>
<div class="st-sub">pypdfium2 terinstall</div></div>
<span class="st-badge bg">✓ Aktif</span></div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="st-row"><div class="st-icon si-r">📄</div>
<div class="st-body"><div class="st-title">PDF Upload</div>
<div class="st-sub">pypdfium2 tidak terinstall</div></div>
<span class="st-badge br">✕ Nonaktif</span></div>""", unsafe_allow_html=True)
        notice("err","Jalankan: <code>pip install pypdfium2==4.30.0</code>")

    st.markdown('<div class="sec-lbl">Tentang Aplikasi</div>', unsafe_allow_html=True)
    st.markdown("""
<div class="about-box">
  <div class="about-ttl">AI CC Reporting System v5</div>
  <div class="about-r"><div class="about-k">Input</div>
    <div class="about-v">PDF · JPG · PNG — bulk upload banyak file sekaligus</div></div>
  <div class="about-r"><div class="about-k">Output</div>
    <div class="about-v">Google Sheets — 17 kolom terstruktur</div></div>
  <div class="about-r"><div class="about-k">Dokumen</div>
    <div class="about-v">Expedia TAAP · Mitra Tours · Invoice hotel</div></div>
  <div class="about-r"><div class="about-k">Model AI</div>
    <div class="about-v">gpt-4o-mini (OpenAI)</div></div>
</div>""", unsafe_allow_html=True)


# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:40px;padding:18px 0 10px;border-top:2px solid #ddd;
    text-align:center;font-size:12px;color:#9e9e9e;line-height:2.2">
  Built with ❤️ &nbsp;·&nbsp; AI CC Reporting System v5<br>
  <a href="https://www.linkedin.com/in/rifyalt" target="_blank"
     style="color:#6398c8;font-weight:700;text-decoration:none;
            display:inline-flex;align-items:center;gap:5px;margin-top:4px">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="#6398c8">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037
               -1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046
               c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286z
               M5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1
               2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452z"/>
    </svg>
    Rifyal Tumber
  </a>
</div>
""", unsafe_allow_html=True)
