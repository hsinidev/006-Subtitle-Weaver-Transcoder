"""
Spatial Bounding Box Table Reconstruction Engine.
Groups OCR items into lines and columns via Euclidean centroid clustering,
then outputs Plain Text, Markdown Table, TSV, and JSON formats.
"""

import json
import re
from typing import List, Dict, Tuple
from src.config import FORMAT_PLAIN, FORMAT_MARKDOWN, FORMAT_TSV, FORMAT_JSON


class TableReconstructor:

    @staticmethod
    def _group_into_lines(items: List[Dict], line_merge_threshold: float = 0.6) -> List[List[Dict]]:
        """
        Groups OCR items into horizontal lines based on Y-centroid proximity.
        Items are sorted left-to-right within each line.
        """
        if not items:
            return []

        # Sort items top-to-bottom by cy
        sorted_items = sorted(items, key=lambda x: x["cy"])

        lines: List[List[Dict]] = []
        current_line: List[Dict] = [sorted_items[0]]

        for item in sorted_items[1:]:
            last_item = current_line[-1]
            last_height = last_item["bbox"][3] - last_item["bbox"][1]
            # If current item's cy is within merge_threshold * avg_line_height from last item's cy → same line
            if abs(item["cy"] - last_item["cy"]) < max(last_height * line_merge_threshold, 8):
                current_line.append(item)
            else:
                # Sort completed line left-to-right
                current_line.sort(key=lambda x: x["cx"])
                lines.append(current_line)
                current_line = [item]

        if current_line:
            current_line.sort(key=lambda x: x["cx"])
            lines.append(current_line)

        return lines

    @staticmethod
    def _detect_columns(lines: List[List[Dict]], gap_threshold: float = 30.0) -> List[List[List[str]]]:
        """
        Detects column structure across lines using X-coordinate gap analysis.
        Returns: list of rows, each row being a list of column-cell strings.
        """
        if not lines:
            return []

        # Collect all x-start positions across all items
        all_x_starts = sorted(set(item["bbox"][0] for line in lines for item in line))

        # Merge close x-starts into column boundaries
        col_boundaries: List[float] = []
        for x in all_x_starts:
            if not col_boundaries or (x - col_boundaries[-1]) > gap_threshold:
                col_boundaries.append(x)

        num_cols = len(col_boundaries)
        if num_cols <= 1:
            # No column structure detected — return single-column plain text
            return [[" ".join(item["text"] for item in line)] for line in lines]

        # Assign each item to a column based on nearest x-boundary
        table_rows: List[List[str]] = []
        for line in lines:
            row = [""] * num_cols
            for item in line:
                # Find closest column boundary
                col_idx = min(range(num_cols), key=lambda i: abs(col_boundaries[i] - item["bbox"][0]))
                if row[col_idx]:
                    row[col_idx] += " " + item["text"]
                else:
                    row[col_idx] = item["text"]
            table_rows.append(row)

        return table_rows

    def reconstruct(self, items: List[Dict], format_mode: str = FORMAT_PLAIN) -> str:
        """
        Main reconstruction entry point. Converts OCR item list to requested format.
        Returns: formatted string output.
        """
        if not items:
            return ""

        lines = self._group_into_lines(items)

        if format_mode == FORMAT_PLAIN:
            return self._to_plain(lines)
        elif format_mode == FORMAT_MARKDOWN:
            return self._to_markdown(lines)
        elif format_mode == FORMAT_TSV:
            return self._to_tsv(lines)
        elif format_mode == FORMAT_JSON:
            return self._to_json(items, lines)
        else:
            return self._to_plain(lines)

    def _to_plain(self, lines: List[List[Dict]]) -> str:
        text_blocks = []
        for line in lines:
            text_blocks.append(" ".join(item["text"] for item in line))
        return "\n".join(text_blocks)

    def _to_markdown(self, lines: List[List[Dict]]) -> str:
        table_rows = self._detect_columns(lines)
        if not table_rows:
            return ""

        num_cols = max(len(row) for row in table_rows)

        # Pad all rows to the same column count
        padded = [row + [""] * (num_cols - len(row)) for row in table_rows]

        def _fmt(s: str) -> str:
            return s.replace("|", "\\|").strip()

        md_lines = []
        # Header row
        header = padded[0]
        md_lines.append("| " + " | ".join(_fmt(c) for c in header) + " |")
        md_lines.append("|" + "|".join(" --- " for _ in header) + "|")

        # Data rows
        for row in padded[1:]:
            md_lines.append("| " + " | ".join(_fmt(c) for c in row) + " |")

        return "\n".join(md_lines)

    def _to_tsv(self, lines: List[List[Dict]]) -> str:
        table_rows = self._detect_columns(lines)
        tsv_lines = []
        for row in table_rows:
            tsv_lines.append("\t".join(cell.replace("\t", " ") for cell in row))
        return "\n".join(tsv_lines)

    def _to_json(self, items: List[Dict], lines: List[List[Dict]]) -> str:
        structured = {
            "lines": [],
            "items": []
        }
        for line_idx, line in enumerate(lines):
            line_entry = {
                "line_index": line_idx,
                "y_center": round(sum(item["cy"] for item in line) / len(line), 1),
                "tokens": [{"text": item["text"], "bbox": item["bbox"], "confidence": round(item["confidence"], 3)} for item in line]
            }
            structured["lines"].append(line_entry)

        for item in items:
            structured["items"].append({
                "text": item["text"],
                "bbox": item["bbox"],
                "cx": round(item["cx"], 1),
                "cy": round(item["cy"], 1),
                "confidence": round(item["confidence"], 3)
            })

        return json.dumps(structured, indent=2, ensure_ascii=False)
