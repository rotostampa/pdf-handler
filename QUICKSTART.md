# Quick Start Guide

## Running the Demo

### Prerequisites

1. Install rustup (if not already installed):
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

2. Add the WebAssembly target:
```bash
rustup target add wasm32-unknown-unknown
```

3. Install wasm-pack:
```bash
cargo install wasm-pack
```

### Build and Run

1. **Build the WASM package:**
```bash
wasm-pack build --target web --features wasm --no-default-features
```

This creates a `pkg/` directory with:
- `pdf_handler_bg.wasm` - The WebAssembly binary
- `pdf_handler.js` - JavaScript bindings
- `pdf_handler.d.ts` - TypeScript definitions

2. **Start a local web server:**

You need an HTTP server because WASM modules can't be loaded via `file://` protocol.

Option A - Using Python:
```bash
python3 -m http.server 8000
```

Option B - Using Node.js http-server:
```bash
npx http-server -p 8000
```

Option C - Using Rust simple-http-server:
```bash
cargo install simple-http-server
simple-http-server -p 8000
```

3. **Open the demo:**

Navigate to http://localhost:8000/example.html in your browser.

### Using the Demo

The demo page has two modes:

**Split from URL:**
- Enter a PDF URL (must support CORS)
- Choose format (PDF or PNG)
- Click "Split PDF from URL"

**Split from File:**
- Click "Choose PDF File" and select a local PDF
- Choose format (PDF or PNG)
- Click "Split PDF from File"

Results will appear below with preview thumbnails (for PNG) and download buttons.

### Troubleshooting

**CORS Errors:**
If you get CORS errors when loading PDFs from URLs, the server must have:
```
Access-Control-Allow-Origin: *
```

Try using a CORS proxy or test with local files instead.

**WASM Module Size:**
First load may take a few seconds as the ~3-4 MB WASM module downloads. Subsequent loads will be cached by the browser.

**Build Errors:**
If you get "wasm32-unknown-unknown target not found", make sure you:
1. Installed rustup (not just Homebrew rust)
2. Added the wasm32 target: `rustup target add wasm32-unknown-unknown`

## Quick Test (Without Building WASM)

To test the native CLI immediately:

```bash
# Build CLI
cargo build --release --features cli

# Test with a PDF
./target/release/pdf-handler your-file.pdf -f png -o output/
```

This will split the PDF into PNG images in the `output/` directory.
