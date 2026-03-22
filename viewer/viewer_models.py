"""テーブル表示・フィルタリング用モデル"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

from data_loader import Record
from dataset_config import DatasetConfig


class GenericTableModel(QAbstractTableModel):
    """Record のリストを DatasetConfig に基づいて表示するモデル"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: list[Record] = []
        self._config: DatasetConfig | None = None

    def set_config(self, config: DatasetConfig):
        self._config = config

    def rowCount(self, parent=QModelIndex()):
        return len(self._records)

    def columnCount(self, parent=QModelIndex()):
        if self._config is None:
            return 0
        return len(self._config.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self._config is None:
            return None
        record = self._records[index.row()]
        col_def = self._config.columns[index.column()]
        value = record.get(col_def.key)

        if role == Qt.ItemDataRole.DisplayRole:
            if col_def.display is not None:
                return col_def.display(record, value)
            return value
        if role == Qt.ItemDataRole.UserRole:
            return record
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(value) if value is not None else ""
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_def.align == "left":
                return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if self._config and 0 <= section < len(self._config.columns):
                return self._config.columns[section].header
        return None

    def set_records(self, records: list[Record]):
        self.beginResetModel()
        self._records = records
        self.endResetModel()

    def get_record(self, row: int) -> Record | None:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None


class GenericFilterProxyModel(QSortFilterProxyModel):
    """テキスト検索 + カスケードフィルタ + ソートを DatasetConfig ベースで管理"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_matcher: Callable[[str], bool] | None = None
        self._filters: dict[str, str] = {}
        self._config: DatasetConfig | None = None

    def set_config(self, config: DatasetConfig):
        self._config = config

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            base = super().headerData(section, orientation, role)
            if base and section == self.sortColumn():
                arrow = " ▲" if self.sortOrder() == Qt.SortOrder.AscendingOrder else " ▼"
                return str(base) + arrow
            return base
        return super().headerData(section, orientation, role)

    def set_search_matcher(self, matcher: Callable[[str], bool] | None):
        self._search_matcher = matcher
        self.invalidateRowsFilter()

    def set_filter(self, code_field: str, value: str):
        self._filters[code_field] = value
        self.invalidateRowsFilter()

    def clear_filters(self):
        self._filters.clear()
        self.invalidateRowsFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        record: Record = model.data(model.index(source_row, 0), Qt.ItemDataRole.UserRole)
        if record is None:
            return False

        for field, value in self._filters.items():
            if value and record.get(field) != value:
                return False

        if self._search_matcher is not None:
            searchable = " ".join(
                str(model.data(model.index(source_row, col), Qt.ItemDataRole.DisplayRole) or "")
                for col in range(model.columnCount())
            ).lower()
            if not self._search_matcher(searchable):
                return False

        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        if self._config is None:
            return super().lessThan(left, right)

        source = self.sourceModel()
        col = left.column()
        if 0 <= col < len(self._config.columns):
            col_def = self._config.columns[col]
            if col_def.sort_key is not None:
                left_record = source.data(left, Qt.ItemDataRole.UserRole)
                right_record = source.data(right, Qt.ItemDataRole.UserRole)
                if left_record is not None and right_record is not None:
                    return col_def.sort_key(left_record) < col_def.sort_key(right_record)

        left_data = str(source.data(left, Qt.ItemDataRole.DisplayRole) or "")
        right_data = str(source.data(right, Qt.ItemDataRole.DisplayRole) or "")
        return left_data < right_data
