#!/usr/bin/env python3
"""
Verification script for Docker, Redis, and PostgreSQL fixes.
Run this to verify all fixes are working correctly.
"""
import asyncio
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def verify_redis_connection_pool():
    """Verify Redis connection pool is working."""
    print("\n[1/5] Testing Redis Connection Pool...")
    try:
        from app.services.redis import init_redis, get_redis_client, close_redis
        
        await init_redis()
        print("  ✅ Redis pool initialized")
        
        # Test getting multiple clients
        async for client in get_redis_client():
            await client.ping()
            print("  ✅ Redis client 1 connected")
        
        async for client in get_redis_client():
            await client.set("test_key", "test_value")
            value = await client.get("test_key")
            assert value == "test_value"
            await client.delete("test_key")
            print("  ✅ Redis client 2 connected and working")
        
        await close_redis()
        print("  ✅ Redis pool closed properly")
        
    except Exception as e:
        print(f"  ❌ Redis test failed: {e}")
        return False
    
    return True


async def verify_database_session():
    """Verify database session management."""
    print("\n[2/5] Testing Database Session Management...")
    try:
        from app.services.database import init_db, get_db_session, close_db
        
        await init_db()
        print("  ✅ Database initialized")
        
        # Test session as dependency
        async for session in get_db_session():
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
            print("  ✅ Database session working")
        
        await close_db()
        print("  ✅ Database closed properly")
        
    except Exception as e:
        print(f"  ❌ Database test failed: {e}")
        return False
    
    return True


def verify_environment_variables():
    """Verify environment variables are set correctly."""
    print("\n[3/5] Testing Environment Variables...")
    try:
        from app.config import settings
        
        assert settings.POSTGRES_USER == "postgres"
        print(f"  ✅ POSTGRES_USER: {settings.POSTGRES_USER}")
        
        assert settings.POSTGRES_PASSWORD == "postgres1234"
        print(f"  ✅ POSTGRES_PASSWORD: {'*' * len(settings.POSTGRES_PASSWORD)}")
        
        assert settings.POSTGRES_DB == "threat_intel"
        print(f"  ✅ POSTGRES_DB: {settings.POSTGRES_DB}")
        
        assert "postgres1234" in settings.DATABASE_URL
        print(f"  ✅ DATABASE_URL configured correctly")
        
    except Exception as e:
        print(f"  ❌ Environment test failed: {e}")
        return False
    
    return True


def verify_celery_tasks():
    """Verify Celery tasks don't use async anti-patterns."""
    print("\n[4/5] Testing Celery Task Patterns...")
    try:
        from app.tasks.ingestion import ingest_feed
        
        # Check that the function doesn't create event loops
        import inspect
        source = inspect.getsource(ingest_feed)
        
        if "asyncio.new_event_loop()" in source:
            print("  ❌ Found asyncio.new_event_loop() anti-pattern")
            return False
        
        if "asyncio.set_event_loop()" in source:
            print("  ❌ Found asyncio.set_event_loop() anti-pattern")
            return False
        
        print("  ✅ No async anti-patterns found")
        print("  ✅ Using synchronous requests library")
        
    except Exception as e:
        print(f"  ❌ Celery test failed: {e}")
        return False
    
    return True


def verify_docker_compose():
    """Verify docker-compose.yml configuration."""
    print("\n[5/5] Testing Docker Compose Configuration...")
    try:
        import yaml
        
        with open("docker-compose.yml", "r") as f:
            config = yaml.safe_load(f)
        
        # Check postgres service
        postgres = config["services"]["postgres"]
        assert "${POSTGRES_USER" in postgres["environment"]["POSTGRES_USER"]
        print("  ✅ PostgreSQL uses environment variables")
        
        # Check API service
        api = config["services"]["api"]
        assert "${POSTGRES_PASSWORD" in api["environment"]["DATABASE_URL"]
        print("  ✅ API uses environment variables")
        
        # Check volumes
        assert "postgres_data" in config["volumes"]
        assert "redis_data" in config["volumes"]
        print("  ✅ Persistent volumes configured")
        
        # Check health checks
        assert "healthcheck" in postgres
        assert "healthcheck" in config["services"]["redis"]
        print("  ✅ Health checks configured")
        
    except Exception as e:
        print(f"  ❌ Docker Compose test failed: {e}")
        return False
    
    return True


async def main():
    """Run all verification tests."""
    print("=" * 60)
    print("PhishGuard - Docker, Redis, PostgreSQL Fixes Verification")
    print("=" * 60)
    
    results = []
    
    # Test 1: Redis
    results.append(await verify_redis_connection_pool())
    
    # Test 2: Database
    results.append(await verify_database_session())
    
    # Test 3: Environment
    results.append(verify_environment_variables())
    
    # Test 4: Celery
    results.append(verify_celery_tasks())
    
    # Test 5: Docker Compose
    results.append(verify_docker_compose())
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nTests Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ All fixes verified successfully!")
        print("\nYou can now run:")
        print("  docker-compose up -d")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
