import socket
import requests
import psycopg2
import redis

def check_port(host, port, service_name):
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            print(f"[OK] {service_name} - Port {port} is OPEN")
            return True
        else:
            print(f"[FAIL] {service_name} - Port {port} is CLOSED")
            return False
    except Exception as e:
        print(f"[ERROR] {service_name} - {e}")
        return False

def test_postgres():
    """Test PostgreSQL connection"""
    passwords = ["postgres", "phishguard123", "password"]
    for pwd in passwords:
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="threat_intel",
                user="postgres",
                password=pwd
            )
            conn.close()
            print(f"[OK] PostgreSQL - Connection successful (password: {pwd})")
            return True
        except:
            continue
    print("[FAIL] PostgreSQL - Authentication failed (tried multiple passwords)")
    return False

def test_redis():
    """Test Redis connection"""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("[OK] Redis - Connection successful")
        return True
    except Exception as e:
        print(f"[FAIL] Redis - {e}")
        return False

def test_fastapi():
    """Test FastAPI connection"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=3)
        if response.status_code == 200:
            print("[OK] FastAPI - Server responding")
            return True
        else:
            print(f"[FAIL] FastAPI - Status code {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[FAIL] FastAPI - Server not running (Port 8000 not responding)")
        return False
    except Exception as e:
        print(f"[FAIL] FastAPI - {e}")
        return False

print("=" * 60)
print("PhishGuard Port Verification")
print("=" * 60)

print("\n1. PORT AVAILABILITY CHECK:")
print("-" * 60)
postgres_port = check_port("localhost", 5432, "PostgreSQL")
redis_port = check_port("localhost", 6379, "Redis")
fastapi_port = check_port("localhost", 8000, "FastAPI")

print("\n2. SERVICE CONNECTION CHECK:")
print("-" * 60)
postgres_conn = test_postgres()
redis_conn = test_redis()
fastapi_conn = test_fastapi()

print("\n3. SUMMARY:")
print("=" * 60)
total = 6
passed = sum([postgres_port, redis_port, fastapi_port, postgres_conn, redis_conn, fastapi_conn])

print(f"Tests Passed: {passed}/{total}")
print()

if not fastapi_port or not fastapi_conn:
    print("[!] MISSING: FastAPI Server (Port 8000)")
    print("   Start with: python -m uvicorn app.main:app --reload")
    print()

if postgres_port and redis_port and postgres_conn and redis_conn:
    print("[OK] Database Infrastructure: READY")
else:
    print("[FAIL] Database Infrastructure: ISSUES DETECTED")

if fastapi_port and fastapi_conn:
    print("[OK] API Server: READY")
else:
    print("[FAIL] API Server: NOT RUNNING")

print()
print("Next Steps:")
if not fastapi_conn:
    print("1. Start FastAPI: python -m uvicorn app.main:app --reload")
    print("2. Load Chrome Extension: chrome://extensions/")
    print("3. Test system: Visit any website")
else:
    print("1. Load Chrome Extension: chrome://extensions/")
    print("2. Test system: Visit any website")
    print("3. Check extension popup for results")
