"""
อ่านตาราง Invoice จากผล OCR ที่มีพิกัด
ระบุคอลัมน์จากความสัมพันธ์ ปริมาณ × ราคา = จำนวนเงิน ไม่ใช่จากข้อความหัวตาราง
จึงไม่ขึ้นกับภาษา รูปแบบ หรือคำที่ผู้ขายแต่ละรายเลือกใช้
"""
from dataclasses import dataclass, field
from itertools import combinations
from statistics import median
import re

from .numbers import parse_number, is_unit

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

_GLUED = re.compile(r"^(?P<num>\d[\d.,]*)\s+(?P<junk>\S{1,4})$")


def split_glued(rows, max_junk=4):
    """แยกเซลล์ที่ OCR เชื่อมข้อความคนละช่องมาไว้ด้วยกัน แล้วหั่นกล่องตามสัดส่วน

    ทำไมต้องแยก: numeric_columns() จัดคอลัมน์จากขอบขวาของเซลล์
    เซลล์ "269.00 26" มีขอบขวาอยู่ที่เลขลำดับ ไม่ใช่ที่จำนวนเงิน
    มันจึงถูกจัดเข้าคอลัมน์เลขลำดับ ทำให้คอลัมน์จำนวนเงินถูกฉีกเป็นสองคอลัมน์
    analyze_invoice เลือกคอลัมน์จำนวนเงินได้คอลัมน์เดียว อีกครึ่งจึงหลุดหายเงียบ ๆ
    (HUANYU ขาดบรรทัด 20 x 13.45 = 269.00 พอดี)

    ไม่แยกเมื่อคำท้ายเป็นชื่อหน่วย เพราะ "150.00 MTR" คือตัวเลขเดียวที่มีหน่วยกำกับ
    ไม่ใช่สองช่องที่ติดกัน

    ตำแหน่งที่หั่นประมาณจากจำนวนตัวอักษร ซึ่งเพียงพอเพราะการจัดคอลัมน์
    ใช้ระยะคลาดเคลื่อนราวหนึ่งเท่าของความสูงตัวอักษรอยู่แล้ว
    """
    out = []
    for r in rows:
        cells = []
        for c in r.cells:
            m = _GLUED.match(c.text)
            if (m is None or len(m.group("junk")) > max_junk
                    or is_unit(m.group("junk"))
                    or parse_number(m.group("num")) is None):
                cells.append(c)
                continue
            t = c.text
            cut = m.end("num")
            w = c.x1 - c.x0
            n = len(t)
            xa = c.x0 + w * cut / n
            xb = c.x0 + w * m.start("junk") / n
            cells.append(Cell(m.group("num"), c.x0, c.y0, xa, c.y1))
            cells.append(Cell(m.group("junk"), xb, c.y0, c.x1, c.y1))
        cells.sort(key=lambda c: c.x0)
        out.append(Row(cells))
    return out



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


def _guard_single_line(res, cols, ai, min_rows=3):
    """ด่านกันข้อผิดพลาดแบบเงียบ — ห้ามยืนยันเมื่อจับได้บรรทัดเดียวจากตารางใหญ่

    ถ้าคอลัมน์จำนวนเงินมีตัวเลขหลายแถว แต่จับความสัมพันธ์
    ปริมาณ x ราคา = จำนวนเงิน ได้เพียงบรรทัดเดียว แปลว่าน่าจะระบุคอลัมน์ผิด
    แล้วไปเจอคู่ที่คูณกันลงตัวโดยบังเอิญ ห้ามรายงานว่า "ยืนยัน" เด็ดขาด

    ที่มา: เคส VORETO ราคาต่อหน่วย 4 ทศนิยม (27.1800) ถูก parser รุ่นเก่าอ่านเป็น
    271,800 ตารางจึงยุบเหลือคู่บังเอิญคู่เดียว แล้วระบบรายงานว่า
    "ยืนยันด้วยยอดพิมพ์ 3.00" ทั้งที่ยอดจริงคือ 118.23
    เป็นข้อผิดพลาดแบบเงียบเพียงครั้งเดียวของโปรเจกต์นี้
    """
    if (len(res["lines"]) == 1 and 0 <= ai < len(cols)
            and len(cols[ai]) > min_rows):
        res["printed"] = None
        res["missing_lines"] = []
        res["computed"] = round(sum(l["amount"] for l in res["lines"]), 2)
        res["status"] = ("จับได้เพียงบรรทัดเดียวจากตารางหลายแถว "
                         "อาจอ่านคอลัมน์ผิด ต้องให้คนตรวจ")
        res["guard"] = "single_line_in_big_table"
    return res


def _digits(v):
    """ตัวเลขล้วนของค่าหนึ่ง  662.70 -> "66270"   "$66270" -> "66270"   """
    import re as _re
    return _re.sub(r"\D", "", v if isinstance(v, str) else f"{float(v):.2f}")


def recover_lines(rows, cols, qi, pi, ai, hits, min_digits=3, max_extra=3):
    """แถวที่อ่าน จำนวน กับ ราคา ได้ แต่เซลล์จำนวนเงินเสียรูป

    เสียรูปที่เจอจริงสองแบบ
      170.7023   เลขลำดับ 23 ถูกเชื่อมท้ายโดยไม่มีช่องว่าง (HUANYU)
      $66270     จุดทศนิยมหาย ของจริงคือ $662.70 (VORETO)

    ทั้งสองแบบ 'ตัวเลขล้วน' ยังขึ้นต้นตรงกับ จำนวน x ราคา
    จึงยืนยันได้โดยไม่ต้องเชื่อ OCR ของเซลล์ที่เสีย
    ส่วนกรณีที่เอกสารคิดเลขผิดจริง ตัวเลขจะไม่ขึ้นต้นตรงกัน แล้วจะไม่ถูกกู้
    การตรวจจับข้อผิดพลาดของเอกสารจึงไม่เสียไป
    """
    out = []
    for ri in sorted(set(cols[qi]) & set(cols[pi])):
        if ri in hits:
            continue
        q, p = cols[qi][ri].number(), cols[pi][ri].number()
        if not q or not p:
            continue
        amt = round(q * p, 2)
        want = _digits(amt)
        if len(want) < min_digits:
            continue
        for c in rows[ri].cells:
            if c.number() is None:
                continue
            got = _digits(c.text)
            if got.startswith(want) and 0 <= len(got) - len(want) <= max_extra:
                out.append({"row": ri, "qty": q, "price": p, "amount": amt,
                            "amount_read": c.number(), "cell": c.text,
                            "recovered": True})
                break
    return out


def analyze_invoice(rows):
    """วิเคราะห์ตาราง Invoice ด้วยความสอดคล้องของตัวเลข"""
    rows = split_glued(rows)
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
    res["repaired"] = []
    for ri in sorted(hits):
        q, p = cols[qi][ri].number(), cols[pi][ri].number()
        read = cols[ai][ri].number()
        amt = round(q * p, 2)
        # ใช้ผลคูณเป็นจำนวนเงิน เพราะเป็นเลขคณิตที่แน่นอน
        # ส่วนเซลล์ที่อ่านมาอาจมีอักขระอื่นติดท้าย เช่น 415.802 ที่จริงคือ 415.80
        res["lines"].append({"row": ri, "qty": q, "price": p,
                             "amount": amt, "amount_read": read})
        if read is not None and abs(read - amt) > 0.005:
            res["repaired"].append({"row": ri, "cell": cols[ai][ri].text,
                                    "read": read, "used": amt,
                                    "why": "เซลล์จำนวนเงินมีอักขระอื่นติดมา"})

    got = recover_lines(rows, cols, qi, pi, ai, hits)
    for line in got:
        res["lines"].append(line)
        res["repaired"].append({"row": line["row"], "cell": line["cell"],
                                "read": line["amount_read"], "used": line["amount"],
                                "why": "จำนวนเงินเสียรูป ยืนยันด้วย จำนวน x ราคา"})
    res["lines"].sort(key=lambda l: l["row"])
    used = set(hits) | {l["row"] for l in got}
    computed = round(sum(l["amount"] for l in res["lines"]), 2)
    res["computed"] = computed
    outside = [c.number() for ri, c in cols[ai].items()
               if ri not in used and c.number()]
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
    _guard_single_line(res, cols, ai)
    return res
