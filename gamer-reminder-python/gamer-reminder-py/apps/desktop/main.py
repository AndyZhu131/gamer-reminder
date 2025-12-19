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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
