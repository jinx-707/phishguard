"""
Integration Test - Verify all services are connected and working
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_integration():
    print("=" * 60)
    print("PhishGuard Integration Test")
    print("=" * 60)
    print()
    
    results = {
        "PostgreSQL": False,
        "Redis": False,
        "FastAPI": False,
        "Graph Service": False,
        "ML Predictor": False
    }
    
    # Test 1: PostgreSQL Connection
    print("[1/5] Testing PostgreSQL connection...")
    try:
        from app.services.database import init_db, close_db
        await init_db()
        print("✅ PostgreSQL: Connected")
        results["PostgreSQL"] = True
        await close_db()
    except Exception as e:
        print(f"❌ PostgreSQL: Failed - {e}")
    
    # Test 2: Redis Connection
    print("\n[2/5] Testing Redis connection...")
    try:
        from app.services.redis import init_redis, close_redis, get_redis_client
        await init_redis()
        redis = await get_redis_client()
        await redis.ping()
        print("✅ Redis: Connected")
        results["Redis"] = True
        await close_redis()
    except Exception as e:
        print(f"❌ Redis: Failed - {e}")
    
    # Test 3: FastAPI App
    print("\n[3/5] Testing FastAPI app...")
    try:
        from app.main import app
        print(f"✅ FastAPI: Loaded (routes: {len(app.routes)})")
        results["FastAPI"] = True
    except Exception as e:
        print(f"❌ FastAPI: Failed - {e}")
    
    # Test 4: Graph Service
    print("\n[4/5] Testing Graph service...")
    try:
        from app.services.graph import GraphService
        graph = GraphService()
        await graph._ensure_graph_loaded()
        print(f"✅ Graph Service: Ready (nodes: {graph.graph.number_of_nodes()})")
        results["Graph Service"] = True
    except Exception as e:
        print(f"❌ Graph Service: Failed - {e}")
    
    # Test 5: ML Predictor
    print("\n[5/5] Testing ML predictor...")
    try:
        from intelligence.nlp.predictor import PhishingPredictor
        predictor = PhishingPredictor()
        test_result = predictor.predict("Verify your account immediately")
        print(f"✅ ML Predictor: Ready (method: {test_result.get('method')})")
        results["ML Predictor"] = True
    except Exception as e:
        print(f"❌ ML Predictor: Failed - {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Integration Test Summary")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for service, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {service}")
    
    print()
    print(f"Result: {passed}/{total} services operational")
    
    if passed == total:
        print("\n🎉 All services integrated successfully!")
        return 0
    else:
        print("\n⚠️  Some services need attention")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(test_integration())
    sys.exit(exit_code)
