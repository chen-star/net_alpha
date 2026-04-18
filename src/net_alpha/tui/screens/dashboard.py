from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label, Select

class DashboardScreen(Screen):
    """Split-pane view for holdings and simulator."""
    
    def compose(self) -> ComposeResult:
        with Container(id="holdings-pane"):
            yield Label("Portfolio Holdings")
            yield DataTable(id="holdings-table")
            
        with Vertical(id="simulator-pane"):
            yield Label("Draft Trade Simulator", classes="section-title")
            yield Input(placeholder="Ticker (e.g. TSLA)", id="sim-ticker")
            yield Select([("Sell", "Sell"), ("Buy", "Buy")], prompt="Action", id="sim-action")
            yield Input(placeholder="Quantity", id="sim-quantity")
            yield Input(placeholder="Price", id="sim-price")
            yield Input(placeholder="Date (YYYY-MM-DD)", id="sim-date")
            yield Label("Status: Pending", id="sim-status")
