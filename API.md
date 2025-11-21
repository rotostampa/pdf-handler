# PDF Handler API Documentation

## Overview

PDF Handler provides a streaming API for splitting PDF files into individual pages. The library is built with Rust and compiled to WebAssembly for use in browsers.

## Architecture

- **Rust/WASM**: Core PDF processing (parsing, rendering)
- **JavaScript**: URL fetching, progress tracking, convenience wrappers
- **Memory Model**: Full PDF must be loaded into memory before processing (limitation of hayro-syntax library)

## Core API

### `PdfSplitter` (WASM Class)

The main class for processing PDF pages one at a time.

#### Constructor

```javascript
import init, { PdfSplitter } from './pkg/pdf_handler.js';

await init(); // Initialize WASM module first

const splitter = new PdfSplitter(pdfBytes, format);
```

**Parameters:**
- `pdfBytes: Uint8Array` - The complete PDF file as bytes
- `format: string` - Output format: `'pdf'` or `'png'`

**Throws:** Error if PDF is invalid or format is unsupported

#### Methods

##### `totalPages(): number`
Returns the total number of pages in the PDF.

```javascript
const total = splitter.totalPages();
console.log(`PDF has ${total} pages`);
```

##### `currentPage(): number`
Returns the current page index (0-based).

```javascript
const current = splitter.currentPage();
console.log(`Currently at page ${current + 1}`);
```

##### `hasNext(): boolean`
Check if there are more pages to process.

```javascript
while (splitter.hasNext()) {
  // Process next page
}
```

##### `next(): PageResult`
Process and return the next page.

```javascript
const page = splitter.next();
console.log(`Page ${page.page_number} (${page.format})`);
// page.data contains base64-encoded PDF or PNG
```

**Returns:** `PageResult` object with:
- `page_number: number` - Page number (1-based)
- `data: string` - Base64-encoded page data
- `format: string` - `'pdf'` or `'png'`

## JavaScript Wrapper API (`pdf-stream.js`)

Convenience functions for common use cases.

### `initWasm()`

Initialize the WASM module. Must be called before any other functions.

```javascript
import { initWasm } from './pdf-stream.js';

await initWasm();
```

### `fetchPdfBytes(url, onProgress?)`

Fetch a PDF from a URL and return as bytes.

```javascript
import { fetchPdfBytes } from './pdf-stream.js';

const bytes = await fetchPdfBytes(
  '/document.pdf',
  (loaded, total, percentage) => {
    console.log(`Download: ${percentage.toFixed(1)}%`);
  }
);
```

**Parameters:**
- `url: string` - URL to fetch
- `onProgress?: (loaded, total, percentage) => void` - Optional progress callback

**Returns:** `Promise<Uint8Array>`

### `splitPdfStream(source, format, onDownloadProgress?)`

Async generator that yields pages as they're processed.

```javascript
import { splitPdfStream } from './pdf-stream.js';

for await (const page of splitPdfStream('/document.pdf', 'png')) {
  console.log(`Got page ${page.page_number}`);
  displayPage(page);
}
```

**Parameters:**
- `source: string | Uint8Array` - URL or PDF bytes
- `format: 'pdf' | 'png'` - Output format
- `onDownloadProgress?: (loaded, total, percentage) => void` - Download progress (URL only)

**Yields:** `PageResult` objects

### `splitPdfWithCallback(source, format, onPage, onProgress?, onDownloadProgress?)`

Process PDF with callbacks for each page.

```javascript
import { splitPdfWithCallback } from './pdf-stream.js';

await splitPdfWithCallback(
  '/document.pdf',
  'pdf',
  // Page callback
  async (page, pageNum, total) => {
    console.log(`Page ${pageNum}/${total}`);
    await savePage(page);
  },
  // Processing progress
  (current, total, percentage) => {
    console.log(`Processing: ${percentage.toFixed(1)}%`);
  },
  // Download progress
  (loaded, total, percentage) => {
    console.log(`Download: ${percentage.toFixed(1)}%`);
  }
);
```

**Parameters:**
- `source: string | Uint8Array` - URL or PDF bytes
- `format: 'pdf' | 'png'` - Output format
- `onPage: (page, pageNumber, totalPages) => void | Promise<void>` - Called for each page
- `onProgress?: (current, total, percentage) => void` - Processing progress
- `onDownloadProgress?: (loaded, total, percentage) => void` - Download progress (URL only)

### `getPdfPageCount(source)`

Get the page count without processing pages.

```javascript
import { getPdfPageCount } from './pdf-stream.js';

const count = await getPdfPageCount('/document.pdf');
console.log(`PDF has ${count} pages`);
```

**Parameters:**
- `source: string | Uint8Array` - URL or PDF bytes

**Returns:** `Promise<number>`

## Usage Examples

### Basic Example (Direct API)

```javascript
import init, { PdfSplitter } from './pkg/pdf_handler.js';

// Initialize
await init();

// Fetch PDF
const response = await fetch('/document.pdf');
const arrayBuffer = await response.arrayBuffer();
const pdfBytes = new Uint8Array(arrayBuffer);

// Create splitter
const splitter = new PdfSplitter(pdfBytes, 'png');

// Process pages
while (splitter.hasNext()) {
  const page = splitter.next();
  
  // Decode base64
  const bytes = atob(page.data);
  const array = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) {
    array[i] = bytes.charCodeAt(i);
  }
  
  // Create blob URL
  const blob = new Blob([array], { type: 'image/png' });
  const url = URL.createObjectURL(blob);
  
  // Display
  const img = document.createElement('img');
  img.src = url;
  document.body.appendChild(img);
}
```

### With Progress Tracking

```javascript
import { initWasm, fetchPdfBytes } from './pdf-stream.js';
import { PdfSplitter } from './pkg/pdf_handler.js';

await initWasm();

// Fetch with download progress
const bytes = await fetchPdfBytes('/large.pdf', (loaded, total, pct) => {
  console.log(`Downloading: ${pct.toFixed(1)}%`);
});

// Process with progress
const splitter = new PdfSplitter(bytes, 'pdf');
const total = splitter.totalPages();

while (splitter.hasNext()) {
  const page = splitter.next();
  const percentage = (page.page_number / total) * 100;
  console.log(`Processing: ${percentage.toFixed(1)}%`);
  
  displayPage(page);
  
  // Yield to UI
  await new Promise(resolve => setTimeout(resolve, 0));
}
```

### Using Async Generator

```javascript
import { initWasm, splitPdfStream } from './pdf-stream.js';

await initWasm();

const container = document.getElementById('pages');

for await (const page of splitPdfStream('/document.pdf', 'png')) {
  // Page is immediately available
  const img = createImageFromPage(page);
  container.appendChild(img);
  
  // UI updates automatically
}
```

## Important Notes

### Memory Limitations

- **The entire PDF must be loaded into memory before processing**
- This is a limitation of the hayro-syntax library
- For very large PDFs (100+ MB), consider server-side processing
- The streaming API streams the *output* (pages), not the *input* (PDF loading)

### What is Streamed

✅ **Streamed (one at a time):**
- Page processing
- Page rendering
- Result delivery to JavaScript

❌ **Not Streamed (must be fully loaded):**
- PDF download (though you can track progress)
- PDF parsing (requires complete file)

### Format Differences

**PDF Output:**
- Preserves vector quality
- Smaller file size for text-heavy pages
- Can be viewed in any PDF reader
- Good for downloading/archiving

**PNG Output (300 DPI):**
- Rasterized image
- Larger file size
- Easy to display in browsers
- Good for previews/thumbnails

### Performance Tips

1. **Use `setTimeout(0)` between pages** to keep UI responsive:
   ```javascript
   while (splitter.hasNext()) {
     processPage(splitter.next());
     await new Promise(resolve => setTimeout(resolve, 0));
   }
   ```

2. **Clean up blob URLs** when done:
   ```javascript
   const urls = [];
   // ... create URLs
   // Later:
   urls.forEach(url => URL.revokeObjectURL(url));
   ```

3. **Show download progress** for better UX:
   ```javascript
   const bytes = await fetchPdfBytes(url, (loaded, total, pct) => {
     updateProgressBar(pct);
   });
   ```

## Browser Support

- Modern browsers with WebAssembly support
- Chrome 57+
- Firefox 52+
- Safari 11+
- Edge 79+

## Dependencies

### Rust (WASM)
- `hayro-syntax` - PDF parsing
- `hayro` - PDF rendering
- `krilla` - PDF page extraction
- `tiny-skia` - PNG encoding
- `wasm-bindgen` - JavaScript bindings
- `serde` - Serialization
- `base64` - Binary encoding

### JavaScript
- None! Pure browser APIs (fetch, Uint8Array, etc.)

## Error Handling

```javascript
try {
  const bytes = await fetchPdfBytes('/document.pdf');
  const splitter = new PdfSplitter(bytes, 'pdf');
  
  while (splitter.hasNext()) {
    try {
      const page = splitter.next();
      processPage(page);
    } catch (pageError) {
      console.error(`Failed page ${splitter.currentPage()}:`, pageError);
      // Continue with next page
    }
  }
} catch (error) {
  console.error('Failed to process PDF:', error);
}
```

Common errors:
- `"Failed to parse PDF"` - Invalid or corrupted PDF
- `"Invalid format"` - Format must be 'pdf' or 'png'
- `"Failed to fetch PDF"` - Network error or CORS issue
- `"No more pages"` - Called `next()` when `hasNext()` is false
