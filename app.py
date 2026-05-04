import streamlit as st
import openai
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
import base64
import re
from PIL import Image
import io

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI CC Reporting System",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Global */
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 900px; }
    
    /* Header */
    .app-header {
        background: #1558b0;
        color: white;
        padding: 16px 24px;
        border-radius: 12px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .app-header h1 { font-size: 20px; margin: 0; font-weight: 600; }
    .app-header p  { font-size: 12px; margin: 0; opacity: .8; }

    /* Step indicator */
    .step-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 20px;
        padding: 12px 16px;
        background: #f8fafc;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
    }
    .step-dot {
        width: 28px; height: 28px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 12px; font-weight: 600; flex-shrink: 0;
    }
    .step-dot.done { background: #16a34a; color: white; }
    .step-dot.active { background: #1558b0; color: white; }
    .step-dot.pending { background: #e2e8f0; color: #94a3b8; }
    .step-line { flex: 1; height: 1px; background: #e2e8f0; }
    .step-line.done { background: #16a34a; }
    .step-label { font-size: 11px; color: #64748b; white-space: nowrap; }

    /* Mode selector cards */
    .mode-card {
        border: 1.5px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px 12px;
        text-align: center;
        cursor: pointer;
        transition: all .15s;
        background: white;
    }
    .mode-card:hover { border-color: #1558b0; background: #f0f7ff; }
    .mode-card.selected { border-color: #1558b0; background: #eff6ff; }
    .mode-card .icon { font-size: 24px; margin-bottom: 6px; }
    .mode-card .title { font-size: 13px; font-weight: 600; color: #1e293b; }
    .mode-card .sub { font-size: 11px; color: #94a3b8; margin-top: 2px; }

    /* Result box */
    .result-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 14px;
        font-family: monospace;
        font-size: 12px;
        color: #334155;
        line-height: 1.7;
        white-space: pre-wrap;
        word-break: break-all;
        max-height: 200px;
        overflow-y: auto;
    }

    /* Success box */
    .success-box {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 10px;
        padding: 16px 20px;
        margin-top: 12px;
    }
    .success-box h3 { color: #166534; font-size: 15px; margin-bottom: 4px; }
    .success-box p  { color: #15803d; font-size: 13px; margin: 0; }

    /* Field preview rows */
    .preview-row {
        display: flex;
        justify-content: space-between;
        padding: 6px 0;
        border-bottom: 1px solid #f1f5f9;
        font-size: 13px;
    }
    .preview-row:last-child { border-bottom: none; }
    .preview-key { color: #64748b; }
    .preview-val { font-weight: 600; color: #1e293b; }

    /* Badges */
    .badge-green {
        display: inline-block;
        background: #dcfce7; color: #166534;
        border: 1px solid #bbf7d0;
        padding: 2px 8px; border-radius: 20px;
        font-size: 11px; font-weight: 600;
    }
    .badge-blue {
        display: inline-block;
        background: #dbeafe; color: #1d4ed8;
        border: 1px solid #bfdbfe;
        padding: 2px 8px; border-radius: 20px;
        font-size: 11px; font-weight: 600;
    }

    /* Hide Streamlit default elements */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
    header    { visibility: hidden; }

    /* Upload zone */
    .uploadedFile { border-radius: 8px; }
    [data-testid="stFileUploader"] > div { border-radius: 10px; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #f8fafc;
        border-radius: 10px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: white;
        box-shadow: 0 1px 3px rgba(0,0,0,.08);
    }

    /* Dataframe */
    [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)


# ─── Helper: Google Sheets connection ───────────────────────────────────────
@st.cache_resource(ttl=300)
def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["google_sheets"]["sheet_id"])
    return sheet.sheet1


def ensure_header(ws):
    """Create header row if sheet is empty."""
    headers = [
        "Timestamp", "Nama Pelapor", "Booking ID", "Supplier",
        "Hotel", "Check-in", "Check-out", "Nominal (Rp)",
        "Kartu", "Metode Pembayaran", "Catatan"
    ]
    if ws.row_count == 0 or ws.cell(1, 1).value != "Timestamp":
        ws.insert_row(headers, 1)


def append_row(data: dict):
    ws = get_sheet()
    ensure_header(ws)
    row = [
        data.get("timestamp", ""),
        data.get("name", ""),
        data.get("booking_id", ""),
        data.get("supplier", ""),
        data.get("hotel", ""),
        data.get("checkin", ""),
        data.get("checkout", ""),
        data.get("nominal", ""),
        data.get("card", ""),
        data.get("method", ""),
        data.get("notes", ""),
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")


def fetch_all_rows():
    ws = get_sheet()
    records = ws.get_all_records()
    return records


# ─── Helper: OpenAI parsing ─────────────────────────────────────────────────
def parse_with_ai(text: str = "", image_b64: str = None, image_mime: str = None) -> dict:
    client = openai.OpenAI(api_key=st.secrets["openai"]["api_key"])

    system_prompt = """Kamu adalah AI parser untuk sistem pelaporan kartu kredit korporat hotel.
Ekstrak informasi dari input (teks bebas, foto struk/invoice/screenshot, atau keduanya).
Kembalikan HANYA JSON valid tanpa penjelasan, tanpa markdown backtick.

Format wajib:
{
  "name": "nama staf pelapor",
  "booking_id": "ID booking",
  "supplier": "nama supplier/platform booking",
  "hotel": "nama hotel lengkap",
  "checkin": "YYYY-MM-DD",
  "checkout": "YYYY-MM-DD",
  "nominal": angka_integer,
  "card": "info kartu",
  "method": "metode pembayaran",
  "notes": "catatan tambahan"
}

Aturan:
- Jika info tidak ditemukan, isi string kosong "" atau 0 untuk nominal.
- Tanggal wajib format YYYY-MM-DD. Konversi dari format apapun.
- Nominal: hilangkan simbol mata uang (Rp, IDR), titik, koma — angka bulat saja.
- Jika ada singkatan seperti "5.4jt" atau "5.4 juta", konversi ke 5400000."""

    content = []

    if image_b64 and image_mime:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{image_mime};base64,{image_b64}",
                "detail": "high"
            }
        })

    user_text = (
        "Ekstrak semua informasi transaksi dari dokumen/foto ini."
        if (image_b64 and not text)
        else f"Dokumen ada di foto. Keterangan tambahan: {text}"
        if (image_b64 and text)
        else f"Teks laporan:\n{text}"
    )
    content.append({"type": "text", "text": user_text})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ],
        max_tokens=700,
        temperature=0.05,
    )

    raw = response.choices[0].message.content
    match = re.search(r'\{[\s\S]*\}', raw)
    if not match:
        raise ValueError("JSON tidak ditemukan dalam respons AI")
    return json.loads(match.group()), raw


# ─── Helper: image → base64 ──────────────────────────────────────────────────
def image_to_b64(uploaded_file):
    img_bytes = uploaded_file.read()
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    mime = uploaded_file.type or "image/jpeg"
    return b64, mime


# ─── Step indicator HTML ─────────────────────────────────────────────────────
def render_steps(current: int):
    steps = ["Input", "Proses AI", "Verifikasi", "Simpan"]
    html = '<div class="step-bar">'
    for i, label in enumerate(steps, 1):
        if i < current:
            cls = "done"
            symbol = "✓"
        elif i == current:
            cls = "active"
            symbol = str(i)
        else:
            cls = "pending"
            symbol = str(i)
        html += f'<div class="step-dot {cls}">{symbol}</div>'
        html += f'<span class="step-label">{label}</span>'
        if i < len(steps):
            line_cls = "done" if i < current else ""
            html += f'<div class="step-line {line_cls}"></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ─── Session state init ───────────────────────────────────────────────────────
for key, default in {
    "step": 1,
    "parsed": {},
    "raw_ai": "",
    "input_mode": "text",
    "saved_data": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <div style="font-size:28px">💳</div>
    <div>
        <h1>AI Credit Card Reporting System</h1>
        <p>Hotel Voucher Transaction Tracker — Powered by GPT-4o + Google Sheets</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── Main Tabs ────────────────────────────────────────────────────────────────
tab_input, tab_dashboard, tab_log = st.tabs([
    "📝  Input Laporan",
    "📊  Dashboard",
    "📋  Log & Riwayat"
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — INPUT LAPORAN
# ═══════════════════════════════════════════════════════════════════════════════
with tab_input:

    render_steps(st.session_state.step)

    # ── STEP 1: Pilih mode & input ─────────────────────────────────────────
    if st.session_state.step == 1:

        st.subheader("Pilih metode input")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("✏️  Teks Bebas\n\nKetik laporan langsung",
                         use_container_width=True,
                         type="secondary" if st.session_state.input_mode != "text" else "primary"):
                st.session_state.input_mode = "text"
                st.rerun()

        with col2:
            if st.button("📷  Foto / Dokumen\n\nStruk, invoice, screenshot",
                         use_container_width=True,
                         type="secondary" if st.session_state.input_mode != "photo" else "primary"):
                st.session_state.input_mode = "photo"
                st.rerun()

        with col3:
            if st.button("🗒️  Foto + Keterangan\n\nFoto dengan catatan",
                         use_container_width=True,
                         type="secondary" if st.session_state.input_mode != "both" else "primary"):
                st.session_state.input_mode = "both"
                st.rerun()

        st.divider()

        # ── Upload foto ──
        uploaded_file = None
        if st.session_state.input_mode in ("photo", "both"):
            st.markdown("#### Upload Foto / Dokumen")
            uploaded_file = st.file_uploader(
                "Foto struk, invoice, screenshot WhatsApp, dll.",
                type=["jpg", "jpeg", "png", "webp"],
                label_visibility="collapsed",
            )
            if uploaded_file:
                img = Image.open(uploaded_file)
                st.image(img, caption=f"📎 {uploaded_file.name}", use_column_width=True)
                uploaded_file.seek(0)

        # ── Teks input ──
        report_text = ""
        if st.session_state.input_mode in ("text", "both"):
            label = "Keterangan tambahan (opsional)" if st.session_state.input_mode == "both" else "Teks laporan bebas"
            st.markdown(f"#### {label}")
            placeholder = (
                "Contoh: Booking Grand Hyatt Jakarta untuk tamu VIP, check-in 15 Januari "
                "checkout 17 Januari, Booking ID HY-2025-001, supplier Expedia, nominal 5.4 juta, "
                "kartu BCA Corp 4521, direct billing. Pelapor: Budi Santoso."
            )
            report_text = st.text_area(
                "laporan",
                placeholder=placeholder,
                height=150,
                label_visibility="collapsed",
            )

        st.divider()
        col_btn1, col_btn2 = st.columns([2, 8])
        with col_btn1:
            process_btn = st.button("✦ Proses dengan AI", type="primary", use_container_width=True)
        with col_btn2:
            if st.button("🗑️ Bersihkan", use_container_width=False):
                st.session_state.step = 1
                st.session_state.parsed = {}
                st.session_state.raw_ai = ""
                st.rerun()

        if process_btn:
            has_text = bool(report_text.strip())
            has_photo = uploaded_file is not None

            if not has_text and not has_photo:
                st.error("⚠️ Masukkan teks laporan atau upload foto terlebih dahulu.")
            else:
                with st.spinner("🤖 Menghubungi GPT-4o, harap tunggu..."):
                    try:
                        img_b64, img_mime = None, None
                        if has_photo:
                            img_b64, img_mime = image_to_b64(uploaded_file)

                        parsed, raw = parse_with_ai(
                            text=report_text,
                            image_b64=img_b64,
                            image_mime=img_mime,
                        )
                        st.session_state.parsed = parsed
                        st.session_state.raw_ai = raw
                        st.session_state.step = 2
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Gagal memproses: {e}")

    # ── STEP 2: Tampilkan hasil AI ─────────────────────────────────────────
    elif st.session_state.step == 2:
        with st.expander("🔍 Raw output dari AI (klik untuk lihat)", expanded=False):
            st.code(st.session_state.raw_ai, language="json")

        st.success("✅ AI berhasil mengekstrak data! Silakan verifikasi di bawah.")
        st.session_state.step = 3
        st.rerun()

    # ── STEP 3: Form verifikasi & edit ────────────────────────────────────
    elif st.session_state.step == 3:
        p = st.session_state.parsed

        with st.expander("🔍 Raw output dari AI", expanded=False):
            st.code(st.session_state.raw_ai, language="json")

        st.markdown("#### Verifikasi & Edit Data")
        st.info("Periksa data hasil ekstraksi AI. Edit jika ada yang kurang tepat sebelum menyimpan.")

        with st.form("verify_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Nama Pelapor *", value=p.get("name", ""))
                supplier = st.text_input("Supplier", value=p.get("supplier", ""))
                checkin = st.text_input("Check-in * (YYYY-MM-DD)", value=p.get("checkin", ""))
                card = st.text_input("Info Kartu", value=p.get("card", ""))

            with col2:
                booking_id = st.text_input("Booking ID *", value=p.get("booking_id", ""))
                hotel = st.text_input("Nama Hotel *", value=p.get("hotel", ""))
                checkout = st.text_input("Check-out * (YYYY-MM-DD)", value=p.get("checkout", ""))
                nominal = st.number_input(
                    "Nominal (Rp) *",
                    value=int(p.get("nominal", 0)),
                    min_value=0,
                    step=10000,
                )

            method_options = ["", "Direct Billing", "Credit Card", "Transfer Bank", "Virtual Account", "Cash"]
            method_val = p.get("method", "")
            method_idx = method_options.index(method_val) if method_val in method_options else 0
            method = st.selectbox("Metode Pembayaran", method_options, index=method_idx)
            notes = st.text_input("Catatan (opsional)", value=p.get("notes", ""))

            col_s1, col_s2 = st.columns([3, 7])
            with col_s1:
                submit = st.form_submit_button("💾 Simpan ke Google Sheets", type="primary", use_container_width=True)
            with col_s2:
                back = st.form_submit_button("← Proses ulang", use_container_width=False)

            if back:
                st.session_state.step = 1
                st.rerun()

            if submit:
                errors = []
                if not name.strip():   errors.append("Nama Pelapor")
                if not booking_id.strip(): errors.append("Booking ID")
                if not hotel.strip():  errors.append("Nama Hotel")
                if not checkin.strip(): errors.append("Check-in")
                if not checkout.strip(): errors.append("Check-out")
                if nominal <= 0:       errors.append("Nominal")

                if errors:
                    st.error(f"⚠️ Wajib diisi: {', '.join(errors)}")
                else:
                    with st.spinner("💾 Menyimpan ke Google Sheets..."):
                        try:
                            save_data = {
                                "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                "name": name,
                                "booking_id": booking_id,
                                "supplier": supplier,
                                "hotel": hotel,
                                "checkin": checkin,
                                "checkout": checkout,
                                "nominal": nominal,
                                "card": card,
                                "method": method,
                                "notes": notes,
                            }
                            append_row(save_data)
                            st.session_state.saved_data = save_data
                            st.session_state.step = 4
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Gagal menyimpan: {e}")

    # ── STEP 4: Sukses ────────────────────────────────────────────────────
    elif st.session_state.step == 4:
        d = st.session_state.saved_data or {}

        st.markdown("""
        <div class="success-box">
            <h3>✅ Transaksi Berhasil Disimpan!</h3>
            <p>Data telah dicatat ke Google Sheets secara otomatis.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### Ringkasan")
        cols = st.columns(2)
        fields = [
            ("Timestamp", d.get("timestamp")),
            ("Booking ID", d.get("booking_id")),
            ("Nama Pelapor", d.get("name")),
            ("Hotel", d.get("hotel")),
            ("Check-in → Check-out", f"{d.get('checkin')} → {d.get('checkout')}"),
            ("Nominal", f"Rp {int(d.get('nominal', 0)):,}".replace(",", ".")),
            ("Kartu", d.get("card")),
            ("Metode", d.get("method")),
        ]
        for i, (k, v) in enumerate(fields):
            with cols[i % 2]:
                st.metric(k, v or "—")

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Input Laporan Baru", type="primary", use_container_width=True):
                st.session_state.step = 1
                st.session_state.parsed = {}
                st.session_state.raw_ai = ""
                st.session_state.saved_data = None
                st.rerun()
        with col2:
            sheet_url = f"https://docs.google.com/spreadsheets/d/{st.secrets['google_sheets']['sheet_id']}"
            st.link_button("📊 Buka Google Sheets →", sheet_url, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
with tab_dashboard:
    col_h1, col_h2 = st.columns([8, 2])
    with col_h1:
        st.subheader("📊 Ringkasan Transaksi")
    with col_h2:
        refresh = st.button("↻ Refresh", use_container_width=True)

    try:
        with st.spinner("Memuat data dari Google Sheets..."):
            rows = fetch_all_rows()

        if not rows:
            st.info("Belum ada transaksi. Tambahkan melalui tab Input Laporan.")
        else:
            import pandas as pd

            df = pd.DataFrame(rows)

            # Stats
            total = len(df)
            total_nominal = 0
            if "Nominal (Rp)" in df.columns:
                df["Nominal (Rp)"] = pd.to_numeric(df["Nominal (Rp)"], errors="coerce").fillna(0)
                total_nominal = df["Nominal (Rp)"].sum()

            today_str = datetime.now().strftime("%d/%m/%Y")
            today_count = 0
            if "Timestamp" in df.columns:
                today_count = df["Timestamp"].astype(str).str.startswith(today_str).sum()

            avg_nominal = total_nominal / total if total else 0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Transaksi", total)
            m2.metric("Total Nominal", f"Rp {int(total_nominal):,}".replace(",", "."))
            m3.metric("Hari Ini", today_count)
            m4.metric("Rata-rata", f"Rp {int(avg_nominal):,}".replace(",", "."))

            st.divider()

            # Filters
            with st.expander("🔎 Filter Data", expanded=False):
                f1, f2 = st.columns(2)
                with f1:
                    search_hotel = st.text_input("Cari hotel", placeholder="misal: Hyatt...")
                with f2:
                    search_name = st.text_input("Cari nama pelapor", placeholder="misal: Budi...")

                if search_hotel and "Hotel" in df.columns:
                    df = df[df["Hotel"].astype(str).str.contains(search_hotel, case=False, na=False)]
                if search_name and "Nama Pelapor" in df.columns:
                    df = df[df["Nama Pelapor"].astype(str).str.contains(search_name, case=False, na=False)]

            st.markdown(f"**{len(df)} transaksi ditampilkan**")
            st.dataframe(
                df.iloc[::-1].reset_index(drop=True),
                use_container_width=True,
                height=400,
            )

            # Chart
            if "Metode Pembayaran" in df.columns and len(df) > 0:
                st.divider()
                st.markdown("#### Distribusi Metode Pembayaran")
                metode_count = df["Metode Pembayaran"].value_counts()
                st.bar_chart(metode_count)

    except Exception as e:
        st.error(f"❌ Gagal memuat data: {e}")
        st.info("Pastikan koneksi Google Sheets sudah dikonfigurasi dengan benar di `.streamlit/secrets.toml`")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — LOG & RIWAYAT
# ═══════════════════════════════════════════════════════════════════════════════
with tab_log:
    st.subheader("📋 Log & Riwayat")

    try:
        with st.spinner("Memuat riwayat..."):
            rows = fetch_all_rows()

        if not rows:
            st.info("Belum ada data transaksi.")
        else:
            import pandas as pd
            df = pd.DataFrame(rows)

            st.markdown(f"**Total: {len(df)} entri tersimpan di Google Sheets**")

            # Show last 20 in detail cards
            for i, row in enumerate(reversed(rows[-20:]), 1):
                with st.expander(
                    f"#{len(rows) - i + 1}  |  {row.get('Booking ID', 'N/A')}  —  "
                    f"{row.get('Hotel', 'N/A')}  |  {row.get('Timestamp', '')}",
                    expanded=(i == 1)
                ):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**Nama:** {row.get('Nama Pelapor', '—')}")
                        st.markdown(f"**Supplier:** {row.get('Supplier', '—')}")
                        st.markdown(f"**Check-in:** {row.get('Check-in', '—')}")
                        st.markdown(f"**Check-out:** {row.get('Check-out', '—')}")
                    with c2:
                        nom = row.get('Nominal (Rp)', 0)
                        try:
                            nom_fmt = f"Rp {int(float(nom)):,}".replace(",", ".")
                        except Exception:
                            nom_fmt = str(nom)
                        st.markdown(f"**Nominal:** {nom_fmt}")
                        st.markdown(f"**Kartu:** {row.get('Kartu', '—')}")
                        st.markdown(f"**Metode:** {row.get('Metode Pembayaran', '—')}")
                        st.markdown(f"**Catatan:** {row.get('Catatan', '—')}")

    except Exception as e:
        st.error(f"❌ Gagal memuat log: {e}")
