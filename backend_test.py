#!/usr/bin/env python3
"""
Backend API Testing for NutriVane - AI Smart Scan Feature
Tests POST /api/scan/ai endpoint with various scenarios
"""
import requests
import json
import time
from pathlib import Path

# Configuration
BASE_URL = "https://nutri-mood-ai.preview.emergentagent.com/api"
TIMEOUT = 120  # 120 seconds for AI calls (Gemini + Tavily)

# Load dev token
DEV_TOKEN_PATH = Path("/app/memory/dev_token.txt")
DEV_TOKEN = DEV_TOKEN_PATH.read_text().strip() if DEV_TOKEN_PATH.exists() else ""

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {test_name}")
    if details:
        print(f"  Details: {details}")
    print()

def test_health():
    """Test GET /api/health"""
    print_section("TEST 0: Health Check")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=10)
        passed = resp.status_code == 200 and resp.json().get("ok") == True
        print_result("Health endpoint", passed, f"Status: {resp.status_code}, Response: {resp.json()}")
        return passed
    except Exception as e:
        print_result("Health endpoint", False, f"Error: {e}")
        return False

def test_text_path_guest():
    """Test 1: Text path (guest, no auth) - POST /api/scan/ai {"dish_name":"Nasi goreng"}"""
    print_section("TEST 1: Text Path (Guest, No Auth) - Nasi goreng")
    try:
        payload = {"dish_name": "Nasi goreng"}
        print(f"Request: POST {BASE_URL}/scan/ai")
        print(f"Payload: {json.dumps(payload)}")
        print(f"Timeout: {TIMEOUT}s (AI call takes ~10-15s)")
        print("Waiting for response...\n")
        
        start = time.time()
        resp = requests.post(f"{BASE_URL}/scan/ai", json=payload, timeout=TIMEOUT)
        elapsed = time.time() - start
        
        print(f"Response time: {elapsed:.1f}s")
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code != 200:
            print_result("Text path guest", False, f"Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
        
        data = resp.json()
        print(f"Response keys: {list(data.keys())}")
        print(f"Mode: {data.get('mode')}")
        print(f"Dish: {data.get('dish')}")
        print(f"Source count: {data.get('source_count')}")
        print(f"Saved to account: {data.get('saved_to_account')}")
        print(f"Spices count: {len(data.get('spices', []))}")
        
        # Validation
        checks = []
        checks.append(("mode is 'web'", data.get("mode") == "web"))
        checks.append(("spices non-empty", len(data.get("spices", [])) > 0))
        checks.append(("insight non-empty", bool(data.get("insight", "").strip())))
        checks.append(("sources non-empty", len(data.get("sources", [])) > 0))
        checks.append(("source_count >= 1", data.get("source_count", 0) >= 1))
        checks.append(("saved_to_account is false", data.get("saved_to_account") == False))
        
        # Check spices structure
        if data.get("spices"):
            spice = data["spices"][0]
            checks.append(("spice has name", "name" in spice))
            checks.append(("spice has avg > 0", spice.get("avg", 0) > 0))
            checks.append(("spice has unit", "unit" in spice))
            checks.append(("spice has pct", "pct" in spice))
            print(f"\nFirst spice: {spice}")
        
        # Check sources structure
        if data.get("sources"):
            source = data["sources"][0]
            checks.append(("source has url", "url" in source))
            checks.append(("source url is http(s)", source.get("url", "").startswith("http")))
            checks.append(("source has name", "name" in source))
            checks.append(("source has title", "title" in source))
            print(f"\nFirst source: {source}")
        
        print("\nValidation checks:")
        for check_name, check_result in checks:
            print(f"  {'✓' if check_result else '✗'} {check_name}")
        
        passed = all(result for _, result in checks)
        print_result("Text path guest (Nasi goreng)", passed)
        return passed
        
    except Exception as e:
        print_result("Text path guest", False, f"Error: {e}")
        return False

def test_graceful_fallback():
    """Test 2: Graceful fallback - POST /api/scan/ai {"dish_name":"asdqwezxc123notafood"}"""
    print_section("TEST 2: Graceful Fallback - Invalid dish name")
    try:
        payload = {"dish_name": "asdqwezxc123notafood"}
        print(f"Request: POST {BASE_URL}/scan/ai")
        print(f"Payload: {json.dumps(payload)}")
        print("Waiting for response...\n")
        
        start = time.time()
        resp = requests.post(f"{BASE_URL}/scan/ai", json=payload, timeout=TIMEOUT)
        elapsed = time.time() - start
        
        print(f"Response time: {elapsed:.1f}s")
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code == 500:
            print_result("Graceful fallback", False, "CRITICAL: Got 500 error, should return 200 with fallback")
            print(f"Response: {resp.text}")
            return False
        
        if resp.status_code != 200:
            print_result("Graceful fallback", False, f"Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
        
        data = resp.json()
        print(f"Response keys: {list(data.keys())}")
        print(f"Mode: {data.get('mode')}")
        print(f"Dish: {data.get('dish')}")
        print(f"Fallback reason: {data.get('fallback_reason')}")
        print(f"Benchmark slug: {data.get('benchmark_slug')}")
        print(f"Spices count: {len(data.get('spices', []))}")
        
        # Validation
        checks = []
        checks.append(("status is 200 (not 500)", resp.status_code == 200))
        checks.append(("mode is 'fallback'", data.get("mode") == "fallback"))
        checks.append(("spices non-empty (from benchmark)", len(data.get("spices", [])) > 0))
        checks.append(("fallback_reason is set", bool(data.get("fallback_reason", "").strip())))
        checks.append(("benchmark_slug present", bool(data.get("benchmark_slug"))))
        
        print("\nValidation checks:")
        for check_name, check_result in checks:
            print(f"  {'✓' if check_result else '✗'} {check_name}")
        
        passed = all(result for _, result in checks)
        print_result("Graceful fallback", passed)
        return passed
        
    except Exception as e:
        print_result("Graceful fallback", False, f"Error: {e}")
        return False

def test_authenticated_path():
    """Test 3: Authenticated path - verify saved_to_account=true and stats increment"""
    print_section("TEST 3: Authenticated Path - Stats Increment")
    
    if not DEV_TOKEN:
        print_result("Authenticated path", False, "Dev token not found at /app/memory/dev_token.txt")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {DEV_TOKEN}"}
        payload = {"dish_name": "Soto ayam"}
        
        print(f"Request: POST {BASE_URL}/scan/ai (with auth)")
        print(f"Payload: {json.dumps(payload)}")
        print("First scan...\n")
        
        # First scan
        start = time.time()
        resp1 = requests.post(f"{BASE_URL}/scan/ai", json=payload, headers=headers, timeout=TIMEOUT)
        elapsed1 = time.time() - start
        
        print(f"Response time: {elapsed1:.1f}s")
        print(f"Status code: {resp1.status_code}")
        
        if resp1.status_code != 200:
            print_result("Authenticated path (scan 1)", False, f"Expected 200, got {resp1.status_code}")
            print(f"Response: {resp1.text}")
            return False
        
        data1 = resp1.json()
        print(f"Mode: {data1.get('mode')}")
        print(f"Saved to account: {data1.get('saved_to_account')}")
        print(f"Stats: {data1.get('stats')}")
        
        plates1 = data1.get("stats", {}).get("plates_recognized", 0)
        print(f"Plates recognized (scan 1): {plates1}")
        
        # Second scan
        print("\nSecond scan...\n")
        time.sleep(2)  # Small delay between scans
        
        start = time.time()
        resp2 = requests.post(f"{BASE_URL}/scan/ai", json=payload, headers=headers, timeout=TIMEOUT)
        elapsed2 = time.time() - start
        
        print(f"Response time: {elapsed2:.1f}s")
        print(f"Status code: {resp2.status_code}")
        
        if resp2.status_code != 200:
            print_result("Authenticated path (scan 2)", False, f"Expected 200, got {resp2.status_code}")
            print(f"Response: {resp2.text}")
            return False
        
        data2 = resp2.json()
        print(f"Mode: {data2.get('mode')}")
        print(f"Saved to account: {data2.get('saved_to_account')}")
        print(f"Stats: {data2.get('stats')}")
        
        plates2 = data2.get("stats", {}).get("plates_recognized", 0)
        print(f"Plates recognized (scan 2): {plates2}")
        
        # Validation
        checks = []
        checks.append(("scan 1: saved_to_account is true", data1.get("saved_to_account") == True))
        checks.append(("scan 1: stats present", "stats" in data1))
        checks.append(("scan 1: plates_recognized present", "plates_recognized" in data1.get("stats", {})))
        checks.append(("scan 2: saved_to_account is true", data2.get("saved_to_account") == True))
        checks.append(("scan 2: stats present", "stats" in data2))
        checks.append(("scan 2: plates_recognized present", "plates_recognized" in data2.get("stats", {})))
        checks.append(("plates_recognized INCREMENTED", plates2 > plates1))
        
        print("\nValidation checks:")
        for check_name, check_result in checks:
            print(f"  {'✓' if check_result else '✗'} {check_name}")
        
        print(f"\nPlates increment: {plates1} → {plates2} (delta: {plates2 - plates1})")
        
        passed = all(result for _, result in checks)
        print_result("Authenticated path", passed)
        return passed
        
    except Exception as e:
        print_result("Authenticated path", False, f"Error: {e}")
        return False

def test_empty_request():
    """Test 4: Empty request - POST /api/scan/ai {} → should 200 fallback, not 500"""
    print_section("TEST 4: Empty Request - No dish, no image")
    try:
        payload = {}
        print(f"Request: POST {BASE_URL}/scan/ai")
        print(f"Payload: {json.dumps(payload)}")
        print("Waiting for response...\n")
        
        start = time.time()
        resp = requests.post(f"{BASE_URL}/scan/ai", json=payload, timeout=TIMEOUT)
        elapsed = time.time() - start
        
        print(f"Response time: {elapsed:.1f}s")
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code == 500:
            print_result("Empty request", False, "CRITICAL: Got 500 error, should return 200 with fallback")
            print(f"Response: {resp.text}")
            return False
        
        if resp.status_code != 200:
            print_result("Empty request", False, f"Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
        
        data = resp.json()
        print(f"Response keys: {list(data.keys())}")
        print(f"Mode: {data.get('mode')}")
        
        # Validation
        checks = []
        checks.append(("status is 200 (not 500)", resp.status_code == 200))
        checks.append(("mode is 'fallback'", data.get("mode") == "fallback"))
        
        print("\nValidation checks:")
        for check_name, check_result in checks:
            print(f"  {'✓' if check_result else '✗'} {check_name}")
        
        passed = all(result for _, result in checks)
        print_result("Empty request", passed)
        return passed
        
    except Exception as e:
        print_result("Empty request", False, f"Error: {e}")
        return False

def test_old_scan_endpoint():
    """Test 5: Regression - confirm old POST /api/scan still works"""
    print_section("TEST 5: Regression - Old /api/scan endpoint")
    try:
        payload = {"benchmark_slug": "rendang", "measure": True}
        print(f"Request: POST {BASE_URL}/scan")
        print(f"Payload: {json.dumps(payload)}")
        print("Waiting for response...\n")
        
        resp = requests.post(f"{BASE_URL}/scan", json=payload, timeout=30)
        
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code != 200:
            print_result("Old scan endpoint", False, f"Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
        
        data = resp.json()
        print(f"Response keys: {list(data.keys())}")
        print(f"Benchmark slug: {data.get('benchmark_slug')}")
        print(f"Menu name: {data.get('menu_name')}")
        print(f"Spices count: {len(data.get('spices', []))}")
        
        # Validation
        checks = []
        checks.append(("status is 200", resp.status_code == 200))
        checks.append(("benchmark_slug present", data.get("benchmark_slug") == "rendang"))
        checks.append(("spices non-empty", len(data.get("spices", [])) > 0))
        
        print("\nValidation checks:")
        for check_name, check_result in checks:
            print(f"  {'✓' if check_result else '✗'} {check_name}")
        
        passed = all(result for _, result in checks)
        print_result("Old scan endpoint", passed)
        return passed
        
    except Exception as e:
        print_result("Old scan endpoint", False, f"Error: {e}")
        return False

def main():
    print("\n" + "="*80)
    print("  NutriVane Backend Testing - AI Smart Scan Feature")
    print("  Backend URL: " + BASE_URL)
    print("="*80)
    
    results = {}
    
    # Run all tests
    results["health"] = test_health()
    results["text_path_guest"] = test_text_path_guest()
    results["graceful_fallback"] = test_graceful_fallback()
    results["authenticated_path"] = test_authenticated_path()
    results["empty_request"] = test_empty_request()
    results["old_scan_endpoint"] = test_old_scan_endpoint()
    
    # Summary
    print_section("TEST SUMMARY")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    print(f"Total tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print()
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    print("\n" + "="*80)
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {failed} test(s) failed. Check details above.")
    
    print("="*80 + "\n")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
