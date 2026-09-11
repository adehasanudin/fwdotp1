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
            user_pin: '123456',
            admin_pin: process.env.DASHBOARD_PIN || '888999',
            sources: [
                { id: '-1003976311793', name: 'Atmosphere Sms', enabled: true },
                { id: '-1003845779628', name: 'Otp quin', enabled: true }
            ]
        };
        saveSettings(settings);
    } else {
        let changed = false;
        if (settings.pin) {
            settings.admin_pin = settings.admin_pin || settings.pin || '888999';
            settings.user_pin = settings.user_pin && settings.user_pin !== settings.pin ? settings.user_pin : '123456';
            delete settings.pin;
            changed = true;
        }
        if (!settings.user_pin) {
            settings.user_pin = '123456';
            changed = true;
        }
        if (!settings.admin_pin) {
            settings.admin_pin = '888999';
            changed = true;
        }
        if (changed) {
            saveSettings(settings);
            console.log(`[Web Server] ✅ Migration settings.json: User PIN=${settings.user_pin}, Admin PIN=${settings.admin_pin}`);
        }
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

// Middleware untuk memverifikasi PIN Admin di endpoint /api/settings/*
function requireAdminPin(req, res, next) {
    const settings = loadSettings();
    const adminPinHeader = req.headers['x-admin-pin'] || req.body?.adminPin;
    if (!adminPinHeader || String(adminPinHeader) !== String(settings.admin_pin)) {
        return res.status(403).json({ ok: false, message: 'Akses Ditolak: Membutuhkan PIN Admin' });
    }
    next();
}

// 0. API Auth — verify dashboard PIN (User vs Admin)
app.post('/api/auth', (req, res) => {
    const { pin } = req.body;
    const settings = loadSettings();
    const cleanPin = String(pin).trim();

    if (cleanPin === String(settings.admin_pin)) {
        return res.json({ ok: true, role: 'admin' });
    }
    if (cleanPin === String(settings.user_pin)) {
        return res.json({ ok: true, role: 'user' });
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

// 6. Admin API Settings (Membutuhkan middleware requireAdminPin)
app.get('/api/settings', requireAdminPin, (req, res) => {
    const settings = loadSettings();
    return res.json({
        ok: true,
        sources: settings.sources,
        user_pin: settings.user_pin,
        admin_pin: settings.admin_pin
    });
});

// Add new Telegram channel source
app.post('/api/settings/sources', requireAdminPin, (req, res) => {
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
app.put('/api/settings/sources/:id/toggle', requireAdminPin, (req, res) => {
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
app.delete('/api/settings/sources/:id', requireAdminPin, (req, res) => {
    const id = decodeURIComponent(req.params.id);
    const settings = loadSettings();
    settings.sources = settings.sources.filter(s => String(s.id) !== String(id));
    saveSettings(settings);
    return res.json({ ok: true, sources: settings.sources });
});

// Change 6-Digit PIN (User or Admin)
app.post('/api/settings/pin', requireAdminPin, (req, res) => {
    const { targetPin, newPin } = req.body; // targetPin: 'user' | 'admin'
    const settings = loadSettings();

    if (!newPin || String(newPin).length !== 6 || !/^\d+$/.test(String(newPin))) {
        return res.status(400).json({ ok: false, message: 'PIN Baru harus 6 digit angka' });
    }

    if (targetPin === 'user') {
        settings.user_pin = String(newPin);
    } else if (targetPin === 'admin') {
        settings.admin_pin = String(newPin);
    } else {
        return res.status(400).json({ ok: false, message: 'Jenis PIN tidak valid' });
    }

    saveSettings(settings);

    // Broadcast SSE to force logout all active sessions immediately
    broadcastSSE({ type: 'pin_changed' });
    console.log(`[Web Dashboard] 🔑 PIN ${targetPin.toUpperCase()} telah diubah. Memutus seluruh sesi aktif.`);

    return res.json({
        ok: true,
        message: `PIN ${targetPin === 'admin' ? 'Admin' : 'Pengunjung'} berhasil diperbarui!`
    });
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

