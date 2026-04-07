// content.js
// Monitors TikTok Live chat comments
// Sends new comments to Fad Fashiown dashboard

(function() {
    if (window.__fadFashiownLoaded) return;
    window.__fadFashiownLoaded = true;

    console.log('👗 Fad Fashiown - Comment Monitor loaded');

    const BACKEND_URL = 'https://web-production-1fba.up.railway.app/api/new-comment';
    const SET_BUYER_URL = 'https://web-production-1fba.up.railway.app/api/set-buyer';

    // Buyer keywords in Filipino and English
    const BUYER_KEYWORDS = [
        'mine', 'ako', 'akin', 'ko', 'me',
        'samin', 'ours', 'want', 'gusto', 'bili'
    ];


    // ── SCAN ALL VISIBLE COMMENTS ──
    function scanComments() {
        const commentEls = document.querySelectorAll('[data-e2e="chat-message"]');

        commentEls.forEach(el => {
            // Skip already processed elements
            if (el.dataset.fadSeen) return;
            el.dataset.fadSeen = 'true';

            const { username, message } = extractComment(el);

            // Skip if we couldn't parse properly
            if (!username) return;
            if (!message || message.length === 0) return;

            // Check if this is a buyer comment
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

            // USERNAME: TikTok uses data-e2e="message-owner-name"
            const usernameEl = el.querySelector('[data-e2e="message-owner-name"]');
            if (usernameEl) {
                username = usernameEl.textContent.trim();
            }

            // MESSAGE: Last div inside the message content area
            // Structure: outer div > [avatar div] + [content div > [name row] + [message div]]
            // The message is the last direct div child of the content area
            const contentArea = el.querySelector('.flex.flex-col');
            if (contentArea) {
                // Get all direct div children
                const divs = contentArea.querySelectorAll(':scope > div');
                if (divs.length > 0) {
                    // Last div = message text
                    const lastDiv = divs[divs.length - 1];
                    message = lastDiv.textContent.trim();
                }
            }

            // Fallback if content area not found
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

            // Clean up
            username = username.replace('@', '').trim();
            message = message.trim();

            // Remove badge texts like "No. 1", "No. 2" from message
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

        console.log(`💬 @${username}: "${message}" ${isBuyer ? '🛒 BUYER!' : ''}`);

        fetch(BACKEND_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'text/plain' },
            body: JSON.stringify({
                username: username,
                message: message,
                is_buyer: isBuyer
            }),
            mode: 'no-cors'
        }).catch(err => console.error('Send error:', err));
    }


    // ── WATCH CHAT FOR NEW COMMENTS ──
    function startChatObserver() {
        const chatContainer = document.querySelector('[data-e2e="live-chat-container"]');

        if (!chatContainer) {
            console.log('⏳ Chat not found, retrying in 2s...');
            setTimeout(startChatObserver, 2000);
            return;
        }

        console.log('✅ Chat found! Watching for comments...');

        // Process existing comments immediately
        scanComments();

        // Watch for new comments
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

        console.log('👁️ Watching chat for "mine" comments...');
    }


    // ── WAIT FOR LIVE PAGE ──
    function waitForLivePage() {
        console.log('⏳ Waiting for TikTok Live...');

        const check = setInterval(() => {
            const isLive = window.location.href.includes('/live');
            const chatContainer = document.querySelector('[data-e2e="live-chat-container"]');

            if (isLive && chatContainer) {
                clearInterval(check);
                console.log('🎉 TikTok Live detected!');
                startChatObserver();
            }
        }, 1000);
    }


    // ── START ──
    waitForLivePage();

})();