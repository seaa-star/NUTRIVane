#!/usr/bin/env python3
"""
Backend API Testing for NutriVane - Scan History & Scan Favorites
Tests the new scan history and scan favorites endpoints with authentication.
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
scan_id = None
favorite_id = None
scan_result_data = None


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


print("=" * 80)
print("NutriVane Backend API Testing - Scan History & Scan Favorites")
print("=" * 80)
print()

# Test 1: POST /api/scan/ai with Bearer token (Rawon daging)
print("Test 1: POST /api/scan/ai with Bearer token (Rawon daging)")
print("   This may take 10-30 seconds for AI processing...")
resp = make_request("POST", "/scan/ai", token=DEV_TOKEN, json_data={"dish_name": "Rawon daging"}, timeout=60)
if resp and resp.status_code == 200:
    data = resp.json()
    scan_result_data = data
    
    # Check required fields
    has_mode = "mode" in data and data["mode"] in ["web", "fallback"]
    has_spices = "spices" in data and isinstance(data["spices"], list) and len(data["spices"]) > 0
    has_sources = "sources" in data and isinstance(data["sources"], list) and len(data["sources"]) > 0
    has_saved = "saved_to_account" in data and data["saved_to_account"] is True
    
    all_checks = has_mode and has_spices and has_sources and has_saved
    
    details = f"Status: {resp.status_code}, Mode: {data.get('mode')}, Spices: {len(data.get('spices', []))}, Sources: {len(data.get('sources', []))}, Saved: {data.get('saved_to_account')}"
    log_test("POST /api/scan/ai with auth", all_checks, details)
    
    if not all_checks:
        print(f"   Missing fields - mode: {has_mode}, spices: {has_spices}, sources: {has_sources}, saved_to_account: {has_saved}")
else:
    log_test("POST /api/scan/ai with auth", False, f"Status: {resp.status_code if resp else 'No response'}")
    scan_result_data = None

time.sleep(1)

# Test 2: GET /api/scans/history (with token) - should include Rawon daging
print("\nTest 2: GET /api/scans/history (with token)")
resp = make_request("GET", "/scans/history", token=DEV_TOKEN)
if resp and resp.status_code == 200:
    data = resp.json()
    is_array = isinstance(data, list)
    
    # Look for Rawon daging scan
    rawon_scan = None
    for item in data:
        dish_name = item.get("dish", "").lower()
        if "rawon" in dish_name and "daging" in dish_name:
            rawon_scan = item
            scan_id = item.get("id")
            break
    
    has_rawon = rawon_scan is not None
    
    # Check required fields in the scan item
    if rawon_scan:
        required_fields = ["id", "dish", "mode", "cached", "source_count", "spice_count", "confidence", "had_image", "benchmark_slug", "created_at"]
        has_all_fields = all(field in rawon_scan for field in required_fields)
        
        details = f"Status: {resp.status_code}, Array: {is_array}, Count: {len(data)}, Has Rawon: {has_rawon}, Fields complete: {has_all_fields}"
        log_test("GET /api/scans/history", is_array and has_rawon and has_all_fields, details)
        
        if not has_all_fields:
            missing = [f for f in required_fields if f not in rawon_scan]
            print(f"   Missing fields in scan item: {missing}")
    else:
        log_test("GET /api/scans/history", False, f"Status: {resp.status_code}, Rawon daging scan not found in history")
else:
    log_test("GET /api/scans/history", False, f"Status: {resp.status_code if resp else 'No response'}")

time.sleep(1)

# Test 3: GET /api/scans/history/{id} (with token) - full result with spices+sources
if scan_id:
    print(f"\nTest 3: GET /api/scans/history/{scan_id} (with token)")
    resp = make_request("GET", f"/scans/history/{scan_id}", token=DEV_TOKEN)
    if resp and resp.status_code == 200:
        data = resp.json()
        
        has_spices = "spices" in data and isinstance(data["spices"], list) and len(data["spices"]) > 0
        has_sources = "sources" in data and isinstance(data["sources"], list) and len(data["sources"]) > 0
        has_insight = "insight" in data and data["insight"]
        has_from_history = "from_history" in data and data["from_history"] is True
        
        all_checks = has_spices and has_sources and has_insight and has_from_history
        
        details = f"Status: {resp.status_code}, Spices: {len(data.get('spices', []))}, Sources: {len(data.get('sources', []))}, from_history: {data.get('from_history')}"
        log_test("GET /api/scans/history/{id}", all_checks, details)
        
        if not all_checks:
            print(f"   Missing - spices: {has_spices}, sources: {has_sources}, insight: {has_insight}, from_history: {has_from_history}")
    else:
        log_test("GET /api/scans/history/{id}", False, f"Status: {resp.status_code if resp else 'No response'}")
    
    time.sleep(1)
    
    # Test 3b: GET /api/scans/history/{random_id} - should return 404
    print(f"\nTest 3b: GET /api/scans/history/999999 (non-owned id)")
    resp = make_request("GET", "/scans/history/999999", token=DEV_TOKEN)
    is_404 = resp and resp.status_code == 404
    log_test("GET /api/scans/history/{non_owned_id} returns 404", is_404, f"Status: {resp.status_code if resp else 'No response'}")
else:
    print("\nTest 3: SKIPPED - No scan_id from previous test")
    log_test("GET /api/scans/history/{id}", False, "Skipped - no scan_id")

time.sleep(1)

# Test 4: POST /api/scan-favorites (with token)
if scan_result_data:
    print("\nTest 4: POST /api/scan-favorites (with token)")
    resp = make_request("POST", "/scan-favorites", token=DEV_TOKEN, 
                       json_data={"dish": "Rawon daging", "result": scan_result_data})
    if resp and resp.status_code == 200:
        data = resp.json()
        is_array = isinstance(data, list)
        
        # Look for Rawon daging in the returned list
        rawon_fav = None
        for item in data:
            dish_name = item.get("dish", "").lower()
            if "rawon" in dish_name and "daging" in dish_name:
                rawon_fav = item
                favorite_id = item.get("id")
                break
        
        has_rawon = rawon_fav is not None
        
        # Check required fields
        if rawon_fav:
            required_fields = ["id", "dish", "source_count", "spice_count", "created_at"]
            has_all_fields = all(field in rawon_fav for field in required_fields)
            
            details = f"Status: {resp.status_code}, Array: {is_array}, Has Rawon: {has_rawon}, Fields complete: {has_all_fields}"
            log_test("POST /api/scan-favorites", is_array and has_rawon and has_all_fields, details)
        else:
            log_test("POST /api/scan-favorites", False, f"Status: {resp.status_code}, Rawon daging not found in returned list")
    else:
        log_test("POST /api/scan-favorites", False, f"Status: {resp.status_code if resp else 'No response'}")
else:
    print("\nTest 4: SKIPPED - No scan result data from Test 1")
    log_test("POST /api/scan-favorites", False, "Skipped - no scan result data")

time.sleep(1)

# Test 5: GET /api/scan-favorites (with token)
print("\nTest 5: GET /api/scan-favorites (with token)")
resp = make_request("GET", "/scan-favorites", token=DEV_TOKEN)
if resp and resp.status_code == 200:
    data = resp.json()
    is_array = isinstance(data, list)
    
    # Look for Rawon daging
    rawon_fav = None
    for item in data:
        dish_name = item.get("dish", "").lower()
        if "rawon" in dish_name and "daging" in dish_name:
            rawon_fav = item
            if not favorite_id:
                favorite_id = item.get("id")
            break
    
    has_rawon = rawon_fav is not None
    
    details = f"Status: {resp.status_code}, Array: {is_array}, Count: {len(data)}, Has Rawon: {has_rawon}"
    log_test("GET /api/scan-favorites", is_array and has_rawon, details)
else:
    log_test("GET /api/scan-favorites", False, f"Status: {resp.status_code if resp else 'No response'}")

time.sleep(1)

# Test 6: GET /api/scan-favorites/{id} (with token)
if favorite_id:
    print(f"\nTest 6: GET /api/scan-favorites/{favorite_id} (with token)")
    resp = make_request("GET", f"/scan-favorites/{favorite_id}", token=DEV_TOKEN)
    if resp and resp.status_code == 200:
        data = resp.json()
        
        has_spices = "spices" in data and isinstance(data["spices"], list) and len(data["spices"]) > 0
        has_sources = "sources" in data and isinstance(data["sources"], list) and len(data["sources"]) > 0
        has_from_favorite = "from_favorite" in data and data["from_favorite"] is True
        
        all_checks = has_spices and has_sources and has_from_favorite
        
        details = f"Status: {resp.status_code}, Spices: {len(data.get('spices', []))}, Sources: {len(data.get('sources', []))}, from_favorite: {data.get('from_favorite')}"
        log_test("GET /api/scan-favorites/{id}", all_checks, details)
        
        if not all_checks:
            print(f"   Missing - spices: {has_spices}, sources: {has_sources}, from_favorite: {has_from_favorite}")
    else:
        log_test("GET /api/scan-favorites/{id}", False, f"Status: {resp.status_code if resp else 'No response'}")
else:
    print("\nTest 6: SKIPPED - No favorite_id from previous tests")
    log_test("GET /api/scan-favorites/{id}", False, "Skipped - no favorite_id")

time.sleep(1)

# Test 7: POST /api/scan-favorites again with same dish (different casing) - upsert, no duplicate
if scan_result_data:
    print("\nTest 7: POST /api/scan-favorites with different casing (upsert test)")
    
    # Get current count
    resp_before = make_request("GET", "/scan-favorites", token=DEV_TOKEN)
    count_before = len(resp_before.json()) if resp_before and resp_before.status_code == 200 else 0
    
    # Post with EXACT same dish name but different casing (to test case-insensitive upsert)
    resp = make_request("POST", "/scan-favorites", token=DEV_TOKEN, 
                       json_data={"dish": "rawon daging", "result": scan_result_data})
    if resp and resp.status_code == 200:
        data = resp.json()
        count_after = len(data)
        
        # Count should be the same (upsert, not insert)
        no_duplicate = count_after == count_before
        
        # Check that Rawon daging still exists (only one entry)
        rawon_count = sum(1 for item in data if "rawon" in item.get("dish", "").lower() and "daging" in item.get("dish", "").lower())
        only_one_rawon = rawon_count == 1
        
        all_checks = no_duplicate and only_one_rawon
        
        details = f"Status: {resp.status_code}, Count before: {count_before}, Count after: {count_after}, Rawon entries: {rawon_count}"
        log_test("POST /api/scan-favorites upsert (no duplicate)", all_checks, details)
    else:
        log_test("POST /api/scan-favorites upsert (no duplicate)", False, f"Status: {resp.status_code if resp else 'No response'}")
else:
    print("\nTest 7: SKIPPED - No scan result data")
    log_test("POST /api/scan-favorites upsert", False, "Skipped - no scan result data")

time.sleep(1)

# Test 8: DELETE /api/scan-favorites/{id} (with token)
if favorite_id:
    print(f"\nTest 8: DELETE /api/scan-favorites/{favorite_id} (with token)")
    resp = make_request("DELETE", f"/scan-favorites/{favorite_id}", token=DEV_TOKEN)
    if resp and resp.status_code == 200:
        data = resp.json()
        is_array = isinstance(data, list)
        
        # Check that Rawon daging is no longer in the list
        rawon_exists = any("rawon" in item.get("dish", "").lower() and "daging" in item.get("dish", "").lower() for item in data)
        
        all_checks = is_array and not rawon_exists
        
        details = f"Status: {resp.status_code}, Array: {is_array}, Rawon still exists: {rawon_exists}"
        log_test("DELETE /api/scan-favorites/{id}", all_checks, details)
    else:
        log_test("DELETE /api/scan-favorites/{id}", False, f"Status: {resp.status_code if resp else 'No response'}")
else:
    print("\nTest 8: SKIPPED - No favorite_id")
    log_test("DELETE /api/scan-favorites/{id}", False, "Skipped - no favorite_id")

time.sleep(1)

# Test 9: Auth guards - endpoints without token should return 401 or 403
print("\nTest 9a: GET /api/scans/history without token (should be 401/403)")
resp = make_request("GET", "/scans/history")
is_unauthorized = resp and resp.status_code in [401, 403]
log_test("GET /api/scans/history without token returns 401/403", is_unauthorized, f"Status: {resp.status_code if resp else 'No response'}")

time.sleep(0.5)

print("\nTest 9b: GET /api/scan-favorites without token (should be 401/403)")
resp = make_request("GET", "/scan-favorites")
is_unauthorized = resp and resp.status_code in [401, 403]
log_test("GET /api/scan-favorites without token returns 401/403", is_unauthorized, f"Status: {resp.status_code if resp else 'No response'}")

time.sleep(0.5)

print("\nTest 9c: POST /api/scan-favorites without token (should be 401/403)")
resp = make_request("POST", "/scan-favorites", json_data={"dish": "Test", "result": {}})
is_unauthorized = resp and resp.status_code in [401, 403]
log_test("POST /api/scan-favorites without token returns 401/403", is_unauthorized, f"Status: {resp.status_code if resp else 'No response'}")

time.sleep(1)

# Test 10: GET /api/me (with token) - should include scan_favorites array
print("\nTest 10: GET /api/me (with token) - should include scan_favorites")
resp = make_request("GET", "/me", token=DEV_TOKEN)
if resp and resp.status_code == 200:
    data = resp.json()
    
    has_scan_favorites = "scan_favorites" in data
    is_array = isinstance(data.get("scan_favorites"), list) if has_scan_favorites else False
    
    all_checks = has_scan_favorites and is_array
    
    details = f"Status: {resp.status_code}, Has scan_favorites: {has_scan_favorites}, Is array: {is_array}"
    log_test("GET /api/me includes scan_favorites array", all_checks, details)
else:
    log_test("GET /api/me includes scan_favorites array", False, f"Status: {resp.status_code if resp else 'No response'}")

# Summary
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

print("\n" + "=" * 80)
