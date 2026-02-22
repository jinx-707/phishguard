# PhishGuard System Flow Diagram

## Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER OPENS WEBSITE                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BLOCKER.JS LOADS FIRST                        │
│                    (document_start)                              │
│  • Registers handleRiskDecision() function                       │
│  • Sets up overlay protection                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONTENT.JS SCANS PAGE                         │
│  • Extract metadata (URL, domain, title)                         │
│  • Extract DOM indicators (forms, inputs, iframes)               │
│  • Detect suspicious signals (redirects, long URLs)              │
│  • Extract text content (first 2000 chars)                       │
│  • Detect login indicators                                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CHECK CACHE (5 min TTL)                       │
│                  chrome.storage.local                            │
└────────────┬───────────────────────────────┬────────────────────┘
             │                               │
        CACHE HIT                       CACHE MISS
             │                               │
             ▼                               ▼
    ┌────────────────┐          ┌──────────────────────────┐
    │  Use Cached    │          │  Send to Background.js   │
    │  Risk Data     │          │  via chrome.runtime      │
    └────────┬───────┘          └────────────┬─────────────┘
             │                               │
             │                               ▼
             │                  ┌──────────────────────────┐
             │                  │   BACKGROUND.JS          │
             │                  │   POST /scan             │
             │                  │   Timeout: 5 seconds     │
             │                  └────────────┬─────────────┘
             │                               │
             │                               ▼
             │                  ┌──────────────────────────┐
             │                  │   BACKEND API            │
             │                  │   Calculate Risk Score   │
             │                  │   • Suspicious keywords  │
             │                  │   • Password fields      │
             │                  │   • External links       │
             │                  │   • URL length           │
             │                  │   • Subdomains           │
             │                  └────────────┬─────────────┘
             │                               │
             │                               ▼
             │                  ┌──────────────────────────┐
             │                  │   Return Risk Verdict    │
             │                  │   {                      │
             │                  │     risk: "HIGH",        │
             │                  │     confidence: 0.85,    │
             │                  │     reasons: [...]       │
             │                  │   }                      │
             │                  └────────────┬─────────────┘
             │                               │
             │                               ▼
             │                  ┌──────────────────────────┐
             │                  │   Cache Result           │
             │                  │   chrome.storage.local   │
             │                  └────────────┬─────────────┘
             │                               │
             └───────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              DECISION ENGINE (blocker.js)                        │
│              handleRiskDecision(response)                        │
└────────────┬────────────────────┬────────────────┬──────────────┘
             │                    │                │
        RISK = HIGH          RISK = MEDIUM    RISK = LOW
             │                    │                │
             ▼                    ▼                ▼
┌──────────────────────┐  ┌──────────────┐  ┌──────────────┐
│  FULL BLOCK OVERLAY  │  │ WARNING      │  │  DO NOTHING  │
│                      │  │ BANNER       │  │              │
│  • Cover viewport    │  │              │  │  Silent      │
│  • Disable page      │  │ • Top banner │  │  operation   │
│  • Show reasons      │  │ • Dismissible│  │              │
│  • 2 buttons:        │  │ • View       │  │              │
│    - Go Back         │  │   details    │  │              │
│    - Proceed Anyway  │  │              │  │              │
└──────────┬───────────┘  └──────┬───────┘  └──────────────┘
           │                     │
           │                     │
           ▼                     ▼
    ┌──────────────┐      ┌──────────────┐
    │ USER ACTION  │      │ USER ACTION  │
    └──────┬───────┘      └──────┬───────┘
           │                     │
     ┌─────┴─────┐               │
     │           │               │
     ▼           ▼               ▼
┌─────────┐ ┌──────────┐  ┌──────────┐
│ Go Back │ │ Proceed  │  │ Dismiss  │
│         │ │ Anyway   │  │ Banner   │
└────┬────┘ └────┬─────┘  └────┬─────┘
     │           │              │
     ▼           ▼              ▼
┌─────────┐ ┌──────────────────────────┐ ┌──────────┐
│history  │ │ 1. Remove overlay        │ │ Remove   │
│.back()  │ │ 2. Restore page          │ │ banner   │
│         │ │ 3. Store in session      │ │          │
│         │ │ 4. Send feedback:        │ │          │
│         │ │    POST /feedback        │ │          │
│         │ │    {                     │ │          │
│         │ │      url,                │ │          │
│         │ │      original_risk,      │ │          │
│         │ │      user_override: true │ │          │
│         │ │    }                     │ │          │
└─────────┘ └──────────────────────────┘ └──────────┘
```

## Component Interaction

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  content.js  │────▶│ background.js│────▶│  Backend API │
│              │     │              │     │              │
│ • Scan page  │     │ • POST /scan │     │ • Calculate  │
│ • Extract    │     │ • Timeout    │     │   risk       │
│   features   │     │ • Handle     │     │ • Return     │
│              │     │   response   │     │   verdict    │
└──────┬───────┘     └──────────────┘     └──────────────┘
       │
       │ chrome.runtime.sendMessage()
       │
       ▼
┌──────────────┐
│  blocker.js  │
│              │
│ • Receive    │
│   risk data  │
│ • Show       │
│   overlay/   │
│   banner     │
│ • Handle     │
│   user       │
│   actions    │
└──────────────┘
```

## Data Flow

```
Page Features
     │
     ▼
┌─────────────────────────────────────┐
│ {                                   │
│   url: "https://example.com",       │
│   domain: "example.com",            │
│   form_count: 2,                    │
│   password_fields: 1,               │
│   suspicious_keywords_found: [...], │
│   external_links: 10,               │
│   ...                               │
│ }                                   │
└─────────────────┬───────────────────┘
                  │
                  ▼
            Backend API
                  │
                  ▼
┌─────────────────────────────────────┐
│ {                                   │
│   risk: "HIGH",                     │
│   confidence: 0.85,                 │
│   reasons: [                        │
│     "Found suspicious keywords",    │
│     "Password fields detected",     │
│     "High external link count"      │
│   ]                                 │
│ }                                   │
└─────────────────┬───────────────────┘
                  │
                  ▼
          Decision Engine
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
    Block Page          Warn User
```

## Storage Architecture

```
chrome.storage.local
├── risk_cache_<url>
│   ├── data: { risk, confidence, reasons }
│   └── timestamp: 1708012800000
│
└── lastScan
    ├── url
    ├── result
    └── timestamp

chrome.storage.session
└── override_<url>
    ├── timestamp: 1708012800000
    └── original_risk: "HIGH"
```

## Security Protection Flow

```
Page Script Attempts to Remove Overlay
              │
              ▼
┌──────────────────────────────┐
│   MutationObserver Detects   │
│   Removal                    │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│   Log Warning                │
│   "[PhishGuard] Overlay      │
│   removal detected..."       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│   Re-inject Overlay          │
│   document.documentElement   │
│   .appendChild(overlay)      │
└──────────────────────────────┘
```

## Performance Timeline

```
0ms     blocker.js loads
        └─ Register functions
        
10ms    content.js starts scan
        └─ Extract features
        
15ms    Check cache
        ├─ HIT: Use cached (5ms)
        └─ MISS: Backend request
        
20ms    Send to background.js
        
25ms    POST to backend
        
200ms   Backend responds
        
205ms   Cache result
        
210ms   handleRiskDecision()
        
215ms   Inject overlay (< 50ms)
        
260ms   ✅ User sees block screen
```

## Error Handling Flow

```
Backend Request
      │
      ▼
┌─────────────┐
│  Timeout?   │
│  (5 sec)    │
└──┬──────┬───┘
   │      │
  YES    NO
   │      │
   ▼      ▼
┌─────┐ ┌──────┐
│ Log │ │ Parse│
│ Warn│ │ JSON │
└──┬──┘ └───┬──┘
   │        │
   └────┬───┘
        │
        ▼
┌───────────────┐
│ Return null   │
│ to content.js │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ NO BLOCKING   │
│ (Fail-safe)   │
└───────────────┘
```

This visual guide shows how all components work together to provide real-time phishing protection!
