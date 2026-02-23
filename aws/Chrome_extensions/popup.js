// PhishGuard Popup - Status Viewer with Rescan Capability

document.addEventListener('DOMContentLoaded', async () => {
  const statusDiv = document.getElementById('status');
  const resultDiv = document.getElementById('result');
  const errorDiv = document.getElementById('error');
  const scanButton = document.getElementById('scan-button');
  
  const riskLevelSpan = document.getElementById('risk-level');
  const confidenceSpan = document.getElementById('confidence');
  const urlSpan = document.getElementById('url');
  const timestampSpan = document.getElementById('timestamp');
  const reasonsContainer = document.getElementById('reasons-container');
  const reasonsList = document.getElementById('reasons-list');

  // Function to perform scan
  async function performScan() {
    try {
      showStatus('Scanning page...');
      scanButton.disabled = true;
      scanButton.textContent = '⏳ Scanning...';

      // Get current tab
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (!tab || !tab.url) {
        showError();
        return;
      }

      const currentUrl = tab.url;

      // Send message to content script to get page data
      try {
        const response = await chrome.tabs.sendMessage(tab.id, { action: 'getPageData' });
        
        if (response && response.data) {
          // Send to backend API
          const apiUrl = 'http://localhost:8000/scan';
          const scanData = {
            url: currentUrl,
            suspicious_keywords_found: response.data.suspicious_keywords_found || [],
            long_url: response.data.long_url || false,
            excessive_subdomains: response.data.excessive_subdomains || false,
            subdomain_count: response.data.subdomain_count || 0,
            password_fields: response.data.password_fields || 0,
            external_links: response.data.external_links || 0,
            hidden_inputs: response.data.hidden_inputs || 0,
            iframe_count: response.data.iframe_count || 0,
            suspicious_url_keywords: response.data.suspicious_url_keywords || [],
            local_result: response.data.local_result || null
          };

          const apiResponse = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(scanData)
          });

          if (!apiResponse.ok) {
            throw new Error(`API error: ${apiResponse.status}`);
          }

          const result = await apiResponse.json();

          // Store result
          await chrome.storage.local.set({
            lastScan: {
              url: currentUrl,
              result: result,
              timestamp: new Date().toISOString()
            }
          });

          // Display result
          showResult(currentUrl, result, new Date().toISOString());
        } else {
          // Fallback: just scan the URL
          await scanUrlOnly(currentUrl);
        }
      } catch (msgError) {
        console.log('[PhishGuard] Content script not available, scanning URL only');
        // Fallback: scan URL only
        await scanUrlOnly(currentUrl);
      }

    } catch (error) {
      console.error('[PhishGuard] Scan error:', error);
      showError();
    } finally {
      scanButton.disabled = false;
      scanButton.textContent = '🔄 Rescan Current Page';
    }
  }

  // Fallback: Scan URL only (without page analysis)
  async function scanUrlOnly(url) {
    try {
      const apiUrl = 'http://localhost:8000/scan';
      const scanData = { url: url };

      const apiResponse = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(scanData)
      });

      if (!apiResponse.ok) {
        throw new Error(`API error: ${apiResponse.status}`);
      }

      const result = await apiResponse.json();

      // Store result
      await chrome.storage.local.set({
        lastScan: {
          url: url,
          result: result,
          timestamp: new Date().toISOString()
        }
      });

      // Display result
      showResult(url, result, new Date().toISOString());

    } catch (error) {
      console.error('[PhishGuard] URL scan error:', error);
      showError();
    }
  }

  // Attach scan button click handler
  if (scanButton) {
    scanButton.addEventListener('click', performScan);
  }

  // Load last scan result
  try {
    // Retrieve last scan result from storage
    const data = await chrome.storage.local.get('lastScan');
    
    if (!data.lastScan) {
      // No previous scan - automatically trigger a new scan
      showStatus('Ready to scan');
      return;
    }

    const { url, result, timestamp } = data.lastScan;

    if (!result) {
      showError();
      return;
    }

    // Display result
    showResult(url, result, timestamp);

  } catch (error) {
    console.error('[PhishGuard] Popup error:', error);
    showError();
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

  function showError() {
    statusDiv.classList.add('hidden');
    resultDiv.classList.add('hidden');
    errorDiv.classList.remove('hidden');
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
