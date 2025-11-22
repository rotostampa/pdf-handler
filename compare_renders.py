#!/usr/bin/env python3
"""
Compare PDF rendering between PDFium and our Rust CLI.

Usage:
    uv run compare_renders.py <pdf_folder> [--dpi 300] [--output results/]

Requirements:
    - uv (https://github.com/astral-sh/uv)
    - pypdfium2 (installed via uv)
    - Pillow (installed via uv)
    - pixelmatch (for perceptual diffing)
    - Rust CLI built at ./target/release/pdf-handler
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional
import json

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pypdfium2>=4.30.0",
#     "pillow>=10.0.0",
#     "pixelmatch>=0.3.0",
# ]
# ///

try:
    import pypdfium2 as pdfium
    from PIL import Image
    from pixelmatch.contrib.PIL import pixelmatch
except ImportError as e:
    print(f"Error: Missing dependency: {e}")
    print("This script uses inline script metadata for uv.")
    print("Run with: uv run compare_renders.py")
    sys.exit(1)


def render_with_pdfium(
    pdf_path: Path,
    pdf_dir: Path,
    dpi: int = 300,
    target_sizes: Optional[List[tuple]] = None
) -> Optional[dict]:
    """
    Render PDF pages using PDFium.

    Args:
        pdf_path: Path to PDF file
        pdf_dir: Output directory
        dpi: DPI for rendering
        target_sizes: Optional list of (width, height) tuples to match Rust output

    Returns manifest dict if rendering was done, None if skipped.
    """
    manifest_path = pdf_dir / "index.json"

    # Check if already rendered (index.json exists means rendering completed)
    if manifest_path.exists():
        print(f"  PDFium: Skipping {pdf_path.name} (already rendered)")
        with open(manifest_path, 'r') as f:
            return json.load(f)

    print(f"  PDFium: Rendering {pdf_path.name}...")

    # Create output directory - clean up any partial files from previous incomplete runs
    if pdf_dir.exists():
        # Remove any partial PNG files (no index.json means incomplete)
        for png_file in pdf_dir.glob("*.png"):
            png_file.unlink()

    pdf_dir.mkdir(parents=True, exist_ok=True)

    pdf = pdfium.PdfDocument(str(pdf_path))
    pages = []

    for page_num in range(len(pdf)):
        page = pdf[page_num]

        # Render page to bitmap
        bitmap = page.render(
            scale=dpi / 72.0,  # PDFium uses 72 DPI as base
            rotation=0,
        )

        # Convert to PIL Image
        pil_image = bitmap.to_pil()

        # If target sizes provided, resize to match exactly
        if target_sizes and page_num < len(target_sizes):
            target_width, target_height = target_sizes[page_num]
            if (pil_image.width, pil_image.height) != (target_width, target_height):
                pil_image = pil_image.resize((target_width, target_height), Image.LANCZOS)

        # Save as PNG with page number (0-indexed)
        output_path = pdf_dir / f"{page_num}.png"
        pil_image.save(output_path, "PNG")

        pages.append({
            "page": page_num,
            "file": f"{page_num}.png",
            "width": pil_image.width,
            "height": pil_image.height,
        })

    pdf.close()

    # Create manifest
    manifest = {
        "backend": "pdfium",
        "pdf": pdf_path.name,
        "dpi": dpi,
        "total_pages": len(pages),
        "pages": pages,
    }

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return manifest


def render_with_rust_cli(
    pdf_path: Path,
    pdf_dir: Path,
    dpi: int = 300
) -> Optional[dict]:
    """
    Render PDF pages using our Rust CLI.

    Returns manifest dict if rendering was done, None if skipped.
    """
    manifest_path = pdf_dir / "index.json"

    # Check if already rendered (index.json exists means rendering completed)
    if manifest_path.exists():
        print(f"  Rust CLI: Skipping {pdf_path.name} (already rendered)")
        with open(manifest_path, 'r') as f:
            return json.load(f)

    print(f"  Rust CLI: Rendering {pdf_path.name}...")

    cli_path = Path("./target/release/pdf-handler")
    if not cli_path.exists():
        raise FileNotFoundError(
            f"Rust CLI not found at {cli_path}. "
            "Build it with: cargo build --release --features cli"
        )

    # Create output directory - clean up any partial files from previous incomplete runs
    if pdf_dir.exists():
        # Remove any partial PNG files (no index.json means incomplete)
        for png_file in pdf_dir.glob("*.png"):
            png_file.unlink()

    pdf_dir.mkdir(parents=True, exist_ok=True)

    # Run CLI to split PDF into PNGs
    result = subprocess.run(
        [
            str(cli_path),
            str(pdf_path),
            "-f", "png",
            "-o", str(pdf_dir),
            "--dpi", str(dpi),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Rust CLI failed: {result.stderr}")

    # Find generated PNG files (CLI outputs as 0001.png, 0002.png, etc.)
    temp_pngs = sorted(pdf_dir.glob("*.png"))

    # Rename to simple page numbers (0.png, 1.png, etc.)
    pages = []
    for i, temp_path in enumerate(temp_pngs):
        final_path = pdf_dir / f"{i}.png"
        temp_path.rename(final_path)

        # Get image dimensions
        with Image.open(final_path) as img:
            pages.append({
                "page": i,
                "file": f"{i}.png",
                "width": img.width,
                "height": img.height,
            })

    # Create manifest
    manifest = {
        "backend": "rust",
        "pdf": pdf_path.name,
        "dpi": dpi,
        "total_pages": len(pages),
        "pages": pages,
    }

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return manifest


def compare_images_perceptual(
    img1_path: Path,
    img2_path: Path,
    output_path: Path
) -> dict:
    """
    Compare two images using perceptual diff.

    Returns:
        dict with comparison metrics
    """
    img1 = Image.open(img1_path)
    img2 = Image.open(img2_path)

    # Convert to RGBA for consistency
    img1 = img1.convert('RGBA')
    img2 = img2.convert('RGBA')

    # Ensure same dimensions
    if img1.size != img2.size:
        print(f"    WARNING: Size mismatch: {img1.size} vs {img2.size}")
        # Resize to match for comparison
        max_width = max(img1.width, img2.width)
        max_height = max(img1.height, img2.height)

        if img1.size != (max_width, max_height):
            new_img1 = Image.new('RGBA', (max_width, max_height), (255, 255, 255, 0))
            new_img1.paste(img1, (0, 0))
            img1 = new_img1

        if img2.size != (max_width, max_height):
            new_img2 = Image.new('RGBA', (max_width, max_height), (255, 255, 255, 0))
            new_img2.paste(img2, (0, 0))
            img2 = new_img2

    # Create diff image
    diff_img = Image.new('RGBA', img1.size)

    # Use pixelmatch for perceptual comparison
    num_diff_pixels = pixelmatch(img1, img2, diff_img, threshold=0.1)

    # Create side-by-side comparison (expected | diff | actual)
    width = img1.width
    height = img1.height
    comparison = Image.new('RGBA', (width * 3, height))
    comparison.paste(img1, (0, 0))
    comparison.paste(diff_img, (width, 0))
    comparison.paste(img2, (width * 2, 0))

    # Save comparison image
    comparison.save(output_path, "PNG")

    total_pixels = img1.width * img1.height
    diff_percentage = (num_diff_pixels / total_pixels) * 100 if total_pixels > 0 else 0

    return {
        "diff_pixels": num_diff_pixels,
        "total_pixels": total_pixels,
        "diff_percentage": diff_percentage,
        "identical": num_diff_pixels == 0,
        "image_size": [img1.width, img1.height],
        "diff_image": output_path.name,
    }


def compare_renders(
    pdf_name: str,
    rust_manifest: dict,
    pdfium_manifest: dict,
    diff_dir: Path,
) -> Optional[dict]:
    """
    Compare rendered pages between rust and pdfium backends.

    Returns manifest dict if comparison was done, None if skipped.
    """
    manifest_path = diff_dir / "index.json"

    # Check if already compared (index.json exists means comparison completed)
    if manifest_path.exists():
        print(f"  Diff: Skipping {pdf_name} (already compared)")
        with open(manifest_path, 'r') as f:
            return json.load(f)

    print(f"  Diff: Comparing {pdf_name}...")

    # Validate page counts
    rust_pages = rust_manifest["total_pages"]
    pdfium_pages = pdfium_manifest["total_pages"]

    if rust_pages != pdfium_pages:
        raise ValueError(
            f"Page count mismatch: rust={rust_pages}, pdfium={pdfium_pages}"
        )

    # Create diff directory - clean up any partial files from previous incomplete runs
    if diff_dir.exists():
        # Remove any partial PNG files (no index.json means incomplete)
        for png_file in diff_dir.glob("*.png"):
            png_file.unlink()

    diff_dir.mkdir(parents=True, exist_ok=True)

    # Get parent directory to find rust/pdfium folders
    base_dir = diff_dir.parent
    rust_dir = base_dir / "rust"
    pdfium_dir = base_dir / "pdfium"

    # Compare each page
    page_results = []
    total_diff_pixels = 0

    for page_num in range(rust_pages):
        print(f"    Page {page_num + 1}/{rust_pages}...", end=" ", flush=True)

        rust_page_file = rust_dir / f"{page_num}.png"
        pdfium_page_file = pdfium_dir / f"{page_num}.png"
        diff_output = diff_dir / f"{page_num}.png"

        result = compare_images_perceptual(
            pdfium_page_file,  # Expected (reference)
            rust_page_file,    # Actual
            diff_output
        )

        result["page"] = page_num
        page_results.append(result)
        total_diff_pixels += result["diff_pixels"]

        print(f"done ({result['diff_pixels']:,} diff pixels)")


    # Create diff manifest
    manifest = {
        "pdf": pdf_name,
        "rust_manifest": "rust/index.json",
        "pdfium_manifest": "pdfium/index.json",
        "total_pages": rust_pages,
        "pages": page_results,
        "total_diff_pixels": total_diff_pixels,
        "identical": total_diff_pixels == 0,
    }

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return manifest


def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    dpi: int,
) -> dict:
    """Process a single PDF and compare renders."""
    print(f"\nProcessing: {pdf_path.name}")

    # Create PDF-specific directory structure
    pdf_stem = pdf_path.stem
    pdf_base_dir = output_dir / pdf_stem

    rust_dir = pdf_base_dir / "rust"
    pdfium_dir = pdf_base_dir / "pdfium"
    diff_dir = pdf_base_dir / "diff"

    try:
        # Render with Rust first to get exact dimensions
        rust_manifest = render_with_rust_cli(pdf_path, rust_dir, dpi)

        # Extract target sizes from Rust manifest
        target_sizes = [(p["width"], p["height"]) for p in rust_manifest["pages"]]

        # Render with PDFium using Rust dimensions to ensure exact match
        pdfium_manifest = render_with_pdfium(pdf_path, pdfium_dir, dpi, target_sizes)

        # Compare results
        diff_manifest = compare_renders(
            pdf_path.name,
            rust_manifest,
            pdfium_manifest,
            diff_dir,
        )

        return {
            "pdf": pdf_path.name,
            "status": "success",
            "diff_manifest_path": str(diff_dir / "index.json"),
        }

    except Exception as e:
        return {
            "pdf": pdf_path.name,
            "status": "error",
            "error": str(e),
        }


def aggregate_results(output_dir: Path) -> dict:
    """Aggregate results by reading all diff manifests."""
    print("\nAggregating results...")

    results = []

    # Find all diff manifests
    diff_manifests = list(output_dir.glob("*/diff/index.json"))

    for manifest_path in diff_manifests:
        with open(manifest_path, 'r') as f:
            diff_data = json.load(f)
            results.append(diff_data)

    # Calculate summary statistics
    total_pdfs = len(results)
    identical_pdfs = sum(1 for r in results if r.get("identical", False))
    total_diff_pixels = sum(r.get("total_diff_pixels", 0) for r in results)
    total_pages = sum(r.get("total_pages", 0) for r in results)

    aggregate = {
        "total_pdfs": total_pdfs,
        "identical_pdfs": identical_pdfs,
        "match_rate": identical_pdfs / total_pdfs if total_pdfs > 0 else 0,
        "total_pages": total_pages,
        "total_diff_pixels": total_diff_pixels,
        "pdfs": results,
    }

    return aggregate


def main():
    parser = argparse.ArgumentParser(
        description="Compare PDF rendering between PDFium and Rust CLI"
    )
    parser.add_argument(
        "pdf_folder",
        type=Path,
        nargs='?',
        default=Path("test_pdfs"),
        help="Folder containing PDF files to test (default: test_pdfs/)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=72,
        help="DPI for rendering (default: 72)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results"),
        help="Output directory for results (default: results/)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.pdf_folder.exists():
        print(f"Error: PDF folder not found: {args.pdf_folder}")
        sys.exit(1)

    # Find all PDFs
    pdf_files = sorted(args.pdf_folder.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {args.pdf_folder}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF files")
    print(f"Output directory: {args.output}")
    print(f"DPI: {args.dpi}")

    # Process each PDF
    process_results = []
    for pdf_path in pdf_files:
        result = process_pdf(pdf_path, args.output, args.dpi)
        process_results.append(result)

    # Aggregate results from all diff manifests
    aggregate = aggregate_results(args.output)

    # Save aggregate results
    aggregate_file = args.output / "aggregate.json"
    with open(aggregate_file, 'w') as f:
        json.dump(aggregate, f, indent=2)

    # Generate summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    total_pdfs = aggregate["total_pdfs"]
    identical = aggregate["identical_pdfs"]
    match_rate = aggregate["match_rate"]
    total_pages = aggregate["total_pages"]

    print(f"Total PDFs: {total_pdfs}")
    print(f"Total pages: {total_pages}")
    print(f"Identical renders: {identical}/{total_pdfs}")
    print(f"Match rate: {match_rate:.1%}")

    # Print details for non-identical PDFs
    non_identical = [r for r in aggregate["pdfs"] if not r.get("identical", False)]
    if non_identical:
        print(f"\nNon-identical PDFs ({len(non_identical)}):")
        for result in non_identical:
            print(f"  - {result['pdf']}")
            print(f"    Total diff pixels: {result.get('total_diff_pixels', 0):,}")
            print(f"    Pages: {result.get('total_pages', 0)}")

    # Print processing errors
    errors = [r for r in process_results if r["status"] == "error"]
    if errors:
        print(f"\nProcessing Errors ({len(errors)}):")
        for result in errors:
            print(f"  - {result['pdf']}: {result.get('error', 'Unknown error')}")

    print(f"\nAggregate results saved to: {aggregate_file}")

    # Exit code: 0 if all identical, 1 otherwise
    sys.exit(0 if identical == total_pdfs and len(errors) == 0 else 1)


if __name__ == "__main__":
    main()
