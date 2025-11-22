# Testing PDF Rendering Quality

This document explains how to compare our Rust PDF renderer against PDFium (the industry standard used by Chrome/Firefox).

## Quick Start

```bash
# 1. Build the Rust CLI
cargo build --release --features cli

# 2. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Run the comparison
uv run compare_renders.py path/to/pdfs/

# 4. Check results
open results/comparison_results.json
```

## What It Does

The `compare_renders.py` script:

1. **Renders PDFs with PDFium** - Uses pypdfium2 (Python bindings to PDFium)
2. **Renders PDFs with our Rust CLI** - Uses hayro via our CLI
3. **Compares pixel-by-pixel** - Calculates MSE and diff pixel counts
4. **Generates diff images** - Visual comparison (expected | diff | actual)
5. **Creates JSON report** - Detailed results for each PDF

## Output Structure

```
results/
├── pdfium/           # PDFium-rendered pages
│   └── document_pdfium_p0.png
├── rust/             # Rust CLI-rendered pages
│   └── document_rust_p0.png
├── diffs/            # Difference visualizations
│   └── document_diff_p0.png
└── comparison_results.json
```

## Understanding Results

### Perfect Match
```json
{
  "pdf": "simple.pdf",
  "status": "success",
  "identical": true,
  "avg_mse": 0.0,
  "total_diff_pixels": 0
}
```

### Differences Found
```json
{
  "pdf": "complex.pdf",
  "status": "success",
  "identical": false,
  "avg_mse": 12.5,
  "total_diff_pixels": 1543,
  "pages": [
    {
      "page": 0,
      "mse": 12.5,
      "diff_pixels": 1543,
      "identical": false
    }
  ]
}
```

### Metrics Explained

- **MSE (Mean Squared Error)**: Average squared difference per pixel
  - `0.0` = Perfect match
  - `< 10.0` = Visually identical (minor antialiasing differences)
  - `10-100` = Noticeable differences
  - `> 100` = Significant differences

- **diff_pixels**: Number of pixels that differ
  - Depends on image size
  - A 1000x1000 image has 1,000,000 pixels
  - 1000 diff pixels = 0.1% difference

## Advanced Usage

### Custom DPI

```bash
uv run compare_renders.py pdfs/ --dpi 150
```

### Custom Output Directory

```bash
uv run compare_renders.py pdfs/ --output my_results/
```

### Process Single PDF

```bash
# Create temporary folder
mkdir temp_pdf
cp important.pdf temp_pdf/
uv run compare_renders.py temp_pdf/
```

## Known Differences

Our Rust renderer (hayro) may differ from PDFium in:

1. **Font rendering** - Different font rasterization engines
2. **Antialiasing** - Slightly different antialiasing algorithms
3. **Color management** - ICC profile handling differences
4. **Missing features** - hayro doesn't support:
   - Password-protected PDFs
   - Some blend modes
   - Knockout transparency groups

## Interpreting Diff Images

Diff images show three panels side-by-side:

```
[PDFium Reference] | [Red = Different] | [Rust Output]
```

- **Left**: What PDFium rendered (ground truth)
- **Middle**: Red pixels indicate differences
- **Right**: What our Rust CLI rendered

## Troubleshooting

### "Rust CLI not found"
```bash
cargo build --release --features cli
```

### "Module not found" errors
The script uses inline script metadata for dependencies. Make sure you're running with `uv run`:
```bash
uv run compare_renders.py pdfs/
```

### Permission denied
```bash
chmod +x compare_renders.py
```

## CI Integration

Add to your CI pipeline:

```yaml
- name: Test PDF rendering quality
  run: |
    cargo build --release --features cli
    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv run compare_renders.py test_pdfs/
```

The script exits with:
- **0** if all PDFs match perfectly
- **1** if there are differences or errors

## Creating Test Corpus

Good test PDFs should include:

- ✅ Simple text documents
- ✅ Complex fonts (CJK, symbols, ligatures)
- ✅ Images (JPEG, PNG, transparency)
- ✅ Vector graphics (paths, clipping)
- ✅ Color spaces (CMYK, RGB, grayscale, Lab)
- ✅ Rotated pages
- ✅ Various page sizes

You can use PDFs from:
- [PDF.js test suite](https://github.com/mozilla/pdf.js)
- [PDFBox issue tracker](https://issues.apache.org/jira/browse/PDFBOX)
- [PDF corpus](https://pdfa.org/new-large-scale-pdf-corpus-now-publicly-available/)

## Performance Comparison

The script also measures rendering time implicitly. Watch the console output:

```
Processing: document.pdf
  PDFium: Rendering document.pdf...
  Rust CLI: Rendering document.pdf...
  Comparing page 1/10...
```

For detailed performance benchmarking, use:

```bash
time cargo run --release -- input.pdf -f png -o output/
```

vs

```bash
time python -c "import pypdfium2; pdf = pypdfium2.PdfDocument('input.pdf'); ..."
```
