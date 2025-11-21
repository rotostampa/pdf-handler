use hayro::{FontData, FontQuery, InterpreterSettings, RenderSettings, StandardFont};
use hayro_syntax::Pdf;
use krilla::page::PageSettings;
use krilla::Document;
use std::sync::Arc;
use tiny_skia::IntSize;

#[cfg(feature = "wasm")]
use wasm_bindgen::prelude::*;

#[cfg(feature = "wasm")]
use web_sys::{Request, RequestInit, RequestMode, Response};

/// Output format for split pages
#[derive(Debug, Clone, Copy)]
#[cfg_attr(feature = "wasm", derive(serde::Deserialize))]
pub enum OutputFormat {
    Pdf,
    Png,
}

/// Result of splitting a single page
#[derive(Debug, Clone)]
#[cfg_attr(feature = "wasm", derive(serde::Serialize))]
pub struct PageResult {
    pub page_number: usize,
    #[cfg_attr(feature = "wasm", serde(with = "serde_bytes"))]
    pub data: Vec<u8>,
    pub format: String,
}

#[cfg(feature = "wasm")]
mod serde_bytes {
    use base64::{engine::general_purpose, Engine as _};
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(bytes: &Vec<u8>, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&general_purpose::STANDARD.encode(bytes))
    }

    pub fn deserialize<'de, D>(_deserializer: D) -> Result<Vec<u8>, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s = String::deserialize(_deserializer)?;
        general_purpose::STANDARD
            .decode(s)
            .map_err(serde::de::Error::custom)
    }
}

/// Split a PDF into individual pages
pub fn split_pdf(pdf_data: &[u8], format: OutputFormat) -> Result<Vec<PageResult>, String> {
    // Load the PDF using hayro-syntax
    let pdf_data_arc = Arc::new(pdf_data.to_vec());
    let pdf =
        Arc::new(Pdf::new(pdf_data_arc).map_err(|e| format!("Failed to parse PDF: {:?}", e))?);

    let num_pages = pdf.pages().len();
    let mut results = Vec::with_capacity(num_pages);

    // Split each page
    for (i, page) in pdf.pages().iter().enumerate() {
        let (width, height) = page.render_dimensions();

        let data = match format {
            OutputFormat::Pdf => extract_page_pdf(&pdf, i, width, height)?,
            OutputFormat::Png => extract_page_png(&pdf, i, width, height)?,
        };

        results.push(PageResult {
            page_number: i + 1,
            data,
            format: match format {
                OutputFormat::Pdf => "pdf".to_string(),
                OutputFormat::Png => "png".to_string(),
            },
        });
    }

    Ok(results)
}

fn extract_page_pdf(
    pdf: &Arc<Pdf>,
    page_index: usize,
    width: f32,
    height: f32,
) -> Result<Vec<u8>, String> {
    let mut document = Document::new();
    let settings = PageSettings::new(width, height);
    let mut page = document.start_page_with(settings);
    let mut surface = page.surface();

    let krilla_pdf = krilla::pdf::PdfDocument::new(pdf.clone());
    let size = krilla::geom::Size::from_wh(width, height)
        .ok_or_else(|| format!("Invalid page dimensions: {}x{}", width, height))?;
    surface.draw_pdf_page(&krilla_pdf, size, page_index);

    drop(surface);
    page.finish();

    let pdf_bytes = document
        .finish()
        .map_err(|e| format!("Failed to serialize PDF: {:?}", e))?;

    Ok(pdf_bytes)
}

fn extract_page_png(
    pdf: &Arc<Pdf>,
    page_index: usize,
    width: f32,
    height: f32,
) -> Result<Vec<u8>, String> {
    const DPI: f32 = 300.0;
    const POINTS_PER_INCH: f32 = 72.0;
    let pixel_per_pt = DPI / POINTS_PER_INCH;

    let out_width = (width * pixel_per_pt).round() as u32;
    let out_height = (height * pixel_per_pt).round() as u32;

    let select_standard_font = |_font: StandardFont| -> Option<(FontData, u32)> { None };

    let interpreter_settings = InterpreterSettings {
        font_resolver: Arc::new(move |query| match query {
            FontQuery::Standard(s) => select_standard_font(*s),
            FontQuery::Fallback(f) => select_standard_font(f.pick_standard_font()),
        }),
        warning_sink: Arc::new(|_| {}),
    };

    let render_settings = RenderSettings {
        x_scale: out_width as f32 / width,
        y_scale: out_height as f32 / height,
        width: Some(out_width as u16),
        height: Some(out_height as u16),
    };

    let page = pdf
        .pages()
        .get(page_index)
        .ok_or_else(|| format!("Page {} not found", page_index + 1))?;

    let hayro_pix = hayro::render(page, &interpreter_settings, &render_settings);

    let pixmap = tiny_skia::Pixmap::from_vec(
        hayro_pix.take_u8(),
        IntSize::from_wh(out_width, out_height)
            .ok_or_else(|| "Invalid output dimensions".to_string())?,
    )
    .ok_or_else(|| "Failed to create pixmap".to_string())?;

    pixmap
        .encode_png()
        .map_err(|e| format!("Failed to encode PNG: {}", e))
}

// WASM bindings
#[cfg(feature = "wasm")]
#[wasm_bindgen]
pub async fn split_pdf_from_url(url: String, format: String) -> Result<JsValue, JsValue> {
    // Fetch the PDF from URL
    let pdf_data = fetch_pdf(&url).await?;

    // Parse format
    let output_format = match format.to_lowercase().as_str() {
        "pdf" => OutputFormat::Pdf,
        "png" => OutputFormat::Png,
        _ => return Err(JsValue::from_str("Invalid format. Use 'pdf' or 'png'")),
    };

    // Split the PDF
    let results = split_pdf(&pdf_data, output_format).map_err(|e| JsValue::from_str(&e))?;

    // Convert to JS
    serde_wasm_bindgen::to_value(&results)
        .map_err(|e| JsValue::from_str(&format!("Serialization error: {}", e)))
}

#[cfg(feature = "wasm")]
#[wasm_bindgen]
pub fn split_pdf_from_bytes(bytes: &[u8], format: String) -> Result<JsValue, JsValue> {
    let output_format = match format.to_lowercase().as_str() {
        "pdf" => OutputFormat::Pdf,
        "png" => OutputFormat::Png,
        _ => return Err(JsValue::from_str("Invalid format. Use 'pdf' or 'png'")),
    };

    let results = split_pdf(bytes, output_format).map_err(|e| JsValue::from_str(&e))?;

    serde_wasm_bindgen::to_value(&results)
        .map_err(|e| JsValue::from_str(&format!("Serialization error: {}", e)))
}

#[cfg(feature = "wasm")]
async fn fetch_pdf(url: &str) -> Result<Vec<u8>, JsValue> {
    let mut opts = RequestInit::new();
    opts.method("GET");
    opts.mode(RequestMode::Cors);

    let request = Request::new_with_str_and_init(url, &opts)?;

    let window = web_sys::window().ok_or_else(|| JsValue::from_str("No window object"))?;
    let resp_value =
        wasm_bindgen_futures::JsFuture::from(window.fetch_with_request(&request)).await?;

    let resp: Response = resp_value.dyn_into()?;

    if !resp.ok() {
        return Err(JsValue::from_str(&format!(
            "Failed to fetch PDF: HTTP {}",
            resp.status()
        )));
    }

    let array_buffer = wasm_bindgen_futures::JsFuture::from(resp.array_buffer()?).await?;
    let uint8_array = js_sys::Uint8Array::new(&array_buffer);
    let mut bytes = vec![0; uint8_array.length() as usize];
    uint8_array.copy_to(&mut bytes);

    Ok(bytes)
}
