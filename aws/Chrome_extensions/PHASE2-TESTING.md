# Phase 2 Testing Guide

## Quick Start

### 1. Start the Mock Backend
```bash
cd Chrome_extensions
node mock-backend.js
```

You should see:
```
🛡️  PhishGuard Mock Backend Server
   Running on http://localhost:8000
   Endpoints:
     POST /scan - Analyze page risk
     POST /feedback - Log user overrides

   Waiting for requests...
```

### 2. Load Extension in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top-right)
3. Click "Load unpacked"
4. Select the `Chrome_extensions` folder
5. Extension should appear with PhishGuard icon

### 3. Open Test Page

Open `test-page.html` in Chrome (drag file into browser or use File → Open)

## Test Scenarios

### Test 1: Low Risk (Default State)
**Action**: Load test page without clicking any buttons

**Expected Result**:
- No overlay or banner appears
- Page functions normally
- Console shows: `[PhishGuard] Risk: LOW`

**Pass Criteria**: ✅ Silent operation, no user interruption

---

### Test 2: Medium Risk Warning
**Action**: Click "Test Medium Risk" button

**Expected Result**:
- Orange warning banner appears at top
- Banner text: "This page shows suspicious signals. Proceed with caution."
- "View Details" button shows reasons
- "×" button dismisses banner
- Page remains functional underneath

**Pass Criteria**: 
- ✅ Banner appears
- ✅ Can dismiss banner
- ✅ Can view details
- ✅ Page still usable

---

### Test 3: High Risk Block
**Action**: Click "Test High Risk" button

**Expected Result**:
- Full-screen dark overlay covers entire page
- White card in center with:
  - 🛑 Red warning icon
  - "Phishing Threat Detected" title
  - Risk level: HIGH
  - List of specific reasons
  - "Go Back to Safety" button (blue)
  - "Proceed Anyway" button (red outline)
- Cannot scroll or click underlying page
- Cannot close overlay with Escape key

**Pass Criteria**:
- ✅ Overlay covers entire viewport
- ✅ Page interaction disabled
- ✅ Reasons displayed clearly
- ✅ Both buttons functional

---

### Test 4: User Override
**Action**: On HIGH risk page, click "Proceed Anyway"

**Expected Result**:
- Overlay disappears
- Page becomes interactive
- Console shows: `[PhishGuard] User override triggered`
- Backend logs feedback (check backend console)
- Reloading page does NOT re-block (session memory)

**Pass Criteria**:
- ✅ Overlay removed
- ✅ Page functional
- ✅ Override logged to backend
- ✅ No re-block on reload

---

### Test 5: Go Back Safety
**Action**: On HIGH risk page, click "Go Back to Safety"

**Expected Result**:
- Browser navigates back to previous page
- If no history, may show blank page

**Pass Criteria**: ✅ Navigation works correctly

---

### Test 6: Cache Performance
**Action**: 
1. Load test page (any risk level)
2. Reload page immediately

**Expected Result**:
- First load: Backend request sent
- Second load: Console shows `[PhishGuard] Using cached risk data`
- No backend request on second load
- Same blocking behavior

**Pass Criteria**: ✅ Cache prevents redundant requests

---

### Test 7: Backend Offline
**Action**:
1. Stop mock backend (Ctrl+C)
2. Load test page

**Expected Result**:
- Console shows: `[PhishGuard] Backend unavailable`
- NO blocking occurs (fail-safe)
- Page loads normally

**Pass Criteria**: ✅ Graceful degradation, no false positives

---

### Test 8: Overlay Protection
**Action**: 
1. Trigger HIGH risk block
2. Open browser console
3. Try to remove overlay: `document.getElementById('phishguard-overlay').remove()`

**Expected Result**:
- Overlay is removed briefly
- Console shows: `[PhishGuard] Overlay removal detected, re-injecting...`
- Overlay reappears immediately

**Pass Criteria**: ✅ Overlay protected from removal

---

## Console Monitoring

### Expected Log Sequence (HIGH Risk)
```
[PhishGuard] Page scanned
[PhishGuard] Sending data to backend...
[PhishGuard] Risk: HIGH (0.85)
[PhishGuard] Reasons: ["Found suspicious keywords: verify, urgent, account suspended", ...]
[PhishGuard] Blocking page...
```

### Backend Console (HIGH Risk)
```
[Mock Backend] Received scan request:
  URL: file:///path/to/test-page.html
  Domain: 
  Forms: 2
  Password fields: 3
  External links: 10
  Suspicious keywords: ["verify", "urgent", "account suspended", ...]

[Mock Backend] Sending response:
  Risk: HIGH
  Confidence: 0.85
  Reasons: [...]
```

### Override Feedback (Backend)
```
[Mock Backend] Received user override feedback:
  URL: file:///path/to/test-page.html
  Original Risk: HIGH
  User Override: true
  Timestamp: 2026-02-14T...
```

## Troubleshooting

### Issue: No overlay appears on HIGH risk
**Check**:
- Backend is running
- Console shows risk level
- No JavaScript errors
- `blocker.js` loaded before `content.js` in manifest

### Issue: Overlay appears but page still clickable
**Check**:
- `document.body.style.pointerEvents` is set to "none"
- Overlay has `z-index: 2147483647`
- No CSS conflicts

### Issue: Banner doesn't dismiss
**Check**:
- Click the "×" button (not outside banner)
- Check console for errors

### Issue: Cache not working
**Check**:
- `chrome.storage.local` permissions in manifest
- Console for cache-related errors
- Cache expires after 5 minutes

### Issue: Backend not receiving requests
**Check**:
- Backend running on port 8000
- CORS headers present
- Network tab shows POST to `http://localhost:8000/scan`

## Performance Checklist

- [ ] Overlay appears in < 50ms
- [ ] No visible layout shift
- [ ] No console errors
- [ ] Backend responds in < 1 second
- [ ] Cache lookup instant
- [ ] No memory leaks (check with multiple page loads)

## Success Criteria Summary

Phase 2 is complete when ALL tests pass:
- ✅ LOW risk: Silent operation
- ✅ MEDIUM risk: Warning banner
- ✅ HIGH risk: Full block overlay
- ✅ User override: Logs and removes block
- ✅ Go back: Navigation works
- ✅ Cache: Prevents redundant requests
- ✅ Offline: Graceful degradation
- ✅ Protection: Overlay cannot be removed
- ✅ Performance: Fast and smooth
- ✅ No broken websites
