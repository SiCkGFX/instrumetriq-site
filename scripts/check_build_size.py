#!/usr/bin/env python3
"""
Check Build Size

Verifies that dist/dataset/index.html is under Cloudflare Pages' 25 MiB limit.
Target: under 1 MiB (ideally under 300 KB).
"""

import sys
from pathlib import Path


def format_size(bytes_size):
    """Format bytes as human-readable string."""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 ** 2:
        return f"{bytes_size / 1024:.2f} KB"
    elif bytes_size < 1024 ** 3:
        return f"{bytes_size / (1024 ** 2):.2f} MB"
    else:
        return f"{bytes_size / (1024 ** 3):.2f} GB"


def main():
    """Check build size."""
    dataset_html = Path("dist/dataset/index.html")
    
    if not dataset_html.exists():
        print("[ERROR] dist/dataset/index.html not found. Run 'npm run build' first.", file=sys.stderr)
        return 1
    
    size_bytes = dataset_html.stat().st_size
    size_mb = size_bytes / (1024 ** 2)
    
    print("=" * 60)
    print("Build Size Check")
    print("=" * 60)
    print()
    print(f"File: {dataset_html}")
    print(f"Size: {format_size(size_bytes)} ({size_bytes:,} bytes)")
    print()
    
    # Check against thresholds
    CLOUDFLARE_LIMIT = 25 * 1024 * 1024  # 25 MiB
    TARGET_SIZE = 1 * 1024 * 1024  # 1 MB
    IDEAL_SIZE = 300 * 1024  # 300 KB
    
    if size_bytes > CLOUDFLARE_LIMIT:
        print(f"❌ FAIL: Exceeds Cloudflare Pages limit ({format_size(CLOUDFLARE_LIMIT)})")
        return 1
    elif size_bytes > TARGET_SIZE:
        print(f"⚠️  WARN: Exceeds target size ({format_size(TARGET_SIZE)})")
        print("   File is under Cloudflare limit but larger than target.")
    elif size_bytes > IDEAL_SIZE:
        print(f"✓ PASS: Under target size ({format_size(TARGET_SIZE)})")
        print(f"  (Ideal: under {format_size(IDEAL_SIZE)})")
    else:
        print(f"✓ PASS: Excellent size! Under {format_size(IDEAL_SIZE)}")
    
    print()
    print(f"Cloudflare limit remaining: {format_size(CLOUDFLARE_LIMIT - size_bytes)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
