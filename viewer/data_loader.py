"""汎用 JSONL データローダー"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from dataset_config import DatasetConfig, FieldMapping


# ---------------------------------------------------------------------------
# 汎用レコード型（dict ラッパー）
# ---------------------------------------------------------------------------

class Record(dict):
    """dict を継承し、属性アクセスもサポートするレコード型"""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"Record has no field '{name}'")


# ---------------------------------------------------------------------------
# JSONパス解決
# ---------------------------------------------------------------------------

def _resolve_path(obj: dict, path: str) -> Any:
    """ドット区切りパスでネストされた値を取得する"""
    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


# ---------------------------------------------------------------------------
# データ読み込み
# ---------------------------------------------------------------------------

def load_jsonl(filepath: str, config: DatasetConfig) -> list[Record]:
    """JSONLファイルを読み込み、field_mappings に基づいてフラット化し、Recordのリストを返す"""
    return _load_with_mappings(filepath, config.field_mappings)


def _load_with_mappings(
    filepath: str, mappings: list[FieldMapping]
) -> list[Record]:
    """field_mappings に基づいて JSONL をフラット化して読み込む"""
    records: list[Record] = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            rec = Record()
            for m in mappings:
                raw = _resolve_path(obj, m.json_path)
                if raw is None:
                    raw = m.default
                if m.convert is not None:
                    raw = m.convert(raw)
                rec[m.field_name] = raw
            records.append(rec)
    return records


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def get_data_dir() -> str:
    """データファイル（JSONL, PDF）が格納されているディレクトリのパスを返す"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))
