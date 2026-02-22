// PhishGuard Popup - Status Viewer

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

  try {
    // Retrieve last scan result from storage
    const data = await chrome.storage.local.get('lastScan');
    
    if (!data.lastScan) {
      showStatus('No scan data available');
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
