# Streaming API Guide

The PDF Handler provides a streaming API that processes and yields PDF pages one at a time, making it ideal for handling large PDFs efficiently.

## Why Streaming?

Traditional approach (loads all pages in memory):
```javascript
const pages = await split_pdf_from_url(url, 'pdf'); // Wait for ALL pages
// Display pages...
```

Streaming approach (yields pages as ready):
```javascript
const splitter = await PdfSplitter.fromUrl(url, 'pdf');
while (splitter.hasNext()) {
  const page = splitter.next(); // Get page immediately
  displayPage(page); // Show it right away
}
```

**Benefits:**
- Lower memory usage
- Faster time-to-first-page
- Better UX with progress updates
- Handles very large PDFs efficiently

## Basic Usage

### 1. From URL

```javascript
import init, { PdfSplitter } from './pkg/pdf_handler.js';

await init();

// Create splitter
const splitter = await PdfSplitter.fromUrl(
  'https://example.com/document.pdf',
  'pdf' // or 'png'
);

console.log(`Total pages: ${splitter.totalPages()}`);

// Process pages one at a time
while (splitter.hasNext()) {
  const page = splitter.next();
  console.log(`Got page ${page.page_number}`);
  
  // page.data is base64-encoded PDF or PNG
  const bytes = atob(page.data);
  const array = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) {
    array[i] = bytes.charCodeAt(i);
  }
  
  // Use the page data...
}
```

### 2. From Bytes

```javascript
import init, { PdfSplitter } from './pkg/pdf_handler.js';

await init();

// Load PDF as Uint8Array (e.g., from file input)
const fileInput = document.querySelector('input[type="file"]');
const file = fileInput.files[0];
const arrayBuffer = await file.arrayBuffer();
const bytes = new Uint8Array(arrayBuffer);

// Create splitter
const splitter = new PdfSplitter(bytes, 'png');

// Process pages
while (splitter.hasNext()) {
  const page = splitter.next();
  // Use page...
}
```

## Advanced Patterns

### With Progress Updates

```javascript
async function splitWithProgress(url, format, onProgress) {
  const splitter = await PdfSplitter.fromUrl(url, format);
  const total = splitter.totalPages();
  
  while (splitter.hasNext()) {
    const current = splitter.currentPage() + 1;
    const page = splitter.next();
    
    // Update progress
    const percentage = Math.round((current / total) * 100);
    onProgress(current, total, percentage);
    
    // Process page...
    displayPage(page);
    
    // Yield to UI thread
    await new Promise(resolve => setTimeout(resolve, 0));
  }
}

// Usage
await splitWithProgress('/large.pdf', 'pdf', (current, total, pct) => {
  console.log(`Processing ${current}/${total} (${pct}%)`);
});
```

### Display Pages Immediately

```javascript
async function displayPagesAsReady(url, format) {
  const container = document.getElementById('pages');
  const splitter = await PdfSplitter.fromUrl(url, format);
  
  while (splitter.hasNext()) {
    const page = splitter.next();
    
    // Convert base64 to blob URL
    const bytes = atob(page.data);
    const array = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) {
      array[i] = bytes.charCodeAt(i);
    }
    
    const mimeType = format === 'png' ? 'image/png' : 'application/pdf';
    const blob = new Blob([array], { type: mimeType });
    const url = URL.createObjectURL(blob);
    
    // Display immediately
    const link = document.createElement('a');
    link.href = url;
    link.textContent = `Page ${page.page_number}`;
    link.target = '_blank';
    container.appendChild(link);
    
    // Allow UI to update
    await new Promise(resolve => setTimeout(resolve, 0));
  }
}
```

### Using the JavaScript Wrapper (Async Generator)

The `pdf-stream.js` wrapper provides a more idiomatic JavaScript API:

```javascript
import { initWasm, splitPdfStream } from './pdf-stream.js';

await initWasm();

// Use async generator
for await (const page of splitPdfStream('/document.pdf', 'png')) {
  console.log(`Page ${page.page_number} ready`);
  displayPage(page);
}
```

### Callback-Based API

```javascript
import { initWasm, splitPdfWithCallback } from './pdf-stream.js';

await initWasm();

await splitPdfWithCallback(
  '/document.pdf',
  'pdf',
  // onPage callback
  async (page, pageNum, total) => {
    console.log(`Page ${pageNum}/${total}`);
    displayPage(page);
  },
  // onProgress callback (optional)
  (current, total, percentage) => {
    updateProgressBar(percentage);
  }
);
```

## API Reference

### PdfSplitter Class

#### Constructor
```typescript
new PdfSplitter(bytes: Uint8Array, format: 'pdf' | 'png'): PdfSplitter
```

#### Static Methods
```typescript
static async fromUrl(url: string, format: 'pdf' | 'png'): Promise<PdfSplitter>
```

#### Instance Methods
```typescript
totalPages(): number
currentPage(): number  // 0-based index
hasNext(): boolean
next(): PageResult
```

### PageResult Type
```typescript
interface PageResult {
  page_number: number;  // 1-based
  data: string;         // base64-encoded bytes
  format: 'pdf' | 'png';
}
```

## Performance Tips

1. **Use `setTimeout(0)` between pages** to yield to the UI thread:
   ```javascript
   while (splitter.hasNext()) {
     const page = splitter.next();
     displayPage(page);
     await new Promise(resolve => setTimeout(resolve, 0));
   }
   ```

2. **Process only visible pages** for virtual scrolling:
   ```javascript
   // Skip to specific page
   const splitter = new PdfSplitter(bytes, 'png');
   for (let i = 0; i < targetPage; i++) {
     if (splitter.hasNext()) splitter.next();
   }
   // Now process visible range
   ```

3. **Use PNG for thumbnails, PDF for downloads**:
   - PNG is better for displaying in browsers
   - PDF preserves quality and is smaller for text-heavy pages

4. **Clean up blob URLs** when done:
   ```javascript
   const urls = [];
   while (splitter.hasNext()) {
     const url = createBlobUrl(splitter.next());
     urls.push(url);
   }
   
   // Later, when unmounting:
   urls.forEach(url => URL.revokeObjectURL(url));
   ```

## Comparison: Batch vs Streaming

### Batch API (Old)
```javascript
// Waits for ALL pages before returning
const pages = await split_pdf_from_url(url, 'pdf');
// Now display all at once
pages.forEach(displayPage);
```

**Pros:** Simple
**Cons:** High memory usage, long wait time, no progress updates

### Streaming API (New)
```javascript
const splitter = await PdfSplitter.fromUrl(url, 'pdf');
while (splitter.hasNext()) {
  const page = splitter.next();
  displayPage(page); // Immediate feedback
}
```

**Pros:** Low memory, fast time-to-first-page, progress updates
**Cons:** Slightly more code

## Error Handling

```javascript
try {
  const splitter = await PdfSplitter.fromUrl(url, 'pdf');
  
  while (splitter.hasNext()) {
    try {
      const page = splitter.next();
      displayPage(page);
    } catch (pageError) {
      console.error(`Failed to process page ${splitter.currentPage()}:`, pageError);
      // Continue with next page
    }
  }
} catch (error) {
  console.error('Failed to load PDF:', error);
}
```
