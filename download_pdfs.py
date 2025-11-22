#!/usr/bin/env python3
"""
Download PDF files from URLs listed in a file.

Usage:
    uv run download_pdfs.py [--input compare.txt] [--output test_pdfs/] [--limit 100]

Requirements:
    - uv (https://github.com/astral-sh/uv)
    - httpx (installed via uv)
"""

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx>=0.27.0",
# ]
# ///

try:
    import httpx
except ImportError as e:
    print(f"Error: Missing dependency: {e}")
    print("This script uses inline script metadata for uv.")
    print("Run with: uv run download_pdfs.py")
    sys.exit(1)


def hash_content(content: bytes) -> str:
    """Create a SHA256 hash of the content."""
    return hashlib.sha256(content).hexdigest()


def download_pdf(url: str, output_dir: Path) -> tuple[bool, str]:
    """
    Download a PDF from URL, hash its content, and save with hash as filename.

    Returns:
        (success: bool, filename: str)
    """
    tmp_path = None
    try:
        print(f"Downloading: {url[:80]}...")

        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()

            content = response.content

        # Hash the content
        content_hash = hash_content(content)
        final_filename = f"{content_hash}.pdf"
        final_path = output_dir / final_filename

        # Check if file already exists with this hash
        if final_path.exists():
            print(f"  ⊙ Already exists (same content): {final_filename}")
            return True, final_filename

        # Download to temp file first
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pdf') as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        # Move to final location
        tmp_path.rename(final_path)
        tmp_path = None  # Moved successfully

        file_size = final_path.stat().st_size
        print(f"  ✓ Saved as {final_filename} ({file_size:,} bytes)")
        return True, final_filename

    except httpx.HTTPError as e:
        print(f"  ✗ HTTP error: {e}")
        return False, ""
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False, ""
    finally:
        # Clean up temp file if it still exists
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except:
                pass


def main():
    parser = argparse.ArgumentParser(
        description="Download PDF files from a list of URLs"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("compare.txt"),
        help="Input file containing URLs (default: compare.txt)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("test_pdfs"),
        help="Output directory for PDFs (default: test_pdfs/)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of PDFs to download (default: 100)",
    )

    args = parser.parse_args()

    # Validate input file
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    # Read URLs from file
    urls = []
    with open(args.input, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append(line)

    if not urls:
        print(f"No URLs found in {args.input}")
        sys.exit(1)

    # Apply limit
    if len(urls) > args.limit:
        print(f"Found {len(urls)} URLs, limiting to {args.limit}")
        urls = urls[:args.limit]
    else:
        print(f"Found {len(urls)} URLs")

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {args.output}")
    print()

    # Download PDFs
    successful = 0
    failed = 0
    skipped = 0

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}]", end=" ")

        success, filename = download_pdf(url, args.output)

        if success:
            if "Already exists" in filename or filename:
                # Check if it was a skip (already exists)
                if "Already exists" not in str(success):
                    successful += 1
                else:
                    skipped += 1
        else:
            failed += 1

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total URLs: {len(urls)}")
    print(f"Successfully downloaded: {successful}")
    print(f"Already existed (same content hash): {skipped}")
    print(f"Failed: {failed}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
