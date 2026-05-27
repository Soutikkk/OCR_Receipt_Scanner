import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("receipt_scanner.parser")

class ReceiptParser:
    def __init__(self):
        # Compiled regular expressions for performance and readability
        self.date_patterns = [
            re.compile(r"\b\d{4}[-/.]\d{2}[-/.]\d{2}\b"),  # YYYY-MM-DD, YYYY/MM/DD
            re.compile(r"\b\d{2}[-/.]\d{2}[-/.]\d{4}\b"),  # DD-MM-YYYY, MM/DD/YYYY
            re.compile(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b", re.IGNORECASE), # 12 Jan 2026
            re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b", re.IGNORECASE)  # Jan 12, 2026
        ]
        
        self.time_patterns = [
            re.compile(r"\b\d{1,2}\s*:\s*\d{2}\s*:\s*\d{2}\s*(?:AM|PM|am|pm)?\b"), # HH:MM:SS AM/PM
            re.compile(r"\b\d{1,2}\s*:\s*\d{2}\s*(?:AM|PM|am|pm)\b"),              # HH:MM AM/PM
            re.compile(r"\b\d{2}\s*:\s*\d{2}\b")                                   # 24hr HH:MM
        ]
        
        # Keywords to identify tax and totals
        self.total_keywords = re.compile(
            r"\b(grand\s*total|total\s*due|net\s*total|amount\s*due|total|due|balance|visa|charge|debit)\b",
            re.IGNORECASE
        )
        self.tax_keywords = re.compile(
            r"\b(tax|sales\s*tax|vat|gst|hst|pst|tax\s*amount|iva|vat\s*total)\b",
            re.IGNORECASE
        )
        
        # Decimal number pattern (handles commas as decimals too, e.g., 12,50 or 12.50)
        self.price_pattern = re.compile(r"\b\d+[\.,\s]\s*\d{2}\b")
        
        # Keywords that mean a line is NOT a product item
        self.ignore_line_keywords = re.compile(
            r"\b(subtotal|tax|vat|gst|hst|pst|total|due|change|cash|visa|mastercard|amex|card|tendered|balance|payment|"
            r"discount|savings|saved|items|qty|price|amount|phone|tel|email|address|street|road|st|ave|rd|ln|welcome|"
            r"thank\s+you|merchant|store|id|auth|trans|terminal|host|invoice|receipt|date|time|served|cashier)\b",
            re.IGNORECASE
        )

    def parse(self, text: str) -> Dict[str, Any]:
        """
        Parses raw text from receipt and returns structured fields.
        """
        # Split into lines and strip whitespace
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        parsed_data = {
            "store_name": self.parse_store_name(lines),
            "date": self.parse_date(text),
            "time": self.parse_time(text),
            "tax": self.parse_tax(lines),
            "total": self.parse_total(lines),
            "line_items": self.parse_line_items(lines)
        }
        
        # Calculate subtotal if missing, or sanity check
        self._post_process(parsed_data)
        
        return parsed_data

    def parse_store_name(self, lines: List[str]) -> str:
        """
        Extracts the store name from the first few lines of the receipt.
        """
        # Usually, the store name is on one of the first 4 non-empty lines
        candidate_lines = lines[:5]
        
        # Clean candidates
        for line in candidate_lines:
            # Skip if line contains numbers that look like dates or phone numbers
            if re.search(r"\b\d{4}\b|\b\d{2}[-/.]\d{2}\b", line):
                continue
            # Skip if it contains phone markers, websites, or emails
            if re.search(r"\b(?:tel|phone|\d{3}-\d{3}-\d{4}|www\.|http|\.com|@)\b", line, re.IGNORECASE):
                continue
            # Skip if it contains street address indicators
            if re.search(r"\b(?:street|st|road|rd|ave|avenue|suite|ste|highway|hwy|floor|fl|block|blvd|boulevard|town|city)\b", line, re.IGNORECASE):
                continue
            # Skip if it has mostly special characters
            alphanumeric = re.sub(r"[^A-Za-z0-9\s]", "", line)
            if len(alphanumeric.strip()) < 3:
                continue
            # Skip if it matches ignore keywords (e.g. WELCOME, RECEIPT)
            if re.search(r"\b(?:welcome|receipt|tax\s*invoice|invoice|sales\s*receipt|cash\s*receipt)\b", line, re.IGNORECASE):
                continue
                
            # If we passed all checks, this is likely the store name!
            # Clean it up by stripping non-alphanumeric chars at ends (like *, #, etc.)
            store_name = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", line).strip()
            if len(store_name) >= 3:
                logger.info(f"Parsed store name: '{store_name}'")
                return store_name
                
        return "Unknown Store"

    def parse_date(self, text: str) -> Optional[str]:
        """
        Searches the entire text for date patterns.
        """
        for pattern in self.date_patterns:
            match = pattern.search(text)
            if match:
                date_str = match.group(0).strip()
                # Normalize separator to hyphen for standard output if numeric
                date_str = re.sub(r"[\./]", "-", date_str)
                logger.info(f"Parsed date: '{date_str}'")
                return date_str
        return None

    def parse_time(self, text: str) -> Optional[str]:
        """
        Searches the entire text for time patterns.
        """
        for pattern in self.time_patterns:
            match = pattern.search(text)
            if match:
                time_str = match.group(0).strip()
                # Remove extra spaces around colon
                time_str = re.sub(r"\s*:\s*", ":", time_str)
                logger.info(f"Parsed time: '{time_str}'")
                return time_str
        return None

    def _parse_price_value(self, price_str: str) -> float:
        """
        Converts a matched price string (e.g. '12.50', '12,50', '12 50') to a float.
        """
        # Replace spaces or commas before the last two digits with a dot
        cleaned = re.sub(r"\s+", "", price_str)
        cleaned = re.sub(r"[,]", ".", cleaned)
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def parse_total(self, lines: List[str]) -> Optional[float]:
        """
        Finds the total receipt amount by scanning lines containing 'total' keywords
        and returns the largest logical price found near those keywords.
        """
        candidates: List[float] = []
        
        for line in lines:
            # Check if line contains a total keyword
            if self.total_keywords.search(line):
                # Search for price patterns on the same line
                prices = self.price_pattern.findall(line)
                for price_str in prices:
                    val = self._parse_price_value(price_str)
                    # Exclude 0 and don't match values that look like tax percentages or card digits
                    if val > 0 and val < 100000:
                        candidates.append(val)
                        
        if candidates:
            # Sort candidates. Often, the absolute largest number matched under 'total' keywords
            # is the final total (which exceeds tax and subtotal).
            # Let's filter out candidates that could be card numbers (e.g. ending in 4 digits without dot)
            # but our price regex matches format xx.xx so that's safe.
            total_val = max(candidates)
            logger.info(f"Parsed total: {total_val}")
            return total_val
            
        # Fallback: scan lines in reverse order (bottom of receipt) for any price
        for line in reversed(lines):
            if "total" in line.lower() or "due" in line.lower():
                prices = self.price_pattern.findall(line)
                if prices:
                    total_val = self._parse_price_value(prices[-1])
                    logger.info(f"Fallback parsed total: {total_val}")
                    return total_val
                    
        return None

    def parse_tax(self, lines: List[str]) -> Optional[float]:
        """
        Finds the tax amount by scanning lines containing 'tax/vat/gst' keywords.
        """
        for line in lines:
            if self.tax_keywords.search(line):
                # Avoid picking subtotal lines that happen to contain 'tax' in some context
                if "subtotal" in line.lower() or "sub-total" in line.lower():
                    continue
                prices = self.price_pattern.findall(line)
                if prices:
                    # Usually tax is the first price on the line
                    tax_val = self._parse_price_value(prices[0])
                    if tax_val > 0:
                        logger.info(f"Parsed tax: {tax_val}")
                        return tax_val
        return None

    def parse_line_items(self, lines: List[str]) -> List[Dict[str, Any]]:
        """
        Parses itemized purchases.
        Scans lines looking for: [Description] [Price]
        Filters out header, footer, tax, and total lines.
        """
        items = []
        
        for line in lines:
            # Skip lines that contain ignore keywords (tax, total, change, headers)
            if self.ignore_line_keywords.search(line):
                continue
                
            # A line item must have a price at the end
            # We look for a price pattern at the end of the line
            prices = self.price_pattern.findall(line)
            if not prices:
                continue
                
            # The price is usually the last number on the line
            price_str = prices[-1]
            price_val = self._parse_price_value(price_str)
            if price_val <= 0:
                continue
                
            # The text preceding the price is the item description
            # We split the line by the matched price string
            parts = line.split(price_str)
            description = parts[0].strip()
            
            # Clean description
            # Strip trailing unit price notation like "@ 0.50" or "x 0.50" or "at 0.50"
            description = re.sub(r"\s*(?:@|x|at)\s*\d+[\.,]\d{2}\s*$", "", description, flags=re.IGNORECASE)
            
            # Remove trailing/leading dots, dashes, stars, spaces, or price indicators
            description = re.sub(r"[\s\.\-\*#]+$", "", description)
            description = re.sub(r"^[\s\.\-\*#]+", "", description)
            
            # Skip if description is too short or consists only of numbers/special chars
            if len(description) < 3:
                continue
                
            # Check for quantity pattern within description (e.g. "2 x 1.50" or "2 @ 1.50" or "QTY 2")
            qty = 1
            qty_match = re.search(r"\b(\d+)\s*(?:x|@)\s*\d+[\.,]\d{2}\b", description, re.IGNORECASE)
            if qty_match:
                qty = int(qty_match.group(1))
                # Remove the quantity calculation from description to clean it
                description = description.replace(qty_match.group(0), "").strip()
            else:
                # check for simple leading digit like "2 CHOCOLATE BAR"
                leading_qty = re.match(r"^(\d+)\s+([A-Za-z]{3,}.*)$", description)
                if leading_qty:
                    qty = int(leading_qty.group(1))
                    description = leading_qty.group(2).strip()
            
            # Clean up double spaces or leftover chars in description
            description = re.sub(r"\s+", " ", description)
            
            items.append({
                "description": description,
                "quantity": qty,
                "price": price_val
            })
            
        logger.info(f"Parsed {len(items)} line items.")
        return items

    def _post_process(self, data: Dict[str, Any]) -> None:
        """
        Cleans and normalizes parsed values. Calculates subtotal from items.
        """
        # If line items exist, compute sum of items as a validation subtotal
        items = data.get("line_items", [])
        calculated_subtotal = sum(item["quantity"] * item["price"] for item in items)
        
        # If total is missing but we have items, set total = items total + tax
        if data["total"] is None and calculated_subtotal > 0:
            tax = data["tax"] or 0.0
            data["total"] = round(calculated_subtotal + tax, 2)
            logger.info(f"Calculated missing total from line items: {data['total']}")
        
        # If we have total and items sum, but total is smaller than items sum,
        # it might be that we parsed some false items. But we trust the items list
        # and total as parsed.
        data["subtotal"] = round(calculated_subtotal, 2) if items else None
