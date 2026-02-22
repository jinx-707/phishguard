# 🚀 PhishGuard - Quick Start Guide

## 3-Step Setup

### Step 1: Start Backend
```bash
node mock-backend.js
```

### Step 2: Load Extension
1. Open `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select this folder

### Step 3: Test
Open `test-page.html` in Chrome and check:
- Console logs: `[PhishGuard] Risk: HIGH (0.85)`
- Extension icon → Click to see results

## What It Does

✅ Automatically scans every webpage
✅ Extracts 20+ security indicators
✅ Sends to backend API
✅ Shows risk level in popup

## Key Files

| File | Purpose |
|------|---------|
| `manifest.json` | Extension config |
| `content.js` | Page scanner (runs on every page) |
| `background.js` | API communication |
| `popup.html/js` | Results viewer |
| `mock-backend.js` | Test server |

## Data Extracted

- Page metadata (URL, title, domain)
- Forms, password fields, hidden inputs
- Iframes, external scripts, external links
- Suspicious keywords (verify, urgent, etc.)
- URL length, subdomain count
- First 2000 chars of visible text

## Expected Response Format

```json
{
  "risk": "LOW | MEDIUM | HIGH",
  "confidence": 0.0-1.0,
  "reasons": ["reason1", "reason2"]
}
```

## Console Logs

```
[PhishGuard] Page scanned
[PhishGuard] Sending data to backend...
[PhishGuard] Risk: HIGH (0.91)
```

## Troubleshooting

**No logs?** → Check extension is enabled
**Backend error?** → Ensure `node mock-backend.js` is running
**No popup data?** → Visit a page first, then click icon

## Phase 1 Complete ✅

- [x] Automatic scanning
- [x] Feature extraction
- [x] Backend communication
- [x] Error handling
- [x] Popup viewer
- [ ] UI blocking (Phase 2)
- [ ] User warnings (Phase 2)

## Next: Replace Mock Backend

Point to your real API by changing in `background.js`:
```javascript
const API_ENDPOINT = 'https://your-api.com/scan';
```
