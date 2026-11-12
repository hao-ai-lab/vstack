#!/usr/bin/env python3
"""Generate Google Sheets batchUpdate payload directly from canonical bugs/verified-bugs.csv.

Usage:
    python3 scripts/sync_bugs_sheet.py --csv bugs/verified-bugs.csv --out /tmp/vstack_sheet_batch.json
    gsheets mutate raw-batch 1FL5QqgzEpja9k8Zw6GmIQDtHveddjj1coHe1MJ3Ts-Q --file /tmp/vstack_sheet_batch.json
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

SYSTEM_BG = {
    "SGLang": "#E6F4EA",
    "vLLM": "#FCE8E6",
    "FlashInfer": "#E8F0FE",
    "DeepGEMM": "#F3E8FD",
    "verl": "#FEF3C7",
    "Megatron-LM": "#DCFCE7",
}

SPEC_STYLE = {
    "Isolation": ("#FCE8E6", "#A50E0E"),
    "Conservation": ("#FEF3C7", "#92400E"),
    "Authority": ("#E0E7FF", "#3730A3"),
    "Finality": ("#E8F0FE", "#1967D2"),
    "Progress": ("#E0F2FE", "#0369A1"),
    "Invariance": ("#F3E8FD", "#681DA8"),
}

IMPACT_STYLE = {
    "Silent Corruption": ("#FCE8E6", "#A50E0E"),
    "Crash": ("#FEF7E0", "#B06000"),
    "Hang / Leak": ("#FEF7E0", "#B06000"),
    "Non-Determinism": ("#F3E8FD", "#681DA8"),
}

PRIOR_STYLE = {
    "Unknown": ("#EEF2FF", "#3730A3"),
    "Known": ("#F1F5F9", "#0F766E"),
}

STATUS_STYLE = {
    "Fixed": ("#CEEAD6", "#0D652D"),
    "Merged": ("#CEEAD6", "#0D652D"),
    "Confirmed": ("#FEF7E0", "#B06000"),
    "PR Open": ("#E8F0FE", "#1967D2"),
    "Upstream Open": ("#E0F2FE", "#0369A1"),
    "Reported": ("#E8F0FE", "#1967D2"),
    "Needs Repro": ("#FEF7E0", "#B06000"),
    "Needs Fix": ("#FEF7E0", "#B06000"),
    "On Hold": ("#F1F5F9", "#475569"),
}

COL_WIDTHS = [88, 148, 368, 112, 128, 104, 78, 126, 98, 114, 192]  # 11 cols, 1556px total


def hex_rgb(h: str) -> dict[str, float]:
    h = h.lstrip("#")
    return {
        "red": round(int(h[0:2], 16) / 255.0, 4),
        "green": round(int(h[2:4], 16) / 255.0, 4),
        "blue": round(int(h[4:6], 16) / 255.0, 4),
    }


def str_cell(
    text: str,
    *,
    bg: str = "#FFFFFF",
    fg: str = "#0F172A",
    bold: bool = False,
    align: str = "LEFT",
    font: str = "Inter",
    size: int = 10,
    wrap: str = "CLIP",
) -> dict:
    return {
        "userEnteredValue": {"stringValue": text},
        "userEnteredFormat": {
            "backgroundColor": hex_rgb(bg),
            "horizontalAlignment": align,
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": wrap,
            "padding": {"top": 5, "bottom": 5, "left": 8, "right": 8},
            "textFormat": {
                "foregroundColor": hex_rgb(fg),
                "fontFamily": font,
                "fontSize": size,
                "bold": bold,
            },
        },
    }


def link_cell(
    url: str,
    label: str,
    *,
    bg: str = "#FFFFFF",
    fg: str = "#1967D2",
) -> dict:
    return {
        "userEnteredValue": {"formulaValue": f'=HYPERLINK("{url}", "{label}")'},
        "userEnteredFormat": {
            "backgroundColor": hex_rgb(bg),
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "CLIP",
            "padding": {"top": 5, "bottom": 5, "left": 8, "right": 8},
            "textFormat": {
                "foregroundColor": hex_rgb(fg),
                "fontFamily": "Inter",
                "fontSize": 10,
                "bold": True,
                "underline": True,
            },
        },
    }


def verifier_cell(raw: str) -> dict:
    val = raw.strip()
    if not val or val.lower() == "unverified":
        return str_cell("Unverified", bg="#F1F5F9", fg="#64748B", bold=True, align="CENTER")
    if val.startswith("@") and "," not in val and " " not in val:
        handle = val[1:]
        return link_cell(f"https://github.com/{handle}", val, bg="#CEEAD6", fg="#0D652D")
    return str_cell(val, bg="#CEEAD6", fg="#0D652D", bold=True, align="CENTER")


def build_payload(csv_path: Path, sheet_id: int = 0, old_cond_rules_count: int = 29) -> dict:
    headers = [
        ("System", "LEFT"),
        ("Module", "LEFT"),
        ("Bug Summary", "LEFT"),
        ("Violated Spec", "CENTER"),
        ("Impact", "CENTER"),
        ("Prior Status", "CENTER"),
        ("Checker", "CENTER"),
        ("Human Verifier", "CENTER"),
        ("Upstream", "CENTER"),
        ("Status", "CENTER"),
        ("Evidence", "LEFT"),
    ]

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    grid_rows = [
        {
            "values": [
                str_cell(h_text, bg="#1F5C8B", fg="#FFFFFF", bold=True, align=h_align, size=10)
                for h_text, h_align in headers
            ]
        }
    ]

    for r in rows:
        sys_bg = SYSTEM_BG.get(r["system"], "#F8FAFC")
        sp_bg, sp_fg = SPEC_STYLE.get(r["violated_spec"], ("#F1F5F9", "#334155"))
        imp_bg, imp_fg = IMPACT_STYLE.get(r["impact"], ("#F1F5F9", "#334155"))
        prior_val = (r.get("prior_status") or "Unknown").strip()
        pr_bg, pr_fg = PRIOR_STYLE.get(prior_val, ("#F1F5F9", "#334155"))
        st_bg, st_fg = STATUS_STYLE.get(r["status"], ("#F1F5F9", "#475569"))

        up_url = (r.get("upstream_url") or "").strip()
        up_lbl = (r.get("upstream_label") or "—").strip() or "—"
        up_cell = (
            link_cell(up_url, up_lbl)
            if up_url
            else str_cell(up_lbl, bg="#FFFFFF", fg="#94A3B8", bold=False, align="CENTER")
        )

        grid_rows.append(
            {
                "values": [
                    str_cell(r["system"], bg=sys_bg, fg="#0F172A", bold=True, align="LEFT"),
                    str_cell(r["module"], bg="#FFFFFF", fg="#1E293B", bold=False, align="LEFT"),
                    str_cell(r["summary"], bg="#FFFFFF", fg="#0F172A", bold=False, align="LEFT", wrap="WRAP"),
                    str_cell(r["violated_spec"], bg=sp_bg, fg=sp_fg, bold=True, align="CENTER"),
                    str_cell(r["impact"], bg=imp_bg, fg=imp_fg, bold=True, align="CENTER"),
                    str_cell(prior_val, bg=pr_bg, fg=pr_fg, bold=True, align="CENTER"),
                    str_cell(r["checker"], bg="#F1F5F9", fg="#1E293B", bold=True, align="CENTER", font="Roboto Mono", size=9),
                    verifier_cell(r["human_verifier"]),
                    up_cell,
                    str_cell(r["status"], bg=st_bg, fg=st_fg, bold=True, align="CENTER"),
                    str_cell(r["evidence"], bg="#FFFFFF", fg="#334155", bold=False, align="LEFT", wrap="WRAP"),
                ]
            }
        )

    total_data_rows = len(grid_rows)
    total_grid_rows = max(35, total_data_rows + 15)
    num_cols = len(headers)

    requests: list[dict] = []
    for _ in range(old_cond_rules_count):
        requests.append({"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": 0}})
    requests.append({"clearBasicFilter": {"sheetId": sheet_id}})

    requests.extend(
        [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "title": "Verified Bugs",
                        "gridProperties": {
                            "rowCount": total_grid_rows,
                            "columnCount": num_cols,
                            "frozenRowCount": 1,
                            "frozenColumnCount": 1,
                        },
                        "tabColorStyle": {"rgbColor": hex_rgb("#1F5C8B")},
                    },
                    "fields": "title,gridProperties.rowCount,gridProperties.columnCount,gridProperties.frozenRowCount,gridProperties.frozenColumnCount,tabColorStyle",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": total_grid_rows,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_cols,
                    },
                    "cell": {
                        "userEnteredValue": {},
                        "userEnteredFormat": {
                            "backgroundColor": hex_rgb("#FFFFFF"),
                            "verticalAlignment": "MIDDLE",
                            "wrapStrategy": "CLIP",
                            "padding": {"top": 5, "bottom": 5, "left": 8, "right": 8},
                            "textFormat": {"fontFamily": "Inter", "fontSize": 10, "foregroundColor": hex_rgb("#0F172A")},
                        },
                    },
                    "fields": "userEnteredValue,userEnteredFormat",
                }
            },
            {
                "updateCells": {
                    "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
                    "rows": grid_rows,
                    "fields": "userEnteredValue,userEnteredFormat",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
                    "properties": {"pixelSize": 36},
                    "fields": "pixelSize",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 1, "endIndex": total_data_rows},
                    "properties": {"pixelSize": 48},
                    "fields": "pixelSize",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": total_data_rows, "endIndex": total_grid_rows},
                    "properties": {"pixelSize": 36},
                    "fields": "pixelSize",
                }
            },
            {
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": total_data_rows,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_cols,
                    },
                    "top": {"style": "SOLID", "width": 1, "color": hex_rgb("#CBD5E1")},
                    "bottom": {"style": "SOLID", "width": 1, "color": hex_rgb("#CBD5E1")},
                    "left": {"style": "SOLID", "width": 1, "color": hex_rgb("#E2E8F0")},
                    "right": {"style": "SOLID", "width": 1, "color": hex_rgb("#E2E8F0")},
                    "innerHorizontal": {"style": "SOLID", "width": 1, "color": hex_rgb("#E2E8F0")},
                    "innerVertical": {"style": "SOLID", "width": 1, "color": hex_rgb("#E2E8F0")},
                }
            },
            {
                "setBasicFilter": {
                    "filter": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": total_data_rows,
                            "startColumnIndex": 0,
                            "endColumnIndex": num_cols,
                        }
                    }
                }
            },
        ]
    )

    for col_idx, px in enumerate(COL_WIDTHS):
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col_idx, "endIndex": col_idx + 1},
                    "properties": {"pixelSize": px},
                    "fields": "pixelSize",
                }
            }
        )

    cond_rules: list[tuple[int, str, str, str, str]] = []
    for k, bg_c in SYSTEM_BG.items():
        cond_rules.append((0, "TEXT_EQ", k, bg_c, "#0F172A"))
    for k, (bg_c, fg_c) in SPEC_STYLE.items():
        cond_rules.append((3, "TEXT_EQ", k, bg_c, fg_c))
    for k, (bg_c, fg_c) in IMPACT_STYLE.items():
        cond_rules.append((4, "TEXT_EQ", k, bg_c, fg_c))
    for k, (bg_c, fg_c) in PRIOR_STYLE.items():
        cond_rules.append((5, "TEXT_EQ", k, bg_c, fg_c))
    cond_rules.append((7, "TEXT_STARTS_WITH", "@", "#CEEAD6", "#0D652D"))
    cond_rules.append((7, "TEXT_EQ", "Unverified", "#F1F5F9", "#64748B"))
    for k, (bg_c, fg_c) in STATUS_STYLE.items():
        cond_rules.append((9, "TEXT_EQ", k, bg_c, fg_c))

    for idx, (col_i, cond_type, val_str, bg_c, fg_c) in enumerate(cond_rules):
        requests.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [
                            {
                                "sheetId": sheet_id,
                                "startRowIndex": 1,
                                "endRowIndex": total_grid_rows,
                                "startColumnIndex": col_i,
                                "endColumnIndex": col_i + 1,
                            }
                        ],
                        "booleanRule": {
                            "condition": {"type": cond_type, "values": [{"userEnteredValue": val_str}]},
                            "format": {
                                "backgroundColor": hex_rgb(bg_c),
                                "textFormat": {"foregroundColor": hex_rgb(fg_c), "bold": True},
                            },
                        },
                    },
                    "index": idx,
                }
            }
        )

    return {"requests": requests}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--old-rules", type=int, default=29)
    args = parser.parse_args()

    payload = build_payload(args.csv, sheet_id=0, old_cond_rules_count=args.old_rules)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} ({len(payload['requests'])} requests)")


if __name__ == "__main__":
    main()
