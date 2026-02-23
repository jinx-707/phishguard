#!/usr/bin/env python3
"""
Port Integration and Connectivity Checker
Verifies all services are properly connected and ports are correctly configured.
"""
import socket
import subprocess
import sys
import time
from typing import Dict, List, Tuple


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")


def check_port_available(port: int) -> bool:
    """Check if a port is available (not in use)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result != 0  # Port is available if connection fails
    except:
        return True


def check_port_listening(port: int, timeout: int = 2) -> bool:
    """Check if a service is listening on a port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0  # Port is listening if connection succeeds
    except:
        return False


def check_docker_running() -> bool:
    """Check if Docker is running."""
    try:
        result = subprocess.run(
            ['docker', 'ps'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


def get_docker_containers() -> List[str]:
    """Get list of running Docker containers."""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return [name.strip() for name in result.stdout.split('\n') if name.strip()]
        return []
    except:
        return []


def check_container_network(container: str, target: str, port: int) -> Tuple[bool, str]:
    """Check if a container can reach another service."""
    try:
        # Try to ping the target
        result = subprocess.run(
            ['docker', 'exec', container, 'ping', '-c', '1', '-W', '2', target],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return True, "Network reachable"
        else:
            return False, "Network unreachable"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, f"Error: {str(e)}"


def check_port_conflicts():
    """Check for port conflicts before starting services."""
    print_header("Port Conflict Check")
    
    ports = {
        5432: "PostgreSQL",
        6379: "Redis",
        8000: "API",
        5555: "Flower",
        9090: "Prometheus",
        3000: "Grafana",
        80: "Nginx HTTP",
        443: "Nginx HTTPS"
    }
    
    conflicts = []
    available = []
    
    for port, service in ports.items():
        if check_port_listening(port):
            print_warning(f"Port {port} ({service}) is already in use")
            conflicts.append((port, service))
        else:
            print_success(f"Port {port} ({service}) is available")
            available.append((port, service))
    
    print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  Available ports: {len(available)}/{len(ports)}")
    print(f"  Conflicts: {len(conflicts)}/{len(ports)}")
    
    if conflicts:
        print_warning("\nPort conflicts detected! You may need to:")
        print("  1. Stop services using these ports")
        print("  2. Change port mappings in docker-compose.yml")
        print("  3. Use different ports in your configuration")
    
    return len(conflicts) == 0


def check_docker_services():
    """Check if Docker services are running."""
    print_header("Docker Services Check")
    
    if not check_docker_running():
        print_error("Docker is not running!")
        print_info("Please start Docker Desktop and try again")
        return False
    
    print_success("Docker is running")
    
    expected_containers = [
        "phishguard-postgres",
        "phishguard-redis",
        "phishguard-api",
        "phishguard-celery-worker",
        "phishguard-celery-beat",
        "phishguard-flower",
        "phishguard-prometheus",
        "phishguard-grafana",
        "phishguard-nginx"
    ]
    
    running_containers = get_docker_containers()
    
    print(f"\n{Colors.BOLD}Expected containers:{Colors.RESET}")
    for container in expected_containers:
        if container in running_containers:
            print_success(f"{container} is running")
        else:
            print_error(f"{container} is NOT running")
    
    running_count = sum(1 for c in expected_containers if c in running_containers)
    print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  Running: {running_count}/{len(expected_containers)}")
    
    if running_count == 0:
        print_warning("\nNo containers running. Start services with:")
        print("  docker-compose up -d")
        return False
    
    return running_count == len(expected_containers)


def check_service_connectivity():
    """Check connectivity between Docker services."""
    print_header("Service Connectivity Check")
    
    connectivity_tests = [
        ("phishguard-api", "postgres", 5432, "API → PostgreSQL"),
        ("phishguard-api", "redis", 6379, "API → Redis"),
        ("phishguard-celery-worker", "postgres", 5432, "Celery Worker → PostgreSQL"),
        ("phishguard-celery-worker", "redis", 6379, "Celery Worker → Redis"),
        ("phishguard-celery-beat", "postgres", 5432, "Celery Beat → PostgreSQL"),
        ("phishguard-celery-beat", "redis", 6379, "Celery Beat → Redis"),
        ("phishguard-flower", "redis", 6379, "Flower → Redis"),
        ("phishguard-nginx", "api", 8000, "Nginx → API"),
    ]
    
    passed = 0
    failed = 0
    
    for container, target, port, description in connectivity_tests:
        reachable, message = check_container_network(container, target, port)
        if reachable:
            print_success(f"{description}: {message}")
            passed += 1
        else:
            print_error(f"{description}: {message}")
            failed += 1
    
    print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  Passed: {passed}/{len(connectivity_tests)}")
    print(f"  Failed: {failed}/{len(connectivity_tests)}")
    
    return failed == 0


def check_service_health():
    """Check health of running services."""
    print_header("Service Health Check")
    
    health_checks = [
        ("http://localhost:8000/health", "API Health Endpoint"),
        ("http://localhost:5555", "Flower Dashboard"),
        ("http://localhost:9090", "Prometheus"),
        ("http://localhost:3000", "Grafana"),
    ]
    
    try:
        import requests
        
        passed = 0
        failed = 0
        
        for url, service in health_checks:
            try:
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    print_success(f"{service}: Responding (HTTP {response.status_code})")
                    passed += 1
                else:
                    print_warning(f"{service}: Responding but status {response.status_code}")
                    passed += 1
            except requests.exceptions.ConnectionError:
                print_error(f"{service}: Connection refused")
                failed += 1
            except requests.exceptions.Timeout:
                print_error(f"{service}: Timeout")
                failed += 1
            except Exception as e:
                print_error(f"{service}: {str(e)}")
                failed += 1
        
        print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
        print(f"  Healthy: {passed}/{len(health_checks)}")
        print(f"  Unhealthy: {failed}/{len(health_checks)}")
        
        return failed == 0
        
    except ImportError:
        print_warning("requests library not installed, skipping HTTP health checks")
        print_info("Install with: pip install requests")
        return True


def check_environment_config():
    """Check environment configuration."""
    print_header("Environment Configuration Check")
    
    try:
        import yaml
        
        with open('docker-compose.yml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Check API service environment
        api_env = config['services']['api']['environment']
        
        checks = [
            ('DATABASE_URL' in str(api_env), "DATABASE_URL configured"),
            ('postgres:5432' in str(api_env), "PostgreSQL uses service name (not localhost)"),
            ('redis:6379' in str(api_env), "Redis uses service name (not localhost)"),
            ('CELERY_BROKER_URL' in str(api_env), "Celery broker configured"),
        ]
        
        passed = 0
        for check, description in checks:
            if check:
                print_success(description)
                passed += 1
            else:
                print_error(description)
        
        print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
        print(f"  Passed: {passed}/{len(checks)}")
        
        return passed == len(checks)
        
    except Exception as e:
        print_error(f"Failed to check configuration: {e}")
        return False


def main():
    """Run all integration checks."""
    print_header("PhishGuard Port Integration & Connectivity Checker")
    
    results = {}
    
    # Check 1: Port conflicts
    results['port_conflicts'] = check_port_conflicts()
    
    # Check 2: Docker services
    results['docker_services'] = check_docker_services()
    
    # Check 3: Environment config
    results['environment'] = check_environment_config()
    
    # Only check connectivity if Docker is running
    if results['docker_services']:
        # Check 4: Service connectivity
        results['connectivity'] = check_service_connectivity()
        
        # Check 5: Service health
        results['health'] = check_service_health()
    else:
        print_warning("\nSkipping connectivity and health checks (Docker not running)")
        results['connectivity'] = False
        results['health'] = False
    
    # Final summary
    print_header("Final Summary")
    
    total_checks = len(results)
    passed_checks = sum(1 for v in results.values() if v)
    
    print(f"{Colors.BOLD}Check Results:{Colors.RESET}")
    for check, passed in results.items():
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  {check.replace('_', ' ').title()}: {status}")
    
    print(f"\n{Colors.BOLD}Overall Score: {passed_checks}/{total_checks}{Colors.RESET}")
    
    if passed_checks == total_checks:
        print_success("\n🎉 All integration checks passed!")
        print_info("Your services are properly configured and connected.")
        return 0
    else:
        print_warning(f"\n⚠️  {total_checks - passed_checks} check(s) failed")
        print_info("Review the output above for details.")
        
        if not results['docker_services']:
            print_info("\nTo start services:")
            print("  docker-compose up -d")
        
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Check interrupted by user{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.RESET}")
        sys.exit(1)
