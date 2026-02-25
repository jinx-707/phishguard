// PhishGuard Background Service Worker - API Communication Handler

const API_ENDPOINT = 'http://localhost:8000/api/v1/scan';
const FEEDBACK_ENDPOINT = 'http://localhost:8000/api/v1/feedback';
const REQUEST_TIMEOUT_MS = 5000;

// JWT Token for backend authentication
const AUTH_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc3MjExMzk4OX0.WbzHzTmEV22XGX6j8zLO8l1ZEzMYPl2zZTTIIo86d6I';

// Cache for pre-navigation scans
const navigationCache = new Map();
const CACHE_TTL_MS = 60000; // 1 minute cache

chrome.runtime.onInstalled.addListener(() => {
  console.log('[PhishGuard] Extension installed and active');
});

// ============================================================
// PRE-NAVIGATION SCANNING (Step 4 - Browser Blocking)
// ============================================================

/**
 * Handle before navigation - scan domain before page loads
 */
async function handleBeforeNavigation(details) {
  const url = details.url;
  
  // Skip chrome internal pages
  if (url.startsWith('chrome://') || url.startsWith('chrome-extension://') || 
      url.startsWith('about:') || url.startsWith('data:')) {
    return;
  }
  
  // Skip if already processed
  if (navigationCache.has(url)) {
    const cached = navigationCache.get(url);
    if (Date.now() - cached.timestamp < CACHE_TTL_MS) {
      if (cached.block) {
        return { cancel: true };
      }
      return;
    }
    navigationCache.delete(url);
  }
  
  try {
    // Extract domain for domain-only scan
    const urlObj = new URL(url);
    const domain = urlObj.hostname;
    
    // Quick domain-only scan for blocking
    const result = await sendToBackend({
      url: url,
      mode: 'domain_only'
    });
    
    if (result && result.success) {
      const { risk, block } = result.data;
      
      // Cache the result
      navigationCache.set(url, {
        ...result.data,
        timestamp: Date.now()
      });
      
      if (block || risk === 'HIGH') {
        console.log('[PhishGuard] Blocking navigation to:', url);
        // Store for content script to show block page
        await chrome.storage.session.set({
          [`block_${url}`]: result.data
        });
        return { redirectUrl: getBlockPageUrl(url, result.data) };
      }
    }
  } catch (error) {
    console.warn('[PhishGuard] Pre-nav scan failed:', error);
  }
}

/**
 * Get block page URL with encoded data
 */
function getBlockPageUrl(originalUrl, result) {
  const encoded = btoa(JSON.stringify({
    url: originalUrl,
    result: result
  }));
  return chrome.runtime.getURL('block.html') + '?data=' + encoded;
}

/**
 * Register navigation listener
 */
function setupNavigationListener() {
  try {
    chrome.webNavigation.onBeforeNavigate.addListener(
      handleBeforeNavigation,
      { urlTypes: ['http', 'https'] }
    );
    console.log('[PhishGuard] Pre-navigation scanning enabled');
  } catch (error) {
    console.warn('[PhishGuard] Navigation listener not available:', error);
  }
}

// Initialize navigation listener
setupNavigationListener();

/**
 * Send scan data to backend API with timeout
 */
async function sendToBackend(payload) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${AUTH_TOKEN}`
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();

    // Validate response structure
    if (!data || typeof data.risk !== 'string') {
      throw new Error('Invalid response format from backend');
    }

    // Safe response parsing
    const safeResponse = JSON.parse(JSON.stringify(data));

    return {
      success: true,
      data: safeResponse
    };

  } catch (error) {
    clearTimeout(timeoutId);

    if (error.name === 'AbortError') {
      return {
        success: false,
        error: 'Request timeout'
      };
    }

    return {
      success: false,
      error: error.message || 'Unknown error'
    };
  }
}

/**
 * Store scan result in chrome.storage
 */
async function storeScanResult(url, result) {
  try {
    await chrome.storage.local.set({
      lastScan: {
        url,
        result,
        timestamp: Date.now()
      }
    });
  } catch (error) {
    console.warn('[PhishGuard] Storage error:', error);
  }
}

/**
 * Send user override feedback to backend
 */
async function sendFeedback(payload) {
  try {
    const response = await fetch(FEEDBACK_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${AUTH_TOKEN}`
      },
      body: JSON.stringify(payload)
    });

    if (response.ok) {
      console.log('[PhishGuard] Feedback sent successfully');
    }
  } catch (error) {
    console.warn('[PhishGuard] Feedback send failed:', error.message);
  }
}

/**
 * Message listener - handles messages from content script
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) {
    return false;
  }

  // Handle SCAN_PAGE
  if (message.type === 'SCAN_PAGE' && message.payload) {
    (async () => {
      try {
        // Log local AI result if present
        if (message.payload.local_result) {
          const { local_risk, local_confidence, inference_time_ms } = message.payload.local_result;
          console.log(`[PhishGuard] Local AI: ${local_risk} (${local_confidence}) in ${inference_time_ms}ms`);
        }

        const result = await sendToBackend(message.payload);

        if (result.success) {
          const { risk, confidence, reasons } = result.data;

          console.log(`[PhishGuard] Backend: ${risk} (${confidence || 'N/A'})`);

          if (reasons && reasons.length > 0) {
            console.log('[PhishGuard] Reasons:', reasons);
          }

          // Store result for popup
          await storeScanResult(message.payload.url, result.data);

          // Send response back to content script
          sendResponse(result.data);
        } else {
          console.warn('[PhishGuard] Backend unavailable:', result.error);
          sendResponse(null);
        }
      } catch (error) {
        console.error('[PhishGuard] Unexpected error:', error);
        sendResponse(null);
      }
    })();

    return true;
  }

  // Handle SCAN_EMAIL
  if (message.type === 'SCAN_EMAIL' && message.payload) {
    (async () => {
      try {
        console.log(`[PhishGuard Email] Scanning email from: ${message.payload.sender?.email || 'unknown'}`);

        if (message.payload.local_result) {
          const { local_risk, local_confidence } = message.payload.local_result;
          console.log(`[PhishGuard Email] Local AI: ${local_risk} (${local_confidence})`);
        }

        const result = await sendToBackend(message.payload);

        if (result.success) {
          const { risk, confidence, reasons } = result.data;
          console.log(`[PhishGuard Email] Backend: ${risk} (${confidence || 'N/A'})`);
          sendResponse(result.data);
        } else {
          console.warn('[PhishGuard Email] Backend unavailable:', result.error);
          sendResponse(null);
        }
      } catch (error) {
        console.error('[PhishGuard Email] Unexpected error:', error);
        sendResponse(null);
      }
    })();

    return true;
  }

  // Handle SCAN_MESSAGE
  if (message.type === 'SCAN_MESSAGE' && message.payload) {
    (async () => {
      try {
        console.log(`[PhishGuard Message] Scanning ${message.payload.platform} message`);

        if (message.payload.local_result) {
          const { local_risk, local_confidence } = message.payload.local_result;
          console.log(`[PhishGuard Message] Local AI: ${local_risk} (${local_confidence})`);
        }

        const result = await sendToBackend(message.payload);

        if (result.success) {
          const { risk, confidence, reasons } = result.data;
          console.log(`[PhishGuard Message] Backend: ${risk} (${confidence || 'N/A'})`);
          sendResponse(result.data);
        } else {
          console.warn('[PhishGuard Message] Backend unavailable:', result.error);
          sendResponse(null);
        }
      } catch (error) {
        console.error('[PhishGuard Message] Unexpected error:', error);
        sendResponse(null);
      }
    })();

    return true;
  }

  // Handle REPORT_PHISHING
  if (message.type === 'REPORT_PHISHING' && message.payload) {
    console.log('[PhishGuard] Phishing reported:', message.payload);

    // Send report to backend
    sendFeedback({
      ...message.payload,
      type: 'phishing_report'
    }).catch(err => {
      console.warn('[PhishGuard] Report send failed:', err);
    });

    return false;
  }

  // Handle USER_OVERRIDE
  if (message.type === 'USER_OVERRIDE' && message.payload) {
    console.log('[PhishGuard] User override logged');

    // Send feedback asynchronously (no response needed)
    sendFeedback(message.payload).catch(err => {
      console.warn('[PhishGuard] Feedback error:', err);
    });

    return false;
  }

  return false;
});
