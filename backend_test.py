#!/usr/bin/env python3
"""
Backend API Testing for NutriVane - AI Scan Nutrition Estimate Feature
Tests the NEW nutrition estimate feature in POST /api/scan/ai endpoint.
"""
import requests
import json
import time
from typing import Optional

# Configuration
BASE_URL = "https://nutrivane-rempah.preview.emergentagent.com/api"
DEV_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMTExMTExMS0xMTExLTQxMTEtODExMS0xMTExMTExMTExMTEiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJpc3MiOiJodHRwOi8vbG9jYWxob3N0OjU0MzIxL2F1dGgvdjEiLCJlbWFpbCI6ImFzaGFAZXhhbXBsZS5jb20iLCJ1c2VyX21ldGFkYXRhIjp7ImZ1bGxfbmFtZSI6IkFzaGEgUHJhdGl3aSIsImF2YXRhcl91cmwiOiIifSwiaWF0IjoxNzkxNzEzOTcwLCJleHAiOjE3OTE4MDAzNzB9.U0nw8hVqGYqgIHUyHlwQg5HTX2BDYDoTyJgST_hq2zo"

# Test results tracking
test_results = []
nasi_goreng_nutrition = None
soto_ayam_scan_id = None


def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"name": test_name, "passed": passed, "details": details})
    print(f"{status}: {test_name}")
    if details:
        print(f"   Details: {details}")


def make_request(method: str, endpoint: str, token: Optional[str] = None, json_data: dict = None, timeout: int = 60):
    """Make HTTP request with optional auth"""
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=timeout)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=json_data, timeout=timeout)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=timeout)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return resp
    except requests.exceptions.Timeout:
        print(f"   Request timeout after {timeout}s")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"   Connection error: {e}")
        return None
    except Exception as e:
        print(f"   Request error: {e}")
        return None


def validate_nutrition_object(nutrition, test_name_prefix: str) -> bool:
    """Validate nutrition object structure and values"""
    if not nutrition:
        log_test(f"{test_name_prefix} - nutrition object exists", False, "nutrition is None or missing")
        return False
    
    if not isinstance(nutrition, dict):
        log_test(f"{test_name_prefix} - nutrition object is dict", False, f"nutrition is {type(nutrition)}")
        return False
    
    # Check required fields
    required_fields = ["serving", "calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "note"]
    missing_fields = [f for f in required_fields if f not in nutrition]
    if missing_fields:
        log_test(f"{test_name_prefix} - nutrition has all fields", False, f"Missing fields: {missing_fields}")
        return False
    
    # Check serving is string
    if not isinstance(nutrition["serving"], str):
        log_test(f"{test_name_prefix} - serving is string", False, f"serving is {type(nutrition['serving'])}")
        return False
    
    # Check note is string
    if not isinstance(nutrition["note"], str):
        log_test(f"{test_name_prefix} - note is string", False, f"note is {type(nutrition['note'])}")
        return False
    
    # Check numeric fields are numbers >= 0
    numeric_fields = ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]
    for field in numeric_fields:
        value = nutrition[field]
        if not isinstance(value, (int, float)):
            log_test(f"{test_name_prefix} - {field} is numeric", False, f"{field} is {type(value)}")
            return False
        if value < 0:
            log_test(f"{test_name_prefix} - {field} >= 0", False, f"{field} = {value}")
            return False
    
    # Check at least one macro > 0
    macros = [nutrition["calories"], nutrition["protein_g"], nutrition["carbs_g"], nutrition["fat_g"]]
    if all(m == 0 for m in macros):
        log_test(f"{test_name_prefix} - at least one macro > 0", False, "All macros are 0")
        return False
    
    # All checks passed
    details = (f"serving='{nutrition['serving']}', calories={nutrition['calories']}, "
               f"protein_g={nutrition['protein_g']}, carbs_g={nutrition['carbs_g']}, "
               f"fat_g={nutrition['fat_g']}, fiber_g={nutrition['fiber_g']}, "
               f"note='{nutrition['note'][:50]}...'")
    log_test(f"{test_name_prefix} - nutrition object valid", True, details)
    return True


print("=" * 80)
print("NutriVane Backend API Testing - AI Scan Nutrition Estimate Feature")
print("=" * 80)
print()

# ============================================================================
# SCENARIO 1: POST /api/scan/ai with {"dish_name": "Nasi goreng"} (no auth)
# ============================================================================
print("SCENARIO 1: POST /api/scan/ai with Nasi goreng (no auth)")
print("   This may take 10-30 seconds for AI processing...")
print()

resp = make_request("POST", "/scan/ai", json_data={"dish_name": "Nasi goreng"}, timeout=60)

if resp and resp.status_code == 200:
    data = resp.json()
    
    # Check response status
    log_test("Scenario 1 - Response 200", True, f"Status: {resp.status_code}")
    
    # Check mode (should be 'web' or 'fallback')
    mode = data.get("mode")
    is_web_or_fallback = mode in ["web", "fallback"]
    log_test("Scenario 1 - mode is web or fallback", is_web_or_fallback, f"mode={mode}")
    
    # Check nutrition object
    nutrition = data.get("nutrition")
    if nutrition:
        nutrition_valid = validate_nutrition_object(nutrition, "Scenario 1")
        nasi_goreng_nutrition = nutrition  # Save for comparison in Scenario 2
    else:
        if mode == "fallback":
            log_test("Scenario 1 - nutrition object", True, "nutrition absent (acceptable for fallback mode)")
            nutrition_valid = True  # Acceptable for fallback
        else:
            log_test("Scenario 1 - nutrition object exists", False, "nutrition is missing (mode=web)")
            nutrition_valid = False
    
    # Check existing fields (regression)
    has_spices = "spices" in data and isinstance(data["spices"], list) and len(data["spices"]) > 0
    has_sources = "sources" in data and isinstance(data["sources"], list)
    has_source_count = "source_count" in data and isinstance(data["source_count"], int)
    has_dish = "dish" in data or "menu_name" in data
    
    regression_pass = has_spices and has_sources and has_source_count and has_dish
    
    details = (f"spices: {len(data.get('spices', []))}, sources: {len(data.get('sources', []))}, "
               f"source_count: {data.get('source_count')}, dish: {data.get('dish') or data.get('menu_name')}")
    log_test("Scenario 1 - regression (existing fields present)", regression_pass, details)
    
    # Check spices structure
    if has_spices:
        first_spice = data["spices"][0]
        spice_has_structure = all(k in first_spice for k in ["name", "avg", "unit", "pct"])
        log_test("Scenario 1 - spices have correct structure", spice_has_structure, 
                f"First spice: {first_spice}")
    
else:
    log_test("Scenario 1 - Response 200", False, f"Status: {resp.status_code if resp else 'No response'}")
    nutrition_valid = False

time.sleep(2)

# ============================================================================
# SCENARIO 2: POST same dish again -> cached=true with nutrition still present
# ============================================================================
print("\nSCENARIO 2: POST /api/scan/ai with Nasi goreng again (cache test)")
print("   Should be much faster (cached)...")
print()

start_time = time.time()
resp = make_request("POST", "/scan/ai", json_data={"dish_name": "Nasi goreng"}, timeout=60)
elapsed_time = time.time() - start_time

if resp and resp.status_code == 200:
    data = resp.json()
    
    # Check response status
    log_test("Scenario 2 - Response 200", True, f"Status: {resp.status_code}, Time: {elapsed_time:.2f}s")
    
    # Check cached flag
    is_cached = data.get("cached") is True
    log_test("Scenario 2 - cached=true", is_cached, f"cached={data.get('cached')}, Time: {elapsed_time:.2f}s")
    
    # Check nutrition object still present
    nutrition = data.get("nutrition")
    if nutrition:
        nutrition_valid = validate_nutrition_object(nutrition, "Scenario 2")
        
        # Compare with Scenario 1 nutrition (should be identical)
        if nasi_goreng_nutrition and nutrition_valid:
            nutrition_identical = (
                nutrition["calories"] == nasi_goreng_nutrition["calories"] and
                nutrition["protein_g"] == nasi_goreng_nutrition["protein_g"] and
                nutrition["carbs_g"] == nasi_goreng_nutrition["carbs_g"] and
                nutrition["fat_g"] == nasi_goreng_nutrition["fat_g"] and
                nutrition["fiber_g"] == nasi_goreng_nutrition["fiber_g"]
            )
            log_test("Scenario 2 - nutrition values identical to Scenario 1", nutrition_identical,
                    f"Scenario 1: {nasi_goreng_nutrition}, Scenario 2: {nutrition}")
    else:
        mode = data.get("mode")
        if mode == "fallback":
            log_test("Scenario 2 - nutrition object", True, "nutrition absent (acceptable for fallback mode)")
        else:
            log_test("Scenario 2 - nutrition object exists", False, "nutrition is missing")
    
    # Check spices and sources still present
    has_spices = "spices" in data and isinstance(data["spices"], list) and len(data["spices"]) > 0
    has_sources = "sources" in data and isinstance(data["sources"], list)
    
    log_test("Scenario 2 - spices and sources still present", has_spices and has_sources,
            f"spices: {len(data.get('spices', []))}, sources: {len(data.get('sources', []))}")
    
else:
    log_test("Scenario 2 - Response 200", False, f"Status: {resp.status_code if resp else 'No response'}")

time.sleep(2)

# ============================================================================
# SCENARIO 3: With Bearer token, POST /api/scan/ai, then GET history
# ============================================================================
print("\nSCENARIO 3: POST /api/scan/ai with Soto ayam (with auth), then check history")
print("   This may take 10-30 seconds for AI processing...")
print()

# Step 3a: POST /api/scan/ai with token
resp = make_request("POST", "/scan/ai", token=DEV_TOKEN, json_data={"dish_name": "Soto ayam"}, timeout=60)

if resp and resp.status_code == 200:
    data = resp.json()
    
    log_test("Scenario 3a - POST /api/scan/ai with token - Response 200", True, f"Status: {resp.status_code}")
    
    # Check saved_to_account
    saved = data.get("saved_to_account") is True
    log_test("Scenario 3a - saved_to_account=true", saved, f"saved_to_account={data.get('saved_to_account')}")
    
    # Check nutrition object
    nutrition = data.get("nutrition")
    if nutrition:
        validate_nutrition_object(nutrition, "Scenario 3a")
    else:
        mode = data.get("mode")
        if mode == "fallback":
            log_test("Scenario 3a - nutrition object", True, "nutrition absent (acceptable for fallback mode)")
        else:
            log_test("Scenario 3a - nutrition object exists", False, "nutrition is missing")
    
else:
    log_test("Scenario 3a - POST /api/scan/ai with token - Response 200", False, 
            f"Status: {resp.status_code if resp else 'No response'}")

time.sleep(2)

# Step 3b: GET /api/scans/history
print("\nScenario 3b: GET /api/scans/history")
resp = make_request("GET", "/scans/history", token=DEV_TOKEN)

if resp and resp.status_code == 200:
    data = resp.json()
    
    log_test("Scenario 3b - GET /api/scans/history - Response 200", True, f"Status: {resp.status_code}")
    
    # Look for Soto ayam scan
    soto_scan = None
    for item in data:
        dish_name = item.get("dish", "").lower()
        if "soto" in dish_name and "ayam" in dish_name:
            soto_scan = item
            soto_ayam_scan_id = item.get("id")
            break
    
    if soto_scan:
        log_test("Scenario 3b - Soto ayam found in history", True, f"id={soto_scan.get('id')}, dish={soto_scan.get('dish')}")
    else:
        log_test("Scenario 3b - Soto ayam found in history", False, "Soto ayam not found in history")
    
else:
    log_test("Scenario 3b - GET /api/scans/history - Response 200", False, 
            f"Status: {resp.status_code if resp else 'No response'}")

time.sleep(2)

# Step 3c: GET /api/scans/history/{id}
if soto_ayam_scan_id:
    print(f"\nScenario 3c: GET /api/scans/history/{soto_ayam_scan_id}")
    resp = make_request("GET", f"/scans/history/{soto_ayam_scan_id}", token=DEV_TOKEN)
    
    if resp and resp.status_code == 200:
        data = resp.json()
        
        log_test("Scenario 3c - GET /api/scans/history/{id} - Response 200", True, f"Status: {resp.status_code}")
        
        # Check nutrition object in history
        nutrition = data.get("nutrition")
        if nutrition:
            validate_nutrition_object(nutrition, "Scenario 3c")
        else:
            mode = data.get("mode")
            if mode == "fallback":
                log_test("Scenario 3c - nutrition object", True, "nutrition absent (acceptable for fallback mode)")
            else:
                log_test("Scenario 3c - nutrition object exists", False, "nutrition is missing in history")
        
        # Check spices and sources present
        has_spices = "spices" in data and isinstance(data["spices"], list) and len(data["spices"]) > 0
        has_sources = "sources" in data and isinstance(data["sources"], list)
        
        log_test("Scenario 3c - spices and sources present in history", has_spices and has_sources,
                f"spices: {len(data.get('spices', []))}, sources: {len(data.get('sources', []))}")
        
    else:
        log_test("Scenario 3c - GET /api/scans/history/{id} - Response 200", False, 
                f"Status: {resp.status_code if resp else 'No response'}")
else:
    print("\nScenario 3c: SKIPPED - No scan_id from Scenario 3b")
    log_test("Scenario 3c - GET /api/scans/history/{id}", False, "Skipped - no scan_id")

time.sleep(2)

# ============================================================================
# SCENARIO 4: Regression - existing fields unaffected
# ============================================================================
print("\nSCENARIO 4: Regression test - verify existing fields still work")
print()

# Test with a simple dish to ensure all existing fields are present
resp = make_request("POST", "/scan/ai", json_data={"dish_name": "Rendang"}, timeout=60)

if resp and resp.status_code == 200:
    data = resp.json()
    
    log_test("Scenario 4 - Response 200", True, f"Status: {resp.status_code}")
    
    # Check all existing fields
    has_dish = "dish" in data or "menu_name" in data
    has_spices = "spices" in data and isinstance(data["spices"], list) and len(data["spices"]) > 0
    has_insight = "insight" in data and isinstance(data["insight"], str)
    has_sources = "sources" in data and isinstance(data["sources"], list)
    has_source_count = "source_count" in data and isinstance(data["source_count"], int)
    has_mode = "mode" in data and data["mode"] in ["web", "fallback"]
    
    all_fields_present = has_dish and has_spices and has_insight and has_sources and has_source_count and has_mode
    
    details = (f"dish: {data.get('dish') or data.get('menu_name')}, "
               f"spices: {len(data.get('spices', []))}, "
               f"insight: {len(data.get('insight', ''))}, "
               f"sources: {len(data.get('sources', []))}, "
               f"source_count: {data.get('source_count')}, "
               f"mode: {data.get('mode')}")
    
    log_test("Scenario 4 - all existing fields present", all_fields_present, details)
    
    # Check spices structure (with avg, unit, pct)
    if has_spices:
        first_spice = data["spices"][0]
        spice_structure_valid = all(k in first_spice for k in ["name", "avg", "unit", "pct"])
        
        # Check avg is numeric and > 0
        avg_valid = isinstance(first_spice.get("avg"), (int, float)) and first_spice.get("avg") > 0
        
        # Check pct is numeric
        pct_valid = isinstance(first_spice.get("pct"), (int, float))
        
        spice_valid = spice_structure_valid and avg_valid and pct_valid
        
        log_test("Scenario 4 - spices structure valid", spice_valid, 
                f"First spice: name={first_spice.get('name')}, avg={first_spice.get('avg')}, "
                f"unit={first_spice.get('unit')}, pct={first_spice.get('pct')}")
    
    # Check sources structure
    if has_sources and len(data["sources"]) > 0:
        first_source = data["sources"][0]
        source_structure_valid = all(k in first_source for k in ["name", "title", "url"])
        
        # Check URL is valid (starts with http)
        url_valid = isinstance(first_source.get("url"), str) and first_source.get("url").startswith("http")
        
        source_valid = source_structure_valid and url_valid
        
        log_test("Scenario 4 - sources structure valid", source_valid,
                f"First source: name={first_source.get('name')}, url={first_source.get('url')[:50]}...")
    
else:
    log_test("Scenario 4 - Response 200", False, f"Status: {resp.status_code if resp else 'No response'}")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

passed = sum(1 for t in test_results if t["passed"])
total = len(test_results)
pass_rate = (passed / total * 100) if total > 0 else 0

print(f"Total tests: {total}")
print(f"Passed: {passed}")
print(f"Failed: {total - passed}")
print(f"Pass rate: {pass_rate:.1f}%")
print()

if total - passed > 0:
    print("Failed tests:")
    for t in test_results:
        if not t["passed"]:
            print(f"  ❌ {t['name']}")
            if t["details"]:
                print(f"     {t['details']}")
    print()

print("=" * 80)
print("NUTRITION FEATURE TEST COMPLETE")
print("=" * 80)
