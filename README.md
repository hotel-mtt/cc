# 💳 AI Credit Card Reporting System

Aplikasi pelaporan kartu kredit korporat berbasis AI untuk mencatat transaksi hotel voucher secara otomatis menggunakan **GPT-4o** dan **Google Sheets** sebagai database.

---

## ✨ Fitur Utama

| Fitur | Keterangan |
|-------|-----------|
| 🤖 AI Parsing | Input teks bebas → GPT-4o ekstrak data otomatis |
| 📷 OCR Visual | Upload foto struk/invoice/screenshot → AI baca langsung |
| 🗒️ Foto + Teks | Kombinasi foto dengan keterangan tambahan |
| ✅ Validasi | Cek field wajib sebelum simpan |
| 📊 Dashboard | Statistik & tabel transaksi real-time |
| 🔗 Google Sheets | Simpan langsung ke spreadsheet secara otomatis |

---

## 📁 Struktur Folder

```
ai-cc-reporting/
├── app.py                    # File utama Streamlit
├── requirements.txt          # Dependensi Python
├── .gitignore                # File yang diabaikan Git
├── README.md                 # Dokumentasi ini
└── .streamlit/
    └── secrets.toml          # ⚠️ RAHASIA — jangan di-commit!
```

---

## 🚀 Panduan Instalasi Lengkap

### BAGIAN A — Persiapan Google Cloud & Sheets

---

#### A1. Buat Project di Google Cloud Console

1. Buka [https://console.cloud.google.com](https://console.cloud.google.com)
2. Klik dropdown project di kiri atas → **New Project**
3. Isi nama project (misal: `ai-cc-reporting`) → **Create**
4. Tunggu project dibuat, lalu pilih project tersebut

---

#### A2. Aktifkan Google Sheets API

1. Di Google Cloud Console, buka menu **APIs & Services → Library**
2. Cari `Google Sheets API` → klik → **Enable**
3. Cari `Google Drive API` → klik → **Enable**

---

#### A3. Buat Service Account

1. Buka **APIs & Services → Credentials**
2. Klik **+ Create Credentials → Service Account**
3. Isi:
   - **Service account name**: `cc-reporting-bot`
   - **Service account ID**: otomatis terisi
4. Klik **Create and Continue**
5. Pada bagian **Grant this service account access**, pilih role:
   - `Editor` (atau minimal `Google Sheets Editor`)
6. Klik **Done**

---

#### A4. Buat dan Download Key JSON

1. Di halaman **Credentials**, klik nama service account yang baru dibuat
2. Buka tab **Keys**
3. Klik **Add Key → Create new key**
4. Pilih format **JSON** → klik **Create**
5. File JSON otomatis ter-download — **simpan baik-baik, jangan share!**

File JSON akan terlihat seperti ini:
```json
{
  "type": "service_account",
  "project_id": "ai-cc-reporting",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "client_email": "cc-reporting-bot@ai-cc-reporting.iam.gserviceaccount.com",
  "client_id": "123456789",
  ...
}
```

---

#### A5. Bagikan Google Spreadsheet ke Service Account

1. Buka Google Spreadsheet Anda:
   👉 [https://docs.google.com/spreadsheets
2. Klik tombol **Share** (kanan atas)
3. Di kolom "Add people and groups", masukkan **client_email** dari file JSON tadi
   Contoh: `cc-reporting-bot@ai-cc-reporting.iam.gserviceaccount.com`
4. Ubah permission menjadi **Editor**
5. Klik **Send** (atau **Share**)

> ⚠️ Langkah ini WAJIB — tanpa ini aplikasi tidak bisa menulis ke spreadsheet!

---

### BAGIAN B — Setup Lokal di Komputer

---

#### B1. Install Python

Pastikan Python 3.9+ sudah terinstall:
```bash
python --version
# Output: Python 3.9.x atau lebih baru
```

Jika belum, download di: [https://python.org/downloads](https://python.org/downloads)

---

#### B2. Clone / Download Kode

**Opsi 1 — Git clone:**
```bash
git clone https://github.com/NAMA_ANDA/ai-cc-reporting.git
cd ai-cc-reporting
```

**Opsi 2 — Download ZIP:**
Ekstrak file ZIP, lalu masuk ke folder tersebut di terminal.

---

#### B3. Buat Virtual Environment

```bash
# Buat virtual environment
python -m venv venv

# Aktifkan (Windows)
venv\Scripts\activate

# Aktifkan (Mac / Linux)
source venv/bin/activate
```

Setelah aktif, terminal akan menampilkan `(venv)` di depan prompt.

---

#### B4. Install Dependencies

```bash
pip install -r requirements.txt
```

Tunggu proses download selesai (mungkin 1-2 menit).

---

#### B5. Konfigurasi Secrets

1. Buat folder `.streamlit` di dalam folder project:
```bash
mkdir .streamlit
```

2. Buat file `.streamlit/secrets.toml`:
```bash
# Windows
copy .streamlit\secrets.toml.example .streamlit\secrets.toml

# Mac/Linux
cp .streamlit/secrets.toml .streamlit/secrets.toml
```

3. Buka file `.streamlit/secrets.toml` dengan text editor dan isi:

```toml
[openai]
api_key = "sk-proj-OPENAI_API_KEY_ANDA_DI_SINI"

[google_sheets]
sheet_id = "1nvgMCmo1EJtbCAt0db_OizvPYDvaEzphKhwzBJ-3X_g"

[gcp_service_account]
type                        = "service_account"
project_id                  = "ISI_DARI_FILE_JSON"
private_key_id              = "ISI_DARI_FILE_JSON"
private_key                 = "-----BEGIN RSA PRIVATE KEY-----\nISI_DARI_FILE_JSON\n-----END RSA PRIVATE KEY-----\n"
client_email                = "ISI_DARI_FILE_JSON"
client_id                   = "ISI_DARI_FILE_JSON"
auth_uri                    = "https://accounts.google.com/o/oauth2/auth"
token_uri                   = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url        = "ISI_DARI_FILE_JSON"
universe_domain             = "googleapis.com"
```

> 💡 Salin nilai dari file JSON yang sudah di-download di langkah A4.
> Perhatian: `private_key` harus tetap dalam satu string dengan `\n` sebagai line break.

---

#### B6. Jalankan Aplikasi

```bash
streamlit run app.py
```

Browser akan otomatis terbuka di `http://localhost:8501`

---

### BAGIAN C — Deploy ke Streamlit Cloud (Opsional)

---

#### C1. Upload ke GitHub

1. Buat repo baru di [https://github.com](https://github.com)
2. **PASTIKAN `.streamlit/secrets.toml` ada di `.gitignore`** sebelum push!
3. Push kode:
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/NAMA/REPO.git
git push -u origin main
```

---

#### C2. Deploy di Streamlit Community Cloud

1. Buka [https://share.streamlit.io](https://share.streamlit.io)
2. Login dengan akun GitHub
3. Klik **New app**
4. Pilih:
   - **Repository**: repo GitHub Anda
   - **Branch**: `main`
   - **Main file path**: `app.py`
5. Klik **Advanced settings → Secrets**
6. Copy-paste seluruh isi `.streamlit/secrets.toml` ke kolom Secrets
7. Klik **Deploy!**

Aplikasi akan live di URL seperti: `https://NAMA-ANDA-ai-cc-reporting.streamlit.app`

---

## 🔑 Cara Mendapatkan OpenAI API Key

1. Buka [https://platform.openai.com](https://platform.openai.com)
2. Login / daftar akun
3. Klik nama akun (kanan atas) → **API Keys**
4. Klik **Create new secret key**
5. Salin key (hanya tampil sekali!) dan simpan di `secrets.toml`

> 💰 Aplikasi ini menggunakan model `gpt-4o` yang membutuhkan kredit. Pastikan akun OpenAI Anda memiliki saldo.

---

## 🛠️ Troubleshooting

| Error | Penyebab | Solusi |
|-------|----------|--------|
| `SpreadsheetNotFound` | Sheet ID salah atau belum di-share | Cek sheet_id & share ke service account |
| `PERMISSION_DENIED` | Service account tidak punya akses | Share spreadsheet ke client_email |
| `AuthenticationError` | OpenAI API key salah/habis | Cek api_key di secrets.toml |
| `ModuleNotFoundError` | Dependencies belum terinstall | Jalankan `pip install -r requirements.txt` |
| `JSONDecodeError` | Format secrets.toml salah | Cek format TOML, terutama private_key |

---

## 📊 Format Data di Google Sheets

Aplikasi akan otomatis membuat baris header jika sheet kosong:

| Kolom | Keterangan |
|-------|-----------|
| Timestamp | Waktu input data |
| Nama Pelapor | Nama staf yang melaporkan |
| Booking ID | ID unik booking |
| Supplier | Platform/supplier booking |
| Hotel | Nama hotel |
| Check-in | Tanggal check-in (YYYY-MM-DD) |
| Check-out | Tanggal check-out (YYYY-MM-DD) |
| Nominal (Rp) | Nominal transaksi dalam rupiah |
| Kartu | Info kartu kredit |
| Metode Pembayaran | Direct Billing / Credit Card / dll. |
| Catatan | Keterangan tambahan |

---

## 📄 Lisensi

Internal use only — PT. [Nama Perusahaan]
