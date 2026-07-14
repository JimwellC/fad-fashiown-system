// print.js — SHARED label/printing machinery.
// Loaded by BOTH the TikTok dashboard (app.js) and the Facebook Live console
// (facebook.js) so the label output can never drift between the two platforms.
// Provides: labelSettings, loadLabelSettings(), silentPrint(), browserPrint(),
//           fillLabelFields()

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


// ── HTML ESCAPE (shared) ──
// Comments come from arbitrary public viewers (TikTok chat / Facebook Live).
// Any value interpolated into innerHTML must pass through this, or a crafted
// comment runs script in the logged-in seller's session (stored XSS).
function escapeHtml(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}


// ── SHARED LIVE-COMMENT RENDERER ──
// Both consoles render comments identically: escape untrusted text, cap the list
// at 50, highlight buyers, and dim-others on click. Keeping it here means the XSS
// escaping and the cap can never drift apart between TikTok and Facebook.
// onSelect(data) runs when the seller clicks a comment.
function renderComment(listId, data, onSelect) {
    const list = document.getElementById(listId);
    if (!list) return;

    const empty = list.querySelector('.empty-state');
    if (empty) empty.remove();

    const existing = list.querySelectorAll('.comment-item');
    if (existing.length >= 50) existing[existing.length - 1].remove();

    const div = document.createElement('div');
    div.className = 'comment-item' + (data.is_buyer ? ' buyer' : '');
    div.innerHTML = `
        <div class="comment-username">@${escapeHtml(data.username)}</div>
        <div class="comment-message">${escapeHtml(data.message)}</div>
        <div class="comment-click-hint">Click to select as buyer</div>
    `;

    div.addEventListener('click', function () {
        list.querySelectorAll('.comment-item').forEach(el => { el.style.opacity = '0.4'; });
        div.style.opacity = '1';
        div.classList.add('selected');
        onSelect(data);
    });

    list.insertBefore(div, list.firstChild);
}


// ── SHARED CONNECTION-STATUS PILL ──
function setConnectionStatus(elId, connected) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.textContent = connected ? 'Connected' : 'Disconnected';
    el.className = 'status-pill ' + (connected ? 'connected' : 'disconnected');
}


// ── LABEL SETTINGS (loaded from server) ──
let labelSettings = {
    title: 'FAD FASHIOWN',
    tagline: 'Live Selling',
    template: 'classic',
    showOrderId: true,
    showDatetime: true
};

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
    if (typeof qz === 'undefined') return;
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


// ── FILL THE HIDDEN LABEL FIELDS (shared by both consoles) ──
function fillLabelFields(username, price, orderId) {
    document.getElementById('print-username').textContent = username;
    document.getElementById('print-price').textContent =
        '₱' + parseFloat(price).toFixed(2);

    const now = new Date();
    document.getElementById('print-date').textContent =
        now.toLocaleDateString('en-PH', {
            month: 'short', day: 'numeric', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    document.getElementById('print-order-id').textContent = 'Order #' + orderId;
}


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
            <div style="text-align:center;font-family:Arial;width:66mm;padding:2mm 3mm;">
                <div style="font-size:12pt;font-weight:900;letter-spacing:2px;text-transform:uppercase;margin-bottom:1mm">${title}</div>
                <div style="border-top:1px solid #000;margin:1mm 0"></div>
                <div style="font-size:16pt;font-weight:900;margin:1mm 0">${username}</div>
                <div style="border-top:1px solid #000;margin:1mm 0"></div>
                <div style="font-size:18pt;font-weight:900">${price}</div>
                ${showDate ? `<div style="font-size:7pt;color:#666;margin-top:1mm">${date}</div>` : ''}
                ${showOrder ? `<div style="font-size:7pt;color:#666">${orderId}</div>` : ''}
            </div>`;

    } else if (labelSettings.template === 'bold') {
        labelContent = `
            <div style="font-family:Arial;width:66mm;">
                <div style="background:#1a3a0a;color:white;padding:2mm 3mm;text-align:center;
                            font-size:12pt;font-weight:900;letter-spacing:2px;
                            text-transform:uppercase">${title}</div>
                <div style="padding:1mm 3mm;text-align:center">
                    <div style="font-size:7pt;color:#666;letter-spacing:2px;
                                text-transform:uppercase;margin-bottom:1mm">BUYER</div>
                    <div style="font-size:18pt;font-weight:900;line-height:1.1;
                                margin:1mm 0;word-break:break-all">${username}</div>
                    <div style="border-top:2px solid #000;margin:1mm 0"></div>
                    <div style="font-size:20pt;font-weight:900">${price}</div>
                    ${showDate ? `<div style="font-size:7pt;color:#666;margin-top:1mm">${date}</div>` : ''}
                    ${showOrder ? `<div style="font-size:7pt;color:#666">${orderId}</div>` : ''}
                </div>
            </div>`;

    } else {
        // Classic template (default)
        labelContent = `
            <div style="text-align:center;font-family:Arial;width:66mm;
                        padding:2mm 3mm;border:1px solid #000;">
                <div style="font-size:15pt;font-weight:900;letter-spacing:2px;
                            text-transform:uppercase;line-height:1.2">${title}</div>
                <div style="font-size:10pt;letter-spacing:2px;text-transform:uppercase;
                            color:#444;margin-bottom:1mm">${tagline}</div>
                <div style="border-top:1px dashed #666;margin:1.5mm 0"></div>
                <div style="font-size:10pt;letter-spacing:2px;text-transform:uppercase;
                            color:#666">BUYER</div>
                <div style="font-size:18pt;font-weight:900;word-break:break-all;
                            line-height:1.2;margin:1mm 0">${username}</div>
                <div style="border-top:1px dashed #666;margin:1.5mm 0"></div>
                <div style="display:flex;justify-content:space-between;
                            align-items:center;margin:1mm 0">
                    <span style="font-size:7pt;font-weight:700;letter-spacing:1px;
                                 text-transform:uppercase;color:#666">PRICE</span>
                    <span style="font-size:16pt;font-weight:900">${price}</span>
                </div>
                ${showDate || showOrder ? `<div style="border-top:1px dashed #666;margin:1.5mm 0"></div>` : ''}
                ${showDate ? `<div style="font-size:7pt;color:#666">${date}</div>` : ''}
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
                html, body { width:70mm; height:50mm; overflow:hidden; }
                body { display:flex; justify-content:center; align-items:center; }
                @page { size:70mm 50mm landscape; margin:0; }
                @media print {
                    html, body { width:70mm; height:50mm; overflow:hidden; }
                }
            </style>
        </head>
        <body>${labelContent}</body>
        </html>`);
    doc.close();
    iframe.contentWindow.focus();
    iframe.contentWindow.print();
    setTimeout(() => document.body.removeChild(iframe), 3000);
}
