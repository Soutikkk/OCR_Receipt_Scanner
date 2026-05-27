# Advanced OCR Receipt Scanner
(Vibecoded)

A production-grade, modular Python application that automates receipt cropping, perspective correction, image enhancement, and field parsing using OpenCV and Tesseract OCR.

---

## Features

- **Automated Receipt Detection & Cropping**: Uses Canny edge detection, morphological closing, and contour approximation to isolate receipt boundaries from complex backgrounds.
- **Perspective Homography Transform**: Projects skewed or angled receipts into a flat, top-down view.
- **OCR Enhancements**: Applies bilateral filters, noise reduction, and Gaussian adaptive thresholding to maximize Tesseract OCR text recognition.
- **Robust Field Parsing**: Implements advanced regular expressions to parse Store Names, Dates, Times, Taxes, Totals, and Itemized Line Items.
- **Flexible Exporter**: Automatically outputs parsed receipt data to detailed CSV and JSON files, supporting single and batch summary runs.
- **Interactive Visual Debugging**: Optional flags display step-by-step images (edges, contours, thresholded text) for tuning parameters.
- **Complete Test Suite**: Standard pytest cases for parsing assertions.

---

## Project Structure

```
OCR_Receipt_Scanner/
├── main.py                     # CLI Entry point & orchestration
├── requirements.txt            # Package dependencies
├── README.md                   # System configuration & usage guide
│
├── scanner/                    # Core modules package
│   ├── __init__.py
│   ├── preprocessing.py        # OpenCV image pipelines & warping
│   ├── ocr_engine.py           # pytesseract wrapper & confidence scores
│   ├── parser.py               # Regex logic for receipt entity extraction
│   ├── exporter.py             # JSON and CSV export handlers
│   └── utils.py                # Logger configuration & robust IO helper
│
├── tests/                      # Testing framework
│   ├── __init__.py
│   └── test_parser.py          # Pytest unit tests for regex validation
│
├── sample_receipts/            # Sample tilted test images
│   └── create_samples.py       # Programmatic PIL receipt image generator
│
└── output/                     # Generated results & intermediate debug images
```

---

## Installation & Setup

### Prerequisites

- **Python 3.11+**
- **Tesseract OCR Engine** (Follow setup instructions below)

### 1. Install Tesseract OCR

You must install the Tesseract system binary to use this scanner.

#### Windows
1. Download the Windows installer from [UB Mannheim Tesseract Repository](https://github.com/UB-Mannheim/tesseract/wiki).
2. Run the installer and complete the setup. By default, it installs to `C:\Program Files\Tesseract-OCR`.
3. The receipt scanner is preconfigured to search this default path automatically. If you install it elsewhere, add the Tesseract directory to your system `PATH` environment variable or specify it via the CLI `--tesseract-path` parameter.

#### macOS
Install Tesseract via Homebrew:
```bash
brew install tesseract
```

#### Linux (Debian/Ubuntu)
Install Tesseract via apt:
```bash
sudo apt update
sudo apt install tesseract-ocr libtesseract-dev
```

### 2. Set Up Python Environment

Clone the repository and install the required Python libraries:
```bash
# Navigate to the workspace
cd "OCR Receipt Scanner"

# Create a virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate      # On Windows
source venv/bin/activate    # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

---

## Quick Start & Usage

### 1. Generate Sample Receipts (Testing Setup)
Create tilted receipt images programmatically to verify your setup:
```bash
python sample_receipts/create_samples.py
```
This generates:
- `sample_receipts/sample_starbucks.png` (skewed -5°)
- `sample_receipts/sample_walmart.png` (skewed +4.5°)

### 2. Run the Scanner

Run the scanner on a single image or a directory:
```bash
# Batch process the sample folder and output JSON & CSV summaries
python main.py --input sample_receipts/ --output output/
```

#### Optional CLI Flags
- `--debug`: Saves step-by-step intermediate images (e.g. gray, edges, warped, thresholded) to `output/debug/<file_name>/` and logs verbose messages.
- `--show-steps`: Interactively displays OpenCV windows of each preprocessing stage (press any key to cycle).
- `--export-format`: Comma-separated list of exports to create. Default is `json,csv`.
- `--tesseract-path`: Explicitly specify the path to your Tesseract binary.
  ```bash
  python main.py --input sample_receipts/ --output output/ --tesseract-path "C:\Program Files\Tesseract-OCR\tesseract.exe"
  ```

---

## Example Output Formats

After processing, JSON and CSV exports are written to the output directory.

### JSON Schema

```json
{
    "store_name": "STARBUCKS COFFEE",
    "date": "2026-05-27",
    "time": "09:40",
    "tax": 1.20,
    "total": 16.20,
    "subtotal": 15.00,
    "line_items": [
        {
            "description": "CAFE LATTE",
            "quantity": 1,
            "price": 4.50
        },
        {
            "description": "CHOCOLATE CROISSANT",
            "quantity": 2,
            "price": 7.00
        },
        {
            "description": "BLUEBERRY MUFFIN",
            "quantity": 1,
            "price": 3.50
        }
    ],
    "file_name": "sample_starbucks.png",
    "confidence_score": 88.07,
    "was_cropped": true
}
```

### CSV Schema (Flattened Table)

The CSV exporter outputs tabular rows representing each item. Metadata is repeated for convenience (ideal for databases or pandas):

| file_name | store_name | date | time | subtotal | tax | total | confidence_score | was_cropped | item_description | item_quantity | item_price |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| sample_starbucks.png | STARBUCKS COFFEE | 2026-05-27 | 09:40 | 15.0 | 1.2 | 16.2 | 88.07 | True | CAFE LATTE | 1 | 4.5 |
| sample_starbucks.png | STARBUCKS COFFEE | 2026-05-27 | 09:40 | 15.0 | 1.2 | 16.2 | 88.07 | True | CHOCOLATE CROISSANT | 2 | 7.0 |
| sample_starbucks.png | STARBUCKS COFFEE | 2026-05-27 | 09:40 | 15.0 | 1.2 | 16.2 | 88.07 | True | BLUEBERRY MUFFIN | 1 | 3.5 |

---

## Unit Testing

To run the unit tests, execute:
```bash
python -m pytest tests/
```

---

## Performance Optimization Suggestions

To scale this scanner for high-throughput or highly skewed environments, consider these performance tweaks:

1. **Resolution Bounds**: Resizing very large camera images (e.g., 4K+) down to a standard 800px width before contour processing significantly reduces CPU latency while preserving homography estimation.
2. **Tesseract Configuration Tuning**: 
   - Restrict characters if receipt values are purely alphanumeric: `--psm 4 -c tessedit_char_whitelist="01234567890.,abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ$%-/ "`
   - Use fast/legacy models (`tessdata_fast`) instead of default `tessdata_best` models to reduce OCR execution times.
3. **Multi-threading/Async Processing**: For batch processing, distribute OCR tasks using Python's `concurrent.futures` since Tesseract binds single-threaded CPU processing per execution.
4. **Hardware Acceleration**: Use OpenCV build configurations linked with CUDA for faster image warping on high-throughput server workloads.

---

## Future Improvements (AI-Based Processing)

Traditional rule-based regex parsers can break when faced with complex layouts, faint fonts, or folding lines. To make this pipeline completely robust and future-proof:

- **AI-Based Key Information Extraction (KIE)**:
  - Transition from regex to LayoutLM-v3 (Layout-Aware Language Models), which analyze both image coordinates (bounding boxes) and raw text to label store names, totals, and line items.
  - Integrate Vision-Language Models (VLMs) like Gemini Flash or GPT-4o-mini using zero-shot prompts (e.g., passing the cropped receipt image directly to extract a structured JSON response).
- **Advanced Deskewing**:
  - Implement U-Net or deep learning-based doc-dewarp architectures to correct non-linear folding and wrinkling on physical paper.
- **Entity Matching**:
  - Link extracted line items to standard SKU/Product databases using fuzzy matching or sentence-transformers.
