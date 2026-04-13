from net_alpha.import_.anonymizer import anonymize_row


def test_numeric_values_replaced():
    row = {"Amount": "1234.56", "Price": "99.50", "Date": "2024-10-15"}
    result = anonymize_row(row)
    assert result["Amount"] == "1.00"
    assert result["Price"] == "1.00"


def test_dates_preserved():
    row = {"Date": "2024-10-15", "Settlement": "10/17/2024"}
    result = anonymize_row(row)
    assert result["Date"] == "2024-10-15"
    assert result["Settlement"] == "10/17/2024"


def test_tickers_preserved():
    row = {"Symbol": "TSLA", "Amount": "500.00"}
    result = anonymize_row(row)
    assert result["Symbol"] == "TSLA"
    assert result["Amount"] == "1.00"


def test_account_numbers_masked():
    row = {"Account": "XXXX-1234567", "Symbol": "AAPL"}
    result = anonymize_row(row)
    assert result["Account"] == "XXXX"
    assert result["Symbol"] == "AAPL"


def test_standalone_long_number_masked():
    row = {"Ref": "987654321", "Symbol": "NVDA"}
    result = anonymize_row(row)
    assert result["Ref"] == "XXXX"


def test_negative_numbers_replaced():
    row = {"Amount": "-1234.56"}
    result = anonymize_row(row)
    assert result["Amount"] == "1.00"


def test_dollar_sign_stripped_and_replaced():
    row = {"Amount": "$5,432.10"}
    result = anonymize_row(row)
    assert result["Amount"] == "1.00"


def test_empty_values_preserved():
    row = {"Amount": "", "Notes": ""}
    result = anonymize_row(row)
    assert result["Amount"] == ""
    assert result["Notes"] == ""


def test_option_symbols_preserved():
    row = {"Symbol": "TSLA 12/20/2024 250.00 C", "Amount": "300.00"}
    result = anonymize_row(row)
    assert result["Symbol"] == "TSLA 12/20/2024 250.00 C"
    assert result["Amount"] == "1.00"
