# =============================================================================
#  AI CC Reporting System  v6  — Mobile Friendly
#  Dual Input Mode: Expedia/TAAP  OR  Non-Expedia (Payment Receipt)
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

st.set_page_config(page_title="Mitra CC Reporter", page_icon="💳",
    layout="centered", initial_sidebar_state="collapsed")

try:
    from streamlit_cookies_controller import CookieController
    _COOKIE_OK = True
except ImportError:
    _COOKIE_OK = False

_COOKIE_NAME = "cc_report_auth"

def _get_password():
    """App-level login password (general access)."""
    try:
        p = st.secrets["auth"]["password"]
        if p and "GANTI" not in p: return p
    except: pass
    return st.session_state.get("_auth_pw_override", "")

def _get_dashboard_password():
    """Dashboard-specific password — set via secrets[auth][dashboard_password]."""
    try:
        p = st.secrets["auth"]["dashboard_password"]
        if p and "GANTI" not in p: return p
    except: pass
    return _get_password()

def _ttl_hours():
    try: return float(st.secrets["auth"].get("session_ttl_hours", 8))
    except: return 8.0

def _check_pw(candidate):
    """Check app-level password."""
    correct = _get_password()
    if not correct: return False
    return hmac.compare_digest(hashlib.sha256(candidate.encode()).digest(),
                               hashlib.sha256(correct.encode()).digest())

def _check_dash_pw(candidate):
    """Check dashboard-specific password."""
    correct = _get_dashboard_password()
    if not correct: return False
    return hmac.compare_digest(hashlib.sha256(candidate.encode()).digest(),
                               hashlib.sha256(correct.encode()).digest())

def _make_token():
    pw = _get_password(); ts = str(int(time.time()))
    sig = hmac.new(pw.encode(), (pw+ts).encode(), hashlib.sha256).hexdigest()
    return f"{ts}:{sig}"

def _verify_token(token):
    if not token or ":" not in token: return False
    try:
        ts_str, sig = token.split(":", 1); ts = int(ts_str)
        if (time.time()-ts) > _ttl_hours()*3600: return False
        pw = _get_password()
        expected = hmac.new(pw.encode(),(pw+ts_str).encode(),hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except: return False

def _get_cookie_ctrl():
    if not _COOKIE_OK: return None
    if "_cookie_ctrl" not in st.session_state:
        st.session_state["_cookie_ctrl"] = CookieController()
    return st.session_state["_cookie_ctrl"]

def _render_logout_button():
    if st.button("Logout", type="secondary", use_container_width=True, key="_auth_logout_btn"):
        st.session_state["_auth_ok"] = False; st.session_state["_auth_login_time"] = 0
        ctrl = _get_cookie_ctrl()
        if ctrl:
            try: ctrl.remove(_COOKIE_NAME)
            except: pass
        st.rerun()

def _dashboard_login_wall():
    """
    Secondary login wall for the Dashboard tab only.
    Uses secrets[auth][dashboard_password] — separate from the app-level password.
    Returns True if authenticated. Otherwise renders mini login form and stops.
    """
    if st.session_state.get("_dash_auth_ok"):
        return True

    _err = st.session_state.get("_dash_login_err", "")
    _err_banner = f'''<div style="background:#fff1f2;border:1px solid #fecdd3;border-radius:8px;
        padding:6px 12px;margin-top:8px;font-size:12px;color:#9f1239;font-weight:500;">{_err}</div>''' if _err else ""

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
/* ── Dashboard login — compact centered card ── */
.dash-login-head{{
    background:#fff;border:1.5px solid #e4e4e4;
    border-radius:16px 16px 0 0;border-bottom:none;
    padding:22px 20px 16px;text-align:center;
    max-width:280px;margin:0 auto;
}}
.dash-login-icon{{font-size:26px;margin-bottom:8px}}
.dash-login-title{{font-size:16px;font-weight:800;color:#191d3a;margin:0 0 2px}}
.dash-login-sub{{font-size:11px;color:#9e9e9e;margin:0}}

/* Card body — target stVerticalBlock dalam konteks dashboard login */
.dash-login-wrap [data-testid="stVerticalBlock"]{{
    background:#fff !important;
    border:1.5px solid #e4e4e4 !important;
    border-radius:0 0 16px 16px !important;
    border-top:1px solid #f0f0f0 !important;
    padding:12px 20px 16px !important;
    box-shadow:0 6px 20px rgba(0,0,0,.07) !important;
    max-width:280px !important;
    margin:0 auto !important;
    gap:0 !important;
}}
.dash-login-wrap [data-testid="stVerticalBlock"] > div,
.dash-login-wrap .element-container{{margin:0 !important;padding:0 !important}}
.dash-login-wrap label[data-testid="stWidgetLabel"]{{display:none !important}}
.dash-login-wrap .stTextInput input{{
    border-radius:10px !important;border:1.5px solid #ddd !important;
    background:#fafafa !important;font-size:15px !important;color:#191d3a !important;
    padding:0 12px !important;height:44px !important;
    box-sizing:border-box !important;width:100% !important;
    -webkit-appearance:none !important;appearance:none !important;}}
.dash-login-wrap .stTextInput input:focus{{
    border-color:#6398c8 !important;background:#fff !important;
    box-shadow:0 0 0 3px rgba(99,152,200,.15) !important;outline:none !important}}
.dash-login-wrap .stTextInput input::placeholder{{color:#bbb !important;font-size:14px !important}}
.dash-login-wrap .stTextInput,.dash-login-wrap .stTextInput>div{{margin:0 !important;padding:0 !important}}
.dash-login-wrap .stButton>button{{
    width:100% !important;border-radius:10px !important;height:44px !important;
    font-size:14px !important;font-weight:700 !important;border:none !important;
    background:#191d3a !important;color:#fff !important;
    box-shadow:none !important;margin-top:8px !important}}
.dash-login-wrap .stButton>button:hover{{background:#2a3060 !important}}
</style>

<div class="dash-login-head">
  <div class="dash-login-icon">🔒</div>
  <div class="dash-login-title">Dashboard</div>
  <div class="dash-login-sub">Masukkan password dashboard</div>
  {_err_banner}
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="dash-login-wrap">', unsafe_allow_html=True)
    _dpw = st.text_input("Dashboard password", type="password",
                         label_visibility="collapsed", key="_dash_pw_input",
                         placeholder="Password dashboard")
    _dbtn = st.button("Masuk ke Dashboard", type="primary",
                      use_container_width=True, key="_dash_login_btn")
    st.markdown('<p style="font-size:11px;color:#bbb;text-align:center;margin-top:8px;max-width:280px;margin-left:auto;margin-right:auto;">Dashboard access terpisah dari login utama</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if _dbtn:
        if _check_dash_pw(_dpw):
            st.session_state["_dash_auth_ok"] = True
            st.session_state["_dash_login_err"] = ""
            st.rerun()
        else:
            st.session_state["_dash_login_err"] = "Password salah. Coba lagi."
            st.rerun()

    return False

def _render_footer():
    st.markdown("""
<div style="margin-top:32px;padding:14px 0 8px;border-top:0.5px solid #ddd;
    display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;">
  <div style="display:flex;align-items:center;gap:8px;">
    <div style="width:24px;height:24px;border-radius:6px;overflow:hidden;flex-shrink:0;"><img src="data:image/png;base64,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" style="width:100%;height:100%;object-fit:contain;" alt="Mitra"></div>
    <div>
      <div style="font-size:11px;font-weight:600;color:#191d3a;line-height:1.2;">Intelligent Automation Scanner</div>
      <div style="font-size:9px;color:#aaa;line-height:1.2;">v6 · Mitra Tours &amp; Travel</div>
    </div>
  </div>
  <a href="https://www.linkedin.com/in/rifyalt" target="_blank"
     style="display:flex;align-items:center;gap:5px;text-decoration:none;
            font-size:10px;font-weight:500;color:#616161;
            border:0.5px solid #e0e0e0;padding:4px 10px;border-radius:20px;background:#fff;">
    Rifyal Tumber
  </a>
</div>""", unsafe_allow_html=True)

# ─── APP-LEVEL LOGIN WALL ─────────────────────────────────────────────────────
# This runs before ANYTHING else is rendered. If not authenticated, show only
# the login screen and call st.stop().

def _app_login_wall():
    """
    Returns True if user is authenticated. Otherwise renders login screen
    and calls st.stop() — blocking the rest of the app from rendering.
    """
    ctrl = _get_cookie_ctrl()

    # 1. Try restoring session from cookie
    if not st.session_state.get("_auth_ok") and ctrl:
        try:
            token = ctrl.get(_COOKIE_NAME)
            if token and _verify_token(token):
                st.session_state["_auth_ok"] = True
                st.session_state["_auth_login_time"] = time.time()
        except: pass

    # 2. Check if already authenticated and not expired
    if st.session_state.get("_auth_ok"):
        elapsed = time.time() - st.session_state.get("_auth_login_time", 0)
        if elapsed < _ttl_hours() * 3600:
            return True
        # Expired — clear session
        st.session_state["_auth_ok"] = False
        if ctrl:
            try: ctrl.remove(_COOKIE_NAME)
            except: pass

    # 3. Not authenticated — render login screen and stop
    # Strategy: pure Streamlit widgets, CSS-only card styling.
    # No JS injection — reliable across all browsers.
    ttl = int(_ttl_hours())
    _err = st.session_state.get("_app_login_err", "")
    _LOGO_B64 = "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"

    _err_banner = f'''<div style="background:#fff1f2;border:1px solid #fecdd3;border-radius:8px;
        padding:7px 12px;margin-top:12px;font-size:12px;color:#9f1239;font-weight:500;text-align:left;">{_err}</div>''' if _err else ""

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html,body,[data-testid="stAppViewContainer"],[data-testid="stAppViewBlockContainer"],.main{{
    background:linear-gradient(160deg,#dce8f5 0%,#edf2f7 60%,#e8edf4 100%) !important;
    min-height:100vh !important;
    font-family:'Inter',system-ui,sans-serif !important}}
[data-testid="stSidebar"],#MainMenu,footer,header,[data-testid="stDecoration"]{{display:none !important}}
*{{font-family:'Inter',system-ui,sans-serif !important}}

.main .block-container{{
    padding:0 !important;max-width:520px !important;margin:0 auto !important;
    padding-top:max(32px,10vh) !important;padding-bottom:32px !important;
    padding-left:0 !important;padding-right:0 !important;
}}

/* ── Single unified card ── */
.lc-card{{
    background:rgba(255,255,255,0.82);
    border:1px solid rgba(255,255,255,0.9);
    border-radius:20px 20px 0 0;
    border-bottom:none;
    max-width:340px;
    margin:0 auto;
    box-shadow:0 8px 32px rgba(100,140,180,0.18),0 1.5px 4px rgba(0,0,0,0.06);
}}
.lc-card-inner{{padding:32px 28px 20px;text-align:center;}}
.lc-logo-wrap{{display:flex;justify-content:center;margin-bottom:18px}}
.lc-logo-inner{{
    width:52px;height:52px;border-radius:14px;overflow:hidden;
    border:1px solid rgba(0,0,0,0.07);background:#fff;padding:3px;
    box-shadow:0 2px 8px rgba(0,0,0,0.08);
}}
.lc-title{{font-size:20px;font-weight:700;color:#111827;margin:0 0 6px;letter-spacing:-.3px}}
.lc-sub{{font-size:13px;color:#6b7280;margin:0;line-height:1.5}}

/* ── Widget wrapper — menyambung di bawah card ── */
.lc-col-wrap [data-testid="stVerticalBlock"]{{
    background:rgba(255,255,255,0.82) !important;
    border:1px solid rgba(255,255,255,0.9) !important;
    border-top:1px solid #f0f0f0 !important;
    border-radius:0 0 20px 20px !important;
    box-shadow:0 8px 32px rgba(100,140,180,0.18),0 1.5px 4px rgba(0,0,0,0.06) !important;
    padding:16px 28px 22px !important;
    max-width:340px !important;
    margin:0 auto !important;
    gap:8px !important;
}}
.lc-col-wrap .element-container{{margin:0 !important;padding:0 !important}}
.lc-col-wrap label[data-testid="stWidgetLabel"]{{display:none !important}}

/* Password input */
.lc-col-wrap .stTextInput input{{
    border-radius:10px !important;
    border:1px solid #e5e7eb !important;
    background:rgba(255,255,255,0.9) !important;
    font-size:14px !important;color:#111827 !important;
    padding:0 14px !important;height:44px !important;
    box-sizing:border-box !important;width:100% !important;
    -webkit-appearance:none !important;appearance:none !important;
    box-shadow:0 1px 3px rgba(0,0,0,0.06) !important;
    transition:border-color .15s,box-shadow .15s !important;
}}
.lc-col-wrap .stTextInput input:focus{{
    border-color:#6398c8 !important;outline:none !important;
    box-shadow:0 0 0 3px rgba(99,152,200,0.15) !important;
    background:#fff !important;
}}
.lc-col-wrap .stTextInput input::placeholder{{color:#9ca3af !important;font-size:14px !important}}
.lc-col-wrap .stTextInput,.lc-col-wrap .stTextInput>div{{margin:0 !important;padding:0 !important}}

/* Masuk button */
.lc-col-wrap .stButton>button{{
    width:100% !important;border-radius:10px !important;height:44px !important;
    font-size:14px !important;font-weight:600 !important;border:none !important;
    background:#1c1c1e !important;color:#fff !important;
    box-shadow:0 2px 8px rgba(0,0,0,0.18) !important;margin:0 !important;
    letter-spacing:-.1px !important;
}}
.lc-col-wrap .stButton>button:hover{{background:#333 !important}}
.lc-col-wrap .stButton>button:active{{transform:scale(0.99) !important}}

@media(max-width:420px){{
    .lc-card{{max-width:calc(100vw - 32px);border-radius:18px 18px 0 0}}
    .lc-card-inner{{padding:26px 20px 16px}}
    .lc-col-wrap [data-testid="stVerticalBlock"]{{
        max-width:calc(100vw - 32px) !important;
        padding:14px 20px 18px !important;
        border-radius:0 0 18px 18px !important;
    }}
}}
</style>

<div class="lc-card">
  <div class="lc-card-inner">
    <div class="lc-logo-wrap">
      <div class="lc-logo-inner">
        <img src="data:image/png;base64,{_LOGO_B64}"
          style="width:100%;height:100%;object-fit:contain;border-radius:9px;" alt="Mitra">
      </div>
    </div>
    <div class="lc-title">Welcome Back</div>
    <div class="lc-sub">Hey! Good to see you again</div>
    {_err_banner}
  </div>
</div>
""", unsafe_allow_html=True)

    # Widget section — columns untuk center & constrain lebar
    _lpad, _lcol, _rpad = st.columns([1, 4, 1])
    with _lcol:
        st.markdown('<div class="lc-col-wrap">', unsafe_allow_html=True)
        pw = st.text_input("pw", type="password", label_visibility="collapsed",
                           key="_app_pw_input", placeholder="Password")
        _btn = st.button("SIGN IN", type="primary", use_container_width=True,
                         key="_app_login_btn")
        st.markdown(f'<p style="font-size:11px;color:#9ca3af;text-align:center;margin-top:10px;">Sesi aktif {ttl} jam</p>',
                    unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if _btn:
        if _check_pw(pw):
            st.session_state["_auth_ok"] = True
            st.session_state["_auth_login_time"] = time.time()
            st.session_state["_app_login_err"] = ""
            ctrl2 = _get_cookie_ctrl()
            if ctrl2:
                try: ctrl2.set(_COOKIE_NAME, _make_token(), max_age=int(_ttl_hours() * 3600))
                except: pass
            st.rerun()
        else:
            st.session_state["_app_login_err"] = "Password salah. Coba lagi."
            st.rerun()

    st.stop()
    return False  # never reached


# ─── RUN APP-LEVEL LOGIN WALL ─────────────────────────────────────────────────
# Every page render checks auth first. st.stop() is called if not authenticated.
_app_login_wall()


# ─── CSS Mobile-First ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

/* ── Viewport & base ── */
html,body,[data-testid="stAppViewContainer"],[data-testid="stAppViewBlockContainer"],.main{
    background:#ededed !important;font-family:'Inter',system-ui,sans-serif !important}
.main .block-container{
    padding:8px 8px 100px !important;
    max-width:480px !important;
    margin:0 auto !important}
[data-testid="stSidebar"],#MainMenu,footer,header,[data-testid="stDecoration"]{display:none !important}
*{font-family:'Inter',system-ui,sans-serif !important;-webkit-tap-highlight-color:transparent}

/* ── Safe area for notch/home bar (iOS) ── */
.main .block-container{
    padding-bottom:max(100px, calc(80px + env(safe-area-inset-bottom))) !important;
    padding-left:max(8px, env(safe-area-inset-left)) !important;
    padding-right:max(8px, env(safe-area-inset-right)) !important}

/* ── App header ── */
.app-header{background:#191d3a;border-radius:16px;padding:12px 14px;
    display:flex;align-items:center;gap:10px;margin-bottom:10px}
.ah-icon{width:40px;height:40px;border-radius:11px;background:#fddb32;
    display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0}
.ah-title{font-size:16px;font-weight:800;color:#fff;line-height:1.2}
.ah-sub{font-size:11px;color:#9e9e9e;margin-top:1px}
.ah-live{margin-left:auto;font-size:9px;font-weight:700;letter-spacing:.4px;
    background:#0f2310;color:#4ade80;border:1px solid #1e4620;
    padding:4px 9px;border-radius:20px;display:flex;align-items:center;gap:4px;white-space:nowrap;flex-shrink:0}
.ah-live::before{content:'';width:5px;height:5px;border-radius:50%;background:#4ade80;display:block}
.ah-ai-badge{font-size:9px;font-weight:700;letter-spacing:.3px;
    padding:3px 8px;border-radius:20px;white-space:nowrap;flex-shrink:0;margin-left:4px}
.ah-ai-openai{background:#0d1f12;color:#4ade80;border:1px solid #1e4620}
.ah-ai-claude{background:#1a1020;color:#c084fc;border:1px solid #6b21a8}

/* ── Bottom nav bar (fixed, mobile-style) ── */
.nb-fixed{
    position:fixed;bottom:0;left:0;right:0;z-index:9999;
    background:#fff;border-top:1px solid #e8e8e8;
    padding:6px 8px calc(6px + env(safe-area-inset-bottom));
    display:grid;grid-template-columns:repeat(4,1fr);gap:4px;
    box-shadow:0 -4px 20px rgba(0,0,0,.08)}
.nb-item{display:flex;flex-direction:column;align-items:center;
    gap:2px;padding:6px 4px;border-radius:10px;cursor:pointer;
    border:none;background:transparent;color:#9e9e9e;
    font-size:9px;font-weight:500;transition:all .15s;
    -webkit-tap-highlight-color:transparent;min-height:44px}
.nb-item:active{background:#f0f0f0}
.nb-item.active{color:#191d3a;background:#f5f5f5}
.nb-item .nb-icon{font-size:20px;line-height:1}
.nb-item .nb-lbl{font-size:9px;font-weight:600;white-space:nowrap}
/* Streamlit override inside fixed nav */
.nb-wrap div[data-testid="stHorizontalBlock"]{gap:4px !important}
.nb-wrap .stButton>button{
    height:56px !important;border-radius:12px !important;
    border:none !important;background:transparent !important;
    color:#9e9e9e !important;font-size:9px !important;font-weight:600 !important;
    padding:4px 2px !important;line-height:1.4 !important;
    box-shadow:none !important;width:100% !important;
    display:flex;flex-direction:column;align-items:center}
.nb-wrap .stButton>button:hover{background:#f5f5f5 !important;color:#191d3a !important}
.nb-wrap .stButton>button[kind="primary"]{
    background:#f0f0f0 !important;color:#191d3a !important;
    border-bottom:2.5px solid #191d3a !important}

/* ── Section label ── */
.sec-lbl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;
    color:#9e9e9e;margin:14px 0 8px;padding-bottom:6px;border-bottom:1.5px solid #ddd}

/* ── Form labels ── */
label[data-testid="stWidgetLabel"] p,label[data-testid="stWidgetLabel"]{
    font-size:12px !important;font-weight:600 !important;color:#191d3a !important;
    text-transform:none !important;letter-spacing:0 !important;margin-bottom:3px !important}

/* ── Inputs — bigger touch targets ── */
.stTextInput input,.stNumberInput input{
    border-radius:12px !important;border:1.5px solid #ddd !important;
    background:#fff !important;font-size:16px !important;color:#191d3a !important;
    padding:0 14px !important;height:52px !important;line-height:52px !important;
    box-sizing:border-box !important;width:100% !important;
    -webkit-appearance:none;appearance:none}
.stTextInput input:focus,.stNumberInput input:focus{
    border-color:#6398c8 !important;background:#fff !important;
    box-shadow:0 0 0 3px rgba(99,152,200,.18) !important;outline:none !important}
.stTextInput input::placeholder{font-size:14px !important;color:#bbb !important}

/* ── Selectbox ── */
[data-testid="stSelectbox"]>div>div{
    border-radius:12px !important;border:1.5px solid #ddd !important;
    background:#fff !important;font-size:16px !important;color:#191d3a !important;
    height:52px !important;min-height:52px !important;
    display:flex !important;align-items:center !important;box-sizing:border-box !important}
.stTextInput,.stSelectbox,[data-testid="stSelectbox"]{width:100% !important;min-width:0 !important}
div[data-testid="stWidgetLabel"]{overflow:visible !important}

/* ── Columns ── */
[data-testid="stHorizontalBlock"]{
    gap:8px !important;align-items:flex-start !important;
    flex-wrap:nowrap !important;overflow:visible !important}
[data-testid="stHorizontalBlock"]>[data-testid="column"]{
    flex:1 1 0% !important;min-width:0 !important;
    max-width:none !important;overflow:visible !important;padding-bottom:4px !important}
[data-testid="stHorizontalBlock"]>[data-testid="column"]>div,
[data-testid="stHorizontalBlock"]>[data-testid="column"] [data-testid="stVerticalBlock"]{
    overflow:visible !important;width:100% !important;min-width:0 !important}

/* Stack columns on very small screens */
@media(max-width:360px){
    [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important}
    [data-testid="stHorizontalBlock"]>[data-testid="column"]{flex:1 1 100% !important}}

/* ── Buttons — big touch targets ── */
.stButton>button{
    width:100% !important;border-radius:14px !important;
    height:52px !important;font-size:15px !important;
    font-weight:700 !important;border:none !important;
    min-height:44px !important;touch-action:manipulation}
.stButton>button[kind="primary"]{
    background:#1668e3 !important;color:#fff !important;box-shadow:none !important}
.stButton>button[kind="primary"]:active{background:#1255c0 !important}
.stButton>button[kind="secondary"]{
    background:#fff !important;border:1.5px solid #ddd !important;color:#616161 !important}
.stButton>button[kind="secondary"]:active{background:#f0f0f0 !important}

.bb-wrap .stButton>button{
    height:52px !important;border-radius:14px !important;
    font-size:15px !important;font-weight:600 !important;width:100% !important}
.bb-wrap .stButton>button[kind="primary"]{
    background:#1668e3 !important;color:#fff !important;border:none !important;box-shadow:none !important}
.bb-wrap .stButton>button[kind="secondary"]{
    background:transparent !important;border:none !important;
    color:#9e9e9e !important;font-size:12px !important;
    font-weight:400 !important;height:36px !important;
    text-decoration:underline !important;text-underline-offset:3px !important}

/* ── Link button ── */
[data-testid="stLinkButton"] a{
    background:#6398c8 !important;color:#fff !important;
    border-radius:14px !important;height:52px !important;
    font-size:14px !important;font-weight:700 !important;border:none !important;
    display:flex !important;align-items:center !important;
    justify-content:center !important;text-decoration:none !important}

/* ── Checkbox ── */
[data-testid="stCheckbox"] label{font-size:13px !important;color:#616161 !important;font-weight:500 !important}
[data-testid="stCheckbox"] input{width:20px !important;height:20px !important}

/* ── Mode toggle ── */
.mode-toggle{display:grid;grid-template-columns:1fr 1fr;gap:0;
    background:#e4e4e4;border-radius:14px;padding:3px;margin-bottom:12px}
.mode-toggle .stButton>button{
    height:44px !important;border-radius:11px !important;
    font-size:13px !important;font-weight:600 !important;border:none !important;
    box-shadow:none !important;background:transparent !important;color:#9e9e9e !important}
.mode-toggle .stButton>button[kind="primary"]{
    background:#fff !important;color:#191d3a !important;
    box-shadow:0 1px 4px rgba(0,0,0,.12) !important}

/* ── Notices ── */
.notice{border-radius:12px;padding:10px 13px;font-size:13px;line-height:1.5;
    display:flex;align-items:flex-start;gap:8px;margin-bottom:10px}
.nok{background:#f0fdf4;border:1px solid #86efac;color:#166534}
.nerr{background:#fff1f2;border:1px solid #fecdd3;color:#9f1239}
.ninfo{background:#e8f0fe;border:1px solid #6398c8;color:#1e3a6e}
.nwarn{background:#fffbeb;border:1px solid #fde68a;color:#92400e}
.nviolet{background:#faf5ff;border:1px solid #d8b4fe;color:#6b21a8}

/* ── Expedia banner & upload ── */
.expedia-banner{background:#fff;border:1.5px solid #ddd;border-bottom:none;
    border-radius:16px 16px 0 0;padding:11px 14px;
    display:flex;align-items:center;justify-content:space-between;margin-top:14px}
.expedia-banner img{height:22px;width:auto;object-fit:contain}
.taap-pill{font-size:10px;font-weight:700;letter-spacing:.3px;
    color:#1e3a6e;background:#e8f0fe;border:1px solid #6398c8;
    padding:3px 10px;border-radius:20px;white-space:nowrap}

[data-testid="stFileUploader"] [data-testid="stWidgetLabel"],
[data-testid="stFileUploader"] [data-testid="stWidgetLabel"] *{display:none !important}
[data-testid="stFileUploaderDropzoneInput"] + label,
[data-testid="stFileUploader"] > section > label,
[data-testid="stFileUploader"] label[for]{
    display:none !important;visibility:hidden !important;height:0 !important;overflow:hidden !important}
[data-testid="stFileUploader"]{margin-top:0 !important}
[data-testid="stFileUploader"]>div:first-child,[data-testid="stFileUploader"] section{
    border:1.5px dashed #b8cde0 !important;border-top:none !important;
    border-radius:0 0 16px 16px !important;background:#f5f8fc !important;
    margin-top:0 !important;padding:24px 16px !important;min-height:110px !important}
[data-testid="stFileUploader"]>div:first-child:hover,[data-testid="stFileUploader"] section:hover{
    border-color:#6398c8 !important;background:#e8f0fe !important}
[data-testid="stFileUploader"] button{
    border-radius:10px !important;border:1.5px solid #ddd !important;
    background:#fff !important;color:#191d3a !important;
    font-size:14px !important;font-weight:600 !important;
    padding:10px 20px !important;height:auto !important;min-height:44px !important}
[data-testid="stFileUploaderDropInstructions"]{font-size:14px !important;font-weight:600 !important;color:#191d3a !important}
[data-testid="stFileUploaderDropInstructions"] small,
[data-testid="stFileUploaderDropInstructions"] span{font-size:12px !important;color:#9e9e9e !important;font-weight:400 !important}

/* ── Stats grid ── */
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
.stat-card{background:#fff;border:1.5px solid #ddd;border-radius:16px;padding:14px 13px}
.stat-val{font-size:20px;font-weight:800;color:#191d3a;line-height:1.1}
.stat-lbl{font-size:10px;color:#9e9e9e;margin-top:4px;font-weight:500}

/* ── Progress bar ── */
.bulk-prog{background:#ddd;border-radius:99px;height:5px;overflow:hidden;margin-bottom:6px}
.bulk-prog-f{height:100%;background:#6398c8;border-radius:99px;transition:width .3s}
.bulk-prog-lbl{font-size:12px;color:#9e9e9e;text-align:center;margin-bottom:12px;font-weight:500}

/* ── Bulk summary ── */
.bulk-sum{background:#fff;border:1.5px solid #ddd;border-radius:16px;padding:16px 14px;margin-bottom:14px}
.bulk-sum-ttl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#9e9e9e;margin-bottom:12px}
.bulk-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;text-align:center;margin-bottom:12px}
.bs-val{font-size:22px;font-weight:800;color:#191d3a;line-height:1}
.bs-lbl{font-size:9px;color:#9e9e9e;margin-top:3px;font-weight:500}
.bs-g{color:#1e9e5a}.bs-r{color:#e53935}.bs-y{color:#e68900}
.bulk-bar{background:#e8e8e8;border-radius:99px;height:5px;overflow:hidden}
.bulk-bar-f{height:100%;background:#1e9e5a;border-radius:99px}
.bulk-pct{font-size:11px;color:#9e9e9e;text-align:right;margin-top:4px}

/* ── File result cards ── */
.file-item{background:#fff;border:1.5px solid #ddd;border-radius:14px;padding:12px 13px;margin-bottom:8px}
.fi-success{border-color:#6ee7b7 !important;background:#f0fdf4 !important}
.fi-error{border-color:#fca5a5 !important;background:#fff1f2 !important}
.fi-skipped{border-color:#fcd34d !important;background:#fffde7 !important}
.fi-top{display:flex;align-items:center;gap:9px}
.fi-icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0}
.ic-ok{background:#dcfce7}.ic-err{background:#ffe4e6}.ic-skip{background:#fef9c3}.ic-n{background:#ededed}
.fi-name{font-size:12px;font-weight:600;color:#191d3a;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fi-badge{font-size:10px;font-weight:700;padding:3px 9px;border-radius:20px;white-space:nowrap}
.fb-ok{background:#dcfce7;color:#166534}.fb-err{background:#ffe4e6;color:#9f1239}.fb-sk{background:#fef9c3;color:#7a5c00}
.fi-grid{margin-top:9px;padding-top:8px;border-top:1px solid #ededed;display:grid;grid-template-columns:1fr 1fr;gap:5px 12px}
.fi-kv{display:flex;gap:4px;align-items:baseline}
.fi-k{font-size:9px;font-weight:700;color:#9e9e9e;min-width:48px;flex-shrink:0;text-transform:uppercase;letter-spacing:.3px}
.fi-v{font-size:12px;font-weight:500;color:#191d3a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* ── Settings rows ── */
.st-row{display:flex;align-items:center;gap:10px;background:#fff;
    border:1.5px solid #ddd;border-radius:14px;padding:12px 13px;margin-bottom:8px}
.st-icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0}
.si-g{background:#f0fdf4}.si-r{background:#fff1f2}.si-b{background:#e8f0fe}.si-y{background:#fffde7}
.st-body{flex:1;min-width:0}
.st-title{font-size:13px;font-weight:700;color:#191d3a;line-height:1}
.st-sub{font-size:11px;color:#9e9e9e;margin-top:2px}
.st-badge{display:inline-flex;align-items:center;font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;flex-shrink:0}
.bg{background:#f0fdf4;color:#166534;border:1px solid #86efac}
.br{background:#fff1f2;color:#9f1239;border:1px solid #fecdd3}
.by{background:#fffde7;color:#7a5c00;border:1px solid #fcd34d}

/* ── AI settings ── */
.ai-card-btn-wrap .stButton>button{
    height:52px !important;border-radius:14px !important;font-size:14px !important;
    font-weight:500 !important;padding:0 14px !important;margin-bottom:8px !important}
.ai-card-btn-wrap .stButton>button[kind="secondary"]{
    background:#fff !important;border:1px solid #e0e0e0 !important;color:#191d3a !important;box-shadow:none !important}
.ai-card-btn-wrap .stButton>button[kind="primary"]{
    background:#f0fdf4 !important;border:1.5px solid #1D9E75 !important;color:#191d3a !important;box-shadow:none !important}
.ai-status-bar{display:flex;align-items:center;gap:8px;padding:9px 13px;
    border-radius:10px;background:#f0fdf4;border:1px solid #bbf7d0;margin-bottom:16px}
.ai-status-dot{width:6px;height:6px;border-radius:50%;background:#1D9E75;flex-shrink:0}
.ai-status-txt{font-size:12px;color:#166534}
.ai-key-row{display:flex;align-items:center;justify-content:space-between;
    padding:10px 13px;border-radius:10px;background:#fff;border:1px solid #e8e8e8;margin-bottom:6px}
.ai-key-left{display:flex;align-items:center;gap:8px}
.ai-key-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.ai-key-name{font-size:13px;color:#191d3a}
.ai-key-ok{font-size:11px;color:#1D9E75}
.ai-key-warn{font-size:11px;color:#e68900}

/* ── About box ── */
.about-box{background:#fff;border:1.5px solid #ddd;border-radius:16px;padding:14px 16px}
.about-ttl{font-size:14px;font-weight:800;color:#191d3a;margin-bottom:12px}
.about-r{display:flex;gap:8px;margin-bottom:6px}
.about-k{font-size:11px;font-weight:700;color:#191d3a;width:62px;flex-shrink:0}
.about-v{font-size:11px;color:#616161;line-height:1.5}

/* ── DataTable ── */
[data-testid="stDataFrame"]{border-radius:14px !important;border:1.5px solid #ddd !important;overflow:hidden !important;box-shadow:none !important}
[data-testid="stDataFrame"] th{background:#f5f8fc !important;color:#616161 !important;font-size:10px !important;font-weight:700 !important;text-transform:uppercase !important;letter-spacing:.4px !important;border-bottom:1.5px solid #ddd !important;padding:9px 11px !important}
[data-testid="stDataFrame"] td{font-size:12px !important;color:#191d3a !important;padding:9px 11px !important;border-bottom:1px solid #ededed !important}
[data-testid="stDataFrame"] tr:hover td{background:#f5f8fc !important}

/* ── Spinner ── */
.stSpinner>div{border-top-color:#6398c8 !important}

/* ── Date input fix ── */
[data-testid="stDateInput"] input{
    font-size:15px !important;height:52px !important;
    border-radius:12px !important;border:1.5px solid #ddd !important;
    padding:0 14px !important;-webkit-appearance:none;appearance:none}

/* ═══════════════════════════════════════════════
   PORTRAIT MODE  (lebar ≤ 430px, orientasi tegak)
   ═══════════════════════════════════════════════ */
@media screen and (max-width:430px) and (orientation:portrait){
  .main .block-container{
    padding:6px 10px max(90px,calc(72px + env(safe-area-inset-bottom))) !important;
    max-width:100vw !important}
  .app-header{padding:10px 12px;border-radius:14px;gap:8px}
  .ah-icon{width:36px;height:36px;font-size:18px}
  .ah-title{font-size:14px}
  .ah-sub{font-size:10px}
  .ah-ai-badge{font-size:8px;padding:2px 7px}
  .ah-live{font-size:8px;padding:3px 8px}
  [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important;gap:6px !important}
  [data-testid="stHorizontalBlock"]>[data-testid="column"]{
    flex:1 1 100% !important;min-width:100% !important;max-width:100% !important}
  .nb-wrap .stButton>button{height:52px !important;font-size:8px !important;padding:3px 1px !important}
  .mode-toggle{margin-bottom:10px}
  .mode-toggle .stButton>button{height:40px !important;font-size:12px !important}
  .stTextInput input,.stNumberInput input{height:50px !important;font-size:16px !important}
  [data-testid="stSelectbox"]>div>div{height:50px !important;min-height:50px !important;font-size:15px !important}
  [data-testid="stDateInput"] input{height:50px !important;font-size:15px !important}
  .stButton>button{height:50px !important;font-size:15px !important;border-radius:13px !important}
  .bb-wrap .stButton>button{height:50px !important}
  .sec-lbl{font-size:10px;margin:12px 0 7px}
  .notice{font-size:12px;padding:9px 11px}
  .stat-val{font-size:18px}
  .stat-card{padding:12px 11px;border-radius:14px}
  .bs-val{font-size:20px}
  .fi-name{font-size:11px}
  .fi-k{font-size:9px;min-width:44px}
  .fi-v{font-size:11px}
  .expedia-banner{padding:9px 12px}
  .expedia-banner img{height:20px}
  .taap-pill{font-size:9px;padding:2px 8px}
  [style*="background:#f0fdf4"][style*="line-height:1.8"]{font-size:10px !important;padding:8px 11px !important}
  [style*="background:#e8f0fe"][style*="border-radius:12px"]{padding:8px 10px !important}
  [style*="background:#e8f0fe"] > div:first-child{font-size:9px !important}
  [style*="background:#e8f0fe"] > div:last-child{font-size:13px !important}
  .about-r{gap:6px}
  .about-k{width:54px;font-size:10px}
  .about-v{font-size:10px}
}

@media screen and (max-width:375px) and (orientation:portrait){
  .main .block-container{padding-left:8px !important;padding-right:8px !important}
  .ah-title{font-size:13px}
  .stat-val{font-size:16px}
  .stat-lbl{font-size:9px}
  .bulk-stats .bs-val{font-size:18px}
}

@media screen and (orientation:landscape){
  [data-testid="stHorizontalBlock"]{flex-wrap:nowrap !important}
  [data-testid="stHorizontalBlock"]>[data-testid="column"]{flex:1 1 0% !important;min-width:0 !important}
  .main .block-container{max-width:600px !important}
}
</style>
""", unsafe_allow_html=True)


# ─── AI Provider helpers ──────────────────────────────────────────────────────
def get_ai_provider(): return st.session_state.get("ai_provider", "claude")

def get_openai_key():
    try:
        k = st.secrets["openai"]["api_key"]
        if k and len(k) > 20 and "GANTI" not in k and "PASTE" not in k: return k
    except: pass
    return st.session_state.get("openai_key_manual", "")

def get_claude_key():
    try:
        k = st.secrets["anthropic"]["api_key"]
        if k and len(k) > 20 and "GANTI" not in k and "PASTE" not in k: return k
    except: pass
    return st.session_state.get("claude_key_manual", "")

def active_ai_ready():
    if get_ai_provider() == "openai": return bool(get_openai_key())
    return bool(get_claude_key())

# ─── Google Sheets ────────────────────────────────────────────────────────────
def sheet_id():
    try:
        s = st.secrets["google_sheets"]["sheet_id"]
        if s and "GANTI" not in s: return s
    except: pass
    return st.session_state.get("sheet_id", "")

COLS = ["Timestamp Input","Supplier","Booking ID","Booking Date","Issued Date",
        "Hotel","Check-in","Room x Night","Room Nights","Total (Rp)","Check-out","Guest Name",
        "Kartu Kredit","Issuer","PIC","No. BC","Nama Kegiatan","Catatan"]

@st.cache_resource(ttl=300)
def ws():
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"])
    s = gspread.authorize(creds).open_by_key(sheet_id()).sheet1
    try:
        if not s.row_values(1) or s.cell(1,1).value != COLS[0]: s.insert_row(COLS,1)
    except: s.insert_row(COLS,1)
    return s

def save_row(d):
    ws().append_row([d.get(k,"") for k in [
        "timestamp_input","supplier","booking_id","booked_on","issued_on","hotel",
        "checkin","qty","room_nights","room","checkout","name","card","issuer","pic",
        "no_bc","nama_kegiatan","notes"]], value_input_option="USER_ENTERED")

def load_rows(): return ws().get_all_records()

# ─── Duplicate check ──────────────────────────────────────────────────────────
def _ns(v): return str(v or "").strip().lower()
def _ni(v):
    try: return int(float(str(v).replace(",","").replace(".","") or 0))
    except: return 0

def _parse_room_nights(qty_str: str) -> int:
    """
    Parse qty string like "1 room x 6 nights", "2 rooms x 3 malam", "3 kamar x 4 malam"
    Returns total room-nights as integer. E.g. "1 room x 6 nights" -> 6
    """
    if not qty_str: return 0
    s = str(qty_str).strip().lower()
    # Pattern: NUMBER x NUMBER (rooms x nights or nights x rooms)
    m = re.search(r'(\d+)\s*(?:room[s]?|kamar)?\s*[x×]\s*(\d+)', s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return a * b  # rooms × nights = total room-nights
    # Pattern: just a number
    m2 = re.search(r'(\d+)', s)
    if m2: return int(m2.group(1))
    return 0

def _fmt_date_display(v: str) -> str:
    """Convert YYYY-MM-DD to DD/MM/YYYY for display, pass through others."""
    if not v: return ""
    s = str(v).strip()
    # Already YYYY-MM-DD
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m: return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return s

def check_duplicate(new, rows):
    bid = _ns(new.get("booking_id"))
    for r in rows:
        if bid and bid == _ns(r.get("Booking ID")): return True,"Booking ID sudah terdaftar",r
        sc = sum([_ns(new.get("hotel"))==_ns(r.get("Hotel")),
                  _ns(new.get("checkin"))==_ns(r.get("Check-in")),
                  _ns(new.get("name"))==_ns(r.get("Guest Name")),
                  _ni(new.get("room"))==_ni(r.get("Total (Rp)"))])
        if sc >= 3: return True,"Kemungkinan duplikat (kesamaan tinggi)",r
    return False,"",None

# ─── PDF helpers ──────────────────────────────────────────────────────────────
def pdf_images(data):
    if not _PDF_OK: raise RuntimeError("pypdfium2 not installed")
    doc = _pdfium.PdfDocument(data)
    return [doc[i].render(scale=2.0).to_pil() for i in range(len(doc))]

def pdf_text(data):
    if not _PDF_OK or not data: return ""
    try:
        doc,parts = _pdfium.PdfDocument(data),[]
        for i in range(len(doc)):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                parts.append(doc[i].get_textpage().get_text_bounded())
        return "\n".join(parts).strip()
    except: return ""

def to_b64(img):
    buf = io.BytesIO(); img.save(buf,"JPEG",quality=92)
    return base64.b64encode(buf.getvalue()).decode(),"image/jpeg"

# ─── AI Prompts ───────────────────────────────────────────────────────────────
_SYS = """You are a corporate hotel expense AI parser for credit card reporting.
Parse any document: Expedia TAAP receipt, Mitra Tours itinerary, hotel invoice.
Return ONLY a valid JSON object — no markdown, no explanation.
Keys: supplier, booking_id, booked_on (YYYY-MM-DD), issued_on (YYYY-MM-DD),
hotel, checkin (YYYY-MM-DD), checkout (YYYY-MM-DD),
qty (ALWAYS format as "N room x N nights", e.g. "1 room x 6 nights"),
room (integer total IDR, strip Rp/commas), name (primary guest),
card (e.g. "Visa •••• 0191"), notes (room type, tax, etc.)

Rules:
1. ALL dates MUST be converted to YYYY-MM-DD without exception.
   - "Booking Date" / "Booked On" / "Order Date"  -> booked_on
   - "Issued Date" / "Issue Date" / "Invoice Date" -> issued_on
   - "Check-in" / "Check In" / "Arrival"           -> checkin
   - "Check-out" / "Check Out" / "Departure"        -> checkout
   - Handle ANY format: DD/MM/YYYY, MM/DD/YYYY, DD MMM YYYY, MMM DD YYYY, YYYY-MM-DD
   - Example: "15 May 2026" -> "2026-05-15", "05/15/2026" -> "2026-05-15"
   - If checkin and checkout are known, compute booked_on/issued_on from context.
2. qty field: ALWAYS use "N room x N nights" format.
   - Count rooms and nights from the document. If "1 room, 6 nights" -> "1 room x 6 nights"
   - If only nights/malam mentioned: "6 malam" -> "1 room x 6 nights"
   - NEVER leave qty empty if checkin+checkout are present; compute nights = checkout - checkin.
3. Amounts -> plain integer (strip Rp, IDR, commas, dots).
4. Missing -> "" strings, 0 integers.
5. Ambiguous dates (01/02/03) -> prefer DD/MM/YYYY for Indonesian docs."""

_SYS_NONEXP = """You are a payment receipt parser. Extract ONLY these 4 fields.
Return ONLY a valid JSON object — no markdown, no explanation.
Keys:
- timestamp_input : string — Date/Time exactly as shown (e.g. "15/05/2026 16:18:34")
- booking_id      : string — Invoice Number / Reference Number / Transaction ID
- room            : integer — Amount charged, strip IDR/Rp/,/. -> plain integer only
- card            : string — Card Number as shown (e.g. "521558******4467")
Missing -> "" for strings, 0 for integers."""

# ─── AI Parsers ───────────────────────────────────────────────────────────────
def _call_openai(content, sys_prompt, max_tokens=800):
    import openai, httpx
    key = get_openai_key()
    if not key: raise ValueError("OpenAI API key belum diisi.")
    resp = openai.OpenAI(api_key=key, http_client=httpx.Client()).chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":sys_prompt},{"role":"user","content":content}],
        temperature=0.0, max_tokens=max_tokens)
    raw = resp.choices[0].message.content
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m: raise ValueError("Format AI tidak valid.")
    return json.loads(m.group()), raw

def _call_claude(content, sys_prompt, max_tokens=800):
    import anthropic
    key = get_claude_key()
    if not key: raise ValueError("Anthropic API key belum diisi.")
    resp = anthropic.Anthropic(api_key=key).messages.create(
        model="claude-sonnet-4-5", max_tokens=max_tokens,
        system=sys_prompt, messages=[{"role":"user","content":content}])
    raw = resp.content[0].text
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m: raise ValueError("Format AI tidak valid.")
    return json.loads(m.group()), raw

def _build_expedia(text, images):
    if get_ai_provider() == "claude":
        c = []
        if images:
            for b64,mime in images: c.append({"type":"image","source":{"type":"base64","media_type":mime,"data":b64}})
        c.append({"type":"text","text":text or "Extract all structured data."})
        return c
    else:
        c = []
        if images:
            for b64,mime in images: c.append({"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}","detail":"high"}})
        c.append({"type":"text","text":text or "Extract all structured data."})
        return c

def _build_receipt(images):
    if get_ai_provider() == "claude":
        c = []
        for b64,mime in images: c.append({"type":"image","source":{"type":"base64","media_type":mime,"data":b64}})
        c.append({"type":"text","text":"Extract the 4 fields from this payment receipt."})
        return c
    else:
        c = []
        for b64,mime in images: c.append({"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}","detail":"high"}})
        c.append({"type":"text","text":"Extract the 4 fields from this payment receipt."})
        return c

def ai_parse(text="", images=None):
    c = _build_expedia(text, images)
    if get_ai_provider() == "claude": return _call_claude(c, _SYS)
    return _call_openai(c, _SYS)

def ai_parse_receipt(images):
    c = _build_receipt(images)
    if get_ai_provider() == "claude": return _call_claude(c, _SYS_NONEXP, max_tokens=400)
    return _call_openai(c, _SYS_NONEXP, max_tokens=400)

# ─── UI utilities ─────────────────────────────────────────────────────────────
def fmt(v):
    try: return "Rp {:,}".format(int(float(v or 0))).replace(",",".")
    except: return str(v) if v else "—"

def now_ts(): return datetime.now().strftime("%d/%m/%Y %H:%M")

def notice(kind, msg):
    icons = {"ok":"✓","err":"✕","info":"ℹ","warn":"⚠","violet":"✦"}
    cls   = {"ok":"nok","err":"nerr","info":"ninfo","warn":"nwarn","violet":"nviolet"}
    st.markdown(f'<div class="notice {cls.get(kind,"ninfo")}"><b>{icons.get(kind,"ℹ")}</b>&ensp;{msg}</div>',
                unsafe_allow_html=True)

# ─── Card normalizer (UPDATED) ────────────────────────────────────────────────
# Maps known BIN6 to (Brand, last4)
_BIN_MAP = {"521558": ("MasterCard", "4467"), "489594": ("Visa", "0191")}

# Canonical display strings (lowercase key → display value)
_DISPLAY_MAP = {
    "mastercard \u2022\u2022\u2022\u2022 4467": "MasterCard \u2022\u2022\u2022\u2022 4467",
    "visa \u2022\u2022\u2022\u2022 0191":        "Visa \u2022\u2022\u2022\u2022 0191",
}

# Brand name aliases for pattern matching
_BRAND_ALIAS = {
    "mastercard":  "MasterCard",
    "master card": "MasterCard",
    "visa":        "Visa",
}

def normalize_card(raw: str) -> str:
    """
    Normalizes any card string to canonical form: "Brand •••• last4"
    Handles inputs like:
      - "521558******4467"        (BIN-based)
      - "MasterCard .... 4467"    (dots)
      - "MasterCard **** 4467"    (asterisks)
      - "MasterCard •••• 4467"    (already correct)
      - "mastercard •••• 4467"    (lowercase)
    """
    if not raw: return ""
    v = str(raw).strip()
    _lower = re.sub(r"\s+", " ", v.lower())

    # 1. Direct display map lookup (exact match after normalization)
    if _lower in _DISPLAY_MAP:
        return _DISPLAY_MAP[_lower]

    # 2. Pattern: "BrandName [mask] last4"
    #    Mask = any combo of . * • - x (with optional spaces)
    _m = re.match(
        r'^(mastercard|master\s+card|visa)\s*[\.\*\u2022\-x]+\s*(\d{4})$',
        _lower, re.IGNORECASE
    )
    if _m:
        brand_key = re.sub(r'\s+', ' ', _m.group(1).strip().lower())
        last4 = _m.group(2)
        brand = _BRAND_ALIAS.get(brand_key, brand_key.title())
        # Verify against known BIN map for canonical casing
        for _bin6, (b, l4) in _BIN_MAP.items():
            if b.lower() == brand.lower() and l4 == last4:
                return f"{b} \u2022\u2022\u2022\u2022 {l4}"
        return f"{brand} \u2022\u2022\u2022\u2022 {last4}"

    # 3. BIN-based lookup (digits only input like "521558******4467")
    digits = re.sub(r"[^\d]", "", v)
    if len(digits) >= 6:
        bin6 = digits[:6]
        if bin6 in _BIN_MAP:
            brand, last4 = _BIN_MAP[bin6]
            return f"{brand} \u2022\u2022\u2022\u2022 {last4}"

    # 4. Fallback: return as-is
    return v

# ─── Session state ────────────────────────────────────────────────────────────
_DEF = {
    "tab":"input","input_mode":"expedia","bulk_results":[],"bulk_saved_count":0,
    "openai_key_manual":"","claude_key_manual":"","ai_provider":"claude",
    "sheet_id":"1nvgMCmo1EJtbCAt0db_OizvPYDvaEzphKhwzBJ-3X_g",
    "last_issuer":"","last_pic":"","last_no_bc":"","last_nama_kegiatan":"",
    "_ne_last_file_key":"","_ne_prefill_ts":"","_ne_prefill_bid":"",
    "_ne_prefill_room":"","_ne_prefill_card":"","_ne_parse_ok":False,"_ne_parse_err":"",
    "_app_login_err":"",
    "_dash_auth_ok":False,"_dash_login_err":"",
}
for _k,_v in _DEF.items():
    if _k not in st.session_state: st.session_state[_k] = _v

# ─── Header ───────────────────────────────────────────────────────────────────
_prov = get_ai_provider()
_prov_lbl = "GPT-4o mini" if _prov=="openai" else "Claude Sonnet"
_prov_cls = "ah-ai-openai" if _prov=="openai" else "ah-ai-claude"
_prov_ico = "🤖" if _prov=="openai" else "🟣"

st.markdown(f"""
<div class="app-header">
  <div class="ah-icon" style="background:#fff;padding:2px;overflow:hidden;"><img src="data:image/png;base64,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" style="width:100%;height:100%;object-fit:contain;border-radius:9px;" alt="Mitra"></div>
  <div>
    <div class="ah-title">CC Reporting</div>
    <div class="ah-sub">Mitra Tours &amp; Travel</div>
  </div>
  <span class="ah-ai-badge {_prov_cls}">{_prov_ico} {_prov_lbl}</span>
  <div class="ah-live">LIVE</div>
</div>
""", unsafe_allow_html=True)

# ─── Bottom Navigation Bar ────────────────────────────────────────────────────
_cur = st.session_state["tab"]

_tab_icons = {"input":"","dashboard":"","log":"","settings":""}
_tab_labels = {"input":"Input","dashboard":"Dashboard","log":"Activity","settings":"Settings"}
_tab_keys   = ["input","dashboard","log","settings"]

st.markdown('<div class="nb-wrap">', unsafe_allow_html=True)
_cols = st.columns(4)
for i, _tk in enumerate(_tab_keys):
    with _cols[i]:
        _ico = _tab_icons[_tk]
        _lbl = _tab_labels[_tk]
        if st.button(f"{_ico}\n{_lbl}", key=f"nb_{_tk}", use_container_width=True,
                     type="primary" if _cur==_tk else "secondary"):
            st.session_state["tab"] = _tk; st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<script>
(function(){
  const nb = document.querySelector('.nb-wrap');
  if(!nb) return;
  nb.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:9999;'+
    'background:#fff;border-top:1px solid #e8e8e8;padding:4px 8px '+
    'calc(4px + env(safe-area-inset-bottom));'+
    'box-shadow:0 -4px 20px rgba(0,0,0,.08);max-width:100vw';
})();
</script>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — INPUT
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state["tab"] == "input":

    if not active_ai_ready():
        _nm = "OpenAI" if get_ai_provider()=="openai" else "Anthropic"
        notice("err", f"{_nm} API key belum diisi — buka <b>Settings</b>."); st.stop()
    if not _PDF_OK:
        notice("warn","pypdfium2 belum terinstall — PDF nonaktif.")

    # ── Mode toggle ───────────────────────────────────────────────────────────
    _cur_mode = st.session_state["input_mode"]
    st.markdown('<div class="mode-toggle">', unsafe_allow_html=True)
    _ma,_mb = st.columns(2)
    with _ma:
        if st.button("✈  Expedia / TAAP", key="mode_expedia", use_container_width=True,
                     type="primary" if _cur_mode=="expedia" else "secondary"):
            st.session_state["input_mode"]="expedia"; st.session_state["bulk_results"]=[]; st.rerun()
    with _mb:
        if st.button("🧾  Non-Expedia", key="mode_nonexp", use_container_width=True,
                     type="primary" if _cur_mode=="nonexpedia" else "secondary"):
            st.session_state["input_mode"]="nonexpedia"; st.session_state["bulk_results"]=[]
            for _k in ["_ne_last_file_key","_ne_prefill_ts","_ne_prefill_bid",
                        "_ne_prefill_room","_ne_prefill_card","_ne_parse_ok","_ne_parse_err"]:
                st.session_state[_k] = _DEF.get(_k,"")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Issuer & PIC ──────────────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl">Issuer &amp; PIC</div>', unsafe_allow_html=True)
    _ISSUERS = ["","Ade Puspitasari","Farras Mahmud","Meijika",
        "Muhammad Geraldi Jagaddhita","Nur Anissa Firda Aulia","Riega Wisudhantara",
        "Rifyal Tumber","Selvy Anggraini","Shaiful Baldy","Veronica Novi Heri","Rida Manora Nasution"]
    _li = st.session_state.get("last_issuer","")
    _bi = _ISSUERS.index(_li) if _li in _ISSUERS else 0
    _ca,_cb = st.columns(2)
    bulk_issuer = _ca.selectbox("Issuer *",options=_ISSUERS,index=_bi,
        format_func=lambda x:"— Pilih —" if x=="" else x, key="bulk_issuer")
    bulk_pic = _cb.text_input("PIC *",value=st.session_state.get("last_pic",""),
        placeholder="Nama PIC",key="bulk_pic")
    _cc,_cd = st.columns(2)
    bulk_no_bc = _cc.text_input("No. BC",value=st.session_state.get("last_no_bc",""),
        placeholder="Nomor BC",key="bulk_no_bc")
    bulk_nama_kegiatan = _cd.text_input("Nama Kegiatan",value=st.session_state.get("last_nama_kegiatan",""),
        placeholder="Kegiatan",key="bulk_nama_kegiatan")

    _ap = get_ai_provider()
    if _ap=="claude": notice("violet","AI: <b>Claude</b> (Anthropic) &nbsp;·&nbsp; Ganti di Settings")
    else: notice("info","AI: <b>OpenAI</b> &nbsp;·&nbsp; Ganti di Settings")

    # ══════════════════════════════════════════════════════════════════════════
    #  MODE A — EXPEDIA
    # ══════════════════════════════════════════════════════════════════════════
    if _cur_mode == "expedia":
        st.markdown("""
<div class="expedia-banner">
  <img src="https://www.expedia.com/newsroom/wp-content/uploads/2023/07/BEX_Logo_Horizontal_CMYK_FullColorDarkBlue--1024x199.jpg"
    alt="Expedia TAAP" onerror="this.parentElement.style.display='none'">
  <span class="taap-pill">TAAP + Mitra Tours</span>
</div>""", unsafe_allow_html=True)

        _ftypes = ["jpg","jpeg","png","webp"] + (["pdf"] if _PDF_OK else [])
        bulk_files = st.file_uploader(label="",type=_ftypes,accept_multiple_files=True,
            label_visibility="collapsed",key="bulk_uf")
        _n = len(bulk_files) if bulk_files else 0
        if _n: notice("info",f"<b>{_n} file</b> dipilih dan siap diproses.")
        skip_dup = st.checkbox("Lewati duplikat",value=True,key="bulk_skip_dup")
        st.markdown("<div style='height:6px'></div>",unsafe_allow_html=True)
        st.markdown('<div class="bb-wrap">',unsafe_allow_html=True)
        _run = st.button("Submit",type="primary",use_container_width=True,
            disabled=(not _n or not bulk_issuer or not bulk_pic.strip()),key="bulk_run")
        _clear = st.button("Delete",type="secondary",use_container_width=True,key="bulk_clear")
        st.markdown('</div>',unsafe_allow_html=True)

        if _clear:
            st.session_state["bulk_results"]=[]; st.session_state["bulk_saved_count"]=0; st.rerun()

        if _run:
            st.session_state.update(last_issuer=bulk_issuer,last_pic=bulk_pic,
                last_no_bc=bulk_no_bc,last_nama_kegiatan=bulk_nama_kegiatan,
                bulk_results=[],bulk_saved_count=0)
            try: _existing = load_rows()
            except: _existing = []
            _all_res,_saved_run = [],0
            _slot = st.empty()
            for _idx,_uf in enumerate(bulk_files):
                _pct = int(_idx/_n*100)
                _slot.markdown(
                    '<div class="bulk-prog"><div class="bulk-prog-f" style="width:'+str(_pct)+'%"></div></div>'
                    '<div class="bulk-prog-lbl">'+str(_idx+1)+'/'+str(_n)+' · '+_uf.name+'</div>',
                    unsafe_allow_html=True)
                _res = {"file":_uf.name,"status":"error","parsed":{},"err":"","mode":"expedia"}
                try:
                    _raw = _uf.read(); _imgs,_txt = [],""
                    if _uf.name.lower().endswith(".pdf"):
                        if not _PDF_OK: raise RuntimeError("pypdfium2 tidak terinstall")
                        _pages = pdf_images(_raw); _imgs = [to_b64(pg) for pg in _pages]; _txt = pdf_text(_raw)
                    else:
                        _io = Image.open(io.BytesIO(_raw)).convert("RGB"); _b,_m = to_b64(_io); _imgs = [(_b,_m)]
                    _comb = ("EXTRACTED PDF TEXT (authoritative):\n"+_txt) if _txt else ""
                    _parsed,_ = ai_parse(_comb,_imgs or None)
                    _parsed["timestamp_input"] = now_ts()
                    _is_dup,_why,_ = check_duplicate({"booking_id":_parsed.get("booking_id"),
                        "hotel":_parsed.get("hotel"),"checkin":_parsed.get("checkin"),
                        "name":_parsed.get("name"),"room":_parsed.get("room")},_existing)
                    if _is_dup and skip_dup:
                        _res.update(status="skipped",parsed=_parsed,err=_why)
                    else:
                        _qty_str = _parsed.get("qty","")
                        _rn = _parse_room_nights(_qty_str)
                        save_row({"timestamp_input":_parsed.get("timestamp_input",""),
                            "supplier":_parsed.get("supplier",""),"booking_id":_parsed.get("booking_id",""),
                            "booked_on":_parsed.get("booked_on",""),"issued_on":_parsed.get("issued_on",""),
                            "hotel":_parsed.get("hotel",""),"checkin":_parsed.get("checkin",""),
                            "qty":_qty_str,"room_nights":_rn if _rn else "",
                            "room":_parsed.get("room",0),
                            "checkout":_parsed.get("checkout",""),"name":_parsed.get("name",""),
                            "card":normalize_card(_parsed.get("card","")),"issuer":bulk_issuer,"pic":bulk_pic,
                            "no_bc":bulk_no_bc.strip(),"nama_kegiatan":bulk_nama_kegiatan.strip(),
                            "notes":_parsed.get("notes","")})
                        _res.update(status="success",parsed=_parsed); _saved_run += 1
                        _existing.append({"Booking ID":_parsed.get("booking_id",""),
                            "Hotel":_parsed.get("hotel",""),"Check-in":_parsed.get("checkin",""),
                            "Guest Name":_parsed.get("name",""),"Total (Rp)":_parsed.get("room",0)})
                except Exception as _exc: _res.update(err=str(_exc)[:140])
                _all_res.append(_res)
            _slot.empty()
            st.session_state["bulk_results"] = _all_res
            st.session_state["bulk_saved_count"] = _saved_run
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    #  MODE B — NON-EXPEDIA
    # ══════════════════════════════════════════════════════════════════════════
    else:
        st.markdown("""
<div style="background:#fff;border:1.5px solid #ddd;border-bottom:none;
    border-radius:16px 16px 0 0;padding:11px 14px;
    display:flex;align-items:center;justify-content:space-between;margin-top:14px">
  <div style="display:flex;align-items:center;gap:8px">
    <span style="font-size:18px">🧾</span>
    <div>
      <div style="font-size:13px;font-weight:700;color:#191d3a">Non-Expedia — Payment Receipt</div>
      <div style="font-size:10px;color:#9e9e9e">AI baca 4 field · sisanya isian manual</div>
    </div>
  </div>
  <span style="font-size:9px;font-weight:700;color:#7a5c00;background:#fef9c3;
    border:1px solid #fcd34d;padding:3px 9px;border-radius:20px">Manual + AI</span>
</div>""", unsafe_allow_html=True)

        ne_files = st.file_uploader(label="",type=["jpg","jpeg","png","webp"],
            accept_multiple_files=False,label_visibility="collapsed",key="ne_uf")

        if ne_files:
            _cur_file_key = ne_files.name + str(ne_files.size)
            if _cur_file_key != st.session_state.get("_ne_last_file_key",""):
                with st.spinner("🤖 AI membaca receipt…"):
                    try:
                        _raw_pre = ne_files.read()
                        _io_pre  = Image.open(io.BytesIO(_raw_pre)).convert("RGB")
                        _b_pre,_m_pre = to_b64(_io_pre)
                        _pre_fields,_ = ai_parse_receipt([(_b_pre,_m_pre)])
                        st.session_state["_ne_prefill_ts"]   = str(_pre_fields.get("timestamp_input","")).strip()
                        st.session_state["_ne_prefill_bid"]  = str(_pre_fields.get("booking_id","")).strip()
                        st.session_state["_ne_prefill_card"] = normalize_card(str(_pre_fields.get("card","")).strip())
                        try:
                            _r = int(float(str(_pre_fields.get("room",0)).replace(",","").replace(".","") or 0))
                        except: _r = 0
                        st.session_state["_ne_prefill_room"] = str(_r) if _r else ""
                        st.session_state["_ne_last_file_key"] = _cur_file_key
                        st.session_state["_ne_parse_ok"]  = True
                        st.session_state["_ne_parse_err"] = ""
                    except Exception as _pre_exc:
                        st.session_state["_ne_parse_ok"]  = False
                        st.session_state["_ne_parse_err"] = str(_pre_exc)[:160]
                        st.session_state["_ne_last_file_key"] = _cur_file_key
                st.rerun()

            if st.session_state.get("_ne_parse_ok"):
                notice("ok","✓ AI berhasil membaca receipt · <b>Timestamp · Invoice · Amount · Card</b> terisi otomatis")
            elif st.session_state.get("_ne_parse_err"):
                notice("warn",f"AI gagal membaca · isi manual.")
        else:
            if st.session_state.get("_ne_last_file_key",""):
                for _k in ["_ne_last_file_key","_ne_prefill_ts","_ne_prefill_bid",
                            "_ne_prefill_room","_ne_prefill_card","_ne_parse_ok","_ne_parse_err"]:
                    st.session_state[_k] = _DEF.get(_k,"")

        st.markdown("""
<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:12px;
    padding:9px 12px;font-size:11px;color:#166534;margin:8px 0 4px;line-height:1.8">
  <b>✓ Otomatis dari AI:</b>
  📅 Timestamp &nbsp;·&nbsp; 💰 Total (Rp) &nbsp;·&nbsp; 💳 Kartu Kredit &nbsp;·&nbsp; 📄 Booking ID
</div>""", unsafe_allow_html=True)

        st.markdown('<div class="sec-lbl">Data Booking — Isian Manual</div>',unsafe_allow_html=True)

        _SUPPLIERS = ["Direct To Hotel", "Direct To Supplier"]
        _n1,_n2 = st.columns(2)
        ne_supplier = _n1.selectbox("Supplier *",options=_SUPPLIERS,index=0,key="ne_supplier")
        ne_hotel    = _n2.text_input("Hotel *",placeholder="Nama hotel",key="ne_hotel")

        _n3,_n4 = st.columns(2)
        ne_name = _n3.text_input("Guest Name *",placeholder="Nama tamu",key="ne_name")
        ne_booking_id = _n4.text_input(
            "Booking ID",
            value=st.session_state.get("_ne_prefill_bid",""),
            placeholder="Dari receipt / manual",
            key="ne_booking_id")

        def _fmt_date(d):
            try: return d.strftime("%Y-%m-%d") if d else ""
            except: return ""

        _n5,_n6 = st.columns(2)
        ne_checkin_d  = _n5.date_input("Check-in",value=None,format="DD/MM/YYYY",key="ne_checkin")
        ne_checkout_d = _n6.date_input("Check-out",value=None,format="DD/MM/YYYY",key="ne_checkout")
        ne_checkin = _fmt_date(ne_checkin_d); ne_checkout = _fmt_date(ne_checkout_d)

        _n7,_n8 = st.columns(2)
        ne_qty         = _n7.text_input("Room × Night",placeholder="1 room x 2 nights",key="ne_qty")
        ne_booked_on_d = _n8.date_input("Booking Date",value=None,format="DD/MM/YYYY",key="ne_booked_on")
        ne_booked_on   = _fmt_date(ne_booked_on_d)

        _n9,_n10 = st.columns(2)
        ne_issued_on_d = _n9.date_input("Issued Date",value=None,format="DD/MM/YYYY",key="ne_issued_on")
        ne_issued_on   = _fmt_date(ne_issued_on_d)
        ne_extra_notes = _n10.text_input("Catatan",placeholder="Opsional",key="ne_extra_notes")

        st.markdown("<div style='height:6px'></div>",unsafe_allow_html=True)

        _ne_ready = (bool(ne_files) and bool(bulk_issuer) and bool(bulk_pic.strip())
                     and bool(ne_supplier) and bool(ne_hotel.strip()) and bool(ne_name.strip()))

        st.markdown('<div class="bb-wrap">',unsafe_allow_html=True)
        _ne_run   = st.button("Submit",type="primary",use_container_width=True,
            disabled=not _ne_ready,key="ne_run")
        _ne_clear = st.button("Hapus Hasil",type="secondary",use_container_width=True,key="ne_clear")
        st.markdown('</div>',unsafe_allow_html=True)

        if not _ne_ready:
            _missing = []
            if not ne_files:           _missing.append("upload receipt")
            if not bulk_issuer:        _missing.append("Issuer")
            if not bulk_pic.strip():   _missing.append("PIC")
            if not ne_hotel.strip():   _missing.append("Hotel")
            if not ne_name.strip():    _missing.append("Guest Name")
            if _missing:
                st.markdown('<div style="font-size:11px;color:#9e9e9e;text-align:center;margin-top:4px">Lengkapi: '
                            +' · '.join(_missing)+'</div>',unsafe_allow_html=True)

        if _ne_clear:
            st.session_state["bulk_results"]=[]; st.session_state["bulk_saved_count"]=0
            for _k in ["_ne_last_file_key","_ne_prefill_ts","_ne_prefill_bid",
                        "_ne_prefill_room","_ne_prefill_card","_ne_parse_ok","_ne_parse_err"]:
                st.session_state[_k] = _DEF.get(_k,"")
            st.rerun()

        if _ne_run and _ne_ready:
            st.session_state.update(last_issuer=bulk_issuer,last_pic=bulk_pic,
                last_no_bc=bulk_no_bc,last_nama_kegiatan=bulk_nama_kegiatan,
                bulk_results=[],bulk_saved_count=0)
            _ne_res = {"file":ne_files.name,"status":"error","parsed":{},"err":"","mode":"nonexpedia"}
            try:
                _ts_final = st.session_state.get("_ne_prefill_ts","").strip() or now_ts()
                _inv_ai   = st.session_state.get("_ne_prefill_bid","").strip()
                _card_ai  = normalize_card(st.session_state.get("_ne_prefill_card","").strip())
                try: _total = int(st.session_state.get("_ne_prefill_room","0") or 0)
                except: _total = 0
                _booking_id_final = ne_booking_id.strip() or _inv_ai
                _catatan = _booking_id_final
                if ne_extra_notes.strip(): _catatan += " · " + ne_extra_notes.strip()
                _ne_qty_str = ne_qty.strip()
                _ne_rn = _parse_room_nights(_ne_qty_str)
                _parsed_ne = {
                    "timestamp_input":_ts_final,"supplier":ne_supplier,
                    "booking_id":_booking_id_final,"booked_on":ne_booked_on,
                    "issued_on":ne_issued_on,"hotel":ne_hotel.strip(),
                    "checkin":ne_checkin,"qty":_ne_qty_str,"room_nights":_ne_rn if _ne_rn else "",
                    "room":_total,
                    "checkout":ne_checkout,"name":ne_name.strip(),"card":_card_ai,
                    "issuer":bulk_issuer,"pic":bulk_pic.strip(),
                    "no_bc":bulk_no_bc.strip(),"nama_kegiatan":bulk_nama_kegiatan.strip(),
                    "notes":_catatan,
                }
                save_row(_parsed_ne)
                _ne_res.update(status="success",parsed=_parsed_ne)
                st.session_state["bulk_saved_count"] = 1
            except Exception as _exc_ne:
                _ne_res.update(err=str(_exc_ne)[:200])
            st.session_state["bulk_results"] = [_ne_res]; st.rerun()

    # ── Results ───────────────────────────────────────────────────────────────
    _results = st.session_state.get("bulk_results",[])
    if _results:
        _ok=sum(1 for r in _results if r["status"]=="success")
        _err=sum(1 for r in _results if r["status"]=="error")
        _skip=sum(1 for r in _results if r["status"]=="skipped")
        _tot=len(_results); _pct=int(_ok/_tot*100) if _tot else 0
        st.markdown(
            '<div class="bulk-sum"><div class="bulk-sum-ttl">Hasil Proses</div><div class="bulk-stats">'
            +f'<div><div class="bs-val">{_tot}</div><div class="bs-lbl">Total</div></div>'
            +f'<div><div class="bs-val bs-g">{_ok}</div><div class="bs-lbl">Tersimpan</div></div>'
            +f'<div><div class="bs-val bs-r">{_err}</div><div class="bs-lbl">Gagal</div></div>'
            +f'<div><div class="bs-val bs-y">{_skip}</div><div class="bs-lbl">Duplikat</div></div>'
            +'</div>'
            +f'<div class="bulk-bar"><div class="bulk-bar-f" style="width:{_pct}%"></div></div>'
            +f'<div class="bulk-pct">{_pct}% tersimpan</div></div>',unsafe_allow_html=True)
        for _r in _results:
            _s=_r["status"]; _p=_r.get("parsed",{}); _fn=_r["file"]; _rmode=_r.get("mode","expedia")
            _ic={"success":"ic-ok","error":"ic-err","skipped":"ic-skip"}.get(_s,"ic-n")
            _bc={"success":"fb-ok","error":"fb-err","skipped":"fb-sk"}.get(_s,"fb-ok")
            _sy={"success":"&#10003;","error":"&#10005;","skipped":"&#9888;"}.get(_s,"")
            _lb={"success":"Tersimpan","error":"Gagal","skipped":"Duplikat"}.get(_s,_s)
            _wc={"success":"fi-success","error":"fi-error","skipped":"fi-skipped"}.get(_s,"")
            if _p and _s in ("success","skipped"):
                _dw=('<div style="margin-top:7px;font-size:11px;color:#7a5c00;background:#fef9c3;padding:5px 9px;border-radius:8px">&#9888; '+_r.get("err","Duplikat")+'</div>') if _s=="skipped" else ""
                if _rmode=="nonexpedia":
                    _det=('<div style="margin-top:5px"><span style="font-size:9px;color:#7a5c00;background:#fef9c3;border:1px solid #fcd34d;border-radius:5px;padding:2px 7px;font-weight:600">🧾 Non-Expedia</span></div>'
                        +'<div class="fi-grid">'
                        +'<div class="fi-kv"><span class="fi-k">Hotel</span><span class="fi-v">'+(_p.get("hotel") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Total</span><span class="fi-v">'+fmt(_p.get("room",0))+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Tamu</span><span class="fi-v">'+(_p.get("name") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Kartu</span><span class="fi-v">'+(_p.get("card") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Booking</span><span class="fi-v">'+(_p.get("booking_id") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Waktu</span><span class="fi-v">'+(_p.get("timestamp_input") or "—")+'</span></div>'
                        +'</div>'+_dw)
                else:
                    _det=('<div class="fi-grid">'
                        +'<div class="fi-kv"><span class="fi-k">Hotel</span><span class="fi-v">'+(_p.get("hotel") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Total</span><span class="fi-v">'+fmt(_p.get("room",0))+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Tamu</span><span class="fi-v">'+(_p.get("name") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Booking</span><span class="fi-v">'+(_p.get("booking_id") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Check-in</span><span class="fi-v">'+(_p.get("checkin") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Supplier</span><span class="fi-v">'+(_p.get("supplier") or "—")+'</span></div>'
                        +'</div>'+_dw)
            elif _r.get("err"):
                _det='<div class="fi-grid" style="grid-template-columns:1fr"><div class="fi-kv"><span class="fi-k">Error</span><span class="fi-v" style="color:#e53935;white-space:normal">'+_r["err"]+'</span></div></div>'
            else: _det=""
            st.markdown('<div class="file-item '+_wc+'"><div class="fi-top"><div class="fi-icon '+_ic+'">&#128247;</div><div class="fi-name">'+_fn+'</div><span class="fi-badge '+_bc+'">'+_sy+' '+_lb+'</span></div>'+_det+'</div>',unsafe_allow_html=True)
        _sid = sheet_id()
        if _sid and _ok:
            st.link_button(f"📊  Buka Google Sheets ({_ok} baris tersimpan)",
                f"https://docs.google.com/spreadsheets/d/{_sid}",use_container_width=True)
        if _err: notice("warn",f"{_err} file gagal.")
    _render_footer()


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["tab"] == "dashboard":
    import pandas as pd
    # Dashboard has its own secondary password (dashboard_password in secrets).
    if not _dashboard_login_wall():
        _render_footer(); st.stop()
    # ── Dashboard header row ──────────────────────────────────────────────────
    _dh1, _dh2 = st.columns([5,1])
    _dh1.markdown('<p style="font-size:18px;font-weight:700;color:#111827;margin:4px 0 14px;">Dashboard</p>',unsafe_allow_html=True)
    with _dh2:
        _da, _db = st.columns(2)
        with _da:
            if st.button("↻", type="secondary", use_container_width=True, key="dash_ref"):
                st.cache_resource.clear(); st.rerun()
        with _db:
            if st.button("⎋", type="secondary", use_container_width=True, key="_dash_logout_btn"):
                st.session_state["_dash_auth_ok"] = False
                st.session_state["_dash_login_err"] = ""
                st.rerun()
    try:
        with st.spinner("Memuat data..."): rows = load_rows()
        if not rows:
            notice("info","Belum ada transaksi.")
        else:
            df = pd.DataFrame(rows)
            if "Total (Rp)" in df.columns:
                df["Total (Rp)"] = pd.to_numeric(df["Total (Rp)"],errors="coerce").fillna(0)
            tn=len(df); tr=df["Total (Rp)"].sum() if "Total (Rp)" in df.columns else 0
            avg=tr/tn if tn else 0
            tds=datetime.now().strftime("%d/%m/%Y")
            tdc=int(df["Timestamp Input"].astype(str).str.startswith(tds).sum()) if "Timestamp Input" in df.columns else 0

            # ── Minimalist stat row ───────────────────────────────────────────
            st.markdown(f"""
<style>
.ds-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px}}
.ds-card{{background:#fff;border-radius:14px;padding:14px 12px;border:1px solid #f0f0f0}}
.ds-val{{font-size:18px;font-weight:700;color:#111827;line-height:1.1}}
.ds-lbl{{font-size:10px;color:#9ca3af;margin-top:3px;font-weight:500;letter-spacing:.3px;text-transform:uppercase}}
.ds-sep{{height:1px;background:#f3f4f6;margin:0 0 14px}}
@media(max-width:380px){{.ds-row{{grid-template-columns:repeat(2,1fr)}}}}
</style>
<div class="ds-row">
  <div class="ds-card"><div class="ds-val">{tn}</div><div class="ds-lbl">Transaksi</div></div>
  <div class="ds-card"><div class="ds-val" style="font-size:14px">{fmt(tr)}</div><div class="ds-lbl">Total</div></div>
  <div class="ds-card"><div class="ds-val" style="font-size:14px">{fmt(avg)}</div><div class="ds-lbl">Rata-rata</div></div>
  <div class="ds-card"><div class="ds-val">{tdc}</div><div class="ds-lbl">Hari ini</div></div>
</div>
""", unsafe_allow_html=True)

            # ── Kartu kredit breakdown ────────────────────────────────────────
            if "Kartu Kredit" in df.columns and "Total (Rp)" in df.columns:
                df["Kartu Kredit"] = df["Kartu Kredit"].astype(str).apply(normalize_card)
                _card_str=df["Kartu Kredit"].astype(str).str.strip().str.lower()
                _cc=df[_card_str.ne("") & _card_str.ne("nan") & _card_str.ne("none")]
                if not _cc.empty:
                    st.markdown('<p style="font-size:11px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:.5px;margin:0 0 8px;">Kartu Kredit</p>',unsafe_allow_html=True)
                    _grp=_cc.groupby("Kartu Kredit")["Total (Rp)"].sum().sort_values(ascending=False).reset_index()
                    _grp.columns=["label","val"]; _tot2=_grp["val"].sum(); _cnt=_cc.groupby("Kartu Kredit").size()
                    _h=""
                    for _,_row in _grp.iterrows():
                        _p=_row["val"]/_tot2*100 if _tot2 else 0
                        _a="Rp {:,.0f}".format(_row["val"]).replace(",",".")
                        _c=int(_cnt.get(_row["label"],0))
                        _h+=(f'<div style="display:flex;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid #f3f4f6;">'
                            +f'<span style="font-size:13px;font-weight:500;color:#111827;flex:1">{_row["label"]}</span>'
                            +f'<span style="font-size:11px;color:#6b7280;white-space:nowrap">{_c} trx</span>'
                            +f'<span style="font-size:13px;font-weight:600;color:#111827;white-space:nowrap">{_a}</span>'
                            +f'</div>')
                    st.markdown(f'<div style="background:#fff;border-radius:14px;border:1px solid #f0f0f0;overflow:hidden;margin-bottom:14px">{_h}</div>',unsafe_allow_html=True)

            # ── Data table ───────────────────────────────────────────────────
            st.markdown('<p style="font-size:11px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:.5px;margin:0 0 8px;">Data Transaksi</p>',unsafe_allow_html=True)
            _disp=df.iloc[::-1].reset_index(drop=True).copy()
            if "Booking ID" in _disp.columns: _disp["Booking ID"]=_disp["Booking ID"].astype(str)
            _cfg={}
            if "Booking ID" in _disp.columns: _cfg["Booking ID"]=st.column_config.TextColumn("Booking ID")
            if "Total (Rp)" in _disp.columns: _cfg["Total (Rp)"]=st.column_config.NumberColumn("Total (Rp)",format="Rp %d")
            if "Room x Night" in _disp.columns: _cfg["Room x Night"]=st.column_config.TextColumn("Room × Night")
            if "Room Nights" in _disp.columns: _cfg["Room Nights"]=st.column_config.NumberColumn("Room Nights",format="%d malam")
            if "Timestamp Input" in _disp.columns: _cfg["Timestamp Input"]=st.column_config.TextColumn("Timestamp")
            # Date columns: tampilkan as-is (string), jangan konversi agar data tidak hilang
            for _dcol in ["Booking Date","Issued Date","Check-in","Check-out"]:
                if _dcol in _disp.columns:
                    _disp[_dcol] = _disp[_dcol].astype(str).replace("nan","").replace("NaT","")
                    _cfg[_dcol] = st.column_config.TextColumn(_dcol)
            if "Room Nights" in _disp.columns:
                import pandas as pd
                _disp["Room Nights"] = pd.to_numeric(_disp["Room Nights"], errors="coerce").fillna(0).astype(int)
            st.dataframe(_disp,use_container_width=True,height=260,column_config=_cfg,hide_index=True)

            st.markdown('<div class="sec-lbl">Analisa dengan Claude</div>',unsafe_allow_html=True)

            def _build_data_context(df_ctx):
                _summary = {
                    "total_transaksi": len(df_ctx),
                    "total_pengeluaran_rp": int(df_ctx["Total (Rp)"].sum()) if "Total (Rp)" in df_ctx.columns else 0,
                    "rata_rata_rp": int(df_ctx["Total (Rp)"].mean()) if "Total (Rp)" in df_ctx.columns and len(df_ctx) > 0 else 0,
                }
                if "Hotel" in df_ctx.columns and "Total (Rp)" in df_ctx.columns:
                    _top_hotel = df_ctx.groupby("Hotel")["Total (Rp)"].sum().sort_values(ascending=False).head(5)
                    _summary["top_hotel"] = {k: int(v) for k, v in _top_hotel.items()}
                if "Issuer" in df_ctx.columns and "Total (Rp)" in df_ctx.columns:
                    _per_issuer = df_ctx.groupby("Issuer")["Total (Rp)"].sum().sort_values(ascending=False)
                    _summary["per_issuer"] = {k: int(v) for k, v in _per_issuer.items()}
                if "Kartu Kredit" in df_ctx.columns and "Total (Rp)" in df_ctx.columns:
                    _per_kartu = df_ctx[df_ctx["Kartu Kredit"].astype(str).str.strip().ne("")].groupby("Kartu Kredit")["Total (Rp)"].sum()
                    _summary["per_kartu_kredit"] = {k: int(v) for k, v in _per_kartu.items()}
                if "Supplier" in df_ctx.columns and "Total (Rp)" in df_ctx.columns:
                    _per_sup = df_ctx[df_ctx["Supplier"].astype(str).str.strip().ne("")].groupby("Supplier")["Total (Rp)"].sum().sort_values(ascending=False)
                    _summary["per_supplier"] = {k: int(v) for k, v in _per_sup.items()}
                if "Total (Rp)" in df_ctx.columns and "Hotel" in df_ctx.columns:
                    _cols5 = [c for c in ["Hotel","Guest Name","Total (Rp)","Check-in","Room Nights","Issuer"] if c in df_ctx.columns]
                    _top5 = df_ctx.nlargest(5, "Total (Rp)")[_cols5].fillna("").astype(str)
                    _summary["transaksi_terbesar"] = _top5.to_dict(orient="records")
                if "Room Nights" in df_ctx.columns:
                    import pandas as pd
                    _rn = pd.to_numeric(df_ctx["Room Nights"], errors="coerce").fillna(0)
                    _summary["total_room_nights"] = int(_rn.sum())
                    _summary["rata_rata_room_nights"] = round(float(_rn[_rn>0].mean()), 1) if (_rn>0).any() else 0
                if "Check-in" in df_ctx.columns:
                    import pandas as pd
                    _ci = pd.to_datetime(df_ctx["Check-in"], errors="coerce", dayfirst=True)
                    _by_month = df_ctx.assign(_m=_ci.dt.to_period("M"))
                    _by_month = _by_month.dropna(subset=["_m"])
                    if not _by_month.empty and "Total (Rp)" in df_ctx.columns:
                        _monthly = _by_month.groupby("_m")["Total (Rp)"].sum()
                        _summary["pengeluaran_per_bulan"] = {str(k): int(v) for k,v in _monthly.items()}
                return json.dumps(_summary, ensure_ascii=False, indent=2)

            _ctx_json = _build_data_context(df)

            if "dash_chat_history" not in st.session_state:
                st.session_state["dash_chat_history"] = []

            _chat_hist = st.session_state["dash_chat_history"]

            st.markdown("""
<style>
.chat-wrap{display:flex;flex-direction:column;gap:8px;margin-bottom:10px;max-height:340px;overflow-y:auto;padding:2px 0}
.chat-user{display:flex;justify-content:flex-end}
.chat-ai{display:flex;justify-content:flex-start}
.bubble-user{background:#191d3a;color:#fff;border-radius:16px 16px 4px 16px;
    padding:9px 13px;font-size:13px;max-width:82%;line-height:1.5;word-break:break-word}
.bubble-ai{background:#fff;border:1.5px solid #ddd;color:#191d3a;
    border-radius:16px 16px 16px 4px;padding:9px 13px;font-size:13px;
    max-width:90%;line-height:1.6;word-break:break-word}
.bubble-ai b{color:#191d3a}
.chat-avatar{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;
    justify-content:center;font-size:13px;flex-shrink:0;margin-top:2px}
.av-claude{background:#1a1020;border:1px solid #6b21a8}
.chat-empty{background:#f5f5f5;border-radius:12px;padding:14px 16px;
    font-size:12px;color:#9e9e9e;text-align:center;margin-bottom:10px}
.quick-btns{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
</style>
""", unsafe_allow_html=True)

            if not _chat_hist:
                st.markdown("""
<div class="chat-empty">
  🟣 Tanya Claude tentang data transaksi ini<br>
  <span style="font-size:11px;color:#bbb">Contoh: "Hotel mana yang paling banyak pengeluarannya?"</span>
</div>""", unsafe_allow_html=True)
            else:
                _bubbles_html = '<div class="chat-wrap">'
                for _msg in _chat_hist:
                    if _msg["role"] == "user":
                        _bubbles_html += f'<div class="chat-user"><div class="bubble-user">{_msg["content"]}</div></div>'
                    else:
                        _content_html = _msg["content"].replace("\n","<br>")
                        _bubbles_html += f'<div class="chat-ai"><div class="chat-avatar av-claude">🟣</div>&nbsp;<div class="bubble-ai">{_content_html}</div></div>'
                _bubbles_html += '</div>'
                st.markdown(_bubbles_html, unsafe_allow_html=True)

            _quick_qs = [
                "Ringkasan pengeluaran keseluruhan",
                "Hotel dengan biaya terbesar?",
                "Siapa issuer dengan transaksi terbanyak?",
                "Kartu kredit mana yang paling sering dipakai?",
                "Supplier mana yang dominan?",
                "Analisa tren pengeluaran",
            ]
            st.markdown('<div class="quick-btns">', unsafe_allow_html=True)
            _q_cols = st.columns(2)
            for _qi, _qq in enumerate(_quick_qs):
                with _q_cols[_qi % 2]:
                    if st.button(_qq, key=f"qbtn_{_qi}", use_container_width=True, type="secondary"):
                        st.session_state["_dash_pending_q"] = _qq
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

            _chat_input_col, _send_col = st.columns([5, 1])
            with _chat_input_col:
                _user_q = st.text_input("",
                    placeholder="Tanya sesuatu tentang data...",
                    label_visibility="collapsed",
                    key="dash_chat_input")
            with _send_col:
                _send_btn = st.button("➤", type="primary", use_container_width=True,
                    key="dash_send_btn")

            if _chat_hist:
                if st.button("Hapus riwayat chat", type="secondary",
                             use_container_width=True, key="dash_clear_chat"):
                    st.session_state["dash_chat_history"] = []
                    st.rerun()

            _pending = st.session_state.pop("_dash_pending_q", None)
            _final_q = _pending or (_user_q.strip() if _send_btn and _user_q.strip() else None)

            if _final_q:
                st.session_state["dash_chat_history"].append({"role":"user","content":_final_q})
                _sys_analyst = f"""Kamu adalah analis keuangan perjalanan bisnis untuk Mitra Tours & Travel.
Kamu diberikan data ringkasan transaksi kartu kredit hotel berikut dalam format JSON:

{_ctx_json}

Jawab pertanyaan user dalam Bahasa Indonesia dengan singkat, padat, dan mudah dipahami.
Gunakan format yang rapi — boleh pakai poin atau angka jika perlu.
Tampilkan angka Rupiah dengan format: Rp 1.500.000 (titik sebagai pemisah ribuan).
Jika data tidak cukup untuk menjawab, katakan dengan jelas."""

                with st.spinner("🟣 Claude sedang menganalisa…"):
                    try:
                        _claude_key = get_claude_key()
                        if not _claude_key:
                            raise ValueError("Claude API key belum dikonfigurasi di Settings.")
                        import anthropic as _anth
                        _anth_client = _anth.Anthropic(api_key=_claude_key)
                        _hist_msgs = [
                            {"role": m["role"], "content": m["content"]}
                            for m in st.session_state["dash_chat_history"][-10:]
                        ]
                        _resp_chat = _anth_client.messages.create(
                            model="claude-sonnet-4-5",
                            max_tokens=600,
                            system=_sys_analyst,
                            messages=_hist_msgs,
                        )
                        _answer = _resp_chat.content[0].text.strip()
                        st.session_state["dash_chat_history"].append({"role":"assistant","content":_answer})
                    except Exception as _chat_exc:
                        _err_msg = f"Gagal: {str(_chat_exc)[:120]}"
                        st.session_state["dash_chat_history"].append({"role":"assistant","content":_err_msg})
                st.rerun()
    except Exception as e:
        notice("err",str(e))
    _render_footer()

# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — RECENT ACTIVITY
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["tab"] == "log":
    try:
        with st.spinner("Memuat data..."): rows = load_rows()
        if not rows:
            notice("info","Belum ada data transaksi.")
        else:
            import pandas as pd
            df_log=pd.DataFrame(rows)
            def _pts(v):
                try: return pd.to_datetime(str(v),dayfirst=True)
                except: return pd.NaT
            df_log["_ts"]=df_log["Timestamp Input"].apply(_pts)
            df_log=df_log.sort_values("_ts",ascending=False).reset_index(drop=True)
            _total=len(df_log); _recent=df_log.head(10)
            st.markdown(f'<div style="display:flex;align-items:center;justify-content:space-between;margin:4px 0 10px;">'
                +f'<div class="sec-lbl" style="margin:0;border:none;padding:0;">Activity Log</div>'
                +f'<span style="font-size:10px;color:#9e9e9e;font-weight:500;">10 dari {_total}</span></div>',
                unsafe_allow_html=True)
            _items_html=""
            for _,_row in _recent.iterrows():
                _ts=str(_row.get("Timestamp Input","—")); _bid=str(_row.get("Booking ID","—"))
                _hotel=str(_row.get("Hotel","")) or "—"; _issuer=str(_row.get("Issuer","")) or "—"
                _total_r=_row.get("Total (Rp)",0)
                try: _amt="Rp {:,}".format(int(float(_total_r))).replace(",",".")
                except: _amt="—"
                _items_html+=f'''
<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;
    background:#fff;border-radius:12px;border:0.5px solid #e8e8e8;margin-bottom:6px;">
  <div style="width:36px;height:36px;border-radius:10px;background:#f5f5f5;
      display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px;">🏨</div>
  <div style="flex:1;min-width:0;">
    <div style="font-size:13px;font-weight:600;color:#191d3a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{_hotel}</div>
    <div style="font-size:10px;color:#9e9e9e;margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{_bid} · {_issuer}</div>
  </div>
  <div style="text-align:right;flex-shrink:0;">
    <div style="font-size:12px;font-weight:600;color:#191d3a;">{_amt}</div>
    <div style="font-size:9px;color:#bbb;margin-top:1px;">{_ts}</div>
  </div>
</div>'''
            st.markdown(_items_html,unsafe_allow_html=True)
    except Exception as e: notice("err",str(e))
    _render_footer()

# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["tab"] == "settings":
    _cur_prov=get_ai_provider(); _active_lbl="OpenAI" if _cur_prov=="openai" else "Claude"
    st.markdown('<div class="sec-lbl" style="margin-top:4px">AI Provider</div>',unsafe_allow_html=True)
    st.markdown('<div class="ai-card-btn-wrap">',unsafe_allow_html=True)
    if st.button(f"{'✦ ' if _cur_prov=='claude' else ''}Claude AI · claude-sonnet-4-5  ★ Default",
        key="sel_claude",use_container_width=True,type="primary" if _cur_prov=="claude" else "secondary"):
        st.session_state["ai_provider"]="claude"; st.rerun()
    if st.button(f"{'✦ ' if _cur_prov=='openai' else ''}OpenAI · gpt-4o-mini",
        key="sel_openai",use_container_width=True,type="primary" if _cur_prov=="openai" else "secondary"):
        st.session_state["ai_provider"]="openai"; st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="ai-status-bar"><div class="ai-status-dot"></div><span class="ai-status-txt">Active: {_active_lbl}</span></div>',unsafe_allow_html=True)
    st.markdown('<div class="sec-lbl" style="margin-top:14px">API Keys</div>',unsafe_allow_html=True)
    for _pname,_sskey,_section,_placeholder,_skey in [
        ("Claude AI","claude_key_manual","anthropic","sk-ant-api03-...","inp_cla_key"),
        ("OpenAI","openai_key_manual","openai","sk-proj-...","inp_oai_key")]:
        _secrets_ok=False
        try:
            k=st.secrets[_section]["api_key"]
            if k and len(k)>20 and "GANTI" not in k and "PASTE" not in k: _secrets_ok=True
        except: pass
        _ready=_secrets_ok or bool(st.session_state.get(_sskey,""))
        _dot_c="#1D9E75" if _ready else "#e68900"
        _lbl="ready" if _ready else "belum dikonfigurasi"
        _lcls="ai-key-ok" if _ready else "ai-key-warn"
        st.markdown(f'<div class="ai-key-row"><div class="ai-key-left"><div class="ai-key-dot" style="background:{_dot_c}"></div><span class="ai-key-name">{_pname}</span></div><span class="{_lcls}">{_lbl}</span></div>',unsafe_allow_html=True)
        if not _ready:
            _nk=st.text_input(_pname+" Key",value=st.session_state.get(_sskey,""),
                type="password",placeholder=_placeholder,label_visibility="collapsed",key=_skey)
            if _nk!=st.session_state.get(_sskey,""): st.session_state[_sskey]=_nk; st.rerun()
    st.markdown('<div class="sec-lbl">Session</div>',unsafe_allow_html=True)
    _render_logout_button()
    st.markdown('<div class="sec-lbl">Status Sistem</div>',unsafe_allow_html=True)
    sh_ok=False
    try:
        if st.secrets["google_sheets"]["sheet_id"] and st.secrets["gcp_service_account"]["client_email"]: sh_ok=True
    except: pass
    if sh_ok:
        st.markdown('<div class="st-row"><div class="st-icon si-g">📊</div><div class="st-body"><div class="st-title">Google Sheets</div><div class="st-sub">Terhubung</div></div><span class="st-badge bg">✓ Aktif</span></div>',unsafe_allow_html=True)
    else:
        st.markdown('<div class="st-row"><div class="st-icon si-y">📊</div><div class="st-body"><div class="st-title">Google Sheets</div><div class="st-sub">Belum dikonfigurasi</div></div><span class="st-badge by">⚠ Belum</span></div>',unsafe_allow_html=True)
        notice("warn","Isi <code>.streamlit/secrets.toml</code>")
        ns=st.text_input("Sheet ID",value=st.session_state.get("sheet_id",""),
            label_visibility="collapsed",placeholder="1nvgMCmo...")
        if ns!=st.session_state.get("sheet_id",""): st.session_state["sheet_id"]=ns
    if _PDF_OK:
        st.markdown('<div class="st-row"><div class="st-icon si-b">📄</div><div class="st-body"><div class="st-title">PDF Upload</div><div class="st-sub">pypdfium2 terinstall</div></div><span class="st-badge bg">✓ Aktif</span></div>',unsafe_allow_html=True)
    else:
        st.markdown('<div class="st-row"><div class="st-icon si-r">📄</div><div class="st-body"><div class="st-title">PDF Upload</div><div class="st-sub">pypdfium2 tidak terinstall</div></div><span class="st-badge br">✕ Nonaktif</span></div>',unsafe_allow_html=True)
        notice("err","Jalankan: <code>pip install pypdfium2==4.30.0</code>")
    st.markdown('<div class="sec-lbl">Tentang</div>',unsafe_allow_html=True)
    _active_model="gpt-4o-mini (OpenAI)" if get_ai_provider()=="openai" else "claude-sonnet-4-5 (Anthropic)"
    st.markdown(f"""
<div class="about-box">
  <div class="about-ttl">AI Intelligent Automation Scanner v6</div>
  <div class="about-r"><div class="about-k">Input</div>
    <div class="about-v">Expedia/TAAP: PDF·JPG·PNG bulk | Non-Expedia: JPG·PNG + manual</div></div>
  <div class="about-r"><div class="about-k">Output</div>
    <div class="about-v">Google Sheets — 17 kolom</div></div>
  <div class="about-r"><div class="about-k">Model AI</div>
    <div class="about-v">{_active_model} <b>(aktif)</b></div></div>
  <div class="about-r"><div class="about-k">Auth</div>
    <div class="about-v">App-level login · sesi {int(_ttl_hours())} jam · cookie persisten</div></div>
</div>""",unsafe_allow_html=True)
    _render_footer()
