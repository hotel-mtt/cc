# =============================================================================
#  AI CC Reporting System  v5
#  Run  : streamlit run app.py
#  Setup: pip install -r requirements.txt
#         .streamlit/secrets.toml
# =============================================================================
import streamlit as st
import openai, gspread, json, base64, re, io, warnings
from google.oauth2.service_account import Credentials
from datetime import datetime
from PIL import Image

try:
    import pypdfium2 as _pdfium
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

# =============================================================================
#  PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="CC Reporting",
    page_icon="💳",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =============================================================================
#  CSS
# =============================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body,[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],.main{background:#F8F9FA !important}
.main .block-container{
    padding:1rem 1rem 4rem !important;
    max-width:580px !important;
    margin:0 auto !important}
[data-testid="stSidebar"],#MainMenu,footer,header,
[data-testid="stDecoration"]{display:none !important}
*{font-family:'Inter',system-ui,sans-serif !important}

/* top bar */
.top-bar{background:#111;padding:13px 18px;border-radius:12px;
    display:flex;align-items:center;gap:10px;margin-bottom:6px}
.top-bar .mark{font-size:16px;font-weight:700;color:#fff;letter-spacing:-1px}
.top-bar .sub{font-size:12px;color:#888;flex:1}
.top-bar .live{font-size:10px;font-weight:700;background:#0d2b0d;color:#4ade80;
    border:1px solid #166534;padding:3px 9px;border-radius:20px}

/* step bar */
.step-row{display:flex;align-items:center;background:#fff;
    border:1px solid #E5E7EB;border-radius:12px;padding:12px 10px;margin-bottom:16px}
.step-col{display:flex;flex-direction:column;align-items:center;flex:1}
.step-dot{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;
    justify-content:center;font-size:11px;font-weight:700;margin-bottom:4px}
.step-dot.done{background:#1a1a1a;color:#fff}
.step-dot.now{background:#111;color:#fff;outline:3px solid #ddd;outline-offset:1px}
.step-dot.wait{background:#F3F4F6;color:#ccc;border:1px solid #E5E7EB}
.step-lbl{font-size:9px;color:#9CA3AF;text-align:center;font-weight:500}
.step-lbl.now{color:#111;font-weight:700}
.step-line{flex:1;height:1px;background:#E5E7EB;margin:0 4px;margin-bottom:14px}
.step-line.done{background:#111}

/* mode selector */
.mode-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}
.mode-card{border:1.5px solid #E5E7EB;border-radius:10px;padding:12px 6px 10px;
    text-align:center;background:#fff}
.mode-card.on{border-color:#111;background:#F9FAFB}
.mode-card .ic{font-size:18px;margin-bottom:5px;display:block}
.mode-card .lb{font-size:11px;font-weight:600;color:#111}
.mode-card .sb{font-size:10px;color:#9CA3AF;margin-top:2px}
.mode-card.on .lb{font-weight:700}

/* section label */
.sec-lbl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
    color:#9CA3AF;margin-bottom:8px;padding-bottom:7px;border-bottom:1px solid #F3F4F6}

/* preview grid */
.preview-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:14px}
.pc{border-left:3px solid;padding:9px 11px;border-radius:0 8px 8px 0}
.pc.wide{grid-column:span 2}
.pc .k{font-size:9px;font-weight:700;text-transform:uppercase;
    letter-spacing:.6px;opacity:.65;margin-bottom:3px}
.pc .v{font-size:13px;font-weight:700;overflow:hidden;
    text-overflow:ellipsis;white-space:nowrap}
.pc .v.na{opacity:.35;font-style:italic;font-weight:400;font-size:11px}

/* field rows */
.frow{display:flex;align-items:center;padding:9px 13px;
    border-bottom:1px solid #F9FAFB;gap:9px}
.frow:last-child{border-bottom:none}
.fdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.fbody{flex:1;min-width:0}
.fk{font-size:9px;font-weight:700;text-transform:uppercase;
    letter-spacing:.6px;color:#9CA3AF;margin-bottom:1px}
.fv{font-size:13px;font-weight:600;color:#111;overflow:hidden;
    text-overflow:ellipsis;white-space:nowrap}

/* notices */
.notice{border-radius:9px;padding:10px 13px;font-size:12px;line-height:1.5;
    display:flex;align-items:flex-start;gap:7px;margin-bottom:12px}
.nok{background:#F0FDF4;border:1px solid #86EFAC;color:#166534}
.nerr{background:#FFF1F2;border:1px solid #FECDD3;color:#9F1239}
.ninfo{background:#F0F6FF;border:1px solid #BFDBFE;color:#1E40AF}
.nwarn{background:#FFFBEB;border:1px solid #FDE68A;color:#92400E}

/* stat grid */
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
.stat-card{background:#fff;border:1px solid #E5E7EB;border-radius:11px;padding:13px 12px}
.stat-val{font-size:20px;font-weight:700;color:#111;line-height:1.1}
.stat-lbl{font-size:10px;color:#9CA3AF;margin-top:4px;font-weight:500}

/* done */
.done-box{text-align:center;padding:22px 14px 14px}
.done-circle{width:52px;height:52px;border-radius:50%;background:#F3F4F6;
    border:2px solid #111;display:flex;align-items:center;justify-content:center;
    font-size:22px;margin:0 auto 11px}
.done-title{font-size:17px;font-weight:700;color:#111;margin-bottom:4px}
.done-sub{font-size:12px;color:#9CA3AF}

/* form overrides */
.stTextInput input,.stNumberInput input,
.stTextArea textarea,.stSelectbox select{
    border-radius:9px !important;border:1.5px solid #E5E7EB !important;
    background:#FAFAFA !important;font-size:13px !important;
    color:#111 !important;padding:9px 12px !important;
    font-family:'Inter',sans-serif !important}
.stTextInput input:focus,.stNumberInput input:focus,
.stTextArea textarea:focus,.stSelectbox select:focus{
    border-color:#111 !important;background:#fff !important;
    box-shadow:0 0 0 3px rgba(0,0,0,.06) !important;outline:none !important}
label[data-testid="stWidgetLabel"] p,
label[data-testid="stWidgetLabel"]{
    font-size:10px !important;font-weight:700 !important;
    color:#9CA3AF !important;text-transform:uppercase !important;
    letter-spacing:.8px !important}
.stButton>button,.stFormSubmitButton>button{
    width:100% !important;height:46px !important;border-radius:10px !important;
    font-size:13px !important;font-weight:600 !important;border:none !important;
    font-family:'Inter',sans-serif !important}

/* ── All primary: black solid ── */
.stButton>button[kind="primary"],
.stFormSubmitButton>button[kind="primary"]{
    background:#111 !important;color:#fff !important;
    border:none !important;box-shadow:none !important}
.stButton>button[kind="primary"]:hover{background:#333 !important}

/* ── All secondary: white with border ── */
.stButton>button[kind="secondary"],
.stFormSubmitButton>button[kind="secondary"]{
    background:#fff !important;border:1.5px solid #E5E7EB !important;
    color:#374151 !important}
.stButton>button[kind="secondary"]:hover{
    background:#F9FAFB !important;border-color:#D1D5DB !important}


[data-testid="stFileUploader"]>div:first-child{
    border:1.5px dashed #D1D5DB !important;border-radius:11px !important;
    background:#FAFAFA !important}
[data-testid="stFileUploader"]>div:first-child:hover{
    border-color:#111 !important;background:#F3F4F6 !important}
.stExpander{border:1px solid #E5E7EB !important;
    border-radius:10px !important;margin-bottom:10px !important}
details>summary{font-size:12px !important;color:#6B7280 !important}
[data-testid="stDataFrame"]{border-radius:11px !important;
    border:1px solid #E5E7EB !important;overflow:hidden !important}
.stSpinner>div{border-top-color:#111 !important}

/* ── Metric cards (step 4 summary) ── */
[data-testid="stMetric"]{
    background:#fff !important;
    border:1px solid #E5E7EB !important;
    border-radius:10px !important;
    padding:10px 12px !important;
    margin-bottom:0 !important;
}
[data-testid="stMetricLabel"]{
    font-size:10px !important;
    font-weight:700 !important;
    color:#9CA3AF !important;
    text-transform:uppercase !important;
    letter-spacing:.7px !important;
}
[data-testid="stMetricValue"]{
    font-size:13px !important;
    font-weight:600 !important;
    color:#111 !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    white-space:nowrap !important;
}

/* ── Dataframe improvements ── */
[data-testid="stDataFrame"]{
    border-radius:12px !important;
    border:1px solid #E5E7EB !important;
    overflow:hidden !important;
    box-shadow:0 1px 3px rgba(0,0,0,.04) !important;
}
[data-testid="stDataFrame"] table{font-size:12px !important}
[data-testid="stDataFrame"] th{
    background:#F9FAFB !important;
    color:#6B7280 !important;
    font-size:11px !important;
    font-weight:600 !important;
    text-transform:uppercase !important;
    letter-spacing:.5px !important;
    border-bottom:1px solid #E5E7EB !important;
    padding:10px 12px !important;
}
[data-testid="stDataFrame"] td{
    font-size:12px !important;
    color:#111827 !important;
    padding:9px 12px !important;
    border-bottom:1px solid #F9FAFB !important;
    vertical-align:middle !important;
}
[data-testid="stDataFrame"] tr:hover td{
    background:#F9FAFB !important;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
#  KEY HELPERS
# =============================================================================
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


# =============================================================================
#  GOOGLE SHEETS  — 13 columns
# =============================================================================
COLS = [
    "Timestamp Input", "Supplier",      "Booking ID",  "Booking Date",
    "Issued Date",     "Hotel",         "Check-in",    "Room x Night",
    "Total (Rp)",      "Check-out",     "Guest Name",  "Kartu Kredit",
    "Issuer",          "PIC",           "No. BC",          "Nama Kegiatan",
    "Catatan",
]


@st.cache_resource(ttl=300)
def ws():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    s = gspread.authorize(creds).open_by_key(sheet_id()).sheet1
    try:
        if not s.row_values(1) or s.cell(1, 1).value != COLS[0]:
            s.insert_row(COLS, 1)
    except Exception:
        s.insert_row(COLS, 1)
    return s


def save_row(d: dict):
    ws().append_row(
        [d.get(k, "") for k in [
            "timestamp_input", "supplier",  "booking_id", "booked_on",
            "issued_on",       "hotel",     "checkin",    "qty",
            "room",            "checkout",  "name",       "card",
            "issuer",          "pic",       "no_bc",     "nama_kegiatan",
            "notes",
        ]],
        value_input_option="USER_ENTERED",
    )


def load_rows() -> list:
    return ws().get_all_records()


# =============================================================================
#  DUPLICATE CHECK
# =============================================================================
def _norm_str(v) -> str:
    return str(v or "").strip().lower()


def _norm_int(v) -> int:
    try:
        return int(float(str(v).replace(",", "").replace(".", "") or 0))
    except Exception:
        return 0


def check_duplicate(new: dict, rows: list) -> tuple:
    """
    Returns (is_dup: bool, reason: str, matched_row: dict | None)
    Primary   : same Booking ID
    Secondary : 3+ of (hotel, checkin, name, amount) match
    """
    bid   = _norm_str(new.get("booking_id"))
    hotel = _norm_str(new.get("hotel"))
    ci    = _norm_str(new.get("checkin"))
    name  = _norm_str(new.get("name"))
    amt   = _norm_int(new.get("room"))

    for r in rows:
        # Primary match
        if bid and bid == _norm_str(r.get("Booking ID")):
            return True, "Booking ID sudah terdaftar", r

        # Secondary match
        score = sum([
            hotel == _norm_str(r.get("Hotel")),
            ci    == _norm_str(r.get("Check-in")),
            name  == _norm_str(r.get("Guest Name")),
            amt   == _norm_int(r.get("Total (Rp)")),
        ])
        if score >= 3:
            return True, "Kemungkinan duplikat (kesamaan tinggi)", r

    return False, "", None


# =============================================================================
#  PDF HELPERS
# =============================================================================
def pdf_images(data: bytes) -> list:
    if not _PDF_OK:
        raise RuntimeError(
            "pypdfium2 not installed — run: pip install pypdfium2==4.30.0"
        )
    doc = _pdfium.PdfDocument(data)
    return [doc[i].render(scale=2.0).to_pil() for i in range(len(doc))]


def pdf_text(data: bytes) -> str:
    if not _PDF_OK or not data:
        return ""
    try:
        doc, parts = _pdfium.PdfDocument(data), []
        for i in range(len(doc)):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                parts.append(doc[i].get_textpage().get_text_bounded())
        return "\n".join(parts).strip()
    except Exception:
        return ""


def to_b64(img: Image.Image) -> tuple:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"


# =============================================================================
#  AI PARSER
# =============================================================================
_SYS = """You are a corporate hotel expense AI parser for credit card reporting.
Parse any document: Expedia TAAP receipt, Mitra Tours itinerary, hotel invoice,
screenshot, or free text.
Return ONLY a valid JSON object — no markdown, no explanation.

Keys:
- supplier   : string  — platform from document header
                         e.g. "Expedia TAAP", "Mitra Tours & Travel"
                         If both appear → "Mitra Tours & Travel / Expedia TAAP"
- booking_id : string  — TAAP itinerary number / Itinerary # / Booking ID
- booked_on  : string  — booking date YYYY-MM-DD  (Booked on)
- issued_on  : string  — issued date YYYY-MM-DD   (Issued on)
- hotel      : string  — full hotel name as written
- checkin    : string  — check-in YYYY-MM-DD
- checkout   : string  — check-out YYYY-MM-DD
- qty        : string  — rooms and nights e.g. "1 room x 3 nights"
- room       : integer — IDR amount from "Subtotal paid to Expedia" line.
                         "Subtotal paid to Expedia  IDR 34,493,666.00" → 34493666
                         This is the amount charged to the credit card.
                         IGNORE "Room" line, per-night lines, and resort fee.
- name       : string  — guest name (Traveller information / Reserved for)
- card       : string  — e.g. "MasterCard •••• 4467", empty string if absent
- notes      : string  — room type, nights, resort fee, confirmation #, other details

Rules:
1. Dates: any format → YYYY-MM-DD.
   "Wed 06 May 2026" → "2026-05-06"   |   "30 Apr 2026" → "2026-04-30"
2. Amounts: strip IDR/Rp/USD/$/commas/dots → plain integer, no decimals.
3. room = "Subtotal paid to Expedia" line only.
4. Missing field → "" for strings, 0 for integers."""


def ai_parse(text: str = "", images: list = None) -> tuple:
    key = oai_key()
    if not key:
        raise ValueError("OpenAI API key belum diisi — buka tab Pengaturan.")

    content = []
    if images:
        for b64, mime in images:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
            })

    content.append({
        "type": "text",
        "text": text if text else "Extract all structured data from this document.",
    })

    resp = openai.OpenAI(api_key=key).chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYS},
            {"role": "user",   "content": content},
        ],
        temperature=0.0,
        max_tokens=800,
    )

    raw = resp.choices[0].message.content
    m   = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise ValueError("Format AI tidak valid — JSON tidak ditemukan.")
    return json.loads(m.group()), raw


# =============================================================================
#  UI UTILITIES
# =============================================================================
def fmt(v) -> str:
    try:    return "Rp {:,}".format(int(float(v or 0))).replace(",", ".")
    except: return str(v) if v else "—"


def now_ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def notice(kind: str, msg: str):
    icons = {"ok": "✓", "err": "✕", "info": "ℹ", "warn": "⚠"}
    cls   = {"ok": "nok", "err": "nerr", "info": "ninfo", "warn": "nwarn"}
    st.markdown(
        f'<div class="notice {cls[kind]}">'
        f'<b>{icons[kind]}</b>&ensp;{msg}</div>',
        unsafe_allow_html=True,
    )


def stepbar(cur: int):
    steps = [("Input", 1), ("Proses", 2), ("Konfirmasi", 3), ("Selesai", 4)]
    h = '<div class="step-row">'
    for lbl, n in steps:
        dc  = "done" if n < cur else ("now" if n == cur else "wait")
        sym = "✓" if n < cur else str(n)
        lc  = " now" if n == cur else ""
        h  += (
            f'<div class="step-col">'
            f'<div class="step-dot {dc}">{sym}</div>'
            f'<div class="step-lbl{lc}">{lbl}</div>'
            f'</div>'
        )
        if n < 4:
            h += f'<div class="step-line{" done" if n < cur else ""}"></div>'
    st.markdown(h + "</div>", unsafe_allow_html=True)


# 12 colour-coded preview fields
_FIELDS = [
    # (key, label, border, bg, fg, wide, fmt_fn)
    ("timestamp_input", "Timestamp",    "#8B5CF6", "#F5F3FF", "#4C1D95", False, None),
    ("supplier",        "Supplier",     "#D946EF", "#FDF4FF", "#701A75", False, None),
    ("booking_id",      "Booking ID",   "#EF4444", "#FFF1F2", "#881337", False, None),
    ("booked_on",       "Booking Date", "#F97316", "#FFF7ED", "#7C2D12", False, None),
    ("issued_on",       "Issued Date",  "#EAB308", "#FEFCE8", "#713F12", False, None),
    ("hotel",           "Hotel",        "#22C55E", "#F0FDF4", "#14532D", True,  None),
    ("checkin",         "Check-in",     "#3B82F6", "#EFF6FF", "#1E3A8A", False, None),
    ("qty",             "Room × Night", "#0D9488", "#F0FDFA", "#134E4A", False, None),
    ("room",            "Total (Rp)",   "#EA580C", "#FFF4EE", "#9A3412", False, fmt),
    ("checkout",        "Check-out",    "#7C3AED", "#EDE9FE", "#3B0764", False, None),
    ("name",            "Guest Name",   "#EC4899", "#FDF2F8", "#9D174D", False, None),
    ("card",            "Credit Card",  "#F43F5E", "#FFF1F2", "#9F1239", False, None),
]


def preview_grid(p: dict):
    h = '<div class="preview-grid">'
    for key, lbl, bdr, bg, fg, wide, fn in _FIELDS:
        val  = p.get(key, "")
        if key == "timestamp_input" and not val:
            val = now_ts()
        disp = fn(val) if fn and val else (str(val) if val else "")
        vcls = "" if disp else " na"
        w    = " wide" if wide else ""
        h   += (
            f'<div class="pc{w}" '
            f'style="background:{bg};border-color:{bdr};color:{fg}">'
            f'<div class="k">{lbl}</div>'
            f'<div class="v{vcls}">{disp or "—"}</div>'
            f'</div>'
        )
    st.markdown(h + "</div>", unsafe_allow_html=True)


def field_row(lbl: str, val: str, color: str = "#9CA3AF"):
    st.markdown(
        f'<div class="frow">'
        f'<div class="fdot" style="background:{color}"></div>'
        f'<div class="fbody">'
        f'<div class="fk">{lbl}</div>'
        f'<div class="fv">{val or "—"}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def card_list_open():
    st.markdown(
        '<div style="background:#fff;border:1px solid #E5E7EB;'
        'border-radius:14px;overflow:hidden;margin-bottom:12px">',
        unsafe_allow_html=True,
    )


def card_list_close():
    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
#  SESSION STATE
# =============================================================================
_DEF = {
    "tab":      "input",
    "step":     1,
    "parsed":   {},
    "raw":      "",
    "mode":     "photo",
    "saved":    None,
    "imgs":     [],
    "pdfraw":   b"",
    "oai_key":  "",
    "sheet_id": "1nvgMCmo1EJtbCAt0db_OizvPYDvaEzphKhwzBJ-3X_g",
}

for k, v in _DEF.items():
    if k not in st.session_state:
        st.session_state[k] = v


def reset():
    for k in list(st.session_state.keys()):
        if k != "tab":
            del st.session_state[k]
    for k, v in _DEF.items():
        st.session_state[k] = v


# =============================================================================
#  HEADER  +  NAV
# =============================================================================
st.markdown("""
<div class="top-bar">
  <span class="mark">CC</span>
  <span class="sub">AI Reporting System</span>
  <span class="live">LIVE</span>
</div>""", unsafe_allow_html=True)

# ── Navigation: st.radio horizontal — single widget, consistent shape ──────
st.markdown("""
<style>
/* Radio nav: hide default radio circle, style label as pill button */
div[data-testid="stRadio"] > label { display:none }
div[data-testid="stRadio"] > div[role="radiogroup"] {
    display: grid !important;
    grid-template-columns: repeat(4, 1fr) !important;
    gap: 6px !important;
    margin-bottom: 14px !important;
}
div[data-testid="stRadio"] label[data-baseweb="radio"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    height: 42px !important;
    border-radius: 10px !important;
    border: 1.5px solid #E5E7EB !important;
    background: #fff !important;
    cursor: pointer !important;
    transition: all .15s !important;
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
}
div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {
    background: #F9FAFB !important;
    border-color: #D1D5DB !important;
}
div[data-testid="stRadio"] label[data-baseweb="radio"][aria-checked="true"] {
    background: #111 !important;
    border-color: #111 !important;
    color: #fff !important;
}
/* Radio text */
div[data-testid="stRadio"] label[data-baseweb="radio"] span:last-child {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #374151 !important;
    font-family: 'Inter', sans-serif !important;
}
div[data-testid="stRadio"] label[data-baseweb="radio"][aria-checked="true"] span:last-child {
    color: #fff !important;
}
/* Hide the actual radio dot */
div[data-testid="stRadio"] label[data-baseweb="radio"] span:first-child {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

_NAV_OPTIONS = ["Input", "Dashboard", "Riwayat", "Pengaturan"]
_NAV_KEYS    = {"Input":"input","Dashboard":"dashboard",
                "Riwayat":"log","Pengaturan":"settings"}
_NAV_REV     = {v:k for k,v in _NAV_KEYS.items()}

_nav_sel = st.radio(
    "nav", _NAV_OPTIONS,
    index=_NAV_OPTIONS.index(_NAV_REV.get(st.session_state.tab, "Input")),
    horizontal=True,
    label_visibility="collapsed",
    key="nav_radio",
)
if _NAV_KEYS[_nav_sel] != st.session_state.tab:
    st.session_state.tab = _NAV_KEYS[_nav_sel]
    st.rerun()


# =============================================================================
#  TAB — INPUT
# =============================================================================
if st.session_state.tab == "input":

    stepbar(st.session_state.step)

    # ── STEP 1 : mode + upload ────────────────────────────────────────────────
    if st.session_state.step == 1:

        m = st.session_state.mode
        # ── Mode selector — pure Streamlit buttons styled as cards via CSS ──────
        st.markdown("""
        <style>
        div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"])
            button[kind="secondary"] {
            height: 88px !important;
            border: 1.5px solid #E5E7EB !important;
            border-radius: 12px !important;
            background: #fff !important;
            color: #111 !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            padding: 8px 4px !important;
            transition: all .18s !important;
            white-space: pre-line !important;
            line-height: 1.5 !important;
        }
        div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"])
            button[kind="secondary"]:hover {
            border-color: #555 !important;
            background: #F9FAFB !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(0,0,0,.08) !important;
        }
        div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"])
            button[kind="primary"] {
            height: 88px !important;
            border: 2.5px solid #111 !important;
            border-radius: 12px !important;
            background: #F9FAFB !important;
            color: #111 !important;
            font-size: 12px !important;
            font-weight: 700 !important;
            padding: 8px 4px !important;
            box-shadow: none !important;
            white-space: pre-line !important;
            line-height: 1.5 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown('<div class="sec-lbl">Metode input</div>', unsafe_allow_html=True)

        _NL = "\n"
        _mc1, _mc2, _mc3 = st.columns(3)
        with _mc1:
            if st.button(
                f"✏️{_NL}Teks Bebas{_NL}Ketik langsung",
                key="m_text", use_container_width=True,
                type="primary" if m == "text" else "secondary",
            ):
                st.session_state.mode   = "text"
                st.session_state.imgs   = []
                st.session_state.pdfraw = b""
                st.rerun()
        with _mc2:
            if st.button(
                f"📄{_NL}Dokumen{_NL}PDF · Foto",
                key="m_photo", use_container_width=True,
                type="primary" if m == "photo" else "secondary",
            ):
                st.session_state.mode   = "photo"
                st.session_state.imgs   = []
                st.session_state.pdfraw = b""
                st.rerun()
        with _mc3:
            if st.button(
                f"🗒️{_NL}Kombinasi{_NL}Dok + catatan",
                key="m_both", use_container_width=True,
                type="primary" if m == "both" else "secondary",
            ):
                st.session_state.mode   = "both"
                st.session_state.imgs   = []
                st.session_state.pdfraw = b""
                st.rerun()

        report_text = ""

        # File uploader
        if m in ("photo", "both"):
            st.markdown(
                '<div class="sec-lbl" style="margin-top:14px">Upload dokumen</div>',
                unsafe_allow_html=True,
            )
            if not _PDF_OK:
                notice("warn",
                    "pypdfium2 belum terinstall — PDF nonaktif. "
                    "Jalankan: <code>pip install pypdfium2==4.30.0</code>")

            ftypes = ["jpg", "jpeg", "png", "webp"] + (["pdf"] if _PDF_OK else [])
            uf = st.file_uploader(
                "Drag & drop atau klik — JPG · PNG · PDF",
                type=ftypes,
                label_visibility="visible",
                key="uf",
            )

            if uf:
                raw_bytes = uf.read()
                if uf.name.lower().endswith(".pdf"):
                    with st.spinner("Membaca PDF..."):
                        try:
                            pages = pdf_images(raw_bytes)
                            st.session_state.imgs   = [to_b64(p) for p in pages]
                            st.session_state.pdfraw = raw_bytes
                            notice("ok", f"PDF berhasil dibaca — {len(pages)} halaman")
                            for i, pg in enumerate(pages, 1):
                                st.image(pg, caption=f"Hal. {i}", use_column_width=True)
                        except Exception as e:
                            notice("err", f"Gagal baca PDF: {e}")
                            st.session_state.imgs   = []
                            st.session_state.pdfraw = b""
                else:
                    try:
                        img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
                        b, mime = to_b64(img)
                        st.session_state.imgs   = [(b, mime)]
                        st.session_state.pdfraw = b""
                        st.image(img, use_column_width=True)
                    except Exception as e:
                        notice("err", f"Gagal baca gambar: {e}")
            else:
                st.session_state.imgs   = []
                st.session_state.pdfraw = b""

        # Text area
        if m in ("text", "both"):
            lbl2 = "Keterangan tambahan" if m == "both" else "Teks laporan"
            st.markdown(
                f'<div class="sec-lbl" style="margin-top:14px">{lbl2}</div>',
                unsafe_allow_html=True,
            )
            report_text = st.text_area(
                "", height=115, label_visibility="collapsed", key="ta",
                placeholder=(
                    "Contoh: Booking Sofitel DC, check-in 6 Mei checkout 9 Mei, "
                    "Itinerary# 73435890401496, 1 room x 3 nights, "
                    "Subtotal paid to Expedia IDR 34.493.666, "
                    "MasterCard 4467, tamu Oki Muraza, Expedia TAAP."
                    if m == "text" else
                    "Info tambahan yang tidak ada di dokumen..."
                ),
            )

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        if st.button("✦  Auto-generate", type="primary", use_container_width=True):
            has_txt = bool(report_text.strip()) if m in ("text", "both") else False
            has_doc = bool(st.session_state.imgs)
            if not has_txt and not has_doc:
                notice("err", "Masukkan teks atau upload dokumen terlebih dahulu.")
            elif not oai_key():
                notice("err", "OpenAI API key belum diisi — buka tab <b>Pengaturan</b>.")
            else:
                with st.spinner("GPT-4o membaca dokumen..."):
                    try:
                        ptxt     = pdf_text(st.session_state.pdfraw)
                        combined = ""
                        if ptxt:
                            combined = (
                                "EXTRACTED PDF TEXT "
                                "(authoritative — use for all numbers and dates):\n" + ptxt
                            )
                        if report_text.strip():
                            combined = (
                                combined + "\n\nREPORTER NOTES:\n" + report_text.strip()
                                if combined else report_text.strip()
                            )
                        parsed, raw = ai_parse(combined, st.session_state.imgs or None)
                        parsed["timestamp_input"] = now_ts()
                        st.session_state.parsed = parsed
                        st.session_state.raw    = raw
                        st.session_state.step   = 3
                        st.rerun()
                    except Exception as e:
                        notice("err", str(e))

        st.button(
            "Reset", type="secondary", use_container_width=True,
            on_click=reset, key="rst",
        )

    # ── STEP 3 : verify + edit ────────────────────────────────────────────────
    elif st.session_state.step == 3:

        p   = st.session_state.parsed
        sup = p.get("supplier", "").lower()
        doc_label = (
            "Expedia TAAP"          if "expedia" in sup else
            "Mitra Tours & Travel"  if "mitra"   in sup else
            p.get("supplier") or "Dokumen"
        )

        notice("info", f"Dokumen: <b>{doc_label}</b> — periksa sebelum menyimpan.")

        # Duplicate pre-check (non-blocking warning)
        try:
            existing = load_rows()
            is_dup, reason, _ = check_duplicate(
                {"booking_id": p.get("booking_id"), "hotel": p.get("hotel"),
                 "checkin": p.get("checkin"), "name": p.get("name"),
                 "room": p.get("room")},
                existing,
            )
            if is_dup:
                notice("warn", f"⚠ Potensi duplikat: {reason}")
        except Exception:
            pass

        st.markdown('<div class="sec-lbl">Hasil ekstraksi AI</div>', unsafe_allow_html=True)
        preview_grid(p)

        with st.expander("Raw JSON dari AI"):
            st.code(st.session_state.raw, language="json")

        st.markdown(
            '<div class="sec-lbl" style="margin-top:4px">Edit & konfirmasi</div>',
            unsafe_allow_html=True,
        )

        with st.form("frm_verify"):
            supplier   = st.text_input("Supplier *",          value=p.get("supplier",   ""))
            booking_id = st.text_input("Booking ID *",        value=p.get("booking_id", ""))

            c1, c2 = st.columns(2)
            booked_on = c1.text_input("Booking Date (YYYY-MM-DD)", value=p.get("booked_on", ""))
            issued_on = c2.text_input("Issued Date (YYYY-MM-DD)",  value=p.get("issued_on", ""))

            hotel = st.text_input("Hotel *", value=p.get("hotel", ""))

            c3, c4 = st.columns(2)
            checkin  = c3.text_input("Check-in * (YYYY-MM-DD)",  value=p.get("checkin",  ""))
            checkout = c4.text_input("Check-out * (YYYY-MM-DD)", value=p.get("checkout", ""))

            qty  = st.text_input(
                "Room × Night",
                value=p.get("qty", ""),
                placeholder="1 room x 3 nights",
            )
            room = st.number_input(
                "Total (Rp)",
                value=int(float(p.get("room") or 0)),
                min_value=0,
                step=1_000,
                help="Nilai dari baris 'Subtotal paid to Expedia' di dokumen",
            )

            c5, c6 = st.columns(2)
            name = c5.text_input("Guest Name *", value=p.get("name", ""))
            card = c6.text_input("Credit Card",  value=p.get("card", ""))

            _ISSUERS = [
                "",
                "Ade Puspitasari",
                "Farras Mahmud",
                "Meijika",
                "Muhammad Geraldi Jagaddhita",
                "Nur Anissa Firda Aulia",
                "Riega Wisudhantara",
                "Rifyal Tumber",
                "Selvy Anggraini",
                "Shaiful Baldy",
                "Veronica Novi Heri",
            ]
            _last = st.session_state.get("last_issuer", "")
            _idx  = _ISSUERS.index(_last) if _last in _ISSUERS else 0
            c7, c8 = st.columns(2)
            issuer = c7.selectbox(
                "Issuer *",
                options=_ISSUERS,
                index=_idx,
                format_func=lambda x: "— Pilih Issuer —" if x == "" else x,
            )
            pic    = c8.text_input("PIC *",
                value=st.session_state.get("last_pic", ""),
                placeholder="Nama penanggung jawab")

            c9, c10 = st.columns(2)
            no_bc         = c9.text_input("No. BC",
                value=p.get("no_bc", ""),
                placeholder="Nomor BC (opsional)")
            nama_kegiatan = c10.text_input("Nama Kegiatan",
                value=p.get("nama_kegiatan", ""),
                placeholder="Nama kegiatan (opsional)")
            notes = st.text_area("Catatan", value=p.get("notes", ""), height=68)

            sb1, sb2 = st.columns(2)
            submit = sb1.form_submit_button(
                "💾  Simpan", type="primary", use_container_width=True)
            back   = sb2.form_submit_button(
                "← Input ulang", type="secondary", use_container_width=True)

            if back:
                st.session_state.step = 1
                st.rerun()

            if submit:
                # Validation
                errs = [lbl for val, lbl in [
                    (supplier,   "Supplier"),
                    (booking_id, "Booking ID"),
                    (hotel,      "Hotel"),
                    (checkin,    "Check-in"),
                    (checkout,   "Check-out"),
                    (name,       "Guest Name"),
                    (issuer,     "Issuer"),
                    (pic,        "PIC"),
                ] if not val.strip()]

                if errs:
                    notice("err", f"Wajib diisi: {', '.join(errs)}")
                else:
                    with st.spinner("Menyimpan ke Google Sheets..."):
                        try:
                            existing = load_rows()
                            is_dup, reason, matched = check_duplicate(
                                {"booking_id": booking_id, "hotel": hotel,
                                 "checkin": checkin, "name": name, "room": room},
                                existing,
                            )

                            if is_dup:
                                notice("err", f"Duplikat terdeteksi: {reason}")
                                st.markdown(
                                    '<div class="sec-lbl" style="margin-top:8px">'
                                    'Data yang sudah ada:</div>',
                                    unsafe_allow_html=True,
                                )
                                card_list_open()
                                for fl, fk, fc in [
                                    ("Booking ID",  "Booking ID",  "#EF4444"),
                                    ("Hotel",       "Hotel",       "#22C55E"),
                                    ("Guest Name",  "Guest Name",  "#EC4899"),
                                    ("Check-in",    "Check-in",    "#3B82F6"),
                                    ("Total (Rp)",  "Total (Rp)",  "#EA580C"),
                                ]:
                                    v = matched.get(fk, "")
                                    field_row(fl,
                                        fmt(v) if fk == "Total (Rp)" else v, fc)
                                card_list_close()
                            else:
                                # remember issuer/pic for next input
                                st.session_state.last_issuer = issuer
                                st.session_state.last_pic    = pic
                                row = {
                                    "timestamp_input": p.get("timestamp_input", ""),
                                    "supplier":  supplier,   "booking_id": booking_id,
                                    "booked_on": booked_on,  "issued_on":  issued_on,
                                    "hotel":     hotel,      "checkin":    checkin,
                                    "qty":       qty,        "room":       room,
                                    "checkout":  checkout,   "name":       name,
                                    "card":      card,       "issuer":     issuer,
                                    "pic":       pic,        "no_bc":      no_bc,
                                    "nama_kegiatan": nama_kegiatan, "notes": notes,
                                }
                                save_row(row)
                                st.session_state.saved = row
                                st.session_state.step  = 4
                                st.rerun()
                        except Exception as e:
                            notice("err", f"Gagal: {e}")

    # ── STEP 4 : success ──────────────────────────────────────────────────────
    elif st.session_state.step == 4:

        d = st.session_state.saved or {}

        st.markdown("""
        <div style="background:#fff;border:1px solid #E5E7EB;border-radius:14px">
          <div class="done-box">
            <div class="done-circle">✓</div>
            <div class="done-title">Tersimpan!</div>
            <div class="done-sub">Data berhasil dicatat ke Google Sheets.</div>
          </div>
        </div>""", unsafe_allow_html=True)

        # ── 2-column metric grid summary ────────────────────────────────────
        st.markdown('<div class="sec-lbl" style="margin-top:14px">Ringkasan</div>',
                    unsafe_allow_html=True)

        _pairs = [
            ("Booking ID",   d.get("booking_id",  "—")),
            ("Supplier",     d.get("supplier",     "—")),
            ("Hotel",        d.get("hotel",        "—")),
            ("Guest Name",   d.get("name",         "—")),
            ("Check-in",     d.get("checkin",      "—")),
            ("Check-out",    d.get("checkout",     "—")),
            ("Room × Night", d.get("qty",          "—")),
            ("Total (Rp)",   fmt(d.get("room", 0))),
            ("Credit Card",  d.get("card",         "—")),
            ("Issuer",       d.get("issuer",       "—")),
            ("PIC",          d.get("pic",          "—")),
        ]
        # Add optional fields only if filled
        if d.get("no_bc"):
            _pairs.append(("No. BC", d.get("no_bc")))
        if d.get("nama_kegiatan"):
            _pairs.append(("Nama Kegiatan", d.get("nama_kegiatan")))

        _g1, _g2 = st.columns(2)
        for _i, (_lbl, _val) in enumerate(_pairs):
            (_g1 if _i % 2 == 0 else _g2).metric(_lbl, _val or "—")

        if st.button("➕  Input Baru", type="primary", use_container_width=True):
            reset()
            st.rerun()

        sid = sheet_id()
        if sid:
            st.link_button(
                "Buka Google Sheets →",
                f"https://docs.google.com/spreadsheets/d/{sid}",
                use_container_width=True,
            )


# =============================================================================
#  TAB — DASHBOARD
# =============================================================================
elif st.session_state.tab == "dashboard":
    import pandas as pd

    st.markdown('<div class="sec-lbl">Ringkasan</div>', unsafe_allow_html=True)

    if st.button("↻  Refresh", type="secondary",
                 use_container_width=True, key="ref"):
        st.cache_resource.clear()
        st.rerun()

    try:
        with st.spinner("Memuat..."):
            rows = load_rows()

        if not rows:
            notice("info", "Belum ada transaksi. Tambahkan melalui tab Input.")
        else:
            df = pd.DataFrame(rows)
            if "Total (Rp)" in df.columns:
                df["Total (Rp)"] = pd.to_numeric(
                    df["Total (Rp)"], errors="coerce").fillna(0)

            tn  = len(df)
            tr  = df["Total (Rp)"].sum() if "Total (Rp)" in df.columns else 0
            avg = tr / tn if tn else 0
            tds = datetime.now().strftime("%d/%m/%Y")
            tdc = int(
                df["Timestamp Input"].astype(str).str.startswith(tds).sum()
            ) if "Timestamp Input" in df.columns else 0

            st.markdown(f"""
            <div class="stat-grid">
              <div class="stat-card">
                <div class="stat-val">{tn}</div>
                <div class="stat-lbl">Total transaksi</div>
              </div>
              <div class="stat-card">
                <div class="stat-val" style="font-size:15px">{fmt(tr)}</div>
                <div class="stat-lbl">Total</div>
              </div>
              <div class="stat-card">
                <div class="stat-val" style="font-size:15px">{fmt(avg)}</div>
                <div class="stat-lbl">Rata-rata</div>
              </div>
              <div class="stat-card">
                <div class="stat-val">{tdc}</div>
                <div class="stat-lbl">Input hari ini</div>
              </div>
            </div>""", unsafe_allow_html=True)

            # ── CC Summary ──────────────────────────────────────────────────
            if "Kartu Kredit" in df.columns and "Total (Rp)" in df.columns:
                _cc_df = df[df["Kartu Kredit"].astype(str).str.strip().ne("")]
                if not _cc_df.empty:
                    st.markdown('<div class="sec-lbl">Kartu Kredit</div>', unsafe_allow_html=True)
                    _cc_grp = (
                        _cc_df.groupby("Kartu Kredit")["Total (Rp)"]
                        .sum().sort_values(ascending=False).reset_index()
                    )
                    _cc_grp.columns = ["label", "val"]
                    _total_cc = _cc_grp["val"].sum()
                    _cc_counts = _cc_df.groupby("Kartu Kredit").size()

                    _rows_html = ""
                    for _i, _r in _cc_grp.iterrows():
                        _pct = _r["val"] / _total_cc * 100 if _total_cc else 0
                        _amt = "Rp {:,.0f}".format(_r["val"]).replace(",", ".")
                        _cnt = int(_cc_counts.get(_r["label"], 0))
                        _bar_w = int(_pct)
                        _rows_html += (
                            f'<div style="padding:10px 0;border-bottom:1px solid #F3F4F6">'
                            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:5px">'
                            f'<span style="font-size:12px;font-weight:600;color:#111">{_r["label"]}</span>'
                            f'<span style="font-size:12px;font-weight:600;color:#111">{_amt}</span>'
                            f'</div>'
                            f'<div style="display:flex;align-items:center;gap:8px">'
                            f'<div style="flex:1;background:#F3F4F6;border-radius:4px;height:4px">'
                            f'<div style="width:{_bar_w}%;background:#111;border-radius:4px;height:4px"></div>'
                            f'</div>'
                            f'<span style="font-size:11px;color:#9CA3AF;white-space:nowrap">{_pct:.1f}% · {_cnt} transaksi</span>'
                            f'</div>'
                            f'</div>'
                        )
                    st.markdown(
                        f'<div style="background:#fff;border:1px solid #E5E7EB;border-radius:10px;padding:4px 14px 4px">'
                        f'{_rows_html}</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown(
                '<div class="sec-lbl">Data transaksi</div>',
                unsafe_allow_html=True,
            )

            srch = st.text_input(
                "", placeholder="🔍  Cari hotel / tamu / booking ID...",
                label_visibility="collapsed", key="srch",
            )
            if srch:
                df = df[df.apply(
                    lambda r: r.astype(str).str.contains(
                        srch, case=False, na=False).any(),
                    axis=1,
                )]

            # ── Force Booking ID as plain string (prevent comma-formatting) ──
            display_df = df.iloc[::-1].reset_index(drop=True).copy()
            if "Booking ID" in display_df.columns:
                display_df["Booking ID"] = display_df["Booking ID"].astype(str)

            # ── Column config: Booking ID as plain text, Total formatted ──────
            import streamlit as _st
            col_cfg = {}
            if "Booking ID" in display_df.columns:
                col_cfg["Booking ID"] = st.column_config.TextColumn(
                    "Booking ID",
                    help="Nomor booking",
                )
            if "Total (Rp)" in display_df.columns:
                col_cfg["Total (Rp)"] = st.column_config.NumberColumn(
                    "Total (Rp)",
                    format="Rp %d",
                )
            if "Room x Night" in display_df.columns:
                col_cfg["Room x Night"] = st.column_config.TextColumn("Room × Night")
            if "Timestamp Input" in display_df.columns:
               col_cfg["Timestamp Input"] = st.column_config.TextColumn("Timestamp")

            st.dataframe(
                display_df,
                use_container_width=True,
                height=360,
                column_config=col_cfg,
                hide_index=True,
            )



    except Exception as e:
        notice("err", str(e))
        notice("info", "Konfigurasi Google Sheets di tab Pengaturan.")


# =============================================================================
#  TAB — RIWAYAT
# =============================================================================
elif st.session_state.tab == "log":

    try:
        with st.spinner("Memuat..."):
            rows = load_rows()

        if not rows:
            notice("info", "Belum ada data transaksi.")
        else:
            import pandas as pd

            df_log = pd.DataFrame(rows)

            # Parse Timestamp Input → sortable datetime
            def _parse_ts(v):
                try:
                    return pd.to_datetime(str(v), dayfirst=True)
                except Exception:
                    return pd.NaT

            df_log["_ts"] = df_log["Timestamp Input"].apply(_parse_ts)
            df_log = df_log.sort_values("_ts", ascending=False).reset_index(drop=True)

            total = len(df_log)
            st.markdown(
                f'<div class="sec-lbl">Riwayat — {total} transaksi</div>',
                unsafe_allow_html=True,
            )

            # ── Table: Timestamp | Booking ID | Issuer ──────────────────────
            display_log = df_log[["Timestamp Input", "Booking ID", "Issuer"]].copy()
            display_log["Booking ID"] = display_log["Booking ID"].astype(str)

            st.dataframe(
                display_log,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Timestamp Input": st.column_config.TextColumn(
                        "Timestamp", width="medium"
                    ),
                    "Booking ID": st.column_config.TextColumn(
                        "Booking ID", width="medium"
                    ),
                    "Issuer": st.column_config.TextColumn(
                        "Issuer", width="medium"
                    ),
                },
            )

    except Exception as e:
        notice("err", str(e))


# =============================================================================
#  TAB — PENGATURAN
# =============================================================================
elif st.session_state.tab == "settings":

    # OpenAI
    st.markdown('<div class="sec-lbl">OpenAI API Key</div>', unsafe_allow_html=True)
    oai_ok = False
    try:
        k = st.secrets["openai"]["api_key"]
        if k and len(k) > 20 and "GANTI" not in k and "PASTE" not in k:
            oai_ok = True
    except Exception:
        pass

    # ── Cek koneksi ───────────────────────────────────────────────────────────
    if st.button("🔍  Cek Koneksi", type="primary", use_container_width=True):
        _results = []
        oai_live = bool(oai_key())
        _results.append((oai_live, "OpenAI", "Terhubung" if oai_live else "Key tidak ditemukan"))
        _sh_check = False
        try:
            s2  = st.secrets["google_sheets"]["sheet_id"]
            em2 = st.secrets["gcp_service_account"]["client_email"]
            if s2 and em2 and "GANTI" not in s2:
                _sh_check = True
        except Exception:
            pass
        if _sh_check:
            try:
                ws()
                _results.append((True, "Google Sheets", "Terhubung"))
            except Exception as e:
                _results.append((False, "Google Sheets", str(e)[:60]))
        else:
            _results.append((False, "Google Sheets", "Belum dikonfigurasi"))
        _results.append((_PDF_OK, "PDF Upload",
            "pypdfium2 aktif" if _PDF_OK else "pypdfium2 tidak terinstall"))

        items = ""
        for ok2, svc, msg in _results:
            clr = "#22C55E" if ok2 else "#EF4444"
            sym = "✓" if ok2 else "✕"
            items += (f'<div class="conn-item">'
                      f'<div class="cdot" style="background:{clr}"></div>'
                      f'<span style="font-weight:600;color:{clr}">{sym} {svc}</span>'
                      f'&ensp;<span style="color:#6B7280">{msg}</span></div>')
        st.markdown(f'<div class="conn-list">{items}</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Status cards ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl">Status Sistem</div>', unsafe_allow_html=True)

    _STATUS_CSS = """
    <style>
    .st-row{display:flex;align-items:center;gap:10px;background:#fff;
        border:1px solid #E5E7EB;border-radius:10px;padding:12px 14px;margin-bottom:8px}
    .st-icon{width:32px;height:32px;border-radius:8px;display:flex;
        align-items:center;justify-content:center;font-size:15px;flex-shrink:0}
    .si-g{background:#F0FDF4} .si-r{background:#FFF1F2} .si-b{background:#EFF6FF}
    .si-y{background:#FFFBEB}
    .st-body{flex:1;min-width:0}
    .st-title{font-size:13px;font-weight:600;color:#111;line-height:1}
    .st-sub{font-size:11px;color:#9CA3AF;margin-top:2px}
    .st-badge{display:inline-flex;align-items:center;font-size:11px;
        font-weight:600;padding:3px 10px;border-radius:20px;flex-shrink:0;white-space:nowrap}
    .bg{background:#F0FDF4;color:#166534;border:1px solid #86EFAC}
    .br{background:#FFF1F2;color:#9F1239;border:1px solid #FECDD3}
    .by{background:#FFFBEB;color:#92400E;border:1px solid #FDE68A}
    .conn-list{background:#fff;border:1px solid #E5E7EB;border-radius:10px;
        overflow:hidden;margin-bottom:12px}
    .conn-item{display:flex;align-items:center;gap:8px;padding:9px 14px;
        border-bottom:1px solid #F9FAFB;font-size:12px}
    .conn-item:last-child{border-bottom:none}
    .cdot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
    .about-box{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:14px 16px}
    .about-ttl{font-size:13px;font-weight:700;color:#111;margin-bottom:10px}
    .about-r{display:flex;gap:8px;margin-bottom:5px}
    .about-k{font-size:11px;font-weight:600;color:#374151;width:65px;flex-shrink:0}
    .about-v{font-size:11px;color:#6B7280}
    </style>
    """
    st.markdown(_STATUS_CSS, unsafe_allow_html=True)

    # OpenAI row
    if oai_ok:
        st.markdown("""<div class="st-row"><div class="st-icon si-g">🤖</div>
        <div class="st-body"><div class="st-title">OpenAI GPT-4o</div>
        <div class="st-sub">API key dikonfigurasi via secrets.toml</div></div>
        <span class="st-badge bg">✓ Aktif</span></div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="st-row"><div class="st-icon si-y">🤖</div>
        <div class="st-body"><div class="st-title">OpenAI GPT-4o</div>
        <div class="st-sub">API key belum dikonfigurasi</div></div>
        <span class="st-badge by">⚠ Belum</span></div>""", unsafe_allow_html=True)
        nk = st.text_input("OpenAI API Key",
            value=st.session_state.oai_key, type="password",
            placeholder="sk-proj-...", label_visibility="collapsed")
        if nk != st.session_state.oai_key:
            st.session_state.oai_key = nk; st.rerun()
        if st.session_state.oai_key:
            notice("ok", "Key aktif untuk sesi ini.")

    # Google Sheets row
    sh_ok = False
    try:
        s  = st.secrets["google_sheets"]["sheet_id"]
        em = st.secrets["gcp_service_account"]["client_email"]
        if s and em and "GANTI" not in s:
            sh_ok = True
    except Exception:
        pass

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
        notice("warn", "Isi <code>.streamlit/secrets.toml</code> sesuai README.")
        ns = st.text_input("Sheet ID", value=st.session_state.sheet_id,
            label_visibility="collapsed", placeholder="1nvgMCmo...")
        if ns != st.session_state.sheet_id:
            st.session_state.sheet_id = ns

    # PDF row
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
        notice("err", "Jalankan: <code>pip install pypdfium2==4.30.0</code>")

    # ── Tentang ───────────────────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl" style="margin-top:14px">Tentang Aplikasi</div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div class="about-box">
      <div class="about-ttl">AI CC Reporting System v5</div>
      <div class="about-r"><div class="about-k">Input</div>
        <div class="about-v">PDF · JPG · PNG · Teks bebas</div></div>
      <div class="about-r"><div class="about-k">Output</div>
        <div class="about-v">Google Sheets — 15 kolom</div></div>
      <div class="about-r"><div class="about-k">Dokumen</div>
        <div class="about-v">Expedia TAAP · Mitra Tours · Invoice hotel</div></div>
      <div class="about-r"><div class="about-k">Model AI</div>
        <div class="about-v">GPT-4o (OpenAI)</div></div>
    </div>""", unsafe_allow_html=True)

# =============================================================================
#  FOOTER — shown on all tabs
# =============================================================================
st.markdown("""
<div style="
    margin-top:32px;
    padding:16px 0 8px;
    border-top:1px solid #E5E7EB;
    text-align:center;
    font-size:11px;
    color:#9CA3AF;
    line-height:1.8;
">
  Built with ❤️ &nbsp;·&nbsp; AI CC Reporting System v5<br>
  <a href="https://www.linkedin.com/in/rifyalt" target="_blank"
     style="color:#0A66C2;font-weight:600;text-decoration:none;
            display:inline-flex;align-items:center;gap:4px;margin-top:4px">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="#0A66C2">
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
