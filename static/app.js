// ── QZ TRAY SECURITY ──
document.addEventListener('DOMContentLoaded', function() {
    if (typeof qz !== 'undefined') {
        qz.security.setCertificatePromise(function(resolve, reject) {
            resolve('-----BEGIN CERTIFICATE-----\n' +
'MIIDVTCCAj2gAwIBAgIUGdmAH44RoQlouQFsWWzd0/a2b60wDQYJKoZIhvcNAQEL\n' +
'BQAwOjEVMBMGA1UEAwwMRmFkIEZhc2hpb3duMRQwEgYDVQQKDAtGYWRGYXNoaW93\n' +
'bjELMAkGA1UEBhMCUEgwHhcNMjYwNDExMTcwNTIzWhcNMzYwNDA4MTcwNTIzWjA6\n' +
'MRUwEwYDVQQDDAxGYWQgRmFzaGlvd24xFDASBgNVBAoMC0ZhZEZhc2hpb3duMQsw\n' +
'CQYDVQQGEwJQSDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMtsC6on\n' +
'KROQkrRN9DEKC0r1EsYgKuj2Ya8QlNAx9tzZS0Dd8h40tOeQ9Ya6K2ah/Mq9UiBU\n' +
'41srkVm6Qse22KYf/X2K+b5CEvZaFJkczROd4EPUPaxRgX1J9POA/qEVKalEp/Xw\n' +
'doCd/ILu+0TRT4Ql9W+ZocbVvO8YeXWKkPJ1BbvX3OoSer34JmBZnRngP2QiTkVP\n' +
'ias7giwFu4k/Eqk2/igntmv3D4lDMjPfQ3RmYJyu/QWRQUS0BCC1qwm9LLUZfYKf\n' +
'OPRDFhA9klx75lvnR0aK2AHKuNjHfs0jh+sGbEuFzIdwmh6kTAeskZZ0PRFcPskF\n' +
'FZOjBdulUuvl0UECAwEAAaNTMFEwHQYDVR0OBBYEFDtIOIV23Rno3oo+hvW+YZOp\n' +
'bLm6MB8GA1UdIwQYMBaAFDtIOIV23Rno3oo+hvW+YZOpbLm6MA8GA1UdEwEB/wQF\n' +
'MAMBAf8wDQYJKoZIhvcNAQELBQADggEBAEup2fLxQefw9ZqgdvSocSOLKPwwpMvA\n' +
'pZ5IMEk1ZkCpBXB7XLUJtfaQtvvoViLNo8EpBQHvWsNEyPfF1g9Hc1L6QFblQyeg\n' +
'E6X8n5fa4eD6/E3UU1wlRbttj/YM+BvJU2LAdYbwB4l/7XHnO4qMwjccnTrJimx0\n' +
'GyzyLdkL+lAdJnk0VXIrOGELlmjzFVqDmIo67xv47j16ZCqeqDiD6NXgd9tOkIrX\n' +
'1FA6QHzShRnFJ68iFjnKGN1lIHYcBk61gGNZEHSJOeEVbyEGZ/UTSUg1lHdLIpgy\n' +
'eXmZpCoOOgzScnljc8lbO3J7rmF1iev7w1Y6847KNnqw7UQ0OleJLfg=\n' +
'-----END CERTIFICATE-----');
        });

        qz.security.setSignatureAlgorithm('SHA512');
        qz.security.setSignaturePromise(function(toSign) {
            return function(resolve, reject) {
                fetch('/api/qz-sign', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ request: toSign })
                })
                .then(res => res.json())
                .then(data => resolve(data.signature))
                .catch(() => resolve(''));
            };
        });
    }
});

// app.js - Fad Fashiown Dashboard Logic
const socket = io();
let currentBuyer = '';
let commentCount = 0;

// Label settings (loaded from server)
let labelSettings = {
    title: 'FAD FASHIOWN',
    tagline: 'Live Selling',
    template: 'classic',
    showOrderId: true,
    showDatetime: true
};

// ── CONNECTION EVENTS ──
socket.on('connect', function () {
    console.log('Connected to server');
    updateConnectionStatus(true);
    updateExtensionStatus(false);
    loadOrders();
    loadLabelSettings();
});

socket.on('disconnect', function () {
    console.log('Disconnected from server');
    updateConnectionStatus(false);
});

socket.on('buyer_detected', function (data) {
    if (data.username && data.username.trim() !== '') {
        setBuyer(data.username, data.detected_at);
    }
});

socket.on('order_saved', function (order) {
    prependOrder(order);
    showToast('Order saved!', 'success');
});

socket.on('new_comment', function (data) {
    addComment(data);
    updateExtensionStatus(true);
});

// ── LOAD LABEL SETTINGS ──
async function loadLabelSettings() {
    try {
        const res = await fetch('/api/client-settings');
        if (res.ok) {
            const data = await res.json();
            labelSettings = {
                title: data.label_title || 'FAD FASHIOWN',
                tagline: data.label_tagline || 'Live Selling',
                template: data.label_template || 'classic',
                showOrderId: data.label_show_order_id !== false,
                showDatetime: data.label_show_datetime !== false
            };
            console.log('Label settings loaded:', labelSettings.template);
        }
    } catch(e) {
        console.log('Using default label settings');
    }
}


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
function addComment(data) {
    const list = document.getElementById('comments-list');
    if (!list) return;

    const empty = list.querySelector('.empty-state');
    if (empty) empty.remove();

    const existing = list.querySelectorAll('.comment-item');
    if (existing.length >= 50) {
        existing[existing.length - 1].remove();
    }

    commentCount++;
    const countEl = document.getElementById('comment-count');
    if (countEl) countEl.textContent = commentCount;

    const div = document.createElement('div');
    div.className = 'comment-item' + (data.is_buyer ? ' buyer' : '');

    div.innerHTML = `
        <div class="comment-username">@${data.username}</div>
        <div class="comment-message">${data.message}</div>
        <div class="comment-click-hint">Click to select as buyer</div>
    `;

    div.addEventListener('click', function () {
        fetch('/api/set-buyer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: data.username })
        })
        .then(res => res.json())
        .then(result => {
            if (result.success) {
                showToast('Buyer set: @' + data.username, 'success');
                document.querySelectorAll('.comment-item').forEach(el => {
                    el.style.opacity = '0.4';
                });
                div.style.opacity = '1';
                div.classList.add('selected');
                // Focus price for fast entry
                document.getElementById('price').focus();
            }
        })
        .catch(err => showToast('Error setting buyer', 'error'));
    });

    list.insertBefore(div, list.firstChild);
}


// ── QZ TRAY CONNECTION (persistent) ──
let qzConnected = false;

async function ensureQZConnected() {
    if (qzConnected && qz.websocket.isActive()) return true;
    try {
        await qz.websocket.connect();
        qzConnected = true;
        console.log('QZ Tray connected!');
        return true;
    } catch (err) {
        console.error('QZ Tray connect error:', err);
        qzConnected = false;
        return false;
    }
}

setInterval(async () => {
    if (qzConnected && !qz.websocket.isActive()) {
        qzConnected = false;
        await ensureQZConnected();
    }
}, 10000);

document.addEventListener('DOMContentLoaded', async function() {
    if (typeof qz !== 'undefined') {
        setTimeout(async () => {
            await ensureQZConnected();
        }, 1000);
    }
});


// ── SILENT PRINT (QZ Tray → fallback browser) ──
async function silentPrint() {
    // Use browser print for now (switch to QZ ESC/POS when thermal arrives)
    browserPrint();
}


// ── BROWSER PRINT ──
function browserPrint() {
    const username = document.getElementById('print-username').textContent;
    const price = document.getElementById('print-price').textContent;
    const date = document.getElementById('print-date').textContent;
    const orderId = document.getElementById('print-order-id').textContent;

    const title = labelSettings.title || 'FAD FASHIOWN';
    const tagline = labelSettings.tagline || 'Live Selling';
    const showDate = labelSettings.showDatetime;
    const showOrder = labelSettings.showOrderId;

    let labelContent = '';

    if (labelSettings.template === 'minimal') {
        labelContent = `
            <div style="text-align:center;font-family:Arial;width:52mm;padding:4mm">
                <div style="font-size:11pt;font-weight:900;letter-spacing:2px;text-transform:uppercase">${title}</div>
                <div style="border-top:1px solid #000;margin:4px 0"></div>
                <div style="font-size:14pt;font-weight:900;margin:6px 0">${username}</div>
                <div style="border-top:1px solid #000;margin:4px 0"></div>
                <div style="font-size:16pt;font-weight:900">${price}</div>
                ${showDate ? `<div style="font-size:7pt;color:#666;margin-top:4px">${date}</div>` : ''}
                ${showOrder ? `<div style="font-size:7pt;color:#666">${orderId}</div>` : ''}
            </div>`;

    } else if (labelSettings.template === 'bold') {
        labelContent = `
            <div style="font-family:Arial;width:52mm">
                <div style="background:#1a3a0a;color:white;padding:6px;text-align:center;
                            font-size:14pt;font-weight:900;letter-spacing:2px;
                            text-transform:uppercase">${title}</div>
                <div style="padding:4mm;text-align:center">
                    <div style="font-size:8pt;color:#666;letter-spacing:2px;
                                text-transform:uppercase;margin-bottom:2px">BUYER</div>
                    <div style="font-size:18pt;font-weight:900;line-height:1.1;
                                margin:4px 0;word-break:break-all">${username}</div>
                    <div style="border-top:2px solid #000;margin:6px 0"></div>
                    <div style="font-size:22pt;font-weight:900">${price}</div>
                    ${showDate ? `<div style="font-size:7pt;color:#666;margin-top:6px">${date}</div>` : ''}
                    ${showOrder ? `<div style="font-size:7pt;color:#666">${orderId}</div>` : ''}
                </div>
            </div>`;

    } else {
        // Classic template (default)
        labelContent = `
            <div style="text-align:center;font-family:Arial;width:52mm;
                        padding:5mm;border:1.5px solid #000">
                <div style="font-size:13pt;font-weight:900;letter-spacing:3px;
                            text-transform:uppercase">${title}</div>
                <div style="font-size:8pt;letter-spacing:3px;text-transform:uppercase;
                            color:#444;margin-bottom:4px">${tagline}</div>
                <div style="border-top:1px dashed #666;margin:5px 0"></div>
                <div style="font-size:7pt;letter-spacing:3px;text-transform:uppercase;
                            color:#666">BUYER</div>
                <div style="font-size:15pt;font-weight:900;word-break:break-all;
                            line-height:1.2;margin:3px 0">${username}</div>
                <div style="border-top:1px dashed #666;margin:5px 0"></div>
                <div style="display:flex;justify-content:space-between;
                            align-items:center;margin:3px 0">
                    <span style="font-size:7pt;font-weight:700;letter-spacing:2px;
                                 text-transform:uppercase;color:#666">PRICE</span>
                    <span style="font-size:13pt;font-weight:900">${price}</span>
                </div>
                <div style="border-top:1px dashed #666;margin:5px 0"></div>
                ${showDate ? `<div style="font-size:7pt;color:#666;margin-top:2px">${date}</div>` : ''}
                ${showOrder ? `<div style="font-size:7pt;color:#666">${orderId}</div>` : ''}
            </div>`;
    }

    const iframe = document.createElement('iframe');
    iframe.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden;';
    document.body.appendChild(iframe);

    const doc = iframe.contentWindow.document;
    doc.open();
    doc.write(`<!DOCTYPE html>
        <html>
        <head>
            <style>
                * { margin:0; padding:0; box-sizing:border-box; }
                body { display:flex; justify-content:center; padding:4mm; }
                @page { size:58mm auto; margin:0; }
            </style>
        </head>
        <body>${labelContent}</body>
        </html>`);
    doc.close();
    iframe.contentWindow.focus();
    iframe.contentWindow.print();
    setTimeout(() => document.body.removeChild(iframe), 3000);
}


// ── PRINT LABEL ──
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
            price: parseFloat(price)
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Fill label
            document.getElementById('print-username').textContent = currentBuyer;
            document.getElementById('print-price').textContent = '₱' + parseFloat(price).toFixed(2);

            const now = new Date();
            document.getElementById('print-date').textContent =
                now.toLocaleDateString('en-PH', {
                    month: 'short', day: 'numeric', year: 'numeric',
                    hour: '2-digit', minute: '2-digit'
                });
            document.getElementById('print-order-id').textContent =
                'Order #' + data.order.id;

            setTimeout(() => silentPrint(), 300);

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