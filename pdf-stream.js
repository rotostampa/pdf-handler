import init, { PdfSplitter } from "./pkg/pdf_handler.js";

// Initialize the WASM module (call this once before using the library)
export async function initWasm() {
  await init();
}

/**
 * Fetch PDF from URL and return bytes
 * @param {string} url - URL to fetch PDF from
 * @param {Function} onProgress - Optional progress callback: (loaded, total, percentage) => void
 * @returns {Promise<Uint8Array>} PDF bytes
 */
export async function fetchPdfBytes(url, onProgress = null) {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch PDF: HTTP ${response.status}`);
  }

  const contentLength = response.headers.get("content-length");
  const total = contentLength ? parseInt(contentLength, 10) : 0;

  if (!response.body || !onProgress) {
    // No streaming support or no progress callback, just get the array buffer
    const arrayBuffer = await response.arrayBuffer();
    return new Uint8Array(arrayBuffer);
  }

  // Stream with progress updates
  const reader = response.body.getReader();
  const chunks = [];
  let loaded = 0;

  while (true) {
    const { done, value } = await reader.read();

    if (done) break;

    chunks.push(value);
    loaded += value.length;

    if (onProgress && total) {
      const percentage = (loaded / total) * 100;
      onProgress(loaded, total, percentage);
    }
  }

  // Concatenate chunks
  const allChunks = new Uint8Array(loaded);
  let position = 0;
  for (const chunk of chunks) {
    allChunks.set(chunk, position);
    position += chunk.length;
  }

  return allChunks;
}

/**
 * Async generator that yields PDF pages as they are processed
 * @param {Uint8Array|string} source - Either PDF bytes (Uint8Array) or URL (string)
 * @param {string} format - Output format: 'pdf' or 'png'
 * @param {Function} onDownloadProgress - Optional download progress callback (only for URLs): (loaded, total, percentage) => void
 * @yields {Object} Page result with { page_number, data (base64), format }
 */
export async function* splitPdfStream(
  source,
  format = "pdf",
  onDownloadProgress = null,
) {
  let bytes;

  // Fetch PDF if source is a URL
  if (typeof source === "string") {
    bytes = await fetchPdfBytes(source, onDownloadProgress);
  } else if (source instanceof Uint8Array) {
    bytes = source;
  } else {
    throw new Error("Source must be a URL string or Uint8Array");
  }

  // Create splitter from bytes
  const splitter = new PdfSplitter(bytes, format);

  // Yield pages one at a time
  while (splitter.hasNext()) {
    const page = splitter.next();
    yield page;
  }
}

/**
 * Process PDF pages with a callback function as each page is ready
 * @param {Uint8Array|string} source - Either PDF bytes (Uint8Array) or URL (string)
 * @param {string} format - Output format: 'pdf' or 'png'
 * @param {Function} onPage - Callback function called for each page: (page, pageNumber, totalPages) => void
 * @param {Function} onProgress - Optional processing progress callback: (current, total, percentage) => void
 * @param {Function} onDownloadProgress - Optional download progress callback (only for URLs): (loaded, total, percentage) => void
 */
export async function splitPdfWithCallback(
  source,
  format,
  onPage,
  onProgress = null,
  onDownloadProgress = null,
) {
  let bytes;

  // Fetch PDF if source is a URL
  if (typeof source === "string") {
    bytes = await fetchPdfBytes(source, onDownloadProgress);
  } else if (source instanceof Uint8Array) {
    bytes = source;
  } else {
    throw new Error("Source must be a URL string or Uint8Array");
  }

  // Create splitter from bytes
  const splitter = new PdfSplitter(bytes, format);
  const totalPages = splitter.totalPages();

  while (splitter.hasNext()) {
    const currentPage = splitter.currentPage();
    const page = splitter.next();

    await onPage(page, page.page_number, totalPages);

    if (onProgress) {
      const percentage = ((currentPage + 1) / totalPages) * 100;
      onProgress(currentPage + 1, totalPages, percentage);
    }
  }
}

/**
 * Get PDF page count without processing
 * @param {Uint8Array|string} source - Either PDF bytes (Uint8Array) or URL (string)
 * @returns {Promise<number>} Total number of pages
 */
export async function getPdfPageCount(source) {
  let bytes;

  // Fetch PDF if source is a URL
  if (typeof source === "string") {
    bytes = await fetchPdfBytes(source);
  } else if (source instanceof Uint8Array) {
    bytes = source;
  } else {
    throw new Error("Source must be a URL string or Uint8Array");
  }

  const splitter = new PdfSplitter(bytes, "pdf");
  return splitter.totalPages();
}
