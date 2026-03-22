#!/usr/bin/env python3
"""CSV → JSONL 変換: shika_corecurriculum_h28_goals"""

import csv
import json
import os
import sys


def _build_sho_path(sho_code: str, sho_display_code: str, sho_title: str) -> list[dict]:
    """sho_code, sho_display_code, sho_title から sho.path を復元
    H28 の path 要素には display_code あり
    """
    if not sho_code:
        return []

    return [{
        "code": sho_code,
        "display_code": sho_display_code or "",
        "title": sho_title or "",
    }]


def convert(csv_path: str, jsonl_path: str) -> None:
    """CSVファイルをJSONLファイルに変換"""
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        lines = []
        for row in reader:
            sho_code = row["sho_code"] if row["sho_code"] else None
            sho_display_code = row["sho_display_code"] if row["sho_display_code"] else None
            sho_title = row["sho_title"]
            path = _build_sho_path(
                row["sho_code"], row["sho_display_code"], sho_title
            )

            sho = {"code": sho_code}
            if sho_display_code is not None:
                sho["display_code"] = sho_display_code
            else:
                sho["display_code"] = None
            sho["title"] = sho_title
            sho["path"] = path

            # goal_section
            gs_code = row["goal_section_code"]
            gs_display_code = row["goal_section_display_code"]
            gs_title = row["goal_section"]
            if gs_code:
                goal_section = {
                    "code": gs_code,
                    "display_code": gs_display_code,
                    "title": gs_title,
                }
            else:
                goal_section = {
                    "code": None,
                    "display_code": None,
                    "title": None,
                }

            obj = {
                "id": row["id"],
                "dai": {
                    "code": row["dai_code"],
                    "title": row["dai_title"],
                },
                "chu": {
                    "code": row["chu_code"],
                    "title": row["chu_title"],
                },
                "sho": sho,
                "goal_section": goal_section,
                "goal": {
                    "code": row["goal_code"],
                    "display_code": row["goal_display_code"],
                    "text": row["goal_text"],
                },
                "source": {
                    "pdf": row["source_pdf"],
                    "page": int(row["source_page"]),
                },
            }
            lines.append(json.dumps(obj, ensure_ascii=False))

    with open(jsonl_path, "w", encoding="utf-8", newline="\n") as f:
        for line in lines:
            f.write(line + "\n")


def main() -> None:
    import argparse

    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)

    parser = argparse.ArgumentParser(description="CSV → JSONL 変換: H28")
    parser.add_argument(
        "--csv",
        default=os.path.join(base_dir, "shika_corecurriculum_h28_goals.csv"),
    )
    parser.add_argument(
        "--out",
        default=os.path.join(base_dir, "viewer", "data", "shika_corecurriculum_h28_goals.jsonl"),
    )
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    convert(args.csv, args.out)
    print(f"Converted: {args.csv} -> {args.out}")


if __name__ == "__main__":
    main()
