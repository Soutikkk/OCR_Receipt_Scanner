import os
import shutil
import logging
from typing import Tuple, Optional, Dict, Any
import numpy as np
import pytesseract

logger = logging.getLogger("receipt_scanner.ocr_engine")

class TesseractNotFoundError(Exception):
    """Exception raised when Tesseract OCR binary is not found on the system."""
    pass

class OcrEngine:
    def __init__(self, tesseract_cmd_path: Optional[str] = None):
        """
        Initializes the OCR Engine.
        Tries to locate Tesseract binary automatically if not provided.
        """
        if tesseract_cmd_path:
            logger.info(f"Setting custom Tesseract path: {tesseract_cmd_path}")
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path
        else:
            self._auto_detect_tesseract()

    def _auto_detect_tesseract(self) -> None:
        """
        Attempts to locate the Tesseract executable.
        If on Windows and not in PATH, checks the default installation path.
        """
        # 1. Check if it's already in the PATH
        in_path = shutil.which("tesseract")
        if in_path:
            logger.debug(f"Tesseract found in system PATH: {in_path}")
            return

        # 2. Check default Windows paths if running on Windows
        if os.name == 'nt':
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")
            ]
            for path in common_paths:
                if os.path.exists(path):
                    logger.info(f"Tesseract found at default Windows path: {path}")
                    pytesseract.pytesseract.tesseract_cmd = path
                    return
        logger.warning("Tesseract not automatically found. Make sure Tesseract is installed and in your PATH.")

    def check_tesseract(self) -> bool:
        """
        Verifies if Tesseract is runnable.
        Raises TesseractNotFoundError if it fails to execute.
        """
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract OCR is available. Version: {version}")
            return True
        except Exception as e:
            msg = (
                "Tesseract OCR executable not found. Please install Tesseract-OCR on your machine. "
                "See README.md for instructions on how to install it on Windows, macOS, and Linux."
            )
            logger.error(msg)
            raise TesseractNotFoundError(msg) from e

    def extract_text_and_confidence(self, image: np.ndarray) -> Tuple[str, float]:
        """
        Extracts raw text and computes the average confidence score from the receipt image.
        
        Args:
            image: Preprocessed CV2 image (grayscale/binary)
            
        Returns:
            Tuple of (raw_extracted_text, average_confidence_score_out_of_100)
        """
        # Ensure Tesseract is runnable
        self.check_tesseract()
        
        logger.info("Performing OCR text extraction...")
        
        # We run image_to_string for general layout-preserved text extraction
        # Adding psm 4 (Assume a single column of text of variable sizes) or 6 (Assume a single uniform block of text)
        # PSM 6 or 4 is generally best for receipts. PSM 4 is great for column alignments.
        custom_config = r'--oem 3 --psm 4'
        
        try:
            raw_text = pytesseract.image_to_string(image, config=custom_config)
            
            # To get word confidence, we run image_to_data
            data: Dict[str, list] = pytesseract.image_to_data(image, config=custom_config, output_type=pytesseract.Output.DICT)
            
            confidences = []
            for conf in data.get('conf', []):
                # Tesseract returns -1 for spaces/layout blocks, which we filter out.
                # Valid word confidence ranges from 0 to 100.
                if conf != -1:
                    confidences.append(float(conf))
            
            avg_confidence = float(np.mean(confidences)) if confidences else 0.0
            
            logger.info(f"OCR finished. Extracted {len(raw_text.splitlines())} lines. Avg confidence: {avg_confidence:.2f}%")
            return raw_text, avg_confidence
            
        except Exception as e:
            logger.error(f"Failed to perform OCR extraction: {e}")
            raise
