"""
Test script for GPU PDH Sampler.
Run this to verify GPU detection is working correctly.

Expected behavior:
- Prints non-zero GPU usage while a 3D game is running
- Prints lower values when idle
- No PDH exceptions in normal use
"""

import sys
import os
import time
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from packages.core.monitor.gpu_pdh_sampler import GpuPdhSampler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

def main():
    print("=" * 60)
    print("GPU PDH Sampler Test")
    print("=" * 60)
    print()
    
    sampler = GpuPdhSampler()
    
    print("Initializing GPU sampler...")
    if not sampler.start():
        print("❌ GPU sampler initialization failed")
        print("   Check logs above for diagnostic information")
        return 1
    
    print("✓ GPU sampler initialized successfully")
    print()
    print("Sampling GPU utilization (press Ctrl+C to stop)...")
    print("Expected: non-zero values during gaming, lower when idle")
    print("-" * 60)
    
    try:
        sample_count = 0
        while True:
            gpu_util = sampler.sample()
            sample_count += 1
            
            if gpu_util is not None:
                bar_length = int(gpu_util / 2)  # Scale to 50 chars
                bar = "█" * bar_length + "░" * (50 - bar_length)
                print(f"[{sample_count:4d}] GPU: {gpu_util:6.2f}% |{bar}|")
            else:
                print(f"[{sample_count:4d}] GPU: N/A (sampling failed)")
            
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print()
        print("-" * 60)
        print("Test stopped by user")
    
    finally:
        sampler.close()
        print("✓ GPU sampler closed")
    
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())

