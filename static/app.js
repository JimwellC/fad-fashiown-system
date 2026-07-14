// app.js — TIKTOK Live Selling Dashboard.
// Facebook has its own console (static/facebook.js + /facebook page) so the two
// pipelines can never be confused mid-live. This file ignores Facebook events.
// Shared label/print machinery lives in static/print.js.

const socket = io();
let currentBuyer = '';
let commentCount = 0;

// ── CONNECTION EVENTS ──
socket.on('connect', function () {
    console.log('Connected to server');
    updateConnectionStatus(true);
    updateExtensionStatus(false);
    loadOrders();
    loadLabelSettings();   // from print.js
});

socket.on('disconnect', function () {
    console.log('Disconnected from server');
    updateConnectionStatus(false);
});

// ── BUYER DETECTED (TikTok only) ──
socket.on('buyer_detected', function (data) {
    if (data.platform === 'facebook') return;   // handled by the Facebook console
    if (data.username && data.username.trim() !== '') {
        setBuyer(data.username, data.detected_at);
        if (data.pinned) {
            showPinModal(data.username, data.message || '');
        }
    }
});

socket.on('order_saved', function (order) {
    if (order.platform === 'facebook') return;   // handled by the Facebook console
    prependOrder(order);
    showToast('Order saved!', 'success');
});

// ── NEW COMMENT (TikTok only) ──
socket.on('new_comment', function (data) {
    if (data.platform === 'facebook') return;   // handled by the Facebook console
    addComment(data);
    updateExtensionStatus(true);
});


// ── SET BUYER DISPLAY ──
function setBuyer(username, detectedAt) {
    currentBuyer = username;

    const usernameEl = document.getElementById('buyer-username');
    const timeEl = document.getElementById('buyer-time');
    const card = document.getElementById('buyer-card');

    usernameEl.textContent = '@' + username;
    timeEl.textContent = detectedAt ? 'Detected at ' + detectedAt : '';
    card.classList.add('active');

    // Auto-focus price field for fast typing
    document.getElementById('price').focus();
    console.log('Buyer set:', username);
}


// ── ADD COMMENT TO LIST ──
// renderComment (print.js) handles escaping, the 50-item cap, and click/dim.
function addComment(data) {
    renderComment('comments-list', data, function (d) {
        fetch('/api/set-buyer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: d.username })
        })
        .then(res => res.json())
        .then(result => {
            if (result.success) {
                showToast('Buyer set: @' + d.username, 'success');
                document.getElementById('price').focus();  // fast entry
            }
        })
        .catch(err => showToast('Error setting buyer', 'error'));
    });

    commentCount++;
    const countEl = document.getElementById('comment-count');
    if (countEl) countEl.textContent = commentCount;
}


// ── PRINT LABEL (TikTok) ──
function printLabel() {
    const price = document.getElementById('price').value.trim();

    if (!currentBuyer) {
        showToast('No buyer selected yet!', 'error');
        return;
    }

    if (!price || isNaN(price) || parseFloat(price) <= 0) {
        showToast('Please enter a valid price', 'error');
        document.getElementById('price').focus();
        return;
    }

    const printBtn = document.getElementById('print-btn');
    printBtn.disabled = true;
    printBtn.textContent = 'Saving...';

    fetch('/api/print-label', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            username: currentBuyer,
            item_name: '-',
            price: parseFloat(price),
            platform: 'tiktok'
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            fillLabelFields(currentBuyer, price, data.order.id);   // print.js
            setTimeout(() => silentPrint(), 300);                  // print.js

            setTimeout(() => {
                clearForm();
                resetCommentHighlights();
                showToast('Order saved and label printed!', 'success');
                printBtn.disabled = false;
                printBtn.textContent = 'Print Label';
            }, 1000);

        } else {
            showToast('Error: ' + (data.error || 'Unknown error'), 'error');
            printBtn.disabled = false;
            printBtn.textContent = 'Print Label';
        }
    })
    .catch(err => {
        showToast('Connection error. Try again.', 'error');
        printBtn.disabled = false;
        printBtn.textContent = 'Print Label';
    });
}


// ── RESET COMMENT HIGHLIGHTS ──
function resetCommentHighlights() {
    document.querySelectorAll('.comment-item').forEach(el => {
        el.style.opacity = '1';
        el.classList.remove('selected');
    });
}


// ── CLEAR FORM ──
function clearForm() {
    document.getElementById('price').value = '';
    document.getElementById('price').focus();
}


// ── MANUAL BUYER OVERRIDE ──
function setManualBuyer() {
    const input = document.getElementById('manual-username');
    const username = input.value.trim();

    if (!username) {
        showToast('Please enter a username', 'error');
        return;
    }

    fetch('/api/set-buyer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            input.value = '';
            showToast('Buyer set: @' + username, 'success');
        }
    })
    .catch(err => showToast('Error setting buyer', 'error'));
}


// ── LOAD ORDERS ──
function loadOrders() {
    fetch('/api/orders')
        .then(res => res.json())
        .then(orders => {
            const list = document.getElementById('orders-list');
            if (orders.length === 0) {
                list.innerHTML = '<div class="empty-state">No orders yet</div>';
                return;
            }
            list.innerHTML = '';
            orders.forEach(order => prependOrder(order, false));
        })
        .catch(err => console.error('Error loading orders:', err));
}


// ── ADD ORDER TO LIST ──
function prependOrder(order, animate = true) {
    const list = document.getElementById('orders-list');

    const emptyState = list.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const time = order.timestamp
        ? order.timestamp.split(' ')[1].substring(0, 5)
        : '';

    const div = document.createElement('div');
    div.className = 'order-item';
    if (!animate) div.style.animation = 'none';

    div.innerHTML = `
        <div>
            <div class="order-username">@${order.username}</div>
            <div class="order-id">#${order.id}</div>
        </div>
        <div>
            <div class="order-price">₱${parseFloat(order.price).toFixed(2)}</div>
            <div class="order-time">${time}</div>
        </div>
    `;

    list.insertBefore(div, list.firstChild);
}


// ── EXTENSION STATUS ──
function updateExtensionStatus(active) {
    const badge = document.getElementById('detection-status');
    if (!badge) return;
    if (active) {
        badge.textContent = 'Extension Active';
        badge.className = 'status-pill extension-on';
    } else {
        badge.textContent = 'Extension Inactive';
        badge.className = 'status-pill extension-off';
    }
}


// ── UI STATE HELPERS ──
function updateConnectionStatus(connected) {
    setConnectionStatus('connection-status', connected);   // print.js
}


// ── TOAST NOTIFICATIONS ──
// showToast is defined globally in base.html

document.addEventListener('DOMContentLoaded', function () {
    const pinPrice = document.getElementById('pin-modal-price');
    if (pinPrice) {
        pinPrice.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') printFromModal();
            if (e.key === 'Escape') closePinModal();
        });
    }
});

// ── KEYBOARD SHORTCUTS ──
document.addEventListener('DOMContentLoaded', function () {
    // Enter in price → print label
    document.getElementById('price').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            printLabel();
        }
    });

    // Enter in manual username → set buyer
    document.getElementById('manual-username').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            setManualBuyer();
        }
    });
});

// ── START PIN DETECTION (TikTok) ──
async function startPinDetection() {
    const btn = document.getElementById('pin-detect-btn');
    const statusEl = document.getElementById('pin-status');

    btn.disabled = true;
    btn.textContent = 'Connecting...';
    if (statusEl) statusEl.textContent = 'Connecting to TikTok...';

    try {
        const tiktokInput = document.getElementById('tiktok-username-input');
        const tiktokUsername = tiktokInput ? tiktokInput.value.trim().replace('@', '') : '';

        const res = await fetch('/api/start-pin-detection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tiktok_username_override: tiktokUsername })
        });
        const data = await res.json();

        if (data.success) {
            btn.textContent = 'Detection Active';
            btn.style.background = 'var(--green-dark)';
            btn.style.color = 'white';
            if (statusEl) statusEl.textContent = '✅ ' + data.message;
            showToast('Pin detection started!', 'success');
            // Show stop button
            const stopBtn = document.getElementById('pin-stop-btn');
            if (stopBtn) stopBtn.style.display = 'inline-block';
        } else {
            btn.disabled = false;
            btn.textContent = 'Start Pin Detection';
            if (statusEl) statusEl.textContent = '❌ ' + (data.error || 'Failed');
            showToast(data.error || 'Failed to start', 'error');
        }
    } catch(e) {
        btn.disabled = false;
        btn.textContent = 'Start Pin Detection';
        if (statusEl) statusEl.textContent = '❌ Connection error';
    }
}

// ── STOP PIN DETECTION (TikTok) ──
async function stopPinDetection() {
    const btn = document.getElementById('pin-detect-btn');
    const stopBtn = document.getElementById('pin-stop-btn');
    const statusEl = document.getElementById('pin-status');

    try {
        await fetch('/api/stop-pin-detection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
    } catch(e) {}

    // Reset UI
    btn.disabled = false;
    btn.textContent = 'Start';
    btn.style.background = '';
    btn.style.color = '';
    if (stopBtn) stopBtn.style.display = 'none';
    if (statusEl) statusEl.textContent = 'Detection stopped.';
    showToast('Pin detection stopped', 'success');
}

// ── PIN COMMENT MODAL (TikTok) ──
function showPinModal(username, message) {
    const modal = document.getElementById('pin-modal');
    const usernameEl = document.getElementById('pin-modal-username');
    const messageEl = document.getElementById('pin-modal-message');
    const priceEl = document.getElementById('pin-modal-price');

    usernameEl.textContent = '@' + username;
    messageEl.textContent = message ? '"' + message + '"' : '';
    priceEl.value = '';

    modal.style.display = 'flex';
    setTimeout(() => priceEl.focus(), 100);
}

function closePinModal() {
    document.getElementById('pin-modal').style.display = 'none';
}

function printFromModal() {
    const price = document.getElementById('pin-modal-price').value.trim();

    if (!price || isNaN(price) || parseFloat(price) <= 0) {
        document.getElementById('pin-modal-price').focus();
        showToast('Please enter a valid price', 'error');
        return;
    }

    document.getElementById('price').value = price;
    closePinModal();
    printLabel();
}
