"""
อ่านตาราง Invoice จากผล OCR ที่มีพิกัด
ระบุคอลัมน์จากความสัมพันธ์ ปริมาณ × ราคา = จำนวนเงิน ไม่ใช่จากข้อความหัวตาราง
จึงไม่ขึ้นกับภาษา รูปแบบ หรือคำที่ผู้ขายแต่ละรายเลือกใช้
"""
from dataclasses import dataclass, field
from itertools import combinations
from statistics import median
import re

from .numbers import parse_number

TOTAL_LABELS = ["TOTAL", "รวม", "ยอดรวม", "GRAND TOTAL", "SAY TOTAL"]


@dataclass
class Cell:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cx(self): return (self.x0 + self.x1) / 2

    @property
    def cy(self): return (self.y0 + self.y1) / 2

    @property
    def h(self): return self.y1 - self.y0

    def number(self):
        return parse_number(self.text)


@dataclass
class Row:
    cells: list = field(default_factory=list)

    @property
    def cy(self): return median(c.cy for c in self.cells)

    def text(self): return " ".join(c.text for c in self.cells)

    def is_total_row(self):
        up = self.text().upper()
        return any(l in up for l in TOTAL_LABELS)


def to_cells(ocr_result):
    out = []
    for item in (ocr_result or []):
        box, text = item[0], item[1]
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        if text.strip():
            out.append(Cell(text.strip(), min(xs), min(ys), max(xs), max(ys)))
    return out


def group_rows(cells, factor=0.6):
    if not cells:
        return []
    tol = median(c.h for c in cells) * factor
    rows = []
    for c in sorted(cells, key=lambda c: c.cy):
        for r in reversed(rows):
            if abs(c.cy - r.cy) <= tol:
                r.cells.append(c)
                break
        else:
            rows.append(Row([c]))
    for r in rows:
        r.cells.sort(key=lambda c: c.x0)
    return sorted(rows, key=lambda r: r.cy)


def numeric_columns(rows, tol_factor=1.2, min_depth=2):
    """จัดเซลล์ตัวเลขเป็นคอลัมน์ตามการเรียงตรงกันของขอบขวา"""
    items = []
    for ri, r in enumerate(rows):
        for c in r.cells:
            if c.number() is not None:
                items.append((ri, c))
    if not items:
        return []
    tol = median(c.h for _, c in items) * tol_factor

    cols = []
    for ri, c in sorted(items, key=lambda t: t[1].x1):
        for col in cols:
            ref = median(x.x1 for x in col.values())
            if abs(c.x1 - ref) <= tol and ri not in col:
                col[ri] = c
                break
        else:
            cols.append({ri: c})
    return [c for c in cols if len(c) >= min_depth]


def _col_x(col):
    return median(c.x1 for c in col.values())


def find_product_triple(cols, tol=0.01, min_hits=2):
    """
    หาคู่คอลัมน์ที่คูณกันแล้วตรงกับคอลัมน์ที่สามในบรรทัดเดียวกันมากที่สุด
    คืน (คอลัมน์ปริมาณ, ราคา, จำนวนเงิน, บรรทัดที่ลงตัว)
    """
    best, best_score = None, None
    n = len(cols)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(n):
                if k in (i, j):
                    continue
                shared = set(cols[i]) & set(cols[j]) & set(cols[k])
                if len(shared) < min_hits:
                    continue
                hits, trivial = [], 0
                for ri in sorted(shared):
                    a, b, c = (cols[i][ri].number(), cols[j][ri].number(),
                               cols[k][ri].number())
                    if not (a and b and c):
                        continue
                    if abs(a * b - c) <= max(tol, abs(c) * 1e-6):
                        hits.append(ri)
                        if a == 1 or b == 1:
                            trivial += 1
                if len(hits) < min_hits:
                    continue
                # เลือก: บรรทัดลงตัวมากสุด → บรรทัดที่ไม่ใช่ 1×c น้อยสุด → คอลัมน์เงินอยู่ขวาสุด
                score = (len(hits), -trivial, _col_x(cols[k]))
                if best_score is None or score > best_score:
                    left, right = (i, j) if _col_x(cols[i]) < _col_x(cols[j]) else (j, i)
                    best, best_score = (left, right, k, hits), score
    return best


def reconcile(computed, unmatched, tol=0.02, max_extra=3):
    """
    หายอดรวมที่อธิบายได้ = ผลรวมที่คำนวณได้ บวกด้วยตัวเลขที่ยังจับคู่ไม่ได้บางตัว
    คืน (ยอดรวม, รายการที่ต้องเติม)
    """
    idx = list(range(len(unmatched)))
    for t in sorted(idx, key=lambda i: unmatched[i]):
        total = unmatched[t]
        if total is None or total < computed - tol:
            continue
        if abs(total - computed) <= tol:
            return total, []
        rest = [i for i in idx if i != t and unmatched[i] < total]
        for k in range(1, min(max_extra, len(rest)) + 1):
            for combo in combinations(rest, k):
                if abs(computed + sum(unmatched[i] for i in combo) - total) <= tol:
                    return total, [unmatched[i] for i in combo]
    return None, []


def analyze_invoice(rows):
    """วิเคราะห์ตาราง Invoice ด้วยความสอดคล้องของตัวเลข"""
    res = {"lines": [], "computed": None, "printed": None,
           "missing_lines": [], "gap": None, "status": "ไม่พบตาราง",
           "n_numeric_cols": 0}

    cols = numeric_columns(rows)
    found = find_product_triple(cols) if len(cols) >= 3 else None
    if not found:                                   # ตารางเล็ก เช่น สินค้าบรรทัดเดียว
        cols = numeric_columns(rows, min_depth=1)
        found = find_product_triple(cols, min_hits=1) if len(cols) >= 3 else None
    res["n_numeric_cols"] = len(cols)

    if not found:
        res["status"] = "ไม่พบความสัมพันธ์ ปริมาณ × ราคา = จำนวนเงิน"
        return res

    qi, pi, ai, hits = found
    for ri in sorted(hits):
        res["lines"].append({"row": ri,
                             "qty": cols[qi][ri].number(),
                             "price": cols[pi][ri].number(),
                             "amount": cols[ai][ri].number()})
    computed = round(sum(l["amount"] for l in res["lines"]), 2)
    res["computed"] = computed

    outside = [c.number() for ri, c in cols[ai].items()
               if ri not in hits and c.number()]
    res["other_totals"] = sorted(set(outside), reverse=True)[:5]

    total, extra = reconcile(computed, outside)
    if total is not None and not extra:
        res["printed"] = total
        res["status"] = "ยืนยันด้วยยอดพิมพ์"
    elif total is not None:
        res["printed"] = total
        res["computed"] = total
        res["missing_lines"] = extra
        res["status"] = f"ลงตัวหลังเติม {len(extra)} บรรทัดที่อ่านปริมาณ/ราคาไม่ครบ"
    else:
        bigger = [v for v in outside if v > computed]
        smaller = [v for v in outside if v < computed]
        if smaller:
            # จำนวนเงินที่เล็กกว่ายอดรวม น่าจะเป็นบรรทัดสินค้าที่อ่านปริมาณ/ราคาไม่ได้
            res["possible_total"] = round(computed + sum(smaller), 2)
            res["unexplained"] = sorted(smaller, reverse=True)
        if bigger:
            cand = min(bigger)
            res["gap"] = (cand, round(cand - computed, 2))
            res["status"] = "ยอดพิมพ์กับยอดคำนวณไม่ตรงกัน"
        else:
            res["status"] = "ไม่พบยอดพิมพ์ให้เทียบ"
    return res
