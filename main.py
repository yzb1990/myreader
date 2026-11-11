from __future__ import annotations

import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from myreader.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("墨读")
    app.setApplicationDisplayName("墨读")
    app.setOrganizationName("MoReader")

    window = MainWindow()
    window.show()

    files = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    if files:
        QTimer.singleShot(0, lambda: window.open_files(files))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
