"""アプリケーション起動処理"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QDir, QLockFile, QTimer
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from data_loader import get_data_dir
from viewer_main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    lock_path = QDir.tempPath() + "/shika_cc_viewer.lock"
    lock_file = QLockFile(lock_path)
    lock_file.setStaleLockTime(30000)
    if not lock_file.tryLock(0):
        msg = QMessageBox()
        msg.setWindowTitle("起動エラー")
        msg.setText("アプリはすでに起動しています。")
        msg.exec()
        return 0

    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(76, 163, 224))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
    app.setPalette(palette)

    icon_path = os.path.join(get_data_dir(), "icon", "icon.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    window: MainWindow | None = MainWindow()
    cleanup_done = False

    def cleanup():
        nonlocal cleanup_done, window
        if cleanup_done:
            return
        cleanup_done = True

        if window is not None:
            window.teardown()
            window.close()
            window.deleteLater()
            window = None

        if lock_file.isLocked():
            lock_file.unlock()

    app.aboutToQuit.connect(cleanup)

    window.show()
    QTimer.singleShot(0, window.check_for_updates)
    try:
        return app.exec()
    finally:
        cleanup()
