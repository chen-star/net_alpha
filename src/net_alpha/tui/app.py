from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

class NetAlphaTUI(App):
    """Main TUI application for net-alpha."""
    
    TITLE = "net-alpha"
    SUB_TITLE = "Cross-Account Wash Sale Detector"
    
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
