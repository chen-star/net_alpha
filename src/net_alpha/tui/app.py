from textual.app import App, ComposeResult
from textual.widgets import Header, Footer
from net_alpha.tui.screens.dashboard import DashboardScreen
from net_alpha.models.domain import Trade

class NetAlphaTUI(App):
    """Main TUI application for net-alpha."""
    
    TITLE = "net-alpha"
    SUB_TITLE = "Cross-Account Wash Sale Detector"
    CSS_PATH = "styles.tcss"
    
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, trades: list[Trade] = None, etf_pairs: dict[str, list[str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.trades = trades or []
        self.etf_pairs = etf_pairs or {}

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
