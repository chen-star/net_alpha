"""Hand-curated demo trades for the onboarding tour.

DEMO_TAXABLE hosts 3 wash sales (TSLA Confirmed same-account, NVDA leg-out for
the cross-account Probable case, SPY-puts Confirmed options) plus an SPX §1256
closed trade. DEMO_IRA hosts the NVDA leg-in plus open holdings. Dates run
2025-08-04 .. 2026-04-28 (today is 2026-05-07).
"""

from __future__ import annotations

DEMO_TAXABLE: list[dict[str, str]] = [
    # --- Confirmed wash sale: TSLA same-account round-trip -----------------
    {
        "Date": "2025-08-04",
        "Action": "Buy",
        "Symbol": "TSLA",
        "Quantity": "20",
        "Price": "$240.00",
        "Amount": "-$4,800.00",
    },
    {
        "Date": "2025-10-15",
        "Action": "Sell",
        "Symbol": "TSLA",
        "Quantity": "20",
        "Price": "$210.00",
        "Amount": "$4,200.00",
    },
    {
        "Date": "2025-10-30",
        "Action": "Buy",
        "Symbol": "TSLA",
        "Quantity": "20",
        "Price": "$215.00",
        "Amount": "-$4,300.00",
    },
    # --- Probable cross-account wash: NVDA leg-out (taxable) ---------------
    {
        "Date": "2025-09-08",
        "Action": "Buy",
        "Symbol": "NVDA",
        "Quantity": "10",
        "Price": "$520.00",
        "Amount": "-$5,200.00",
    },
    {
        "Date": "2025-12-01",
        "Action": "Sell",
        "Symbol": "NVDA",
        "Quantity": "10",
        "Price": "$470.00",
        "Amount": "$4,700.00",
    },
    # --- Holding-period edge: AAPL ----------------------------------------
    {
        "Date": "2025-09-22",
        "Action": "Buy",
        "Symbol": "AAPL",
        "Quantity": "30",
        "Price": "$185.00",
        "Amount": "-$5,550.00",
    },
    {
        "Date": "2026-01-14",
        "Action": "Sell",
        "Symbol": "AAPL",
        "Quantity": "30",
        "Price": "$172.00",
        "Amount": "$5,160.00",
    },
    {
        "Date": "2026-02-10",
        "Action": "Buy",
        "Symbol": "AAPL",
        "Quantity": "30",
        "Price": "$178.00",
        "Amount": "-$5,340.00",
    },
    # --- Confirmed options wash: SPY puts ----------------------------------
    {
        "Date": "2025-11-04",
        "Action": "Buy to Open",
        "Symbol": "SPY 11/21/2025 540.00 P",
        "Quantity": "2",
        "Price": "$3.50",
        "Amount": "-$700.00",
    },
    {
        "Date": "2025-11-12",
        "Action": "Sell to Close",
        "Symbol": "SPY 11/21/2025 540.00 P",
        "Quantity": "2",
        "Price": "$1.20",
        "Amount": "$240.00",
    },
    {
        "Date": "2025-11-18",
        "Action": "Buy to Open",
        "Symbol": "SPY 12/19/2025 540.00 P",
        "Quantity": "2",
        "Price": "$2.80",
        "Amount": "-$560.00",
    },
    # --- §1256 closed trade: SPX call --------------------------------------
    {
        "Date": "2026-01-05",
        "Action": "Buy to Open",
        "Symbol": "SPX 03/20/2026 4800.00 C",
        "Quantity": "1",
        "Price": "$95.00",
        "Amount": "-$9,500.00",
    },
    {
        "Date": "2026-03-15",
        "Action": "Sell to Close",
        "Symbol": "SPX 03/20/2026 4800.00 C",
        "Quantity": "1",
        "Price": "$115.00",
        "Amount": "$11,500.00",
    },
    # --- Open buys with unrealized losses (5 positions) --------------------
    {
        "Date": "2025-12-20",
        "Action": "Buy",
        "Symbol": "AMZN",
        "Quantity": "8",
        "Price": "$220.00",
        "Amount": "-$1,760.00",
    },
    {
        "Date": "2026-01-09",
        "Action": "Buy",
        "Symbol": "GOOGL",
        "Quantity": "12",
        "Price": "$165.00",
        "Amount": "-$1,980.00",
    },
    {
        "Date": "2026-02-03",
        "Action": "Buy",
        "Symbol": "META",
        "Quantity": "5",
        "Price": "$520.00",
        "Amount": "-$2,600.00",
    },
    {
        "Date": "2026-02-22",
        "Action": "Buy",
        "Symbol": "AMD",
        "Quantity": "15",
        "Price": "$155.00",
        "Amount": "-$2,325.00",
    },
    {
        "Date": "2026-03-30",
        "Action": "Buy",
        "Symbol": "JPM",
        "Quantity": "10",
        "Price": "$220.00",
        "Amount": "-$2,200.00",
    },
    # --- Open winners ------------------------------------------------------
    {
        "Date": "2025-08-25",
        "Action": "Buy",
        "Symbol": "MSFT",
        "Quantity": "10",
        "Price": "$405.00",
        "Amount": "-$4,050.00",
    },
    {
        "Date": "2025-09-12",
        "Action": "Buy",
        "Symbol": "VOO",
        "Quantity": "20",
        "Price": "$455.00",
        "Amount": "-$9,100.00",
    },
]

DEMO_IRA: list[dict[str, str]] = [
    # --- NVDA leg-in for the cross-account Probable wash sale -------------
    {
        "Date": "2025-12-15",
        "Action": "Buy",
        "Symbol": "NVDA",
        "Quantity": "10",
        "Price": "$475.00",
        "Amount": "-$4,750.00",
    },
    # --- Long-term IRA holdings -------------------------------------------
    {
        "Date": "2025-08-04",
        "Action": "Buy",
        "Symbol": "VTI",
        "Quantity": "30",
        "Price": "$240.00",
        "Amount": "-$7,200.00",
    },
    {
        "Date": "2025-09-15",
        "Action": "Buy",
        "Symbol": "BND",
        "Quantity": "50",
        "Price": "$72.00",
        "Amount": "-$3,600.00",
    },
    {
        "Date": "2025-10-08",
        "Action": "Buy",
        "Symbol": "QQQM",
        "Quantity": "15",
        "Price": "$190.00",
        "Amount": "-$2,850.00",
    },
    {
        "Date": "2025-11-19",
        "Action": "Buy",
        "Symbol": "SPLG",
        "Quantity": "25",
        "Price": "$68.00",
        "Amount": "-$1,700.00",
    },
    {
        "Date": "2026-01-20",
        "Action": "Buy",
        "Symbol": "AVUV",
        "Quantity": "20",
        "Price": "$95.00",
        "Amount": "-$1,900.00",
    },
    # --- Realized winner --------------------------------------------------
    {
        "Date": "2025-12-05",
        "Action": "Buy",
        "Symbol": "COST",
        "Quantity": "5",
        "Price": "$880.00",
        "Amount": "-$4,400.00",
    },
    {
        "Date": "2026-04-10",
        "Action": "Sell",
        "Symbol": "COST",
        "Quantity": "5",
        "Price": "$945.00",
        "Amount": "$4,725.00",
    },
    # --- Open option (covered call premium) -------------------------------
    {
        "Date": "2026-03-12",
        "Action": "Sell to Open",
        "Symbol": "VTI 06/19/2026 260.00 C",
        "Quantity": "1",
        "Price": "$2.10",
        "Amount": "$210.00",
    },
]
