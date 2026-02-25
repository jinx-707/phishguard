// PhishGuard Popup - Status Viewer with Live Scan

document.addEventListener('DOMContentLoaded', async () => {
  const statusDiv = document.getElementById('status');
  const resultDiv = document.getElementById('result');
  const errorDiv = document.getElementById('error');
  
  const riskLevelSpan = document.getElementById('risk-level');
  const confidenceSpan = document.getElementById('confidence');
  const urlSpan = document.getElementById('url');
  const timestampSpan = document.getElementById('timestamp');
  const reasonsContainer = document.getElementById('reasons-container');
  const reasonsList = document.getElementById('reasons-list');

  // Show loading state
  showStatus('Scanning current page...');

  try {
    // Get current active tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (!tab || !tab.url) {
      showStatus('No active page found');
      return;
    }

    // Skip chrome:// and extension:// URLs
    if (tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://') || tab.url.startsWith('about:')) {
      showStatus('Cannot scan browser pages');
      return;
    }

    // Trigger fresh scan via background script
    const scanResult = await triggerScan(tab.id, tab.url);
    
    if (scanResult && scanResult.success) {
      showResult(tab.url, scanResult.data, Date.now());
    } else if (scanResult && scanResult.error) {
      // Try to show cached result if available
      const cached = await chrome.storage.local.get('lastScan');
      if (cached.lastScan && cached.lastScan.url === tab.url) {
        showResult(tab.url, cached.lastScan.result, cached.lastScan.timestamp);
      } else {
        showError(scanResult.error);
      }
    } else {
      showError('Scan failed');
    }

  } catch (error) {
    console.error('[PhishGuard] Popup error:', error);
    showError(error.message || 'Connection error');
  }

  function showStatus(message) {
    statusDiv.classList.remove('hidden');
    resultDiv.classList.add('hidden');
    errorDiv.classList.add('hidden');
    
    const statusText = statusDiv.querySelector('.status-text');
    if (statusText) {
      statusText.textContent = message;
    }
  }

  function showError(message = 'Unable to connect to backend') {
    statusDiv.classList.add('hidden');
    resultDiv.classList.add('hidden');
    errorDiv.classList.remove('hidden');
    
    const errorText = errorDiv.querySelector('p');
    if (errorText) {
      errorText.textContent = '⚠️ ' + message;
    }
  }

  /**
   * Trigger scan via background script
   */
  async function triggerScan(tabId, url) {
    return new Promise((resolve) => {
      // First inject content script to extract features
      chrome.scripting.executeScript({
        target: { tabId: tabId },
        func: extractPageFeatures
      }, (results) => {
        if (chrome.runtime.lastError) {
          console.error('[PhishGuard] Script injection failed:', chrome.runtime.lastError);
          resolve({ success: false, error: 'Cannot access page' });
          return;
        }

        const features = results && results[0] && results[0].result;
        
        if (!features) {
          resolve({ success: false, error: 'Failed to extract page data' });
          return;
        }

        // Send to background for backend scan
        chrome.runtime.sendMessage(
          {
            type: 'SCAN_PAGE',
            payload: {
              url: url,
              ...features
            }
          },
          (response) => {
            if (chrome.runtime.lastError) {
              console.error('[PhishGuard] Scan failed:', chrome.runtime.lastError);
              resolve({ success: false, error: chrome.runtime.lastError.message });
              return;
            }

            if (response && response.risk) {
              resolve({ success: true, data: response });
            } else {
              resolve({ success: false, error: 'Invalid response' });
            }
          }
        );
      });
    });
  }

  /**
   * Feature extraction function (runs in page context)
   */
  function extractPageFeatures() {
    const body = document.body;
    const text = body ? (body.innerText || body.textContent || '').slice(0, 2000) : '';
    
    return {
      text_snippet: text,
      password_fields: document.querySelectorAll('input[type="password"]').length,
      hidden_inputs: document.querySelectorAll('input[type="hidden"]').length,
      external_links: document.querySelectorAll('a[href^="http"]').length,
      iframe_count: document.querySelectorAll('iframe').length,
      form_count: document.querySelectorAll('form').length,
      has_login_indicators: document.querySelectorAll('input[type="password"]').length > 0,
      suspicious_keywords_found: [],
      timestamp: Date.now()
    };
  }

  function showResult(url, result, timestamp) {
    statusDiv.classList.add('hidden');
    resultDiv.classList.remove('hidden');
    errorDiv.classList.add('hidden');

    // Set risk level with color
    const risk = result.risk || 'UNKNOWN';
    riskLevelSpan.textContent = risk;
    riskLevelSpan.className = `risk-${risk.toLowerCase()}`;

    // Set confidence
    const confidence = result.confidence;
    if (confidence !== undefined && confidence !== null) {
      confidenceSpan.textContent = (confidence * 100).toFixed(1) + '%';
    } else {
      confidenceSpan.textContent = 'N/A';
    }

    // Set URL (truncate if too long)
    const truncatedUrl = url.length > 50 ? url.substring(0, 47) + '...' : url;
    urlSpan.textContent = truncatedUrl;
    urlSpan.title = url;

    // Set timestamp
    const date = new Date(timestamp);
    timestampSpan.textContent = date.toLocaleTimeString();

    // Set reasons if available
    if (result.reasons && result.reasons.length > 0) {
      reasonsContainer.classList.remove('hidden');
      reasonsList.innerHTML = '';
      
      result.reasons.forEach(reason => {
        const li = document.createElement('li');
        li.textContent = reason;
        reasonsList.appendChild(li);
      });
    } else {
      reasonsContainer.classList.add('hidden');
    }
  }
});
