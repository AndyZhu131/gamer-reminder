"""
[DEPRECATED] GPU PDH Sampler - Reliable GPU utilization reading via Windows Performance Counters.

This module is deprecated and replaced by nvidia_smi_sampler.py.
It is kept for reference but should not be used in new code.

GPU PDH Sampler - Reliable GPU utilization reading via Windows Performance Counters.

Counter Path Used:
  \\GPU Engine(*)\\Utilization Percentage
  (expanded via PdhExpandWildCardPathW to get all instance paths)
  Note: In code, use r"\\GPU Engine" which becomes single backslash in string

Aggregation Logic:
  1. Expand wildcard path using PdhExpandWildCardPathW to get all GPU Engine instances
  2. Filter instances: prefer those containing 'engtype_3D' (most relevant for gaming)
  3. Compute: gpu_3d_usage = max(value) over all engtype_3D instances
  4. Fallback: if no engtype_3D instances found, use max(value) over all instances
  5. Result: single percentage value (0-100) representing peak GPU utilization

This implementation follows the correct PDH pattern:
  1. PdhOpenQueryW - Open PDH query
  2. PdhExpandWildCardPathW - Expand wildcard (PDH_MORE_DATA expected on size query)
     - First call with NULL buffer returns PDH_MORE_DATA + required WCHAR count
     - Allocate buffer and call again, retry loop if still PDH_MORE_DATA
     - Parse MULTI_SZ (null-separated strings) into path list
  3. PdhAddCounterW - Add each expanded counter path to query
  4. Warm-up: PdhCollectQueryData twice with ~1s interval
  5. Sample: PdhCollectQueryData + PdhGetFormattedCounterValue for each counter
  6. Aggregate: max over preferred instances (3D engines)
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes
from typing import Optional

log = logging.getLogger(__name__)

# PDH constants
ERROR_SUCCESS = 0
PDH_FMT_DOUBLE = 0x00002000
PDH_MORE_DATA = 0x800007D2  # 0x800007d2 - expected during buffer size queries
PDH_CSTATUS_VALID_DATA = 0

# Load PDH DLL
try:
    pdh_dll = ctypes.windll.pdh
    _PDH_AVAILABLE = True
except OSError:
    _PDH_AVAILABLE = False
    log.error("PDH DLL not available")


def _check_pdh_result(result: int, func_name: str) -> None:
    """Check PDH result code and raise exception if not success."""
    if result != ERROR_SUCCESS:
        hex_code = hex(result & 0xFFFFFFFF)
        raise RuntimeError(f"PDH {func_name} failed with error code {result} ({hex_code})")


class GpuPdhSampler:
    """
    GPU utilization sampler using Windows PDH API.
    
    Aggregation logic:
    - Prefer instances containing 'engtype_3D' (most relevant for gaming)
    - Compute max(value) over engtype_3D instances
    - If no engtype_3D instances, fallback to max(all instances)
    """
    
    def __init__(self) -> None:
        self._query_handle: Optional[wintypes.HANDLE] = None
        self._counter_handles: list[wintypes.HANDLE] = []
        self._counter_paths: list[str] = []
        self._is_initialized = False
        self._warmup_complete = False
        self._sample_count = 0  # For periodic logging
        
    def start(self) -> bool:
        """
        Initialize GPU PDH sampler.
        Returns True if successful, False otherwise.
        """
        if not _PDH_AVAILABLE:
            log.error("PDH DLL not available")
            return False
        
        try:
            # Step 1: Open PDH query
            query_handle = wintypes.HANDLE()
            result = pdh_dll.PdhOpenQueryW(None, 0, ctypes.byref(query_handle))
            # Use bitwise AND for robust signed/unsigned comparison
            result_unsigned = result & 0xFFFFFFFF
            if result_unsigned != ERROR_SUCCESS:
                hex_code = hex(result_unsigned)
                raise RuntimeError(f"PDH PdhOpenQueryW failed with error code {result} ({hex_code})")
            self._query_handle = query_handle
            
            # Step 2: Enumerate GPU Engine instances and construct specific counter paths
            # Note: Wildcard counters can be added but return PDH_CSTATUS_NO_DATA when sampled.
            # We must enumerate instances and use specific paths like \GPU Engine(pid_1234_engtype_3D_0)\Utilization Percentage
            log.info("Enumerating GPU Engine instances to construct counter paths...")
            expanded_paths = self._enumerate_and_construct_paths()
            
            # If enumeration failed, try wildcard expansion as fallback
            if not expanded_paths:
                log.info("Enumeration failed, trying wildcard expansion...")
                expanded_paths = self._expand_wildcard_path(r"\GPU Engine(*)\Utilization Percentage")
            
            if not expanded_paths:
                log.warning("No GPU Engine counters found after enumeration and expansion")
                log.warning("This usually means:")
                log.warning("  1. GPU Engine instances are not active (no GPU workload running)")
                log.warning("  2. GPU drivers don't expose PDH counters")
                log.warning("  3. GPU may need to be under load for instances to appear")
                self._diagnose_gpu_engine_availability()
                self.close()
                return False
            
            log.info(f"Found {len(expanded_paths)} GPU Engine counter paths")
            for i, path in enumerate(expanded_paths[:10], 1):
                log.info(f"  {i}. {path}")
            if len(expanded_paths) > 10:
                log.info(f"  ... and {len(expanded_paths) - 10} more")
            
            # Step 3: Add all expanded counters to query
            counter_handles = []
            counter_paths = []
            failed_paths = []
            
            log.info(f"Attempting to add {len(expanded_paths)} counters to query...")
            for i, path in enumerate(expanded_paths):
                counter_handle = wintypes.HANDLE()
                result = pdh_dll.PdhAddCounterW(
                    self._query_handle,
                    path,
                    0,
                    ctypes.byref(counter_handle)
                )
                # Use bitwise AND for robust signed/unsigned comparison
                result_unsigned = result & 0xFFFFFFFF
                if result_unsigned == ERROR_SUCCESS:
                    counter_handles.append(counter_handle)
                    counter_paths.append(path)
                    if i < 5:  # Log first 5 successful additions
                        log.debug(f"  ✓ Added counter {i+1}: {path[:80]}...")
                else:
                    failed_paths.append((path, result_unsigned))
                    if len(failed_paths) <= 5:  # Log first 5 failures
                        log.warning(f"  ✗ Failed to add counter {i+1}: error {hex(result_unsigned)}")
                        log.warning(f"     Path: {path[:80]}...")
            
            log.info(f"Successfully added {len(counter_handles)}/{len(expanded_paths)} counters")
            if failed_paths:
                log.warning(f"Failed to add {len(failed_paths)} counters (showing first 5 above)")
            
            if not counter_handles:
                log.error("No GPU counters could be added to query - all paths failed")
                log.error("This usually means:")
                log.error("  1. Counter paths are incorrect")
                log.error("  2. GPU Engine instances are not active")
                log.error("  3. Permissions issue accessing performance counters")
                self.close()
                return False
            
            self._counter_handles = counter_handles
            self._counter_paths = counter_paths
            self._is_initialized = True
            
            # Step 4: Warm-up sampling (two samples ~1s apart)
            log.info("Warming up GPU counters (collecting initial samples)...")
            result1 = pdh_dll.PdhCollectQueryData(self._query_handle)
            result1_unsigned = result1 & 0xFFFFFFFF
            if result1_unsigned != ERROR_SUCCESS:
                log.warning(f"First warm-up PdhCollectQueryData failed: {result1} ({hex(result1_unsigned)})")
            time.sleep(1.0)
            result2 = pdh_dll.PdhCollectQueryData(self._query_handle)
            result2_unsigned = result2 & 0xFFFFFFFF
            if result2_unsigned != ERROR_SUCCESS:
                log.warning(f"Second warm-up PdhCollectQueryData failed: {result2} ({hex(result2_unsigned)})")
            else:
                log.debug("Warm-up completed successfully")
            self._warmup_complete = True
            
            log.info(f"GPU PDH sampler initialized successfully with {len(counter_handles)} counters")
            log.info(f"Counter paths: {len(self._counter_paths)} total, filtering for engtype_3D instances")
            return True
            
        except Exception as e:
            log.error(f"GPU PDH sampler initialization failed: {e}", exc_info=True)
            self.close()
            return False
    
    def _expand_wildcard_path(self, wildcard_path: str) -> list[str]:
        """
        Expand wildcard path using PdhExpandWildCardPathW.
        
        Note: PDH_MORE_DATA is EXPECTED during the size query call - it indicates
        the buffer is too small and tells us the required size. This is normal behavior.
        
        Returns list of expanded counter paths.
        """
        paths = []
        try:
            # First call: get required buffer size (WCHAR count, not bytes)
            # PDH_MORE_DATA is EXPECTED here - it means buffer is too small
            buffer_size = ctypes.c_ulong(0)
            result = pdh_dll.PdhExpandWildCardPathW(
                None,  # Local machine
                wildcard_path,
                None,  # NULL buffer for size query
                ctypes.byref(buffer_size),
                0  # Flags
            )
            
            # PDH_MORE_DATA is expected - it tells us the required size
            # Use bitwise AND to handle signed/unsigned comparison robustly
            result_unsigned = result & 0xFFFFFFFF
            if result_unsigned != PDH_MORE_DATA:
                if result_unsigned == ERROR_SUCCESS:
                    # SUCCESS with 0 size means no matching counters
                    log.warning("PdhExpandWildCardPathW returned SUCCESS but 0 size - no matching counters")
                    log.warning("This usually means:")
                    log.warning("  1. GPU Engine instances are not active (no GPU workload)")
                    log.warning("  2. GPU drivers don't expose PDH counters")
                    log.warning("  3. Counter path format is incorrect")
                    # Try fallback: enumerate and construct paths manually
                    log.info("Attempting fallback: enumerate GPU Engine items directly...")
                    return self._enumerate_and_construct_paths()
                log.warning(f"PdhExpandWildCardPathW size query failed: {result} ({hex(result_unsigned)})")
                # Try fallback
                return self._enumerate_and_construct_paths()
            
            if buffer_size.value == 0:
                log.warning("PdhExpandWildCardPathW returned 0 required size")
                return self._enumerate_and_construct_paths()
            
            log.debug(f"PdhExpandWildCardPathW requires {buffer_size.value} WCHARs (size query returned PDH_MORE_DATA as expected)")
            
            # Loop: allocate buffer and call again, retry if still PDH_MORE_DATA
            max_retries = 5
            for attempt in range(max_retries):
                # Allocate buffer: size is WCHAR count
                expanded_buffer = ctypes.create_unicode_buffer(buffer_size.value)
                
                # Second call: get expanded paths
                result = pdh_dll.PdhExpandWildCardPathW(
                    None,
                    wildcard_path,
                    expanded_buffer,
                    ctypes.byref(buffer_size),
                    0
                )
                
                # Use bitwise AND for robust signed/unsigned comparison
                result_unsigned = result & 0xFFFFFFFF
                if result_unsigned == ERROR_SUCCESS:
                    # Success - parse MULTI_SZ (null-separated strings, double null terminated)
                    # Use wstring_at to get full buffer including embedded NULs
                    paths_str = ctypes.wstring_at(expanded_buffer, buffer_size.value)
                    # Split on '\0' and filter out empty strings (stop at empty)
                    paths = []
                    for p in paths_str.split('\0'):
                        p_stripped = p.strip()
                        if not p_stripped:  # Stop at empty string (end of MULTI_SZ)
                            break
                        paths.append(p_stripped)
                    
                    log.info(f"Expanded wildcard path: {len(paths)} counter paths found")
                    log.debug(f"Required buffer size: {buffer_size.value} WCHARs")
                    log.debug(f"Number of expanded paths: {len(paths)}")
                    
                    # Filter to only 3D engine instances (most relevant for gaming)
                    filtered_paths = self._filter_3d_engine_paths(paths)
                    if filtered_paths:
                        log.info(f"Filtered to {len(filtered_paths)} 3D engine paths (from {len(paths)} total)")
                        if filtered_paths:
                            log.debug(f"First 5 filtered paths:")
                            for i, path in enumerate(filtered_paths[:5], 1):
                                log.debug(f"  {i}. {path}")
                        return filtered_paths
                    else:
                        log.warning("No 3D engine paths found after filtering - using all paths")
                        if paths:
                            log.debug(f"First 10 paths:")
                            for i, path in enumerate(paths[:10], 1):
                                log.debug(f"  {i}. {path}")
                            if len(paths) > 10:
                                log.debug(f"  ... and {len(paths) - 10} more")
                        return paths
                
                elif result_unsigned == PDH_MORE_DATA:
                    # Buffer still too small - retry with larger size
                    log.debug(f"Buffer too small (attempt {attempt + 1}/{max_retries}), retrying with size {buffer_size.value}")
                    if attempt == max_retries - 1:
                        log.error(f"PdhExpandWildCardPathW still returns PDH_MORE_DATA after {max_retries} attempts")
                        return self._enumerate_and_construct_paths()
                    continue
                else:
                    # Other error
                    log.warning(f"PdhExpandWildCardPathW failed: {result} ({hex(result_unsigned)})")
                    return self._enumerate_and_construct_paths()
            
            return []
            
        except Exception as e:
            log.error(f"Wildcard expansion failed: {e}", exc_info=True)
            return self._enumerate_and_construct_paths()
    
    def _filter_3d_engine_paths(self, paths: list[str]) -> list[str]:
        """
        Filter paths to only include 3D engine instances (most relevant for gaming).
        Returns filtered list of paths containing 'engtype_3D' in the instance name.
        """
        filtered = []
        for path in paths:
            # Check if path contains 3D engine instance
            # Path format: \GPU Engine(pid_1234_luid_0x..._engtype_3D_...)\Utilization Percentage
            if 'engtype_3D' in path.lower():
                filtered.append(path)
        return filtered
    
    def _enumerate_and_construct_paths(self) -> list[str]:
        """
        Fallback method: enumerate GPU Engine items and construct paths manually.
        This works even when wildcard expansion fails.
        """
        paths = []
        try:
            log.info("Attempting to enumerate GPU Engine items directly...")
            instance_buffer_size = ctypes.c_ulong(0)
            counter_buffer_size = ctypes.c_ulong(0)
            result = pdh_dll.PdhEnumObjectItemsW(
                None, None, "GPU Engine",
                None, ctypes.byref(instance_buffer_size),
                None, ctypes.byref(counter_buffer_size),
                0x00000002  # PDH_NOEXPANDCOUNTERS
            )
            result_unsigned = result & 0xFFFFFFFF
            
            if result_unsigned == PDH_MORE_DATA:
                if instance_buffer_size.value == 0:
                    log.warning("GPU Engine enumeration returned 0 instance buffer size")
                    log.warning("This usually means:")
                    log.warning("  1. GPU Engine instances only appear when GPU is active (run a game/GPU workload)")
                    log.warning("  2. GPU drivers may not expose PDH counters")
                    log.warning("  3. GPU may not be properly initialized")
                    return []
                
                # Even if counter_buffer_size is 0, we can still construct paths with known counter name
                instance_buffer = ctypes.create_unicode_buffer(instance_buffer_size.value)
                # Allocate counter buffer even if size is 0 (some systems return 0 but counters exist)
                counter_buffer_size_actual = max(counter_buffer_size.value, 1024)  # Minimum buffer
                counter_buffer = ctypes.create_unicode_buffer(counter_buffer_size_actual)
                
                result = pdh_dll.PdhEnumObjectItemsW(
                    None, None, "GPU Engine",
                    instance_buffer, ctypes.byref(instance_buffer_size),
                    counter_buffer, ctypes.byref(ctypes.c_ulong(counter_buffer_size_actual)),
                    0x00000002
                )
                result_unsigned = result & 0xFFFFFFFF
                
                if result_unsigned == ERROR_SUCCESS or result_unsigned == PDH_MORE_DATA:
                    # Parse MULTI_SZ buffers
                    instances_raw = [i.strip() for i in instance_buffer.value.split('\0') if i.strip()]
                    counters_raw = []
                    if counter_buffer_size.value > 0:
                        counters_raw = [c.strip() for c in counter_buffer.value.split('\0') if c.strip()]
                    
                    log.debug(f"Raw buffers: instance_buffer has {len(instances_raw)} items, counter_buffer has {len(counters_raw)} items")
                    if instances_raw:
                        log.debug(f"First instance_buffer item: '{instances_raw[0]}'")
                    if counters_raw:
                        log.debug(f"First counter_buffer item: '{counters_raw[0]}'")
                    
                    # PDH quirk: Sometimes instances and counters are swapped in the buffers
                    # Real instances look like: pid_1234_luid_0x..._engtype_3D
                    # Real counters look like: Utilization Percentage, Dedicated Usage, etc.
                    # Detect and fix if swapped
                    instances = []
                    counters = []
                    
                    # Check instance_buffer - should contain instance names
                    for item in instances_raw:
                        if 'pid_' in item.lower() or 'luid_' in item.lower() or 'engtype_' in item.lower():
                            # This is an instance name (correct)
                            instances.append(item)
                        elif 'utilization' in item.lower() or 'usage' in item.lower() or 'percentage' in item.lower():
                            # This is actually a counter name (buffers are swapped!)
                            counters.append(item)
                        else:
                            # Ambiguous - assume it's an instance
                            instances.append(item)
                    
                    # Check counter_buffer - should contain counter names
                    for item in counters_raw:
                        if 'pid_' in item.lower() or 'luid_' in item.lower() or 'engtype_' in item.lower():
                            # This is actually an instance name (buffers are swapped!)
                            instances.append(item)
                        elif 'utilization' in item.lower() or 'usage' in item.lower() or 'percentage' in item.lower():
                            # This is a counter name (correct)
                            counters.append(item)
                        else:
                            # Ambiguous - assume it's a counter
                            counters.append(item)
                    
                    # Remove duplicates
                    instances = list(dict.fromkeys(instances))
                    counters = list(dict.fromkeys(counters))
                    
                    log.info(f"Enumerated {len(instances)} GPU Engine instances and {len(counters)} counters")
                    if instances:
                        log.debug(f"Sample instances: {instances[:3]}")
                    if counters:
                        log.debug(f"Sample counters: {counters[:3]}")
                    
                    # Find Utilization Percentage counter, or use known name
                    util_counter = None
                    if counters:
                        for counter in counters:
                            if 'utilization' in counter.lower() and 'percentage' in counter.lower():
                                util_counter = counter
                                break
                    
                    # If counter enumeration failed, use known counter name
                    if not util_counter:
                        util_counter = "Utilization Percentage"
                        log.info(f"Using known counter name: {util_counter}")
                    
                    if not instances:
                        log.warning("No GPU Engine instances found - cannot construct counter paths")
                        log.warning("This usually means GPU is idle or no GPU workload is running")
                        return []
                    
                    # Filter instances: prefer 3D engines (most relevant for gaming)
                    # Also filter out instances that look like they're for inactive processes
                    filtered_instances = []
                    for instance in instances:
                        # Prefer 3D engine instances
                        if 'engtype_3D' in instance.lower():
                            filtered_instances.append(instance)
                    
                    # If no 3D engines, use all instances (but this is less ideal)
                    if not filtered_instances:
                        log.warning("No 3D engine instances found, using all instances")
                        filtered_instances = instances
                    else:
                        log.info(f"Filtered to {len(filtered_instances)} 3D engine instances (from {len(instances)} total)")
                    
                    # Construct paths (single backslash at start for local machine)
                    # Note: Do NOT include machine name - use local path format
                    for instance in filtered_instances:
                        # Ensure path starts with single backslash (local machine)
                        path = f"\\GPU Engine({instance})\\{util_counter}"
                        paths.append(path)
                    
                    log.info(f"Constructed {len(paths)} GPU Engine counter paths via enumeration")
                    if paths:
                        log.debug(f"First 5 paths: {paths[:5]}")
                    return paths
                else:
                    log.warning(f"PdhEnumObjectItemsW failed: {result} ({hex(result_unsigned)})")
                    return []
            elif result_unsigned == 0xC0000BB8:  # PDH_CSTATUS_NO_OBJECT
                log.warning("PDH_CSTATUS_NO_OBJECT - GPU Engine object does not exist")
                return []
            else:
                log.warning(f"PdhEnumObjectItemsW size query failed: {result} ({hex(result_unsigned)})")
                return []
        except OSError as e:
            if "access violation" in str(e).lower():
                log.warning("Access violation enumerating GPU Engine - object may not exist or be inaccessible")
            else:
                log.warning(f"Exception enumerating GPU Engine: {e}")
            return []
        except Exception as e:
            log.warning(f"Enumeration fallback failed: {e}")
            return []
    
    def _diagnose_gpu_engine_availability(self) -> None:
        """Diagnostic: enumerate available PDH objects and items."""
        try:
            # Check if GPU Engine object exists
            buffer_size = ctypes.c_ulong(0)
            result = pdh_dll.PdhEnumObjectsW(
                None,
                None,
                None,
                ctypes.byref(buffer_size),
                0x00000001,  # PERF_DETAIL_WIZARD
                False
            )
            
            result_unsigned = result & 0xFFFFFFFF
            if result_unsigned == PDH_MORE_DATA and buffer_size.value > 0:
                buffer = ctypes.create_unicode_buffer(buffer_size.value)
                result = pdh_dll.PdhEnumObjectsW(
                    None,
                    None,
                    buffer,
                    ctypes.byref(buffer_size),
                    0x00000001,
                    False
                )
                result_unsigned = result & 0xFFFFFFFF
                if result_unsigned == ERROR_SUCCESS:
                    objects = [o.strip() for o in buffer.value.split('\0') if o.strip()]
                    has_gpu_engine = "GPU Engine" in objects
                    log.info(f"GPU Engine object exists: {has_gpu_engine}")
                    if not has_gpu_engine:
                        log.warning("GPU Engine not found in PDH objects. Available objects (first 20):")
                        for obj in objects[:20]:
                            log.warning(f"  - {obj}")
            
            # Enumerate GPU Engine items
            instance_buffer_size = ctypes.c_ulong(0)
            counter_buffer_size = ctypes.c_ulong(0)
            result = pdh_dll.PdhEnumObjectItemsW(
                None,
                None,
                "GPU Engine",
                None,
                ctypes.byref(instance_buffer_size),
                None,
                ctypes.byref(counter_buffer_size),
                0x00000002  # PDH_NOEXPANDCOUNTERS
            )
            
            result_unsigned = result & 0xFFFFFFFF
            if result_unsigned == PDH_MORE_DATA:
                instance_buffer = ctypes.create_unicode_buffer(instance_buffer_size.value)
                counter_buffer = ctypes.create_unicode_buffer(counter_buffer_size.value)
                result = pdh_dll.PdhEnumObjectItemsW(
                    None,
                    None,
                    "GPU Engine",
                    instance_buffer,
                    ctypes.byref(instance_buffer_size),
                    counter_buffer,
                    ctypes.byref(counter_buffer_size),
                    0x00000002
                )
                result_unsigned = result & 0xFFFFFFFF
                if result_unsigned == ERROR_SUCCESS:
                    counters = [c.strip() for c in counter_buffer.value.split('\0') if c.strip()]
                    log.info(f"GPU Engine counters available: {len(counters)}")
                    for counter in counters[:10]:
                        log.info(f"  - {counter}")
        except Exception as e:
            log.debug(f"Diagnostic enumeration failed: {e}")
    
    def sample(self) -> Optional[float]:
        """
        Sample GPU utilization.
        Returns percentage (0-100) or None if unavailable.
        
        Aggregation: max(value) over engtype_3D instances, fallback to max(all)
        """
        if not self._is_initialized or not self._query_handle:
            log.debug("Sample called but sampler not initialized or query handle missing")
            return None
        
        try:
            # Collect query data
            result = pdh_dll.PdhCollectQueryData(self._query_handle)
            result_unsigned = result & 0xFFFFFFFF
            if result_unsigned != ERROR_SUCCESS:
                log.warning(f"PdhCollectQueryData failed: {result} ({hex(result_unsigned)})")
                return None
            
            # Read all counter values
            # Note: If wildcard counters were added, each handle returns aggregated value for all matching instances
            values_3d = []  # engtype_3D instances
            values_all = []  # All instances
            failed_counters = 0
            invalid_status_counters = 0
            
            log.debug(f"Sampling {len(self._counter_handles)} GPU counters")
            
            for i, counter_handle in enumerate(self._counter_handles):
                value = wintypes.DOUBLE()
                status = wintypes.DWORD()
                result = pdh_dll.PdhGetFormattedCounterValue(
                    counter_handle,
                    PDH_FMT_DOUBLE,
                    ctypes.byref(status),
                    ctypes.byref(value)
                )
                
                # Use bitwise AND for robust signed/unsigned comparison
                result_unsigned = result & 0xFFFFFFFF
                path = self._counter_paths[i] if i < len(self._counter_paths) else "unknown"
                
                if result_unsigned != ERROR_SUCCESS:
                    failed_counters += 1
                    # Only log first few failures to avoid spam
                    if failed_counters <= 3:
                        log.debug(f"Counter {i} ({path[:60] if path else 'wildcard'}...): PdhGetFormattedCounterValue failed: {result} ({hex(result_unsigned)})")
                    continue
                
                # PDH_CSTATUS_NO_DATA (0xc0000bbd) means counter exists but has no data (inactive process)
                # This is expected for many GPU Engine instances - filter them out silently
                if status.value == 0xc0000bbd:  # PDH_CSTATUS_NO_DATA
                    invalid_status_counters += 1
                    # Don't log these - they're expected for inactive processes
                    continue
                
                if status.value != PDH_CSTATUS_VALID_DATA:
                    invalid_status_counters += 1
                    # Only log first few invalid status to avoid spam
                    if invalid_status_counters <= 3:
                        log.debug(f"Counter {i} ({path[:60] if path else 'wildcard'}...): Invalid status: {status.value} (expected {PDH_CSTATUS_VALID_DATA})")
                    continue
                
                util_value = float(value.value)
                # Clamp to 0-100
                util_value = max(0.0, min(100.0, util_value))
                
                log.debug(f"Counter {i} ({path[:60] if path else 'wildcard'}...): {util_value:.2f}%")
                
                # Categorize by instance type (wildcard paths contain pattern info)
                if 'engtype_3D' in path.lower():
                    values_3d.append(util_value)
                values_all.append(util_value)
            
            # Log diagnostic info if many counters failed
            if failed_counters > 0 or invalid_status_counters > 0:
                log.warning(f"Sample diagnostics: {failed_counters} counters failed, {invalid_status_counters} invalid status, {len(values_all)} valid values")
            
            # Aggregation: prefer 3D engine instances
            if values_3d:
                gpu_util = max(values_3d)
                self._sample_count += 1
                # Log every 10 samples or if value is significant (>5%)
                if self._sample_count % 10 == 0 or gpu_util > 5.0:
                    log.info(f"GPU utilization: {gpu_util:.1f}% (3D engines: {len(values_3d)} instances, max of {len(values_all)} total)")
            elif values_all:
                gpu_util = max(values_all)
                self._sample_count += 1
                if self._sample_count % 10 == 0 or gpu_util > 5.0:
                    log.info(f"GPU utilization: {gpu_util:.1f}% (all engines: {len(values_all)} instances, no 3D)")
            else:
                log.warning(f"No valid GPU counter values returned (checked {len(self._counter_handles)} counters, {failed_counters} failed, {invalid_status_counters} invalid status)")
                return None
            
            return gpu_util
            
        except Exception as e:
            log.error(f"GPU sampling error: {e}", exc_info=True)
            return None
    
    def close(self) -> None:
        """Close PDH query and cleanup resources."""
        if self._query_handle:
            try:
                pdh_dll.PdhCloseQuery(self._query_handle)
            except Exception:
                pass
            self._query_handle = None
        
        self._counter_handles.clear()
        self._counter_paths.clear()
        self._is_initialized = False
        self._warmup_complete = False
    
    def __del__(self) -> None:
        """Cleanup on destruction."""
        self.close()

