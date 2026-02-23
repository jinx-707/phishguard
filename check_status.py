"""
System Status Checker - Verify all ports and services
"""
import socket
import subprocess
import sys
import time

def check_port(host, port, service_name):
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"[OK] {service_name:20} - Port {port} is OPEN")
            return True
        else:
            print(f"[FAIL] {service_name:20} - Port {port} is CLOSED")
            return False
    except Exception as e:
        print(f"[FAIL] {service_name:20} - Error: {e}")
        return False

def check_docker():
    """Check if Docker is running"""
    try:
        result = subprocess.run(['docker', 'ps'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        if result.returncode == 0:
            print("[OK] Docker                - RUNNING")
            
            # Parse running containers
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                print(f"   Running containers: {len(lines) - 1}")
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 2:
                        print(f"   - {parts[1]}")
            return True
        else:
            print("[FAIL] Docker                - NOT RUNNING")
            return False
    except Exception as e:
        print(f"[FAIL] Docker                - Error: {e}")
        return False

def check_python():
    """Check Python version"""
    try:
        version = sys.version.split()[0]
        print(f"[OK] Python                - Version {version}")
        return True
    except Exception as e:
        print(f"[FAIL] Python                - Error: {e}")
        return False

def main():
    print("=" * 70)
    print("PhishGuard System Status Check")
    print("=" * 70)
    print()
    
    results = {}
    
    # Check Python
    print("[1/7] Checking Python...")
    results['Python'] = check_python()
    print()
    
    # Check Docker
    print("[2/7] Checking Docker...")
    results['Docker'] = check_docker()
    print()
    
    # Check PostgreSQL
    print("[3/7] Checking PostgreSQL...")
    results['PostgreSQL'] = check_port('localhost', 5432, 'PostgreSQL')
    print()
    
    # Check Redis
    print("[4/7] Checking Redis...")
    results['Redis'] = check_port('localhost', 6379, 'Redis')
    print()
    
    # Check FastAPI
    print("[5/7] Checking FastAPI...")
    results['FastAPI'] = check_port('localhost', 8000, 'FastAPI')
    print()
    
    # Check if Chrome extension can connect
    print("[6/7] Checking Chrome Extension endpoint...")
    try:
        import urllib.request
        import urllib.error
        
        try:
            response = urllib.request.urlopen('http://localhost:8000/health', timeout=3)
            if response.status == 200:
                print("[OK] API Health Endpoint   - ACCESSIBLE")
                results['API Health'] = True
            else:
                print(f"[WARN] API Health Endpoint   - Status {response.status}")
                results['API Health'] = False
        except urllib.error.URLError:
            print("[FAIL] API Health Endpoint   - NOT ACCESSIBLE")
            results['API Health'] = False
    except Exception as e:
        print(f"[FAIL] API Health Endpoint   - Error: {e}")
        results['API Health'] = False
    print()
    
    # Check Dashboard port
    print("[7/7] Checking Dashboard port...")
    results['Dashboard'] = check_port('localhost', 5173, 'Dashboard (Vite)')
    print()
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    
    passed = sum(results.values())
    total = len(results)
    
    for service, status in results.items():
        status_icon = "[OK]" if status else "[FAIL]"
        print(f"{status_icon} {service}")
    
    print()
    print(f"Status: {passed}/{total} services operational")
    print()
    
    # Recommendations
    if not results.get('Docker'):
        print("[ACTION] Start Docker Desktop first")
    
    if not results.get('PostgreSQL') or not results.get('Redis'):
        print("[ACTION] Run: docker-compose up -d db redis")
    
    if not results.get('FastAPI'):
        print("[ACTION] Run: python -m uvicorn app.main:app --reload")
    
    if not results.get('Dashboard'):
        print("[INFO] Dashboard is optional. Run: cd dashboard && npm run dev")
    
    print()
    
    if passed >= 5:  # At least core services
        print("SUCCESS: Core services are ready!")
        print()
        print("Next steps:")
        print("1. Load Chrome extension from: aws/Chrome_extensions/")
        print("2. Visit any website to test phishing detection")
        print("3. Check extension popup for results")
        return 0
    else:
        print("WARNING: Some services need to be started")
        return 1

if __name__ == "__main__":
    sys.exit(main())
