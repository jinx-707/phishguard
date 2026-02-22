# PhishGuard Phase 2 - Quick Reference Card

## 🚀 Quick Start (30 seconds)

```bash
# 1. Start backend
node mock-backend.js

# 2. Load extension
# Chrome → chrome://extensions/ → Load unpacked → Select folder

# 3. Test
# Open test-page.html → Click "Test High Risk"
```

## 📁 Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `blocker.js` | Block overlay & warning system | 419 |
| `content.js` | Page scanner & feature extraction | 283 |
| `background.js` | API communication | 158 |
| `overlay.css` | Overlay styles | 40 |
| `manifest.json` | Extension config | 30 |

## 🎯 Risk Levels

| Risk | Action | User Experience |
|------|--------|-----------------|
| **HIGH** | Full-screen block | Cannot interact with page |
| **MEDIUM** | Warning banner | Can dismiss, page usable |
| **LOW** | Silent | No interruption |

## 🔧 API Endpoints

### POST /scan
```json
Request: { url, domain, form_count, ... }
Response: { risk: "HIGH", confidence: 0.85, reasons: [...] }
```

### POST /feedback
```json
Request: { url, original_risk, user_override: true, timestamp }
Response: { success: true }
```

## 🧪 Testing Commands

```bash
# Start backend
node mock-backend.js

# Check extension loaded
chrome://extensions/

# View logs
F12 → Console → Filter: [PhishGuard]

# Test scenarios
Open test-page.html
Click: "Test Low Risk" | "Test Medium Risk" | "Test High Risk"
```

## 📊 Expected Behavior

### LOW Risk
```
✓ No overlay
✓ No banner
✓ Silent operation
✓ Console: [PhishGuard] Risk: LOW
```

### MEDIUM Risk
```
✓ Orange banner at top
✓ "View Details" button
✓ Dismissible with ×
✓ Page remains functional
```

### HIGH Risk
```
✓ Full-screen dark overlay
✓ White security card
✓ Threat details + reasons
✓ "Go Back" + "Proceed Anyway" buttons
✓ Page interaction disabled
✓ Cannot be removed by page scripts
```

## 🔍 Console Logs

```javascript
[PhishGuard] Page scanned
[PhishGuard] Sending data to backend...
[PhishGuard] Risk: HIGH (0.85)
[PhishGuard] Reasons: [...]
[PhishGuard] Blocking page...
[PhishGuard] User override triggered
[PhishGuard] Using cached risk data
```

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| No overlay on HIGH risk | Check backend running, console for errors |
| Overlay but page clickable | Check `pointerEvents: none` applied |
| Banner won't dismiss | Click × button, check console |
| Backend not responding | Verify port 8000, check CORS |
| Cache not working | Check `chrome.storage.local` permissions |

## 📦 Storage

```javascript
// Risk cache (5 min TTL)
chrome.storage.local.set({
  'risk_cache_<url>': { data, timestamp }
});

// User override (session only)
chrome.storage.session.set({
  'override_<url>': { timestamp, original_risk }
});
```

## ⚡ Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| Overlay injection | < 50ms | ✅ |
| Backend response | < 1s | ✅ |
| Cache lookup | < 5ms | ✅ |
| Memory usage | < 50MB | ✅ |

## 🔐 Security Features

- ✅ MutationObserver protects overlay
- ✅ Re-injects if removed
- ✅ Isolated CSS prevents conflicts
- ✅ Session-based override tracking
- ✅ Fail-safe: No blocking without backend confirmation

## 📝 Key Functions

```javascript
// blocker.js
triggerBlockOverlay(response)    // Show full-screen block
showWarningBanner(response)      // Show warning banner
handleUserOverride(response)     // Process user override
handleRiskDecision(response)     // Route based on risk

// content.js
extractAllFeatures()             // Scan page
getCachedRisk(url)              // Check cache
cacheRiskResult(url, data)      // Store result
runPageScan()                   // Main entry point

// background.js
sendToBackend(payload)          // POST /scan
sendFeedback(payload)           // POST /feedback
```

## 🎨 UI Components

### Block Overlay
- Background: `rgba(0, 0, 0, 0.95)`
- Z-index: `2147483647`
- Card: White, rounded, centered
- Icon: 🛑 (64px)
- Buttons: Blue (safe) + Red outline (danger)

### Warning Banner
- Background: `#ff9800` (orange)
- Position: Fixed top
- Z-index: `2147483646`
- Dismissible: × button
- Details: Alert with reasons

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| `README.md` | Main overview |
| `PHASE2-COMPLETE.md` | Full Phase 2 docs |
| `PHASE2-TESTING.md` | Testing guide |
| `PHASE2-SUMMARY.md` | Implementation summary |
| `SYSTEM-FLOW.md` | Visual diagrams |
| `DEPLOYMENT-CHECKLIST.md` | Pre-deployment checks |

## 🎯 Completion Criteria

- [x] HIGH-risk pages blocked instantly
- [x] Overlay protected from removal
- [x] MEDIUM risk shows banner
- [x] User override with logging
- [x] Risk caching (5 min)
- [x] Session override memory
- [x] Explainable alerts
- [x] Performance < 50ms
- [x] Professional UI
- [x] Graceful failure
- [x] Complete documentation

## 🚦 Status

**Phase 2: ✅ COMPLETE**

All objectives met. Ready for testing and deployment.

---

## Quick Commands Cheat Sheet

```bash
# Development
node mock-backend.js              # Start backend
chrome://extensions/              # Manage extensions
F12                              # Open DevTools

# Testing
Open test-page.html              # Load test page
Click "Test High Risk"           # Trigger block
Check console for logs           # Verify behavior

# Debugging
document.getElementById('phishguard-overlay')  # Check overlay
chrome.storage.local.get()                     # Check cache
chrome.storage.session.get()                   # Check overrides
```

## Support

- Issues: Check console logs first
- Backend: Verify running on port 8000
- Cache: Clear with `chrome.storage.local.clear()`
- Session: Cleared on browser close

---

**Version**: 2.0.0  
**Last Updated**: Phase 2 Complete  
**Status**: Production Ready
