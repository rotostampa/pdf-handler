# Building for WebAssembly

## Prerequisites

You need to have the `wasm32-unknown-unknown` target installed. If you're using rustup:

```bash
rustup target add wasm32-unknown-unknown
```

You also need `wasm-pack`:

```bash
cargo install wasm-pack
```

## Building

```bash
wasm-pack build --target web --features wasm --no-default-features
```

This will create a `pkg/` directory with:
- `pdf_handler_bg.wasm` - The WebAssembly binary
- `pdf_handler.js` - JavaScript bindings
- `pdf_handler.d.ts` - TypeScript definitions
- `package.json` - NPM package configuration

## Usage in JavaScript

### Basic Example

```javascript
import init, { split_pdf_from_url, split_pdf_from_bytes } from './pkg/pdf_handler.js';

// Initialize the WASM module
await init();

// Split PDF from URL
const results = await split_pdf_from_url('https://example.com/document.pdf', 'png');

// Results is an array of objects:
// [
//   { page_number: 1, data: "base64-encoded-data", format: "png" },
//   { page_number: 2, data: "base64-encoded-data", format: "png" },
//   ...
// ]

// Convert base64 to blob and download
results.forEach(result => {
    const bytes = atob(result.data);
    const byteArray = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) {
        byteArray[i] = bytes.charCodeAt(i);
    }
    const blob = new Blob([byteArray], { type: `image/${result.format}` });
    const url = URL.createObjectURL(blob);
    
    // Create download link
    const a = document.createElement('a');
    a.href = url;
    a.download = `page-${result.page_number}.${result.format}`;
    a.click();
    URL.revokeObjectURL(url);
});
```

### Split from Bytes

```javascript
import init, { split_pdf_from_bytes } from './pkg/pdf_handler.js';

await init();

// From File input
const fileInput = document.querySelector('input[type="file"]');
fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    const arrayBuffer = await file.arrayBuffer();
    const bytes = new Uint8Array(arrayBuffer);
    
    // Split to PDF pages
    const results = await split_pdf_from_bytes(bytes, 'pdf');
    
    // Process results...
});
```

## API

### `split_pdf_from_url(url: string, format: string): Promise<Array<PageResult>>`

Fetches a PDF from the given URL and splits it into individual pages.

**Parameters:**
- `url`: The URL of the PDF file
- `format`: Output format, either `"pdf"` or `"png"`

**Returns:** Promise that resolves to an array of `PageResult` objects

### `split_pdf_from_bytes(bytes: Uint8Array, format: string): Array<PageResult>`

Splits a PDF from a byte array into individual pages.

**Parameters:**
- `bytes`: The PDF file as a Uint8Array
- `format`: Output format, either `"pdf"` or `"png"`

**Returns:** Array of `PageResult` objects

### `PageResult` Type

```typescript
interface PageResult {
    page_number: number;      // 1-indexed page number
    data: string;             // Base64-encoded page data
    format: string;           // "pdf" or "png"
}
```

## Expected WASM Size

- **Uncompressed**: ~3-4 MB
- **Compressed (gzip)**: ~1-1.5 MB
- **Compressed (brotli)**: ~900 KB - 1.2 MB

The size is relatively large due to:
- Full PDF parsing and rendering engine (hayro)
- PDF writing library (krilla)
- 2D rasterization engine (tiny-skia)
- Image encoding libraries

## Optimization Tips

### Size Optimization

Add to `Cargo.toml`:

```toml
[profile.release]
opt-level = "z"     # Optimize for size
lto = true          # Link-time optimization
codegen-units = 1   # Better optimization
panic = "abort"     # Smaller panic handler
strip = true        # Strip symbols
```

Build with optimization:

```bash
wasm-pack build --target web --features wasm --no-default-features --release
```

### Runtime Optimization

- **Lazy Loading**: Load the WASM module only when needed
- **Caching**: Cache the WASM module in IndexedDB
- **Streaming**: Use streaming compilation for faster startup:

```javascript
const { instance, module } = await WebAssembly.instantiateStreaming(
    fetch('pdf_handler_bg.wasm'),
    imports
);
```

## CORS Considerations

When using `split_pdf_from_url`, the PDF must be served with appropriate CORS headers:

```
Access-Control-Allow-Origin: *
```

For same-origin requests, no CORS configuration is needed.

## Browser Compatibility

- Chrome/Edge: 57+
- Firefox: 52+
- Safari: 11+

All modern browsers support WebAssembly.
