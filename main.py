import argparse
import os
import sys
import logging
from typing import List, Dict, Any

from scanner.utils import setup_logger, read_image, write_image
from scanner.preprocessing import ReceiptPreprocessor
from scanner.ocr_engine import OcrEngine, TesseractNotFoundError
from scanner.parser import ReceiptParser
from scanner.exporter import export_to_json, export_to_csv

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Production-Grade OCR Receipt Scanner CLI. Automatically detects, deskews, and extracts receipt text."
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to a receipt image file or a directory containing receipt images."
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="Directory to save OCR results (JSON, CSV) and debug images. Default is 'output/'."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose logging and save intermediate preprocessing images to output/debug/."
    )
    parser.add_argument(
        "--show-steps",
        action="store_true",
        help="Display interactive OpenCV step windows for visual inspection."
    )
    parser.add_argument(
        "--export-format",
        default="json,csv",
        help="Comma-separated formats to export results (e.g., 'json,csv', 'json', or 'csv')."
    )
    parser.add_argument(
        "--tesseract-path",
        default=None,
        help="Optional custom path to the Tesseract OCR binary (e.g., 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe')."
    )
    return parser.parse_args()

def get_image_files(input_path: str) -> List[str]:
    """
    Returns list of image files given a directory or single file path.
    """
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
    
    if os.path.isfile(input_path):
        ext = os.path.splitext(input_path)[1].lower()
        if ext in valid_extensions:
            return [input_path]
        else:
            logger = logging.getLogger("receipt_scanner")
            logger.error(f"File {input_path} does not have a supported image extension: {valid_extensions}")
            return []
            
    if os.path.isdir(input_path):
        files = []
        for entry in os.scandir(input_path):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in valid_extensions:
                    files.append(entry.path)
        return sorted(files)
        
    return []

def main() -> None:
    args = parse_args()
    
    # 1. Setup Logger
    logger = setup_logger(debug_mode=args.debug)
    logger.info("Initializing OCR Receipt Scanner...")
    
    # Normalize export formats
    export_formats = [fmt.strip().lower() for fmt in args.export_format.split(",") if fmt.strip()]
    if not export_formats:
        logger.error("No valid export formats specified. Use --export-format json,csv")
        sys.exit(1)
        
    # 2. Check input path
    input_files = get_image_files(args.input)
    if not input_files:
        logger.error(f"No valid image files found at input location: '{args.input}'")
        sys.exit(1)
        
    logger.info(f"Found {len(input_files)} image(s) to process.")
    
    # 3. Instantiate core components
    try:
        ocr_engine = OcrEngine(tesseract_cmd_path=args.tesseract_path)
        # Perform initial availability check
        ocr_engine.check_tesseract()
    except TesseractNotFoundError as e:
        logger.error(f"Initialization failed: {e}")
        sys.exit(1)
        
    parser = ReceiptParser()
    
    # Ensure output directory exists
    os.makedirs(args.output, exist_ok=True)
    
    batch_results: List[Dict[str, Any]] = []
    
    # 4. Process each image
    for i, file_path in enumerate(input_files, start=1):
        file_name = os.path.basename(file_path)
        base_name_no_ext = os.path.splitext(file_name)[0]
        logger.info(f"[{i}/{len(input_files)}] Processing file: '{file_name}'")
        
        # Determine debug path for this receipt
        receipt_debug_dir = None
        if args.debug:
            receipt_debug_dir = os.path.join(args.output, "debug", base_name_no_ext)
            os.makedirs(receipt_debug_dir, exist_ok=True)
            
        preprocessor = ReceiptPreprocessor(debug_dir=receipt_debug_dir, show_steps=args.show_steps)
        
        # Load image
        img = read_image(file_path)
        if img is None:
            logger.error(f"Could not load image: '{file_name}'. Skipping.")
            continue
            
        try:
            # Preprocess image
            processed_img, was_cropped = preprocessor.preprocess(img)
            
            # Extract text & confidence
            raw_text, confidence = ocr_engine.extract_text_and_confidence(processed_img)
            
            # Optional: save raw text to debug folder if in debug mode
            if args.debug and receipt_debug_dir:
                text_path = os.path.join(receipt_debug_dir, "raw_ocr.txt")
                with open(text_path, "w", encoding="utf-8") as f:
                    f.write(raw_text)
                logger.debug(f"Saved raw OCR text to {text_path}")
                
            # Parse text
            parsed_data = parser.parse(raw_text)
            
            # Enrich parsed data with metadata
            parsed_data["file_name"] = file_name
            parsed_data["confidence_score"] = round(confidence, 2)
            parsed_data["was_cropped"] = was_cropped
            
            batch_results.append(parsed_data)
            
            # Export individual results
            for fmt in export_formats:
                export_name = f"{base_name_no_ext}.{fmt}"
                export_path = os.path.join(args.output, export_name)
                
                if fmt == "json":
                    export_to_json(parsed_data, export_path)
                elif fmt == "csv":
                    export_to_csv(parsed_data, export_path)
                    
            logger.info(f"Successfully processed '{file_name}' - Total: {parsed_data['total']}, Tax: {parsed_data['tax']}, Items Count: {len(parsed_data['line_items'])}")
            
        except Exception as e:
            logger.error(f"Error processing '{file_name}': {e}", exc_info=args.debug)
            continue
            
    # 5. Export combined batch results if more than 1 file processed
    if len(batch_results) > 1:
        logger.info(f"Generating combined batch exports in '{args.output}'...")
        for fmt in export_formats:
            batch_name = f"batch_summary.{fmt}"
            batch_path = os.path.join(args.output, batch_name)
            
            if fmt == "json":
                export_to_json(batch_results, batch_path)
            elif fmt == "csv":
                export_to_csv(batch_results, batch_path)
                
    logger.info("OCR Receipt Scanner task completed.")

if __name__ == "__main__":
    main()
