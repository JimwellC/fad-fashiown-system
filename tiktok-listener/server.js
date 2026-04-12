// tiktok-listener/server.js
const { TikTokLiveConnection, WebcastEvent, ControlEvent } = require('tiktok-live-connector');
const express = require('express');
const app = express();
app.use(express.json());

const connections = {};

// ── START LISTENING ──
app.post('/start', async (req, res) => {
    const { tiktok_username, client_token, flask_url } = req.body;

    if (!tiktok_username || !client_token) {
        return res.json({ error: 'Missing tiktok_username or client_token' });
    }

    // Stop existing connection
    if (connections[client_token]) {
        try { connections[client_token].disconnect(); } catch(e) {}
    }

    console.log(`Connecting to @${tiktok_username}...`);

    const tiktokConn = new TikTokLiveConnection(tiktok_username);
    connections[client_token] = tiktokConn;

    // ── PINNED COMMENT EVENT ──
    tiktokConn.on(WebcastEvent.ROOM_PIN, (data) => {
        console.log('📌 Pin event received:', JSON.stringify(data).substring(0, 200));

        const chatText = data.chatMessage?.comment;
        const username = data.chatMessage?.user?.uniqueId
            || data.chatMessage?.user?.nickname
            || data.operator?.uniqueId;

        if (chatText && username) {
            console.log(`📌 Pinned: @${username}: "${chatText}"`);

            fetch(`${flask_url}/api/pinned-comment`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: username,
                    message: chatText,
                    token: client_token
                })
            }).catch(err => console.error('Flask error:', err));
        }
    });

    // ── COMMENT EVENT ──
    tiktokConn.on(WebcastEvent.CHAT, (data) => {
        const username = data.user?.uniqueId || data.uniqueId;
        const message = data.comment;

        if (username && message) {
            fetch(`${flask_url}/api/new-comment`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: username,
                    message: message,
                    is_buyer: false,
                    token: client_token
                })
            }).catch(err => console.error('Flask error:', err));
        }
    });

    // ── CONNECTION EVENTS ──
    tiktokConn.on(ControlEvent.CONNECTED, (state) => {
        console.log(`✅ Connected to @${tiktok_username}`, state);
    });

    tiktokConn.on(ControlEvent.DISCONNECTED, () => {
        console.log(`❌ Disconnected from @${tiktok_username}`);
    });

    tiktokConn.on(ControlEvent.ERROR, (err) => {
        console.error(`Error:`, err);
    });

    try {
        await tiktokConn.connect();
        res.json({ success: true, message: `Connected to @${tiktok_username}` });
    } catch(err) {
        const errMsg = err.message || String(err);
        console.error('Connection error:', errMsg);

        // Clean up failed connection
        delete connections[client_token];

        // Detect offline error
        if (errMsg.toLowerCase().includes('offline') ||
            errMsg.toLowerCase().includes('isn\'t online')) {
            return res.json({
                error: `@${tiktok_username} is not live right now. Go live first then try again.`
            });
        }

        res.json({ error: errMsg });
    }
});

// ── STOP LISTENING ──
app.post('/stop', (req, res) => {
    const { client_token } = req.body;
    if (connections[client_token]) {
        connections[client_token].disconnect();
        delete connections[client_token];
    }
    res.json({ success: true });
});

// ── STATUS ──
app.get('/status', (req, res) => {
    res.json({
        active_connections: Object.keys(connections).length,
        connections: Object.keys(connections)
    });
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`TikTok Listener running on port ${PORT}`);
});