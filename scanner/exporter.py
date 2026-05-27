import json
import csv
import os
import logging
from typing import Dict, Any, List, Union

logger = logging.getLogger("receipt_scanner.exporter")

def export_to_json(data: Union[Dict[str, Any], List[Dict[str, Any]]], file_path: str) -> bool:
    """
    Exports the receipt data (dict or list of dicts) to a JSON file.
    """
    try:
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        logger.info(f"Successfully exported data to JSON: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to export data to JSON at {file_path}: {e}")
        return False

def export_to_csv(data: Union[Dict[str, Any], List[Dict[str, Any]]], file_path: str) -> bool:
    """
    Exports receipt data to a CSV file.
    If the data contains line items, it flattens them so that each row is a line item,
    repeating receipt-level metadata (store, date, total, etc.).
    If no items are present, it writes a single row for the receipt summary.
    """
    try:
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            
        # Standardize input to a list of dicts
        receipts = [data] if isinstance(data, dict) else data
        
        # Headers for flat CSV export
        headers = [
            "file_name", "store_name", "date", "time", 
            "subtotal", "tax", "total", "confidence_score", "was_cropped",
            "item_description", "item_quantity", "item_price"
        ]
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for r in receipts:
                items = r.get("line_items", [])
                
                # Base metadata columns
                base_info = [
                    r.get("file_name", ""),
                    r.get("store_name", "Unknown Store"),
                    r.get("date", ""),
                    r.get("time", ""),
                    r.get("subtotal", ""),
                    r.get("tax", ""),
                    r.get("total", ""),
                    r.get("confidence_score", 0.0),
                    r.get("was_cropped", False)
                ]
                
                if items:
                    for item in items:
                        row = base_info + [
                            item.get("description", ""),
                            item.get("quantity", 1),
                            item.get("price", 0.0)
                        ]
                        writer.writerow(row)
                else:
                    # Write summary row only with empty item fields
                    row = base_info + ["", "", ""]
                    writer.writerow(row)
                    
        logger.info(f"Successfully exported data to CSV: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to export data to CSV at {file_path}: {e}")
        return False
