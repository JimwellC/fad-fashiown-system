// app.js - Fad Fashiown Dashboard Logic
// Handles real-time updates, form submission, order display, and live comments

// ── WEBSOCKET CONNECTION ──
const socket = io();

// Current buyer username (kept in memory)
let currentBuyer = '';
let commentCount = 0;

// ── CONNECTION EVENTS ──
socket.on('connect', function () {
    console.log('✅ Connected to server');
    updateConnectionStatus(true);
    updateExtensionStatus(false); // Default off until comment received
    loadOrders();
});

socket.on('disconnect', function () {
    console.log('❌ Disconnected from server');
    updateConnectionStatus(false);
});

// ── BUYER DETECTED EVENT ──
socket.on('buyer_detected', function (data) {
    if (data.username && data.username.trim() !== '') {
        setBuyer(data.username, data.detected_at);
    }
});

// ── ORDER SAVED EVENT ──
socket.on('order_saved', function (order) {
    prependOrder(order);
    showToast('✅ Order saved!', 'success');
});

// ── NEW COMMENT EVENT ──
// Fires every time someone comments on TikTok Live
socket.on('new_comment', function (data) {
    addComment(data);
    updateExtensionStatus(true); // Mark extension as active

    if (data.is_buyer) {
        setBuyer(data.username, new Date().toLocaleTimeString());
        showToast('🛒 Buyer: @' + data.username, 'success');
    }
});


// ── SET BUYER DISPLAY ──
function setBuyer(username, detectedAt) {
    currentBuyer = username;

    const usernameEl = document.getElementById('buyer-username');
    const timeEl = document.getElementById('buyer-time');
    const card = document.getElementById('buyer-card');

    usernameEl.textContent = '@' + username;
    timeEl.textContent = detectedAt ? 'Detected at ' + detectedAt : '';

    // Flash green to signal new buyer
    card.classList.add('active');

    // Auto-focus item name field for fast typing
    document.getElementById('item-name').focus();

    console.log('👤 Buyer set:', username);
}


// ── ADD COMMENT TO LIST ──
function addComment(data) {
    const list = document.getElementById('comments-list');
    if (!list) return;

    // Remove empty state
    const empty = list.querySelector('.empty-state');
    if (empty) empty.remove();

    // Keep only last 50 comments for performance
    const existing = list.querySelectorAll('.comment-item');
    if (existing.length >= 50) {
        existing[existing.length - 1].remove();
    }

    // Update comment counter
    commentCount++;
    const countEl = document.getElementById('comment-count');
    if (countEl) countEl.textContent = commentCount;

    // Create comment element
    const div = document.createElement('div');
    div.className = 'comment-item' + (data.is_buyer ? ' buyer' : '');

    div.innerHTML = `
        <div class="comment-username">@${data.username}</div>
        <div class="comment-message">${data.message}</div>
        <div class="comment-click-hint">
            ${data.is_buyer ? '🛒 Click to confirm as buyer' : '👆 Click to select as buyer'}
        </div>
    `;

    // Click to manually set as buyer
    div.addEventListener('click', function () {
        // Set as buyer
        fetch('/api/set-buyer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: data.username })
        })
        .then(res => res.json())
        .then(result => {
            if (result.success) {
                showToast('✅ Buyer set: @' + data.username, 'success');

                // Dim all comments, highlight selected
                document.querySelectorAll('.comment-item').forEach(el => {
                    el.style.opacity = '0.4';
                });
                div.style.opacity = '1';
                div.classList.add('selected');

                // Focus item name for fast entry
                document.getElementById('item-name').focus();
            }
        })
        .catch(err => showToast('❌ Error setting buyer', 'error'));
    });

    // Add to TOP of list (newest first)
    list.insertBefore(div, list.firstChild);
}


// ── PRINT LABEL ──
function printLabel() {
    const itemName = document.getElementById('item-name').value.trim();
    const price = document.getElementById('price').value.trim();

    if (!currentBuyer) {
        showToast('❌ No buyer selected yet!', 'error');
        return;
    }

    if (!itemName) {
        showToast('❌ Please enter item name', 'error');
        document.getElementById('item-name').focus();
        return;
    }

    if (!price || isNaN(price) || parseFloat(price) <= 0) {
        showToast('❌ Please enter a valid price', 'error');
        document.getElementById('price').focus();
        return;
    }

    const printBtn = document.getElementById('print-btn');
    printBtn.disabled = true;
    printBtn.textContent = '⏳ Printing...';

    fetch('/api/print-label', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            username: currentBuyer,
            item_name: itemName,
            price: parseFloat(price)
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast('✅ Label printed! Ready for next buyer.', 'success');
            clearForm();
            resetCommentHighlights();
        } else {
            showToast('❌ Error: ' + data.error, 'error');
        }
    })
    .catch(err => {
        showToast('❌ Connection error. Try again.', 'error');
    })
    .finally(() => {
        printBtn.disabled = false;
        printBtn.textContent = '🖨️ PRINT LABEL';
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
    document.getElementById('item-name').value = '';
    document.getElementById('price').value = '';
    document.getElementById('item-name').focus();
}


// ── MANUAL BUYER OVERRIDE ──
function setManualBuyer() {
    const input = document.getElementById('manual-username');
    const username = input.value.trim();

    if (!username) {
        showToast('❌ Please enter a username', 'error');
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
            showToast('✅ Buyer set: @' + username, 'success');
        }
    })
    .catch(err => showToast('❌ Error setting buyer', 'error'));
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
            <div class="order-item-name">${order.item_name}</div>
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
    const el = document.getElementById('connection-status');
    if (connected) {
        el.textContent = 'Connected';
        el.className = 'status-pill connected';
    } else {
        el.textContent = 'Disconnected';
        el.className = 'status-pill disconnected';
    }
}


// ── TOAST NOTIFICATIONS ──
let toastTimeout;
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    // Remove common emojis from messages
    message = message.replace(/[✅❌🛒🖨️⏳]/g, '').trim();
    toast.textContent = message;
    toast.className = 'toast ' + type;
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        toast.className = 'toast hidden';
    }, 3000);
}


// ── KEYBOARD SHORTCUTS ──
document.addEventListener('DOMContentLoaded', function () {
    // Enter in item name → jump to price
    document.getElementById('item-name').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            document.getElementById('price').focus();
        }
    });

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