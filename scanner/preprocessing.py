import cv2
import numpy as np
import os
import logging
from typing import Tuple, Optional, List

logger = logging.getLogger("receipt_scanner.preprocessing")

def order_points(pts: np.ndarray) -> np.ndarray:
    """
    Orders a set of 4 points in the format:
    [top-left, top-right, bottom-right, bottom-left]
    """
    rect = np.zeros((4, 2), dtype="float32")
    
    # top-left has the smallest sum, bottom-right has the largest sum
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    
    # top-right has the smallest difference (y - x),
    # bottom-left has the largest difference (y - x)
    diff = np.diff(pts, axis=1).flatten()
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    
    return rect

def four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """
    Applies a perspective transform to obtain a top-down, bird's-eye view of the image.
    """
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    
    # Compute the width of the new image
    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    max_width = max(int(width_a), int(width_b))
    
    # Compute the height of the new image
    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    max_height = max(int(height_a), int(height_b))
    
    # Construct set of destination points for top-down view
    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]
    ], dtype="float32")
    
    # Compute the perspective transform matrix and apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (max_width, max_height))
    
    return warped

class ReceiptPreprocessor:
    def __init__(self, debug_dir: Optional[str] = None, show_steps: bool = False):
        self.debug_dir = debug_dir
        self.show_steps = show_steps
        if self.debug_dir:
            os.makedirs(self.debug_dir, exist_ok=True)

    def _save_debug_image(self, name: str, image: np.ndarray) -> None:
        """Saves intermediate image results to debug_dir if enabled."""
        if self.debug_dir:
            from scanner.utils import write_image
            path = os.path.join(self.debug_dir, f"step_{name}.png")
            write_image(path, image)
            logger.debug(f"Saved debug step image to {path}")
        if self.show_steps:
            cv2.imshow(name, cv2.resize(image, (600, int(600 * image.shape[0] / image.shape[1]))) if image.shape[1] > 600 else image)
            cv2.waitKey(0)
            cv2.destroyWindow(name)

    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        Executes the entire receipt preprocessing pipeline:
        1. Resizes for standard processing.
        2. Detects receipt contour.
        3. Warps perspective (if receipt contour found).
        4. Enhances text quality via adaptive thresholding.
        
        Returns:
            Tuple of (preprocessed_image, was_cropped_bool)
        """
        if image is None:
            raise ValueError("Input image is None")
            
        logger.info("Starting image preprocessing pipeline...")
        orig = image.copy()
        
        # 1. Resize to a manageable width (e.g., 800px) for contour detection
        ratio = image.shape[0] / 800.0
        resized = cv2.resize(image, (int(image.shape[1] / ratio), 800))
        self._save_debug_image("0_original_resized", resized)
        
        # 2. Detect the receipt contour on the resized image
        pts = self.detect_receipt_contour(resized)
        
        # 3. Perspective warp
        if pts is not None:
            logger.info("Receipt contour successfully detected. Performing perspective warp...")
            # Scale the contour points back to original image size
            scaled_pts = pts * ratio
            warped = four_point_transform(orig, scaled_pts)
            self._save_debug_image("4_warped", warped)
            was_cropped = True
        else:
            logger.warning("No clear receipt contour detected. Falling back to whole image.")
            warped = orig
            was_cropped = False
            
        # 4. Convert warped/cropped image to grayscale
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        self._save_debug_image("5_gray", gray)
        
        # 5. Enhance image quality for OCR (Adaptive Thresholding)
        enhanced = self.enhance_for_ocr(gray)
        self._save_debug_image("6_enhanced_thresholded", enhanced)
        
        logger.info("Preprocessing complete.")
        return enhanced, was_cropped

    def detect_receipt_contour(self, resized_img: np.ndarray) -> Optional[np.ndarray]:
        """
        Finds the 4 corners of the receipt in the resized image.
        Returns a 4x2 array of points if found, otherwise None.
        """
        # Grayscale
        gray = cv2.cvtColor(resized_img, cv2.COLOR_BGR2GRAY)
        
        # Noise reduction (Bilateral filter + Gaussian blur)
        # Bilateral filter reduces noise while keeping edges sharp
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        blurred = cv2.GaussianBlur(filtered, (5, 5), 0)
        self._save_debug_image("1_blurred", blurred)
        
        # Edge detection
        edged = cv2.Canny(blurred, 75, 200)
        self._save_debug_image("2_edges", edged)
        
        # Morphological operations (Closing to bridge any small gaps in edges)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, kernel)
        self._save_debug_image("3_closed_edges", closed)
        
        # Find contours
        contours, _ = cv2.findContours(closed.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        logger.debug(f"Found {len(contours)} contours in the image.")
        
        # Sort contours by area in descending order and keep the top ones
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        
        # Loop over the contours to find a candidate quadrilateral
        img_area = resized_img.shape[0] * resized_img.shape[1]
        
        for c in contours:
            # Approximate the contour
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            
            # The contour must have 4 points and its area must be reasonably large
            # (e.g., at least 5% of the total image area)
            area = cv2.contourArea(c)
            if len(approx) == 4 and area > (0.05 * img_area):
                logger.info(f"Detected receipt contour with area fraction: {area / img_area:.2f}")
                # Reshape to a 4x2 array
                return approx.reshape(4, 2)
                
        # If we failed to find a 4-corner contour, let's try a softer threshold or RETR_LIST
        # sometimes receipt edges merge with image edges if RETR_EXTERNAL is used.
        contours_list, _ = cv2.findContours(closed.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours_list = sorted(contours_list, key=cv2.contourArea, reverse=True)[:5]
        for c in contours_list:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.03 * peri, True)
            area = cv2.contourArea(c)
            if len(approx) == 4 and area > (0.05 * img_area):
                logger.info(f"Detected receipt contour via list-based search with area fraction: {area / img_area:.2f}")
                return approx.reshape(4, 2)
                
        return None

    def enhance_for_ocr(self, gray_image: np.ndarray) -> np.ndarray:
        """
        Enhances the image to make text as clear as possible.
        Uses adaptive thresholding to deal with local illumination variations.
        """
        # Clean noise before thresholding
        denoised = cv2.medianBlur(gray_image, 3)
        
        # Apply Gaussian adaptive thresholding
        # block size 21, constant subtraction 10 generally gives great results for text
        thresholded = cv2.adaptiveThreshold(
            denoised, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            21, 10
        )
        
        # Morphological opening to remove minor salt-and-pepper noise from thresholding
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        opened = cv2.morphologyEx(thresholded, cv2.MORPH_OPEN, kernel)
        
        return opened
