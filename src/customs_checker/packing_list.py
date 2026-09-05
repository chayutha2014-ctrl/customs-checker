# -*- coding: utf-8 -*-
"""อ่านตาราง Packing List

Packing List ไม่มีความสัมพันธ์ ปริมาณ x ราคา = จำนวนเงิน แบบ Invoice
สิ่งที่มีคือ **ผลรวมของแต่ละคอลัมน์เท่ากับค่าในแถวรวม**
จึงใช้ความสัมพันธ์นั้นเป็นตัวระบุทั้งแถวรวมและคอลัมน์ข้อมูล
โดยไม่ต้องอ่านหัวตาราง ไม่ต้องหาคำว่า TOTAL และไม่ขึ้นกับภาษา

และ Packing List มียอดรวมอยู่ 2 ที่เสมอ — แถวรวมในตาราง กับข้อความใต้ตาราง
สองที่นี้เคยขัดกันจริงและหลุดถึงเอกสารตัวจริง
(ชุดตัวอย่างที่ 4: ตารางรวมได้ 18.38 CBM แต่ข้อความเขียน TOTAL MEASUREMENT: 9.19CBM)
จึงต้องอ่านแยกกันแล้วเอามาเทียบ ห้ามอ่านที่เดียวแล้วถือว่าพอ
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from .tables import numeric_columns, _col_x, Row

MAX_TOKENS_IN_NUMERIC_CELL = 2   # เซลล์ตัวเลขจริงมีได้ไม่เกิน "ค่า + หน่วย"


def numeric_rows(rows, max_tokens: int = MAX_TOKENS_IN_NUMERIC_CELL):
    """ตัดเซลล์ที่เป็นประโยคออกก่อนจัดคอลัมน์

    ทำไมต้องมี: `parse_number` ดึงเลขจากข้อความอะไรก็ได้ ประโยคใต้ตารางอย่าง
    "TOTAL PACKED IN EIGHT (8) PLTS ONLY." จึงถูกอ่านเป็นเลข 8 แล้วถูกจัดเข้า
    คอลัมน์พาเลทเพราะขอบขวาบังเอิญตรงกัน ทำให้ผลรวมของคอลัมน์นั้นเพี้ยน
    (พบจริงตอนทดสอบกับ Packing List ของชุดที่ 4 — คอลัมน์พาเลทหายไปทั้งคอลัมน์)

    เซลล์ตัวเลขจริงมีได้อย่างมาก 2 คำ คือค่ากับหน่วย เช่น `3424.00KGS` หรือ `500 M`
    """
    out = []
    for r in rows:
        keep = [c for c in r.cells if len(c.text.split()) <= max_tokens]
        if keep:
            out.append(Row(keep))
    return out

TOL = 0.02          # ผลรวมคลาดได้เท่านี้ (ปัดเศษทศนิยม)
MIN_COLS_AGREE = 2  # ต้องมีคอลัมน์อย่างน้อยเท่านี้ที่ผลรวมลงตัว จึงเชื่อว่าเป็นแถวรวม


# ---------------- ยอดรวมในตาราง ----------------
@dataclass
class ColumnTotal:
    col: int
    x: float                       # ตำแหน่งขอบขวาของคอลัมน์ ใช้เรียงซ้ายไปขวา
    line_rows: list[int]
    values: list[float]
    computed: float                # ผลบวกของค่ารายบรรทัด
    printed: float                 # ค่าที่อยู่ในแถวรวม
    trivial: bool = False          # มีค่ารายบรรทัดเดียว ผลรวมจึงลงตัวโดยปริยาย


def find_total_row(cols, tol: float = TOL, min_cols: int = MIN_COLS_AGREE):
    """หาแถวรวมด้วยเลขคณิตล้วน

    ทุกคอลัมน์ทุกแถว ถามว่า "ค่านี้เท่ากับผลบวกของค่าที่เหลือในคอลัมน์เดียวกันหรือไม่"
    แถวที่ได้เสียงจากหลายคอลัมน์ที่สุดคือแถวรวม

    ต้องมีอย่างน้อย min_cols คอลัมน์เห็นตรงกัน มิฉะนั้นคืน None
    เพราะคอลัมน์เดียวอาจลงตัวโดยบังเอิญ (หลักเดียวกับด่านกันข้อผิดเงียบใน analyze_invoice)

    คืน (เลขแถวรวม, [เลขคอลัมน์ที่ลงตัว]) หรือ (None, [])
    """
    votes: dict[int, list[int]] = {}
    solid: dict[int, int] = {}          # นับเฉพาะเสียงที่ไม่ใช่กรณีบรรทัดเดียว
    for ci, col in enumerate(cols):
        nums = {ri: c.number() for ri, c in col.items() if c.number() is not None}
        if len(nums) < 2:
            continue
        for ri, total in nums.items():
            rest = [v for r, v in nums.items() if r != ri]
            if not rest:
                continue
            if abs(sum(rest) - total) <= max(tol, abs(total) * 1e-6):
                votes.setdefault(ri, []).append(ci)
                if len(rest) > 1:
                    solid[ri] = solid.get(ri, 0) + 1
    if not votes:
        return None, []
    # เลือก: เสียงที่ไม่ใช่บรรทัดเดียวมากสุด -> เสียงรวมมากสุด -> แถวล่างสุด
    ri = max(votes, key=lambda r: (solid.get(r, 0), len(votes[r]), r))
    if len(votes[ri]) < min_cols:
        return None, []
    return ri, votes[ri]


def column_totals(cols, total_row: int, agree: list[int]) -> list[ColumnTotal]:
    out = []
    for ci in agree:
        col = cols[ci]
        nums = {ri: c.number() for ri, c in col.items() if c.number() is not None}
        printed = nums[total_row]
        lines = {r: v for r, v in nums.items() if r != total_row}
        out.append(ColumnTotal(
            col=ci, x=_col_x(col),
            line_rows=sorted(lines), values=[lines[r] for r in sorted(lines)],
            computed=round(sum(lines.values()), 4), printed=printed,
            trivial=len(lines) < 2))
    return sorted(out, key=lambda c: c.x)


# ---------------- ยอดรวมที่เขียนเป็นข้อความใต้ตาราง ----------------
UNITS = ("CTNS", "CARTONS", "CTN", "PCS", "PIECES", "SETS", "PLTS", "PALLETS",
         "PALLET", "KGS", "KG", "CBM", "M3", "PKGS", "PACKAGES", "MTR", "M")

_PARen = re.compile(r"\(\s*([\d][\d.,]*)\s*\)")
_NUM = re.compile(r"(?<![\d.,])([\d][\d.,]*)")


@dataclass
class TextTotal:
    label: str
    value: float
    unit: str
    raw: str
    matched: str = ""      # ผลการเทียบกับยอดในตาราง


def text_totals(text: str) -> list[TextTotal]:
    """ดึงยอดรวมที่พิมพ์เป็นข้อความใต้ตาราง

    รูปแบบที่พบจริง
      TOTAL PACKED IN EIGHT (8) PLTS ONLY.
      TOTAL GROSS WEIGHT: 3424.00KGS
      TOTAL MEASUREMENT: 9.19CBM
      SAY TOTAL FIVE HUNDRED AND TWENTY (520) CTNS ONLY.
      TOTAL PACKED ON ONE (1) PALLET.
    """
    from .numbers import parse_number
    out = []
    for raw in (text or "").splitlines():
        line = " ".join(raw.split())
        up = line.upper()
        if "TOTAL" not in up:
            continue
        # ตัวเลขในวงเล็บมาก่อน เพราะเป็นรูปตัวเลขที่กำกับตัวหนังสือไว้
        m = _PARen.search(line)
        if not m:
            after = up.split("TOTAL", 1)[1]
            m2 = _NUM.search(after)
            if not m2:
                continue
            token = m2.group(1)
            pos_txt = after
        else:
            token = m.group(1)
            pos_txt = up[up.index(m.group(0)) + len(m.group(0)):]
        val = parse_number(token)
        if val is None:
            continue
        unit = ""
        tail = pos_txt.lstrip(" :.")
        for u in sorted(UNITS, key=len, reverse=True):
            if re.match(rf"{u}\b", tail) or re.search(rf"(?<![A-Z]){u}\b", tail[:24]):
                unit = u
                break
        label = up.split("TOTAL", 1)[1]
        label = re.split(r"[:(]|\d", label, 1)[0].strip(" .:-") or "TOTAL"
        out.append(TextTotal(label=label, value=val, unit=unit, raw=line))
    return out


def sums_matching_text(cols, texts, tol: float = TOL) -> list[ColumnTotal]:
    """ทางที่ 2 — บางใบไม่มีแถวรวมในตาราง มียอดรวมเฉพาะที่เขียนเป็นข้อความใต้ตาราง

    ตัวอย่างจริง (Scan2026-09-03_181503 หน้า 4)
        TOTALPCS 150 PCS / TOTALCTNS 4 CTNS / TOTAL N.W. 20.50 KGS ...
    ตารางมีแต่บรรทัดสินค้า ไม่มีแถวรวม find_total_row จึงหาไม่เจอ

    วิธี: บวกทุกค่าในแต่ละคอลัมน์ แล้วดูว่าตรงกับยอดที่เขียนเป็นข้อความหรือไม่
    """
    want = {round(t.value, 4) for t in texts}
    out = []
    for ci, col in enumerate(cols):
        nums = {ri: c.number() for ri, c in col.items() if c.number() is not None}
        if len(nums) < 2:
            continue
        total = round(sum(nums.values()), 4)
        if any(abs(total - w) <= tol for w in want):
            out.append(ColumnTotal(
                col=ci, x=_col_x(col), line_rows=sorted(nums),
                values=[nums[r] for r in sorted(nums)],
                computed=total, printed=total, trivial=False))
    return sorted(out, key=lambda c: c.x)


# ---------------- ผลลัพธ์รวม ----------------
@dataclass
class PackingList:
    total_row: int | None = None
    columns: list[ColumnTotal] = field(default_factory=list)
    texts: list[TextTotal] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    status: str = "ยังไม่ได้อ่าน"

    @property
    def ok(self) -> bool:
        return self.total_row is not None and not self.issues


def cross_check(columns: list[ColumnTotal], texts: list[TextTotal],
                tol: float = TOL) -> list[str]:
    """เทียบยอดรวมที่เขียนเป็นข้อความ กับยอดรวมในตาราง

    กรณีที่ต้องจับให้ได้: ข้อความไปตรงกับ **ค่าบรรทัดเดียว** แทนที่จะเป็นยอดรวม
    คือสิ่งที่เกิดขึ้นจริงกับ TOTAL MEASUREMENT: 9.19CBM (ค่าบรรทัด)
    ทั้งที่ตารางรวมได้ 18.38

    ส่วนข้อความที่ไม่ตรงกับอะไรเลย **ไม่นับเป็นข้อผิดพลาด** เพราะเอกสารมักเขียน
    ข้อความที่ไม่มีคอลัมน์รองรับ เช่น "TOTAL PACKED ON ONE (1) PALLET"
    ในตารางที่ไม่มีคอลัมน์พาเลท — ถ้าฟ้องจะกลายเป็นเตือนผิดแทบทุกใบ
    จึงบันทึกว่า "ตรวจไม่ได้" ให้คนดูแทน
    """
    issues = []
    totals = {round(c.printed, 4) for c in columns}
    for t in texts:
        # ถ้าบรรทัดนั้นมีตัวเลขอื่นที่เป็นยอดรวมอยู่ด้วย แปลว่านี่คือแถวรวมในตารางเอง
        # ไม่ใช่ข้อความใต้ตาราง จึงไม่ต้องเทียบ
        from .numbers import parse_number
        others = [parse_number(tok) for tok in re.findall(r"[\d][\d.,]*", t.raw)]
        if any(v is not None and round(v, 4) in totals and abs(v - t.value) > tol
               for v in others):
            t.matched = "เป็นแถวรวมในตารางเอง ไม่ใช่ข้อความใต้ตาราง"
            continue

        if any(abs(c.printed - t.value) <= tol for c in columns):
            t.matched = "ตรงกับยอดรวมในตาราง"
            continue

        line_hit = [c for c in columns
                    if any(abs(v - t.value) <= tol for v in c.values)]
        if line_hit:
            t.matched = "ตรงกับค่าของบรรทัดเดียว ไม่ใช่ยอดรวม"
            issues.append(
                f"ข้อความใต้ตาราง '{t.raw}' ระบุ {t.value:g} "
                f"ซึ่งตรงกับค่าของบรรทัดเดียวในตาราง ไม่ใช่ยอดรวม "
                f"(ยอดรวมของคอลัมน์นั้นคือ {line_hit[0].printed:g})")
        else:
            t.matched = "ไม่มีคอลัมน์ในตารางให้เทียบ — ตรวจไม่ได้"
    return issues


def analyze_packing_list(rows, text: str = "") -> PackingList:
    """อ่าน Packing List จากแถวที่จัดกลุ่มแล้ว + ข้อความทั้งหน้า"""
    res = PackingList()
    cols = numeric_columns(numeric_rows(rows))
    if len(cols) < 2:
        res.status = "ไม่พบตารางตัวเลข"
        return res

    ri, agree = find_total_row(cols)
    res.texts = text_totals(text)
    if ri is None:
        alt = sums_matching_text(cols, res.texts)
        if len(alt) >= MIN_COLS_AGREE:
            res.columns = alt
            for t in res.texts:
                if any(abs(c.computed - t.value) <= TOL for c in alt):
                    t.matched = "ตรงกับผลบวกของคอลัมน์"
                elif any(abs(v - t.value) <= TOL for c in alt for v in c.values):
                    t.matched = "ตรงกับค่าของบรรทัดเดียว ไม่ใช่ยอดรวม"
                    res.issues.append(
                        f"ข้อความใต้ตาราง '{t.raw}' ระบุ {t.value:g} "
                        f"ซึ่งตรงกับค่าของบรรทัดเดียวในตาราง ไม่ใช่ยอดรวม")
                else:
                    t.matched = "ไม่มีคอลัมน์ในตารางให้เทียบ — ตรวจไม่ได้"
            n_line = len({r for c in alt for r in c.line_rows})
            res.status = (f"ไม่มีแถวรวมในตาราง — ยืนยันด้วยยอดรวมที่เขียนเป็นข้อความ "
                          f"{len(alt)} คอลัมน์ {n_line} บรรทัด")
            return res
        res.status = ("ไม่พบแถวรวมที่ผลบวกลงตัว — อาจอ่านตารางไม่ครบ ต้องให้คนตรวจ")
        return res

    res.total_row = ri
    res.columns = column_totals(cols, ri, agree)
    n_solid = sum(1 for c in res.columns if not c.trivial)
    if n_solid < MIN_COLS_AGREE:
        res.total_row = None
        res.columns = []
        res.status = ("แถวรวมลงตัวจากคอลัมน์ที่มีบรรทัดเดียวเท่านั้น "
                      "เชื่อไม่ได้ ต้องให้คนตรวจ")
        return res

    res.issues = cross_check(res.columns, res.texts)
    n_line = len({r for c in res.columns for r in c.line_rows})
    res.status = (f"ผลรวมลงตัว {len(res.columns)} คอลัมน์ {n_line} บรรทัด"
                  + (f" | พบข้อขัดแย้ง {len(res.issues)} จุด" if res.issues else ""))
    return res
