#!/usr/bin/env python3
"""CSV → JSONL 変換: shika_kokushi_r5_kijun"""

import csv
import json
import os
import sys


def convert(csv_path: str, jsonl_path: str) -> None:
    """CSVファイルをJSONLファイルに変換"""
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        lines = []
        for row in reader:
            obj = {
                "id": row["id"],
                "domain": {
                    "code": row["domain_code"],
                    "title": row["domain_title"],
                },
                "dai": {
                    "code": row["dai_code"],
                    "title": row["dai_title"],
                },
                "chu": {
                    "code": row["chu_code"],
                    "title": row["chu_title"],
                },
                "sho": {
                    "code": row["sho_code"],
                    "title": row["sho_title"],
                },
                "remarks": row["remarks"],
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

    parser = argparse.ArgumentParser(description="CSV → JSONL 変換: 国試R5")
    parser.add_argument(
        "--csv",
        default=os.path.join(base_dir, "shika_kokushi_r5_kijun.csv"),
    )
    parser.add_argument(
        "--out",
        default=os.path.join(base_dir, "viewer", "data", "shika_kokushi_r5_kijun.jsonl"),
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
