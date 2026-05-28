import argparse
import os
import sys
import logging
import time
from typing import List, Dict, Any

from scanner.utils import setup_logger, read_image, write_image
from scanner.preprocessing import ReceiptPreprocessor
from scanner.parser import ReceiptParser
from scanner.exporter import export_to_json, export_to_csv
from scanner.ocr_engine import OcrEngine, TesseractNotFoundError


# =========================
# CONSTANTS
# =========================

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

FORMAT_JSON = "json"
FORMAT_CSV = "csv"

SUPPORTED_EXPORTS = {FORMAT_JSON, FORMAT_CSV}


# =========================
# ARGUMENT PARSER
# =========================

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
        help="Optional custom path to the Tesseract OCR binary "
             "(e.g., 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe')."
    )

    return parser.parse_args()


# =========================
# IMAGE FILE COLLECTION
# =========================

def get_image_files(input_path: str) -> List[str]:
    """
    Returns list of image files given a directory or single file path.
    """

    logger = logging.getLogger("receipt_scanner")

    if os.path.isfile(input_path):
        ext = os.path.splitext(input_path)[1].lower()

        if ext in VALID_EXTENSIONS:
            return [input_path]

        logger.error(
            "File %s does not have a supported image extension: %s",
            input_path,
            VALID_EXTENSIONS
        )
        return []

    if os.path.isdir(input_path):
        files = []

        # Recursive directory scan
        for root, _, filenames in os.walk(input_path):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()

                if ext in VALID_EXTENSIONS:
                    files.append(os.path.join(root, filename))

        return sorted(files)

    return []


# =========================
# MAIN
# =========================

def main() -> None:

    args = parse_args()

    # Setup logger
    logger = setup_logger(debug_mode=args.debug)

    logger.info("Initializing OCR Receipt Scanner...")

    # Normalize export formats
    export_formats = [
        fmt.strip().lower()
        for fmt in args.export_format.split(",")
        if fmt.strip()
    ]

    if not export_formats:
        logger.error("No valid export formats specified.")
        sys.exit(1)

    # Validate export formats
    invalid_formats = set(export_formats) - SUPPORTED_EXPORTS

    if invalid_formats:
        logger.error("Unsupported export format(s): %s", invalid_formats)
        sys.exit(1)

    # Check input path
    input_files = get_image_files(args.input)

    if not input_files:
        logger.error(
            "No valid image files found at input location: '%s'",
            args.input
        )
        sys.exit(1)

    logger.info("Found %d image(s) to process.", len(input_files))

    # Instantiate OCR engine
    try:
        ocr_engine = OcrEngine(
            tesseract_cmd_path=args.tesseract_path
        )

        ocr_engine.check_tesseract()

    except TesseractNotFoundError as e:
        logger.error("Initialization failed: %s", e)
        sys.exit(1)

    # Instantiate parser
    parser = ReceiptParser()

    # Ensure output directory exists
    os.makedirs(args.output, exist_ok=True)

    batch_results: List[Dict[str, Any]] = []

    # =========================
    # PROCESS EACH IMAGE
    # =========================

    for i, file_path in enumerate(input_files, start=1):

        start_time = time.time()

        file_name = os.path.basename(file_path)
        base_name_no_ext = os.path.splitext(file_name)[0]

        progress = (i / len(input_files)) * 100

        logger.info(
            "[%d/%d - %.1f%%] Processing file: '%s'",
            i,
            len(input_files),
            progress,
            file_name
        )

        # Debug directory
        receipt_debug_dir = None

        if args.debug:
            receipt_debug_dir = os.path.join(
                args.output,
                "debug",
                base_name_no_ext
            )

            os.makedirs(receipt_debug_dir, exist_ok=True)

        # Create preprocessor
        preprocessor = ReceiptPreprocessor(
            debug_dir=receipt_debug_dir,
            show_steps=args.show_steps
        )

        # Load image
        img = read_image(file_path)

        if img is None:
            logger.error(
                "Could not load image: '%s'. Skipping.",
                file_name
            )
            continue

        try:
            # =========================
            # PREPROCESS IMAGE
            # =========================

            processed_img, was_cropped = preprocessor.preprocess(img)

            # =========================
            # OCR EXTRACTION
            # =========================

            raw_text, confidence = (
                ocr_engine.extract_text_and_confidence(processed_img)
            )

            # Save raw OCR text
            if args.debug and receipt_debug_dir:

                text_path = os.path.join(
                    receipt_debug_dir,
                    "raw_ocr.txt"
                )

                with open(text_path, "w", encoding="utf-8") as f:
                    f.write(raw_text)

                logger.debug(
                    "Saved raw OCR text to %s",
                    text_path
                )

            # =========================
            # PARSE TEXT
            # =========================

            parsed_data = parser.parse(raw_text)

            # Add metadata
            parsed_data["file_name"] = file_name
            parsed_data["confidence_score"] = round(confidence, 2)
            parsed_data["was_cropped"] = was_cropped

            batch_results.append(parsed_data)

            # =========================
            # EXPORT RESULTS
            # =========================

            for fmt in export_formats:

                export_name = f"{base_name_no_ext}.{fmt}"

                export_path = os.path.join(
                    args.output,
                    export_name
                )

                try:

                    if fmt == FORMAT_JSON:
                        export_to_json(parsed_data, export_path)

                    elif fmt == FORMAT_CSV:
                        export_to_csv(parsed_data, export_path)

                except Exception as export_error:
                    logger.error(
                        "Failed to export '%s': %s",
                        export_name,
                        export_error
                    )

            # =========================
            # LOG SUCCESS
            # =========================

            logger.info(
                "Successfully processed '%s' | "
                "Total: %s | Tax: %s | Items Count: %d",
                file_name,
                parsed_data.get("total"),
                parsed_data.get("tax"),
                len(parsed_data.get("line_items", []))
            )

            elapsed = time.time() - start_time

            logger.info(
                "Processing time for '%s': %.2f seconds",
                file_name,
                elapsed
            )

        except Exception as e:

            logger.error(
                "Error processing '%s': %s",
                file_name,
                e,
                exc_info=args.debug
            )

            continue

    # =========================
    # EXPORT BATCH SUMMARY
    # =========================

    if len(batch_results) > 1:

        logger.info(
            "Generating combined batch exports in '%s'...",
            args.output
        )

        for fmt in export_formats:

            batch_name = f"batch_summary.{fmt}"

            batch_path = os.path.join(
                args.output,
                batch_name
            )

            try:

                if fmt == FORMAT_JSON:
                    export_to_json(batch_results, batch_path)

                elif fmt == FORMAT_CSV:
                    export_to_csv(batch_results, batch_path)

            except Exception as export_error:

                logger.error(
                    "Failed batch export '%s': %s",
                    batch_name,
                    export_error
                )

    # =========================
    # FINAL SUMMARY
    # =========================

    logger.info(
        "Processed %d/%d files successfully.",
        len(batch_results),
        len(input_files)
    )

    logger.info("OCR Receipt Scanner task completed.")


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    main()
