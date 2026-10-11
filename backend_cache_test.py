#!/usr/bin/env python3
"""
Backend API Testing for NutriVane - CACHE Testing for POST /api/scan/ai
Tests cache functionality: miss, hit, normalization, fallback, regression
"""
import requests
import json
import time

# Configuration
BASE_URL = "https://nutrivane-rempah.preview.emergentagent.com/api"
TIMEOUT = 120  # 120 seconds for AI calls (Gemini + Tavily)

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

def test_scenario_1_cache_miss():
    """
    Scenario 1: CACHE MISS
    POST /api/scan/ai {"dish_name":"Rawon daging"}
    Expect: HTTP 200, mode="web", cached=false, spices[] non-empty, 
            insight non-empty, sources[] non-empty with real http(s) urls, 
            source_count>=1, response time several seconds
    """
    print_section("SCENARIO 1: CACHE MISS - Rawon daging (first call)")
    try:
        payload = {"dish_name": "Rawon daging"}
        print(f"Request: POST {BASE_URL}/scan/ai")
        print(f"Payload: {json.dumps(payload)}")
        print(f"Timeout: {TIMEOUT}s")
        print("Waiting for response (expecting ~10-25s for AI calls)...\n")
        
        start = time.time()
        resp = requests.post(f"{BASE_URL}/scan/ai", json=payload, timeout=TIMEOUT)
        elapsed = time.time() - start
        
        print(f"Response time: {elapsed:.2f}s")
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code != 200:
            print_result("Scenario 1: Cache MISS", False, f"Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            return False, None, None
        
        data = resp.json()
        print(f"\nResponse structure:")
        print(f"  mode: {data.get('mode')}")
        print(f"  cached: {data.get('cached')}")
        print(f"  dish: {data.get('dish')}")
        print(f"  spices count: {len(data.get('spices', []))}")
        print(f"  source_count: {data.get('source_count')}")
        print(f"  insight length: {len(data.get('insight', ''))}")
        
        # Validation checks
        checks = []
        checks.append(("HTTP 200", resp.status_code == 200))
        checks.append(("mode is 'web'", data.get("mode") == "web"))
        checks.append(("cached is false", data.get("cached") == False))
        checks.append(("spices non-empty", len(data.get("spices", [])) > 0))
        checks.append(("insight non-empty", bool(data.get("insight", "").strip())))
        checks.append(("sources non-empty", len(data.get("sources", [])) > 0))
        checks.append(("source_count >= 1", data.get("source_count", 0) >= 1))
        checks.append(("response time > 5s (AI call)", elapsed > 5))
        
        # Check spices structure
        if data.get("spices"):
            spice = data["spices"][0]
            checks.append(("spice has name", "name" in spice and bool(spice["name"])))
            checks.append(("spice avg > 0", spice.get("avg", 0) > 0))
            checks.append(("spice has unit", "unit" in spice and bool(spice["unit"])))
            checks.append(("spice has pct", "pct" in spice))
            print(f"\n  First spice: {spice}")
        
        # Check sources structure
        if data.get("sources"):
            source = data["sources"][0]
            url = source.get("url", "")
            checks.append(("source has url", bool(url)))
            checks.append(("source url is http(s)", url.startswith("http://") or url.startswith("https://")))
            checks.append(("source has name", "name" in source))
            checks.append(("source has title", "title" in source))
            print(f"  First source: {source}")
        
        print("\nValidation checks:")
        for check_name, check_result in checks:
            print(f"  {'✓' if check_result else '✗'} {check_name}")
        
        passed = all(result for _, result in checks)
        
        # Store spices count and source_count for comparison in scenario 2
        spices_count = len(data.get("spices", []))
        source_count = data.get("source_count", 0)
        
        print_result("Scenario 1: Cache MISS", passed, 
                    f"Response time: {elapsed:.2f}s, spices: {spices_count}, sources: {source_count}")
        
        return passed, spices_count, source_count
        
    except Exception as e:
        print_result("Scenario 1: Cache MISS", False, f"Error: {e}")
        return False, None, None

def test_scenario_2_cache_hit(expected_spices_count, expected_source_count):
    """
    Scenario 2: CACHE HIT
    Immediately repeat POST /api/scan/ai {"dish_name":"Rawon daging"}
    Expect: HTTP 200, cached=true, response time clearly FASTER (ideally <1-2s),
            spices count + source_count IDENTICAL to scenario 1
    """
    print_section("SCENARIO 2: CACHE HIT - Rawon daging (immediate repeat)")
    try:
        payload = {"dish_name": "Rawon daging"}
        print(f"Request: POST {BASE_URL}/scan/ai")
        print(f"Payload: {json.dumps(payload)}")
        print("Waiting for response (expecting <2s from cache)...\n")
        
        start = time.time()
        resp = requests.post(f"{BASE_URL}/scan/ai", json=payload, timeout=TIMEOUT)
        elapsed = time.time() - start
        
        print(f"Response time: {elapsed:.2f}s")
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code != 200:
            print_result("Scenario 2: Cache HIT", False, f"Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
        
        data = resp.json()
        print(f"\nResponse structure:")
        print(f"  mode: {data.get('mode')}")
        print(f"  cached: {data.get('cached')}")
        print(f"  dish: {data.get('dish')}")
        print(f"  spices count: {len(data.get('spices', []))}")
        print(f"  source_count: {data.get('source_count')}")
        
        spices_count = len(data.get("spices", []))
        source_count = data.get("source_count", 0)
        
        # Validation checks
        checks = []
        checks.append(("HTTP 200", resp.status_code == 200))
        checks.append(("cached is true", data.get("cached") == True))
        checks.append(("response time < 5s (from cache)", elapsed < 5))
        checks.append(("response time ideally < 2s", elapsed < 2))
        
        if expected_spices_count is not None:
            checks.append(("spices count IDENTICAL", spices_count == expected_spices_count))
        if expected_source_count is not None:
            checks.append(("source_count IDENTICAL", source_count == expected_source_count))
        
        print("\nValidation checks:")
        for check_name, check_result in checks:
            print(f"  {'✓' if check_result else '✗'} {check_name}")
        
        print(f"\nComparison with Scenario 1:")
        print(f"  Spices: {expected_spices_count} → {spices_count} (match: {spices_count == expected_spices_count})")
        print(f"  Sources: {expected_source_count} → {source_count} (match: {source_count == expected_source_count})")
        
        passed = all(result for _, result in checks)
        print_result("Scenario 2: Cache HIT", passed, 
                    f"Response time: {elapsed:.2f}s (cached), data identical")
        
        return passed
        
    except Exception as e:
        print_result("Scenario 2: Cache HIT", False, f"Error: {e}")
        return False

def test_scenario_3_normalization():
    """
    Scenario 3: NORMALIZATION
    POST /api/scan/ai {"dish_name":"  rawon  DAGING "} (different casing + extra spaces)
    Expect: cached=true (same cache entry matched)
    """
    print_section("SCENARIO 3: NORMALIZATION - '  rawon  DAGING ' (different casing/spaces)")
    try:
        payload = {"dish_name": "  rawon  DAGING "}
        print(f"Request: POST {BASE_URL}/scan/ai")
        print(f"Payload: {json.dumps(payload)}")
        print("Testing cache normalization (lowercase + trim + collapse spaces)...\n")
        
        start = time.time()
        resp = requests.post(f"{BASE_URL}/scan/ai", json=payload, timeout=TIMEOUT)
        elapsed = time.time() - start
        
        print(f"Response time: {elapsed:.2f}s")
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code != 200:
            print_result("Scenario 3: Normalization", False, f"Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
        
        data = resp.json()
        print(f"\nResponse structure:")
        print(f"  mode: {data.get('mode')}")
        print(f"  cached: {data.get('cached')}")
        print(f"  dish: {data.get('dish')}")
        
        # Validation checks
        checks = []
        checks.append(("HTTP 200", resp.status_code == 200))
        checks.append(("cached is true (normalization worked)", data.get("cached") == True))
        checks.append(("response time < 5s (from cache)", elapsed < 5))
        
        print("\nValidation checks:")
        for check_name, check_result in checks:
            print(f"  {'✓' if check_result else '✗'} {check_name}")
        
        passed = all(result for _, result in checks)
        print_result("Scenario 3: Normalization", passed, 
                    f"Cache normalization working (cached={data.get('cached')})")
        
        return passed
        
    except Exception as e:
        print_result("Scenario 3: Normalization", False, f"Error: {e}")
        return False

def test_scenario_4_fallback():
    """
    Scenario 4: FALLBACK unaffected
    POST /api/scan/ai {"dish_name":"zzxqwe999notarealfood"}
    Expect: 200, must NOT 500 (mode web or fallback either is fine, just no 500)
    """
    print_section("SCENARIO 4: FALLBACK - zzxqwe999notarealfood (nonsense dish)")
    try:
        payload = {"dish_name": "zzxqwe999notarealfood"}
        print(f"Request: POST {BASE_URL}/scan/ai")
        print(f"Payload: {json.dumps(payload)}")
        print("Testing graceful fallback (should NOT return 500)...\n")
        
        start = time.time()
        resp = requests.post(f"{BASE_URL}/scan/ai", json=payload, timeout=TIMEOUT)
        elapsed = time.time() - start
        
        print(f"Response time: {elapsed:.2f}s")
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code == 500:
            print_result("Scenario 4: Fallback", False, "CRITICAL: Got 500 error, should return 200")
            print(f"Response: {resp.text}")
            return False
        
        if resp.status_code != 200:
            print_result("Scenario 4: Fallback", False, f"Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
        
        data = resp.json()
        print(f"\nResponse structure:")
        print(f"  mode: {data.get('mode')}")
        print(f"  dish: {data.get('dish')}")
        print(f"  fallback_reason: {data.get('fallback_reason', 'N/A')}")
        
        # Validation checks
        checks = []
        checks.append(("HTTP 200 (NOT 500)", resp.status_code == 200))
        checks.append(("mode is 'web' or 'fallback'", data.get("mode") in ["web", "fallback"]))
        
        print("\nValidation checks:")
        for check_name, check_result in checks:
            print(f"  {'✓' if check_result else '✗'} {check_name}")
        
        passed = all(result for _, result in checks)
        print_result("Scenario 4: Fallback", passed, 
                    f"Graceful handling (mode={data.get('mode')})")
        
        return passed
        
    except Exception as e:
        print_result("Scenario 4: Fallback", False, f"Error: {e}")
        return False

def test_scenario_5_regression():
    """
    Scenario 5: REGRESSION
    POST /api/scan {"benchmark_slug":"rendang","measure":true} → 200 with spices
    GET /api/health → {ok:true}
    """
    print_section("SCENARIO 5: REGRESSION - Old endpoints still work")
    
    all_passed = True
    
    # Test 5a: POST /api/scan
    print("Test 5a: POST /api/scan (old benchmark endpoint)")
    try:
        payload = {"benchmark_slug": "rendang", "measure": True}
        print(f"Request: POST {BASE_URL}/scan")
        print(f"Payload: {json.dumps(payload)}\n")
        
        resp = requests.post(f"{BASE_URL}/scan", json=payload, timeout=30)
        
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code != 200:
            print_result("Test 5a: POST /api/scan", False, f"Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            all_passed = False
        else:
            data = resp.json()
            print(f"Response: benchmark_slug={data.get('benchmark_slug')}, spices count={len(data.get('spices', []))}")
            
            checks = []
            checks.append(("HTTP 200", resp.status_code == 200))
            checks.append(("benchmark_slug is 'rendang'", data.get("benchmark_slug") == "rendang"))
            checks.append(("spices non-empty", len(data.get("spices", [])) > 0))
            
            print("\nValidation checks:")
            for check_name, check_result in checks:
                print(f"  {'✓' if check_result else '✗'} {check_name}")
            
            passed = all(result for _, result in checks)
            print_result("Test 5a: POST /api/scan", passed)
            all_passed = all_passed and passed
    
    except Exception as e:
        print_result("Test 5a: POST /api/scan", False, f"Error: {e}")
        all_passed = False
    
    # Test 5b: GET /api/health
    print("\nTest 5b: GET /api/health")
    try:
        print(f"Request: GET {BASE_URL}/health\n")
        
        resp = requests.get(f"{BASE_URL}/health", timeout=10)
        
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code != 200:
            print_result("Test 5b: GET /api/health", False, f"Expected 200, got {resp.status_code}")
            print(f"Response: {resp.text}")
            all_passed = False
        else:
            data = resp.json()
            print(f"Response: {data}")
            
            checks = []
            checks.append(("HTTP 200", resp.status_code == 200))
            checks.append(("ok is true", data.get("ok") == True))
            
            print("\nValidation checks:")
            for check_name, check_result in checks:
                print(f"  {'✓' if check_result else '✗'} {check_name}")
            
            passed = all(result for _, result in checks)
            print_result("Test 5b: GET /api/health", passed)
            all_passed = all_passed and passed
    
    except Exception as e:
        print_result("Test 5b: GET /api/health", False, f"Error: {e}")
        all_passed = False
    
    print_result("Scenario 5: Regression", all_passed, "Old endpoints working correctly")
    return all_passed

def main():
    print("\n" + "="*80)
    print("  NutriVane Backend CACHE Testing - POST /api/scan/ai")
    print("  Backend URL: " + BASE_URL)
    print("  Testing cache functionality with 5 scenarios")
    print("="*80)
    
    results = {}
    
    # Scenario 1: Cache MISS (first call)
    passed_1, spices_count, source_count = test_scenario_1_cache_miss()
    results["scenario_1_cache_miss"] = passed_1
    
    # Small delay between scenarios
    time.sleep(1)
    
    # Scenario 2: Cache HIT (immediate repeat)
    results["scenario_2_cache_hit"] = test_scenario_2_cache_hit(spices_count, source_count)
    
    # Small delay
    time.sleep(1)
    
    # Scenario 3: Normalization
    results["scenario_3_normalization"] = test_scenario_3_normalization()
    
    # Small delay
    time.sleep(1)
    
    # Scenario 4: Fallback
    results["scenario_4_fallback"] = test_scenario_4_fallback()
    
    # Small delay
    time.sleep(1)
    
    # Scenario 5: Regression
    results["scenario_5_regression"] = test_scenario_5_regression()
    
    # Summary
    print_section("TEST SUMMARY")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    print(f"Total scenarios: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print()
    
    for scenario_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {scenario_name}")
    
    print("\n" + "="*80)
    
    if failed == 0:
        print("🎉 ALL CACHE TESTS PASSED!")
        print("Cache functionality working correctly:")
        print("  ✓ Cache MISS: First call takes ~10-25s (AI calls)")
        print("  ✓ Cache HIT: Repeat call <2s (from cache)")
        print("  ✓ Normalization: Different casing/spaces matched")
        print("  ✓ Fallback: Graceful handling (no 500 errors)")
        print("  ✓ Regression: Old endpoints still working")
    else:
        print(f"⚠️  {failed} scenario(s) failed. Check details above.")
    
    print("="*80 + "\n")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
