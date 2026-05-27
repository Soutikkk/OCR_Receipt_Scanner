import os
import logging
from PIL import Image, ImageDraw, ImageFont

# Set up simple logging for sample generation
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
logger = logging.getLogger("create_samples")

def get_font(size: int) -> ImageFont.ImageFont:
    """
    Attempts to load a standard system monospaced or sans-serif font.
    Falls back to the default Pillow font if none are found.
    """
    font_names = [
        "consola.ttf", "consolas.ttf", "cour.ttf", "courier.ttf",
        "Arial.ttf", "arial.ttf", "LiberationMono-Regular.ttf",
        "DejaVuSansMono.ttf"
    ]
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except IOError:
            continue
    logger.warning("Could not find standard TrueType fonts. Falling back to default low-resolution font.")
    return ImageFont.load_default()

def draw_receipt_text(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, lines: list) -> None:
    """
    Draws text lines onto the image canvas.
    """
    y_text = 40
    line_spacing = 30
    for line in lines:
        draw.text((30, y_text), line, fill=(0, 0, 0), font=font)
        y_text += line_spacing

def generate_sample_receipt(
    filename: str,
    output_dir: str,
    lines: list,
    rotation_angle: float,
    bg_color: tuple = (40, 40, 45),
    paper_color: tuple = (252, 252, 248)
) -> None:
    """
    Generates a mock receipt image, tilts it, and pastes it onto a background canvas.
    """
    # 1. Create receipt paper canvas (width: 420px, height: 750px)
    receipt_w, receipt_h = 420, 750
    receipt = Image.new("RGB", (receipt_w, receipt_h), paper_color)
    draw = ImageDraw.Draw(receipt)
    
    # 2. Draw text lines on receipt
    # Courier / Consolas size 18 is clear and readable
    font = get_font(18)
    draw_receipt_text(draw, font, lines)
    
    # 3. Create a larger background canvas (width: 900px, height: 1100px)
    bg_w, bg_h = 900, 1100
    background = Image.new("RGB", (bg_w, bg_h), bg_color)
    
    # 4. Rotate the receipt image to simulate skew/perspective
    # We expand the rotated image so corners are not cut off, filling border gaps with background color
    rotated_receipt = receipt.rotate(
        rotation_angle,
        expand=True,
        resample=Image.BICUBIC,
        fillcolor=bg_color
    )
    
    # 5. Paste the rotated receipt onto the center of the background
    rr_w, rr_h = rotated_receipt.size
    offset_x = (bg_w - rr_w) // 2
    offset_y = (bg_h - rr_h) // 2
    background.paste(rotated_receipt, (offset_x, offset_y))
    
    # 6. Save image
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)
    background.save(out_path)
    logger.info(f"Generated test receipt image: '{out_path}' (Rotated {rotation_angle} degrees)")

def main() -> None:
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sample_receipts"))
    
    # Sample 1: Starbucks
    starbucks_lines = [
        "        STARBUCKS COFFEE",
        "         Store #04821",
        "      1200 Pine St, Seattle",
        "        TEL: (206) 555-0199",
        "=================================",
        "Date: 2026-05-27      Time: 09:40",
        "---------------------------------",
        "1 CAFE LATTE                4.50",
        "2 CHOCOLATE CROISSANT       7.00",
        "1 BLUEBERRY MUFFIN          3.50",
        "---------------------------------",
        "SUBTOTAL:                  15.00",
        "TAX (8.00%):                1.20",
        "TOTAL:                     16.20",
        "=================================",
        "    THANK YOU FOR YOUR VISIT",
        "       HAVE A GREAT DAY!"
    ]
    generate_sample_receipt(
        filename="sample_starbucks.png",
        output_dir=output_dir,
        lines=starbucks_lines,
        rotation_angle=-5.0 # Tilted 5 degrees counter-clockwise
    )
    
    # Sample 2: Walmart-style Grocery
    walmart_lines = [
        "          WAL-MART STORE",
        "        Manager: John Doe",
        "      1500 N Main St, Bentonville",
        "         Phone: 479-555-0100",
        "=================================",
        "DATE: 05/27/2026   TIME: 14:32:10",
        "---------------------------------",
        "MILK 1GAL                   3.89",
        "WHOLE WHEAT BREAD           2.49",
        "3 BANANAS @ 0.50            1.50",
        "PAPER TOWELS 6PK            8.99",
        "---------------------------------",
        "SUBTOTAL                   16.87",
        "SALES TAX (6.50%)           1.10",
        "TOTAL                      17.97",
        "CASH TENDERED              20.00",
        "CHANGE DUE                  2.03",
        "=================================",
        "       WE SELL FOR LESS!",
        "     THANK YOU FOR SHOPPING"
    ]
    generate_sample_receipt(
        filename="sample_walmart.png",
        output_dir=output_dir,
        lines=walmart_lines,
        rotation_angle=4.5 # Tilted 4.5 degrees clockwise
    )

if __name__ == "__main__":
    main()
