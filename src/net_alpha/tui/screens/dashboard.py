from datetime import date
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label, Select
from net_alpha.tui.simulator import simulate_trade

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

    def on_mount(self) -> None:
        table = self.query_one("#holdings-table", DataTable)
        table.add_columns("Date", "Account", "Action", "Ticker", "Qty")
        self.load_trades()

    @on(Input.Changed)
    @on(Select.Changed)
    def on_input_changed(self) -> None:
        self.run_simulation()

    def run_simulation(self) -> None:
        status_label = self.query_one("#sim-status", Label)
        
        # Read inputs
        ticker = self.query_one("#sim-ticker", Input).value
        action = self.query_one("#sim-action", Select).value
        qty_str = self.query_one("#sim-quantity", Input).value
        price_str = self.query_one("#sim-price", Input).value
        date_str = self.query_one("#sim-date", Input).value

        # Basic validation
        if not all([ticker, action, qty_str, price_str, date_str]):
            status_label.update("Status: Waiting for input...")
            status_label.set_classes("")
            return

        try:
            qty = float(qty_str)
            price = float(price_str)
            trade_date = date.fromisoformat(date_str)
        except ValueError:
            status_label.update("Status: Invalid quantity, price, or date format.")
            status_label.set_classes("error")
            return

        # Run engine
        success, result, error = simulate_trade(
            self.app.trades, 
            self.app.etf_pairs, 
            str(action), 
            ticker, 
            qty, 
            price, 
            trade_date
        )

        if not success:
            status_label.update(f"Status: Error - {error}")
            status_label.set_classes("error")
            return

        if len(result.violations) > 0:
            status_label.update("⚠️ Wash Sale Triggered!")
            status_label.set_classes("warning")
        else:
            status_label.update("✅ Safe to Trade")
            status_label.set_classes("safe")

    @work
    async def load_trades(self) -> None:
        table = self.query_one("#holdings-table", DataTable)
        trades = self.app.trades
        
        if not trades:
            self.query_one("#holdings-pane").mount(Label("No trade data found. Press 'i' to import."))
            # Disable simulator
            for input_widget in self.query(Input):
                input_widget.disabled = True
            return
            
        for t in trades:
            table.add_row(str(t.date), t.account, t.action, t.ticker, str(t.quantity))
