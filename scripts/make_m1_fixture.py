"""Create the deterministic physical M1 acceptance fixture without overwriting."""

import argparse
import hashlib
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--size", type=int, default=100 * 1024 * 1024)
    arguments = parser.parse_args()
    if not 0 <= arguments.size <= 512 * 1024 * 1024:
        parser.error("size must be between zero and 512 MiB")
    block = hashlib.sha256(b"barnCompute-M1").digest() * (1024 * 1024 // 32)
    digest = hashlib.sha256()
    remaining = arguments.size
    with arguments.output.open("xb") as output:
        while remaining:
            data = block[:min(remaining, len(block))]
            output.write(data)
            digest.update(data)
            remaining -= len(data)
    print(f"size={arguments.size} sha256={digest.hexdigest()}")
