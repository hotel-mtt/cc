# =============================================================================
#  AI CC Reporting System  v6
#  Run  : streamlit run app.py
#  Setup: pip install -r requirements.txt  |  .streamlit/secrets.toml
#  New  : Dual AI provider — OpenAI gpt-4o-mini  OR  Anthropic Claude
#         Pilih provider di tab Pengaturan (disimpan ke session state)
# =============================================================================
import streamlit as st
import hmac, hashlib, time
import gspread, json, base64, re, io, warnings
from google.oauth2.service_account import Credentials
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

# ── Cookie-based auth helpers ─────────────────────────────────────────────────
# Login persist setelah refresh menggunakan browser cookie (HMAC token).
# Tambahkan ke requirements.txt:  streamlit-cookies-controller>=0.0.4
try:
    from streamlit_cookies_controller import CookieController
    _COOKIE_OK = True
except ImportError:
    _COOKIE_OK = False

_COOKIE_NAME = "cc_report_auth"

def _get_password() -> str:
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
    return hmac.compare_digest(
        hashlib.sha256(candidate.encode()).digest(),
        hashlib.sha256(correct.encode()).digest(),
    )

def _make_token() -> str:
    """Buat signed token: timestamp:HMAC — disimpan di browser cookie."""
    pw  = _get_password()
    ts  = str(int(time.time()))
    sig = hmac.new(pw.encode(), (pw + ts).encode(), hashlib.sha256).hexdigest()
    return f"{ts}:{sig}"

def _verify_token(token: str) -> bool:
    """Verifikasi token dari cookie, termasuk cek TTL."""
    if not token or ":" not in token:
        return False
    try:
        ts_str, sig = token.split(":", 1)
        ts  = int(ts_str)
        if (time.time() - ts) > _ttl_hours() * 3600:
            return False
        pw       = _get_password()
        expected = hmac.new(pw.encode(), (pw + ts_str).encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False

def _get_cookie_ctrl():
    if not _COOKIE_OK:
        return None
    if "_cookie_ctrl" not in st.session_state:
        st.session_state["_cookie_ctrl"] = CookieController()
    return st.session_state["_cookie_ctrl"]

# ── login wall ────────────────────────────────────────────────────────────────
def require_login():
    """Tidak digunakan sebagai global wall — hanya Dashboard yang terkunci.
    Tetap ada untuk backward-compatibility jika dipanggil dari luar."""
    pass

def _render_logout_button():
    """Tombol logout kecil — dipakai di dalam dashboard."""
    if st.button("🔒 Logout Dashboard", type="secondary",
                 use_container_width=True, key="_auth_logout_btn"):
        st.session_state["_auth_ok"]         = False
        st.session_state["_auth_login_time"] = 0
        ctrl = _get_cookie_ctrl()
        if ctrl:
            try: ctrl.remove(_COOKIE_NAME)
            except: pass
        st.rerun()


def _render_footer():
    st.markdown("""
<div style="margin-top:40px;padding:16px 0 10px;border-top:0.5px solid #ddd;
    display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
  <div style="display:flex;align-items:center;gap:9px;">
    <div style="width:26px;height:26px;border-radius:7px;background:#191d3a;
        display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;">&#x1F4B3;</div>
    <div>
      <div style="font-size:12px;font-weight:600;color:#191d3a;line-height:1.2;">CC Reporting</div>
      <div style="font-size:10px;color:#aaa;line-height:1.2;">v6 &middot; Mitra Tours &amp; Travel</div>
    </div>
  </div>
  <a href="https://www.linkedin.com/in/rifyalt" target="_blank"
     style="display:flex;align-items:center;gap:6px;text-decoration:none;
            font-size:11px;font-weight:500;color:#616161;
            border:0.5px solid #e0e0e0;padding:5px 12px;border-radius:20px;
            background:#fff;">
    <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
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

def _dashboard_login_wall() -> bool:
    """
    Guard khusus untuk tab Dashboard.
    Return True  → sudah login, lanjut render dashboard.
    Return False → belum login, tampilkan form login inline lalu return False.
    """
    ctrl = _get_cookie_ctrl()

    # Restore dari cookie jika session belum ada
    if not st.session_state.get("_auth_ok") and ctrl:
        try:
            token = ctrl.get(_COOKIE_NAME)
            if token and _verify_token(token):
                st.session_state["_auth_ok"]         = True
                st.session_state["_auth_login_time"] = time.time()
        except Exception:
            pass

    # Cek TTL
    if st.session_state.get("_auth_ok"):
        elapsed = time.time() - st.session_state.get("_auth_login_time", 0)
        if elapsed < _ttl_hours() * 3600:
            return True
        # Expired
        st.session_state["_auth_ok"] = False
        if ctrl:
            try: ctrl.remove(_COOKIE_NAME)
            except: pass

    # ── Form login — single HTML block, no Streamlit spacing gaps ──────────
    ttl   = int(_ttl_hours())
    _err  = st.session_state.get("_dash_err", "")

    st.markdown(f"""
<style>
.dash-lock-wrap{{
    display:flex;flex-direction:column;align-items:center;
    padding:60px 16px 8px;text-align:center}}
.dash-lock-icon{{
    width:48px;height:48px;border-radius:14px;
    background:#fff;border:1px solid #e4e4e4;
    display:flex;align-items:center;justify-content:center;margin-bottom:18px}}
.dash-lock-title{{font-size:16px;font-weight:600;color:#191d3a;margin-bottom:5px}}
.dash-lock-sub{{font-size:12px;color:#aaa;margin-bottom:32px}}
.dash-lock-err{{
    font-size:12px;color:#e53935;margin-bottom:8px;min-height:16px;text-align:center}}
.dash-lock-foot{{
    font-size:11px;color:#ccc;margin-top:14px;margin-bottom:4px;text-align:center}}
</style>
<div class="dash-lock-wrap">
  <div class="dash-lock-icon">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
        stroke="#191d3a" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
  </div>
  <div class="dash-lock-title">Dashboard</div>
  <div class="dash-lock-sub">Masukkan password untuk melanjutkan</div>
</div>
<div class="dash-lock-err">{_err}</div>
""", unsafe_allow_html=True)

    # Kolom tengah untuk batasi lebar input & tombol
    _col_l, _col_c, _col_r = st.columns([1, 2, 1])
    with _col_c:
        pw = st.text_input("Password", type="password",
                           placeholder="Password",
                           label_visibility="collapsed",
                           key="_dash_pw_input")

        _btn = st.button("Buka Dashboard", type="primary",
                         use_container_width=True, key="_dash_login_btn")

    if _btn:
        if _check_pw(pw):
            st.session_state["_auth_ok"]         = True
            st.session_state["_auth_login_time"] = time.time()
            st.session_state["_dash_err"]         = ""
            ctrl2 = _get_cookie_ctrl()
            if ctrl2:
                try:
                    ctrl2.set(_COOKIE_NAME, _make_token(),
                              max_age=int(_ttl_hours() * 3600))
                except Exception:
                    pass
            st.rerun()
        else:
            st.session_state["_dash_err"] = "Password salah. Coba lagi."
            st.rerun()

    st.markdown(
        f'<div class="dash-lock-foot">Sesi aktif {ttl} jam &nbsp;·&nbsp; ' +
        'Tab lain bebas diakses</div>',
        unsafe_allow_html=True)
    return False

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

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    pw_input = st.text_input(
        "Password", type="password", placeholder="••••••••",
        key="_auth_pw_input", label_visibility="collapsed")
    login_btn = st.button("Masuk →", type="primary", use_container_width=True, key="_auth_login_btn")

    if login_btn:
        if not _get_password():
            st.markdown('<div class="err-box">⚠ Password belum dikonfigurasi di secrets.toml</div>',
                        unsafe_allow_html=True)
        elif _check_pw(pw_input):
            st.session_state["_auth_ok"]         = True
            st.session_state["_auth_login_time"] = time.time()
            # Simpan token ke browser cookie agar persist setelah refresh
            ctrl = _get_cookie_ctrl()
            if ctrl:
                try:
                    ctrl.set(_COOKIE_NAME, _make_token(),
                             max_age=int(_ttl_hours() * 3600))
                except Exception:
                    pass
            st.rerun()
        else:
            st.markdown('<div class="err-box">✕ Password salah. Coba lagi.</div>',
                        unsafe_allow_html=True)

    ttl = _ttl_hours()
    extra = "" if _COOKIE_OK else ' &nbsp;·&nbsp; <code>pip install streamlit-cookies-controller</code> untuk persist'
    st.markdown(f'<div class="hint">Sesi aktif selama {int(ttl)} jam setelah login.{extra}</div>',
                unsafe_allow_html=True)


# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
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

/* ── AI provider badge in header ── */
.ah-ai-badge{
    font-size:10px;font-weight:700;letter-spacing:.4px;
    padding:4px 10px;border-radius:20px;white-space:nowrap;flex-shrink:0;margin-left:6px}
.ah-ai-openai{background:#0d1f12;color:#4ade80;border:1px solid #1e4620}
.ah-ai-claude{background:#1a1020;color:#c084fc;border:1px solid #6b21a8}

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

.sec-lbl{
    font-size:11px;font-weight:700;text-transform:uppercase;
    letter-spacing:.9px;color:#9e9e9e;margin:16px 0 10px;
    padding-bottom:8px;border-bottom:1.5px solid #ddd}

label[data-testid="stWidgetLabel"] p,
label[data-testid="stWidgetLabel"]{
    font-size:12px !important;font-weight:600 !important;
    color:#191d3a !important;text-transform:none !important;
    letter-spacing:0 !important;margin-bottom:4px !important}

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

.stTextInput,.stSelectbox,[data-testid="stSelectbox"]{
    width:100% !important;min-width:0 !important}
div[data-testid="stWidgetLabel"]{overflow:visible !important}

[data-testid="stHorizontalBlock"]{
    gap:12px !important;align-items:flex-start !important;
    flex-wrap:nowrap !important;overflow:visible !important}
[data-testid="stHorizontalBlock"]>[data-testid="column"]{
    flex:1 1 0% !important;min-width:0 !important;
    max-width:none !important;overflow:visible !important;padding-bottom:4px !important}
[data-testid="stHorizontalBlock"]>[data-testid="column"]>div,
[data-testid="stHorizontalBlock"]>[data-testid="column"] [data-testid="stVerticalBlock"]{
    overflow:visible !important;width:100% !important;min-width:0 !important}

.stButton>button{
    width:100% !important;border-radius:13px !important;
    height:50px !important;font-size:14px !important;
    font-weight:700 !important;border:none !important}
.stButton>button[kind="primary"]{
    background:#ffc744 !important;color:#191d3a !important;
    box-shadow:0 3px 10px rgba(255,199,68,.3) !important}
.stButton>button[kind="primary"]:hover{
    background:#fddb32 !important;box-shadow:0 4px 14px rgba(255,199,68,.4) !important}

/* ── Dashboard login button — dark navy style ── */
[data-testid="stButton"] button[data-testid="baseButton-primary"][kind="primary"]#_dash_login_btn{
    background:#191d3a !important;color:#fddb32 !important;
    box-shadow:none !important}
.stButton>button[kind="secondary"]{
    background:#fff !important;border:1.5px solid #ddd !important;color:#616161 !important}
.stButton>button[kind="secondary"]:hover{
    border-color:#6398c8 !important;background:#e8f0fe !important;color:#191d3a !important}

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

[data-testid="stLinkButton"] a{
    background:#6398c8 !important;color:#fff !important;
    border-radius:13px !important;height:52px !important;
    font-size:14px !important;font-weight:700 !important;border:none !important;
    display:flex !important;align-items:center !important;
    justify-content:center !important;text-decoration:none !important}

[data-testid="stCheckbox"] label{
    font-size:14px !important;color:#616161 !important;font-weight:500 !important}

/* ── AI provider selector cards — minimalist ── */
.ai-sel{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}
.ai-card-min{
    background:#fff;border:1px solid #e0e0e0;border-radius:14px;
    padding:12px 14px;cursor:pointer;transition:border-color .12s,background .12s;
    display:flex;align-items:center;gap:10px}
.ai-card-min:hover{border-color:#9e9e9e}
.ai-card-min.active{border:1.5px solid #1D9E75;background:#f0fdf4}
.ai-card-icon{width:30px;height:30px;border-radius:8px;background:#f5f5f5;
    border:1px solid #e8e8e8;display:flex;align-items:center;
    justify-content:center;flex-shrink:0;font-size:14px}
.ai-card-info{flex:1;min-width:0}
.ai-card-info b{font-size:13px;font-weight:600;color:#191d3a;display:block}
.ai-card-info span{font-size:11px;color:#9e9e9e}
.ai-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;background:#e0e0e0}
.ai-dot.on{background:#1D9E75}
.ai-status-bar{display:flex;align-items:center;gap:8px;padding:9px 13px;
    border-radius:10px;background:#f0fdf4;border:1px solid #bbf7d0;margin-bottom:18px}
.ai-status-dot{width:6px;height:6px;border-radius:50%;background:#1D9E75;flex-shrink:0}
.ai-status-txt{font-size:12px;color:#166534}
.ai-key-row{display:flex;align-items:center;justify-content:space-between;
    padding:9px 13px;border-radius:10px;background:#fff;
    border:1px solid #e8e8e8;margin-bottom:6px}
.ai-key-left{display:flex;align-items:center;gap:9px}
.ai-key-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.ai-key-name{font-size:13px;color:#191d3a}
.ai-key-ok{font-size:11px;color:#1D9E75}
.ai-key-warn{font-size:11px;color:#e68900}

.notice{border-radius:12px;padding:11px 14px;font-size:13px;line-height:1.5;
    display:flex;align-items:flex-start;gap:8px;margin-bottom:12px}
.nok  {background:#f0fdf4;border:1px solid #86efac;color:#166534}
.nerr {background:#fff1f2;border:1px solid #fecdd3;color:#9f1239}
.ninfo{background:#e8f0fe;border:1px solid #6398c8;color:#1e3a6e}
.nwarn{background:#fffbeb;border:1px solid #fde68a;color:#92400e}
.nviolet{background:#faf5ff;border:1px solid #d8b4fe;color:#6b21a8}

.expedia-banner{
    background:#fff;border:1.5px solid #ddd;border-bottom:none;
    border-radius:16px 16px 0 0;padding:13px 16px;
    display:flex;align-items:center;justify-content:space-between;margin-top:16px}
.expedia-banner img{height:24px;width:auto;object-fit:contain}
.taap-pill{
    font-size:11px;font-weight:700;letter-spacing:.3px;
    color:#1e3a6e;background:#e8f0fe;border:1px solid #6398c8;
    padding:4px 11px;border-radius:20px;white-space:nowrap}

[data-testid="stFileUploader"] [data-testid="stWidgetLabel"],
[data-testid="stFileUploader"] [data-testid="stWidgetLabel"] *{display:none !important}
[data-testid="stFileUploaderDropzoneInput"] + label,
[data-testid="stFileUploader"] > section > label,
[data-testid="stFileUploader"] label[for]{
    display:none !important;visibility:hidden !important;
    height:0 !important;overflow:hidden !important}
[data-testid="stFileUploader"]{margin-top:0 !important}
[data-testid="stFileUploader"]>div:first-child,
[data-testid="stFileUploader"] section{
    border:1.5px dashed #b8cde0 !important;border-top:none !important;
    border-radius:0 0 16px 16px !important;background:#f5f8fc !important;
    margin-top:0 !important;padding:28px 20px !important;min-height:120px !important}
[data-testid="stFileUploader"]>div:first-child:hover,
[data-testid="stFileUploader"] section:hover{
    border-color:#6398c8 !important;background:#e8f0fe !important}
[data-testid="stFileUploader"] button{
    border-radius:10px !important;border:1.5px solid #ddd !important;
    background:#fff !important;color:#191d3a !important;
    font-size:13px !important;font-weight:600 !important;
    padding:8px 18px !important;height:auto !important}
[data-testid="stFileUploader"] button:hover{
    border-color:#6398c8 !important;background:#e8f0fe !important}
[data-testid="stFileUploaderDropInstructions"]{
    font-size:14px !important;font-weight:600 !important;color:#191d3a !important}
[data-testid="stFileUploaderDropInstructions"] small,
[data-testid="stFileUploaderDropInstructions"] span{
    font-size:12px !important;color:#9e9e9e !important;font-weight:400 !important}

.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px}
.stat-card{background:#fff;border:1.5px solid #ddd;border-radius:18px;padding:16px 15px}
.stat-val{font-size:22px;font-weight:800;color:#191d3a;line-height:1.1}
.stat-lbl{font-size:11px;color:#9e9e9e;margin-top:5px;font-weight:500}

.bulk-prog{background:#ddd;border-radius:99px;height:5px;overflow:hidden;margin-bottom:6px}
.bulk-prog-f{height:100%;background:#6398c8;border-radius:99px;transition:width .3s}
.bulk-prog-lbl{font-size:12px;color:#9e9e9e;text-align:center;margin-bottom:14px;font-weight:500}

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

.st-row{display:flex;align-items:center;gap:12px;background:#fff;
    border:1.5px solid #ddd;border-radius:15px;padding:14px 15px;margin-bottom:10px}
.st-icon{width:38px;height:38px;border-radius:11px;display:flex;align-items:center;
    justify-content:center;font-size:18px;flex-shrink:0}
.si-g{background:#f0fdf4}.si-r{background:#fff1f2}
.si-b{background:#e8f0fe}.si-y{background:#fffde7}.si-v{background:#faf5ff}
.st-body{flex:1;min-width:0}
.st-title{font-size:14px;font-weight:700;color:#191d3a;line-height:1}
.st-sub{font-size:12px;color:#9e9e9e;margin-top:3px}
.st-badge{display:inline-flex;align-items:center;font-size:11px;
    font-weight:700;padding:4px 12px;border-radius:20px;flex-shrink:0}
.bg{background:#f0fdf4;color:#166534;border:1px solid #86efac}
.br{background:#fff1f2;color:#9f1239;border:1px solid #fecdd3}
.by{background:#fffde7;color:#7a5c00;border:1px solid #fcd34d}
.bv{background:#f3e8ff;color:#6b21a8;border:1px solid #d8b4fe}
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

[data-testid="stDataFrame"]{border-radius:15px !important;border:1.5px solid #ddd !important;
    overflow:hidden !important;box-shadow:none !important}
[data-testid="stDataFrame"] table{font-size:13px !important}
[data-testid="stDataFrame"] th{background:#f5f8fc !important;color:#616161 !important;
    font-size:11px !important;font-weight:700 !important;text-transform:uppercase !important;
    letter-spacing:.5px !important;border-bottom:1.5px solid #ddd !important;padding:11px 13px !important}
[data-testid="stDataFrame"] td{font-size:13px !important;color:#191d3a !important;
    padding:10px 13px !important;border-bottom:1px solid #ededed !important}
[data-testid="stDataFrame"] tr:hover td{background:#f5f8fc !important}

[data-testid="stMetric"]{background:#fff !important;border:1.5px solid #ddd !important;
    border-radius:15px !important;padding:14px !important;margin-bottom:0 !important}
[data-testid="stMetricLabel"]{font-size:11px !important;font-weight:700 !important;
    color:#9e9e9e !important;text-transform:uppercase !important;letter-spacing:.6px !important}
[data-testid="stMetricValue"]{font-size:15px !important;font-weight:800 !important;
    color:#191d3a !important}

.stSpinner>div{border-top-color:#6398c8 !important}
.stExpander{border:1.5px solid #ddd !important;border-radius:14px !important;
    background:#fff !important;margin-bottom:10px !important}
details>summary{font-size:13px !important;color:#616161 !important}

@media(max-width:480px){
    .main .block-container{padding:8px 8px 80px !important}
    .app-header{border-radius:16px;padding:12px 14px}
    .ah-icon{width:40px;height:40px;font-size:20px}
    .ah-title{font-size:16px}
    .nb-wrap button{height:68px !important;font-size:10px !important}
    .bs-val{font-size:20px}.stat-val{font-size:18px}
    .ai-selector{grid-template-columns:1fr 1fr}}
</style>
""", unsafe_allow_html=True)


# ─── AI Provider helpers ──────────────────────────────────────────────────────
# Provider: "openai" | "claude"

def get_ai_provider() -> str:
    """Kembalikan provider aktif: 'openai' atau 'claude'."""
    return st.session_state.get("ai_provider", "openai")

def get_openai_key() -> str:
    try:
        k = st.secrets["openai"]["api_key"]
        if k and len(k) > 20 and "GANTI" not in k and "PASTE" not in k:
            return k
    except Exception:
        pass
    return st.session_state.get("openai_key_manual", "")

def get_claude_key() -> str:
    try:
        k = st.secrets["anthropic"]["api_key"]
        if k and len(k) > 20 and "GANTI" not in k and "PASTE" not in k:
            return k
    except Exception:
        pass
    return st.session_state.get("claude_key_manual", "")

def active_ai_ready() -> bool:
    """Apakah provider yang dipilih sudah punya API key?"""
    if get_ai_provider() == "openai":
        return bool(get_openai_key())
    return bool(get_claude_key())

def active_ai_label() -> str:
    if get_ai_provider() == "openai":
        return "OpenAI gpt-4o-mini"
    return "Claude claude-sonnet-4-5"


# ─── Google Sheets ────────────────────────────────────────────────────────────
def sheet_id() -> str:
    try:
        s = st.secrets["google_sheets"]["sheet_id"]
        if s and "GANTI" not in s:
            return s
    except Exception:
        pass
    return st.session_state.get("sheet_id", "")

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


# ─── AI System Prompt (shared) ────────────────────────────────────────────────
_SYS = """You are a corporate hotel expense AI parser for credit card reporting.
Parse any document: Expedia TAAP receipt, Mitra Tours itinerary, hotel invoice
(IHG, Marriott, Hilton, etc.), screenshot, or free text.
Return ONLY a valid JSON object — no markdown, no explanation.

Keys:
- supplier   : string  — platform/OTA/hotel brand from document header
- booking_id : string  — itinerary/booking/confirmation number
- booked_on  : string  — booking date YYYY-MM-DD
- issued_on  : string  — issued/receipt date YYYY-MM-DD
- hotel      : string  — full hotel name as written
- checkin    : string  — check-in date YYYY-MM-DD
- checkout   : string  — check-out date YYYY-MM-DD
- qty        : string  — rooms and nights e.g. "2 rooms x 2 nights"
- room       : integer — TOTAL amount charged to the credit card (IDR/Rp).
                         Priority: 1) "Subtotal paid to Expedia"  2) Grand Total
                         3) Sum of all room totals  4) Sum of subtotals
- name       : string  — primary guest name (first traveller listed)
- card       : string  — e.g. "Visa •••• 0191", empty if absent
- notes      : string  — room type(s), number of rooms, tax details, confirmation #

Rules:
1. Dates: any format → YYYY-MM-DD.
2. Amounts: strip IDR/Rp/USD/$/commas → plain integer, no decimals.
3. room = single final total the credit card was charged.
4. qty: count distinct rooms × nights.
5. Missing field → "" for strings, 0 for integers."""


# ─── AI Parser — OpenAI ───────────────────────────────────────────────────────
def _parse_openai(text: str = "", images: list = None) -> tuple:
    import openai, httpx
    key = get_openai_key()
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


# ─── AI Parser — Claude ───────────────────────────────────────────────────────
def _parse_claude(text: str = "", images: list = None) -> tuple:
    import anthropic
    key = get_claude_key()
    if not key:
        raise ValueError("Anthropic API key belum diisi — buka tab Pengaturan.")
    content = []
    if images:
        for b64, mime in images:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": b64}
            })
    content.append({
        "type": "text",
        "text": text if text else "Extract all structured data from this document."
    })
    client = anthropic.Anthropic(api_key=key)
    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        system=_SYS,
        messages=[{"role": "user", "content": content}],
    )
    raw = resp.content[0].text
    m   = re.search(r"\{[\s\S]*\}", raw)
    if not m: raise ValueError("Format AI tidak valid — JSON tidak ditemukan.")
    return json.loads(m.group()), raw


# ─── Unified AI parser ────────────────────────────────────────────────────────
def ai_parse(text: str = "", images: list = None) -> tuple:
    """Dispatch ke provider yang sedang aktif."""
    if get_ai_provider() == "claude":
        return _parse_claude(text, images)
    return _parse_openai(text, images)


# ─── UI utilities ─────────────────────────────────────────────────────────────
def fmt(v) -> str:
    try:    return "Rp {:,}".format(int(float(v or 0))).replace(",",".")
    except: return str(v) if v else "—"

def now_ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")

def notice(kind: str, msg: str):
    icons = {"ok":"✓","err":"✕","info":"ℹ","warn":"⚠","violet":"✦"}
    cls   = {"ok":"nok","err":"nerr","info":"ninfo","warn":"nwarn","violet":"nviolet"}
    st.markdown(
        f'<div class="notice {cls.get(kind,"ninfo")}"><b>{icons.get(kind,"ℹ")}</b>&ensp;{msg}</div>',
        unsafe_allow_html=True)


# ─── Session state ────────────────────────────────────────────────────────────
_DEF = {
    "tab":                "input",
    "bulk_results":       [],
    "bulk_saved_count":   0,
    "openai_key_manual":  "",
    "claude_key_manual":  "",
    "ai_provider":        "openai",   # "openai" | "claude"
    "sheet_id":           "1nvgMCmo1EJtbCAt0db_OizvPYDvaEzphKhwzBJ-3X_g",
    "last_issuer":        "",
    "last_pic":           "",
    "last_no_bc":         "",
    "last_nama_kegiatan": "",
}
for _k, _v in _DEF.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─── Header ───────────────────────────────────────────────────────────────────
_prov      = get_ai_provider()
_prov_lbl  = "GPT-4o mini" if _prov == "openai" else "Claude Sonnet"
_prov_cls  = "ah-ai-openai" if _prov == "openai" else "ah-ai-claude"
_prov_ico  = "🤖" if _prov == "openai" else "🟣"

st.markdown(f"""
<div class="app-header">
  <div class="ah-icon" style="background:#fff;padding:2px;overflow:hidden;">
    <img src="data:image/png;base64,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" style="width:100%;height:100%;object-fit:contain;display:block;border-radius:10px;">
  </div>
  <div>
    <div class="ah-title">Credit Card Reporting</div>
    <div class="ah-sub">Mitra Tours &amp; Travel</div>
  </div>
  <span class="ah-ai-badge {_prov_cls}">{_prov_ico} {_prov_lbl}</span>
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
    _dash_locked = not st.session_state.get("_auth_ok")
    _dash_lbl    = f"📊{_NL}Dashboard 🔒" if _dash_locked else f"📊{_NL}Dashboard"
    if st.button(_dash_lbl, key="nb_dash", use_container_width=True,
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

    if not active_ai_ready():
        _pv = get_ai_provider()
        _nm = "OpenAI" if _pv == "openai" else "Anthropic"
        notice("err", f"{_nm} API key belum diisi — buka tab <b>Pengaturan</b>.")
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

    # ── AI provider info banner ───────────────────────────────────────────────
    _ap = get_ai_provider()
    if _ap == "claude":
        notice("violet", "AI aktif: <b>Claude claude-sonnet-4-5</b> (Anthropic) &nbsp;·&nbsp; "
               "Ganti di tab <b>Pengaturan</b>")
    else:
        notice("info", "AI aktif: <b>OpenAI gpt-4o-mini</b> &nbsp;·&nbsp; "
               "Ganti di tab <b>Pengaturan</b>")

    # ── Expedia banner ────────────────────────────────────────────────────────
    st.markdown("""
<div class="expedia-banner">
  <img src="https://www.expedia.com/newsroom/wp-content/uploads/2023/07/BEX_Logo_Horizontal_CMYK_FullColorDarkBlue--1024x199.jpg"
    alt="Expedia TAAP" onerror="this.parentElement.style.display='none'">
  <span class="taap-pill">TAAP + Mitra Tours</span>
</div>
""", unsafe_allow_html=True)

    # ── File uploader ─────────────────────────────────────────────────────────
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
        st.session_state["bulk_results"]     = []
        st.session_state["bulk_saved_count"] = 0
        st.rerun()

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
            st.session_state["bulk_results"]       = []
            st.session_state["bulk_saved_count"]   = 0

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

    _render_footer()

# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["tab"] == "dashboard":
    import pandas as pd

    # ── Auth guard — hanya dashboard yang butuh password ─────────────────────
    if not _dashboard_login_wall():
        _render_footer()
        st.stop()

    _cr, _cb2, _cb3 = st.columns([3, 1, 1])
    _cr.markdown('<div class="sec-lbl" style="margin-top:6px">Ringkasan</div>',
                 unsafe_allow_html=True)
    if _cb2.button("↻ Refresh", type="secondary", use_container_width=True, key="dash_ref"):
        st.cache_resource.clear(); st.rerun()
    with _cb3:
        _render_logout_button()

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

    _render_footer()

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

            _total = len(df_log)
            _recent = df_log.head(10)

            # Header row
            st.markdown(
                f'''<div style="display:flex;align-items:center;justify-content:space-between;
                    margin-top:6px;margin-bottom:12px;">
                  <div class="sec-lbl" style="margin:0;border:none;padding:0;">
                    Activity Log</div>
                  <span style="font-size:11px;color:#9e9e9e;font-weight:500;">
                    10 dari {_total} transaksi</span>
                </div>''',
                unsafe_allow_html=True)

            # Render tiap baris sebagai card minimalis
            _items_html = ""
            for _, _row in _recent.iterrows():
                _ts      = str(_row.get("Timestamp Input","—"))
                _bid     = str(_row.get("Booking ID","—"))
                _hotel   = str(_row.get("Hotel","")) or "—"
                _issuer  = str(_row.get("Issuer","")) or "—"
                _total_r = _row.get("Total (Rp)", 0)
                try:    _amt = "Rp {:,}".format(int(float(_total_r))).replace(",",".")
                except: _amt = "—"

                _items_html += f'''
<div style="display:flex;align-items:center;gap:12px;padding:11px 14px;
    background:#fff;border-radius:12px;border:0.5px solid #e8e8e8;margin-bottom:6px;">
  <div style="width:36px;height:36px;border-radius:10px;background:#f5f5f5;
      display:flex;align-items:center;justify-content:center;flex-shrink:0;">
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
        stroke="#9e9e9e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
    </svg>
  </div>
  <div style="flex:1;min-width:0;">
    <div style="font-size:13px;font-weight:600;color:#191d3a;
        overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{_hotel}</div>
    <div style="font-size:11px;color:#9e9e9e;margin-top:1px;
        overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
      {_bid} &nbsp;·&nbsp; {_issuer}</div>
  </div>
  <div style="text-align:right;flex-shrink:0;">
    <div style="font-size:12px;font-weight:600;color:#191d3a;">{_amt}</div>
    <div style="font-size:10px;color:#bbb;margin-top:1px;">{_ts}</div>
  </div>
</div>'''

            st.markdown(_items_html, unsafe_allow_html=True)

    except Exception as e:
        notice("err", str(e))

    _render_footer()

# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — PENGATURAN
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["tab"] == "settings":

    _cur_prov = get_ai_provider()   # dibutuhkan oleh Cek Koneksi dan AI Provider

    # ── ③ Cek Koneksi ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl">Cek Koneksi</div>', unsafe_allow_html=True)

    if st.button("🔍  Cek Koneksi", type="primary", use_container_width=True):
        _rl = []

        # OpenAI check
        _ol = bool(get_openai_key())
        _rl.append((_ol, "OpenAI gpt-4o-mini",
                    ("Terhubung" if _ol else "Key tidak ditemukan")
                    + (" · Aktif" if _cur_prov == "openai" and _ol else "")))

        # Claude check
        _cl2 = bool(get_claude_key())
        _rl.append((_cl2, "Claude claude-sonnet-4-5",
                    ("Terhubung" if _cl2 else "Key tidak ditemukan")
                    + (" · Aktif" if _cur_prov == "claude" and _cl2 else "")))

        # Google Sheets check
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

        _rl.append((_PDF_OK,"PDF Upload",
                    "pypdfium2 aktif" if _PDF_OK else "pypdfium2 tidak terinstall"))

        _it = ""
        for _ok2,_sv,_ms in _rl:
            _cl  = "#1e9e5a" if _ok2 else "#e53935"
            _it += (f'<div class="conn-item">'
                    f'<div class="cdot" style="background:{_cl}"></div>'
                    f'<span style="font-weight:700;color:{_cl}">{"✓" if _ok2 else "✕"} {_sv}</span>'
                    f'&ensp;<span style="color:#9e9e9e">{_ms}</span></div>')
        st.markdown(f'<div class="conn-list">{_it}</div>', unsafe_allow_html=True)


    # ── ① AI Provider Selector — minimalist ─────────────────────────────────
    st.markdown('<div class="sec-lbl" style="margin-top:6px">AI Provider</div>',
                unsafe_allow_html=True)

    _oai_has  = bool(get_openai_key())
    _cla_has  = bool(get_claude_key())

    _oai_active = "active" if _cur_prov == "openai" else ""
    _cla_active = "active" if _cur_prov == "claude"  else ""
    _oai_dot    = "on"     if _cur_prov == "openai" else ""
    _cla_dot    = "on"     if _cur_prov == "claude"  else ""
    _active_lbl = "OpenAI gpt-4o-mini" if _cur_prov == "openai" else "Claude claude-sonnet-4-5"

    st.markdown(
        f'''<div class="ai-sel">
  <div class="ai-card-min {_oai_active}">
    <div class="ai-card-icon">🤖</div>
    <div class="ai-card-info"><b>OpenAI</b><span>gpt-4o-mini</span></div>
    <div class="ai-dot {_oai_dot}"></div>
  </div>
  <div class="ai-card-min {_cla_active}">
    <div class="ai-card-icon">🟣</div>
    <div class="ai-card-info"><b>Claude AI</b><span>claude-sonnet-4-5</span></div>
    <div class="ai-dot {_cla_dot}"></div>
  </div>
</div>
<div class="ai-status-bar">
  <div class="ai-status-dot"></div>
  <span class="ai-status-txt">Active: {_active_lbl}</span>
</div>''',
        unsafe_allow_html=True)

    _pa, _pb = st.columns(2)
    with _pa:
        if st.button("Gunakan OpenAI",
                     type="primary" if _cur_prov == "openai" else "secondary",
                     use_container_width=True, key="sel_openai"):
            st.session_state["ai_provider"] = "openai"
            st.rerun()
    with _pb:
        if st.button("Gunakan Claude AI",
                     type="primary" if _cur_prov == "claude" else "secondary",
                     use_container_width=True, key="sel_claude"):
            st.session_state["ai_provider"] = "claude"
            st.rerun()

    # ── ② API Keys — hanya tampilkan status, tanpa nilai key ─────────────────
    st.markdown('<div class="sec-lbl" style="margin-top:18px">API Keys</div>',
                unsafe_allow_html=True)

    # — OpenAI key —
    _oai_secrets_ok = False
    try:
        k = st.secrets["openai"]["api_key"]
        if k and len(k) > 20 and "GANTI" not in k and "PASTE" not in k:
            _oai_secrets_ok = True
    except: pass

    _oai_ready = _oai_secrets_ok or bool(st.session_state.get("openai_key_manual",""))
    _oai_dot_c = "#1D9E75" if _oai_ready else "#e68900"
    _oai_lbl   = "ready" if _oai_ready else "belum dikonfigurasi"
    _oai_lcls  = "ai-key-ok" if _oai_ready else "ai-key-warn"

    st.markdown(
        f'<div class="ai-key-row"><div class="ai-key-left">' +
        f'<div class="ai-key-dot" style="background:{_oai_dot_c}"></div>' +
        f'<span class="ai-key-name">OpenAI</span></div>' +
        f'<span class="{_oai_lcls}">{_oai_lbl}</span></div>',
        unsafe_allow_html=True)
    if not _oai_ready:
        _nk_oai = st.text_input(
            "OpenAI API Key", value=st.session_state.get("openai_key_manual",""),
            type="password", placeholder="sk-proj-...",
            label_visibility="collapsed", key="inp_oai_key")
        if _nk_oai != st.session_state.get("openai_key_manual",""):
            st.session_state["openai_key_manual"] = _nk_oai; st.rerun()

    # — Claude key —
    _cla_secrets_ok = False
    try:
        k = st.secrets["anthropic"]["api_key"]
        if k and len(k) > 20 and "GANTI" not in k and "PASTE" not in k:
            _cla_secrets_ok = True
    except: pass

    _cla_ready = _cla_secrets_ok or bool(st.session_state.get("claude_key_manual",""))
    _cla_dot_c = "#1D9E75" if _cla_ready else "#e68900"
    _cla_lbl   = "ready" if _cla_ready else "belum dikonfigurasi"
    _cla_lcls  = "ai-key-ok" if _cla_ready else "ai-key-warn"

    st.markdown(
        f'<div class="ai-key-row"><div class="ai-key-left">' +
        f'<div class="ai-key-dot" style="background:{_cla_dot_c}"></div>' +
        f'<span class="ai-key-name">Claude AI</span></div>' +
        f'<span class="{_cla_lcls}">{_cla_lbl}</span></div>',
        unsafe_allow_html=True)
    if not _cla_ready:
        _nk_cla = st.text_input(
            "Anthropic API Key", value=st.session_state.get("claude_key_manual",""),
            type="password", placeholder="sk-ant-api03-...",
            label_visibility="collapsed", key="inp_cla_key")
        if _nk_cla != st.session_state.get("claude_key_manual",""):
            st.session_state["claude_key_manual"] = _nk_cla; st.rerun()

    # ── ④ Status Sistem ───────────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl">Status Sistem</div>', unsafe_allow_html=True)

    # Google Sheets status
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

    # PDF status
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

    # ── ⑤ Tentang ─────────────────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl">Tentang Aplikasi</div>', unsafe_allow_html=True)
    _active_model = "gpt-4o-mini (OpenAI)" if get_ai_provider() == "openai" \
                    else "claude-sonnet-4-5 (Anthropic)"
    st.markdown(f"""
<div class="about-box">
  <div class="about-ttl">AI CC Reporting System v6</div>
  <div class="about-r"><div class="about-k">Input</div>
    <div class="about-v">PDF · JPG · PNG — bulk upload banyak file sekaligus</div></div>
  <div class="about-r"><div class="about-k">Output</div>
    <div class="about-v">Google Sheets — 17 kolom terstruktur</div></div>
  <div class="about-r"><div class="about-k">Dokumen</div>
    <div class="about-v">Expedia TAAP · Mitra Tours · Invoice hotel</div></div>
  <div class="about-r"><div class="about-k">Model AI</div>
    <div class="about-v">{_active_model} <b>(aktif)</b> · bisa diganti di atas</div></div>
</div>""", unsafe_allow_html=True)


    _render_footer()

# ─── Footer already rendered inside each tab ─────────────────────────────────
