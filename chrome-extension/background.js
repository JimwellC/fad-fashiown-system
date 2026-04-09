// background.js
// Chrome Extension background service worker
// Handles extension lifecycle and tab monitoring

console.log('Fad Fashiown background service started');

// Listen for tab updates (when user navigates to TikTok)
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    // Check if user navigated to TikTok
    if (changeInfo.status === 'complete' &&
        tab.url &&
        tab.url.includes('tiktok.com')) {

        console.log('TikTok tab detected:', tab.url);

        // Inject content script if not already there
        chrome.scripting.executeScript({
            target: { tabId: tabId },
            files: ['content.js']
        }).catch(err => {
            // Script already injected, ignore error
            console.log('Content script already active');
        });
    }
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'PINNED_USER_DETECTED') {
        console.log('Pinned user detected:', message.username);
        sendResponse({ success: true });
    }
});