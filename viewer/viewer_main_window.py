"""メインウィンドウ実装"""

from __future__ import annotations

import os
from collections import OrderedDict
from typing import Callable

from PySide6.QtCore import QEvent, QModelIndex, Qt, QThread, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence, QShortcut, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from data_loader import Record, get_data_dir, load_jsonl
from dataset_config import ALL_DATASETS, DatasetConfig, _code_sort_key
from update_checker import UpdateCheckResult, UpdateCheckWorker
from version import __version__
from viewer_highlight import HighlightDelegate, REMARKS_ROLE
from viewer_models import GenericFilterProxyModel, GenericTableModel
from viewer_pdf import PdfViewerDialog, open_pdf_at_page
from viewer_search import QuerySyntaxError, parse_query
from viewer_sticky import StickyHeaderOverlay


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"歯科コアカリ・出題基準ビューワ v{__version__}")
        self.resize(1400, 800)

        self._datasets = ALL_DATASETS
        self._current_config: DatasetConfig | None = None
        self._current_records: list[Record] = []
        self._pdf_dialogs: set[PdfViewerDialog] = set()
        self._teardown_done = False
        self._search_matcher: Callable[[str], bool] | None = None
        self._search_error: str | None = None
        self._update_thread: QThread | None = None
        self._update_worker: UpdateCheckWorker | None = None
        self._update_check_interactive = False

        self._source_model = GenericTableModel()
        self._proxy_model = GenericFilterProxyModel()
        self._proxy_model.setSourceModel(self._source_model)

        self._filter_combos: list[QComboBox] = []
        self._filter_labels: list[QLabel] = []
        self._filter_row: QHBoxLayout | None = None
        self._stretch_col_indices: list[int] = []

        self._build_ui()
        self._build_menu_bar()
        self._connect_signals()
        self._load_dataset(0)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("データ:"))
        self._dataset_combo = QComboBox()
        self._dataset_combo.setMinimumWidth(160)
        for dataset in self._datasets:
            self._dataset_combo.addItem(dataset.name)
        row1.addWidget(self._dataset_combo)

        row1.addSpacing(20)
        row1.addWidget(QLabel("表示:"))
        self._view_combo = QComboBox()
        self._view_combo.addItem("テーブル")
        self._view_combo.addItem("ツリー")
        self._view_combo.setMinimumWidth(100)
        row1.addWidget(self._view_combo)

        row1.addSpacing(20)
        row1.addWidget(QLabel("検索:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText('キーワード検索（AND/OR/NOT、-除外、"フレーズ"）')
        self._search_edit.setClearButtonEnabled(True)
        row1.addWidget(self._search_edit, 1)
        layout.addLayout(row1)

        self._filter_row = QHBoxLayout()
        layout.addLayout(self._filter_row)

        self._view_stack = QStackedWidget()

        self._table_view = QTableView()
        self._table_view.setModel(self._proxy_model)
        self._table_view.setSortingEnabled(True)
        self._table_view.horizontalHeader().setSortIndicatorShown(False)
        self._table_view.horizontalHeader().sortIndicatorChanged.connect(
            lambda: self._proxy_model.headerDataChanged.emit(
                Qt.Orientation.Horizontal,
                0,
                self._proxy_model.columnCount() - 1,
            )
        )
        self._table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table_view.setWordWrap(True)
        vertical_header = self._table_view.verticalHeader()
        vertical_header.setVisible(False)
        vertical_header.setDefaultSectionSize(vertical_header.defaultSectionSize() * 2)
        self._table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._table_view.viewport().installEventFilter(self)
        self._highlight_delegate = HighlightDelegate(self._table_view)
        self._table_view.setItemDelegate(self._highlight_delegate)
        self._view_stack.addWidget(self._table_view)

        self._tree_view = QTreeView()
        self._tree_model = QStandardItemModel()
        self._tree_model.setHorizontalHeaderLabels(["項目"])
        self._tree_view.setModel(self._tree_model)
        self._tree_view.setAlternatingRowColors(True)
        self._tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree_highlight_delegate = HighlightDelegate(self._tree_view)
        self._tree_view.setItemDelegate(self._tree_highlight_delegate)
        self._tree_view.setHeaderHidden(False)
        self._tree_view.header().setStretchLastSection(True)

        tree_container = QWidget()
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(4)
        tree_button_row = QHBoxLayout()
        self._expand_all_btn = QPushButton("すべて開く")
        self._collapse_all_btn = QPushButton("すべて閉じる")
        self._expand_all_btn.setFixedHeight(24)
        self._collapse_all_btn.setFixedHeight(24)
        self._expand_all_btn.clicked.connect(self._tree_view.expandAll)
        self._collapse_all_btn.clicked.connect(self._on_collapse_all)
        tree_button_row.addWidget(self._expand_all_btn)
        tree_button_row.addWidget(self._collapse_all_btn)
        tree_button_row.addStretch()
        tree_layout.addLayout(tree_button_row)
        tree_layout.addWidget(self._tree_view)
        self._sticky_overlay = StickyHeaderOverlay(self._tree_view, parent=self._tree_view)
        self._view_stack.addWidget(tree_container)

        layout.addWidget(self._view_stack, 1)

        self._status_label = QLabel()
        self.statusBar().addWidget(self._status_label)

        shortcut = QShortcut(QKeySequence.StandardKey.Copy, self._table_view)
        shortcut.activated.connect(self._copy_cell)

    def _build_menu_bar(self):
        menu_bar = self.menuBar()

        help_menu = menu_bar.addMenu("Help")
        check_update_action = QAction("Check for Update", self)
        check_update_action.triggered.connect(lambda: self.check_for_updates(interactive=True))
        help_menu.addAction(check_update_action)

        help_menu.addSeparator()

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about_dialog)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        help_menu.addAction(about_action)

        font_menu = menu_bar.addMenu("Font")
        font_group = QActionGroup(self)
        font_group.setExclusive(True)
        for label, size in [("小", 10), ("中", 12), ("大", 14)]:
            action = QAction(label, self, checkable=True)
            action.setData(size)
            action.triggered.connect(lambda checked, point_size=size: self._change_font_size(point_size))
            font_group.addAction(action)
            font_menu.addAction(action)
            if size == 10:
                action.setChecked(True)

        link_menu = menu_bar.addMenu("Link")
        seen_urls: set[str] = set()
        for config in self._datasets:
            for label, url in config.source_urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                action = QAction(label, self)
                action.triggered.connect(lambda checked, target=url: QDesktopServices.openUrl(QUrl(target)))
                link_menu.addAction(action)

    def check_for_updates(self, interactive: bool = False):
        if self._update_thread is not None:
            if interactive:
                QMessageBox.information(self, "更新確認", "更新確認はすでに実行中です。")
            return

        self._update_check_interactive = interactive
        self.statusBar().showMessage("更新を確認しています...", 3000)

        self._update_thread = QThread(self)
        self._update_worker = UpdateCheckWorker(__version__)
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.finished.connect(self._on_update_check_finished)
        self._update_worker.finished.connect(self._update_thread.quit)
        self._update_thread.finished.connect(self._cleanup_update_thread)
        self._update_thread.start()

    def _on_update_check_finished(self, result: UpdateCheckResult):
        self.statusBar().showMessage("更新確認が完了しました。", 3000)

        if result.status == "update_available":
            msg = QMessageBox(self)
            msg.setWindowTitle("アップデートがあります")
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setText(
                "新しいバージョンが利用可能です。<br><br>"
                f"現在のバージョン: <b>{result.current_version}</b><br>"
                f"最新リリース: <b>{result.latest_version}</b><br>"
                f"リリースページ: <a href='{result.release_url}'>{result.release_url}</a>"
            )
            msg.exec()
            return

        if result.status == "up_to_date":
            if self._update_check_interactive:
                QMessageBox.information(
                    self,
                    "更新確認",
                    f"現在のバージョン {result.current_version} は最新です。",
                )
            return

        if result.status == "comparison_unavailable":
            if self._update_check_interactive:
                QMessageBox.information(
                    self,
                    "更新確認",
                    "現在のバージョンは開発版または比較不能な形式です。\n"
                    f"最新リリース: {result.latest_version}\n"
                    f"リリースページ: {result.release_url}",
                )
            return

        if self._update_check_interactive:
            QMessageBox.warning(
                self,
                "更新確認エラー",
                result.error_message or "更新確認に失敗しました。",
            )

    def _cleanup_update_thread(self):
        if self._update_worker is not None:
            self._update_worker.deleteLater()
            self._update_worker = None
        if self._update_thread is not None:
            self._update_thread.deleteLater()
            self._update_thread = None
        self._update_check_interactive = False

    def _show_about_dialog(self):
        repo_url = "https://github.com/yosukey/shika-curriculum-kokushi-data"
        agpl_url = "https://www.gnu.org/licenses/agpl-3.0.html"
        pdl_url = "https://www.digital.go.jp/resources/open_data/public_data_license_v1.0"
        mext_url = "https://www.mext.go.jp/b_menu/1351168.htm"
        corecurriculum_url = "https://www.mext.go.jp/a_menu/koutou/iryou/mext_00009.html"
        kokushi_url = "https://www.mhlw.go.jp/stf/shingi2/0000163627_00002.html"
        msg = QMessageBox(self)
        msg.setWindowTitle("About")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            f"<b>歯科コアカリ・出題基準ビューワ</b> &nbsp; v{__version__}<br><br>"
            "<b>アプリ開発:</b> 山崎洋介（日本大学歯学部解剖学第2講座）<br>"
            f"リポジトリ: <a href='{repo_url}'>{repo_url}</a><br>"
            f"ライセンス: <a href='{agpl_url}'>GNU AGPL v3.0</a><br>"
            "<hr>"
            "<b>ライセンス（データ）</b><br><br>"
            "本データセットは、以下出典に示すデータを構造化・整理したものです。"
            f"<a href='{pdl_url}'>公共データ利用規約 第1.0版 (PDL1.0)</a> および"
            f"<a href='{mext_url}'>文部科学省ウェブサイト利用規約</a>に従い、公開しています。<br><br>"
            "<b>出典</b><br><br>"
            "<b>歯学教育モデル・コア・カリキュラム（R4版・H28版）</b><br>"
            f"「歯学教育モデル・コア・カリキュラム（令和4年度改訂版）」（文部科学省）"
            f"（<a href='{corecurriculum_url}'>{corecurriculum_url}</a>）、<br>"
            f"「歯学教育モデル・コア・カリキュラム（平成28年度改訂版）」（文部科学省）"
            f"（<a href='{corecurriculum_url}'>{corecurriculum_url}</a>）<br>"
            "を加工して作成<br><br>"
            "<b>歯科医師国家試験出題基準（R5版）</b><br>"
            f"「歯科医師国家試験出題基準（令和5年版）」（厚生労働省）"
            f"（<a href='{kokushi_url}'>{kokushi_url}</a>）を加工して作成"
        )
        msg.exec()

    def closeEvent(self, event):
        self.teardown()
        super().closeEvent(event)

    def teardown(self):
        if self._teardown_done:
            return
        self._teardown_done = True

        for dialog in list(self._pdf_dialogs):
            dialog.close()
            dialog.deleteLater()
        self._pdf_dialogs.clear()

        self._sticky_overlay.remove_event_filter()
        self._table_view.viewport().removeEventFilter(self)

        if self._update_thread is not None:
            self._update_thread.quit()
            self._update_thread.wait(1000)

    def _change_font_size(self, size: int):
        font = self._table_view.font()
        font.setPointSize(size)
        self._table_view.setFont(font)
        self._tree_view.setFont(font)
        self._sticky_overlay.update_font(font)

    def _connect_signals(self):
        self._dataset_combo.currentIndexChanged.connect(self._load_dataset)
        self._view_combo.currentIndexChanged.connect(self._on_view_changed)
        self._search_edit.textChanged.connect(self._on_search_text_changed)
        self._table_view.doubleClicked.connect(self._on_double_click)
        self._table_view.customContextMenuRequested.connect(self._show_context_menu)
        self._tree_view.doubleClicked.connect(self._on_tree_double_click)
        self._tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)
        self._proxy_model.layoutChanged.connect(self._update_status)
        self._proxy_model.modelReset.connect(self._update_status)
        self._sticky_overlay.attach()

    def _load_dataset(self, index: int):
        config = self._datasets[index]
        self._current_config = config

        filepath = os.path.join(get_data_dir(), config.filename)
        self._current_records = load_jsonl(filepath, config)

        self._source_model.set_config(config)
        self._proxy_model.set_config(config)
        self._source_model.set_records(self._current_records)

        self._apply_table_columns(config)
        self._table_view.sortByColumn(config.default_sort_column, Qt.SortOrder.AscendingOrder)
        self._table_view.horizontalHeader().setSortIndicator(
            config.default_sort_column,
            Qt.SortOrder.AscendingOrder,
        )

        self._search_edit.clear()
        self._apply_search_query("")
        self._proxy_model.clear_filters()

        self._apply_theme(config)
        self._rebuild_filter_combos(config)
        if self._is_tree_view_active():
            self._rebuild_tree()
        self._update_status()

    def _apply_table_columns(self, config: DatasetConfig):
        header = self._table_view.horizontalHeader()
        header.setStretchLastSection(False)
        self._stretch_col_indices = []

        for index, col_def in enumerate(config.columns):
            self._table_view.setColumnHidden(index, col_def.hidden)
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)
            if col_def.stretch:
                self._stretch_col_indices.append(index)
            else:
                self._table_view.setColumnWidth(index, col_def.width)

        self._adjust_stretch_columns()

    def _adjust_stretch_columns(self):
        if not self._stretch_col_indices or not self._current_config:
            return
        header = self._table_view.horizontalHeader()
        viewport_width = self._table_view.viewport().width()
        used = 0
        for index, _ in enumerate(self._current_config.columns):
            if self._table_view.isColumnHidden(index) or index in self._stretch_col_indices:
                continue
            used += header.sectionSize(index)
        remaining = max(0, viewport_width - used)
        per_col = remaining // len(self._stretch_col_indices)
        min_width = 100
        for index in self._stretch_col_indices:
            self._table_view.setColumnWidth(index, max(per_col, min_width))

    def eventFilter(self, obj, event):
        if obj is self._table_view.viewport() and event.type() == QEvent.Type.Resize:
            self._adjust_stretch_columns()
        return super().eventFilter(obj, event)

    def _apply_theme(self, config: DatasetConfig):
        theme = config.theme
        header_stylesheet = f"""
            QHeaderView::section {{
                background-color: {theme['header_bg']};
                color: {theme['header_fg']};
                padding: 4px;
                border: 1px solid #888;
                font-weight: bold;
            }}
        """
        table_stylesheet = header_stylesheet + f"""
            QTableView {{
                alternate-background-color: {theme['alt_row']};
            }}
            QTableView::item:selected {{
                background-color: {theme['selection']};
                color: black;
            }}
            QTableView::item:hover {{
                background-color: {theme['hover']};
                color: black;
            }}
        """
        self._table_view.setStyleSheet(table_stylesheet)
        tree_stylesheet = header_stylesheet + f"""
            QTreeView {{
                alternate-background-color: {theme['alt_row']};
            }}
            QTreeView::item:selected {{
                background-color: {theme['selection']};
                color: black;
            }}
            QTreeView::item:hover {{
                background-color: {theme['hover']};
                color: black;
            }}
        """
        self._tree_view.setStyleSheet(tree_stylesheet)
        self._sticky_overlay.update_theme(theme)

    def _rebuild_filter_combos(self, config: DatasetConfig):
        self._filter_combos.clear()
        self._filter_labels.clear()

        while self._filter_row.count():
            item = self._filter_row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for index, filter_def in enumerate(config.filters):
            if index > 0:
                self._filter_row.addSpacing(10)
            label = QLabel(f"{filter_def.label}:")
            self._filter_labels.append(label)
            self._filter_row.addWidget(label)

            combo = QComboBox()
            combo.setMinimumWidth(filter_def.min_width)
            combo.setStyleSheet(
                "QComboBox:disabled { background-color: #E0E0E0; color: #999999; }"
            )
            combo.setProperty("filter_index", index)
            combo.setProperty("code_field", filter_def.code_field)
            self._filter_combos.append(combo)
            self._filter_row.addWidget(combo)
            combo.currentIndexChanged.connect(lambda _, filter_index=index: self._on_filter_combo_changed(filter_index))

        self._filter_row.addStretch()
        self._populate_filter_combos()

        for index in range(1, len(self._filter_combos)):
            self._filter_combos[index].setEnabled(False)

    def _populate_filter_combos(self):
        if not self._current_config:
            return
        for index in range(len(self._filter_combos)):
            self._rebuild_single_filter(index)

    def _rebuild_single_filter(self, filter_index: int):
        config = self._current_config
        if not config or filter_index >= len(config.filters):
            return

        filter_def = config.filters[filter_index]
        combo = self._filter_combos[filter_index]
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("全て", "")

        parent_filters: dict[str, str] = {}
        for parent_index in range(filter_index):
            parent_filter = config.filters[parent_index]
            value = self._filter_combos[parent_index].currentData() or ""
            if value:
                parent_filters[parent_filter.code_field] = value

        seen: dict[str, str] = {}
        for record in self._current_records:
            if any(record.get(field) != value for field, value in parent_filters.items()):
                continue
            code = record.get(filter_def.code_field)
            if code not in seen:
                seen[code] = record.get(filter_def.title_field, "") or ""

        sort_fn = filter_def.sort_key if filter_def.sort_key else _code_sort_key
        for code in sorted(seen, key=sort_fn):
            title = seen[code]
            label = f"{code}: {title}" if title else str(code) if code else "(なし)"
            combo.addItem(label, code)

        combo.blockSignals(False)

    def _on_filter_combo_changed(self, filter_index: int):
        config = self._current_config
        if not config:
            return

        filter_def = config.filters[filter_index]
        combo = self._filter_combos[filter_index]
        value = combo.currentData() or ""
        self._proxy_model.set_filter(filter_def.code_field, value)

        for child_index in range(filter_index + 1, len(config.filters)):
            child_filter = config.filters[child_index]
            self._proxy_model.set_filter(child_filter.code_field, "")
            self._rebuild_single_filter(child_index)
            if child_index == filter_index + 1:
                self._filter_combos[child_index].setEnabled(bool(value))
            else:
                self._filter_combos[child_index].setEnabled(False)

        self._on_filter_changed()

    def _on_filter_changed(self):
        if self._is_tree_view_active():
            self._rebuild_tree()
        self._update_status()

    def _update_highlight_terms(self, terms: list[str]):
        self._highlight_delegate.set_search_terms(terms)
        self._tree_highlight_delegate.set_search_terms(terms)
        self._sticky_overlay.set_search_terms(terms)
        self._table_view.viewport().update()
        self._tree_view.viewport().update()

    def _apply_search_query(self, text: str):
        stripped = text.strip()
        if not stripped:
            self._search_matcher = None
            self._search_error = None
            self._proxy_model.set_search_matcher(None)
            self._update_highlight_terms([])
            return

        try:
            parsed = parse_query(stripped)
        except QuerySyntaxError as exc:
            self._search_matcher = None
            self._search_error = str(exc)
            self._proxy_model.set_search_matcher(None)
            self._update_highlight_terms([])
            return

        self._search_matcher = parsed.matcher
        self._search_error = None
        self._proxy_model.set_search_matcher(parsed.matcher)
        self._update_highlight_terms(parsed.positive_terms)

    def _on_search_text_changed(self, text: str):
        self._apply_search_query(text)
        self._on_filter_changed()

    def _on_view_changed(self, index: int):
        self._view_stack.setCurrentIndex(index)
        if index == 1:
            self._rebuild_tree()
        self._update_status()

    def _on_collapse_all(self):
        self._tree_view.collapseAll()
        self._sticky_overlay.reset()

    def _is_tree_view_active(self) -> bool:
        return self._view_stack.currentIndex() == 1

    def _rebuild_tree(self):
        self._tree_model.clear()
        self._tree_model.setHorizontalHeaderLabels(["項目"])

        config = self._current_config
        if not config:
            return

        active_filters = self._get_active_filters(config)
        search_matcher = self._search_matcher

        filtered_records = [
            record
            for record in self._current_records
            if all(record.get(field) == value for field, value in active_filters.items())
        ]

        root = self._tree_model.invisibleRootItem()
        self._build_hierarchy(root, filtered_records, config.hierarchy, 0, config)

        if search_matcher is not None:
            self._prune_tree(root, search_matcher)
            self._expand_matching_nodes(search_matcher)
        else:
            self._tree_view.expandToDepth(0)
        self._sticky_overlay.reset()

    def _get_active_filters(self, config: DatasetConfig) -> dict[str, str]:
        active_filters: dict[str, str] = {}
        for index, filter_def in enumerate(config.filters):
            if index >= len(self._filter_combos):
                continue
            value = self._filter_combos[index].currentData() or ""
            if value:
                active_filters[filter_def.code_field] = value
        return active_filters

    def _prune_tree(self, parent: QStandardItem, search_matcher: Callable[[str], bool]):
        rows_to_remove: list[int] = []
        for row in range(parent.rowCount()):
            child = parent.child(row, 0)
            if child is None:
                continue
            self._prune_tree(child, search_matcher)
            child_text = self._tree_node_text(child)
            node_matches = search_matcher(child_text)
            has_children = child.rowCount() > 0
            if not node_matches and not has_children:
                rows_to_remove.append(row)
        for row in reversed(rows_to_remove):
            parent.removeRow(row)

    def _expand_matching_nodes(self, search_matcher: Callable[[str], bool]):
        self._tree_view.collapseAll()

        def process(item: QStandardItem):
            for row in range(item.rowCount()):
                child = item.child(row, 0)
                if child is None:
                    continue
                if search_matcher(self._tree_node_text(child)):
                    ancestor = child.parent()
                    while ancestor is not None:
                        self._tree_view.expand(ancestor.index())
                        ancestor = ancestor.parent()
                process(child)

        process(self._tree_model.invisibleRootItem())

    @staticmethod
    def _tree_node_text(item: QStandardItem) -> str:
        text = item.text().lower()
        remarks = item.data(REMARKS_ROLE) or ""
        if remarks:
            text = text + " " + remarks.lower()
        return text

    def _build_hierarchy(
        self,
        parent_item: QStandardItem,
        records: list[Record],
        levels: list,
        level_index: int,
        config: DatasetConfig,
    ):
        if level_index >= len(levels):
            for record in records:
                label = config.leaf_label(record) if config.leaf_label else str(record.get("id", ""))
                if not label.strip():
                    parent_item.setData(record, Qt.ItemDataRole.UserRole)
                else:
                    item = QStandardItem(label)
                    item.setData(record, Qt.ItemDataRole.UserRole)
                    if config.leaf_remarks:
                        remarks_text = config.leaf_remarks(record)
                        if remarks_text:
                            item.setData(remarks_text, REMARKS_ROLE)
                    parent_item.appendRow(item)
            return

        level = levels[level_index]
        groups: OrderedDict[str | None, dict] = OrderedDict()
        null_records: list[Record] = []

        for record in records:
            code = record.get(level.code_field)
            if code is None and level.allow_null:
                null_records.append(record)
                continue
            key = code if code is not None else ""
            if key not in groups:
                groups[key] = {"records": [], "sample": record}
            groups[key]["records"].append(record)

        sort_fn = level.sort_key if level.sort_key else lambda key: _code_sort_key(str(key))
        for key in sorted(groups, key=sort_fn):
            info = groups[key]
            sample = info["sample"]
            group_label = level.label(sample) if level.label else self._default_group_label(level, key, sample)
            group_item = QStandardItem(group_label)
            group_item.setData(None, Qt.ItemDataRole.UserRole)
            parent_item.appendRow(group_item)
            self._build_hierarchy(group_item, info["records"], levels, level_index + 1, config)

        if null_records:
            self._build_hierarchy(parent_item, null_records, levels, level_index + 1, config)

    @staticmethod
    def _default_group_label(level, key: str | None, sample: Record) -> str:
        title = sample.get(level.title_field, "")
        return f"{key} {title}" if title else str(key)

    def _update_status(self):
        total = self._source_model.rowCount()
        dataset_name = self._dataset_combo.currentText()
        if self._is_tree_view_active():
            shown = self._count_tree_leaves(self._tree_model.invisibleRootItem())
            view_label = "ツリー"
        else:
            shown = self._proxy_model.rowCount()
            view_label = "テーブル"
        status = f"表示: {shown} / {total} 件  |  {dataset_name}  |  {view_label}"
        if self._search_error:
            status += f"  |  検索式エラー: {self._search_error}"
        self._status_label.setText(status)

    def _count_tree_leaves(self, item: QStandardItem) -> int:
        count = 0
        for index in range(item.rowCount()):
            child = item.child(index)
            if child.data(Qt.ItemDataRole.UserRole) is not None:
                count += 1
            else:
                count += self._count_tree_leaves(child)
        return count

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("セルをコピー", self._copy_cell)
        menu.addAction("行をコピー", self._copy_row)
        if self._current_config and "id_goal" in self._current_config.custom_copy_actions:
            menu.addAction("ID+学修目標のコピー", self._copy_id_and_goal)
        menu.addSeparator()
        menu.addAction("PDFを開く", self._open_pdf_for_selection)
        menu.exec(self._table_view.viewport().mapToGlobal(pos))

    def _show_tree_context_menu(self, pos):
        index = self._tree_view.indexAt(pos)
        if not index.isValid():
            return
        menu = QMenu(self)
        menu.addAction("テキストをコピー", self._copy_tree_text)
        record = index.data(Qt.ItemDataRole.UserRole)
        if record is not None:
            if self._current_config and "id_goal" in self._current_config.custom_copy_actions:
                menu.addAction("ID+学修目標のコピー", self._copy_tree_id_and_goal)
            menu.addSeparator()
            menu.addAction("PDFを開く", lambda: self._open_pdf_for_record(record))
        menu.exec(self._tree_view.viewport().mapToGlobal(pos))

    def _on_tree_double_click(self, index: QModelIndex):
        record = index.data(Qt.ItemDataRole.UserRole)
        if record is not None:
            self._open_pdf_for_record(record)

    def _open_pdf_for_record(self, record: Record):
        config = self._current_config
        if not config:
            return
        pdf_file = record.get(config.pdf_file_field)
        pdf_page = record.get(config.pdf_page_field)
        if pdf_file and pdf_page:
            self.statusBar().showMessage(f"PDF を開いています: {pdf_file}, p.{pdf_page}", 3000)
            dialog = open_pdf_at_page(pdf_file, pdf_page, parent=self)
            if dialog is None:
                return
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self._pdf_dialogs.add(dialog)
            dialog.destroyed.connect(lambda _=None, dlg=dialog: self._pdf_dialogs.discard(dlg))
            dialog.show()

    def _copy_tree_text(self):
        index = self._tree_view.currentIndex()
        if index.isValid():
            QApplication.clipboard().setText(str(index.data(Qt.ItemDataRole.DisplayRole)))
            self.statusBar().showMessage("コピーしました", 2000)

    def _copy_tree_id_and_goal(self):
        indexes = self._tree_view.selectionModel().selectedIndexes()
        if not indexes:
            return
        config = self._current_config
        if not config:
            return
        col_def = config.columns[0]
        lines = []
        seen = set()
        for index in indexes:
            row_key = (index.row(), index.parent().internalId())
            if row_key in seen:
                continue
            seen.add(row_key)
            record = index.data(Qt.ItemDataRole.UserRole)
            if record is None:
                continue
            raw_value = record.get(col_def.key, "")
            id_value = col_def.display(record, raw_value) if col_def.display is not None else str(raw_value)
            goal_value = record.get("goal_text", "")
            lines.append(f"{id_value} {goal_value}")
        if lines:
            QApplication.clipboard().setText("\n".join(lines))
            self.statusBar().showMessage(f"{len(lines)} 件をコピーしました", 2000)

    def _copy_cell(self):
        index = self._table_view.currentIndex()
        if index.isValid():
            QApplication.clipboard().setText(str(index.data(Qt.ItemDataRole.DisplayRole)))
            self.statusBar().showMessage("コピーしました", 2000)

    def _copy_row(self):
        rows = sorted({index.row() for index in self._table_view.selectionModel().selectedIndexes()})
        if not rows:
            return
        lines = []
        for row in rows:
            columns = []
            for column in range(self._proxy_model.columnCount()):
                if self._table_view.isColumnHidden(column):
                    continue
                index = self._proxy_model.index(row, column)
                columns.append(str(index.data(Qt.ItemDataRole.DisplayRole)))
            lines.append("\t".join(columns))
        QApplication.clipboard().setText("\n".join(lines))
        self.statusBar().showMessage(f"{len(rows)} 行をコピーしました", 2000)

    def _copy_id_and_goal(self):
        rows = sorted({index.row() for index in self._table_view.selectionModel().selectedIndexes()})
        if not rows:
            return
        lines = []
        for row in rows:
            id_value = str(self._proxy_model.index(row, 0).data(Qt.ItemDataRole.DisplayRole))
            record: Record = self._proxy_model.index(row, 0).data(Qt.ItemDataRole.UserRole)
            goal_value = record.get("goal_text", "") if record is not None else ""
            lines.append(f"{id_value} {goal_value}")
        QApplication.clipboard().setText("\n".join(lines))
        self.statusBar().showMessage(f"{len(rows)} 件をコピーしました", 2000)

    def _on_double_click(self, index: QModelIndex):
        self._open_pdf_for_index(index)

    def _open_pdf_for_selection(self):
        index = self._table_view.currentIndex()
        if index.isValid():
            self._open_pdf_for_index(index)

    def _open_pdf_for_index(self, index: QModelIndex):
        source_index = self._proxy_model.mapToSource(index)
        record = self._source_model.get_record(source_index.row())
        if record:
            self._open_pdf_for_record(record)
