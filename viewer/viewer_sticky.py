"""ツリービュー用のスティッキーヘッダー"""

from __future__ import annotations

import re
from html import escape as html_escape

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPoint, Qt
from PySide6.QtWidgets import QAbstractItemView, QFrame, QHBoxLayout, QLabel, QTreeView

from viewer_highlight import highlight_html


class StickyHeaderOverlay(QObject):
    """ツリービューでスクロール時に親ノードをビューポート上部に固定表示する"""

    _MAX_LEVELS = 5

    def __init__(self, tree_view: QTreeView, parent=None):
        super().__init__(parent)
        self._tree_view = tree_view
        self._headers: list[QFrame] = []
        self._current_indices: list[QModelIndex] = []
        self._highlight_pattern: re.Pattern | None = None
        self._event_filter_installed = False

        for level in range(self._MAX_LEVELS):
            frame = QFrame(tree_view.viewport())
            frame.setAutoFillBackground(True)
            frame.setCursor(Qt.CursorShape.PointingHandCursor)
            label = QLabel(frame)
            label.setTextFormat(Qt.TextFormat.RichText)
            layout = QHBoxLayout(frame)
            layout.setContentsMargins(4, 2, 4, 2)
            layout.setSpacing(0)
            layout.addWidget(label)
            frame.hide()
            frame.mousePressEvent = lambda event, lvl=level: self._on_header_clicked(lvl)
            self._headers.append(frame)

    def set_search_terms(self, terms: list[str]):
        if terms:
            escaped = [re.escape(term) for term in sorted(terms, key=len, reverse=True) if term]
            self._highlight_pattern = re.compile("|".join(escaped), re.IGNORECASE) if escaped else None
        else:
            self._highlight_pattern = None
        self._update_sticky_headers()

    def attach(self):
        if self._event_filter_installed:
            return
        self._tree_view.viewport().installEventFilter(self)
        self._tree_view.verticalScrollBar().valueChanged.connect(self._update_sticky_headers)
        self._tree_view.expanded.connect(lambda: self._update_sticky_headers())
        self._tree_view.collapsed.connect(lambda: self._update_sticky_headers())
        self._event_filter_installed = True

    def remove_event_filter(self):
        if not self._event_filter_installed:
            return
        self._tree_view.viewport().removeEventFilter(self)
        self._event_filter_installed = False

    def reset(self):
        self._current_indices.clear()
        for frame in self._headers:
            frame.hide()

    @staticmethod
    def _lighten_color(hex_color: str, factor: float = 0.75) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def update_theme(self, theme: dict):
        background = self._lighten_color(theme.get("header_bg", "#4a6da7"))
        stylesheet = f"""
            QFrame {{
                background-color: {background};
                color: #333;
                border-bottom: 1px solid #ccc;
                font-weight: bold;
            }}
            QLabel {{
                background: transparent;
                color: #333;
                font-weight: bold;
            }}
        """
        for frame in self._headers:
            frame.setStyleSheet(stylesheet)

    def update_font(self, font):
        for frame in self._headers:
            frame.findChild(QLabel).setFont(font)

    def eventFilter(self, obj, event):
        if obj is self._tree_view.viewport() and event.type() == QEvent.Type.Resize:
            self._update_sticky_headers()
        return False

    def _collect_sticky_indices(self, y_offset: int):
        top_index = self._tree_view.indexAt(QPoint(0, y_offset))
        if not top_index.isValid():
            return []

        sticky_indices: list[QModelIndex] = []
        idx = top_index.parent()
        while idx.isValid():
            if self._tree_view.visualRect(idx).top() < y_offset:
                sticky_indices.insert(0, idx)
            idx = idx.parent()

        top_rect = self._tree_view.visualRect(top_index)
        if (
            self._tree_view.model().hasChildren(top_index)
            and top_rect.top() < y_offset
            and self._tree_view.isExpanded(top_index)
        ):
            sticky_indices.append(top_index)

        return sticky_indices

    def _update_sticky_headers(self):
        viewport = self._tree_view.viewport()
        model = self._tree_view.model()
        if model is None or model.rowCount() == 0:
            self._hide_all()
            return

        row_height = self._tree_view.sizeHintForRow(0)
        if row_height <= 0:
            row_height = 24
        header_height = row_height + 4

        y_offset = 0
        sticky_indices: list[QModelIndex] = []
        for _ in range(self._MAX_LEVELS + 1):
            sticky_indices = self._collect_sticky_indices(y_offset)
            new_offset = len(sticky_indices) * header_height
            if new_offset == y_offset:
                break
            y_offset = new_offset

        if not sticky_indices and not self._tree_view.indexAt(QPoint(0, 0)).isValid():
            self._hide_all()
            return

        indent = self._tree_view.indentation()
        cumulative_y = 0

        self._current_indices = sticky_indices
        for index, frame in enumerate(self._headers):
            if index < len(sticky_indices):
                sticky_index = sticky_indices[index]
                text = model.data(sticky_index, Qt.ItemDataRole.DisplayRole) or ""
                label = frame.findChild(QLabel)
                label.setText(f"▼ {self._make_label_html(text)}")
                left_margin = indent * index + 4
                label.setContentsMargins(left_margin, 0, 0, 0)
                frame.setGeometry(0, cumulative_y, viewport.width(), header_height)
                frame.show()
                frame.raise_()
                cumulative_y += header_height
            else:
                frame.hide()

    def _hide_all(self):
        self._current_indices.clear()
        for frame in self._headers:
            frame.hide()

    def _make_label_html(self, text: str) -> str:
        if self._highlight_pattern is None:
            return html_escape(text)
        return highlight_html(text, self._highlight_pattern)

    def _on_header_clicked(self, level: int):
        if level < len(self._current_indices):
            index = self._current_indices[level]
            self._tree_view.collapse(index)
            self._tree_view.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtTop)
            self._update_sticky_headers()
