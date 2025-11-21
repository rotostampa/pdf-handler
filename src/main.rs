use anyhow::{Context, Result};
use clap::{Parser, ValueEnum};
use hayro::{FontData, FontQuery, InterpreterSettings, RenderSettings, StandardFont};
use hayro_syntax::Pdf;
use krilla::page::PageSettings;
use krilla::Document;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tiny_skia::IntSize;

/// Output format for split pages
#[derive(Debug, Clone, Copy, ValueEnum)]
enum OutputFormat {
    /// Output as PDF files
    Pdf,
    /// Output as PNG images (300 DPI)
    Png,
}

/// Split a PDF file into individual pages
#[derive(Parser, Debug)]
#[command(name = "pdf-handler")]
#[command(about = "Split PDF files into individual pages", long_about = None)]
struct Args {
    /// Input PDF file path
    #[arg(value_name = "INPUT")]
    input: PathBuf,

    /// Output directory for split pages
    #[arg(short, long, default_value = "output")]
    output: PathBuf,

    /// Output format (pdf or png)
    #[arg(short, long, value_enum, default_value = "pdf")]
    format: OutputFormat,
}

fn main() -> Result<()> {
    let args = Args::parse();

    // Read the input PDF file
    let pdf_data = fs::read(&args.input)
        .with_context(|| format!("Failed to read input file: {}", args.input.display()))?;

    // Load the PDF using hayro-syntax
    let pdf_data_arc = Arc::new(pdf_data);
    let pdf = Arc::new(
        Pdf::new(pdf_data_arc).map_err(|e| anyhow::anyhow!("Failed to parse PDF: {:?}", e))?,
    );

    let num_pages = pdf.pages().len();
    println!("PDF has {} page(s)", num_pages);

    // Create output directory if it doesn't exist
    fs::create_dir_all(&args.output).with_context(|| {
        format!(
            "Failed to create output directory: {}",
            args.output.display()
        )
    })?;

    // Split each page
    for (i, page) in pdf.pages().iter().enumerate() {
        let extension = match args.format {
            OutputFormat::Pdf => "pdf",
            OutputFormat::Png => "png",
        };
        let output_filename = format!("{:04}.{}", i + 1, extension);
        let output_path = args.output.join(&output_filename);

        println!("Extracting page {} to {}", i + 1, output_filename);

        // Get page dimensions
        let (width, height) = page.render_dimensions();

        // Extract the page in the specified format
        match args.format {
            OutputFormat::Pdf => extract_page_pdf(&pdf, i, width, height, &output_path)?,
            OutputFormat::Png => extract_page_png(&pdf, i, width, height, &output_path)?,
        }
    }

    println!(
        "Successfully split {} pages to {}",
        num_pages,
        args.output.display()
    );

    Ok(())
}

fn extract_page_pdf(
    pdf: &Arc<Pdf>,
    page_index: usize,
    width: f32,
    height: f32,
    output_path: &Path,
) -> Result<()> {
    // Create a new PDF document
    let mut document = Document::new();

    // Create a page with the same dimensions as the original
    let settings = PageSettings::new(width, height);
    let mut page = document.start_page_with(settings);

    // Get a surface to draw on
    let mut surface = page.surface();

    // Create a krilla PdfDocument from the hayro Pdf Arc
    let krilla_pdf = krilla::pdf::PdfDocument::new(pdf.clone());

    // Draw the specific page onto the surface
    let size = krilla::geom::Size::from_wh(width, height)
        .ok_or_else(|| anyhow::anyhow!("Invalid page dimensions: {}x{}", width, height))?;
    surface.draw_pdf_page(&krilla_pdf, size, page_index);

    // Finish the surface and page
    drop(surface);
    page.finish();

    // Serialize the document to bytes
    let pdf_bytes = document
        .finish()
        .map_err(|e| anyhow::anyhow!("Failed to serialize PDF: {:?}", e))?;

    // Write to file
    fs::write(output_path, pdf_bytes)
        .with_context(|| format!("Failed to write output file: {}", output_path.display()))?;

    Ok(())
}

fn extract_page_png(
    pdf: &Arc<Pdf>,
    page_index: usize,
    width: f32,
    height: f32,
    output_path: &Path,
) -> Result<()> {
    // 300 DPI = 300 pixels per inch, and 1 inch = 72 points
    // So: pixels_per_point = 300 / 72 ≈ 4.167
    const DPI: f32 = 300.0;
    const POINTS_PER_INCH: f32 = 72.0;
    let pixel_per_pt = DPI / POINTS_PER_INCH;

    // Calculate output dimensions in pixels
    let out_width = (width * pixel_per_pt).round() as u32;
    let out_height = (height * pixel_per_pt).round() as u32;

    // Set up font resolver for PDF standard fonts
    let select_standard_font = |_font: StandardFont| -> Option<(FontData, u32)> {
        // For now, return None to use fallback fonts
        // In production, you'd want to embed the fonts like Typst does
        None
    };

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

    // Get the specific page
    let page = pdf
        .pages()
        .get(page_index)
        .ok_or_else(|| anyhow::anyhow!("Page {} not found", page_index + 1))?;

    // Render the page using hayro
    let hayro_pix = hayro::render(page, &interpreter_settings, &render_settings);

    // Convert to tiny-skia Pixmap
    let pixmap = tiny_skia::Pixmap::from_vec(
        hayro_pix.take_u8(),
        IntSize::from_wh(out_width, out_height)
            .ok_or_else(|| anyhow::anyhow!("Invalid output dimensions"))?,
    )
    .ok_or_else(|| anyhow::anyhow!("Failed to create pixmap"))?;

    // Save as PNG using the image crate
    pixmap
        .save_png(output_path)
        .map_err(|e| anyhow::anyhow!("Failed to save PNG: {}", e))?;

    Ok(())
}
