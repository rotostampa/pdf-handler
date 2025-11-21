# pdf-handler

A Rust library and CLI tool to split PDF files into individual pages using Typst's internal libraries. Available as both a native binary and WebAssembly module.

## Features

- Split PDF files into individual pages
- **Output formats**: PDF or PNG (300 DPI)
- **Deployment options**: Native CLI or WebAssembly (browser/Node.js)
- Automatically names output files as `0001.pdf`/`0001.png`, `0002.pdf`/`0002.png`, etc.
- Preserves page dimensions and content
- Uses Typst's hayro-syntax, hayro, krilla, and tiny-skia libraries

## Installation

### Native CLI

```bash
cargo build --release --features cli
```

The binary will be available at `target/release/pdf-handler`.

### WebAssembly

See [BUILD_WASM.md](BUILD_WASM.md) for detailed instructions on building for WebAssembly.

## Usage

```bash
# Split a PDF into PDF pages in the default "output" directory
pdf-handler input.pdf

# Split into PNG images at 300 DPI
pdf-handler input.pdf -f png

# Specify a custom output directory
pdf-handler input.pdf -o my-output-folder -f png

# Show help
pdf-handler --help
```

## Examples

### Split to PDF
```bash
$ pdf-handler document.pdf -o split-pages
PDF has 5 page(s)
Extracting page 1 to 0001.pdf
Extracting page 2 to 0002.pdf
Extracting page 3 to 0003.pdf
Extracting page 4 to 0004.pdf
Extracting page 5 to 0005.pdf
Successfully split 5 pages to split-pages
```

### Split to PNG (300 DPI)
```bash
$ pdf-handler document.pdf -o split-images -f png
PDF has 5 page(s)
Extracting page 1 to 0001.png
Extracting page 2 to 0002.png
Extracting page 3 to 0003.png
Extracting page 4 to 0004.png
Extracting page 5 to 0005.png
Successfully split 5 pages to split-images
```

## How It Works

This tool leverages Typst's internal PDF libraries:

### PDF Output Mode
1. **hayro-syntax** - Parses and loads PDF files, providing access to individual pages
2. **krilla** - Creates new PDF documents and embeds pages as XObjects
3. The tool extracts each page by:
   - Loading the source PDF with hayro-syntax
   - Creating a new single-page PDF document for each page
   - Embedding the specific page using krilla's `draw_pdf_page` method
   - Writing the output to disk

### PNG Output Mode
1. **hayro-syntax** - Parses and loads PDF files
2. **hayro** - Interprets and renders PDF pages to raster images
3. **tiny-skia** - CPU-based rasterization engine that creates pixel buffers
4. The tool renders each page by:
   - Loading the source PDF with hayro-syntax
   - Setting up font resolvers and render settings (300 DPI = 4.167 pixels per point)
   - Rendering the page with hayro's interpreter
   - Converting to PNG using tiny-skia's Pixmap
   - Writing the PNG file to disk

**PNG Resolution**: At 300 DPI, a standard A4 page (595×842 points) becomes 2480×3508 pixels, suitable for high-quality printing.

## Command-Line Options

- `<INPUT>` - Input PDF file path (required)
- `-o, --output <OUTPUT>` - Output directory for split pages (default: `output`)
- `-f, --format <FORMAT>` - Output format: `pdf` or `png` (default: `pdf`)

## Limitations

- Does not preserve PDF metadata, bookmarks, or form fields
- Embedded PDFs must have compatible versions
- Password-protected PDFs are not supported
- PNG mode uses fallback fonts (standard PDF fonts not yet embedded)

## Dependencies

- `clap` - CLI argument parsing
- `hayro-syntax` - PDF parsing and page access
- `hayro` - PDF rendering to raster images
- `krilla` - PDF creation with page embedding support
- `tiny-skia` - CPU-based 2D graphics rasterizer
- `image` - Image encoding/decoding
- `anyhow` - Error handling

## License

This project uses Typst's libraries which are licensed under Apache 2.0.
