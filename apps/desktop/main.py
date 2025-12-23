import signal
import sys
from PySide6.QtWidgets import QApplication

from packages.shared.paths import ensure_app_dirs
from packages.core.logging_ import setup_logging
from .ui.window import MainWindow


def main() -> None:
    ensure_app_dirs()
    setup_logging()

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    
    # Handle Ctrl+C gracefully (works on Unix/Linux/Mac)
    # On Windows, Qt handles Ctrl+C automatically and triggers closeEvent
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal (Ctrl+C), shutting down...")
        win.close()
    
    # Register signal handler for Ctrl+C (Unix/Linux/Mac)
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, signal_handler)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
