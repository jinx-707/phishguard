"""Comprehensive API tests for the Threat Intelligence Platform."""
import requests
import json

BASE_URL = 'http://localhost:8000'

def test_health():
    """Test health endpoint."""
    r = requests.get(f'{BASE_URL}/health')
    print(f'=== Health Endpoint ===')
    print(f'Status: {r.status_code}')
    print(f'Response: {r.json()}')
    print()
    return r.status_code == 200

def test_scan_url():
    """Test /scan with URL input."""
    r = requests.post(f'{BASE_URL}/scan', json={'url': 'https://google.com'})
    print(f'=== Scan URL ===')
    print(f'Status: {r.status_code}')
    result = r.json()
    print(f'Risk: {result.get("risk")}')
    print(f'Confidence: {result.get("confidence")}')
    print(f'Total Score: {result.get("total_score")}')
    print()
    return r.status_code == 200

def test_scan_text():
    """Test /scan with text input."""
    r = requests.post(f'{BASE_URL}/scan', json={'text': 'This is a test email content'})
    print(f'=== Scan Text ===')
    print(f'Status: {r.status_code}')
    result = r.json()
    print(f'Risk: {result.get("risk")}')
    print(f'Confidence: {result.get("confidence")}')
    print()
    return r.status_code == 200

def test_scan_html():
    """Test /scan with HTML input."""
    r = requests.post(f'{BASE_URL}/scan', json={'html': '<html><body>Test</body></html>'})
    print(f'=== Scan HTML ===')
    print(f'Status: {r.status_code}')
    result = r.json()
    print(f'Risk: {result.get("risk")}')
    print(f'Confidence: {result.get("confidence")}')
    print()
    return r.status_code == 200

def test_feedback():
    """Test /feedback endpoint."""
    r = requests.post(f'{BASE_URL}/feedback', json={
        'scan_id': 'test-123',
        'user_flag': True,
        'corrected_label': 'HIGH',
        'comment': 'This is clearly a phishing site'
    })
    print(f'=== Feedback ===')
    print(f'Status: {r.status_code}')
    print(f'Response: {r.json()}')
    print()
    return r.status_code == 200

def test_metrics():
    """Test /metrics endpoint."""
    r = requests.get(f'{BASE_URL}/metrics')
    print(f'=== Metrics ===')
    print(f'Status: {r.status_code}')
    print(f'Has content: {len(r.text) > 0}')
    print()
    return r.status_code == 200

def test_phishing_url():
    """Test with a known phishing URL pattern."""
    r = requests.post(f'{BASE_URL}/scan', json={
        'url': 'https://secure-bank.com-verify-login.com/login'
    })
    print(f'=== Phishing URL Pattern ===')
    print(f'Status: {r.status_code}')
    result = r.json()
    print(f'Risk: {result.get("risk")}')
    print(f'Confidence: {result.get("confidence")}')
    print()
    return r.status_code == 200

def main():
    """Run all tests."""
    print('\n' + '='*50)
    print('THREAT INTELLIGENCE PLATFORM - API TESTS')
    print('='*50 + '\n')

    tests = [
        ('Health', test_health),
        ('Scan URL', test_scan_url),
        ('Scan Text', test_scan_text),
        ('Scan HTML', test_scan_html),
        ('Feedback', test_feedback),
        ('Metrics', test_metrics),
        ('Phishing Pattern', test_phishing_url),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f'✓ {name} PASSED')
            else:
                failed += 1
                print(f'✗ {name} FAILED')
        except Exception as e:
            failed += 1
            print(f'✗ {name} ERROR: {e}')

    print('\n' + '='*50)
    print(f'RESULTS: {passed} passed, {failed} failed')
    print('='*50)

if __name__ == '__main__':
    main()
