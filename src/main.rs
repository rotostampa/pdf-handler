use anyhow::{Context, Result};
use clap::{Parser, ValueEnum};
use std::fs;
use std::path::PathBuf;

/// Output format for split pages
#[derive(Debug, Clone, Copy, ValueEnum)]
enum OutputFormat {
    /// Output as PDF files
    Pdf,
    /// Output as PNG images
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

    /// DPI for PNG output (only used with --format png)
    #[arg(long, default_value = "300")]
    dpi: u32,
}

fn main() -> Result<()> {
    let args = Args::parse();

    // Read the input PDF file
    let pdf_data = fs::read(&args.input)
        .with_context(|| format!("Failed to read input file: {}", args.input.display()))?;

    // Convert CLI format to library format
    let lib_format = match args.format {
        OutputFormat::Pdf => pdf_handler::OutputFormat::Pdf,
        OutputFormat::Png => pdf_handler::OutputFormat::Png,
    };

    // Split the PDF using the library
    let results = pdf_handler::split_pdf(&pdf_data, lib_format, args.dpi)
        .map_err(|e| anyhow::anyhow!("{}", e))?;

    println!("PDF has {} page(s)", results.len());

    // Create output directory if it doesn't exist
    fs::create_dir_all(&args.output).with_context(|| {
        format!(
            "Failed to create output directory: {}",
            args.output.display()
        )
    })?;

    // Write each page to disk
    for result in &results {
        // Convert MIME type to file extension
        let extension = match result.format.as_str() {
            "application/pdf" => "pdf",
            "image/png" => "png",
            _ => "bin",
        };

        let output_filename = format!("{:04}.{}", result.page_number, extension);
        let output_path = args.output.join(&output_filename);

        println!(
            "Extracting page {} to {}",
            result.page_number, output_filename
        );

        fs::write(&output_path, &result.data)
            .with_context(|| format!("Failed to write output file: {}", output_path.display()))?;
    }

    println!(
        "Successfully split {} pages to {}",
        results.len(),
        args.output.display()
    );

    Ok(())
}
