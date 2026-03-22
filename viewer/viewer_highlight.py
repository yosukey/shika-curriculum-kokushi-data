"""検索ハイライト表示用のデリゲート"""

from __future__ import annotations

import re
from html import escape as html_escape

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QPainter, QTextDocument
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QStyledItemDelegate


def highlight_html(text: str, pattern: re.Pattern) -> str:
    """検索パターンにマッチした部分を黄色ハイライトした HTML を返す"""
    result: list[str] = []
    last_end = 0
    for match in pattern.finditer(text):
        result.append(html_escape(text[last_end:match.start()]))
        result.append(
            f'<span style="background-color: #FFFF00">{html_escape(match.group())}</span>'
        )
        last_end = match.end()
    result.append(html_escape(text[last_end:]))
    return "".join(result)


# ツリービューのリーフノードに備考テキストを格納するカスタムデータロール
REMARKS_ROLE = Qt.ItemDataRole.UserRole + 2


class HighlightDelegate(QStyledItemDelegate):
    """検索語にマッチした部分を黄色ハイライトで描画するデリゲート"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pattern: re.Pattern | None = None

    def set_search_terms(self, terms: list[str]):
        if terms:
            escaped = [re.escape(term) for term in sorted(terms, key=len, reverse=True) if term]
            self._pattern = re.compile("|".join(escaped), re.IGNORECASE) if escaped else None
        else:
            self._pattern = None

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        style = opt.widget.style() if opt.widget else QApplication.style()
        remarks = index.data(REMARKS_ROLE) or ""

        if not self._pattern and not remarks:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            return

        saved_text = opt.text
        opt.text = ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        if not saved_text and not remarks:
            return

        main_html = self._highlight_html(saved_text) if saved_text and self._pattern else html_escape(saved_text)
        if remarks:
            remarks_inner = self._highlight_html(remarks) if self._pattern else html_escape(remarks)
            remarks_html = f'<span style="color: #888888;"> [備考：{remarks_inner}]</span>'
        else:
            remarks_html = ""

        doc = QTextDocument()
        doc.setDefaultFont(opt.font)
        doc.setDocumentMargin(0)
        doc.setTextWidth(opt.rect.width())
        doc.setHtml(main_html + remarks_html)

        margin = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, opt, opt.widget) + 1
        text_height = doc.size().height()
        y_offset = max(0, (opt.rect.height() - text_height) / 2)
        painter.save()
        painter.translate(opt.rect.x() + margin, opt.rect.y() + y_offset)
        painter.setClipRect(opt.rect.translated(-opt.rect.x() - margin, -opt.rect.y() - y_offset))
        doc.drawContents(painter)
        painter.restore()

    def _highlight_html(self, text: str) -> str:
        return highlight_html(text, self._pattern)
