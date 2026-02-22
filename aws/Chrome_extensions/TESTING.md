# PhishGuard Extension - Testing Guide

## Quick Start Testing

### 1. Start the Mock Backend

```bash
node mock-backend.js
```

You should see:
```
🛡️  PhishGuard Mock Backend Server
   Running on http://localhost:8000
   Endpoint: POST /scan

   Waiting for scan requests...
```

### 2. Load the Extension in Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top-right corner)
3. Click "Load unpacked"
4. Select the `phishguard-extension` folder
5. You should see "PhishGuard Scanner" in your extensions list

### 3. Test with the Test Page

Open `test-page.html` in Chrome:
```bash
open test-page.html  # macOS
# or just drag the file into Chrome
```

### 4. Check the Results

#### In Chrome DevTools Console (F12):
You should see logs like:
```
[PhishGuard] Page scanned
[PhishGuard] Sending data to backend...
[PhishGuard] Risk: HIGH (0.85)
[PhishGuard] Reasons: ["Found suspicious keywords: verify, urgent, account suspended", ...]
```

#### In Mock Backend Terminal:
You should see:
```
[Mock Backend] Received scan request:
  URL: file:///path/to/test-page.html
  Domain: 
  Forms: 1
  Password fields: 1
  External links: 3
  Suspicious keywords: ["verify", "urgent", "account suspended", ...]

[Mock Backend] Sending response:
  Risk: HIGH
  Confidence: 0.85
  Reasons: [...]
```

#### In Extension Popup:
1. Click the PhishGuard extension icon in Chrome toolbar
2. You should see:
   - Risk level badge (colored: red for HIGH, yellow for MEDIUM, green for LOW)
   - Confidence percentage
   - Current page URL
   - Timestamp of last scan
   - List of reasons

## Testing Different Scenarios

### Test 1: Safe Page (Low Risk)
Visit a legitimate site like `https://google.com`

Expected:
- Risk: LOW
- Few or no suspicious indicators
- Low confidence score

### Test 2: Login Page (Medium Risk)
Visit `https://github.com/login`

Expected:
- Risk: MEDIUM (has password field)
- Reasons include "Page contains password input fields"

### Test 3: Suspicious Page (High Risk)
Use the included `test-page.html`

Expected:
- Risk: HIGH
- Multiple reasons:
  - Suspicious keywords found
  - Password fields present
  - External links
  - Iframes
  - Hidden inputs

## Debugging

### Extension Not Scanning?

1. Check if extension is enabled in `chrome://extensions/`
2. Open DevTools (F12) and check Console for errors
3. Verify content script is injected:
   - In DevTools, go to Sources tab
   - Look for `content.js` under "Content scripts"

### Backend Not Receiving Requests?

1. Verify backend is running: `curl http://localhost:8000/scan`
2. Check for CORS errors in browser console
3. Verify extension has correct permissions in manifest.json

### Popup Not Showing Data?

1. Open popup
2. Right-click in popup → "Inspect"
3. Check console for errors
4. Verify chrome.storage has data:
   ```javascript
   chrome.storage.local.get('lastScan', console.log)
   ```

## Manual Testing Checklist

- [ ] Extension loads without errors
- [ ] Content script runs on page load
- [ ] Data is extracted correctly (check console logs)
- [ ] Backend receives POST request
- [ ] Backend response is valid JSON
- [ ] Response is stored in chrome.storage
- [ ] Popup displays last scan result
- [ ] Risk level colors are correct
- [ ] Confidence percentage displays
- [ ] Reasons list shows (when available)
- [ ] Extension handles backend offline gracefully
- [ ] No performance issues (page loads normally)
- [ ] Works on HTTP and HTTPS pages
- [ ] Works on different domains

## Performance Testing

### Check Page Load Impact

1. Open DevTools → Performance tab
2. Start recording
3. Navigate to a page
4. Stop recording
5. Look for PhishGuard activity
6. Verify it doesn't block page rendering

### Expected Performance:
- Content script execution: < 50ms
- Feature extraction: < 100ms
- No blocking of page load
- Runs after `document_idle`

## Security Testing

### Verify No Unsafe Practices

1. Search codebase for `eval(` - should find none
2. Check for `innerHTML` with user data - should find none
3. Verify all external data is sanitized
4. Check permissions in manifest.json - should be minimal

### Test Error Handling

1. Stop backend server
2. Navigate to a page
3. Verify extension logs warning but doesn't crash
4. Check popup shows "Unable to connect to backend"

## Common Issues

### Issue: "Failed to fetch"
**Solution:** Ensure backend is running on port 8000

### Issue: Extension icon not showing
**Solution:** Add icon PNG files or remove icons field from manifest.json

### Issue: Content script not running
**Solution:** Check run_at is "document_idle" and matches is "<all_urls>"

### Issue: Popup shows "No scan data available"
**Solution:** Navigate to a page first, then open popup

## Next Steps

After Phase 1 testing is complete:
- Phase 2: Add UI blocking for high-risk pages
- Phase 2: Add user warnings and confirmations
- Phase 2: Add whitelist/blacklist functionality
- Phase 2: Add settings page
