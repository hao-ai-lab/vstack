#!/usr/bin/env python3
"""Generate Google Sheets batchUpdate payload directly from canonical bugs/verified-bugs.csv.

Renders a neutral `Overview` landing tab (gid=0, index=0) followed by one tab per target system
in canonical order (default: vLLM at gid=100000001, SGLang at gid=100000000).
Pass --sheet-info (output of `gsheets readonly info <SHEET_ID> --json`) to discover live sheetIds and
existing conditionalFormatRule counts automatically so repeated syncs stay strictly idempotent.

Usage:
    gsheets readonly info 1FL5QqgzEpja9k8Zw6GmIQDtHveddjj1coHe1MJ3Ts-Q --json > /tmp/vstack_sheet_info.json
    python3 scripts/sync_bugs_sheet.py --csv bugs/verified-bugs.csv --sheet-info /tmp/vstack_sheet_info.json --out /tmp/vstack_sheet_batch.json
    gsheets mutate raw-batch 1FL5QqgzEpja9k8Zw6GmIQDtHveddjj1coHe1MJ3Ts-Q --file /tmp/vstack_sheet_batch.json
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

OVERVIEW_SHEET_ID = 0

SYSTEM_BG = {
    "vLLM": "#FCE8E6",
    "SGLang": "#E6F4EA",
    "FlashInfer": "#E8F0FE",
    "DeepGEMM": "#F3E8FD",
    "verl": "#FEF3C7",
    "Megatron-LM": "#DCFCE7",
}

DEFAULT_TAB_IDS = {
    "vLLM": 100000001,
    "SGLang": 100000000,
}

SPEC_STYLE = {
    "Isolation": ("#FCE8E6", "#A50E0E"),
    "Integrity": ("#FFEDD5", "#9A3412"),
    "Conservation": ("#FEF3C7", "#92400E"),
    "Agreement": ("#E0E7FF", "#3730A3"),
    "Finality": ("#E8F0FE", "#1967D2"),
    "Progress": ("#E0F2FE", "#0369A1"),
    "Invariance": ("#F3E8FD", "#681DA8"),
}

SPEC_PILLARS = [
    (
        "Isolation",
        "Safety (□)",
        "Live requests never overwrite, read, or alias another request's KV/state slots.",
    ),
    (
        "Integrity",
        "Safety (□)",
        "A request's own KV blocks, recurrent state, cache keys, and adapter weights remain uncorrupted across steps and reloads.",
    ),
    (
        "Conservation",
        "Safety (□)",
        "Slot allocations, reference counts, reserved indices, and clear hooks stay exact.",
    ),
    (
        "Agreement",
        "Safety (□)",
        "Ranks, control plane, and execution plane agree on active generation/memory state.",
    ),
    (
        "Progress",
        "Liveness (~>)",
        "Admissible requests eventually run without livelock, deadlock, or queue starvation.",
    ),
    (
        "Finality",
        "Bounded-response (□)",
        "Aborts, disconnects, and expired leases terminate and reclaim resources in bounded steps.",
    ),
    (
        "Invariance",
        "Equivalence (≡)",
        "Output is invariant across batch composition (M=1 vs M>1) and streaming chunking.",
    ),
]

IMPACT_STYLE = {
    "Silent Corruption": ("#FCE8E6", "#A50E0E"),
    "Crash": ("#FEF7E0", "#B06000"),
    "Hang / Leak": ("#FEF7E0", "#B06000"),
    "Non-Determinism": ("#F3E8FD", "#681DA8"),
    "API Error": ("#F1F5F9", "#475569"),
    "Request Error": ("#FEF3C7", "#92400E"),
}

PRIOR_STYLE = {
    "Unknown": ("#EEF2FF", "#3730A3"),
    "Partly Known": ("#FEF3C7", "#92400E"),
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
    "Not Reported": ("#F1F5F9", "#475569"),
    "On Hold": ("#F1F5F9", "#475569"),
}

COL_WIDTHS = [88, 152, 392, 112, 128, 104, 96, 128, 102, 114, 280]  # 11 cols, 1696px total
OVERVIEW_COL_WIDTHS = [156, 148, 152, 152, 164, 348]  # 6 cols, 1120px total


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


def formula_cell(
    formula: str,
    *,
    bg: str = "#FFFFFF",
    fg: str = "#0F172A",
    bold: bool = True,
    align: str = "CENTER",
    font: str = "Inter",
    size: int = 10,
) -> dict:
    return {
        "userEnteredValue": {"formulaValue": formula},
        "userEnteredFormat": {
            "backgroundColor": hex_rgb(bg),
            "horizontalAlignment": align,
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "CLIP",
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
    if not val or val.lower() in ("in progress", "unverified"):
        label = "In Progress" if val.lower() != "unverified" else "Unverified"
        if not val:
            label = "In Progress"
        return str_cell(label, bg="#F1F5F9", fg="#64748B", bold=True, align="CENTER")
    if val.startswith("@") and "," not in val and " " not in val:
        handle = val[1:]
        return link_cell(f"https://github.com/{handle}", val, bg="#CEEAD6", fg="#0D652D")
    return str_cell(val, bg="#CEEAD6", fg="#0D652D", bold=True, align="CENTER")


def box_border_request(sheet_id: int, r0: int, r1: int, c0: int, c1: int) -> dict:
    return {
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": r0,
                "endRowIndex": r1,
                "startColumnIndex": c0,
                "endColumnIndex": c1,
            },
            "top": {"style": "SOLID", "width": 1, "color": hex_rgb("#CBD5E1")},
            "bottom": {"style": "SOLID", "width": 1, "color": hex_rgb("#CBD5E1")},
            "left": {"style": "SOLID", "width": 1, "color": hex_rgb("#CBD5E1")},
            "right": {"style": "SOLID", "width": 1, "color": hex_rgb("#CBD5E1")},
            "innerHorizontal": {"style": "SOLID", "width": 1, "color": hex_rgb("#E2E8F0")},
            "innerVertical": {"style": "SOLID", "width": 1, "color": hex_rgb("#E2E8F0")},
        }
    }


def merge_row_cols(sheet_id: int, row_idx: int, c0: int, c1: int) -> dict:
    return {
        "mergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row_idx,
                "endRowIndex": row_idx + 1,
                "startColumnIndex": c0,
                "endColumnIndex": c1,
            },
            "mergeType": "MERGE_ALL",
        }
    }


def build_overview_requests(
    system_tabs: list[tuple[str, int]],
    *,
    sheet_id: int,
    old_cond_rules_count: int,
    has_basic_filter: bool,
    create_sheet: bool,
) -> list[dict]:
    num_cols = len(OVERVIEW_COL_WIDTHS)
    empty = str_cell("")
    sys_names_str = ", ".join(s for s, _ in system_tabs)

    grid_rows: list[dict] = []
    merges: list[dict] = []
    row_heights: list[tuple[int, int, int]] = []

    # Row 0: Banner Title
    r_banner_title = len(grid_rows)
    grid_rows.append(
        {
            "values": [
                str_cell(
                    "Verified AI Infra Bugs — vstack Formal Verification Tracker",
                    bg="#1F5C8B",
                    fg="#FFFFFF",
                    bold=True,
                    align="LEFT",
                    size=12,
                ),
                *[str_cell("", bg="#1F5C8B") for _ in range(num_cols - 1)],
            ]
        }
    )
    merges.append(merge_row_cols(sheet_id, r_banner_title, 0, num_cols))
    row_heights.append((r_banner_title, r_banner_title + 1, 38))

    # Row 1: Banner Subtitle
    r_banner_sub = len(grid_rows)
    grid_rows.append(
        {
            "values": [
                str_cell(
                    f"Read-only live tracker synced one-way from hao-ai-lab/vstack (bugs/verified-bugs.csv). "
                    f"Select a system tab below ({sys_names_str}) to inspect per-bug counterexamples, hardware reproductions, and upstream fix PRs.",
                    bg="#F8FAFC",
                    fg="#334155",
                    bold=False,
                    align="LEFT",
                    size=10,
                    wrap="WRAP",
                ),
                *[str_cell("", bg="#F8FAFC") for _ in range(num_cols - 1)],
            ]
        }
    )
    merges.append(merge_row_cols(sheet_id, r_banner_sub, 0, num_cols))
    row_heights.append((r_banner_sub, r_banner_sub + 1, 36))

    # Row 2: Quick Links
    r_banner_links = len(grid_rows)
    grid_rows.append(
        {
            "values": [
                str_cell("Quick Links", bg="#F1F5F9", fg="#334155", bold=True, align="CENTER"),
                link_cell("https://github.com/hao-ai-lab/vstack", "GitHub Repo ↗"),
                link_cell("https://github.com/hao-ai-lab/vstack/tree/main/bugs", "CSV & Guide (bugs/) ↗"),
                link_cell("https://github.com/hao-ai-lab/vstack/blob/main/docs/exposure-gate.md", "Exposure Gate ↗"),
                link_cell("https://haoailab.com/blogs/verifiable-llm-infra/", "Technical Blog ↗"),
                link_cell("https://x.com/haoailab/status/2120595980659917024", "X Threads (@haoailab) ↗"),
            ]
        }
    )
    row_heights.append((r_banner_links, r_banner_links + 1, 32))

    # Spacer
    r_sp1 = len(grid_rows)
    grid_rows.append({"values": [empty for _ in range(num_cols)]})
    row_heights.append((r_sp1, r_sp1 + 1, 16))

    # Section 1 Title
    r_s1_title = len(grid_rows)
    grid_rows.append(
        {
            "values": [
                str_cell("1. Tracked Systems Summary", bg="#FFFFFF", fg="#0F172A", bold=True, align="LEFT", size=11),
                *[empty for _ in range(num_cols - 1)],
            ]
        }
    )
    merges.append(merge_row_cols(sheet_id, r_s1_title, 0, num_cols))
    row_heights.append((r_s1_title, r_s1_title + 1, 28))

    # Section 1 Table Header
    r_s1_start = len(grid_rows)
    s1_headers = [
        ("System", "LEFT"),
        ("Tracked Bugs", "CENTER"),
        ("Net-New (Unknown)", "CENTER"),
        ("Verified (@handle)", "CENTER"),
        ("Upstream Issue / PR", "CENTER"),
        ("Sheet Tab", "CENTER"),
    ]
    grid_rows.append(
        {
            "values": [
                str_cell(h, bg="#1F5C8B", fg="#FFFFFF", bold=True, align=a, size=10)
                for h, a in s1_headers
            ]
        }
    )

    first_sys_excel_row = len(grid_rows) + 1
    for sys_name, sys_sid in system_tabs:
        sys_bg = SYSTEM_BG.get(sys_name, "#F8FAFC")
        grid_rows.append(
            {
                "values": [
                    str_cell(sys_name, bg=sys_bg, fg="#0F172A", bold=True, align="LEFT"),
                    formula_cell(f"=COUNTA('{sys_name}'!A2:A)"),
                    formula_cell(f'=COUNTIF(\'{sys_name}\'!F2:F, "Unknown")'),
                    formula_cell(f'=COUNTIF(\'{sys_name}\'!H2:H, "@*")'),
                    formula_cell(f'=COUNTIFS(\'{sys_name}\'!A2:A, "{sys_name}", \'{sys_name}\'!I2:I, "<>—")'),
                    link_cell(f"#gid={sys_sid}", f"Open {sys_name} Tab →"),
                ]
            }
        )
    last_sys_excel_row = len(grid_rows)

    # Total Row
    grid_rows.append(
        {
            "values": [
                str_cell("Total", bg="#F1F5F9", fg="#0F172A", bold=True, align="LEFT"),
                formula_cell(f"=SUM(B{first_sys_excel_row}:B{last_sys_excel_row})", bg="#F1F5F9"),
                formula_cell(f"=SUM(C{first_sys_excel_row}:C{last_sys_excel_row})", bg="#F1F5F9"),
                formula_cell(f"=SUM(D{first_sys_excel_row}:D{last_sys_excel_row})", bg="#F1F5F9"),
                formula_cell(f"=SUM(E{first_sys_excel_row}:E{last_sys_excel_row})", bg="#F1F5F9"),
                str_cell("Synced from bugs/verified-bugs.csv", bg="#F1F5F9", fg="#475569", bold=False, align="CENTER"),
            ]
        }
    )
    r_s1_end = len(grid_rows)
    row_heights.append((r_s1_start, r_s1_end, 34))

    # Spacer
    r_sp2 = len(grid_rows)
    grid_rows.append({"values": [empty for _ in range(num_cols)]})
    row_heights.append((r_sp2, r_sp2 + 1, 16))

    # Section 2 Title
    r_s2_title = len(grid_rows)
    grid_rows.append(
        {
            "values": [
                str_cell(
                    "2. Formal Specification Pillars (Violated Spec)",
                    bg="#FFFFFF",
                    fg="#0F172A",
                    bold=True,
                    align="LEFT",
                    size=11,
                ),
                *[empty for _ in range(num_cols - 1)],
            ]
        }
    )
    merges.append(merge_row_cols(sheet_id, r_s2_title, 0, num_cols))
    row_heights.append((r_s2_title, r_s2_title + 1, 28))

    # Section 2 Header
    r_s2_start = len(grid_rows)
    grid_rows.append(
        {
            "values": [
                str_cell("Violated Spec", bg="#1F5C8B", fg="#FFFFFF", bold=True, align="CENTER"),
                str_cell("Formal Class", bg="#1F5C8B", fg="#FFFFFF", bold=True, align="CENTER"),
                str_cell("Meaning", bg="#1F5C8B", fg="#FFFFFF", bold=True, align="LEFT"),
                *[str_cell("", bg="#1F5C8B") for _ in range(num_cols - 3)],
            ]
        }
    )
    merges.append(merge_row_cols(sheet_id, r_s2_start, 2, num_cols))

    for pillar, p_class, p_meaning in SPEC_PILLARS:
        r_cur = len(grid_rows)
        sp_bg, sp_fg = SPEC_STYLE[pillar]
        grid_rows.append(
            {
                "values": [
                    str_cell(pillar, bg=sp_bg, fg=sp_fg, bold=True, align="CENTER"),
                    str_cell(p_class, bg="#FFFFFF", fg="#334155", bold=False, align="CENTER"),
                    str_cell(p_meaning, bg="#FFFFFF", fg="#0F172A", bold=False, align="LEFT", wrap="WRAP"),
                    *[empty for _ in range(num_cols - 3)],
                ]
            }
        )
        merges.append(merge_row_cols(sheet_id, r_cur, 2, num_cols))
    r_s2_end = len(grid_rows)
    row_heights.append((r_s2_start, r_s2_end, 32))

    # Spacer
    r_sp3 = len(grid_rows)
    grid_rows.append({"values": [empty for _ in range(num_cols)]})
    row_heights.append((r_sp3, r_sp3 + 1, 16))

    # Section 3 Title
    r_s3_title = len(grid_rows)
    grid_rows.append(
        {
            "values": [
                str_cell(
                    "3. Attribution & Verification Columns (Prior Status & Human Verifier)",
                    bg="#FFFFFF",
                    fg="#0F172A",
                    bold=True,
                    align="LEFT",
                    size=11,
                ),
                *[empty for _ in range(num_cols - 1)],
            ]
        }
    )
    merges.append(merge_row_cols(sheet_id, r_s3_title, 0, num_cols))
    row_heights.append((r_s3_title, r_s3_title + 1, 28))

    # Section 3 Header
    r_s3_start = len(grid_rows)
    grid_rows.append(
        {
            "values": [
                str_cell("Column", bg="#1F5C8B", fg="#FFFFFF", bold=True, align="LEFT"),
                str_cell("Badge / Value", bg="#1F5C8B", fg="#FFFFFF", bold=True, align="CENTER"),
                str_cell("Meaning", bg="#1F5C8B", fg="#FFFFFF", bold=True, align="LEFT"),
                *[str_cell("", bg="#1F5C8B") for _ in range(num_cols - 3)],
            ]
        }
    )
    merges.append(merge_row_cols(sheet_id, r_s3_start, 2, num_cols))

    s3_rows = [
        (
            "Prior Status",
            str_cell("Unknown", bg="#EEF2FF", fg="#3730A3", bold=True, align="CENTER"),
            "Unreported upstream prior to the vstack formal scan.",
        ),
        (
            "Prior Status",
            str_cell("Partly Known", bg="#FEF3C7", fg="#92400E", bold=True, align="CENTER"),
            "A narrower symptom or crash was reported upstream, while the deeper corruption or root mechanism was unreported.",
        ),
        (
            "Prior Status",
            str_cell("Known", bg="#F1F5F9", fg="#0F766E", bold=True, align="CENTER"),
            "Previously reported in an upstream Issue or unmerged PR (still present on main at scan time) and independently rediscovered by vstack without reading GitHub reports.",
        ),
        (
            "Human Verifier",
            str_cell("@github_handle", bg="#CEEAD6", fg="#0D652D", bold=True, align="CENTER"),
            "Verified: passed every applicable exposure gate, including a real-engine reproduction on hardware next to a passing control.",
        ),
        (
            "Human Verifier",
            str_cell("In Progress", bg="#F1F5F9", fg="#64748B", bold=True, align="CENTER"),
            "Candidate awaiting independent human verification; community verifications and new bug PRs welcome via bugs/verified-bugs.csv.",
        ),
    ]
    for col_name, badge_cell, meaning_text in s3_rows:
        r_cur = len(grid_rows)
        grid_rows.append(
            {
                "values": [
                    str_cell(col_name, bg="#FFFFFF", fg="#334155", bold=True, align="LEFT"),
                    badge_cell,
                    str_cell(meaning_text, bg="#FFFFFF", fg="#0F172A", bold=False, align="LEFT", wrap="WRAP"),
                    *[empty for _ in range(num_cols - 3)],
                ]
            }
        )
        merges.append(merge_row_cols(sheet_id, r_cur, 2, num_cols))
    r_s3_end = len(grid_rows)
    row_heights.append((r_s3_start, r_s3_end, 34))

    total_grid_rows = len(grid_rows) + 3
    row_heights.append((r_s3_end, total_grid_rows, 24))

    requests: list[dict] = []
    if create_sheet:
        requests.append(
            {
                "addSheet": {
                    "properties": {
                        "sheetId": sheet_id,
                        "title": "Overview",
                        "index": 0,
                        "gridProperties": {
                            "rowCount": total_grid_rows,
                            "columnCount": num_cols,
                            "frozenRowCount": 0,
                            "frozenColumnCount": 0,
                            "hideGridlines": True,
                        },
                        "tabColorStyle": {"rgbColor": hex_rgb("#1F5C8B")},
                    }
                }
            }
        )
    else:
        for _ in range(old_cond_rules_count):
            requests.append({"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": 0}})
        if has_basic_filter:
            requests.append({"clearBasicFilter": {"sheetId": sheet_id}})
        requests.append(
            {
                "unmergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": max(total_grid_rows, 35),
                        "startColumnIndex": 0,
                        "endColumnIndex": num_cols,
                    }
                }
            }
        )
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "title": "Overview",
                        "index": 0,
                        "gridProperties": {
                            "rowCount": total_grid_rows,
                            "columnCount": num_cols,
                            "frozenRowCount": 0,
                            "frozenColumnCount": 0,
                            "hideGridlines": True,
                        },
                        "tabColorStyle": {"rgbColor": hex_rgb("#1F5C8B")},
                    },
                    "fields": "title,index,gridProperties.rowCount,gridProperties.columnCount,gridProperties.frozenRowCount,gridProperties.frozenColumnCount,gridProperties.hideGridlines,tabColorStyle",
                }
            }
        )

    requests.extend(
        [
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
            *merges,
            box_border_request(sheet_id, 0, r_banner_links + 1, 0, num_cols),
            box_border_request(sheet_id, r_s1_start, r_s1_end, 0, num_cols),
            box_border_request(sheet_id, r_s2_start, r_s2_end, 0, num_cols),
            box_border_request(sheet_id, r_s3_start, r_s3_end, 0, num_cols),
        ]
    )

    for r0, r1, px in row_heights:
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": r0, "endIndex": r1},
                    "properties": {"pixelSize": px},
                    "fields": "pixelSize",
                }
            }
        )

    for col_idx, px in enumerate(OVERVIEW_COL_WIDTHS):
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": col_idx, "endIndex": col_idx + 1},
                    "properties": {"pixelSize": px},
                    "fields": "pixelSize",
                }
            }
        )

    return requests


def build_tab_requests(
    rows: list[dict[str, str]],
    *,
    tab_title: str,
    sheet_id: int,
    tab_index: int,
    old_cond_rules_count: int,
    has_basic_filter: bool = True,
    create_sheet: bool = False,
) -> list[dict]:
    headers = [
        ("System", "LEFT"),
        ("Module", "LEFT"),
        ("Bug Summary", "LEFT"),
        ("Violated Spec", "CENTER"),
        ("Impact", "CENTER"),
        ("Prior Status", "CENTER"),
        ("Found", "CENTER"),
        ("Human Verifier", "CENTER"),
        ("Upstream", "CENTER"),
        ("Status", "CENTER"),
        ("Evidence", "LEFT"),
    ]

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
                    str_cell((r.get("found_on") or "").strip(), bg="#FFFFFF", fg="#334155", bold=False, align="CENTER"),
                    verifier_cell(r["human_verifier"]),
                    up_cell,
                    str_cell(r["status"], bg=st_bg, fg=st_fg, bold=True, align="CENTER"),
                    str_cell(r["evidence"], bg="#FFFFFF", fg="#334155", bold=False, align="LEFT", wrap="WRAP"),
                ]
            }
        )

    total_data_rows = len(grid_rows)
    total_grid_rows = max(25, total_data_rows + 8)
    num_cols = len(headers)

    requests: list[dict] = []
    if create_sheet:
        requests.append(
            {
                "addSheet": {
                    "properties": {
                        "sheetId": sheet_id,
                        "title": tab_title,
                        "index": tab_index,
                        "gridProperties": {
                            "rowCount": total_grid_rows,
                            "columnCount": num_cols,
                            "frozenRowCount": 1,
                            "frozenColumnCount": 1,
                            "hideGridlines": False,
                        },
                        "tabColorStyle": {"rgbColor": hex_rgb("#1F5C8B")},
                    }
                }
            }
        )
    else:
        for _ in range(old_cond_rules_count):
            requests.append({"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": 0}})
        if has_basic_filter:
            requests.append({"clearBasicFilter": {"sheetId": sheet_id}})
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "title": tab_title,
                        "index": tab_index,
                        "gridProperties": {
                            "rowCount": total_grid_rows,
                            "columnCount": num_cols,
                            "frozenRowCount": 1,
                            "frozenColumnCount": 1,
                            "hideGridlines": False,
                        },
                        "tabColorStyle": {"rgbColor": hex_rgb("#1F5C8B")},
                    },
                    "fields": "title,index,gridProperties.rowCount,gridProperties.columnCount,gridProperties.frozenRowCount,gridProperties.frozenColumnCount,gridProperties.hideGridlines,tabColorStyle",
                }
            }
        )

    requests.extend(
        [
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
    col = {h_text: i for i, (h_text, _) in enumerate(headers)}
    cond_rules.append((col["Human Verifier"], "TEXT_STARTS_WITH", "@", "#CEEAD6", "#0D652D"))
    cond_rules.append((col["Human Verifier"], "TEXT_EQ", "In Progress", "#F1F5F9", "#64748B"))
    cond_rules.append((col["Human Verifier"], "TEXT_EQ", "Unverified", "#F1F5F9", "#64748B"))
    for k, (bg_c, fg_c) in STATUS_STYLE.items():
        cond_rules.append((col["Status"], "TEXT_EQ", k, bg_c, fg_c))

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

    return requests


def build_payload(
    csv_path: Path,
    *,
    sheet_info_path: Path | None = None,
    old_cond_rules_count: int = 29,
) -> dict:
    with csv_path.open(newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    ordered_systems: list[str] = []
    for sys_name in list(SYSTEM_BG.keys()) + [r["system"] for r in all_rows]:
        if sys_name not in ordered_systems and any(r["system"] == sys_name for r in all_rows):
            ordered_systems.append(sys_name)

    live_by_id: dict[int, tuple[str, int, bool]] = {}
    live_by_title: dict[str, int] = {}
    used_sheet_ids: set[int] = {OVERVIEW_SHEET_ID, *DEFAULT_TAB_IDS.values()}
    if sheet_info_path is not None:
        info = json.loads(sheet_info_path.read_text(encoding="utf-8"))
        for s in info.get("sheets", []):
            props = s.get("properties", {})
            title = props.get("title", "")
            sid = int(props.get("sheetId", 0))
            cond_cnt = len(s.get("conditionalFormats", []))
            has_bf = "basicFilter" in s
            live_by_id[sid] = (title, cond_cnt, has_bf)
            if sid != OVERVIEW_SHEET_ID:
                live_by_title[title] = sid
            used_sheet_ids.add(sid)

    next_auto_id = max(used_sheet_ids | {100000001}) + 1
    system_tab_specs: list[tuple[str, int, int, bool, bool]] = []
    for sys_name in ordered_systems:
        target_sid = DEFAULT_TAB_IDS.get(sys_name, live_by_title.get(sys_name))
        if target_sid is not None and target_sid in live_by_id:
            _, cond_cnt, has_bf = live_by_id[target_sid]
            create_sheet = False
            sid = target_sid
        elif sheet_info_path is None and target_sid is not None:
            sid = target_sid
            cond_cnt = old_cond_rules_count
            has_bf = True
            create_sheet = False
        else:
            sid = target_sid if target_sid is not None else next_auto_id
            if sid in used_sheet_ids and sys_name not in DEFAULT_TAB_IDS:
                sid = next_auto_id
            next_auto_id = max(next_auto_id, sid + 1)
            used_sheet_ids.add(sid)
            cond_cnt = 0
            has_bf = False
            create_sheet = True
        system_tab_specs.append((sys_name, sid, cond_cnt, has_bf, create_sheet))

    # If gid=0 exists under an old system name (e.g. "SGLang"), rename it to
    # "Overview" first so creating the new system tab never collides by title;
    # then populate all system tabs before writing Overview formulas that reference them.
    requests: list[dict] = []
    if OVERVIEW_SHEET_ID in live_by_id:
        old_ov_title, ov_cond_cnt, ov_has_bf = live_by_id[OVERVIEW_SHEET_ID]
        ov_create = False
        if old_ov_title != "Overview":
            requests.append(
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": OVERVIEW_SHEET_ID, "title": "Overview", "index": 0},
                        "fields": "title,index",
                    }
                }
            )
    elif sheet_info_path is None:
        ov_cond_cnt = 0
        ov_has_bf = False
        ov_create = False
    else:
        ov_cond_cnt = 0
        ov_has_bf = False
        ov_create = True

    for offset, (sys_name, sid, cond_cnt, has_bf, create_sheet) in enumerate(system_tab_specs, start=1):
        sys_rows = [r for r in all_rows if r["system"] == sys_name]
        requests.extend(
            build_tab_requests(
                sys_rows,
                tab_title=sys_name,
                sheet_id=sid,
                tab_index=offset,
                old_cond_rules_count=cond_cnt,
                has_basic_filter=has_bf,
                create_sheet=create_sheet,
            )
        )

    requests.extend(
        build_overview_requests(
            [(sys_name, sid) for sys_name, sid, _, _, _ in system_tab_specs],
            sheet_id=OVERVIEW_SHEET_ID,
            old_cond_rules_count=ov_cond_cnt,
            has_basic_filter=ov_has_bf,
            create_sheet=ov_create,
        )
    )

    return {"requests": requests}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sheet-info", type=Path, default=None, help="JSON from `gsheets readonly info <ID> --json`")
    parser.add_argument("--old-rules", type=int, default=29, help="Fallback conditional rule count when --sheet-info is omitted")
    args = parser.parse_args()

    payload = build_payload(
        args.csv,
        sheet_info_path=args.sheet_info,
        old_cond_rules_count=args.old_rules,
    )
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} ({len(payload['requests'])} requests)")


if __name__ == "__main__":
    main()
