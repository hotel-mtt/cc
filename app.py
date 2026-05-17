# =============================================================================
#  AI CC Reporting System  v6
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

st.set_page_config(page_title="Intelligent Automation Scanner", page_icon="💳",
    layout="centered", initial_sidebar_state="collapsed")

try:
    from streamlit_cookies_controller import CookieController
    _COOKIE_OK = True
except ImportError:
    _COOKIE_OK = False

_COOKIE_NAME = "cc_report_auth"

def _get_password():
    try:
        p = st.secrets["auth"]["password"]
        if p and "GANTI" not in p: return p
    except: pass
    return st.session_state.get("_auth_pw_override", "")

def _ttl_hours():
    try: return float(st.secrets["auth"].get("session_ttl_hours", 8))
    except: return 8.0

def _check_pw(candidate):
    correct = _get_password()
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

def require_login(): pass

def _render_logout_button():
    if st.button("Logout", type="secondary", use_container_width=True, key="_auth_logout_btn"):
        st.session_state["_auth_ok"] = False; st.session_state["_auth_login_time"] = 0
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
        display:flex;align-items:center;justify-content:center;font-size:12px;">💳</div>
    <div>
      <div style="font-size:12px;font-weight:600;color:#191d3a;">Intelligent Automation Scanner</div>
      <div style="font-size:10px;color:#aaa;">v6 · Mitra Tours &amp; Travel</div>
    </div>
  </div>
  <a href="https://www.linkedin.com/in/rifyalt" target="_blank"
     style="display:flex;align-items:center;gap:6px;text-decoration:none;
            font-size:11px;font-weight:500;color:#616161;
            border:0.5px solid #e0e0e0;padding:5px 12px;border-radius:20px;background:#fff;">
    Rifyal Tumber
  </a>
</div>""", unsafe_allow_html=True)

def _dashboard_login_wall():
    ctrl = _get_cookie_ctrl()
    if not st.session_state.get("_auth_ok") and ctrl:
        try:
            token = ctrl.get(_COOKIE_NAME)
            if token and _verify_token(token):
                st.session_state["_auth_ok"] = True
                st.session_state["_auth_login_time"] = time.time()
        except: pass
    if st.session_state.get("_auth_ok"):
        elapsed = time.time() - st.session_state.get("_auth_login_time", 0)
        if elapsed < _ttl_hours()*3600: return True
        st.session_state["_auth_ok"] = False
        if ctrl:
            try: ctrl.remove(_COOKIE_NAME)
            except: pass
    ttl = int(_ttl_hours()); _err = st.session_state.get("_dash_err","")
    st.markdown(f"""
<style>
.dash-lock-wrap{{display:flex;flex-direction:column;align-items:center;padding:60px 16px 8px;text-align:center}}
.dash-lock-icon{{width:48px;height:48px;border-radius:14px;background:#fff;border:1px solid #e4e4e4;
    display:flex;align-items:center;justify-content:center;margin-bottom:18px}}
.dash-lock-title{{font-size:16px;font-weight:600;color:#191d3a;margin-bottom:5px}}
.dash-lock-sub{{font-size:12px;color:#aaa;margin-bottom:32px}}
.dash-lock-err{{font-size:12px;color:#e53935;margin-bottom:8px;min-height:16px;text-align:center}}
.dash-lock-foot{{font-size:11px;color:#ccc;margin-top:14px;margin-bottom:4px;text-align:center}}
</style>
<div class="dash-lock-wrap">
  <div class="dash-lock-icon">🔒</div>
  <div class="dash-lock-title">Welcome</div>
  <div class="dash-lock-sub">Masukkan password untuk melanjutkan</div>
</div>
<div class="dash-lock-err">{_err}</div>""", unsafe_allow_html=True)
    _col_l, _col_c, _col_r = st.columns([1,2,1])
    with _col_c:
        pw = st.text_input("Password", type="password", placeholder="Password",
                           label_visibility="collapsed", key="_dash_pw_input")
        _btn = st.button("Login", type="primary", use_container_width=True, key="_dash_login_btn")
    if _btn:
        if _check_pw(pw):
            st.session_state["_auth_ok"] = True
            st.session_state["_auth_login_time"] = time.time()
            st.session_state["_dash_err"] = ""
            ctrl2 = _get_cookie_ctrl()
            if ctrl2:
                try: ctrl2.set(_COOKIE_NAME, _make_token(), max_age=int(_ttl_hours()*3600))
                except: pass
            st.rerun()
        else:
            st.session_state["_dash_err"] = "Password salah. Coba lagi."
            st.rerun()
    st.markdown(f'<div class="dash-lock-foot">Sesi aktif {ttl} jam · Tab lain bebas diakses</div>',
                unsafe_allow_html=True)
    return False


# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body,[data-testid="stAppViewContainer"],[data-testid="stAppViewBlockContainer"],.main{
    background:#ededed !important;font-family:'Inter',system-ui,sans-serif !important}
.main .block-container{padding:12px 12px 80px !important;max-width:600px !important;margin:0 auto !important}
[data-testid="stSidebar"],#MainMenu,footer,header,[data-testid="stDecoration"]{display:none !important}
*{font-family:'Inter',system-ui,sans-serif !important}
.app-header{background:#191d3a;border-radius:20px;padding:16px 18px;
    display:flex;align-items:center;gap:13px;margin-bottom:12px}
.ah-icon{width:46px;height:46px;border-radius:13px;background:#fddb32;
    display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0}
.ah-title{font-size:18px;font-weight:800;color:#fff;line-height:1.2}
.ah-sub{font-size:12px;color:#9e9e9e;margin-top:1px}
.ah-live{margin-left:auto;font-size:10px;font-weight:700;letter-spacing:.5px;
    background:#0f2310;color:#4ade80;border:1px solid #1e4620;
    padding:5px 11px;border-radius:20px;display:flex;align-items:center;gap:5px;white-space:nowrap;flex-shrink:0}
.ah-live::before{content:'';width:6px;height:6px;border-radius:50%;background:#4ade80;display:block}
.ah-ai-badge{font-size:10px;font-weight:700;letter-spacing:.4px;
    padding:4px 10px;border-radius:20px;white-space:nowrap;flex-shrink:0;margin-left:6px}
.ah-ai-openai{background:#0d1f12;color:#4ade80;border:1px solid #1e4620}
.ah-ai-claude{background:#1a1020;color:#c084fc;border:1px solid #6b21a8}
.nb-wrap div[data-testid="stHorizontalBlock"]{gap:8px !important}
.nb-wrap button{height:52px !important;border-radius:16px !important;
    border:1.5px solid #d8d8d8 !important;background:#fff !important;
    color:#616161 !important;font-size:11px !important;font-weight:600 !important;
    padding:0 4px !important;line-height:1.7 !important;box-shadow:none !important;width:100% !important}
.nb-wrap button:hover{border-color:#6398c8 !important;background:#e8f0fe !important;color:#191d3a !important}
.nb-wrap button[kind="primary"]{background:#191d3a !important;border-color:#191d3a !important;
    color:#fddb32 !important;box-shadow:0 3px 10px rgba(0,0,0,.22) !important}
.nb-wrap .stButton>button[kind="primary"]{background:#191d3a !important;color:#fddb32 !important;
    border-color:#191d3a !important;box-shadow:0 3px 10px rgba(0,0,0,.22) !important}
.nb-wrap .stButton>button[kind="primary"]:hover{background:#333 !important;border-color:#333 !important;color:#fddb32 !important}
.sec-lbl{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;
    color:#9e9e9e;margin:16px 0 10px;padding-bottom:8px;border-bottom:1.5px solid #ddd}
label[data-testid="stWidgetLabel"] p,label[data-testid="stWidgetLabel"]{
    font-size:12px !important;font-weight:600 !important;color:#191d3a !important;
    text-transform:none !important;letter-spacing:0 !important;margin-bottom:4px !important}
.stTextInput input,.stNumberInput input{border-radius:12px !important;border:1.5px solid #ddd !important;
    background:#fff !important;font-size:15px !important;color:#191d3a !important;
    padding:0 14px !important;height:48px !important;line-height:48px !important;
    box-sizing:border-box !important;width:100% !important}
.stTextInput input:focus,.stNumberInput input:focus{border-color:#6398c8 !important;
    background:#fff !important;box-shadow:0 0 0 3px rgba(99,152,200,.18) !important;outline:none !important}
[data-testid="stSelectbox"]>div>div{border-radius:12px !important;border:1.5px solid #ddd !important;
    background:#fff !important;font-size:15px !important;color:#191d3a !important;
    height:48px !important;min-height:48px !important;display:flex !important;align-items:center !important;box-sizing:border-box !important}
.stTextInput,.stSelectbox,[data-testid="stSelectbox"]{width:100% !important;min-width:0 !important}
div[data-testid="stWidgetLabel"]{overflow:visible !important}
[data-testid="stHorizontalBlock"]{gap:12px !important;align-items:flex-start !important;flex-wrap:nowrap !important;overflow:visible !important}
[data-testid="stHorizontalBlock"]>[data-testid="column"]{flex:1 1 0% !important;min-width:0 !important;max-width:none !important;overflow:visible !important;padding-bottom:4px !important}
[data-testid="stHorizontalBlock"]>[data-testid="column"]>div,[data-testid="stHorizontalBlock"]>[data-testid="column"] [data-testid="stVerticalBlock"]{overflow:visible !important;width:100% !important;min-width:0 !important}
.stButton>button{width:100% !important;border-radius:13px !important;height:50px !important;font-size:14px !important;font-weight:700 !important;border:none !important}
.stButton>button[kind="primary"]{background:#1668e3 !important;color:#ffffff !important;box-shadow:none !important}
.stButton>button[kind="primary"]:hover{background:#1255c0 !important;color:#ffffff !important;box-shadow:none !important}
.stButton>button[kind="secondary"]{background:#fff !important;border:1.5px solid #ddd !important;color:#616161 !important}
.stButton>button[kind="secondary"]:hover{border-color:#6398c8 !important;background:#e8f0fe !important;color:#191d3a !important}
.bb-wrap .stButton>button{height:48px !important;border-radius:13px !important;font-size:14px !important;font-weight:600 !important;width:100% !important}
.bb-wrap .stButton>button[kind="primary"]{background:#1668e3 !important;color:#ffffff !important;border:none !important;box-shadow:none !important}
.bb-wrap .stButton>button[kind="primary"]:hover{background:#1255c0 !important}
.bb-wrap .stButton>button[kind="secondary"]{background:transparent !important;border:none !important;color:#9e9e9e !important;font-size:12px !important;font-weight:400 !important;height:32px !important;text-decoration:underline !important;text-underline-offset:3px !important}
.bb-wrap .stButton>button[kind="secondary"]:hover{color:#e53935 !important;background:transparent !important;border:none !important}
[data-testid="stLinkButton"] a{background:#6398c8 !important;color:#fff !important;border-radius:13px !important;height:52px !important;font-size:14px !important;font-weight:700 !important;border:none !important;display:flex !important;align-items:center !important;justify-content:center !important;text-decoration:none !important}
[data-testid="stCheckbox"] label{font-size:14px !important;color:#616161 !important;font-weight:500 !important}
.mode-toggle{display:grid;grid-template-columns:1fr 1fr;gap:0;
    background:#e8e8e8;border-radius:14px;padding:4px;margin-bottom:14px}
.mode-toggle .stButton>button{height:40px !important;border-radius:10px !important;
    font-size:12px !important;font-weight:600 !important;border:none !important;
    box-shadow:none !important;background:transparent !important;color:#9e9e9e !important}
.mode-toggle .stButton>button[kind="primary"]{background:#fff !important;color:#191d3a !important;
    box-shadow:0 1px 4px rgba(0,0,0,.12) !important}
.mode-toggle .stButton>button[kind="primary"]:hover{background:#fff !important;color:#191d3a !important}
.mode-toggle .stButton>button[kind="secondary"]:hover{background:rgba(255,255,255,.5) !important;color:#191d3a !important;border:none !important}
.ai-card-btn-wrap .stButton>button{height:52px !important;border-radius:14px !important;font-size:13px !important;font-weight:500 !important;text-align:left !important;padding:0 16px !important;letter-spacing:0 !important;margin-bottom:8px !important}
.ai-card-btn-wrap .stButton>button[kind="secondary"]{background:#fff !important;border:0.5px solid #e0e0e0 !important;color:#191d3a !important;box-shadow:none !important}
.ai-card-btn-wrap .stButton>button[kind="secondary"]:hover{border-color:#9e9e9e !important;background:#f9f9f9 !important}
.ai-card-btn-wrap .stButton>button[kind="primary"]{background:#f0fdf4 !important;border:1.5px solid #1D9E75 !important;color:#191d3a !important;box-shadow:none !important}
.ai-status-bar{display:flex;align-items:center;gap:8px;padding:9px 13px;border-radius:10px;background:#f0fdf4;border:1px solid #bbf7d0;margin-bottom:18px}
.ai-status-dot{width:6px;height:6px;border-radius:50%;background:#1D9E75;flex-shrink:0}
.ai-status-txt{font-size:12px;color:#166534}
.ai-key-row{display:flex;align-items:center;justify-content:space-between;padding:9px 13px;border-radius:10px;background:#fff;border:1px solid #e8e8e8;margin-bottom:6px}
.ai-key-left{display:flex;align-items:center;gap:9px}
.ai-key-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.ai-key-name{font-size:13px;color:#191d3a}
.ai-key-ok{font-size:11px;color:#1D9E75}
.ai-key-warn{font-size:11px;color:#e68900}
.notice{border-radius:12px;padding:11px 14px;font-size:13px;line-height:1.5;display:flex;align-items:flex-start;gap:8px;margin-bottom:12px}
.nok{background:#f0fdf4;border:1px solid #86efac;color:#166534}
.nerr{background:#fff1f2;border:1px solid #fecdd3;color:#9f1239}
.ninfo{background:#e8f0fe;border:1px solid #6398c8;color:#1e3a6e}
.nwarn{background:#fffbeb;border:1px solid #fde68a;color:#92400e}
.nviolet{background:#faf5ff;border:1px solid #d8b4fe;color:#6b21a8}
.expedia-banner{background:#fff;border:1.5px solid #ddd;border-bottom:none;border-radius:16px 16px 0 0;padding:13px 16px;display:flex;align-items:center;justify-content:space-between;margin-top:16px}
.expedia-banner img{height:24px;width:auto;object-fit:contain}
.taap-pill{font-size:11px;font-weight:700;letter-spacing:.3px;color:#1e3a6e;background:#e8f0fe;border:1px solid #6398c8;padding:4px 11px;border-radius:20px;white-space:nowrap}
[data-testid="stFileUploader"] [data-testid="stWidgetLabel"],[data-testid="stFileUploader"] [data-testid="stWidgetLabel"] *{display:none !important}
[data-testid="stFileUploaderDropzoneInput"] + label,[data-testid="stFileUploader"] > section > label,[data-testid="stFileUploader"] label[for]{display:none !important;visibility:hidden !important;height:0 !important;overflow:hidden !important}
[data-testid="stFileUploader"]{margin-top:0 !important}
[data-testid="stFileUploader"]>div:first-child,[data-testid="stFileUploader"] section{border:1.5px dashed #b8cde0 !important;border-top:none !important;border-radius:0 0 16px 16px !important;background:#f5f8fc !important;margin-top:0 !important;padding:28px 20px !important;min-height:120px !important}
[data-testid="stFileUploader"]>div:first-child:hover,[data-testid="stFileUploader"] section:hover{border-color:#6398c8 !important;background:#e8f0fe !important}
[data-testid="stFileUploader"] button{border-radius:10px !important;border:1.5px solid #ddd !important;background:#fff !important;color:#191d3a !important;font-size:13px !important;font-weight:600 !important;padding:8px 18px !important;height:auto !important}
[data-testid="stFileUploaderDropInstructions"]{font-size:14px !important;font-weight:600 !important;color:#191d3a !important}
[data-testid="stFileUploaderDropInstructions"] small,[data-testid="stFileUploaderDropInstructions"] span{font-size:12px !important;color:#9e9e9e !important;font-weight:400 !important}
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px}
.stat-card{background:#fff;border:1.5px solid #ddd;border-radius:18px;padding:16px 15px}
.stat-val{font-size:22px;font-weight:800;color:#191d3a;line-height:1.1}
.stat-lbl{font-size:11px;color:#9e9e9e;margin-top:5px;font-weight:500}
.bulk-prog{background:#ddd;border-radius:99px;height:5px;overflow:hidden;margin-bottom:6px}
.bulk-prog-f{height:100%;background:#6398c8;border-radius:99px;transition:width .3s}
.bulk-prog-lbl{font-size:12px;color:#9e9e9e;text-align:center;margin-bottom:14px;font-weight:500}
.bulk-sum{background:#fff;border:1.5px solid #ddd;border-radius:18px;padding:18px 16px;margin-bottom:16px}
.bulk-sum-ttl{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:#9e9e9e;margin-bottom:14px}
.bulk-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;text-align:center;margin-bottom:14px}
.bs-val{font-size:24px;font-weight:800;color:#191d3a;line-height:1}
.bs-lbl{font-size:10px;color:#9e9e9e;margin-top:4px;font-weight:500}
.bs-g{color:#1e9e5a}.bs-r{color:#e53935}.bs-y{color:#e68900}
.bulk-bar{background:#e8e8e8;border-radius:99px;height:5px;overflow:hidden}
.bulk-bar-f{height:100%;background:#1e9e5a;border-radius:99px}
.bulk-pct{font-size:11px;color:#9e9e9e;text-align:right;margin-top:5px}
.file-item{background:#fff;border:1.5px solid #ddd;border-radius:15px;padding:13px 15px;margin-bottom:8px}
.fi-success{border-color:#6ee7b7 !important;background:#f0fdf4 !important}
.fi-error{border-color:#fca5a5 !important;background:#fff1f2 !important}
.fi-skipped{border-color:#fcd34d !important;background:#fffde7 !important}
.fi-top{display:flex;align-items:center;gap:10px}
.fi-icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0}
.ic-ok{background:#dcfce7}.ic-err{background:#ffe4e6}.ic-skip{background:#fef9c3}.ic-n{background:#ededed}
.fi-name{font-size:13px;font-weight:600;color:#191d3a;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fi-badge{font-size:10px;font-weight:700;padding:4px 10px;border-radius:20px;white-space:nowrap}
.fb-ok{background:#dcfce7;color:#166534}.fb-err{background:#ffe4e6;color:#9f1239}.fb-sk{background:#fef9c3;color:#7a5c00}
.fi-grid{margin-top:10px;padding-top:9px;border-top:1.5px solid #ededed;display:grid;grid-template-columns:1fr 1fr;gap:6px 14px}
.fi-kv{display:flex;gap:5px;align-items:baseline}
.fi-k{font-size:10px;font-weight:700;color:#9e9e9e;min-width:52px;flex-shrink:0;text-transform:uppercase;letter-spacing:.3px}
.fi-v{font-size:12px;font-weight:500;color:#191d3a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.st-row{display:flex;align-items:center;gap:12px;background:#fff;border:1.5px solid #ddd;border-radius:15px;padding:14px 15px;margin-bottom:10px}
.st-icon{width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.si-g{background:#f0fdf4}.si-r{background:#fff1f2}.si-b{background:#e8f0fe}.si-y{background:#fffde7}
.st-body{flex:1;min-width:0}
.st-title{font-size:14px;font-weight:700;color:#191d3a;line-height:1}
.st-sub{font-size:12px;color:#9e9e9e;margin-top:3px}
.st-badge{display:inline-flex;align-items:center;font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;flex-shrink:0}
.bg{background:#f0fdf4;color:#166534;border:1px solid #86efac}
.br{background:#fff1f2;color:#9f1239;border:1px solid #fecdd3}
.by{background:#fffde7;color:#7a5c00;border:1px solid #fcd34d}
.about-box{background:#fff;border:1.5px solid #ddd;border-radius:18px;padding:16px 18px}
.about-ttl{font-size:15px;font-weight:800;color:#191d3a;margin-bottom:13px}
.about-r{display:flex;gap:10px;margin-bottom:7px}
.about-k{font-size:12px;font-weight:700;color:#191d3a;width:70px;flex-shrink:0}
.about-v{font-size:12px;color:#616161;line-height:1.5}
[data-testid="stDataFrame"]{border-radius:15px !important;border:1.5px solid #ddd !important;overflow:hidden !important;box-shadow:none !important}
[data-testid="stDataFrame"] th{background:#f5f8fc !important;color:#616161 !important;font-size:11px !important;font-weight:700 !important;text-transform:uppercase !important;letter-spacing:.5px !important;border-bottom:1.5px solid #ddd !important;padding:11px 13px !important}
[data-testid="stDataFrame"] td{font-size:13px !important;color:#191d3a !important;padding:10px 13px !important;border-bottom:1px solid #ededed !important}
[data-testid="stDataFrame"] tr:hover td{background:#f5f8fc !important}
[data-testid="stMetric"]{background:#fff !important;border:1.5px solid #ddd !important;border-radius:15px !important;padding:14px !important;margin-bottom:0 !important}
[data-testid="stMetricLabel"]{font-size:11px !important;font-weight:700 !important;color:#9e9e9e !important;text-transform:uppercase !important;letter-spacing:.6px !important}
[data-testid="stMetricValue"]{font-size:15px !important;font-weight:800 !important;color:#191d3a !important}
.stSpinner>div{border-top-color:#6398c8 !important}
@media(max-width:480px){
    .main .block-container{padding:8px 8px 80px !important}
    .app-header{border-radius:16px;padding:12px 14px}
    .nb-wrap button{height:52px !important;font-size:11px !important}
    .bs-val{font-size:20px}.stat-val{font-size:18px}}
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

def active_ai_label():
    return "OpenAI" if get_ai_provider() == "openai" else "Claude"

# ─── Google Sheets ────────────────────────────────────────────────────────────
def sheet_id():
    try:
        s = st.secrets["google_sheets"]["sheet_id"]
        if s and "GANTI" not in s: return s
    except: pass
    return st.session_state.get("sheet_id", "")

COLS = ["Timestamp Input","Supplier","Booking ID","Booking Date","Issued Date",
        "Hotel","Check-in","Room x Night","Total (Rp)","Check-out","Guest Name",
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
        "checkin","qty","room","checkout","name","card","issuer","pic",
        "no_bc","nama_kegiatan","notes"]], value_input_option="USER_ENTERED")

def load_rows(): return ws().get_all_records()

# ─── Duplicate check ──────────────────────────────────────────────────────────
def _ns(v): return str(v or "").strip().lower()
def _ni(v):
    try: return int(float(str(v).replace(",","").replace(".","") or 0))
    except: return 0

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

# ─── AI System Prompts ────────────────────────────────────────────────────────
_SYS = """You are a corporate hotel expense AI parser for credit card reporting.
Parse any document: Expedia TAAP receipt, Mitra Tours itinerary, hotel invoice.
Return ONLY a valid JSON object — no markdown, no explanation.
Keys: supplier, booking_id, booked_on (YYYY-MM-DD), issued_on (YYYY-MM-DD),
hotel, checkin (YYYY-MM-DD), checkout (YYYY-MM-DD), qty (e.g. "1 room x 2 nights"),
room (integer total IDR, strip Rp/commas), name (primary guest),
card (e.g. "Visa •••• 0191"), notes (room type, tax, etc.)
Rules: 1.Dates->YYYY-MM-DD. 2.Amounts->plain integer. 3.Missing->"" or 0."""

_SYS_NONEXP = """You are a payment receipt parser. Extract ONLY these 4 fields from the payment receipt image.
Return ONLY a valid JSON object — no markdown, no explanation.
Keys:
- timestamp_input : string — Date/Time exactly as shown on receipt (e.g. "15/05/2026 16:18:34")
- booking_id      : string — Invoice Number / Reference Number / Transaction ID from the receipt
- room            : integer — Amount charged, strip IDR/Rp/,/. -> plain integer only
- card            : string — Card Number as shown (e.g. "521558******4467")
Missing field -> "" for strings, 0 for integers."""

# ─── AI Parsers ───────────────────────────────────────────────────────────────
def _call_openai(content, sys_prompt, max_tokens=800):
    import openai, httpx
    key = get_openai_key()
    if not key: raise ValueError("OpenAI API key belum diisi — buka tab Pengaturan.")
    _client = httpx.Client()
    resp = openai.OpenAI(api_key=key, http_client=_client).chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":sys_prompt},{"role":"user","content":content}],
        temperature=0.0, max_tokens=max_tokens)
    raw = resp.choices[0].message.content
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m: raise ValueError("Format AI tidak valid — JSON tidak ditemukan.")
    return json.loads(m.group()), raw

def _call_claude(content, sys_prompt, max_tokens=800):
    import anthropic
    key = get_claude_key()
    if not key: raise ValueError("Anthropic API key belum diisi — buka tab Pengaturan.")
    client = anthropic.Anthropic(api_key=key)
    resp = client.messages.create(model="claude-sonnet-4-5", max_tokens=max_tokens,
        system=sys_prompt, messages=[{"role":"user","content":content}])
    raw = resp.content[0].text
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m: raise ValueError("Format AI tidak valid — JSON tidak ditemukan.")
    return json.loads(m.group()), raw

def _build_content_expedia(text, images):
    if get_ai_provider() == "claude":
        content = []
        if images:
            for b64,mime in images:
                content.append({"type":"image","source":{"type":"base64","media_type":mime,"data":b64}})
        content.append({"type":"text","text":text if text else "Extract all structured data."})
        return content
    else:
        content = []
        if images:
            for b64,mime in images:
                content.append({"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}","detail":"high"}})
        content.append({"type":"text","text":text if text else "Extract all structured data."})
        return content

def _build_content_receipt(images):
    if get_ai_provider() == "claude":
        content = []
        for b64,mime in images:
            content.append({"type":"image","source":{"type":"base64","media_type":mime,"data":b64}})
        content.append({"type":"text","text":"Extract the 4 fields from this payment receipt."})
        return content
    else:
        content = []
        for b64,mime in images:
            content.append({"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}","detail":"high"}})
        content.append({"type":"text","text":"Extract the 4 fields from this payment receipt."})
        return content

def ai_parse(text="", images=None):
    content = _build_content_expedia(text, images)
    if get_ai_provider() == "claude": return _call_claude(content, _SYS)
    return _call_openai(content, _SYS)

def ai_parse_receipt(images):
    content = _build_content_receipt(images)
    if get_ai_provider() == "claude": return _call_claude(content, _SYS_NONEXP, max_tokens=400)
    return _call_openai(content, _SYS_NONEXP, max_tokens=400)

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

# ─── Card number normalizer ───────────────────────────────────────────────────
# Mapping BIN 6-digit → brand display canonical
_BIN_MAP = {
    "521558": ("MasterCard", "4467"),
    "489594": ("Visa",       "0191"),
}
# Reverse: lowercase display label → canonical
_DISPLAY_MAP = {
    "mastercard •••• 4467": "MasterCard \u2022\u2022\u2022\u2022 4467",
    "visa \u2022\u2022\u2022\u2022 0191":       "Visa \u2022\u2022\u2022\u2022 0191",
}

def normalize_card(raw: str) -> str:
    """
    Normalisasi nomor kartu ke format display canonical.
    521558******4467  -> MasterCard \u2022\u2022\u2022\u2022 4467
    521558 ****** 4467-> MasterCard \u2022\u2022\u2022\u2022 4467
    MasterCard \u2022\u2022\u2022\u2022 4467 -> MasterCard \u2022\u2022\u2022\u2022 4467
    489594******0191  -> Visa \u2022\u2022\u2022\u2022 0191
    Visa \u2022\u2022\u2022\u2022 0191 -> Visa \u2022\u2022\u2022\u2022 0191
    "" -> ""
    """
    if not raw:
        return ""
    v = str(raw).strip()
    # Already in display format? (case-insensitive)
    _lower = re.sub(r"\s+", " ", v.lower())
    if _lower in _DISPLAY_MAP:
        return _DISPLAY_MAP[_lower]
    # Extract digits only and check BIN
    digits = re.sub(r"[^\d]", "", v)
    if len(digits) >= 6:
        bin6 = digits[:6]
        if bin6 in _BIN_MAP:
            brand, last4 = _BIN_MAP[bin6]
            return f"{brand} \u2022\u2022\u2022\u2022 {last4}"
    return v


# ─── Session state ────────────────────────────────────────────────────────────
_DEF = {
    "tab":                  "input",
    "input_mode":           "expedia",
    "bulk_results":         [],
    "bulk_saved_count":     0,
    "openai_key_manual":    "",
    "claude_key_manual":    "",
    "ai_provider":          "claude",      # Claude = default utama
    "sheet_id":             "1nvgMCmo1EJtbCAt0db_OizvPYDvaEzphKhwzBJ-3X_g",
    "last_issuer":          "",
    "last_pic":             "",
    "last_no_bc":           "",
    "last_nama_kegiatan":   "",
    # Non-Expedia pre-parse state
    "_ne_last_file_key":    "",            # nama+size file yang sudah di-pre-parse
    "_ne_prefill_ts":       "",            # hasil pre-parse: timestamp_input
    "_ne_prefill_bid":      "",            # hasil pre-parse: booking_id (invoice)
    "_ne_prefill_room":     "",            # hasil pre-parse: room (amount)
    "_ne_prefill_card":     "",            # hasil pre-parse: card
    "_ne_parse_ok":         False,
    "_ne_parse_err":        "",
}
for _k,_v in _DEF.items():
    if _k not in st.session_state: st.session_state[_k] = _v

# ─── Header ───────────────────────────────────────────────────────────────────
_prov = get_ai_provider()
_prov_lbl = "GPT-4o mini" if _prov == "openai" else "Claude Sonnet"
_prov_cls = "ah-ai-openai" if _prov == "openai" else "ah-ai-claude"
_prov_ico = "🤖" if _prov == "openai" else "🟣"

st.markdown(f"""
<div class="app-header">
  <div class="ah-icon">💳</div>
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
st.markdown('<div class="nb-wrap">', unsafe_allow_html=True)
_na,_nb,_nc,_nd = st.columns(4)
with _na:
    if st.button("Input",key="nb_input",use_container_width=True,
                 type="primary" if _cur=="input" else "secondary"):
        st.session_state["tab"]="input"; st.rerun()
with _nb:
    if st.button("Dashboard",key="nb_dash",use_container_width=True,
                 type="primary" if _cur=="dashboard" else "secondary"):
        st.session_state["tab"]="dashboard"; st.rerun()
with _nc:
    if st.button("Recent Activity",key="nb_log",use_container_width=True,
                 type="primary" if _cur=="log" else "secondary"):
        st.session_state["tab"]="log"; st.rerun()
with _nd:
    if st.button("Settings",key="nb_set",use_container_width=True,
                 type="primary" if _cur=="settings" else "secondary"):
        st.session_state["tab"]="settings"; st.rerun()
st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — INPUT
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state["tab"] == "input":

    if not active_ai_ready():
        _pv = get_ai_provider(); _nm = "OpenAI" if _pv=="openai" else "Anthropic"
        notice("err", f"{_nm} API key belum diisi — buka tab <b>Pengaturan</b>."); st.stop()
    if not _PDF_OK:
        notice("warn","pypdfium2 belum terinstall — PDF nonaktif. Jalankan: <code>pip install pypdfium2==4.30.0</code>")

    # ── Mode toggle ───────────────────────────────────────────────────────────
    _cur_mode = st.session_state["input_mode"]
    st.markdown('<div class="mode-toggle">', unsafe_allow_html=True)
    _ma,_mb = st.columns(2)
    with _ma:
        if st.button("✈  Expedia / TAAP", key="mode_expedia", use_container_width=True,
                     type="primary" if _cur_mode=="expedia" else "secondary"):
            st.session_state["input_mode"]="expedia"
            st.session_state["bulk_results"]=[]
            st.rerun()
    with _mb:
        if st.button("🧾  Non-Expedia", key="mode_nonexp", use_container_width=True,
                     type="primary" if _cur_mode=="nonexpedia" else "secondary"):
            st.session_state["input_mode"]="nonexpedia"
            st.session_state["bulk_results"]=[]
            # Reset pre-parse state
            for _k in ["_ne_last_file_key","_ne_prefill_ts","_ne_prefill_bid",
                        "_ne_prefill_room","_ne_prefill_card","_ne_parse_ok","_ne_parse_err"]:
                st.session_state[_k] = _DEF.get(_k,"")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Issuer & PIC (shared) ─────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl">Issuer &amp; PIC</div>', unsafe_allow_html=True)
    _ISSUERS = ["","Ade Puspitasari","Farras Mahmud","Meijika",
        "Muhammad Geraldi Jagaddhita","Nur Anissa Firda Aulia","Riega Wisudhantara",
        "Rifyal Tumber","Selvy Anggraini","Shaiful Baldy","Veronica Novi Heri","Rida Manora Nasution"]
    _li = st.session_state.get("last_issuer","")
    _bi = _ISSUERS.index(_li) if _li in _ISSUERS else 0
    _ca,_cb = st.columns(2)
    bulk_issuer = _ca.selectbox("Issuer *",options=_ISSUERS,index=_bi,
        format_func=lambda x:"— Pilih Issuer —" if x=="" else x, key="bulk_issuer")
    bulk_pic = _cb.text_input("PIC *",value=st.session_state.get("last_pic",""),
        placeholder="Nama penanggung jawab",key="bulk_pic")
    _cc,_cd = st.columns(2)
    bulk_no_bc = _cc.text_input("No. BC",value=st.session_state.get("last_no_bc",""),
        placeholder="Nomor BC (opsional)",key="bulk_no_bc")
    bulk_nama_kegiatan = _cd.text_input("Nama Kegiatan",value=st.session_state.get("last_nama_kegiatan",""),
        placeholder="Nama kegiatan (opsional)",key="bulk_nama_kegiatan")

    _ap = get_ai_provider()
    if _ap=="claude": notice("violet","AI aktif: <b>Claude</b> (Anthropic) &nbsp;·&nbsp; Ganti di tab <b>Pengaturan</b>")
    else: notice("info","AI aktif: <b>OpenAI</b> &nbsp;·&nbsp; Ganti di tab <b>Pengaturan</b>")

    # ══════════════════════════════════════════════════════════════════════════
    #  MODE A — EXPEDIA / TAAP
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
        skip_dup = st.checkbox("Lewati duplikat — jangan simpan jika booking sudah ada",
            value=True,key="bulk_skip_dup")
        st.markdown("<div style='height:8px'></div>",unsafe_allow_html=True)
        st.markdown('<div class="bb-wrap">',unsafe_allow_html=True)
        _run = st.button("Submit",type="primary",use_container_width=True,
            disabled=(not _n or not bulk_issuer or not bulk_pic.strip()),key="bulk_run")
        _clear = st.button("Delete",type="secondary",use_container_width=True,key="bulk_clear")
        st.markdown('</div>',unsafe_allow_html=True)

        if _clear:
            st.session_state["bulk_results"]=[]; st.session_state["bulk_saved_count"]=0; st.rerun()

        if _run:
            if not bulk_issuer: notice("err","Pilih Issuer terlebih dahulu.")
            elif not bulk_pic.strip(): notice("err","Isi PIC terlebih dahulu.")
            else:
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
                        '<div class="bulk-prog-lbl">Memproses '+str(_idx+1)+' / '+str(_n)+' &nbsp;·&nbsp; '+_uf.name+'</div>',
                        unsafe_allow_html=True)
                    _res = {"file":_uf.name,"status":"error","parsed":{},"err":"","mode":"expedia"}
                    try:
                        _raw = _uf.read(); _imgs,_txt = [],""
                        if _uf.name.lower().endswith(".pdf"):
                            if not _PDF_OK: raise RuntimeError("pypdfium2 tidak terinstall")
                            _pages = pdf_images(_raw); _imgs = [to_b64(pg) for pg in _pages]
                            _txt = pdf_text(_raw)
                        else:
                            _io = Image.open(io.BytesIO(_raw)).convert("RGB")
                            _b,_m = to_b64(_io); _imgs = [(_b,_m)]
                        _comb = ("EXTRACTED PDF TEXT (authoritative):\n"+_txt) if _txt else ""
                        _parsed,_ = ai_parse(_comb,_imgs or None)
                        _parsed["timestamp_input"] = now_ts()
                        _is_dup,_why,_ = check_duplicate({"booking_id":_parsed.get("booking_id"),
                            "hotel":_parsed.get("hotel"),"checkin":_parsed.get("checkin"),
                            "name":_parsed.get("name"),"room":_parsed.get("room")},_existing)
                        if _is_dup and skip_dup:
                            _res.update(status="skipped",parsed=_parsed,err=_why)
                        else:
                            save_row({"timestamp_input":_parsed.get("timestamp_input",""),
                                "supplier":_parsed.get("supplier",""),"booking_id":_parsed.get("booking_id",""),
                                "booked_on":_parsed.get("booked_on",""),"issued_on":_parsed.get("issued_on",""),
                                "hotel":_parsed.get("hotel",""),"checkin":_parsed.get("checkin",""),
                                "qty":_parsed.get("qty",""),"room":_parsed.get("room",0),
                                "checkout":_parsed.get("checkout",""),"name":_parsed.get("name",""),
                                "card":normalize_card(_parsed.get("card","")),"issuer":bulk_issuer,"pic":bulk_pic,
                                "no_bc":bulk_no_bc.strip() or _parsed.get("no_bc",""),
                                "nama_kegiatan":bulk_nama_kegiatan.strip() or _parsed.get("nama_kegiatan",""),
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
    #  MODE B — NON-EXPEDIA (Payment Receipt)
    # ══════════════════════════════════════════════════════════════════════════
    else:
        st.markdown("""
<div style="background:#fff;border:1.5px solid #ddd;border-bottom:none;
    border-radius:16px 16px 0 0;padding:13px 16px;
    display:flex;align-items:center;justify-content:space-between;margin-top:16px">
  <div style="display:flex;align-items:center;gap:9px">
    <span style="font-size:20px">🧾</span>
    <div>
      <div style="font-size:13px;font-weight:700;color:#191d3a">Non-Expedia — Payment Receipt</div>
      <div style="font-size:11px;color:#9e9e9e">Upload struk pembayaran · 4 field dibaca AI · sisanya isian manual</div>
    </div>
  </div>
  <span style="font-size:10px;font-weight:700;color:#7a5c00;background:#fef9c3;
    border:1px solid #fcd34d;padding:4px 11px;border-radius:20px">Manual + AI</span>
</div>""", unsafe_allow_html=True)

        ne_files = st.file_uploader(label="",type=["jpg","jpeg","png","webp"],
            accept_multiple_files=False,label_visibility="collapsed",key="ne_uf")

        # ── PRE-PARSE: jalankan AI segera saat file baru diupload ─────────────
        if ne_files:
            _cur_file_key = ne_files.name + str(ne_files.size)
            if _cur_file_key != st.session_state.get("_ne_last_file_key",""):
                # File baru — parse langsung
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

            # Tampilkan status pre-parse
            if st.session_state.get("_ne_parse_ok"):
                notice("ok",
                    "✓ AI berhasil membaca receipt &nbsp;·&nbsp; "
                    "<b>Timestamp · Invoice · Amount · Card</b> terisi otomatis di bawah")
            elif st.session_state.get("_ne_parse_err"):
                notice("warn",
                    f"AI gagal membaca: {st.session_state['_ne_parse_err']} "
                    "— isi field secara manual.")
        else:
            # File dihapus — reset prefill
            if st.session_state.get("_ne_last_file_key",""):
                for _k in ["_ne_last_file_key","_ne_prefill_ts","_ne_prefill_bid",
                            "_ne_prefill_room","_ne_prefill_card","_ne_parse_ok","_ne_parse_err"]:
                    st.session_state[_k] = _DEF.get(_k,"")

        # Panduan mapping field
        st.markdown("""
<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:12px;
    padding:10px 14px;font-size:12px;color:#166534;margin:10px 0 4px;line-height:1.9">
  <b>✓ Diisi otomatis dari gambar (AI):</b><br>
  <span style="display:inline-flex;gap:16px;flex-wrap:wrap;">
    <span>📅 <b>Timestamp Input</b> &larr; Date/Time</span>
    <span>💰 <b>Total (Rp)</b> &larr; Amount</span>
    <span>💳 <b>Kartu Kredit</b> &larr; Card Number</span>
    <span>📄 <b>Booking ID</b> &larr; Invoice Number</span>
  </span>
</div>""", unsafe_allow_html=True)

        st.markdown('<div class="sec-lbl">Data Booking — Isian Manual</div>',unsafe_allow_html=True)
        notice("warn","Field berikut <b>tidak tersedia di receipt</b> — harap isi secara manual.")

        # ── Field 1: Supplier (DROPDOWN) & Hotel ─────────────────────────────
        _SUPPLIERS = ["Direct To Hotel", "Direct To Supplier"]
        _n1,_n2 = st.columns(2)
        ne_supplier = _n1.selectbox(
            "Supplier *",
            options=_SUPPLIERS,
            index=0,
            key="ne_supplier"
        )
        ne_hotel = _n2.text_input("Hotel *",placeholder="Nama hotel lengkap",key="ne_hotel")

        # ── Field 2: Guest Name & Booking ID (prefilled dari AI) ──────────────
        _n3,_n4 = st.columns(2)
        ne_name = _n3.text_input("Guest Name *",placeholder="Nama tamu utama",key="ne_name")
        # Booking ID: value dari pre-parse AI (_ne_prefill_bid), bisa diedit
        ne_booking_id = _n4.text_input(
            "Booking ID (Invoice Number)",
            value=st.session_state.get("_ne_prefill_bid",""),
            placeholder="Otomatis dari receipt · bisa diedit",
            key="ne_booking_id",
            help="Diisi otomatis dari Invoice Number pada receipt. Bisa diubah manual jika perlu."
        )

        def _fmt_date(d):
            try: return d.strftime("%Y-%m-%d") if d else ""
            except: return ""

        _n5,_n6 = st.columns(2)
        ne_checkin_d  = _n5.date_input("Check-in",value=None,format="DD/MM/YYYY",key="ne_checkin")
        ne_checkout_d = _n6.date_input("Check-out",value=None,format="DD/MM/YYYY",key="ne_checkout")
        ne_checkin  = _fmt_date(ne_checkin_d)
        ne_checkout = _fmt_date(ne_checkout_d)

        _n7,_n8 = st.columns(2)
        ne_qty         = _n7.text_input("Room × Night",placeholder="mis: 1 room x 2 nights",key="ne_qty")
        ne_booked_on_d = _n8.date_input("Booking Date",value=None,format="DD/MM/YYYY",key="ne_booked_on")
        ne_booked_on   = _fmt_date(ne_booked_on_d)

        _n9,_n10 = st.columns(2)
        ne_issued_on_d  = _n9.date_input("Issued Date",value=None,format="DD/MM/YYYY",key="ne_issued_on")
        ne_issued_on    = _fmt_date(ne_issued_on_d)
        ne_extra_notes  = _n10.text_input("Catatan Tambahan",placeholder="Tipe kamar, dll (opsional)",key="ne_extra_notes")

        st.markdown("<div style='height:8px'></div>",unsafe_allow_html=True)

        _ne_ready = (bool(ne_files) and bool(bulk_issuer) and bool(bulk_pic.strip())
                     and bool(ne_supplier) and bool(ne_hotel.strip()) and bool(ne_name.strip()))

        st.markdown('<div class="bb-wrap">',unsafe_allow_html=True)
        _ne_run   = st.button("Submit",type="primary",use_container_width=True,
            disabled=not _ne_ready,key="ne_run")
        _ne_clear = st.button("Delete",type="secondary",use_container_width=True,key="ne_clear")
        st.markdown('</div>',unsafe_allow_html=True)

        if not _ne_ready:
            _missing = []
            if not ne_files:           _missing.append("upload receipt")
            if not bulk_issuer:        _missing.append("pilih Issuer")
            if not bulk_pic.strip():   _missing.append("isi PIC")
            if not ne_hotel.strip():   _missing.append("isi Hotel")
            if not ne_name.strip():    _missing.append("isi Guest Name")
            if _missing:
                st.markdown('<div style="font-size:11px;color:#9e9e9e;text-align:center;margin-top:4px">Lengkapi: '
                            +' · '.join(_missing)+'</div>',unsafe_allow_html=True)

        if _ne_clear:
            st.session_state["bulk_results"]=[]
            st.session_state["bulk_saved_count"]=0
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
                # Gunakan hasil pre-parse yang sudah ada di session_state
                _ts_final = st.session_state.get("_ne_prefill_ts","").strip() or now_ts()
                _inv_ai   = st.session_state.get("_ne_prefill_bid","").strip()
                _card_ai  = normalize_card(st.session_state.get("_ne_prefill_card","").strip())
                try: _total = int(st.session_state.get("_ne_prefill_room","0") or 0)
                except: _total = 0

                # Booking ID: utamakan hasil edit user di field, fallback ke AI
                _booking_id_final = ne_booking_id.strip() or _inv_ai

                # Catatan: Invoice Number + catatan tambahan
                _catatan = _booking_id_final
                if ne_extra_notes.strip():
                    _catatan += " · " + ne_extra_notes.strip()

                _parsed_ne = {
                    "timestamp_input": _ts_final,
                    "supplier":        ne_supplier,
                    "booking_id":      _booking_id_final,
                    "booked_on":       ne_booked_on,
                    "issued_on":       ne_issued_on,
                    "hotel":           ne_hotel.strip(),
                    "checkin":         ne_checkin,
                    "qty":             ne_qty.strip(),
                    "room":            _total,
                    "checkout":        ne_checkout,
                    "name":            ne_name.strip(),
                    "card":            _card_ai,
                    "issuer":          bulk_issuer,
                    "pic":             bulk_pic.strip(),
                    "no_bc":           bulk_no_bc.strip(),
                    "nama_kegiatan":   bulk_nama_kegiatan.strip(),
                    "notes":           _catatan,
                }
                save_row(_parsed_ne)
                _ne_res.update(status="success", parsed=_parsed_ne)
                st.session_state["bulk_saved_count"] = 1
            except Exception as _exc_ne:
                _ne_res.update(err=str(_exc_ne)[:200])

            st.session_state["bulk_results"] = [_ne_res]
            st.rerun()

    # ── Results (shared) ──────────────────────────────────────────────────────
    _results = st.session_state.get("bulk_results",[])
    if _results:
        _ok   = sum(1 for r in _results if r["status"]=="success")
        _err  = sum(1 for r in _results if r["status"]=="error")
        _skip = sum(1 for r in _results if r["status"]=="skipped")
        _tot  = len(_results); _pct = int(_ok/_tot*100) if _tot else 0
        st.markdown(
            '<div class="bulk-sum"><div class="bulk-sum-ttl">Hasil Proses</div><div class="bulk-stats">'
            +f'<div><div class="bs-val">{_tot}</div><div class="bs-lbl">Total</div></div>'
            +f'<div><div class="bs-val bs-g">{_ok}</div><div class="bs-lbl">Tersimpan</div></div>'
            +f'<div><div class="bs-val bs-r">{_err}</div><div class="bs-lbl">Gagal</div></div>'
            +f'<div><div class="bs-val bs-y">{_skip}</div><div class="bs-lbl">Duplikat</div></div>'
            +'</div>'
            +f'<div class="bulk-bar"><div class="bulk-bar-f" style="width:{_pct}%"></div></div>'
            +f'<div class="bulk-pct">{_pct}% berhasil tersimpan</div></div>',
            unsafe_allow_html=True)
        st.markdown('<div class="sec-lbl">Detail</div>',unsafe_allow_html=True)
        for _r in _results:
            _s=_r["status"]; _p=_r.get("parsed",{}); _fn=_r["file"]; _rmode=_r.get("mode","expedia")
            _ic={"success":"ic-ok","error":"ic-err","skipped":"ic-skip"}.get(_s,"ic-n")
            _bc={"success":"fb-ok","error":"fb-err","skipped":"fb-sk"}.get(_s,"fb-ok")
            _sy={"success":"&#10003;","error":"&#10005;","skipped":"&#9888;"}.get(_s,"")
            _lb={"success":"Tersimpan","error":"Gagal","skipped":"Duplikat"}.get(_s,_s)
            _wc={"success":"fi-success","error":"fi-error","skipped":"fi-skipped"}.get(_s,"")
            if _p and _s in ("success","skipped"):
                _dw=('<div style="margin-top:8px;font-size:12px;color:#7a5c00;background:#fef9c3;padding:6px 10px;border-radius:9px">&#9888; '+_r.get("err","Duplikat")+'</div>') if _s=="skipped" else ""
                if _rmode=="nonexpedia":
                    _pill='<div style="margin-top:6px"><span style="font-size:10px;color:#7a5c00;background:#fef9c3;border:1px solid #fcd34d;border-radius:6px;padding:2px 8px;font-weight:600">🧾 Non-Expedia</span></div>'
                    _det=(_pill+'<div class="fi-grid">'
                        +'<div class="fi-kv"><span class="fi-k">Hotel</span><span class="fi-v">'+(_p.get("hotel") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Total</span><span class="fi-v">'+fmt(_p.get("room",0))+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Tamu</span><span class="fi-v">'+(_p.get("name") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Kartu</span><span class="fi-v">'+(_p.get("card") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Booking ID</span><span class="fi-v">'+(_p.get("booking_id") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Waktu</span><span class="fi-v">'+(_p.get("timestamp_input") or "—")+'</span></div>'
                        +'</div>'+_dw)
                else:
                    _det=('<div class="fi-grid">'
                        +'<div class="fi-kv"><span class="fi-k">Hotel</span><span class="fi-v">'+(_p.get("hotel") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Total</span><span class="fi-v">'+fmt(_p.get("room",0))+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Tamu</span><span class="fi-v">'+(_p.get("name") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Booking ID</span><span class="fi-v">'+(_p.get("booking_id") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Check-in</span><span class="fi-v">'+(_p.get("checkin") or "—")+'</span></div>'
                        +'<div class="fi-kv"><span class="fi-k">Supplier</span><span class="fi-v">'+(_p.get("supplier") or "—")+'</span></div>'
                        +'</div>'+_dw)
            elif _r.get("err"):
                _det=('<div class="fi-grid" style="grid-template-columns:1fr"><div class="fi-kv"><span class="fi-k">Error</span><span class="fi-v" style="color:#e53935;white-space:normal">'+_r["err"]+'</span></div></div>')
            else: _det=""
            st.markdown('<div class="file-item '+_wc+'"><div class="fi-top"><div class="fi-icon '+_ic+'">&#128247;</div><div class="fi-name">'+_fn+'</div><span class="fi-badge '+_bc+'">'+_sy+' '+_lb+'</span></div>'+_det+'</div>',unsafe_allow_html=True)
        _sid = sheet_id()
        if _sid and _ok:
            st.link_button(f"📊  Buka Google Sheets ({_ok} baris tersimpan)",
                f"https://docs.google.com/spreadsheets/d/{_sid}",use_container_width=True)
        if _err: notice("warn",f"{_err} file gagal. Periksa kualitas file dan coba lagi.")
    _render_footer()


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["tab"] == "dashboard":
    import pandas as pd
    if not _dashboard_login_wall():
        _render_footer(); st.stop()
    _cr,_cb2,_cb3 = st.columns([3,1,1])
    _cr.markdown('<div class="sec-lbl" style="margin-top:6px">Ringkasan</div>',unsafe_allow_html=True)
    if _cb2.button("↻ Refresh",type="secondary",use_container_width=True,key="dash_ref"):
        st.cache_resource.clear(); st.rerun()
    with _cb3: _render_logout_button()
    try:
        with st.spinner("Memuat data..."): rows = load_rows()
        if not rows:
            notice("info","Belum ada transaksi. Tambahkan melalui tab Input.")
        else:
            df = pd.DataFrame(rows)
            if "Total (Rp)" in df.columns:
                df["Total (Rp)"] = pd.to_numeric(df["Total (Rp)"],errors="coerce").fillna(0)
            tn = len(df); tr = df["Total (Rp)"].sum() if "Total (Rp)" in df.columns else 0
            avg = tr/tn if tn else 0
            tds = datetime.now().strftime("%d/%m/%Y")
            tdc = int(df["Timestamp Input"].astype(str).str.startswith(tds).sum()) if "Timestamp Input" in df.columns else 0
            st.markdown('<div class="stat-grid">'
                +f'<div class="stat-card"><div class="stat-val">{tn}</div><div class="stat-lbl">Total transaksi</div></div>'
                +f'<div class="stat-card"><div class="stat-val" style="font-size:17px">{fmt(tr)}</div><div class="stat-lbl">Total pengeluaran</div></div>'
                +f'<div class="stat-card"><div class="stat-val" style="font-size:17px">{fmt(avg)}</div><div class="stat-lbl">Rata-rata</div></div>'
                +f'<div class="stat-card"><div class="stat-val">{tdc}</div><div class="stat-lbl">Input hari ini</div></div>'
                +'</div>',unsafe_allow_html=True)
            st.markdown('<div class="sec-lbl">Filter</div>',unsafe_allow_html=True)
            _date_opts = [c for c in ["Check-in","Booking Date","Issued Date","Timestamp Input"] if c in df.columns]
            _fa,_fb,_fc = st.columns([2,1,1])
            with _fa:
                _filter_col = st.selectbox("Kolom tanggal",options=_date_opts,index=0,
                    label_visibility="collapsed",key="dash_filter_col")
            def _parse_date_col(series):
                p = pd.to_datetime(series,dayfirst=True,errors="coerce")
                if p.isna().all(): p = pd.to_datetime(series,errors="coerce")
                return p
            _df_dated = df.copy()
            _df_dated["_parsed_date"] = _parse_date_col(_df_dated[_filter_col].astype(str))
            _valid = _df_dated["_parsed_date"].dropna()
            if not _valid.empty:
                _min_date=_valid.min().date(); _max_date=_valid.max().date()
                with _fb:
                    _date_from = st.date_input("Dari",value=_min_date,min_value=_min_date,
                        max_value=_max_date,label_visibility="collapsed",key="dash_date_from")
                with _fc:
                    _date_to = st.date_input("Sampai",value=_max_date,min_value=_min_date,
                        max_value=_max_date,label_visibility="collapsed",key="dash_date_to")
                _mask = ((_df_dated["_parsed_date"].dt.date >= _date_from) &
                         (_df_dated["_parsed_date"].dt.date <= _date_to))
                df = _df_dated[_mask].drop(columns=["_parsed_date"]).reset_index(drop=True)
                _fn2=len(df); _tr2=df["Total (Rp)"].sum() if "Total (Rp)" in df.columns else 0
                _avg2=_tr2/_fn2 if _fn2 else 0
                if _fn2 != tn:
                    st.markdown(f'<div style="display:flex;gap:8px;margin-bottom:12px;">'
                        +f'<div style="flex:1;background:#e8f0fe;border-radius:12px;padding:10px 14px;"><div style="font-size:11px;color:#1e3a6e;">Transaksi terfilter</div><div style="font-size:18px;font-weight:700;color:#191d3a;">{_fn2}</div></div>'
                        +f'<div style="flex:1;background:#e8f0fe;border-radius:12px;padding:10px 14px;"><div style="font-size:11px;color:#1e3a6e;">Total terfilter</div><div style="font-size:16px;font-weight:700;color:#191d3a;">{fmt(_tr2)}</div></div>'
                        +f'<div style="flex:1;background:#e8f0fe;border-radius:12px;padding:10px 14px;"><div style="font-size:11px;color:#1e3a6e;">Rata-rata</div><div style="font-size:16px;font-weight:700;color:#191d3a;">{fmt(_avg2)}</div></div>'
                        +'</div>',unsafe_allow_html=True)
            if "Kartu Kredit" in df.columns and "Total (Rp)" in df.columns:
                # Normalize semua nilai kartu kredit ke format display canonical
                df["Kartu Kredit"] = df["Kartu Kredit"].astype(str).apply(normalize_card)
                _card_str = df["Kartu Kredit"].astype(str).str.strip().str.lower()
                _cc = df[_card_str.ne("") & _card_str.ne("nan") & _card_str.ne("none")]
                if not _cc.empty:
                    st.markdown('<div class="sec-lbl">Kartu Kredit</div>',unsafe_allow_html=True)
                    _grp = _cc.groupby("Kartu Kredit")["Total (Rp)"].sum().sort_values(ascending=False).reset_index()
                    _grp.columns = ["label","val"]; _tot2 = _grp["val"].sum(); _cnt = _cc.groupby("Kartu Kredit").size()
                    _h = ""
                    for _,_row in _grp.iterrows():
                        _p=_row["val"]/_tot2*100 if _tot2 else 0; _a="Rp {:,.0f}".format(_row["val"]).replace(",",".")
                        _c=int(_cnt.get(_row["label"],0))
                        _h += (f'<div style="padding:12px 0;border-bottom:1.5px solid #ededed">'
                            +f'<div style="display:flex;justify-content:space-between;margin-bottom:6px"><span style="font-size:14px;font-weight:600;color:#191d3a">{_row["label"]}</span><span style="font-size:14px;font-weight:700;color:#191d3a">{_a}</span></div>'
                            +f'<div style="display:flex;align-items:center;gap:10px"><div style="flex:1;background:#e8e8e8;border-radius:4px;height:4px"><div style="width:{int(_p)}%;background:#6398c8;border-radius:4px;height:4px"></div></div>'
                            +f'<span style="font-size:12px;color:#9e9e9e;white-space:nowrap">{_p:.1f}% · {_c} transaksi</span></div></div>')
                    st.markdown(f'<div style="background:#fff;border:1.5px solid #ddd;border-radius:18px;padding:4px 16px">{_h}</div>',unsafe_allow_html=True)
            st.markdown('<div class="sec-lbl">Data transaksi</div>',unsafe_allow_html=True)
            srch = st.text_input("",placeholder="🔍  Cari hotel / tamu / booking ID...",
                label_visibility="collapsed",key="srch")
            if srch:
                df = df[df.apply(lambda r:r.astype(str).str.contains(srch,case=False,na=False).any(),axis=1)]
            _disp = df.iloc[::-1].reset_index(drop=True).copy()
            if "Booking ID" in _disp.columns: _disp["Booking ID"] = _disp["Booking ID"].astype(str)
            _cfg = {}
            if "Booking ID" in _disp.columns: _cfg["Booking ID"]=st.column_config.TextColumn("Booking ID")
            if "Total (Rp)" in _disp.columns: _cfg["Total (Rp)"]=st.column_config.NumberColumn("Total (Rp)",format="Rp %d")
            if "Room x Night" in _disp.columns: _cfg["Room x Night"]=st.column_config.TextColumn("Room × Night")
            if "Timestamp Input" in _disp.columns: _cfg["Timestamp Input"]=st.column_config.TextColumn("Timestamp")
            st.dataframe(_disp,use_container_width=True,height=360,column_config=_cfg,hide_index=True)
    except Exception as e:
        notice("err",str(e)); notice("info","Konfigurasi Google Sheets di tab Pengaturan.")
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
            df_log = pd.DataFrame(rows)
            def _pts(v):
                try: return pd.to_datetime(str(v),dayfirst=True)
                except: return pd.NaT
            df_log["_ts"] = df_log["Timestamp Input"].apply(_pts)
            df_log = df_log.sort_values("_ts",ascending=False).reset_index(drop=True)
            _total = len(df_log); _recent = df_log.head(10)
            st.markdown(f'''<div style="display:flex;align-items:center;justify-content:space-between;
                margin-top:6px;margin-bottom:12px;">
              <div class="sec-lbl" style="margin:0;border:none;padding:0;">Activity Log</div>
              <span style="font-size:11px;color:#9e9e9e;font-weight:500;">10 dari {_total} transaksi</span>
            </div>''',unsafe_allow_html=True)
            _items_html = ""
            for _,_row in _recent.iterrows():
                _ts=str(_row.get("Timestamp Input","—")); _bid=str(_row.get("Booking ID","—"))
                _hotel=str(_row.get("Hotel","")) or "—"; _issuer=str(_row.get("Issuer","")) or "—"
                _total_r=_row.get("Total (Rp)",0)
                try: _amt="Rp {:,}".format(int(float(_total_r))).replace(",",".")
                except: _amt="—"
                _items_html += f'''
<div style="display:flex;align-items:center;gap:12px;padding:11px 14px;
    background:#fff;border-radius:12px;border:0.5px solid #e8e8e8;margin-bottom:6px;">
  <div style="width:36px;height:36px;border-radius:10px;background:#f5f5f5;
      display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px;">🏨</div>
  <div style="flex:1;min-width:0;">
    <div style="font-size:13px;font-weight:600;color:#191d3a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{_hotel}</div>
    <div style="font-size:11px;color:#9e9e9e;margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{_bid} &nbsp;·&nbsp; {_issuer}</div>
  </div>
  <div style="text-align:right;flex-shrink:0;">
    <div style="font-size:12px;font-weight:600;color:#191d3a;">{_amt}</div>
    <div style="font-size:10px;color:#bbb;margin-top:1px;">{_ts}</div>
  </div>
</div>'''
            st.markdown(_items_html,unsafe_allow_html=True)
    except Exception as e: notice("err",str(e))
    _render_footer()

# ═══════════════════════════════════════════════════════════════════════════════
#  TAB — SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["tab"] == "settings":
    _cur_prov = get_ai_provider(); _active_lbl = "OpenAI" if _cur_prov=="openai" else "Claude"
    st.markdown('<div class="sec-lbl" style="margin-top:6px">AI Provider</div>',unsafe_allow_html=True)
    st.markdown('<div class="ai-card-btn-wrap">',unsafe_allow_html=True)
    if st.button(f"{'✦ ' if _cur_prov=='claude' else ''}Claude AI  ·  claude-sonnet-4-5  ★ Default",
        key="sel_claude",use_container_width=True,type="primary" if _cur_prov=="claude" else "secondary"):
        st.session_state["ai_provider"]="claude"; st.rerun()
    if st.button(f"{'✦ ' if _cur_prov=='openai' else ''}OpenAI  ·  gpt-4o-mini",
        key="sel_openai",use_container_width=True,type="primary" if _cur_prov=="openai" else "secondary"):
        st.session_state["ai_provider"]="openai"; st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)
    st.markdown(
        f'<div class="ai-status-bar"><div class="ai-status-dot"></div>'
        f'<span class="ai-status-txt">Active: {_active_lbl}</span></div>',
        unsafe_allow_html=True)
    st.markdown('<div class="sec-lbl" style="margin-top:18px">API Keys</div>',unsafe_allow_html=True)
    for _pname,_sskey,_section,_placeholder,_skey in [
        ("Claude AI","claude_key_manual","anthropic","sk-ant-api03-...","inp_cla_key"),
        ("OpenAI","openai_key_manual","openai","sk-proj-...","inp_oai_key")]:
        _secrets_ok = False
        try:
            k = st.secrets[_section]["api_key"]
            if k and len(k)>20 and "GANTI" not in k and "PASTE" not in k: _secrets_ok = True
        except: pass
        _ready = _secrets_ok or bool(st.session_state.get(_sskey,""))
        _dot_c = "#1D9E75" if _ready else "#e68900"
        _lbl   = "ready" if _ready else "belum dikonfigurasi"
        _lcls  = "ai-key-ok" if _ready else "ai-key-warn"
        st.markdown(f'<div class="ai-key-row"><div class="ai-key-left"><div class="ai-key-dot" style="background:{_dot_c}"></div><span class="ai-key-name">{_pname}</span></div><span class="{_lcls}">{_lbl}</span></div>',unsafe_allow_html=True)
        if not _ready:
            _nk = st.text_input(_pname+" Key",value=st.session_state.get(_sskey,""),
                type="password",placeholder=_placeholder,label_visibility="collapsed",key=_skey)
            if _nk != st.session_state.get(_sskey,""):
                st.session_state[_sskey]=_nk; st.rerun()
    st.markdown('<div class="sec-lbl">Status Sistem</div>',unsafe_allow_html=True)
    sh_ok = False
    try:
        if st.secrets["google_sheets"]["sheet_id"] and st.secrets["gcp_service_account"]["client_email"]: sh_ok=True
    except: pass
    if sh_ok:
        st.markdown('<div class="st-row"><div class="st-icon si-g">📊</div><div class="st-body"><div class="st-title">Google Sheets</div><div class="st-sub">Terhubung via secrets.toml</div></div><span class="st-badge bg">✓ Aktif</span></div>',unsafe_allow_html=True)
    else:
        st.markdown('<div class="st-row"><div class="st-icon si-y">📊</div><div class="st-body"><div class="st-title">Google Sheets</div><div class="st-sub">Belum dikonfigurasi</div></div><span class="st-badge by">⚠ Belum</span></div>',unsafe_allow_html=True)
        notice("warn","Isi <code>.streamlit/secrets.toml</code> sesuai README.")
        ns = st.text_input("Sheet ID",value=st.session_state.get("sheet_id",""),
            label_visibility="collapsed",placeholder="1nvgMCmo...")
        if ns != st.session_state.get("sheet_id",""): st.session_state["sheet_id"]=ns
    if _PDF_OK:
        st.markdown('<div class="st-row"><div class="st-icon si-b">📄</div><div class="st-body"><div class="st-title">PDF Upload</div><div class="st-sub">pypdfium2 terinstall</div></div><span class="st-badge bg">✓ Aktif</span></div>',unsafe_allow_html=True)
    else:
        st.markdown('<div class="st-row"><div class="st-icon si-r">📄</div><div class="st-body"><div class="st-title">PDF Upload</div><div class="st-sub">pypdfium2 tidak terinstall</div></div><span class="st-badge br">✕ Nonaktif</span></div>',unsafe_allow_html=True)
        notice("err","Jalankan: <code>pip install pypdfium2==4.30.0</code>")
    st.markdown('<div class="sec-lbl">Tentang Aplikasi</div>',unsafe_allow_html=True)
    _active_model = "gpt-4o-mini (OpenAI)" if get_ai_provider()=="openai" else "claude-sonnet-4-5 (Anthropic)"
    st.markdown(f"""
<div class="about-box">
  <div class="about-ttl">AI Intelligent Automation Scanner System v6</div>
  <div class="about-r"><div class="about-k">Input</div>
    <div class="about-v">Expedia/TAAP: PDF · JPG · PNG bulk upload &nbsp;|&nbsp; Non-Expedia: JPG · PNG + isian manual</div></div>
  <div class="about-r"><div class="about-k">Output</div>
    <div class="about-v">Google Sheets — 17 kolom terstruktur</div></div>
  <div class="about-r"><div class="about-k">Dokumen</div>
    <div class="about-v">Expedia TAAP · Mitra Tours · Invoice hotel · Payment Receipt</div></div>
  <div class="about-r"><div class="about-k">Model AI</div>
    <div class="about-v">{_active_model} <b>(aktif)</b> · bisa diganti di atas</div></div>
</div>""",unsafe_allow_html=True)
    _render_footer()
