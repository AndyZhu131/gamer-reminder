"""
Deep diagnostic script for GPU PDH sampler.
Tests each step of the PDH GPU detection process to identify issues.
"""

import sys
import os
import logging
import time
import io

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from packages.core.monitor.gpu_pdh_sampler import GpuPdhSampler
import ctypes
from ctypes import wintypes

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

def test_pdh_dll():
    """Test 1: Check if PDH DLL is available."""
    print("=" * 70)
    print("TEST 1: PDH DLL Availability")
    print("=" * 70)
    try:
        pdh_dll = ctypes.windll.pdh
        print("✓ PDH DLL loaded successfully")
        return pdh_dll
    except OSError as e:
        print(f"✗ PDH DLL not available: {e}")
        return None

def test_open_query(pdh_dll):
    """Test 2: Open PDH query."""
    print("\n" + "=" * 70)
    print("TEST 2: Open PDH Query")
    print("=" * 70)
    try:
        query_handle = wintypes.HANDLE()
        result = pdh_dll.PdhOpenQueryW(None, 0, ctypes.byref(query_handle))
        result_unsigned = result & 0xFFFFFFFF
        if result_unsigned == 0:
            print(f"✓ PdhOpenQueryW succeeded: handle={query_handle.value}")
            return query_handle
        else:
            print(f"✗ PdhOpenQueryW failed: {result} ({hex(result_unsigned)})")
            return None
    except Exception as e:
        print(f"✗ Exception: {e}")
        return None

def test_enum_objects(pdh_dll):
    """Test 3: Enumerate PDH objects to check if GPU Engine exists."""
    print("\n" + "=" * 70)
    print("TEST 3: Enumerate PDH Objects")
    print("=" * 70)
    try:
        # Try different detail levels
        for detail_level in [0x00000001, 0x00000000, 0x00000002]:  # PERF_DETAIL_WIZARD, PERF_DETAIL_NOVICE, PERF_DETAIL_ADVANCED
            buffer_size = ctypes.c_ulong(0)
            result = pdh_dll.PdhEnumObjectsW(
                None, None, None,
                ctypes.byref(buffer_size),
                detail_level, False
            )
            result_unsigned = result & 0xFFFFFFFF
            
            if result_unsigned == 0x800007D2:  # PDH_MORE_DATA
                print(f"✓ PdhEnumObjectsW size query returned PDH_MORE_DATA (detail={detail_level})")
                print(f"  Required buffer size: {buffer_size.value} WCHARs")
                
                buffer = ctypes.create_unicode_buffer(buffer_size.value)
                result = pdh_dll.PdhEnumObjectsW(
                    None, None, buffer,
                    ctypes.byref(buffer_size),
                    detail_level, False
                )
                result_unsigned = result & 0xFFFFFFFF
                
                if result_unsigned == 0:
                    objects = [o.strip() for o in buffer.value.split('\0') if o.strip()]
                    has_gpu = "GPU Engine" in objects
                    print(f"✓ Enumerated {len(objects)} PDH objects (detail={detail_level})")
                    print(f"  GPU Engine exists: {has_gpu}")
                    
                    # Check for GPU-related objects
                    gpu_related = [o for o in objects if 'gpu' in o.lower() or 'graphics' in o.lower() or 'video' in o.lower()]
                    if gpu_related:
                        print(f"  GPU-related objects found: {gpu_related}")
                    
                    if has_gpu:
                        print("  ✓ GPU Engine object found!")
                        return True
                    elif len(objects) < 10:
                        # If very few objects, show all
                        print("  Available objects:")
                        for obj in objects:
                            print(f"    - {obj}")
                    else:
                        print("  Available objects (first 50):")
                        for obj in objects[:50]:
                            print(f"    - {obj}")
                        if len(objects) > 50:
                            print(f"    ... and {len(objects) - 50} more")
                else:
                    print(f"✗ PdhEnumObjectsW failed: {result} ({hex(result_unsigned)})")
        
        # Even if not in enumeration, try direct access
        print("\n  Attempting direct access to GPU Engine (may work even if not in enumeration)...")
        return None  # Return None to indicate "try anyway"
    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_enum_gpu_items(pdh_dll):
    """Test 4: Enumerate GPU Engine items (instances and counters)."""
    print("\n" + "=" * 70)
    print("TEST 4: Enumerate GPU Engine Items")
    print("=" * 70)
    try:
        instance_size = ctypes.c_ulong(0)
        counter_size = ctypes.c_ulong(0)
        result = pdh_dll.PdhEnumObjectItemsW(
            None, None, "GPU Engine",
            None, ctypes.byref(instance_size),
            None, ctypes.byref(counter_size),
            0x00000002  # PDH_NOEXPANDCOUNTERS
        )
        result_unsigned = result & 0xFFFFFFFF
        
        if result_unsigned == 0x800007D2:  # PDH_MORE_DATA
            print(f"✓ PdhEnumObjectItemsW size query returned PDH_MORE_DATA (expected)")
            print(f"  Instance buffer size: {instance_size.value} WCHARs")
            print(f"  Counter buffer size: {counter_size.value} WCHARs")
            
            if instance_size.value == 0 or counter_size.value == 0:
                print("  ⚠ Buffer sizes are 0 - GPU Engine may not be available")
                return False
            
            instance_buffer = ctypes.create_unicode_buffer(instance_size.value)
            counter_buffer = ctypes.create_unicode_buffer(counter_size.value)
            result = pdh_dll.PdhEnumObjectItemsW(
                None, None, "GPU Engine",
                instance_buffer, ctypes.byref(instance_size),
                counter_buffer, ctypes.byref(counter_size),
                0x00000002
            )
            result_unsigned = result & 0xFFFFFFFF
            
            if result_unsigned == 0:
                instances = [i.strip() for i in instance_buffer.value.split('\0') if i.strip()]
                counters = [c.strip() for c in counter_buffer.value.split('\0') if c.strip()]
                print(f"✓ Enumerated {len(instances)} instances and {len(counters)} counters")
                
                print(f"\n  Instances (first 10):")
                for i, inst in enumerate(instances[:10], 1):
                    is_3d = "engtype_3D" in inst.lower()
                    marker = " [3D]" if is_3d else ""
                    print(f"    {i}. {inst}{marker}")
                if len(instances) > 10:
                    print(f"    ... and {len(instances) - 10} more")
                
                print(f"\n  Counters:")
                for i, cnt in enumerate(counters[:20], 1):
                    is_util = "utilization" in cnt.lower() and "percentage" in cnt.lower()
                    marker = " [UTIL]" if is_util else ""
                    print(f"    {i}. {cnt}{marker}")
                if len(counters) > 20:
                    print(f"    ... and {len(counters) - 20} more")
                
                util_counter = None
                for cnt in counters:
                    if 'utilization' in cnt.lower() and 'percentage' in cnt.lower():
                        util_counter = cnt
                        break
                
                if util_counter:
                    print(f"\n  ✓ Found Utilization Percentage counter: {util_counter}")
                else:
                    print(f"\n  ✗ Utilization Percentage counter NOT found")
                
                return len(instances) > 0 and util_counter is not None
            else:
                print(f"✗ PdhEnumObjectItemsW failed: {result} ({hex(result_unsigned)})")
                return False
        else:
            print(f"✗ PdhEnumObjectItemsW size query failed: {result} ({hex(result_unsigned)})")
            if result_unsigned == 0xC0000BB8:  # PDH_CSTATUS_NO_OBJECT
                print("  Error: PDH_CSTATUS_NO_OBJECT - GPU Engine object does not exist")
            elif result_unsigned == 0xC0000BB9:  # PDH_CSTATUS_NO_COUNTER
                print("  Error: PDH_CSTATUS_NO_COUNTER - GPU Engine exists but has no counters")
            return False
    except OSError as e:
        if "access violation" in str(e).lower():
            print(f"✗ Access violation - GPU Engine object likely doesn't exist or is inaccessible")
            print("  This usually means:")
            print("    - GPU drivers don't expose PDH counters")
            print("    - GPU is not properly initialized")
            print("    - Need to run as administrator")
        else:
            print(f"✗ Exception: {e}")
            import traceback
            traceback.print_exc()
        return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_expand_wildcard(pdh_dll):
    """Test 5: Expand wildcard path."""
    print("\n" + "=" * 70)
    print("TEST 5: Expand Wildcard Path")
    print("=" * 70)
    try:
        # Try both single and double backslash formats
        wildcards = [
            r"\GPU Engine(*)\Utilization Percentage",  # Single backslash (correct)
            r"\\GPU Engine(*)\\Utilization Percentage",  # Double backslash (for comparison)
        ]
        
        for wildcard in wildcards:
            print(f"\nTesting wildcard path: {wildcard}")
        
        buffer_size = ctypes.c_ulong(0)
        result = pdh_dll.PdhExpandWildCardPathW(
            None, wildcard, None,
            ctypes.byref(buffer_size), 0
        )
        result_unsigned = result & 0xFFFFFFFF
        
        if result_unsigned == 0x800007D2:  # PDH_MORE_DATA
            print(f"✓ Size query returned PDH_MORE_DATA (expected)")
            print(f"  Required buffer size: {buffer_size.value} WCHARs")
            
            expanded_buffer = ctypes.create_unicode_buffer(buffer_size.value)
            result = pdh_dll.PdhExpandWildCardPathW(
                None, wildcard, expanded_buffer,
                ctypes.byref(buffer_size), 0
            )
            result_unsigned = result & 0xFFFFFFFF
            
            if result_unsigned == 0:
                # Use wstring_at to get full buffer
                paths_str = ctypes.wstring_at(expanded_buffer, buffer_size.value)
                paths = []
                for p in paths_str.split('\0'):
                    p_stripped = p.strip()
                    if not p_stripped:
                        break
                    paths.append(p_stripped)
                
                print(f"✓ Expanded to {len(paths)} paths")
                print(f"\n  First 10 paths:")
                for i, path in enumerate(paths[:10], 1):
                    is_3d = "engtype_3D" in path.lower()
                    marker = " [3D]" if is_3d else ""
                    print(f"    {i}. {path}{marker}")
                if len(paths) > 10:
                    print(f"    ... and {len(paths) - 10} more")
                
                return len(paths) > 0
            else:
                print(f"✗ PdhExpandWildCardPathW failed: {result} ({hex(result_unsigned)})")
                return False
        else:
            print(f"✗ Size query failed: {result} ({hex(result_unsigned)})")
            if result_unsigned == 0:
                print("  (Returned SUCCESS but 0 size - no matching counters)")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_sampler():
    """Test 6: Full sampler test."""
    print("\n" + "=" * 70)
    print("TEST 6: Full GPU Sampler Test")
    print("=" * 70)
    try:
        sampler = GpuPdhSampler()
        print("Initializing sampler...")
        if sampler.start():
            print("✓ Sampler initialized successfully")
            print(f"  Counters: {len(sampler._counter_handles)}")
            print(f"  Paths: {len(sampler._counter_paths)}")
            
            print("\nSampling GPU utilization (5 samples)...")
            for i in range(5):
                gpu_util = sampler.sample()
                if gpu_util is not None:
                    print(f"  Sample {i+1}: {gpu_util:.2f}%")
                else:
                    print(f"  Sample {i+1}: N/A (sampling failed)")
                time.sleep(1.0)
            
            sampler.close()
            return True
        else:
            print("✗ Sampler initialization failed")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 70)
    print("GPU PDH Deep Diagnostic Tool")
    print("=" * 70)
    print()
    
    # Run tests
    pdh_dll = test_pdh_dll()
    if not pdh_dll:
        print("\n✗ Cannot proceed - PDH DLL not available")
        return 1
    
    query_handle = test_open_query(pdh_dll)
    if query_handle:
        # Close the test query
        pdh_dll.PdhCloseQuery(query_handle)
    
    has_gpu = test_enum_objects(pdh_dll)
    if has_gpu is False:
        print("\n⚠ GPU Engine object not found in enumeration")
        print("  However, PowerShell Get-Counter can see it, so trying direct access...")
    elif has_gpu is None:
        print("\n⚠ GPU Engine not in enumeration, but attempting direct access anyway...")
    
    # Try enumeration even if not in object list (PowerShell can access it)
    has_items = test_enum_gpu_items(pdh_dll)
    has_paths = test_expand_wildcard(pdh_dll)
    
    # Try alternative: use PowerShell's approach - query directly
    if not has_paths:
        print("\n" + "=" * 70)
        print("TEST 5b: Alternative - Direct Counter Query")
        print("=" * 70)
        print("Attempting to query GPU Engine counter directly...")
        try:
            query_handle = wintypes.HANDLE()
            result = pdh_dll.PdhOpenQueryW(None, 0, ctypes.byref(query_handle))
            if (result & 0xFFFFFFFF) == 0:
                # Try a few common GPU Engine path patterns
                test_paths = [
                    r"\\GPU Engine(*engtype_3D*)\Utilization Percentage",
                    r"\\GPU Engine(*)\Utilization Percentage",
                    r"\GPU Engine(*engtype_3D*)\Utilization Percentage",
                    r"\GPU Engine(*)\Utilization Percentage",
                ]
                for test_path in test_paths:
                    counter_handle = wintypes.HANDLE()
                    result = pdh_dll.PdhAddCounterW(
                        query_handle, test_path, 0, ctypes.byref(counter_handle)
                    )
                    result_unsigned = result & 0xFFFFFFFF
                    if result_unsigned == 0:
                        print(f"  ✓ Direct path works: {test_path}")
                        pdh_dll.PdhCloseQuery(query_handle)
                        has_paths = True
                        break
                    else:
                        print(f"  ✗ Direct path failed: {test_path} - error {hex(result_unsigned)}")
                if not has_paths:
                    pdh_dll.PdhCloseQuery(query_handle)
        except Exception as e:
            print(f"  ✗ Exception: {e}")
    
    if has_paths:
        test_sampler()
    else:
        print("\n⚠ Cannot test sampler - all methods failed")
        print("\nTroubleshooting suggestions:")
        print("  1. Check if GPU is active (run a game or GPU workload)")
        print("  2. Update GPU drivers to latest version")
        print("  3. Try running as administrator")
        print("  4. Check Windows version (GPU Engine requires Windows 10 1809+)")
        print("  5. Verify PowerShell can access: Get-Counter -ListSet 'GPU Engine'")
    
    print("\n" + "=" * 70)
    print("Diagnostic Complete")
    print("=" * 70)
    return 0

if __name__ == "__main__":
    sys.exit(main())

