import pytest
from scanner.parser import ReceiptParser

@pytest.fixture
def parser():
    return ReceiptParser()

def test_parse_store_name(parser):
    # Standard top lines
    lines1 = [
        "STARBUCKS COFFEE",
        "Store #123456",
        "123 Main St",
        "Tel: 555-1234"
    ]
    assert parser.parse_store_name(lines1) == "STARBUCKS COFFEE"

    # Line with Welcome greeting
    lines2 = [
        "WELCOME TO",
        "TARGET STORE",
        "1500 Broadway",
        "Phone: 212-555-9999"
    ]
    # "WELCOME TO" is skipped, "TARGET STORE" should be picked
    assert parser.parse_store_name(lines2) == "TARGET STORE"

    # Line with special characters
    lines3 = [
        "*** WHOLE FOODS MARKET ***",
        "Date: 2026-05-27"
    ]
    assert parser.parse_store_name(lines3) == "WHOLE FOODS MARKET"

def test_parse_date(parser):
    # ISO Date format
    assert parser.parse_date("Date: 2026-05-27 Time: 09:40") == "2026-05-27"
    
    # Slash Date format (normalized to hyphens)
    assert parser.parse_date("05/27/2026") == "05-27-2026"
    
    # Dot Date format (normalized to hyphens)
    assert parser.parse_date("27.05.2026") == "27-05-2026"
    
    # Month Name Date format
    assert parser.parse_date("12 Jan 2026") == "12 Jan 2026"
    assert parser.parse_date("January 12, 2026") == "January 12, 2026"
    
    # No date in text
    assert parser.parse_date("No date here, just text 12345") is None

def test_parse_time(parser):
    # HH:MM:SS format
    assert parser.parse_time("TIME: 14:32:10") == "14:32:10"
    
    # HH:MM AM/PM format
    assert parser.parse_time("09:40 AM") == "09:40 AM"
    
    # Simple HH:MM 24hr format
    assert parser.parse_time("Time: 09:40") == "09:40"
    
    # No time in text
    assert parser.parse_time("No time here 12-34-56") is None

def test_parse_total(parser):
    # Simple TOTAL line
    lines1 = [
        "SUBTOTAL 15.00",
        "TAX 1.20",
        "TOTAL 16.20"
    ]
    assert parser.parse_total(lines1) == 16.20

    # GRAND TOTAL with comma decimal separator
    lines2 = [
        "NET TOTAL: 12,50",
        "GRAND TOTAL: 13,99",
        "CASH 20.00"
    ]
    assert parser.parse_total(lines2) == 13.99

    # Fallback to bottom of receipt
    lines3 = [
        "SOME PRODUCT 5.00",
        "TOTAL DUE 5.00"
    ]
    assert parser.parse_total(lines3) == 5.00

def test_parse_tax(parser):
    lines1 = [
        "SUBTOTAL 15.00",
        "TAX (8%): 1.20",
        "TOTAL 16.20"
    ]
    assert parser.parse_tax(lines1) == 1.20

    lines2 = [
        "SALES TAX: 0,99",
        "TOTAL: 10.99"
    ]
    assert parser.parse_tax(lines2) == 0.99

def test_parse_line_items(parser):
    lines = [
        "STARBUCKS COFFEE",
        "Date: 2026-05-27",
        "---------------------------------",
        "1 CAFE LATTE                4.50",
        "2 CHOCOLATE CROISSANT       7.00",
        "3 BANANAS @ 0.50            1.50",
        "PAPER TOWELS                8.99",
        "---------------------------------",
        "SUBTOTAL:                  21.99",
        "TAX:                        1.50",
        "TOTAL:                     23.49"
    ]
    items = parser.parse_line_items(lines)
    
    assert len(items) == 4
    
    # Verify Item 1
    assert items[0]["description"] == "CAFE LATTE"
    assert items[0]["quantity"] == 1
    assert items[0]["price"] == 4.50
    
    # Verify Item 2
    assert items[1]["description"] == "CHOCOLATE CROISSANT"
    assert items[1]["quantity"] == 2
    assert items[1]["price"] == 7.00
    
    # Verify Item 3 (quantity multiplier parsed)
    assert items[2]["description"] == "BANANAS"
    assert items[2]["quantity"] == 3
    assert items[2]["price"] == 1.50

    # Verify Item 4 (no leading quantity, defaults to 1)
    assert items[3]["description"] == "PAPER TOWELS"
    assert items[3]["quantity"] == 1
    assert items[3]["price"] == 8.99

def test_parser_orchestration(parser):
    raw_text = (
        "    TARGET STORE\n"
        "Date: 2026-05-27  Time: 12:00\n"
        "1 MILK               3.50\n"
        "1 BREAD              2.00\n"
        "TAX                  0.44\n"
        "TOTAL                5.94\n"
    )
    result = parser.parse(raw_text)
    
    assert result["store_name"] == "TARGET STORE"
    assert result["date"] == "2026-05-27"
    assert result["time"] == "12:00"
    assert result["tax"] == 0.44
    assert result["total"] == 5.94
    assert result["subtotal"] == 5.50
    assert len(result["line_items"]) == 2
    assert result["line_items"][0]["description"] == "MILK"
