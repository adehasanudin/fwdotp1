# Telegram Auto Forwarder Bot (Atmosphere Sms & Channel OTP)

Bot Telegram Userbot berbasis Python menggunakan library **Pyrogram** untuk meneruskan (forward/copy) pesan SMS OTP dari channel/grup sumber (seperti **Atmosphere Sms**) ke bot Telegram target atau user Telegram tertentu secara otomatis dan real-time.

---

## 📌 Fitur Utama

- ⚡ **Real-time Forwarding**: Meneruskan pesan secara instan saat pesan SMS OTP baru masuk.
- 📱 **Telegram Userbot**: Dapat membaca channel/grup mana saja tempat akun Anda bergabung (tanpa perlu dijadikan admin channel).
- 🧹 **Mode Clean Copy (`FORWARD_MODE=copy`)**: Mengirim teks pesan tanpa header "Forwarded from..." sehingga tampak bersih.
- 🔄 **Mode Telegram Forward (`FORWARD_MODE=forward`)**: Meneruskan pesan dengan header forward Telegram asli.
- 🎯 **Multi-Target & Multi-Source**: Bisa meneruskan dari banyak channel ke banyak target sekaligus.
- 🔍 **Filter Kata Kunci (Optional)**: Meneruskan pesan yang mengandung kata kunci tertentu saja (misal `Visa`, `PAYPAL`, `DISCORD`).
- 🛡️ **FloodWait Auto-Retry**: Menangani pembatasan rate-limit dari Telegram secara otomatis.
- 📋 **Script Helper `get_chat_id.py`**: Memudahkan melihat daftar seluruh Chat ID akun Telegram Anda.

---

## 🛠️ Prasyarat

1. **Python 3.8+** terinstal di komputer/VPS.
2. **Akun Telegram** aktif.
3. **API_ID & API_HASH** Telegram.

---

## 🚀 Langkah Instalasi & Konfigurasi

### 1. Cara Mendapatkan API_ID dan API_HASH Telegram

1. Buka situs resmi Telegram: [https://my.telegram.org](https://my.telegram.org)
2. Masukkan nomor telepon akun Telegram Anda (format internasional, misal: `+6281234567890`).
3. Masukkan kode konfirmasi yang dikirimkan ke aplikasi Telegram Anda.
4. Pilih menu **API Development Tools**.
5. Isi formulir singkat (Title & Short Name bisa diisi bebas, contoh: `MyForwarderBot`).
6. Anda akan mendapatkan **`App api_id`** (berupa angka) dan **`App api_hash`** (berupa string acak).

---

### 2. Install Dependency

Jalankan perintah berikut di terminal:

```bash
pip install -r requirements.txt
```

---

### 3. Cek Chat ID dengan `get_chat_id.py`

Sebelum mengatur file `.env`, Anda perlu membuat file `.env` terlebih dahulu dan mengisi `API_ID` & `API_HASH`:

```bash
cp .env.example .env
```

Buka file `.env` dan isi `API_ID` serta `API_HASH`. Kemudian jalankan:

```bash
python3 get_chat_id.py
```

- Pada eksekusi pertama, Anda akan diminta memasukkan nomor telepon dan kode OTP Telegram untuk verifikasi login.
- Script akan menampilkan daftar channel, grup, dan chat beserta **CHAT ID**-nya.
- Cari nama channel sumber (contoh: **Atmosphere Sms**) dan salin **CHAT ID**-nya (misal: `-1001987654321`).
- Cari nama bot target atau user target dan salin **CHAT ID** atau **USERNAME**-nya.

---

### 4. Konfigurasi File `.env`

Edit file `.env` dan sesuaikan nilainya:

```env
# Telegram API Credentials
API_ID=12345678
API_HASH=abcdef0123456789abcdef0123456789

# Nomor Telepon (opsional)
PHONE_NUMBER=+6281234567890

# Source Chat ID (Channel Atmosphere Sms / sumber pesan)
SOURCE_CHAT_ID=-1001987654321

# Target Chat ID / Username (Bot target atau User Telegram tujuan)
TARGET_CHAT_ID=@NamaBotTargetSaya

# Mode Forwarding ('copy' untuk salinan bersih, 'forward' untuk tag forward)
FORWARD_MODE=copy

# Filter kata kunci (Kosongkan untuk meneruskan SEMUA pesan)
KEYWORDS=
```

---

### 5. Jalankan Userbot

Untuk menjalankan userbot:

```bash
python3 main.py
```

Userbot akan aktif dan mendengarkan setiap pesan SMS OTP yang masuk di channel Atmosphere Sms lalu meneruskannya secara otomatis ke bot/user target.

---

## 🏃 Running 24/7 di Background (VPS / Server)

Agar bot tetap berjalan meskipun terminal ditutup:

### Menggunakan PM2 (Direkomendasikan):

```bash
npm install -g pm2
pm2 start main.py --name "telegram-forwarder" --interpreter python3
pm2 save
```

### Menggunakan Nohup:

```bash
nohup python3 main.py > bot.log 2>&1 &
```

---

## ❓ Troubleshooting & FAQ

- **Bagaimana jika pesan tidak diteruskan?**
  Pastikan `SOURCE_CHAT_ID` dan `TARGET_CHAT_ID` sudah benar. Gunakan Chat ID angka (contoh: `-100...`) yang diperoleh dari `python3 get_chat_id.py`.
- **Apakah akun saya aman?**
  Script ini menggunakan library resmi Pyrogram. File sesi (`userbot_session.session`) disimpan secara lokal di folder project Anda dan tidak dikirim ke pihak mana pun.
# fwdotp1
