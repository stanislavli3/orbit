#!/usr/bin/env python3
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.formula import Tokenizer


REQUIRED_SHEETS = [
    "BOM Summary",
    "Supplier Comparison",
    "Assumptions & Inputs",
    "Research Log",
    "Risk Matrix",
]


def validate_workbook(path: Path) -> list[str]:
    errors: list[str] = []
    workbook = load_workbook(path, data_only=False)
    try:
        missing = [sheet for sheet in REQUIRED_SHEETS if sheet not in workbook.sheetnames]
        if missing:
            errors.append(f"Missing sheets: {', '.join(missing)}")

        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    value = cell.value
                    if not isinstance(value, str):
                        continue
                    if value.startswith("="):
                        try:
                            Tokenizer(value)
                        except Exception as exc:
                            errors.append(f"{sheet.title}!{cell.coordinate}: invalid formula ({exc})")
                    elif value.startswith("#") and value.endswith("!"):
                        errors.append(f"{sheet.title}!{cell.coordinate}: cached Excel error literal {value}")
    finally:
        workbook.close()

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: scripts/recalc.py <workbook.xlsx>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    if not path.exists():
        print(f"Workbook not found: {path}", file=sys.stderr)
        return 2

    errors = validate_workbook(path)
    if errors:
        print("Formula validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Workbook validation passed with zero formula errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
