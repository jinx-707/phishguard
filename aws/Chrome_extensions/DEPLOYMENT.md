# PhishGuard Extension - Deployment Guide

## Moving from Mock to Production Backend

### Step 1: Update API Endpoint

Edit `background.js` and change:

```javascript
// FROM:
const API_ENDPOINT = 'http://localhost:8000/scan';

// TO:
const API_ENDPOINT = 'https://your-production-api.com/scan';
```

### Step 2: Update Timeout (Optional)

If your production API is slower, increase timeout:

```javascript
// FROM:
const REQUEST_TIMEOUT_MS = 5000;

// TO:
const REQUEST_TIMEOUT_MS = 10000; // 10 seconds
```

### Step 3: Add Icons

Replace placeholder icons in `icons/` folder:
- `icon16.png` - 16x16 pixels
- `icon48.png` - 48x48 pixels  
- `icon128.png` - 128x128 pixels

Or remove the `icons` field from `manifest.json` if not ready.

### Step 4: Test with Production API

1. Ensure your backend API is running
2. Test the `/scan` endpoint manually:

```bash
curl -X POST https://your-api.com/scan \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "domain": "example.com",
    "title": "Example",
    "form_count": 0,
    "password_fields": 0
  }'
```

Expected response:
```json
{
  "risk": "LOW",
  "confidence": 0.85,
  "reasons": []
}
```

### Step 5: Update Extension

1. Go to `chrome://extensions/`
2. Click "Reload" button on PhishGuard extension
3. Test on a real webpage
4. Check console for successful API calls

## Backend API Requirements

Your production backend must:

### 1. Accept POST Requests
```
POST /scan
Content-Type: application/json
```

### 2. Handle CORS (if different origin)
```javascript
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

### 3. Accept This Payload Structure
```javascript
{
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
```

### 4. Return This Response Structure
```javascript
{
  risk: "LOW" | "MEDIUM" | "HIGH",
  confidence: 0.0 - 1.0,  // Optional
  reasons: string[]        // Optional
}
```

### 5. Handle Errors Gracefully
- Return 200 OK for successful scans
- Return 400 Bad Request for invalid payloads
- Return 500 Internal Server Error for processing errors
- Always return valid JSON

## Publishing to Chrome Web Store

### Prerequisites
- Google Developer account ($5 one-time fee)
- Extension icons (16, 48, 128 px)
- Screenshots for store listing
- Privacy policy (if collecting data)

### Steps

1. **Prepare Package**
   ```bash
   # Remove development files
   rm -rf .git .vscode test-page.html mock-backend.js
   rm TESTING.md DEPLOYMENT.md PHASE1-CHECKLIST.md
   
   # Create zip
   zip -r phishguard-extension.zip . -x "*.git*" -x "*node_modules*"
   ```

2. **Create Developer Account**
   - Go to [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
   - Pay $5 registration fee

3. **Upload Extension**
   - Click "New Item"
   - Upload `phishguard-extension.zip`
   - Fill in store listing details

4. **Store Listing Requirements**
   - Name: "PhishGuard Scanner"
   - Description: 132 characters minimum
   - Category: Productivity or Security
   - Language: English
   - Screenshots: At least 1 (1280x800 or 640x400)
   - Small tile icon: 440x280
   - Privacy policy URL (if applicable)

5. **Privacy Considerations**
   - Disclose what data is collected
   - Explain how data is used
   - Provide privacy policy if sending data to server
   - Be transparent about backend communication

6. **Submit for Review**
   - Review can take 1-3 days
   - Address any feedback from Google
   - Once approved, extension goes live

## Security Checklist Before Production

- [ ] HTTPS endpoint (not HTTP)
- [ ] API authentication (if needed)
- [ ] Rate limiting on backend
- [ ] Input validation on backend
- [ ] Sanitize all user data
- [ ] No sensitive data in logs
- [ ] Secure storage of API keys (if any)
- [ ] Content Security Policy configured
- [ ] No eval() or unsafe practices
- [ ] Error messages don't leak info

## Performance Checklist

- [ ] Backend responds in < 2 seconds
- [ ] Extension doesn't slow page loads
- [ ] Memory usage is reasonable
- [ ] No memory leaks
- [ ] Efficient DOM queries
- [ ] Minimal storage usage

## Monitoring & Analytics

Consider adding:
- Error tracking (Sentry, Rollbar)
- Usage analytics (Google Analytics)
- Performance monitoring
- User feedback mechanism
- Crash reporting

## Maintenance

### Regular Updates
- Update manifest version for each release
- Test with latest Chrome version
- Update dependencies
- Monitor user reviews
- Fix reported bugs

### Version Numbering
Follow semantic versioning:
- `1.0.0` - Initial release
- `1.0.1` - Bug fixes
- `1.1.0` - New features
- `2.0.0` - Breaking changes

## Rollback Plan

If issues occur in production:

1. **Quick Fix**
   - Fix bug in code
   - Increment version
   - Upload new version
   - Submit for review

2. **Emergency Rollback**
   - Unpublish current version
   - Revert to previous version
   - Notify users

3. **Communication**
   - Update store description
   - Post on support channels
   - Email affected users (if possible)

## Support

Provide support channels:
- GitHub Issues (if open source)
- Support email
- FAQ page
- Documentation site

## Legal Considerations

- Terms of Service
- Privacy Policy
- Data retention policy
- GDPR compliance (if EU users)
- CCPA compliance (if CA users)
- User consent for data collection

## Cost Considerations

- Chrome Web Store: $5 one-time
- Backend hosting: Variable
- Domain name: ~$10-15/year
- SSL certificate: Free (Let's Encrypt)
- Monitoring tools: Free tier available

## Success Metrics

Track:
- Daily active users
- Scans per day
- Detection accuracy
- False positive rate
- User retention
- Average response time
- Error rate

## Next Steps After Deployment

1. Monitor initial user feedback
2. Fix critical bugs quickly
3. Gather feature requests
4. Plan Phase 2 features
5. Improve ML model based on data
6. Add user-requested features
7. Optimize performance
8. Expand documentation

## Phase 2 Feature Ideas

- UI blocking for high-risk pages
- User warnings with override option
- Whitelist/blacklist management
- Settings page
- Scan history
- Export reports
- Custom risk thresholds
- Offline mode
- Multi-language support
- Dark mode
