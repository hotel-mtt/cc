"""
Mitra Tours & Travel — Visitor Appointment System
Redesign: Attractive Mobile-First UI — FIXED VERSION
Warna: #1BA0E2 #1494C6 #0D7FCC #F0F0F0 #ff5e1f #DEDEDE

Bugs Fixed:
1. Session buttons showing as duplicate text below cards
   → Removed CSS overlay approach; now uses pure st.button with CSS that
     hides default button text and positions it correctly, OR uses a
     simpler pattern: render the visual card INSIDE the button container
     by using st.markdown + st.button side by side with a key-driven approach.
     Final solution: render HTML card visuals separately, then use
     st.button with label_visibility tricks. Actually cleanest fix:
     wrap the entire sess-card in a container, render the HTML card,
     then render a REAL st.button below but style it to look like part
     of the card via CSS that hides its own text. Since Streamlit always
     renders buttons below HTML, the only reliable fix is to NOT use
     raw HTML for the clickable session cards, and instead style
     st.button natively via CSS to look like the card design.

2. _prev_date_key rerun loop → fixed by removing the nested rerun trigger

3. Double submit guard → added st.session_state.submitting flag
"""

import streamlit as st
import requests, random, string, re
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="Kunjungan Sales — Mitra Tours",
    page_icon="📅",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── CONFIG ─────────────────────────────────────────────────────────────────────
GAS_ENDPOINT    = "https://script.google.com/macros/s/AKfycbz78iwrv1FiIHqpqbA4dX6sQVzcfO4UodJ3BhW4bLH_7zLA_c4wMmXpuhHSGC5yiE6Pww/exec"
SHEET_ID        = "1AQz-w3sLjGVdOsneDmdTFHFW6Nx7Z337Kjw2zzqFoXI"
API_KEY         = "AIzaSyA1Mau8yZxao0MD5Mx_Dt027EuMbrUN9oo"
SHEET_NAME      = "Sheet1"
NOTIF_EMAIL     = "hotel@mitratour.com"
SHEETS_READ_URL = (
    f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}"
    f"/values/{SHEET_NAME}?key={API_KEY}"
)

DATES = [
    {"key":"6 Mei 2026",  "label":"Selasa, 6 Mei 2026",  "day":"6",  "mon":"Mei"},
    {"key":"13 Mei 2026", "label":"Selasa, 13 Mei 2026", "day":"13", "mon":"Mei"},
    {"key":"20 Mei 2026", "label":"Selasa, 20 Mei 2026", "day":"20", "mon":"Mei"},
    {"key":"27 Mei 2026", "label":"Selasa, 27 Mei 2026", "day":"27", "mon":"Mei"},
    {"key":"2 Jun 2026",  "label":"Selasa, 2 Jun 2026",  "day":"2",  "mon":"Jun"},
    {"key":"9 Jun 2026",  "label":"Selasa, 9 Jun 2026",  "day":"9",  "mon":"Jun"},
    {"key":"16 Jun 2026", "label":"Selasa, 16 Jun 2026", "day":"16", "mon":"Jun"},
    {"key":"23 Jun 2026", "label":"Selasa, 23 Jun 2026", "day":"23", "mon":"Jun"},
    {"key":"30 Jun 2026", "label":"Selasa, 30 Jun 2026", "day":"30", "mon":"Jun"},
    {"key":"7 Jul 2026",  "label":"Selasa, 7 Jul 2026",  "day":"7",  "mon":"Jul"},
    {"key":"14 Jul 2026", "label":"Selasa, 14 Jul 2026", "day":"14", "mon":"Jul"},
    {"key":"21 Jul 2026", "label":"Selasa, 21 Jul 2026", "day":"21", "mon":"Jul"},
    {"key":"28 Jul 2026", "label":"Selasa, 28 Jul 2026", "day":"28", "mon":"Jul"},
    {"key":"4 Agt 2026",  "label":"Selasa, 4 Agt 2026",  "day":"4",  "mon":"Agt"},
    {"key":"11 Agt 2026", "label":"Selasa, 11 Agt 2026", "day":"11", "mon":"Agt"},
    {"key":"18 Agt 2026", "label":"Selasa, 18 Agt 2026", "day":"18", "mon":"Agt"},
    {"key":"25 Agt 2026", "label":"Selasa, 25 Agt 2026", "day":"25", "mon":"Agt"},
]

SESSIONS = [
    {"id":"P1","value":"09.00-10.00 WIB","label":"09.00 – 10.00 WIB","period":"Pagi"},
    {"id":"P2","value":"10.00-11.00 WIB","label":"10.00 – 11.00 WIB","period":"Pagi"},
    {"id":"S1","value":"13.30-14.30 WIB","label":"13.30 – 14.30 WIB","period":"Siang"},
]

HOTEL_BRANDS = [
    "",
    "Accor","Aman Resorts","Archipelago International","ARTOTEL Group",
    "Aryaduta","Ascott Limited","Azana Hotels","Banyan Group Limited",
    "Best Western Hotels","Cross Hotels & Resorts","Dafam Hotel Management",
    "Dusit International","Four Seasons Hotels and Resorts","Hilton Worldwide",
    "Horison Hotels Group","Hotel Indonesia Group","Hyatt Hotels Corporation",
    "IHG Hotels & Resorts","Jambuluwuk Hotels & Resorts","Jumeirah","Kempinski",
    "Mandarin Oriental Hotel Group","Marriott International","Meliá Hotels International",
    "Minor Hotels","Oberoi Group","Pan Pacific Hotels and Resorts",
    "Parador Hotels & Resorts","Radisson Hotel Group",
    "Santika Indonesia Hotels & Resorts","Shangri-La Hotels and Resorts",
    "Swiss-Belhotel International","The Ascott Limited",
    "Waringin Hospitality Hotel Group","Wyndham Hotels & Resorts",
    "Independen / Tidak Berantai","Lainnya",
]

TUJUAN_OPTIONS = [
    "Perkenalan Hotel",
    "Presentasi Produk / Fasilitas",
    "Corporate Rate / Contract Rate",
    "Promo / Special Offer",
    "Kerja Sama Partnership",
    "Follow Up Existing Business",
]

TUJUAN_BADGES = {
    "Perkenalan Hotel":             "Intro",
    "Presentasi Produk / Fasilitas":"Produk",
    "Corporate Rate / Contract Rate":"Rate",
    "Promo / Special Offer":        "Promo",
    "Kerja Sama Partnership":       "Partner",
    "Follow Up Existing Business":  "Follow Up",
}

# ── DATA LAYER ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=20)
def _fetch_cached():
    try:
        r = requests.get(SHEETS_READ_URL, timeout=10)
        r.raise_for_status()
        rows = r.json().get("values", [])[1:]
        booked = {}
        for row in rows:
            while len(row) < 16:
                row.append("")
            if row[15].lower().strip() in ("ditolak","dibatalkan"):
                continue
            dk = re.sub(r"\s*\(.*?\)", "", row[11].strip()).strip()
            sv = row[12].strip()
            if dk and sv:
                key = f"{dk}|{sv}"
                booked[key] = booked.get(key, 0) + 1
        return booked, ""
    except Exception as e:
        return {}, str(e)

def fetch_booked():
    b, err = _fetch_cached()
    if err:
        st.toast(f"Gagal memuat jadwal: {err}", icon="⚠️")
    return b

def is_booked(b, dk, sv):
    return b.get(f"{dk}|{sv}", 0) >= 1

def get_alts(b, edk, esv, n=3):
    out = []
    for d in DATES:
        for s in SESSIONS:
            if d["key"] == edk and s["value"] == esv:
                continue
            if not is_booked(b, d["key"], s["value"]):
                out.append({
                    "date_key":   d["key"],
                    "date_label": d["label"],
                    "sess_value": s["value"],
                    "sess_label": s["label"],
                })
                if len(out) >= n:
                    return out
    return out

def gen_ref():
    return "SV-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))

def save_to_gas(payload):
    import json as _j
    payload["notifEmail"] = NOTIF_EMAIL
    headers = {"Content-Type": "application/json"}
    body    = _j.dumps(payload)
    ref     = payload.get("ref", "")
    try:
        resp = requests.post(GAS_ENDPOINT, data=body, headers=headers,
                             allow_redirects=True, timeout=30)
        raw = resp.text.strip()
        if raw.startswith("{"):
            r = _j.loads(raw)
            if r.get("success"):
                return True, r.get("ref", ref)
            if r.get("error") in ("Jadwal_TAKEN", "SLOT_TAKEN"):
                return False, "Jadwal_TAKEN"
            if "duplicate" in r.get("message","").lower():
                return True, ref
            return False, r.get("message", r.get("error", "Unknown"))
        if resp.status_code in (200, 201, 302):
            return True, ref
        return False, f"HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return False, "Timeout — coba lagi"
    except Exception as e:
        return False, str(e)

def valid_email(e):
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", e.strip()))

def valid_phone(p):
    digits = re.sub(r"[\s\-\(\)]", "", p)
    return bool(re.match(r"^(\+62|62|0)\d{8,13}$", digits))

# ── SESSION STATE ──────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "step": 1,
        "sel_date_key": None, "sel_date_label": None,
        "sel_sess_value": None, "sel_sess_label": None,
        "nama_hotel": "", "alamat_hotel": "", "brand_hotel": "",
        "nama_pic": "", "jabatan": "", "no_hp": "", "email": "",
        "peserta": "1 orang", "tujuan": [],
        "durasi": "30 Menit", "catatan": "",
        "ref_number": "", "submitted_ref": "",
        "conflict_type": None, "conflict_msg": "", "alternatives": [],
        "submitting": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ── MASTER CSS ─────────────────────────────────────────────────────────────────
def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800;900&family=Nunito+Sans:wght@400;500;600;700&display=swap');

/* ── VARIABLES ── */
:root {
  --c1: #1BA0E2;
  --c2: #1494C6;
  --c3: #0D7FCC;
  --bg: #F0F0F0;
  --border: #DEDEDE;
  --accent: #ff5e1f;
  --accent-dk: #e04c10;
  --white: #ffffff;
  --text: #1a1f2e;
  --muted: #6b7280;
  --light: #F7F9FC;
  --danger: #ef4444;
  --success: #10b981;
  --r: 14px;
  --r-sm: 10px;
  --r-xs: 7px;
  --shadow: 0 2px 12px rgba(13,127,204,0.10);
  --shadow-md: 0 6px 24px rgba(13,127,204,0.16);
}

/* ── RESET ── */
*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] {
  font-family: 'Nunito Sans', sans-serif !important;
  -webkit-font-smoothing: antialiased;
  background: var(--bg) !important;
}
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton,[data-testid="stToolbar"],[data-testid="collapsedControl"]{ display:none!important; }
.main { background: var(--bg) !important; }
.main .block-container {
  padding: 0 0 100px !important;
  max-width: 460px !important;
  margin: 0 auto !important;
}

/* ── TOPBAR ── */
.topbar {
  background: var(--white);
  border-bottom: 2px solid var(--border);
  padding: 0 18px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 200;
}
.topbar-logo {
  display: flex;
  align-items: center;
  gap: 9px;
}
.topbar-live {
  display: flex; align-items: center; gap: 5px;
  background: #ecfdf5;
  border: 1px solid #6ee7b7;
  border-radius: 20px;
  padding: 4px 10px;
  font-size: 10px;
  font-weight: 700;
  color: #059669;
  letter-spacing: 0.2px;
}
.pulse-dot {
  width: 6px; height: 6px;
  background: #10b981;
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%,100% { opacity:1; transform:scale(1); }
  50%      { opacity:.4; transform:scale(.8); }
}

/* ── HERO HEADER ── */
.hero {
  background: linear-gradient(145deg, var(--c1) 0%, var(--c3) 100%);
  padding: 24px 20px 40px;
  position: relative;
  overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute; top: -30px; right: -30px;
  width: 130px; height: 130px;
  border-radius: 50%;
  background: rgba(255,255,255,0.07);
}
.hero::after {
  content: '';
  position: absolute; bottom: -20px; left: 50%;
  width: 80px; height: 80px;
  border-radius: 50%;
  background: rgba(255,255,255,0.05);
}
.hero-step-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255,255,255,0.18);
  border: 1px solid rgba(255,255,255,0.28);
  border-radius: 20px;
  padding: 4px 12px;
  font-size: 10px;
  font-weight: 700;
  color: rgba(255,255,255,0.9);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-bottom: 12px;
}
.hero-title {
  font-family: 'Nunito', sans-serif;
  font-size: 22px;
  font-weight: 900;
  color: #fff;
  line-height: 1.18;
  margin-bottom: 5px;
  letter-spacing: -0.5px;
}
.hero-sub {
  font-size: 12.5px;
  color: rgba(255,255,255,0.72);
  line-height: 1.55;
}

/* ── STEP TRACKER ── */
.step-track {
  display: flex;
  align-items: center;
  background: var(--white);
  margin: -20px 14px 0;
  border-radius: var(--r);
  padding: 14px 12px;
  box-shadow: var(--shadow-md);
  position: relative;
  z-index: 10;
}
.st-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  position: relative;
}
.st-item:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 13px;
  left: 60%;
  width: 80%;
  height: 2px;
  background: var(--border);
}
.st-item.done:not(:last-child)::after,
.st-item.active:not(:last-child)::after {
  background: linear-gradient(90deg, var(--c1), var(--border));
}
.st-dot {
  width: 26px; height: 26px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px;
  font-weight: 800;
  border: 2px solid var(--border);
  color: var(--muted);
  background: var(--white);
  transition: all 0.25s;
  z-index: 1;
}
.st-item.done .st-dot {
  background: var(--c1);
  border-color: var(--c1);
  color: white;
  font-size: 12px;
}
.st-item.active .st-dot {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
  box-shadow: 0 0 0 4px rgba(255,94,31,0.18);
}
.st-label {
  font-size: 9px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.st-item.done .st-label  { color: var(--c2); }
.st-item.active .st-label { color: var(--accent); }

/* ── CONTENT WRAP ── */
.content { padding: 16px 14px 0; }

/* ── SECTION HEADING ── */
.sec-head {
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--muted);
  margin: 18px 0 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.sec-head::after {
  content: '';
  flex: 1;
  height: 1.5px;
  background: var(--border);
  border-radius: 1px;
}

/* ── INFO BOX ── */
.ibox {
  background: rgba(27,160,226,0.07);
  border: 1.5px solid rgba(27,160,226,0.22);
  border-radius: var(--r-sm);
  padding: 11px 14px;
  font-size: 12px;
  color: var(--c3);
  line-height: 1.6;
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.ibox-icon { font-size: 13px; flex-shrink: 0; margin-top: 1px; }

/* ── ALERT ── */
.alert {
  border-radius: var(--r-sm);
  padding: 11px 14px;
  font-size: 12.5px;
  line-height: 1.55;
  margin-bottom: 12px;
  display: flex; gap: 9px; align-items: flex-start;
  font-weight: 500;
}
.alert-error   { background:#fef2f2; border:1.5px solid #fca5a5; color:#991b1b; }
.alert-success { background:#ecfdf5; border:1.5px solid #6ee7b7; color:#065f46; }
.alert-warn    { background:#fff7ed; border:1.5px solid #fed7aa; color:#92400e; }

/* ── SESSION BUTTONS — KEY FIX ──
   Each session is rendered as a styled st.button.
   We style the button itself to look like a card.
   The button label carries all the visual info.
   We use data-session-* approach via CSS targeting.
*/

/* Session card buttons — available state */
/* ── SESSION BUTTONS — Opsi A card style ── */
div[data-testid="stButton"]:has(> button[data-testid^="sb_"]) {
  margin-bottom: 6px !important;
}
div[data-testid="stButton"] > button[data-testid^="sb_"] {
  width: 100% !important;
  background: #ffffff !important;
  border: 1.5px solid #DEDEDE !important;
  border-radius: 10px !important;
  padding: 0 14px !important;
  min-height: 50px !important;
  cursor: pointer !important;
  box-shadow: none !important;
  transition: border-color 0.15s, background 0.15s !important;
  display: flex !important;
  align-items: center !important;
  justify-content: flex-start !important;
  text-align: left !important;
}
div[data-testid="stButton"] > button[data-testid^="sb_"]:hover {
  border-color: #1BA0E2 !important;
  background: rgba(27,160,226,0.04) !important;
}
div[data-testid="stButton"] > button[data-testid^="sb_"] > div,
div[data-testid="stButton"] > button[data-testid^="sb_"] > div > p {
  display: none !important;
}
/* sb_ button styles handled per-session inline */

/* ── REVIEW TABLE ── */
.rev-card {
  background: var(--white);
  border: 2px solid var(--border);
  border-radius: var(--r);
  overflow: hidden;
  margin-bottom: 14px;
}
.rev-group-head {
  background: linear-gradient(90deg, rgba(27,160,226,0.08), transparent);
  border-bottom: 1.5px solid var(--border);
  padding: 8px 14px;
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.7px;
  color: var(--c2);
  display: flex;
  align-items: center;
  gap: 6px;
}
.rev-row { display:flex; border-bottom:1px solid var(--bg); }
.rev-row:last-child { border-bottom:none; }
.rev-lbl {
  width: 82px; flex-shrink:0;
  padding: 9px 12px;
  font-size: 11px;
  font-weight: 700;
  color: var(--muted);
  border-right: 1px solid var(--bg);
}
.rev-val {
  padding: 9px 13px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  flex: 1;
  word-break: break-word;
  line-height: 1.45;
}
.rev-val.hl { color: var(--c3); font-weight: 800; }

/* ── SUCCESS SCREEN ── */
.succ-wrap { padding: 20px 14px; }
.succ-hero {
  background: linear-gradient(145deg, var(--c1), var(--c3));
  border-radius: var(--r);
  padding: 28px 20px;
  text-align: center;
  position: relative;
  overflow: hidden;
  margin-bottom: 14px;
  box-shadow: var(--shadow-md);
}
.succ-hero::before {
  content:''; position:absolute; top:-20px; right:-20px;
  width:100px; height:100px; border-radius:50%;
  background:rgba(255,255,255,0.07);
}
.succ-ring {
  width: 64px; height: 64px;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
  border: 3px solid rgba(255,255,255,0.5);
  margin: 0 auto 14px;
  display: flex; align-items: center; justify-content: center;
  font-size: 26px; color: white;
  animation: pop 0.5s cubic-bezier(0.175,0.885,0.32,1.275);
}
@keyframes pop {
  0%   { transform:scale(0); opacity:0; }
  100% { transform:scale(1); opacity:1; }
}
.succ-title {
  font-family: 'Nunito', sans-serif;
  font-size: 20px; font-weight: 900;
  color: white; margin-bottom: 5px;
  letter-spacing: -0.4px;
}
.succ-sub { font-size: 12px; color: rgba(255,255,255,0.78); line-height: 1.65; }
.ref-tag {
  display: inline-block;
  font-family: 'Nunito', sans-serif;
  font-size: 17px; font-weight: 900;
  color: white;
  background: rgba(255,255,255,0.18);
  border: 1.5px solid rgba(255,255,255,0.35);
  border-radius: var(--r-xs);
  padding: 7px 18px;
  letter-spacing: 2.5px;
  margin: 12px 0 6px;
}
.ref-hint { font-size:10px; color:rgba(255,255,255,0.55); }
.succ-grid {
  display: grid; grid-template-columns:1fr 1fr;
  gap: 8px; margin-bottom: 14px;
}
.succ-item {
  background: var(--white);
  border: 2px solid var(--border);
  border-radius: var(--r-xs);
  padding: 11px 13px;
}
.succ-lbl { font-size:9px; font-weight:800; text-transform:uppercase; letter-spacing:0.5px; color:var(--muted); margin-bottom:3px; }
.succ-val { font-size:13px; font-weight:700; color:var(--text); }

/* ── GLOBAL BUTTONS ── */
div[data-testid="stButton"] > button {
  font-family: 'Nunito', sans-serif !important;
  font-weight: 800 !important;
  font-size: 14px !important;
  border-radius: var(--r-xs) !important;
  padding: 12px 18px !important;
  width: 100% !important;
  transition: all 0.18s !important;
  letter-spacing: -0.2px !important;
}
div[data-testid="stButton"] > button[kind="primary"] {
  background: linear-gradient(135deg, var(--c1), var(--c3)) !important;
  border: none !important;
  color: white !important;
  box-shadow: 0 4px 14px rgba(13,127,204,0.3) !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 20px rgba(13,127,204,0.4) !important;
}
div[data-testid="stButton"] > button[kind="secondary"] {
  background: var(--white) !important;
  border: 2px solid var(--border) !important;
  color: var(--muted) !important;
}
div[data-testid="stButton"] > button[kind="secondary"]:hover {
  border-color: var(--c1) !important;
  color: var(--c1) !important;
}

/* ── PESERTA & DURASI RADIO ── */
div[data-testid="stRadio"] > div {
  gap: 6px !important;
  flex-wrap: wrap !important;
}
div[data-testid="stRadio"] > div > label {
  border: 2px solid var(--border) !important;
  border-radius: var(--r-xs) !important;
  padding: 8px 14px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  background: var(--white) !important;
  cursor: pointer !important;
  transition: all 0.15s !important;
  color: var(--text) !important;
}
div[data-testid="stRadio"] > div > label:has(input:checked) {
  border-color: var(--c1) !important;
  background: rgba(27,160,226,0.10) !important;
  color: var(--c3) !important;
}
div[data-testid="stRadio"] > div > label > div:first-child { display:none !important; }
div[data-testid="stRadio"] > div > label > div:last-child p {
  font-size: 13px !important;
  font-weight: 600 !important;
  color: inherit !important;
  margin: 0 !important;
}

/* ── ACCENT SUBMIT BUTTON (Step 4 only) ── */
.submit-accent-wrap div[data-testid="stButton"] > button {
  background: linear-gradient(135deg, var(--accent), var(--accent-dk)) !important;
  border: none !important;
  color: white !important;
  box-shadow: 0 4px 14px rgba(255,94,31,0.35) !important;
  font-size: 15px !important;
  padding: 13px !important;
}
.submit-accent-wrap div[data-testid="stButton"] > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 22px rgba(255,94,31,0.45) !important;
}

/* ── FOOTER ── */
.footer { text-align:center; padding:20px 0 32px; font-size:11px; color:#bbb; letter-spacing:0.3px; }
.footer span { color:var(--c1); font-weight:700; }

/* ── SPACING OVERRIDES ── */
div[data-testid="stVerticalBlock"] { gap: 6px !important; }

/* Tujuan toggle rows — zero gap between HTML card and invisible button */
div[data-testid="stButton"]:has(button[data-testid^="tuj_"]) + div[data-testid="stButton"]:has(button[data-testid^="tuj_"]) {
  margin-top: 0 !important;
}
</style>
""", unsafe_allow_html=True)

# ── COMPONENT HELPERS ──────────────────────────────────────────────────────────
def render_topbar():
    st.markdown("""
<div class="topbar">
  <div class="topbar-logo">
    <img src="https://mitratour.com/wp-content/uploads/2019/09/LOGO-MITRA-Converted-Copy-min.png"
         alt="Mitra Tours & Travel"
         style="height:36px;width:auto;object-fit:contain;display:block;" />
  </div>
  <div class="topbar-live">
    <div class="pulse-dot"></div>
    Sistem Aktif
  </div>
</div>""", unsafe_allow_html=True)

STEP_META = {
    1: ("📅", "Pilih Jadwal",  "Tentukan tanggal & sesi kunjungan"),
    2: ("🏨", "Data Hotel",    "Informasi properti yang dikunjungi"),
    3: ("👤", "Data Kontak",   "PIC & tujuan kunjungan"),
    4: ("✅", "Review & Kirim","Periksa & konfirmasi permohonan"),
    5: ("🎉", "Selesai",       "Permohonan berhasil terkirim"),
}

def render_hero(step):
    icon, title, sub = STEP_META.get(step, ("📅","Kunjungan",""))
    step_labels = ["Jadwal","Hotel","Kontak","Kirim"]
    tag_label   = step_labels[step-1] if step <= 4 else "Selesai"
    st.markdown(f"""
<div class="hero">
  <div class="hero-step-tag">
    <span>{icon}</span>
    Langkah {min(step,4)} dari 4 · {tag_label}
  </div>
  <div class="hero-title">{title}</div>
  <div class="hero-sub">{sub}</div>
</div>""", unsafe_allow_html=True)

def render_step_tracker(cur):
    labels = ["Jadwal","Hotel","Kontak","Kirim"]
    items  = ""
    for i, lbl in enumerate(labels, 1):
        if   i < cur:  cls = "done";   dot_content = "✓"
        elif i == cur: cls = "active";  dot_content = str(i)
        else:          cls = "";        dot_content = str(i)
        items += f"""
<div class="st-item {cls}">
  <div class="st-dot">{dot_content}</div>
  <div class="st-label">{lbl}</div>
</div>"""
    st.markdown(f'<div class="step-track">{items}</div>', unsafe_allow_html=True)

def sel_banner():
    if st.session_state.sel_date_key and st.session_state.sel_sess_value:
        st.markdown(f"""
<div class="sel-banner">
  <div class="sb-info">
    <div class="sb-tag">📅 Jadwal Dipilih</div>
    <div class="sb-val">{st.session_state.sel_date_label} &nbsp;·&nbsp; {st.session_state.sel_sess_label}</div>
  </div>
  <div class="sb-check">✓</div>
</div>""", unsafe_allow_html=True)

def ibox(txt):
    st.markdown(f"""
<div class="ibox">
  <span class="ibox-icon">ℹ️</span>
  <div>{txt}</div>
</div>""", unsafe_allow_html=True)

def alert(msg, kind="warn", icon="⚠️"):
    st.markdown(f"""
<div class="alert alert-{kind}">
  <span style="font-size:14px;flex-shrink:0">{icon}</span>
  <div>{msg}</div>
</div>""", unsafe_allow_html=True)

def sec(txt):
    st.markdown(f'<div class="sec-head">{txt}</div>', unsafe_allow_html=True)

# ── STEP 1 ─────────────────────────────────────────────────────────────────────
def render_step1():
    booked = fetch_booked()

    st.markdown('<div class="content">', unsafe_allow_html=True)
    ibox("Kunjungan dilakukan setiap <strong>Selasa</strong> · 1 hotel per sesi · Pilih tanggal lalu pilih jam")

    # ── Conflict alerts
    if st.session_state.conflict_type == "blocking":
        alert(f"<strong>Jadwal penuh!</strong> {st.session_state.conflict_msg}", kind="error", icon="❌")
        if st.session_state.alternatives:
            st.caption("Jadwal alternatif tersedia:")
            for alt in st.session_state.alternatives:
                if st.button(
                    f"→ {alt['date_label']} · {alt['sess_label']}",
                    key=f"alt_{alt['date_key']}_{alt['sess_value']}",
                ):
                    st.session_state.sel_date_key   = alt["date_key"]
                    st.session_state.sel_date_label = alt["date_label"]
                    st.session_state.sel_sess_value = alt["sess_value"]
                    st.session_state.sel_sess_label = alt["sess_label"]
                    st.session_state.conflict_type  = "ok"
                    st.session_state.conflict_msg   = f"{alt['date_label']} · {alt['sess_label']} tersedia."
                    st.rerun()

    elif st.session_state.conflict_type == "ok":
        alert(st.session_state.conflict_msg, kind="success", icon="✅")

    # ── Date selector ──
    sec("Pilih Tanggal Kunjungan")

    date_opts = ["— Pilih tanggal —"]
    date_map  = {}
    for dt in DATES:
        free = sum(1 for s in SESSIONS if not is_booked(booked, dt["key"], s["value"]))
        suf  = " ✕ Penuh" if free == 0 else (f" · {free} sesi" if free < len(SESSIONS) else "")
        opt  = dt["label"] + suf
        date_opts.append(opt)
        date_map[opt] = dt

    # Find current selection index
    cur_opt = None
    if st.session_state.sel_date_key:
        for lbl, dt in date_map.items():
            if dt["key"] == st.session_state.sel_date_key:
                cur_opt = lbl; break
    cur_idx = date_opts.index(cur_opt) if cur_opt in date_opts else 0

    chosen_label = st.selectbox(
        "Tanggal", options=date_opts, index=cur_idx,
        label_visibility="collapsed", key="dd_tanggal"
    )
    chosen_dt = date_map.get(chosen_label)

    # ── FIX BUG 2: Date change detection without rerun loop ──
    # Only update state if user picked a DIFFERENT date; don't rerun just for sync
    if chosen_dt:
        if chosen_dt["key"] != st.session_state.sel_date_key:
            # Date changed — reset session selection
            st.session_state.sel_date_key   = chosen_dt["key"]
            st.session_state.sel_date_label = chosen_dt["label"]
            st.session_state.sel_sess_value = None
            st.session_state.sel_sess_label = None
            st.session_state.conflict_type  = None
            st.rerun()
    else:
        # Placeholder selected — clear date if one was previously set
        if st.session_state.sel_date_key is not None:
            st.session_state.sel_date_key   = None
            st.session_state.sel_date_label = None
            st.session_state.sel_sess_value = None
            st.session_state.sel_sess_label = None
            st.session_state.conflict_type  = None
            st.rerun()

    # ── Session slots ──
    if chosen_dt:
        dk = chosen_dt["key"]
        sec("Pilih Sesi Waktu")

        # ── Session rendering: HTML card + invisible overlapping button ──
        # All cards rendered first as a group, then buttons overlap via CSS
        # Each card uses a wrapper container with consistent height

        CARD_H = 52  # px — fixed height for card + button alignment

        # One-time CSS for this render
        sess_css = "<style>"
        for sess in SESSIONS:
            sid = f"sb_{dk}_{sess['id']}"
            sess_css += (
                f"div[data-testid='stButton']:has(>button[data-testid='{sid}']){{"
                f"margin-top:-{CARD_H}px!important;"
                f"margin-bottom:6px!important;"
                f"position:relative!important;z-index:10!important;}}"
                f"div[data-testid='stButton']>button[data-testid='{sid}']{{"
                f"opacity:0!important;height:{CARD_H}px!important;"
                f"min-height:{CARD_H}px!important;width:100%!important;"
                f"border:none!important;background:transparent!important;"
                f"box-shadow:none!important;padding:0!important;"
                f"border-radius:10px!important;"
                f"cursor:{'not-allowed' if is_booked(booked, dk, sess['value']) else 'pointer'}!important;"
                f"pointer-events:{'none' if is_booked(booked, dk, sess['value']) else 'auto'}!important;"
                f"outline:none!important;box-shadow:none!important;}}"
                f"div[data-testid='stButton']>button[data-testid='{sid}']:focus{{"
                f"outline:none!important;box-shadow:none!important;background:transparent!important;}}"
                f"div[data-testid='stButton']>button[data-testid='{sid}']:active{{"
                f"outline:none!important;box-shadow:none!important;background:transparent!important;transform:none!important;}}"
                f"div[data-testid='stButton']>button[data-testid='{sid}']:focus-visible{{"
                f"outline:none!important;box-shadow:none!important;}}"
            )
        sess_css += "</style>"
        st.markdown(sess_css, unsafe_allow_html=True)

        for i, sess in enumerate(SESSIONS):
            taken    = is_booked(booked, dk, sess["value"])
            selected = (
                st.session_state.sel_sess_value == sess["value"]
                and st.session_state.sel_date_key == dk
            )
            sid = f"sb_{dk}_{sess['id']}"

            radio_bg   = "#1BA0E2" if selected else "#ffffff"
            radio_brd  = "#1BA0E2" if selected else "#DEDEDE"
            period_bg  = "#1BA0E2" if selected else ("#fee2e2" if taken else "#F0F0F0")
            period_col = "#ffffff" if selected else ("#ef4444" if taken else "#6b7280")
            period_lbl = "Penuh"   if taken else sess["period"]
            time_col   = "#185FA5" if selected else ("#9ca3af" if taken else "#1a1f2e")
            time_dec   = "line-through" if taken else "none"
            status_txt = "Penuh"   if taken else ("Dipilih" if selected else "Tersedia")
            status_col = "#ef4444" if taken else ("#1BA0E2" if selected else "#9ca3af")
            row_border = "#1BA0E2" if selected else "#DEDEDE"
            row_bg     = "rgba(27,160,226,0.07)" if selected else ("#F7F7F7" if taken else "#ffffff")
            op_val     = "0.42" if taken else "1"
            radio_inner = "<div style='width:7px;height:7px;border-radius:50%;background:#fff;'></div>" if selected else ""

            # Visual card — fixed height, margin-bottom negative pulls button up
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:12px;"
                f"padding:0 14px;height:{CARD_H}px;"
                f"border-radius:10px;border:1.5px solid {row_border};"
                f"background:{row_bg};opacity:{op_val};"
                f"margin-bottom:-{CARD_H}px;position:relative;z-index:1;"
                f"pointer-events:none;box-sizing:border-box;'>"
                f"<div style='width:18px;height:18px;border-radius:50%;flex-shrink:0;"
                f"border:1.5px solid {radio_brd};background:{radio_bg};"
                f"display:flex;align-items:center;justify-content:center;'>"
                f"{radio_inner}</div>"
                f"<span style='font-size:10px;font-weight:600;padding:2px 9px;"
                f"border-radius:20px;background:{period_bg};color:{period_col};"
                f"white-space:nowrap;flex-shrink:0;'>{period_lbl}</span>"
                f"<span style='font-size:14px;font-weight:600;color:{time_col};"
                f"flex:1;text-decoration:{time_dec};'>{sess['label']}</span>"
                f"<span style='font-size:11px;font-weight:500;color:{status_col};'>"
                f"{status_txt}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

            # Invisible button exactly same height as card
            clicked = st.button("​", key=sid, disabled=taken)

            if clicked and not taken:
                _fetch_cached.clear()
                fresh = fetch_booked()
                if is_booked(fresh, dk, sess["value"]):
                    alts = get_alts(fresh, dk, sess["value"])
                    st.session_state.conflict_type = "blocking"
                    st.session_state.conflict_msg  = "Jadwal ini baru saja terisi hotel lain."
                    st.session_state.alternatives  = alts
                else:
                    st.session_state.sel_date_key   = dk
                    st.session_state.sel_date_label = chosen_dt["label"]
                    st.session_state.sel_sess_value = sess["value"]
                    st.session_state.sel_sess_label = sess["label"]
                    st.session_state.conflict_type  = "ok"
                    st.session_state.conflict_msg   = (
                        chosen_dt["label"] + " · " + sess["label"] + " siap di-booking."
                    )
                    st.session_state.alternatives   = []
                st.rerun()

    # ── CTA ──
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if st.session_state.sel_date_key and st.session_state.sel_sess_value:
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("Batal", key="clear_jadwal"):
                for k in ("sel_date_key","sel_date_label","sel_sess_value","sel_sess_label"):
                    st.session_state[k] = None
                st.session_state.conflict_type = None
                st.rerun()
        with c2:
            if st.button("Lanjut →", type="primary", key="btn1_next"):
                st.session_state.step = 2
                st.rerun()
    else:
        if chosen_dt:
            alert("Pilih sesi waktu di atas untuk melanjutkan.", kind="warn", icon="👆")
        else:
            alert("Pilih tanggal kunjungan terlebih dahulu.", kind="warn", icon="📅")

    st.markdown('</div>', unsafe_allow_html=True)

# ── STEP 2 ─────────────────────────────────────────────────────────────────────
def render_step2():
    st.markdown('<div class="content">', unsafe_allow_html=True)
    sel_banner()

    st.session_state.nama_hotel = st.text_input(
        "Nama Hotel / Property *",
        value=st.session_state.nama_hotel,
        placeholder="Contoh: Grand Hyatt Jakarta",
        key="inp_nama_hotel",
    )
    st.session_state.alamat_hotel = st.text_area(
        "Alamat Lengkap *",
        value=st.session_state.alamat_hotel,
        placeholder="Jl. ..., Kelurahan, Kecamatan, Kota",
        height=90, key="inp_alamat",
    )
    opts = HOTEL_BRANDS
    idx  = opts.index(st.session_state.brand_hotel) if st.session_state.brand_hotel in opts else 0
    st.session_state.brand_hotel = st.selectbox(
        "Brand / Chain Hotel (opsional)", options=opts, index=idx, key="inp_brand",
        format_func=lambda x: "— Pilih brand / chain —" if x == "" else x,
    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("← Kembali", key="btn2_back"):
            st.session_state.step = 1; st.rerun()
    with c2:
        if st.button("Lanjut →", type="primary", key="btn2_next"):
            errs = []
            if not st.session_state.nama_hotel.strip():   errs.append("Nama hotel wajib diisi.")
            if not st.session_state.alamat_hotel.strip(): errs.append("Alamat hotel wajib diisi.")
            if errs:
                [st.error(e) for e in errs]
            else:
                st.session_state.step = 3; st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ── STEP 3 ─────────────────────────────────────────────────────────────────────
def render_step3():
    st.markdown('<div class="content">', unsafe_allow_html=True)
    sel_banner()

    sec("Identitas PIC")
    st.session_state.nama_pic = st.text_input("Nama PIC Utama *",
        value=st.session_state.nama_pic, placeholder="Nama lengkap", key="inp_nama_pic")

    c1, c2 = st.columns(2)
    with c1:
        st.session_state.jabatan = st.text_input("Jabatan *",
            value=st.session_state.jabatan, placeholder="Sales Manager, GM...", key="inp_jabatan")
    with c2:
        st.session_state.no_hp = st.text_input("WhatsApp *",
            value=st.session_state.no_hp, placeholder="08xx-xxxx-xxxx", key="inp_no_hp")

    st.session_state.email = st.text_input("Email *",
        value=st.session_state.email, placeholder="nama@hotel.com", key="inp_email")

    sec("Jumlah Peserta")
    p_opts = ["1 orang","2 orang","3 orang","4 orang","5 orang"]
    cur_p  = p_opts.index(st.session_state.peserta) if st.session_state.peserta in p_opts else 0
    st.session_state.peserta = st.radio("Peserta", options=p_opts, index=cur_p,
        horizontal=True, label_visibility="collapsed", key="inp_peserta")

    sec("Tujuan Kunjungan")

    # Render tujuan as styled st.button rows — single element, no overlay trick
    # CSS makes each button look like the Opsi C card row
    # Tujuan — st.checkbox hidden, replaced visually with custom card row
    st.markdown("""
<style>
/* Hide native checkbox widget completely */
div[data-testid="stCheckbox"] { all: unset !important; display: block !important; margin-bottom: 6px !important; }
div[data-testid="stCheckbox"] > label {
  all: unset !important;
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  width: 100% !important;
  padding: 11px 14px !important;
  border-radius: 8px !important;
  border: 1.5px solid #DEDEDE !important;
  background: #ffffff !important;
  cursor: pointer !important;
  box-sizing: border-box !important;
  transition: border-color 0.15s !important;
  min-height: 46px !important;
}
div[data-testid="stCheckbox"] > label:hover {
  border-color: #1BA0E2 !important;
}
div[data-testid="stCheckbox"]:has(input:checked) > label {
  border-color: #1BA0E2 !important;
  background: rgba(27,160,226,0.07) !important;
}
/* Hide the native checkbox square */
div[data-testid="stCheckbox"] > label > div:first-child {
  display: none !important;
}
/* The text part — make it fill space */
div[data-testid="stCheckbox"] > label > div:last-child {
  display: contents !important;
}
div[data-testid="stCheckbox"] > label > div:last-child > p {
  display: none !important;
}
</style>""", unsafe_allow_html=True)

    TUJUAN_BADGE_MAP = {
        "Perkenalan Hotel":              "Intro",
        "Presentasi Produk / Fasilitas": "Produk",
        "Corporate Rate / Contract Rate":"Rate",
        "Promo / Special Offer":         "Promo",
        "Kerja Sama Partnership":        "Partner",
        "Follow Up Existing Business":   "Follow Up",
    }

    tujuan_sel = []
    for i, tuj in enumerate(TUJUAN_OPTIONS):
        is_on   = tuj in st.session_state.tujuan
        badge   = TUJUAN_BADGE_MAP.get(tuj, "")
        chk_bg  = "#1BA0E2" if is_on else "#ffffff"
        chk_brd = "#1BA0E2" if is_on else "#DEDEDE"
        lbl_col = "#185FA5" if is_on else "#1a1f2e"
        tag_bg  = "#1BA0E2" if is_on else "#F0F0F0"
        tag_col = "#ffffff" if is_on else "#9ca3af"
        svg_chk = "<svg viewBox='0 0 24 24' style='width:10px;height:10px;stroke:#fff;stroke-width:2.5;fill:none;display:block'><polyline points='20 6 9 17 4 12'/></svg>" if is_on else ""

        st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
  padding:11px 14px;border-radius:8px;
  border:1.5px solid {'#1BA0E2' if is_on else '#DEDEDE'};
  background:{'rgba(27,160,226,0.07)' if is_on else '#ffffff'};
  margin-bottom:0px;pointer-events:none;">
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="width:18px;height:18px;border-radius:4px;
      border:1.5px solid {chk_brd};background:{chk_bg};
      display:flex;align-items:center;justify-content:center;flex-shrink:0;">{svg_chk}</div>
    <span style="font-size:13px;font-weight:600;color:{lbl_col};">{tuj}</span>
  </div>
  <span style="font-size:10px;font-weight:600;padding:2px 9px;border-radius:20px;
    background:{tag_bg};color:{tag_col};white-space:nowrap;">{badge}</span>
</div>""", unsafe_allow_html=True)

        # Real (invisible) checkbox for interactivity — sits right below the visual card
        st.markdown("""<style>
div[data-testid="stCheckbox"]:last-of-type {
  margin-top: -46px !important;
  opacity: 0 !important;
  position: relative !important;
  z-index: 10 !important;
  height: 46px !important;
  overflow: hidden !important;
}
div[data-testid="stCheckbox"]:last-of-type > label {
  height: 46px !important;
  min-height: 46px !important;
  border: none !important;
  background: transparent !important;
  cursor: pointer !important;
}
</style>""", unsafe_allow_html=True)

        checked = st.checkbox(" ", value=is_on, key=f"tuj_{i}", label_visibility="hidden")
        if checked:
            tujuan_sel.append(tuj)

    # Sync state if changed
    if set(tujuan_sel) != set(st.session_state.tujuan):
        st.session_state.tujuan = tujuan_sel
        st.rerun()
    sec("Estimasi Durasi")
    d_opts = ["15 Menit","30 Menit","45 Menit"]
    cur_d  = d_opts.index(st.session_state.durasi) if st.session_state.durasi in d_opts else 1
    st.session_state.durasi = st.radio("Durasi", options=d_opts, index=cur_d,
        horizontal=True, label_visibility="collapsed", key="inp_durasi")

    sec("Catatan Tambahan (Opsional)")
    st.session_state.catatan = st.text_area("Catatan", value=st.session_state.catatan,
        placeholder="Informasi tambahan...", height=75,
        label_visibility="collapsed", key="inp_catatan")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("← Kembali", key="btn3_back"):
            st.session_state.step = 2; st.rerun()
    with c2:
        if st.button("Review →", type="primary", key="btn3_next"):
            errs = []
            if not st.session_state.nama_pic.strip():  errs.append("Nama PIC wajib diisi.")
            if not st.session_state.jabatan.strip():   errs.append("Jabatan wajib diisi.")
            if not st.session_state.no_hp.strip():     errs.append("Nomor WhatsApp wajib diisi.")
            elif not valid_phone(st.session_state.no_hp): errs.append("Format nomor WA tidak valid.")
            if not st.session_state.email.strip():     errs.append("Email wajib diisi.")
            elif not valid_email(st.session_state.email): errs.append("Format email tidak valid.")
            if not st.session_state.tujuan:            errs.append("Pilih minimal satu tujuan kunjungan.")
            if errs:
                [st.error(e) for e in errs]
            else:
                st.session_state.step = 4; st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ── STEP 4 ─────────────────────────────────────────────────────────────────────
def render_step4():
    st.markdown('<div class="content">', unsafe_allow_html=True)

    def row(lbl, val, hl=False):
        vcls = "rev-val hl" if hl else "rev-val"
        return f'<div class="rev-row"><div class="rev-lbl">{lbl}</div><div class="{vcls}">{val}</div></div>'

    html = (
        '<div class="rev-card">'
        '<div class="rev-group-head">📅 Jadwal</div>'
        + row("Tanggal", st.session_state.sel_date_label or "—", hl=True)
        + row("Sesi",    st.session_state.sel_sess_label  or "—", hl=True)
        + '<div class="rev-group-head">🏨 Hotel</div>'
        + row("Hotel",   st.session_state.nama_hotel)
        + row("Alamat",  st.session_state.alamat_hotel)
        + row("Brand",   st.session_state.brand_hotel or "—")
        + '<div class="rev-group-head">👤 Kontak</div>'
        + row("Nama PIC", st.session_state.nama_pic)
        + row("Jabatan",  st.session_state.jabatan)
        + row("WA",       st.session_state.no_hp)
        + row("Email",    st.session_state.email)
        + row("Peserta",  st.session_state.peserta)
        + row("Durasi",   st.session_state.durasi)
        + row("Tujuan",   ", ".join(st.session_state.tujuan) or "—")
        + (row("Catatan", st.session_state.catatan) if st.session_state.catatan.strip() else "")
        + '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

    ibox("Dengan mengirim, Anda bersedia dihubungi via WhatsApp atau Email untuk konfirmasi jadwal.")

    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("← Edit", key="btn4_back"):
            st.session_state.step = 3; st.rerun()
    with c2:
        if st.session_state.get("submitting"):
            st.info("Sedang mengirim, mohon tunggu...")
        else:
            st.markdown('<div class="submit-accent-wrap">', unsafe_allow_html=True)
            if st.button("Kirim", key="btn4_submit", type="primary"):
                st.session_state.submitting = True
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # Execute submission after flag is set (on next rerun)
    if st.session_state.get("submitting"):
        _do_submit()

    st.markdown('</div>', unsafe_allow_html=True)

def _do_submit():
    # Guard against double submit
    if st.session_state.get("submitted_ref"):
        st.session_state.submitting = False
        st.session_state.step = 5
        st.rerun()
        return

    _fetch_cached.clear()
    fresh = fetch_booked()
    dk = st.session_state.sel_date_key
    sv = st.session_state.sel_sess_value

    if is_booked(fresh, dk, sv):
        alts = get_alts(fresh, dk, sv)
        st.session_state.conflict_type = "blocking"
        st.session_state.conflict_msg  = (
            f"Jadwal {st.session_state.sel_sess_label} pada "
            f"{st.session_state.sel_date_label} baru saja dipesan hotel lain.")
        st.session_state.alternatives = alts
        for k in ("sel_date_key","sel_date_label","sel_sess_value","sel_sess_label"):
            st.session_state[k] = None
        st.session_state.submitting = False
        st.session_state.step = 1
        st.rerun()
        return

    wib = datetime.now(ZoneInfo("Asia/Jakarta"))
    ref = gen_ref()
    payload = {
        "ref": ref, "timestamp": wib.strftime("%d/%m/%Y %H:%M:%S"),
        "namaHotel":   st.session_state.nama_hotel.strip(),
        "alamatHotel": st.session_state.alamat_hotel.strip(),
        "brand":       st.session_state.brand_hotel or "—",
        "namaPIC":     st.session_state.nama_pic.strip(),
        "jabatan":     st.session_state.jabatan.strip(),
        "noHP":        st.session_state.no_hp.strip(),
        "email":       st.session_state.email.strip(),
        "peserta":     st.session_state.peserta,
        "tujuan":      ", ".join(st.session_state.tujuan),
        "tanggal":     dk + " (Selasa)", "slot": sv,
        "durasi":      st.session_state.durasi,
        "catatan":     st.session_state.catatan or "",
    }
    with st.spinner("Menyimpan & mengirim notifikasi..."):
        ok, result = save_to_gas(payload)

    st.session_state.submitting = False

    if ok:
        st.session_state.ref_number    = result or ref
        st.session_state.submitted_ref = result or ref
        st.session_state.step = 5
        _fetch_cached.clear()
        st.rerun()
    elif result == "Jadwal_TAKEN":
        _fetch_cached.clear()
        fresh2 = fetch_booked()
        alts = get_alts(fresh2, dk, sv)
        st.session_state.conflict_type = "blocking"
        st.session_state.conflict_msg  = f"Jadwal {st.session_state.sel_sess_label} baru saja dipesan saat Anda submit."
        st.session_state.alternatives  = alts
        for k in ("sel_date_key","sel_date_label","sel_sess_value","sel_sess_label"):
            st.session_state[k] = None
        st.session_state.step = 1
        st.rerun()
    else:
        st.error(f"Gagal menyimpan: {result}. Silakan coba lagi.")

# ── STEP 5 ─────────────────────────────────────────────────────────────────────
def render_success():
    import streamlit.components.v1 as components

    ref      = st.session_state.ref_number
    hotel    = st.session_state.nama_hotel
    pic      = st.session_state.nama_pic
    tanggal  = st.session_state.sel_date_label
    sesi     = st.session_state.sel_sess_label
    sesi_jam = sesi.split("\u2013")[0].strip() if sesi else "\u2014"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@700;800;900&family=Nunito+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: transparent; font-family: 'Nunito Sans', sans-serif; padding: 0 16px; }}
.gpass {{
  background: #fff;
  border: 1.5px solid #DEDEDE;
  border-radius: 14px;
  overflow: hidden;
  max-width: 420px;
  margin: 0 auto;
}}
.gpass-top {{
  background: #1BA0E2;
  padding: 20px 22px 18px;
}}
.gpass-co {{
  font-size: 10px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: rgba(255,255,255,0.6);
  margin-bottom: 10px;
}}
.gpass-top-row {{
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}}
.gpass-time-lbl {{
  font-size: 10px;
  color: rgba(255,255,255,0.6);
  margin-bottom: 4px;
}}
.gpass-time {{
  font-size: 30px;
  font-weight: 900;
  color: #fff;
  font-family: 'Nunito', sans-serif;
  letter-spacing: 1px;
  line-height: 1;
}}
.gpass-right {{ text-align: right; }}
.gpass-right-lbl {{
  font-size: 10px;
  color: rgba(255,255,255,0.6);
  margin-bottom: 2px;
  margin-top: 8px;
}}
.gpass-right-val {{ font-size: 13px; font-weight: 600; color: #fff; }}
.gpass-status {{
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: rgba(255,255,255,0.18);
  border: 1px solid rgba(255,255,255,0.3);
  border-radius: 20px;
  padding: 3px 10px;
  font-size: 11px;
  color: #fff;
  font-weight: 700;
  margin-top: 4px;
}}
.gpass-tear {{
  height: 1px;
  background: repeating-linear-gradient(90deg,#DEDEDE 0,#DEDEDE 6px,transparent 6px,transparent 12px);
  position: relative;
}}
.gpass-tear::before, .gpass-tear::after {{
  content: '';
  position: absolute;
  top: -9px;
  width: 18px; height: 18px;
  border-radius: 50%;
  background: #F0F0F0;
  border: 1.5px solid #DEDEDE;
}}
.gpass-tear::before {{ left: -9px; }}
.gpass-tear::after  {{ right: -9px; }}
.gpass-body {{ padding: 18px 22px 16px; }}
.gpass-fields {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px 20px;
  margin-bottom: 14px;
}}
.gpass-flbl {{
  font-size: 9px;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-bottom: 3px;
}}
.gpass-fval {{ font-size: 13px; font-weight: 600; color: #1a1f2e; }}
.gpass-ref-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 11px 14px;
  background: #F7F9FC;
  border-radius: 8px;
  border: 1px solid #EDEDEE;
}}
.gpass-ref-lbl {{
  font-size: 9px;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-bottom: 3px;
}}
.gpass-ref-val {{
  font-size: 16px;
  font-weight: 900;
  color: #1a1f2e;
  letter-spacing: 2.5px;
  font-family: 'Nunito', sans-serif;
}}
.gpass-ref-hint {{ font-size: 11px; color: #9ca3af; }}
.gpass-foot {{
  padding: 12px 22px;
  border-top: 1px solid #EDEDEE;
  background: #F7F9FC;
  display: flex;
  justify-content: space-between;
  align-items: center;
}}
.gpass-note {{ font-size: 11px; color: #9ca3af; }}
.gpass-savebtn {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #1BA0E2;
  background: none;
  border: 1.5px solid #1BA0E2;
  border-radius: 7px;
  padding: 7px 14px;
  cursor: pointer;
  font-family: 'Nunito Sans', sans-serif;
  transition: background 0.15s, opacity 0.15s;
}}
.gpass-savebtn:hover {{ background: rgba(27,160,226,0.07); }}
.gpass-savebtn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
.gpass-savebtn svg {{
  width: 13px; height: 13px;
  stroke: #1BA0E2; stroke-width: 2.2;
  fill: none; display: block;
}}

.logo-bar {{
  max-width: 420px;
  margin: 0 auto 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0 0;
}}
.logo-bar img {{
  height: 34px;
  width: auto;
  object-fit: contain;
  display: block;
}}
.logo-live {{
  display: flex;
  align-items: center;
  gap: 5px;
  background: #ecfdf5;
  border: 1px solid #6ee7b7;
  border-radius: 20px;
  padding: 4px 10px;
  font-size: 10px;
  font-weight: 700;
  color: #059669;
}}
.pulse-dot {{
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #10b981;
  animation: pulse 2s ease-in-out infinite;
}}
@keyframes pulse {{
  0%,100% {{ opacity:1; transform:scale(1); }}
  50%      {{ opacity:.4; transform:scale(.8); }}
}}
.page-footer {{
  max-width: 420px;
  margin: 12px auto 0;
  text-align: center;
  font-size: 11px;
  color: #bbb;
  letter-spacing: 0.3px;
  padding-bottom: 20px;
}}
.page-footer span {{ color: #1BA0E2; font-weight: 700; }}
</style>
</head>
<body>
<div class="logo-bar">
  <img src="https://mitratour.com/wp-content/uploads/2019/09/LOGO-MITRA-Converted-Copy-min.png" alt="Mitra Tours & Travel" />
  <div class="logo-live"><div class="pulse-dot"></div>Sistem Aktif</div>
</div>
<div id="gpass-capture">
<div class="gpass">
  <div class="gpass-top">
    <div class="gpass-co">Kunjungan Sales &nbsp;&middot;&nbsp; Mitra Tours &amp; Travel</div>
    <div class="gpass-top-row">
      <div>
        <div class="gpass-time-lbl">Waktu sesi</div>
        <div class="gpass-time">{sesi_jam}</div>
      </div>
      <div class="gpass-right">
        <div class="gpass-right-lbl">Tanggal</div>
        <div class="gpass-right-val">{tanggal}</div>
        <div class="gpass-status">&#10003; Terkirim</div>
      </div>
    </div>
  </div>
  <div class="gpass-tear"></div>
  <div class="gpass-body">
    <div class="gpass-fields">
      <div><div class="gpass-flbl">Hotel</div><div class="gpass-fval">{hotel}</div></div>
      <div><div class="gpass-flbl">PIC</div><div class="gpass-fval">{pic}</div></div>
      <div><div class="gpass-flbl">Sesi</div><div class="gpass-fval">{sesi}</div></div>
      <div><div class="gpass-flbl">Notifikasi</div><div class="gpass-fval" style="font-size:11px;word-break:break-all">{NOTIF_EMAIL}</div></div>
    </div>
    <div class="gpass-ref-row">
      <div>
        <div class="gpass-ref-lbl">Nomor Referensi</div>
        <div class="gpass-ref-val">{ref}</div>
      </div>
      <div class="gpass-ref-hint">Simpan kode ini</div>
    </div>
  </div>
  <div class="gpass-foot">
    <span class="gpass-note">Booking System v2.0</span>
    <button class="gpass-savebtn" id="savebtn" onclick="saveAsJpg()">
      <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      Simpan JPG
    </button>
  </div>
</div>
</div>

<div class="page-footer">Mitra Tours and Travel &nbsp;&middot;&nbsp; <span>Booking System</span> &nbsp;&middot;&nbsp; v2.0</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script>
function saveAsJpg() {{
  var btn = document.getElementById('savebtn');
  btn.disabled = true;
  btn.innerHTML = 'Menyimpan...';
  var el = document.getElementById('gpass-capture');
  html2canvas(el, {{
    scale: 2,
    useCORS: true,
    allowTaint: true,
    backgroundColor: '#ffffff',
    logging: false,
    onclone: function(doc) {{
      doc.getElementById('gpass-capture').style.padding = '12px';
    }}
  }}).then(function(canvas) {{
    var a = document.createElement('a');
    a.download = 'konfirmasi-{ref}.jpg';
    a.href = canvas.toDataURL('image/jpeg', 0.95);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    btn.disabled = false;
    btn.innerHTML = '<svg viewBox=\"0 0 24 24\" style=\"width:13px;height:13px;stroke:#1BA0E2;stroke-width:2.2;fill:none;display:block\"><path d=\"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4\"/><polyline points=\"7 10 12 15 17 10\"/><line x1=\"12\" y1=\"15\" x2=\"12\" y2=\"3\"/></svg> Tersimpan \u2713';
  }}).catch(function(e) {{
    console.error(e);
    btn.disabled = false;
    btn.innerHTML = 'Coba lagi';
  }});
}}

</script>
</body>
</html>"""

    components.html(html, height=560, scrolling=False)

# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    init_state()
    inject_css()

    s = st.session_state.step

    if s != 5:
        render_topbar()

    if s <= 4:
        render_hero(s)
        render_step_tracker(s)

    if   s == 1: render_step1()
    elif s == 2: render_step2()
    elif s == 3: render_step3()
    elif s == 4: render_step4()
    elif s == 5: render_success()

    if s != 5:
        st.markdown(
            '<div class="footer">Mitra Tours and Travel &nbsp;·&nbsp; '
            '<span>Booking System</span> &nbsp;·&nbsp; v2.0</div>',
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    main()
