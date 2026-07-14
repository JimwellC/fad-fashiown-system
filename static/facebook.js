// facebook.js — FACEBOOK Live Selling console (/facebook).
// Completely separate pipeline from the TikTok dashboard: this file ignores
// TikTok events, and app.js ignores Facebook events.
// Shared label/print machinery lives in static/print.js.

const fbSocket = io();
let fbCurrentBuyer = '';
let fbCurrentCommentId = null;
let fbCurrentPsid = null;
let fbCommentCount = 0;

// ── CONNECTION ──
fbSocket.on('connect', function () {
    updateFbConnectionStatus(true);
    loadLabelSettings();   // from print.js
});

fbSocket.on('disconnect', function () {
    updateFbConnectionStatus(false);
});

// ── NEW COMMENT (Facebook only) ──
fbSocket.on('new_comment', function (data) {
    if (data.platform !== 'facebook') return;   // TikTok handled by the dashboard
    addFbComment(data);
});

// ── AUTO-MESSAGE STATUS (from the batched Private Reply send) ──
fbSocket.on('fb_message_status', function (data) {
    addMessageLog(data);
    if (data.sent) {
        showToast('Messenger message sent to @' + data.buyer, 'success');
    } else {
        showToast('Messenger message failed for @' + data.buyer, 'error');
    }
});


// ── COMMENT LIST ──
function addFbComment(data) {
    const list = document.getElementById('fb-comments-list');
    if (!list) return;

    const empty = list.querySelector('.empty-state');
    if (empty) empty.remove();

    const existing = list.querySelectorAll('.comment-item');
    if (existing.length >= 50) existing[existing.length - 1].remove();

    fbCommentCount++;
    const countEl = document.getElementById('fb-comment-count');
    if (countEl) countEl.textContent = fbCommentCount;

    const div = document.createElement('div');
    div.className = 'comment-item' + (data.is_buyer ? ' buyer' : '');
    div.innerHTML = `
        <div class="comment-username">@${data.username}</div>
        <div class="comment-message">${data.message}</div>
        <div class="comment-click-hint">Click to select as buyer</div>
    `;

    div.addEventListener('click', function () {
        selectFbBuyer(data.username, data.comment_id, data.from_id);
        document.querySelectorAll('#fb-comments-list .comment-item')
            .forEach(el => { el.style.opacity = '0.4'; });
        div.style.opacity = '1';
        div.classList.add('selected');
    });

    list.insertBefore(div, list.firstChild);
}


// ── SELECT BUYER ──
function selectFbBuyer(username, commentId, psid) {
    fbCurrentBuyer = username;
    fbCurrentCommentId = commentId || null;
    fbCurrentPsid = psid || null;

    document.getElementById('fb-buyer-username').textContent = '@' + username;
    document.getElementById('fb-buyer-card').classList.add('active');

    // Warn early if we have no way to message this buyer.
    const warn = document.getElementById('fb-buyer-warning');
    if (warn) {
        if (!fbCurrentCommentId && !fbCurrentPsid) {
            warn.style.display = 'block';
            warn.textContent = 'No comment ID for this buyer — auto-message will fail.';
        } else {
            warn.style.display = 'none';
        }
    }

    showToast('Buyer set: @' + username, 'success');
    document.getElementById('fb-price').focus();
}


// ── PRINT LABEL + SCHEDULE AUTO-MESSAGE ──
function fbPrintLabel() {
    const price = document.getElementById('fb-price').value.trim();

    if (!fbCurrentBuyer) {
        showToast('No buyer selected yet!', 'error');
        return;
    }
    if (!price || isNaN(price) || parseFloat(price) <= 0) {
        showToast('Please enter a valid price', 'error');
        document.getElementById('fb-price').focus();
        return;
    }

    const btn = document.getElementById('fb-print-btn');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    fetch('/api/print-label', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            username: fbCurrentBuyer,
            item_name: '-',
            price: parseFloat(price),
            platform: 'facebook',
            comment_id: fbCurrentCommentId,
            psid: fbCurrentPsid
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            fillLabelFields(fbCurrentBuyer, price, data.order.id);   // print.js
            setTimeout(() => silentPrint(), 300);                    // print.js

            setTimeout(() => {
                document.getElementById('fb-price').value = '';
                document.getElementById('fb-price').focus();
                document.querySelectorAll('#fb-comments-list .comment-item')
                    .forEach(el => { el.style.opacity = '1'; el.classList.remove('selected'); });
                showToast('Order saved — message queued for @' + fbCurrentBuyer, 'success');
                btn.disabled = false;
                btn.textContent = 'Print Label';
            }, 1000);
        } else {
            showToast('Error: ' + (data.error || 'Unknown error'), 'error');
            btn.disabled = false;
            btn.textContent = 'Print Label';
        }
    })
    .catch(() => {
        showToast('Connection error. Try again.', 'error');
        btn.disabled = false;
        btn.textContent = 'Print Label';
    });
}


// ── MESSAGE LOG ──
function addMessageLog(data) {
    const list = document.getElementById('fb-message-log');
    if (!list) return;
    const empty = list.querySelector('.empty-state');
    if (empty) empty.remove();

    const div = document.createElement('div');
    div.className = 'order-item';
    const count = (data.order_ids || []).length;
    div.innerHTML = `
        <div>
            <div class="order-username">@${data.buyer}</div>
            <div class="order-id">${count} item${count === 1 ? '' : 's'} in one message</div>
        </div>
        <div>
            <span class="badge ${data.sent ? 'badge-success' : ''}"
                  style="${data.sent ? '' : 'background:#FDECEC;color:#C0392B;border:1px solid #F5C6C6'}">
                ${data.sent ? 'Sent' : 'Failed'}
            </span>
        </div>
    `;
    list.insertBefore(div, list.firstChild);
}


// ── DETECTION START/STOP ──
async function startFacebookDetection() {
    const btn = document.getElementById('fb-detect-btn');
    const stopBtn = document.getElementById('fb-stop-btn');
    const statusEl = document.getElementById('fb-status');

    btn.disabled = true;
    btn.textContent = 'Connecting...';
    if (statusEl) statusEl.textContent = 'Connecting to Facebook Live...';

    try {
        const res = await fetch('/api/facebook/start-detection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();

        if (data.success) {
            btn.textContent = 'Detection Active';
            btn.style.background = 'var(--green-dark)';
            btn.style.color = 'white';
            if (stopBtn) stopBtn.style.display = 'inline-block';
            if (statusEl) statusEl.textContent = '✅ ' + data.message;
            showToast('Facebook detection started!', 'success');
        } else {
            btn.disabled = false;
            btn.textContent = 'Start Detection';
            if (statusEl) statusEl.textContent = '❌ ' + (data.error || 'Failed');
            showToast(data.error || 'Failed to start', 'error');
        }
    } catch (e) {
        btn.disabled = false;
        btn.textContent = 'Start Detection';
        if (statusEl) statusEl.textContent = '❌ Connection error';
    }
}

async function stopFacebookDetection() {
    const btn = document.getElementById('fb-detect-btn');
    const stopBtn = document.getElementById('fb-stop-btn');
    const statusEl = document.getElementById('fb-status');

    try {
        await fetch('/api/facebook/stop-detection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
    } catch (e) {}

    btn.disabled = false;
    btn.textContent = 'Start Detection';
    btn.style.background = '';
    btn.style.color = '';
    if (stopBtn) stopBtn.style.display = 'none';
    if (statusEl) statusEl.textContent = 'Detection stopped. Pending messages were sent.';
    showToast('Facebook detection stopped', 'success');
}


// ── UI HELPERS ──
function updateFbConnectionStatus(connected) {
    const el = document.getElementById('fb-connection-status');
    if (!el) return;
    el.textContent = connected ? 'Connected' : 'Disconnected';
    el.className = 'status-pill ' + (connected ? 'connected' : 'disconnected');
}

document.addEventListener('DOMContentLoaded', function () {
    const priceEl = document.getElementById('fb-price');
    if (priceEl) {
        priceEl.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') fbPrintLabel();
        });
    }

    // Restore detection state if the consumer is already running
    fetch('/api/facebook/status')
        .then(r => r.json())
        .then(d => {
            if (d.running) {
                const btn = document.getElementById('fb-detect-btn');
                const stopBtn = document.getElementById('fb-stop-btn');
                const statusEl = document.getElementById('fb-status');
                if (btn) {
                    btn.disabled = true;
                    btn.textContent = 'Detection Active';
                    btn.style.background = 'var(--green-dark)';
                    btn.style.color = 'white';
                }
                if (stopBtn) stopBtn.style.display = 'inline-block';
                if (statusEl) statusEl.textContent = '✅ Listening to your Facebook Live';
            }
        })
        .catch(() => {});
});
