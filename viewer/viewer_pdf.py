"""PDF 表示ダイアログ"""

from __future__ import annotations

import os

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QVBoxLayout

from data_loader import get_data_dir


class PdfViewerDialog(QDialog):
    """PDF を指定ページで表示するモードレスダイアログ"""

    def __init__(self, pdf_path: str, page: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF")
        self.resize(900, 700)
        self._target_page = page - 1
        self._doc = QPdfDocument(self)
        self._doc.load(pdf_path)
        self._view = QPdfView(self)
        self._view.setDocument(self._doc)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setZoomMode(QPdfView.ZoomMode.FitInView)

        self._page_label = QLabel()
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_page_label(self._target_page)
        self._view.pageNavigator().currentPageChanged.connect(self._update_page_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
        layout.addWidget(self._page_label)

    def closeEvent(self, event):
        self._view.setDocument(None)
        self._doc.close()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        navigator = self._view.pageNavigator()
        QTimer.singleShot(0, lambda: navigator.jump(self._target_page, QPointF(), navigator.currentZoom()))

    def _update_page_label(self, page_zero_indexed: int):
        current = page_zero_indexed + 1
        total = self._doc.pageCount()
        self._page_label.setText(f"Page {current} / {total}")


def open_pdf_at_page(pdf_file: str, page: int, parent=None):
    """指定された PDF を該当ページで開く"""
    pdf_path = os.path.join(get_data_dir(), "pdf", pdf_file)
    if not os.path.isfile(pdf_path):
        QMessageBox.warning(
            parent,
            "PDF が見つかりません",
            f"ファイルが見つかりません:\n{pdf_path}",
        )
        return None
    return PdfViewerDialog(pdf_path, page, parent)
