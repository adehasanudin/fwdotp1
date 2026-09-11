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

const PORT = process.env.PORT || process.env.WA_PORT || 4001;
const OTPS_FILE = path.join(__dirname, 'otps.json');
const DASHBOARD_PIN = process.env.DASHBOARD_PIN || '123456';

let sseClients = [];

// Helper to load OTP history
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

// Helper to save OTP history (Maksimal 9 OTP terbaru)
function saveOtps(otps) {
    try {
        fs.writeFileSync(OTPS_FILE, JSON.stringify(otps.slice(0, 9), null, 2));
    } catch (e) {
        console.error('[Web Server] Error saving otps.json:', e.message);
    }
}

let otpHistory = loadOtps().slice(0, 9);

// SSE Broadcast helper for real-time web clients
function broadcastSSE(data) {
    sseClients.forEach(client => {
        client.res.write(`data: ${JSON.stringify(data)}\n\n`);
    });
}

// 0. API Auth — verify dashboard PIN
app.post('/api/auth', (req, res) => {
    const { pin } = req.body;
    if (String(pin) === String(DASHBOARD_PIN)) {
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

app.get('/status', (req, res) => {
    return res.json({ status: 'online', port: PORT, connectedClients: sseClients.length, totalOtps: otpHistory.length });
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`\n===============================================================`);
    console.log(`🌐 WEB OTP DASHBOARD BERHASIL DIJALANKAN DI PORT ${PORT}`);
    console.log(`📌 AKSES WEBSITE: http://0.0.0.0:${PORT} (atau http://IP-VPS:${PORT})`);
    console.log(`===============================================================\n`);
});
