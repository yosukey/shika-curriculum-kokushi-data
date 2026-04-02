"""データセット設定 — 列定義・階層・フィルタ・テーマをルールとして記述する"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# ユーティリティ関数（表示変換用）
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 設定データクラス
# ---------------------------------------------------------------------------

@dataclass
class ColumnDef:
    """テーブルの1列の定義"""
    key: str                                    # Recordのフィールド名
    header: str                                 # ヘッダー表示名
    hidden: bool = False                        # テーブルで非表示にするか
    width: int = 100                            # デフォルト列幅
    stretch: bool = False                       # Stretch列か
    align: str = "center"                       # "left" | "center"
    display: Callable[[Any, Any], str] | None = None   # (record, value) -> str
    sort_key: Callable[[Any], Any] | None = None       # (record) -> comparable


@dataclass
class HierarchyLevel:
    """ツリービューの1階層の定義"""
    code_field: str             # コードのフィールド名
    title_field: str            # タイトルのフィールド名
    label: Callable[[Any], str] | None = None  # ラベル関数 (record) -> str
    allow_null: bool = False    # Trueなら、コードがNullの場合スキップして親に直接追加
    sort_key: Callable[[Any], Any] | None = None  # グループキーのソート関数 (code) -> comparable


@dataclass
class FilterDef:
    """カスケードフィルタの1段の定義"""
    code_field: str          # フィルタ対象のフィールド名
    label: str               # UIラベル (例: "大項目")
    title_field: str = ""    # コンボ表示用タイトルのフィールド名（省略時はコード値をそのまま表示）
    min_width: int = 250
    sort_key: Callable[[Any], Any] | None = None  # コードのソート関数 (code) -> comparable


@dataclass
class FieldMapping:
    """JSONLのネストされたパスからフラットなフィールドへのマッピング"""
    field_name: str     # フラットなフィールド名
    json_path: str      # ドット区切りのJSONパス (例: "dai.code")
    default: Any = None # 値がない場合のデフォルト値
    convert: Callable[[Any], Any] | None = None  # 型変換関数


@dataclass
class DatasetConfig:
    """1つのデータセットの全設定"""
    name: str                               # UI表示名
    filename: str                           # JSONLファイル名
    theme: dict[str, str]                   # テーマカラー
    columns: list[ColumnDef] = field(default_factory=list)
    hierarchy: list[HierarchyLevel] = field(default_factory=list)
    leaf_label: Callable[[Any], str] | None = None  # リーフノードのラベル関数
    leaf_remarks: Callable[[Any], str] | None = None  # ツリービューのリーフに表示する備考テキスト関数
    field_mappings: list[FieldMapping] = field(default_factory=list)
    filters: list[FilterDef] = field(default_factory=list)
    pdf_file_field: str = "pdf_file"
    pdf_page_field: str = "pdf_page"
    default_sort_column: int = 0            # テーブルビューのデフォルトソート列インデックス
    custom_copy_actions: list[str] = field(default_factory=list)  # カスタムコピーアクション識別子
    source_urls: list[tuple[str, str]] = field(default_factory=list)  # (ラベル, URL) 原典リンク一覧


# ---------------------------------------------------------------------------
# ソートキーユーティリティ
# ---------------------------------------------------------------------------

def _code_sort_key(code: str):
    """コード文字列のソートキー。カッコ内数字を数値として比較する"""
    if not code:
        return []
    parts = re.split(r'[-()]', code)
    result = []
    for p in parts:
        if not p:
            continue
        try:
            result.append((0, int(p)))
        except ValueError:
            result.append((1, p))
    return result


# ---------------------------------------------------------------------------
# R4 設定
# ---------------------------------------------------------------------------

def _r4_dai_title_display(r: Any, v: Any) -> str:
    return f"{r['dai_code']} {v}"


def _r4_chu_title_display(r: Any, v: Any) -> str:
    return f"{r['chu_code']} {v}"


def _r4_sho_title_display(r: Any, v: Any) -> str:
    sho_code = r.get("sho_code") or ""
    return f"{sho_code} {v}" if v else sho_code


def _r4_sub_sho_title_display(r: Any, v: Any) -> str:
    sub_sho_code = r.get("sub_sho_code") or ""
    return f"{sub_sho_code} {v}" if v else sub_sho_code


def _r4_sub_sub_sho_title_display(r: Any, v: Any) -> str:
    sub_sub_sho_code = r.get("sub_sub_sho_code") or ""
    return f"{sub_sub_sho_code} {v}" if v else sub_sub_sho_code


def _r4_goal_text_display(r: Any, v: Any) -> str:
    return f"{r['goal_code']} {v}"


def _r4_id_sort(r: Any) -> Any:
    return _code_sort_key(r["id"])


def _r4_chu_title_sort(r: Any) -> Any:
    try:
        return int(r["chu_code"])
    except (ValueError, TypeError):
        return 0


def _r4_sho_sort(r: Any) -> Any:
    return _code_sort_key(r.get("sho_code") or "")


def _r4_sub_sho_sort(r: Any) -> Any:
    return _code_sort_key(r.get("sub_sho_code") or "")


def _r4_sub_sub_sho_sort(r: Any) -> Any:
    return _code_sort_key(r.get("sub_sub_sho_code") or "")


def _r4_goal_text_sort(r: Any) -> Any:
    try:
        return int(r["goal_code"])
    except (ValueError, TypeError):
        return 0


def _r4_leaf_label(r: Any) -> str:
    return f"{r['goal_code']} {r['goal_text']}"


R4_CONFIG = DatasetConfig(
    name="コアカリ（R4年度版）",
    filename="data/shika_corecurriculum_r4_goals.jsonl",
    theme={
        "header_bg": "#2471A3",
        "header_fg": "#FFFFFF",
        "alt_row": "#F0F7FD",
        "selection": "#AED6F1",
        "hover": "#D6EAF8",
    },
    columns=[
        ColumnDef(key="id", header="ID", width=80, align="left",
                  sort_key=_r4_id_sort),
        ColumnDef(key="dai_code", header="大項目ID", hidden=True, width=55),
        ColumnDef(key="dai_title", header="大項目", width=220, align="left",
                  display=_r4_dai_title_display),
        ColumnDef(key="chu_code", header="中項目ID", hidden=True, width=55),
        ColumnDef(key="chu_title", header="中項目", width=200, align="left",
                  display=_r4_chu_title_display,
                  sort_key=_r4_chu_title_sort),
        ColumnDef(key="sho_code", header="小項目ID", hidden=True, width=65),
        ColumnDef(key="sho_title", header="小項目", width=220, align="left",
                  display=_r4_sho_title_display,
                  sort_key=_r4_sho_sort),
        ColumnDef(key="sub_sho_code", header="サブ小項目ID", hidden=True, width=65),
        ColumnDef(key="sub_sho_title", header="サブ小項目", width=220, align="left",
                  display=_r4_sub_sho_title_display,
                  sort_key=_r4_sub_sho_sort),
        ColumnDef(key="sub_sub_sho_code", header="サブサブ小項目ID", hidden=True, width=65),
        ColumnDef(key="sub_sub_sho_title", header="サブサブ小項目", width=220, align="left",
                  display=_r4_sub_sub_sho_title_display,
                  sort_key=_r4_sub_sub_sho_sort),
        ColumnDef(key="goal_code", header="目標番号", hidden=True, width=70),
        ColumnDef(key="goal_text", header="学修目標", width=400, stretch=True,
                  align="left", display=_r4_goal_text_display,
                  sort_key=_r4_goal_text_sort),
        ColumnDef(key="pdf_page", header="ページ", hidden=True, width=55),
    ],
    hierarchy=[
        HierarchyLevel(
            code_field="dai_code", title_field="dai_title",
            label=lambda r: f"{r['dai_code']} {r['dai_title']}",
        ),
        HierarchyLevel(
            code_field="chu_code", title_field="chu_title",
            label=lambda r: f"{r['chu_code']} {r['chu_title']}",
        ),
        HierarchyLevel(
            code_field="sho_code", title_field="sho_title",
            label=lambda r: (
                f"{r['sho_code']} {r['sho_title']}"
                if r.get("sho_title")
                else r.get("sho_code") or ""
            ),
            allow_null=True,
        ),
        HierarchyLevel(
            code_field="sub_sho_code", title_field="sub_sho_title",
            label=lambda r: (
                f"{r['sub_sho_code']} {r['sub_sho_title']}"
                if r.get("sub_sho_title")
                else r.get("sub_sho_code") or ""
            ),
            allow_null=True,
        ),
        HierarchyLevel(
            code_field="sub_sub_sho_code", title_field="sub_sub_sho_title",
            label=lambda r: (
                f"{r['sub_sub_sho_code']} {r['sub_sub_sho_title']}"
                if r.get("sub_sub_sho_title")
                else r.get("sub_sub_sho_code") or ""
            ),
            allow_null=True,
        ),
    ],
    leaf_label=_r4_leaf_label,
    field_mappings=[
        FieldMapping("id", "id"),
        FieldMapping("dai_code", "dai.code"),
        FieldMapping("dai_title", "dai.title"),
        FieldMapping("chu_code", "chu.code"),
        FieldMapping("chu_title", "chu.title"),
        FieldMapping("sho_code", "sho.code"),
        FieldMapping("sho_title", "sho.title", default=""),
        FieldMapping("sub_sho_code", "sub_sho.code"),
        FieldMapping("sub_sho_title", "sub_sho.title", default=""),
        FieldMapping("sub_sub_sho_code", "sub_sub_sho.code"),
        FieldMapping("sub_sub_sho_title", "sub_sub_sho.title", default=""),
        FieldMapping("goal_code", "goal.code", default="",
                     convert=lambda v: str(v) if v is not None else ""),
        FieldMapping("goal_text", "goal.text"),
        FieldMapping("pdf_file", "source.pdf"),
        FieldMapping("pdf_page", "source.page"),
    ],
    filters=[
        FilterDef(code_field="dai_code", label="大項目",
                  title_field="dai_title", min_width=250),
        FilterDef(code_field="chu_code", label="中項目",
                  title_field="chu_title", min_width=250),
    ],
    custom_copy_actions=["id_goal"],
    source_urls=[
        ("歯学教育モデル・コア・カリキュラム（R4, H28）",
         "https://www.mext.go.jp/a_menu/koutou/iryou/mext_00009.html"),
    ],
)


# ---------------------------------------------------------------------------
# H28 設定
# ---------------------------------------------------------------------------

def _h28_goal_text_display(r: Any, v: Any) -> str:
    return f"{r['goal_display_code']} {v}"


def _h28_id_sort(r: Any) -> Any:
    id_str = r["id"]
    prefix, _ = id_str.rsplit("-", 1)
    goal_code = r["goal_code"]
    return (_code_sort_key(prefix), int(goal_code) if goal_code.isdigit() else 0)


def _h28_goal_text_sort(r: Any) -> Any:
    return int(r["goal_code"]) if r["goal_code"].isdigit() else 0


def _h28_leaf_label(r: Any) -> str:
    return f"{r['goal_display_code']} {r['goal_text']}"


def _h28_goal_section_display(r: Any, v: Any) -> str:
    code = r.get("goal_section_display_code") or ""
    return f"{code} {v}" if code and v else v or ""


def _h28_goal_section_sort(r: Any) -> Any:
    code = r.get("goal_section_code") or ""
    return int(code) if code.isdigit() else 0


def _h28_sho_title_display(r: Any, v: Any) -> str:
    sho_display_code = r.get("sho_display_code") or r.get("sho_code") or ""
    return f"{sho_display_code} {v}" if v else sho_display_code


H28_CONFIG = DatasetConfig(
    name="コアカリ（H28年度版）",
    filename="data/shika_corecurriculum_h28_goals.jsonl",
    theme={
        "header_bg": "#A04000",
        "header_fg": "#FFFFFF",
        "alt_row": "#FDF6EE",
        "selection": "#F5CBA7",
        "hover": "#FDEBD0",
    },
    columns=[
        ColumnDef(key="id", header="ID", width=80, align="left",
                  sort_key=_h28_id_sort),
        ColumnDef(key="dai_code", header="大項目ID", hidden=True, width=55),
        ColumnDef(key="dai_title", header="大項目", width=220, align="left",
                  display=_r4_dai_title_display),  # R4と同じ
        ColumnDef(key="chu_code", header="中項目ID", hidden=True, width=55),
        ColumnDef(key="chu_title", header="中項目", width=200, align="left",
                  display=_r4_chu_title_display,    # R4と同じ
                  sort_key=_r4_chu_title_sort),
        ColumnDef(key="sho_code", header="小項目ID", hidden=True, width=65),
        ColumnDef(key="sho_title", header="小項目", width=220, align="left",
                  display=_h28_sho_title_display,
                  sort_key=_r4_sho_sort),
        ColumnDef(key="goal_section_code", header="目標区分ID", hidden=True, width=65),
        ColumnDef(key="goal_section_display_code", header="目標区分表示ID", hidden=True, width=65),
        ColumnDef(key="goal_section", header="学習目標項目", width=200,
                  align="left", display=_h28_goal_section_display,
                  sort_key=_h28_goal_section_sort),
        ColumnDef(key="goal_code", header="目標番号", hidden=True, width=70),
        ColumnDef(key="goal_display_code", header="目標表示番号", hidden=True, width=70),
        ColumnDef(key="goal_text", header="学修目標", width=400, stretch=True,
                  align="left", display=_h28_goal_text_display,
                  sort_key=_h28_goal_text_sort),
        ColumnDef(key="pdf_page", header="ページ", hidden=True, width=55),
    ],
    hierarchy=[
        HierarchyLevel(
            code_field="dai_code", title_field="dai_title",
            label=lambda r: f"{r['dai_code']} {r['dai_title']}",
        ),
        HierarchyLevel(
            code_field="chu_code", title_field="chu_title",
            label=lambda r: f"{r['chu_code']} {r['chu_title']}",
        ),
        HierarchyLevel(
            code_field="sho_code", title_field="sho_title",
            label=lambda r: (
                f"{r.get('sho_display_code') or r['sho_code']} {r['sho_title']}"
                if r.get("sho_title")
                else r.get("sho_display_code") or r.get("sho_code") or ""
            ),
            allow_null=True,
        ),
        HierarchyLevel(
            code_field="goal_section_code", title_field="goal_section",
            label=lambda r: (
                f"{r['goal_section_display_code']} {r['goal_section']}"
                if r.get("goal_section")
                else ""
            ),
            allow_null=True,
        ),
    ],
    leaf_label=_h28_leaf_label,
    field_mappings=[
        FieldMapping("id", "id"),
        FieldMapping("dai_code", "dai.code"),
        FieldMapping("dai_title", "dai.title"),
        FieldMapping("chu_code", "chu.code"),
        FieldMapping("chu_title", "chu.title"),
        FieldMapping("sho_code", "sho.code"),
        FieldMapping("sho_display_code", "sho.display_code", default=""),
        FieldMapping("sho_title", "sho.title", default=""),
        FieldMapping("goal_section_code", "goal_section.code", default=None),
        FieldMapping("goal_section_display_code", "goal_section.display_code", default=""),
        FieldMapping("goal_section", "goal_section.title", default=""),
        FieldMapping("goal_code", "goal.code", default="",
                     convert=lambda v: str(v) if v is not None else ""),
        FieldMapping("goal_display_code", "goal.display_code", default=""),
        FieldMapping("goal_text", "goal.text"),
        FieldMapping("pdf_file", "source.pdf"),
        FieldMapping("pdf_page", "source.page"),
    ],
    filters=[
        FilterDef(code_field="dai_code", label="大項目",
                  title_field="dai_title", min_width=250),
        FilterDef(code_field="chu_code", label="中項目",
                  title_field="chu_title", min_width=250),
    ],
    custom_copy_actions=["id_goal"],
)


# ---------------------------------------------------------------------------
# 国試出題基準 R5 設定
# ---------------------------------------------------------------------------

# ローマ数字 → 整数 のマッピング（ソート用）
_ROMAN_TO_INT: dict[str, int] = {
    "Ⅰ": 1, "Ⅱ": 2, "Ⅲ": 3, "Ⅳ": 4, "Ⅴ": 5,
    "Ⅵ": 6, "Ⅶ": 7, "Ⅷ": 8,
}


def _kokushi_domain_sort_key(code: Any) -> tuple:
    """domainの表示値を正しい順（必修→総論→各論）でソートするキー"""
    s = str(code) if code is not None else ""
    if s == "必修":
        return (0, 0)
    prefix_order = {"総論": 1, "各論": 2}
    for prefix, major in prefix_order.items():
        if s.startswith(prefix):
            for roman, n in _ROMAN_TO_INT.items():
                if roman in s:
                    return (major, n)
            return (major, 99)
    return (99, s)


def _kokushi_id_sort(r: Any) -> Any:
    id_str = r.get("id", "")
    # プレフィックスは H, S1-S8, K1-K5 の形式
    prefix = id_str.split("-")[0] if id_str else ""
    kind = prefix[0] if prefix else ""
    num = int(prefix[1:]) if len(prefix) > 1 and prefix[1:].isdigit() else 0
    kind_order = {"H": 0, "S": 1, "K": 2}
    return [kind_order.get(kind, 99), num] + _code_sort_key(id_str)


def _kokushi_dai_title_display(r: Any, v: Any) -> str:
    code = r.get("dai_code", "")
    return f"{code} {v}"


def _kokushi_chu_title_display(r: Any, v: Any) -> str:
    return f"{r.get('chu_code', '')} {v}"


def _kokushi_sho_title_display(r: Any, v: Any) -> str:
    sho_code = r.get("sho_code", "")
    return f"{sho_code} {v}" if v else sho_code


def _kokushi_leaf_label(r: Any) -> str:
    sho_code = r.get("sho_code", "")
    title = r.get("sho_title", "")
    return f"{sho_code} {title}" if title else sho_code


KOKUSHI_R5_CONFIG = DatasetConfig(
    name="国試出題基準（R5年度版）",
    filename="data/shika_kokushi_r5_kijun.jsonl",
    theme={
        "header_bg": "#1E8449",
        "header_fg": "#FFFFFF",
        "alt_row": "#EAFAF1",
        "selection": "#ABEBC6",
        "hover": "#D5F5E3",
    },
    columns=[
        ColumnDef(key="id", header="ID", width=90, align="left",
                  sort_key=_kokushi_id_sort),
        ColumnDef(key="domain", header="領域", width=60, align="center",
                  sort_key=lambda r: _kokushi_domain_sort_key(r.get("domain", ""))),
        ColumnDef(key="dai_code", header="大項目ID", hidden=True, width=55),
        ColumnDef(key="dai_title", header="大項目", width=240, align="left",
                  display=_kokushi_dai_title_display),
        ColumnDef(key="chu_code", header="中項目ID", hidden=True, width=55),
        ColumnDef(key="chu_title", header="中項目", width=200, align="left",
                  display=_kokushi_chu_title_display),
        ColumnDef(key="sho_code", header="小項目ID", hidden=True, width=65),
        ColumnDef(key="sho_title", header="小項目", width=400, stretch=True,
                  align="left", display=_kokushi_sho_title_display),
        ColumnDef(key="remarks", header="備考", width=150, align="left"),
        ColumnDef(key="pdf_page", header="ページ", hidden=True, width=55),
    ],
    hierarchy=[
        HierarchyLevel(
            code_field="domain", title_field="domain",
            label=lambda r: r["domain"],
            sort_key=_kokushi_domain_sort_key,
        ),
        HierarchyLevel(
            code_field="dai_code", title_field="dai_title",
            label=lambda r: f"{r['dai_code']} {r['dai_title']}",
        ),
        HierarchyLevel(
            code_field="chu_code", title_field="chu_title",
            label=lambda r: f"{r['chu_code']} {r['chu_title']}",
        ),
    ],
    leaf_label=_kokushi_leaf_label,
    leaf_remarks=lambda r: r.get("remarks", ""),
    field_mappings=[
        FieldMapping("id", "id"),
        FieldMapping("domain", "domain.title"),
        FieldMapping("dai_code", "dai.code"),
        FieldMapping("dai_title", "dai.title"),
        FieldMapping("chu_code", "chu.code"),
        FieldMapping("chu_title", "chu.title"),
        FieldMapping("sho_code", "sho.code"),
        FieldMapping("sho_title", "sho.title", default=""),
        FieldMapping("remarks", "remarks", default=""),
        FieldMapping("pdf_file", "source.pdf"),
        FieldMapping("pdf_page", "source.page"),
    ],
    filters=[
        FilterDef(code_field="domain", label="領域",
                  min_width=120,
                  sort_key=_kokushi_domain_sort_key),
        FilterDef(code_field="dai_code", label="大項目",
                  title_field="dai_title", min_width=250),
        FilterDef(code_field="chu_code", label="中項目",
                  title_field="chu_title", min_width=250),
    ],
    source_urls=[
        ("歯科医師国家試験出題基準（令和5年版）",
         "https://www.mhlw.go.jp/stf/shingi2/0000163627_00002.html"),
    ],
)


# ---------------------------------------------------------------------------
# 国試出題基準 R9 設定
# ---------------------------------------------------------------------------

KOKUSHI_R9_CONFIG = DatasetConfig(
    name="国試出題基準（R9年度版）",
    filename="data/shika_kokushi_r9_kijun.jsonl",
    theme={
        "header_bg": "#6C3483",
        "header_fg": "#FFFFFF",
        "alt_row": "#F5EEF8",
        "selection": "#D2B4DE",
        "hover": "#E8DAEF",
    },
    columns=[
        ColumnDef(key="id", header="ID", width=90, align="left",
                  sort_key=_kokushi_id_sort),
        ColumnDef(key="domain", header="領域", width=60, align="center",
                  sort_key=lambda r: _kokushi_domain_sort_key(r.get("domain", ""))),
        ColumnDef(key="dai_code", header="大項目ID", hidden=True, width=55),
        ColumnDef(key="dai_title", header="大項目", width=240, align="left",
                  display=_kokushi_dai_title_display),
        ColumnDef(key="chu_code", header="中項目ID", hidden=True, width=55),
        ColumnDef(key="chu_title", header="中項目", width=200, align="left",
                  display=_kokushi_chu_title_display),
        ColumnDef(key="sho_code", header="小項目ID", hidden=True, width=65),
        ColumnDef(key="sho_title", header="小項目", width=400, stretch=True,
                  align="left", display=_kokushi_sho_title_display),
        ColumnDef(key="remarks", header="備考", width=150, align="left"),
        ColumnDef(key="pdf_page", header="ページ", hidden=True, width=55),
    ],
    hierarchy=[
        HierarchyLevel(
            code_field="domain", title_field="domain",
            label=lambda r: r["domain"],
            sort_key=_kokushi_domain_sort_key,
        ),
        HierarchyLevel(
            code_field="dai_code", title_field="dai_title",
            label=lambda r: f"{r['dai_code']} {r['dai_title']}",
        ),
        HierarchyLevel(
            code_field="chu_code", title_field="chu_title",
            label=lambda r: f"{r['chu_code']} {r['chu_title']}",
        ),
    ],
    leaf_label=_kokushi_leaf_label,
    leaf_remarks=lambda r: r.get("remarks", ""),
    field_mappings=[
        FieldMapping("id", "id"),
        FieldMapping("domain", "domain.title"),
        FieldMapping("dai_code", "dai.code"),
        FieldMapping("dai_title", "dai.title"),
        FieldMapping("chu_code", "chu.code"),
        FieldMapping("chu_title", "chu.title"),
        FieldMapping("sho_code", "sho.code"),
        FieldMapping("sho_title", "sho.title", default=""),
        FieldMapping("remarks", "remarks", default=""),
        FieldMapping("pdf_file", "source.pdf"),
        FieldMapping("pdf_page", "source.page"),
    ],
    filters=[
        FilterDef(code_field="domain", label="領域",
                  min_width=120,
                  sort_key=_kokushi_domain_sort_key),
        FilterDef(code_field="dai_code", label="大項目",
                  title_field="dai_title", min_width=250),
        FilterDef(code_field="chu_code", label="中項目",
                  title_field="chu_title", min_width=250),
    ],
    source_urls=[
        ("歯科医師国家試験出題基準（令和9年版）",
         "https://www.mhlw.go.jp/stf/shingi2/0000163627_00005.html"),
    ],
)


# ---------------------------------------------------------------------------
# 全データセット設定リスト
# ---------------------------------------------------------------------------

ALL_DATASETS: list[DatasetConfig] = [R4_CONFIG, H28_CONFIG, KOKUSHI_R5_CONFIG, KOKUSHI_R9_CONFIG]
