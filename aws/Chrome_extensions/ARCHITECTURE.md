# PhishGuard Extension - Architecture Overview

## System Flow

```
┌─────────────────────────────────────────────────────────────┐
│                         USER VISITS PAGE                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    CONTENT SCRIPT (content.js)               │
│  • Runs on document_idle                                     │
│  • Extracts page features (metadata, DOM, text)              │
│  • Detects suspicious signals                                │
│  • Scans for phishing keywords                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    chrome.runtime.sendMessage()
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              BACKGROUND SERVICE WORKER (background.js)       │
│  • Receives message from content script                      │
│  • Validates payload                                         │
│  • Sends POST to backend API                                 │
│  • Handles timeout (5s)                                      │
│  • Stores result in chrome.storage                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
                      HTTP POST /scan
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND API (your server)                 │
│  • Receives structured JSON payload                          │
│  • Analyzes features with ML model                           │
│  • Returns risk assessment                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    Response: { risk, confidence, reasons }
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  CHROME STORAGE (local)                      │
│  • Stores last scan result                                   │
│  • Persists across browser sessions                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    User clicks extension icon
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    POPUP (popup.html/js)                     │
│  • Reads from chrome.storage                                 │
│  • Displays risk level (color-coded)                         │
│  • Shows confidence, URL, timestamp                          │
│  • Lists reasons for risk assessment                         │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Content Script (content.js)
**Purpose:** Extract page features and send to background

**Key Functions:**
- `extractMetadata()` - URL, domain, title, referrer, protocol
- `extractDOMIndicators()` - Forms, inputs, iframes, links
- `detectSuspiciousSignals()` - URL analysis, redirects, subdomains
- `extractTextContent()` - Visible text + keyword scanning
- `detectLoginPage()` - Password fields, login keywords

**Performance:**
- Runs once per page load
- Non-blocking (async)
- Limits text to 2000 chars
- Single DOM traversal

**Security:**
- No eval()
- No innerHTML with user data
- Isolated from page scripts

### 2. Background Service Worker (background.js)
**Purpose:** Handle API communication and storage

**Key Functions:**
- `sendToBackend()` - POST request with timeout
- `storeScanResult()` - Save to chrome.storage
- Message listener for SCAN_PAGE events

**Error Handling:**
- 5-second timeout
- Graceful fallback if backend offline
- Response validation
- Safe JSON parsing

**Security:**
- Validates message structure
- Sanitizes response data
- No sensitive data exposure

### 3. Popup Interface (popup.html/js/css)
**Purpose:** Display scan results to user

**Features:**
- Risk level badge (color-coded)
- Confidence percentage
- URL display (truncated)
- Timestamp
- Reasons list
- Error state handling

**States:**
- Loading (spinner)
- Result (risk display)
- Error (backend unavailable)
- No data (first load)

### 4. Utilities (utils/extractor.js)
**Purpose:** Modular extraction functions (for future use)

**Note:** Currently, extraction logic is in content.js for simplicity. The utils folder provides a modular structure for Phase 2 enhancements.

## Data Flow

### Message Format (Content → Background)
```javascript
{
  type: "SCAN_PAGE",
  payload: {
    // Metadata
    url: string,
    domain: string,
    title: string,
    referrer: string,
    protocol: string,
    
    // DOM Indicators
    form_count: number,
    password_fields: number,
    hidden_inputs: number,
    iframe_count: number,
    external_scripts: number,
    total_links: number,
    external_links: number,
    
    // Suspicious Signals
    loaded_via_redirect: boolean,
    url_length: number,
    long_url: boolean,
    subdomain_count: number,
    excessive_subdomains: boolean,
    suspicious_url_keywords: boolean,
    
    // Text Content
    text_snippet: string,
    suspicious_keywords_found: string[],
    
    // Login Indicators
    has_login_indicators: boolean,
    has_password_field: boolean,
    
    timestamp: number
  }
}
```

### API Request (Background → Backend)
```javascript
POST http://localhost:8000/scan
Content-Type: application/json

{
  // Same as payload above
}
```

### API Response (Backend → Background)
```javascript
{
  risk: "LOW" | "MEDIUM" | "HIGH",
  confidence: 0.0 - 1.0,
  reasons: string[]
}
```

### Storage Format (Background → chrome.storage)
```javascript
{
  lastScan: {
    url: string,
    result: {
      risk: string,
      confidence: number,
      reasons: string[]
    },
    timestamp: number
  }
}
```

## Security Considerations

### Content Script Isolation
- Runs in isolated world (separate from page scripts)
- Cannot access page JavaScript variables
- Page cannot access extension variables

### Permissions (Minimal)
- `activeTab` - Access current tab only
- `scripting` - Inject content script
- `storage` - Store scan results
- `<all_urls>` - Scan any webpage

### Data Sanitization
- All backend responses parsed safely
- No eval() or Function() constructors
- No innerHTML with untrusted data
- URL validation before processing

### Error Boundaries
- Try/catch around all extraction
- Timeout on API requests
- Graceful degradation if backend offline
- No crashes on malformed data

## Performance Optimizations

### Content Script
- Runs at `document_idle` (after page load)
- Single DOM query per selector
- Text limited to 2000 characters
- No full array creation for link counting
- Prevents multiple scans with flag

### Background Script
- Async/await for non-blocking
- AbortController for timeout
- Minimal storage writes
- Efficient message passing

### Popup
- Reads from storage (no API call)
- Minimal DOM manipulation
- CSS-based styling (no JS animations)
- Lazy loading of data

## Extension Lifecycle

### Installation
1. User loads extension
2. `chrome.runtime.onInstalled` fires
3. Background service worker initializes
4. Extension icon appears in toolbar

### Page Visit
1. User navigates to page
2. Content script injected at `document_idle`
3. Features extracted
4. Message sent to background
5. Background sends to API
6. Response stored in chrome.storage
7. Console logs show result

### Popup Open
1. User clicks extension icon
2. Popup HTML loads
3. popup.js reads from chrome.storage
4. Results displayed
5. Popup closes when user clicks away

### Background Service Worker
- Starts on demand (Manifest V3)
- Terminates when idle
- Restarts on message
- No persistent background page

## Testing Strategy

### Unit Testing (Future)
- Test extraction functions individually
- Mock DOM elements
- Verify data structure

### Integration Testing
- Test message passing
- Test API communication
- Test storage operations

### Manual Testing
- Use test-page.html
- Use mock-backend.js
- Test on real websites
- Verify console logs

### Performance Testing
- Measure extraction time
- Check memory usage
- Verify no page blocking
- Test on slow connections

## Future Enhancements (Phase 2+)

### UI Blocking
- Intercept navigation on HIGH risk
- Show warning modal
- Allow user override
- Whitelist trusted sites

### Advanced Features
- Settings page
- Whitelist/blacklist management
- Scan history
- Export reports
- Custom risk thresholds

### Analytics
- Track scan statistics
- False positive reporting
- User feedback collection
- Performance metrics

### ML Integration
- On-device model inference
- Offline risk assessment
- Federated learning
- Model updates
