// app.js - Fad Fashiown Dashboard Logic
// Handles real-time updates, form submission, and order display

// ── WEBSOCKET CONNECTION ──
const socket = io();

// Current buyer username (kept in memory)
let currentBuyer = '';

// ── CONNECTION EVENTS ──
socket.on('connect', function () {
    console.log('✅ Connected to server');
    updateConnectionStatus(true);
    loadOrders();
    checkDetectionStatus();
});

socket.on('disconnect', function () {
    console.log('❌ Disconnected from server');
    updateConnectionStatus(false);
});

// ── BUYER DETECTION EVENT ──
// This fires instantly when a new pinned comment is detected
socket.on('buyer_detected', function (data) {
    if (data.username && data.username.trim() !== '') {
        setBuyer(data.username, data.detected_at);
    }
});

// ── ORDER SAVED EVENT ──
// Fires when a new order is saved - updates the orders list
socket.on('order_saved', function (order) {
    prependOrder(order);
    showToast('✅ Order saved & label printed!', 'success');
});

// ── SET BUYER DISPLAY ──
function setBuyer(username, detectedAt) {
    currentBuyer = username;

    const usernameEl = document.getElementById('buyer-username');
    const timeEl = document.getElementById('buyer-time');
    const card = document.getElementById('buyer-card');

    usernameEl.textContent = '@' + username;
    timeEl.textContent = detectedAt ? 'Detected at ' + detectedAt : '';

    // Flash the card green to signal new detection
    card.classList.add('active');

    console.log('👤 Buyer set:', username);
}

// ── PRINT LABEL ──
function printLabel() {
    const itemName = document.getElementById('item-name').value.trim();
    const price = document.getElementById('price').value.trim();

    // Validate inputs
    if (!currentBuyer) {
        showToast('❌ No buyer detected yet!', 'error');
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

    // Disable print button to prevent double-clicking
    const printBtn = document.getElementById('print-btn');
    printBtn.disabled = true;
    printBtn.textContent = '⏳ Printing...';

    // Send to backend
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
        } else {
            showToast('❌ Error: ' + data.error, 'error');
        }
    })
    .catch(err => {
        showToast('❌ Connection error. Try again.', 'error');
        console.error(err);
    })
    .finally(() => {
        // Re-enable print button
        printBtn.disabled = false;
        printBtn.textContent = '🖨️ PRINT LABEL';
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
            showToast('✅ Buyer set manually: @' + username, 'success');
        }
    })
    .catch(err => {
        showToast('❌ Error setting buyer', 'error');
    });
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

    // Remove empty state if present
    const emptyState = list.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    // Format time to show only HH:MM
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

    // Add to top of list
    list.insertBefore(div, list.firstChild);
}

// ── DETECTION CONTROLS ──
function startDetection() {
    fetch('/api/detection/start', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            updateDetectionStatus(true);
            showToast('🔍 Detection started', 'success');
        });
}

function stopDetection() {
    fetch('/api/detection/stop', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            updateDetectionStatus(false);
            showToast('⏹️ Detection stopped', 'success');
        });
}

function checkDetectionStatus() {
    fetch('/api/detection/status')
        .then(res => res.json())
        .then(data => updateDetectionStatus(data.active));
}

// ── UI STATE HELPERS ──
function updateConnectionStatus(connected) {
    const el = document.getElementById('connection-status');
    if (connected) {
        el.textContent = '🟢 Connected';
        el.className = 'status-dot connected';
    } else {
        el.textContent = '🔴 Disconnected';
        el.className = 'status-dot disconnected';
    }
}

function updateDetectionStatus(active) {
    const badge = document.getElementById('detection-status');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');

    if (active) {
        badge.textContent = '🟢 Detection ON';
        badge.className = 'detection-badge on';
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        badge.textContent = '🔴 Detection OFF';
        badge.className = 'detection-badge off';
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

// ── TOAST NOTIFICATIONS ──
let toastTimeout;
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast ' + type;

    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        toast.className = 'toast hidden';
    }, 3000);
}

// ── KEYBOARD SHORTCUTS ──
// Press Enter in item name field → jump to price
document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('item-name').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            document.getElementById('price').focus();
        }
    });

    // Press Enter in price field → trigger print
    document.getElementById('price').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            printLabel();
        }
    });

    // Press Enter in manual username field → set buyer
    document.getElementById('manual-username').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            setManualBuyer();
        }
    });
});