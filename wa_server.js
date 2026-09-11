const express = require('express');
const path = require('path');
const fs = require('fs');
try {
    require('dotenv').config();
} catch (e) {
    // dotenv optional fallback
}

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Admin Secret Path — hanya bisa diakses via URL rahasia
const ADMIN_SECRET = process.env.ADMIN_SECRET || 'admin-secret-elzoi';
app.get(`/admin-${ADMIN_SECRET}`, (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});
// Block public /admin route
app.get('/admin', (req, res) => {
    return res.status(404).send('Not Found');
});

const PORT = process.env.PORT || process.env.WA_PORT || 4001;
const OTPS_FILE = path.join(__dirname, 'otps.json');
const SETTINGS_FILE = path.join(__dirname, 'settings.json');

let sseClients = [];

function loadOtps() {
    if (fs.existsSync(OTPS_FILE)) {
        try {
            return JSON.parse(fs.readFileSync(OTPS_FILE, 'utf-8'));
        } catch (e) {
            console.error('[Web Server] Error reading otps.json:', e.message);
        }
    }
    return [];
}

function saveOtps(otps) {
    try {
        fs.writeFileSync(OTPS_FILE, JSON.stringify(otps.slice(0, 9), null, 2));
    } catch (e) {
        console.error('[Web Server] Error saving otps.json:', e.message);
    }
}

let otpHistory = loadOtps().slice(0, 9);

function broadcastSSE(data) {
    sseClients.forEach(client => {
        client.res.write(`data: ${JSON.stringify(data)}\n\n`);
    });
}

function loadSettings() {
    let settings;
    if (fs.existsSync(SETTINGS_FILE)) {
        try {
            settings = JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf-8'));
        } catch (e) {
            console.error('[Web Server] Error reading settings.json:', e.message);
        }
    }
    if (!settings) {
        settings = {
            pin: process.env.DASHBOARD_PIN || '123456',
            sources: [
                { id: '-1003976311793', name: 'Atmosphere Sms', enabled: true },
                { id: '-1003845779628', name: 'Otp quin', enabled: true }
            ]
        };
        saveSettings(settings);
        console.log('[Web Server] settings.json dibuat baru dari default .env');
    }
    return settings;
}

function saveSettings(settings) {
    try {
        fs.writeFileSync(SETTINGS_FILE, JSON.stringify(settings, null, 2));
    } catch (e) {
        console.error('[Web Server] Error saving settings.json:', e.message);
    }
}

// 0. API Auth — verify dashboard PIN
app.post('/api/auth', (req, res) => {
    const { pin } = req.body;
    const settings = loadSettings();
    if (String(pin) === String(settings.pin)) {
        return res.json({ ok: true });
    }
    return res.status(401).json({ ok: false, message: 'PIN salah' });
});

// 1. API GET OTPs history
app.get('/api/otps', (req, res) => {
    return res.json(otpHistory);
});

// 2. API DELETE OTPs history
app.delete('/api/otps', (req, res) => {
    otpHistory = [];
    saveOtps(otpHistory);
    return res.json({ status: 'cleared' });
});

// 3. SSE Endpoint for Real-time push to web dashboard
app.get('/api/events', (req, res) => {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.flushHeaders();

    const clientId = Date.now();
    const newClient = { id: clientId, res };
    sseClients.push(newClient);

    req.on('close', () => {
        sseClients = sseClients.filter(client => client.id !== clientId);
    });
});

// 4. API POST OTP (From Telegram Python Userbot main.py)
app.post('/api/otp', (req, res) => {
    try {
        const { otp, vcc, merchant, amount, raw_text } = req.body;
        if (!otp && !raw_text) {
            return res.status(400).json({ status: 'error', message: 'OTP or raw_text is required.' });
        }

        const now = new Date();
        const timeStr = now.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        const otpItem = {
            id: Date.now(),
            otp: otp || '??????',
            vcc: vcc || '?',
            merchant: merchant || '?',
            amount: amount || '?',
            raw_text: raw_text || '',
            copied: false,
            time: timeStr,
            date: now.toISOString()
        };

        // Save to memory and JSON file (Max 9 OTPs)
        otpHistory.unshift(otpItem);
        if (otpHistory.length > 9) {
            otpHistory = otpHistory.slice(0, 9);
        }
        saveOtps(otpHistory);

        // Broadcast real-time update to open web browsers
        broadcastSSE({ type: 'new_otp', data: otpItem });
        console.log(`[Web Dashboard] 🔔 OTP Baru Diterima & Pushed ke Web: ${otpItem.otp} (${otpItem.merchant})`);

        return res.json({ status: 'success', data: otpItem });
    } catch (err) {
        console.error('[API Error]:', err);
        return res.status(500).json({ status: 'error', message: err.message });
    }
});

// 5. API POST Mark OTP as Copied Globally (Synchronize to all visitors)
app.post('/api/otp/:id/copy', (req, res) => {
    const id = req.params.id;
    const item = otpHistory.find(o => String(o.id) === String(id));
    if (item) {
        item.copied = true;
        saveOtps(otpHistory);
        broadcastSSE({ type: 'otp_copied', id: item.id });
        console.log(`[Web Dashboard] 📋 OTP ${item.otp} disalin oleh pengunjung, menyamakan ke seluruh visitor`);
        return res.json({ status: 'success', id: item.id });
    }
    return res.status(404).json({ status: 'error', message: 'OTP tidak ditemukan' });
});

// 6. Admin API Settings
app.get('/api/settings', (req, res) => {
    const settings = loadSettings();
    return res.json({ ok: true, sources: settings.sources });
});

// Add new Telegram channel source
app.post('/api/settings/sources', (req, res) => {
    const { id, name } = req.body;
    if (!id || !name) {
        return res.status(400).json({ ok: false, message: 'ID/Username dan Nama Channel wajib diisi' });
    }
    const settings = loadSettings();
    const cleanId = String(id).trim();
    const cleanName = String(name).trim();
    const exists = settings.sources.find(s => String(s.id).toLowerCase() === cleanId.toLowerCase());
    if (exists) {
        return res.status(400).json({ ok: false, message: 'Sumber channel ini sudah terdaftar' });
    }
    settings.sources.push({ id: cleanId, name: cleanName, enabled: true });
    saveSettings(settings);
    return res.json({ ok: true, sources: settings.sources });
});

// Toggle channel source ON/OFF
app.put('/api/settings/sources/:id/toggle', (req, res) => {
    const id = decodeURIComponent(req.params.id);
    const settings = loadSettings();
    const source = settings.sources.find(s => String(s.id) === String(id));
    if (!source) {
        return res.status(404).json({ ok: false, message: 'Sumber channel tidak ditemukan' });
    }
    source.enabled = !source.enabled;
    saveSettings(settings);
    return res.json({ ok: true, source, sources: settings.sources });
});

// Delete channel source
app.delete('/api/settings/sources/:id', (req, res) => {
    const id = decodeURIComponent(req.params.id);
    const settings = loadSettings();
    settings.sources = settings.sources.filter(s => String(s.id) !== String(id));
    saveSettings(settings);
    return res.json({ ok: true, sources: settings.sources });
});

// Change 6-Digit PIN
app.post('/api/settings/pin', (req, res) => {
    const { oldPin, newPin } = req.body;
    const settings = loadSettings();
    if (String(oldPin) !== String(settings.pin)) {
        return res.status(400).json({ ok: false, message: 'PIN Lama salah' });
    }
    if (!newPin || String(newPin).length !== 6 || !/^\d+$/.test(String(newPin))) {
        return res.status(400).json({ ok: false, message: 'PIN Baru harus berupa 6 digit angka' });
    }
    settings.pin = String(newPin);
    saveSettings(settings);

    // Broadcast SSE to force logout all active sessions immediately
    broadcastSSE({ type: 'pin_changed' });
    console.log(`[Web Dashboard] 🔑 PIN telah diubah. Memutus seluruh sesi aktif.`);

    return res.json({ ok: true, message: 'PIN 6-digit berhasil diperbarui' });
});


app.get('/status', (req, res) => {
    return res.json({ status: 'online', port: PORT, connectedClients: sseClients.length, totalOtps: otpHistory.length });
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`\n===============================================================`);
    console.log(`🌐 WEB OTP DASHBOARD BERHASIL DIJALANKAN DI PORT ${PORT}`);
    console.log(`📌 AKSES WEBSITE: http://0.0.0.0:${PORT} (atau http://IP-VPS:${PORT})`);
    console.log(`===============================================================\n`);
});

