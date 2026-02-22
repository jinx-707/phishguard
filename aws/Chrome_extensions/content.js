// PhishGuard Content Script - Page Data Extraction Engine
(() => {
  'use strict';

  let hasScanned = false;

  /**
   * Extract all page metadata
   */
  function extractMetadata() {
    return {
      url: window.location.href,
      domain: window.location.hostname,
      title: document.title || '',
      referrer: document.referrer || '',
      protocol: window.location.protocol.replace(':', '')
    };
  }

  /**
   * Extract DOM risk indicators
   */
  function extractDOMIndicators() {
    const forms = document.querySelectorAll('form');
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    const hiddenInputs = document.querySelectorAll('input[type="hidden"]');
    const iframes = document.querySelectorAll('iframe');
    const externalScripts = document.querySelectorAll('script[src]');
    const allLinks = document.querySelectorAll('a[href]');
    
    // Count external links efficiently
    const origin = window.location.origin;
    let externalLinkCount = 0;
    
    for (const link of allLinks) {
      try {
        const href = link.getAttribute('href');
        if (href && href.startsWith('http')) {
          const linkUrl = new URL(href);
          if (linkUrl.origin !== origin) {
            externalLinkCount++;
          }
        }
      } catch (e) {
        // Invalid URL, skip
      }
    }

    return {
      form_count: forms.length,
      password_fields: passwordInputs.length,
      hidden_inputs: hiddenInputs.length,
      iframe_count: iframes.length,
      external_scripts: externalScripts.length,
      total_links: allLinks.length,
      external_links: externalLinkCount
    };
  }

  /**
   * Detect suspicious behavioral signals
   */
  function detectSuspiciousSignals() {
    const url = window.location.href;
    const urlLength = url.length;
    
    // Check for redirect
    let hasRedirect = false;
    try {
      hasRedirect = document.referrer && 
        new URL(document.referrer).hostname !== window.location.hostname;
    } catch (e) {
      // Invalid referrer
    }
    
    // Check subdomain count
    const hostname = window.location.hostname;
    const parts = hostname.split('.');
    const subdomainCount = Math.max(0, parts.length - 2);
    
    // Check for suspicious keywords in URL
    const suspiciousUrlKeywords = ['login', 'verify', 'account', 'secure', 'update', 'confirm'];
    const urlLower = url.toLowerCase();
    const hasSuspiciousUrl = suspiciousUrlKeywords.some(keyword => urlLower.includes(keyword));
    
    return {
      loaded_via_redirect: hasRedirect,
      url_length: urlLength,
      long_url: urlLength > 100,
      subdomain_count: subdomainCount,
      excessive_subdomains: subdomainCount > 3,
      suspicious_url_keywords: hasSuspiciousUrl
    };
  }

  /**
   * Extract and analyze visible text content
   */
  function extractTextContent() {
    const body = document.body;
    if (!body) return { text_snippet: '', suspicious_keywords_found: [] };
    
    // Get visible text efficiently
    let text = body.innerText || body.textContent || '';
    
    // Clean whitespace
    text = text.replace(/\s+/g, ' ').trim();
    
    // Take first 2000 characters
    const textSnippet = text.slice(0, 2000);
    
    // Scan for suspicious keywords
    const suspiciousKeywords = [
      'verify',
      'urgent',
      'account suspended',
      'reset password',
      'confirm your identity',
      'unusual activity',
      'click here immediately',
      'verify your account',
      'suspended account',
      'update payment'
    ];
    
    const textLower = textSnippet.toLowerCase();
    const foundKeywords = suspiciousKeywords.filter(keyword => 
      textLower.includes(keyword)
    );
    
    return {
      text_snippet: textSnippet,
      suspicious_keywords_found: foundKeywords
    };
  }

  /**
   * Check if page has login indicators
   */
  function detectLoginPage() {
    const hasPasswordField = document.querySelectorAll('input[type="password"]').length > 0;
    const title = document.title.toLowerCase();
    const bodyText = (document.body?.innerText || '').toLowerCase().slice(0, 1000);
    
    const loginKeywords = ['login', 'sign in', 'log in', 'signin'];
    const hasLoginKeyword = loginKeywords.some(keyword => 
      title.includes(keyword) || bodyText.includes(keyword)
    );
    
    return {
      has_login_indicators: hasPasswordField || hasLoginKeyword,
      has_password_field: hasPasswordField
    };
  }

  /**
   * Main extraction function - combines all extractors
   */
  function extractAllFeatures() {
    try {
      const metadata = extractMetadata();
      const domIndicators = extractDOMIndicators();
      const suspiciousSignals = detectSuspiciousSignals();
      const textContent = extractTextContent();
      const loginIndicators = detectLoginPage();

      return {
        ...metadata,
        ...domIndicators,
        ...suspiciousSignals,
        ...textContent,
        ...loginIndicators,
        timestamp: Date.now()
      };
    } catch (error) {
      console.error('[PhishGuard] Feature extraction error:', error);
      return null;
    }
  }

  /**
   * Check if URL is cached in session
   */
  async function getCachedRisk(url) {
    try {
      const result = await chrome.storage.local.get(`risk_cache_${url}`);
      const cached = result[`risk_cache_${url}`];
      
      if (cached && (Date.now() - cached.timestamp < 300000)) { // 5 min cache
        return cached.data;
      }
      return null;
    } catch (error) {
      return null;
    }
  }

  /**
   * Cache risk result
   */
  async function cacheRiskResult(url, data) {
    try {
      await chrome.storage.local.set({
        [`risk_cache_${url}`]: {
          data,
          timestamp: Date.now()
        }
      });
    } catch (error) {
      console.warn('[PhishGuard] Cache error:', error);
    }
  }

  /**
   * Run local AI inference first (Phase 3)
   */
  async function runLocalInference(payload) {
    if (!window.phishGuardLocalAI) {
      console.warn('[PhishGuard] Local AI not available');
      return null;
    }

    try {
      const result = await window.phishGuardLocalAI.runInference(
        payload.text_snippet,
        {
          password_fields: payload.password_fields,
          hidden_inputs: payload.hidden_inputs,
          external_links: payload.external_links,
          long_url: payload.long_url,
          excessive_subdomains: payload.excessive_subdomains,
          suspicious_url_keywords: payload.suspicious_url_keywords,
          iframe_count: payload.iframe_count
        }
      );

      return result;
    } catch (error) {
      console.error('[PhishGuard] Local inference failed:', error);
      return null;
    }
  }

  /**
   * Hybrid decision engine - local AI + backend
   */
  async function makeHybridDecision(url, payload, localResult) {
    // If local risk is LOW, trust it and skip backend
    if (localResult && localResult.local_risk === 'LOW' && localResult.local_confidence > 0.7) {
      console.log('[PhishGuard] Local AI: LOW risk, skipping backend');
      
      const decision = {
        risk: 'LOW',
        confidence: localResult.local_confidence,
        reasons: ['Local AI assessment: Low threat'],
        source: 'local_only',
        inference_time: localResult.inference_time_ms
      };

      await cacheRiskResult(url, decision);
      return decision;
    }

    // For MEDIUM or HIGH local risk, verify with backend
    console.log(`[PhishGuard] Local AI: ${localResult?.local_risk || 'UNKNOWN'}, requesting backend verification...`);

    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { 
          type: 'SCAN_PAGE', 
          payload: {
            ...payload,
            local_result: localResult
          }
        },
        async (response) => {
          if (chrome.runtime.lastError) {
            console.warn('[PhishGuard] Backend unavailable:', chrome.runtime.lastError.message);
            
            // Fallback to local AI result
            if (localResult) {
              console.log('[PhishGuard] Using local AI result (offline mode)');
              const fallbackDecision = {
                risk: localResult.local_risk,
                confidence: localResult.local_confidence,
                reasons: ['Backend unavailable - Local AI assessment'],
                source: 'local_fallback',
                inference_time: localResult.inference_time_ms
              };
              resolve(fallbackDecision);
            } else {
              resolve(null);
            }
            return;
          }

          if (response) {
            // Backend response takes priority
            const { risk, confidence, reasons } = response;
            console.log(`[PhishGuard] Backend verdict: ${risk} (${confidence})`);
            
            const finalDecision = {
              ...response,
              source: 'backend',
              local_result: localResult
            };

            await cacheRiskResult(url, finalDecision);
            resolve(finalDecision);
          } else {
            // Backend failed, use local result
            if (localResult) {
              console.log('[PhishGuard] Backend failed, using local AI result');
              const fallbackDecision = {
                risk: localResult.local_risk,
                confidence: localResult.local_confidence,
                reasons: ['Backend error - Local AI assessment'],
                source: 'local_fallback',
                inference_time: localResult.inference_time_ms
              };
              resolve(fallbackDecision);
            } else {
              resolve(null);
            }
          }
        }
      );
    });
  }

  /**
   * Run the page scan with hybrid AI
   */
  async function runPageScan() {
    // Prevent multiple scans
    if (hasScanned) return;
    hasScanned = true;

    const url = window.location.href;

    // Check cache first
    const cached = await getCachedRisk(url);
    if (cached) {
      console.log('[PhishGuard] Using cached risk data');
      if (window.phishGuardBlocker) {
        window.phishGuardBlocker.handleRiskDecision(cached);
      }
      return;
    }

    console.log('[PhishGuard] Page scanned - Starting hybrid analysis');

    const payload = extractAllFeatures();
    
    if (!payload) {
      console.warn('[PhishGuard] Failed to extract features');
      return;
    }

    // Phase 3: Run local AI inference first
    const localResult = await runLocalInference(payload);

    // Phase 3: Hybrid decision (local + backend)
    const finalDecision = await makeHybridDecision(url, payload, localResult);

    if (finalDecision) {
      const { risk, confidence, reasons } = finalDecision;
      console.log(`[PhishGuard] Final decision: ${risk} (${confidence}) [${finalDecision.source}]`);
      
      if (reasons && reasons.length > 0) {
        console.log('[PhishGuard] Reasons:', reasons);
      }

      // Handle risk decision (block/warn)
      if (window.phishGuardBlocker) {
        window.phishGuardBlocker.handleRiskDecision(finalDecision);
      }
    }
  }

  // Run scan when page is fully loaded
  if (document.readyState === 'loading') {
    window.addEventListener('load', runPageScan, { once: true });
  } else {
    // Page already loaded
    runPageScan();
  }
})();
