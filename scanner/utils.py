import logging
import os
import cv2
import numpy as np
from typing import Optional

def setup_logger(debug_mode: bool = False) -> logging.Logger:
    """
    Sets up and configures the logger.
    If debug_mode is True, sets logging level to DEBUG, otherwise INFO.
    """
    logger = logging.getLogger("receipt_scanner")
    
    # Avoid duplicate handlers if setup is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # Define formatter
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

def read_image(file_path: str) -> Optional[np.ndarray]:
    """
    Reads an image using OpenCV.
    Uses np.fromfile to safely handle Windows/Unicode file paths.
    """
    if not os.path.exists(file_path):
        return None
    try:
        # Read file as bytes to handle Unicode paths properly on Windows
        image_data = np.fromfile(file_path, dtype=np.uint8)
        image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
        return image
    except Exception as e:
        logger = logging.getLogger("receipt_scanner")
        logger.error(f"Error reading image {file_path}: {e}")
        return None

def write_image(file_path: str, image: np.ndarray) -> bool:
    """
    Writes an image to file using OpenCV.
    Uses cv2.imencode and tofile to safely handle Windows/Unicode paths.
    """
    try:
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            
        extension = os.path.splitext(file_path)[1]
        if not extension:
            extension = ".jpg"
            file_path += extension
            
        success, encoded_img = cv2.imencode(extension, image)
        if success:
            encoded_img.tofile(file_path)
            return True
        return False
    except Exception as e:
        logger = logging.getLogger("receipt_scanner")
        logger.error(f"Error writing image to {file_path}: {e}")
        return False
