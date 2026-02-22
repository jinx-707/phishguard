// PhishGuard Background Service Worker - API Communication Handler

const API_ENDPOINT = 'http://localhost:8000/scan';
const FEEDBACK_ENDPOINT = 'http://localhost:8000/feedback';
const REQUEST_TIMEOUT_MS = 5000;

chrome.runtime.onInstalled.addListener(() => {
  console.log('[PhishGuard] Extension installed and active');
});

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
        'Content-Type': 'application/json'
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
        'Content-Type': 'application/json'
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
