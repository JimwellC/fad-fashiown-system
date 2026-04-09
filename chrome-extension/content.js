// content.js
// Monitors TikTok Live chat comments
// Sends new comments to Fad Fashiown dashboard

(function() {
    if (window.__fadFashiownLoaded) return;
    window.__fadFashiownLoaded = true;

    console.log('Fad Fashiown - Comment Monitor loaded');

    const BACKEND_URL = 'https://web-production-1fba.up.railway.app/api/new-comment';
    const CLIENT_TOKEN = 'ed707688f74dffedd4fd14d11c2f7427c547d3f085aba2dcacfb47ec1c3d360e';

    // Buyer keywords in Filipino and English
    const BUYER_KEYWORDS = [
        'mine', 'ako', 'akin', 'ko', 'me',
        'samin', 'ours', 'want', 'gusto', 'bili'
    ];


    // ── SCAN ALL VISIBLE COMMENTS ──
    function scanComments() {
        const commentEls = document.querySelectorAll('[data-e2e="chat-message"]');

        commentEls.forEach(el => {
            if (el.dataset.fadSeen) return;
            el.dataset.fadSeen = 'true';

            const { username, message } = extractComment(el);

            if (!username) return;
            if (!message || message.length === 0) return;

            const msgLower = message.toLowerCase().trim();
            const isBuyer = BUYER_KEYWORDS.some(k =>
                msgLower === k || msgLower.startsWith(k + ' ')
            );

            sendComment(username, message, isBuyer);
        });
    }


    // ── EXTRACT USERNAME + MESSAGE ──
    function extractComment(el) {
        try {
            let username = '';
            let message = '';

            const usernameEl = el.querySelector('[data-e2e="message-owner-name"]');
            if (usernameEl) {
                username = usernameEl.textContent.trim();
            }

            const contentArea = el.querySelector('.flex.flex-col');
            if (contentArea) {
                const divs = contentArea.querySelectorAll(':scope > div');
                if (divs.length > 0) {
                    const lastDiv = divs[divs.length - 1];
                    message = lastDiv.textContent.trim();
                }
            }

            if (!message) {
                const allDivs = el.querySelectorAll('div');
                allDivs.forEach(div => {
                    if (div.children.length === 0) {
                        const t = div.textContent.trim();
                        if (t && t !== username && t.length > 0) {
                            message = t;
                        }
                    }
                });
            }

            username = username.replace('@', '').trim();
            message = message.trim();
            message = message.replace(/No\.\s*\d+/g, '').trim();

            return { username, message };

        } catch(e) {
            console.error('Extract error:', e);
            return { username: '', message: '' };
        }
    }


    // ── SEND COMMENT TO BACKEND ──
    function sendComment(username, message, isBuyer) {
        if (!username) return;

        console.log(`@${username}: "${message}" ${isBuyer ? '→ BUYER' : ''}`);

        fetch(BACKEND_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: username,
                message: message,
                is_buyer: isBuyer,
                token: CLIENT_TOKEN
            })
        }).then(res => {
            if (!res.ok) {
                console.error('Server error:', res.status);
            }
        }).catch(err => console.error('Send error:', err));
    }


    // ── WATCH CHAT FOR NEW COMMENTS ──
    function startChatObserver() {
        const chatContainer = document.querySelector('[data-e2e="live-chat-container"]');

        if (!chatContainer) {
            console.log('Chat not found, retrying in 2s...');
            setTimeout(startChatObserver, 2000);
            return;
        }

        console.log('Chat found! Watching for comments...');

        scanComments();

        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.addedNodes.length > 0) {
                    scanComments();
                    break;
                }
            }
        });

        observer.observe(chatContainer, {
            childList: true,
            subtree: true
        });

        console.log('Watching chat for buyer comments...');
    }


    // ── WAIT FOR LIVE PAGE ──
    function waitForLivePage() {
        console.log('Waiting for TikTok Live...');

        const check = setInterval(() => {
            const isLive = window.location.href.includes('/live');
            const chatContainer = document.querySelector('[data-e2e="live-chat-container"]');

            if (isLive && chatContainer) {
                clearInterval(check);
                console.log('TikTok Live detected!');
                startChatObserver();
            }
        }, 1000);
    }


    // ── START ──
    waitForLivePage();

})();