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

from .tables import numeric_columns, _col_x, Row, Cell
from .numbers import parse_number

MAX_TOKENS_IN_NUMERIC_CELL = 2   # เซลล์ตัวเลขจริงมีได้ไม่เกิน "ค่า + หน่วย"


_NUM_WITH_UNIT = re.compile(
    r"^(?P<num>\d[\d.,]*)\s*(?P<unit>[A-Za-z][A-Za-z0-9]{0,4})$")


def split_units(rows):
    """แยกหน่วยออกจากตัวเลข แล้วหดกล่องให้เหลือเฉพาะส่วนที่เป็นตัวเลข

    ทำไมต้องมี: numeric_columns() จัดคอลัมน์จากขอบขวาของเซลล์
    บรรทัดสินค้ามักเขียนตัวเลขเปล่า แต่แถวรวมเขียนหน่วยติดมาด้วย
    เซลล์แถวรวมจึงกว้างกว่าและขอบขวาเลื่อนไปตรงกับคอลัมน์ถัดไป

    ของจริง SKM_450i26090315172 หน้า 8
      บรรทัดสินค้า  1000       167        1,767.33
      แถวรวม        27526PCS   2006CTNS   16123.02KGS
    ทั้งแถวรวมเลื่อนไปหนึ่งคอลัมน์ ระบบจึงหาแถวรวมไม่เจอทั้งที่ตัวเลขถูกหมด

    ตัดตำแหน่งตามสัดส่วนจำนวนตัวอักษร ซึ่งตรงพอดีเมื่อความกว้างตัวอักษรใกล้เคียงกัน
    ถ้าทุกบรรทัดมีหน่วยเหมือนกัน ทุกเซลล์ก็หดเท่ากัน คอลัมน์ยังตรงเหมือนเดิม
    """
    out = []
    for r in rows:
        cells = []
        for c in r.cells:
            t = c.text.strip()
            m = _NUM_WITH_UNIT.match(t)
            if m is None or parse_number(m.group("num")) is None:
                cells.append(c)
                continue
            w = c.x1 - c.x0
            xa = c.x0 + w * m.end("num") / len(t)
            xb = c.x0 + w * m.start("unit") / len(t)
            cells.append(Cell(m.group("num"), c.x0, c.y0, xa, c.y1))
            cells.append(Cell(m.group("unit"), xb, c.y0, c.x1, c.y1))
        cells.sort(key=lambda c: c.x0)
        out.append(Row(cells))
    return out


def numeric_rows(rows, max_tokens: int = MAX_TOKENS_IN_NUMERIC_CELL):
    """ตัดเซลล์ที่เป็นประโยคออกก่อนจัดคอลัมน์

    ทำไมต้องมี: `parse_number` ดึงเลขจากข้อความอะไรก็ได้ ประโยคใต้ตารางอย่าง
    "TOTAL PACKED IN EIGHT (8) PLTS ONLY." จึงถูกอ่านเป็นเลข 8 แล้วถูกจัดเข้า
    คอลัมน์พาเลทเพราะขอบขวาบังเอิญตรงกัน ทำให้ผลรวมของคอลัมน์นั้นเพี้ยน
    (พบจริงตอนทดสอบกับ Packing List ของชุดที่ 4 — คอลัมน์พาเลทหายไปทั้งคอลัมน์)

    เซลล์ตัวเลขจริงมีได้อย่างมาก 2 คำ คือค่ากับหน่วย เช่น `3424.00KGS` หรือ `500 M`
    """
    out = []
    for r in split_units(rows):
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
    unit: str = ""                 # หน่วยที่เขียนติดกับค่าในแถวรวม เช่น CTNS KGS
    label: str = ""                # ป้ายชื่อจากยอดรวมที่เขียนเป็นข้อความใต้ตาราง


def find_total_row(cols, tol: float = TOL, min_cols: int = MIN_COLS_AGREE):
    """หาแถวรวมด้วยเลขคณิตล้วน

    ทุกคอลัมน์ทุกแถว ถามว่า "ค่านี้เท่ากับผลบวกของค่าที่อยู่ **เหนือมัน** ในคอลัมน์เดียวกันหรือไม่"
    แถวที่ได้เสียงจากหลายคอลัมน์ที่สุดคือแถวรวม

    ที่ต้องนับเฉพาะแถวเหนือแถวรวม เพราะท้ายกระดาษมีตัวเลขที่ไม่ใช่บรรทัดสินค้า
    และมักอยู่ตรงกับคอลัมน์พอดี เช่นของ VORETO
      版本号：1.1     ถูกอ่านเป็น 1.1 เข้าคอลัมน์น้ำหนักสุทธิ ทำให้เกินยอดรวม 1.10
      Version: V.01  ถูกอ่านเป็น 1   เข้าคอลัมน์จำนวน       ทำให้เกินยอดรวม 1.00
    แถวรวมคือผลบวกของบรรทัดที่อยู่เหนือมันตามนิยาม การนับแถวใต้มันจึงผิดตั้งแต่ต้น

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
            rest = [v for r, v in nums.items() if r < ri]
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


def _unit_beside(rows, ri, cell):
    """หน่วยที่เขียนติดกับค่าในแถวรวม เช่น `2006 CTNS`

    split_units() แยกหน่วยออกมาเป็นเซลล์ของตัวเองแล้ว หน่วยจึงอยู่ถัดไปทางขวา
    ของเซลล์ค่าเสมอ ใช้ตั้งชื่อคอลัมน์ได้โดยไม่ต้องอ่านหัวตาราง
    ซึ่งสำคัญเพราะหัวตารางที่ OCR อ่านมามักเพี้ยนจนเทียบคำไม่ได้
    (VORETO ได้ `Quendlry | UnktPrice | Weig(KGS)`)
    """
    if not (0 <= ri < len(rows)) or cell is None:
        return ""
    best = None
    for c in rows[ri].cells:
        if c.number() is not None:
            continue
        t = c.text.strip().upper().strip(".:,")
        if t not in UNITS:
            continue
        gap = c.x0 - cell.x1
        if -2.0 <= gap <= max(cell.h, 1.0) * 2 and (best is None or gap < best[0]):
            best = (gap, t)
    return best[1] if best else ""


def column_totals(cols, total_row: int, agree: list[int],
                  rows=None) -> list[ColumnTotal]:
    out = []
    for ci in agree:
        col = cols[ci]
        nums = {ri: c.number() for ri, c in col.items() if c.number() is not None}
        printed = nums[total_row]
        # เหตุผลเดียวกับใน find_total_row — นับเฉพาะบรรทัดเหนือแถวรวม
        lines = {r: v for r, v in nums.items() if r < total_row}
        out.append(ColumnTotal(
            col=ci, x=_col_x(col),
            line_rows=sorted(lines), values=[lines[r] for r in sorted(lines)],
            computed=round(sum(lines.values()), 4), printed=printed,
            trivial=len(lines) < 2,
            unit=_unit_beside(rows, total_row, col.get(total_row)) if rows else ""))
    return sorted(out, key=lambda c: c.x)


# คำที่บ่งบอกว่าเป็น "ชื่อของสิ่งที่วัด" จริง ๆ ไม่ใช่การสะกดจำนวนเป็นตัวหนังสือ
# ถ้าไม่กรอง `SAY TOTAL FOUR HUNDRED (400) CTNS ONLY` จะให้ป้ายว่า "FOUR HUNDRED"
NAME_WORDS = ("WEIGHT", "MEASUREMENT", "MEASURE", "VOLUME", "QUANTITY", "QTY",
              "CARTON", "CTNS", "CTN", "PACKAGE", "PKGS", "PALLET", "PLTS",
              "PIECES", "PCS", "NET", "GROSS", "N.W", "G.W", "CBM",
              "น้ำหนัก", "ปริมาตร", "จำนวน", "หีบห่อ")


def _is_name(label):
    up = (label or "").upper()
    return any(w in up for w in NAME_WORDS)


WEIGHT_UNITS = ("KGS", "KG", "KGM")


def _name_weight_pair(columns):
    """แยกน้ำหนักสุทธิกับน้ำหนักรวม ด้วยกฎทางกายภาพ

    น้ำหนักรวม = น้ำหนักสุทธิ + บรรจุภัณฑ์ จึงมากกว่าเสมอ
    ใช้ได้เมื่อมีคอลัมน์หน่วยน้ำหนักสองคอลัมน์พอดี และยังไม่มีป้ายชื่อจากข้อความ

    หลักฐานนี้อ่อนกว่าการจับคู่ด้วยค่าจากข้อความใต้ตาราง จึงบันทึกที่มาไว้ด้วย
    ถ้าค่าเท่ากันแปลว่าแยกไม่ออก ต้องไม่เดา
    """
    kg = [c for c in columns
          if (c.unit or "").upper() in WEIGHT_UNITS and not c.label]
    if len(kg) != 2:
        return []
    lo, hi = sorted(kg, key=lambda c: c.printed)
    if abs(hi.printed - lo.printed) <= TOL:
        return ["สองคอลัมน์น้ำหนักมีค่าเท่ากัน แยกสุทธิกับรวมไม่ได้ ต้องให้คนดู"]
    lo.label, hi.label = "NET WEIGHT", "GROSS WEIGHT"
    return [f"แยกน้ำหนักสุทธิ ({lo.printed:,g}) กับน้ำหนักรวม ({hi.printed:,g}) "
            f"จากกฎที่ว่าน้ำหนักรวมมากกว่าสุทธิเสมอ ไม่ได้อ่านจากป้ายชื่อในเอกสาร"]


def _unit_row_names(columns, rows, first_line_row):
    """ชื่อจากแถวที่มีแต่หน่วยล้วนในหัวตาราง

    ของจริง SKM_450i26090410270 หน้า 3
      r9   ITEM NO. | PACKAGES... | G.W. | N.W. | VOL
      r10                           KGS  | KGS  | CBM
    แถวหน่วยแบบนี้ความหมายไม่กำกวม เหลือแค่ต้องจับให้ตรงคอลัมน์

    หลักฐานนี้อาศัยตำแหน่ง ไม่ใช่เลขคณิต จึงอ่อนกว่าสองทางแรก
    ใช้ต่อเมื่อคอลัมน์นั้นยังไม่มีชื่อ และจับคู่ได้แบบไม่กำกวมเท่านั้น
    """
    if not rows:
        return []
    cands = []
    for ri in range(min(first_line_row, len(rows))):
        cells = [c for c in rows[ri].cells if c.number() is None]
        if len(cells) < 2 or len(cells) != len(rows[ri].cells):
            continue
        us = [c for c in cells if c.text.strip().upper().strip(".:,") in UNITS]
        if len(us) == len(cells):
            cands.append(us)
    if not cands:
        return []
    marks = cands[-1]                      # แถวหน่วยที่อยู่ใกล้ตารางที่สุด
    named = []
    for c in columns:
        if c.unit or c.label:
            continue
        near = sorted(marks, key=lambda m: abs((m.x0 + m.x1) / 2 - c.x))
        if not near:
            continue
        best = near[0]
        span = max(best.x1 - best.x0, 1.0)
        if abs((best.x0 + best.x1) / 2 - c.x) > span * 2.5:
            continue
        if len(near) > 1 and abs(
                abs((near[1].x0 + near[1].x1) / 2 - c.x)
                - abs((best.x0 + best.x1) / 2 - c.x)) < span * 0.5:
            continue                       # ใกล้พอกันสองอัน ไม่เดา
        c.unit = best.text.strip().upper().strip(".:,")
        named.append(c)
    if named:
        return [f"ตั้งชื่อ {len(named)} คอลัมน์จากแถวหน่วยในหัวตาราง "
                f"ซึ่งอาศัยตำแหน่ง ไม่ใช่เลขคณิต ควรตรวจซ้ำ"]
    return []


def name_columns(columns, texts, tol: float = TOL, rows=None):
    """ตั้งชื่อคอลัมน์ด้วยเลขคณิต ไม่ใช่ด้วยคำในหัวตาราง

    ยอดรวมที่เขียนเป็นข้อความใต้ตารางบอกทั้งค่าและความหมาย
      TOTAL GROSS WEIGHT: 3424.00KGS  ->  คอลัมน์ที่รวมได้ 3424 คือน้ำหนักรวม
    จับคู่ด้วยค่า จึงไม่ขึ้นกับว่าหัวตารางสะกดถูกหรือไม่

    คืนรายการข้อสังเกตที่ต้องให้คนดู เมื่อสองคอลัมน์ได้ชื่อเดียวกัน
    """
    notes = []
    for c in columns:
        for t in texts:
            if not _is_name(t.label):
                continue
            if abs(t.value - c.printed) <= tol or abs(t.value - c.computed) <= tol:
                c.label = t.label
                if not c.unit:
                    c.unit = t.unit
                break

    first_line = min((r for c in columns for r in c.line_rows), default=0)
    notes += _unit_row_names(columns, rows, first_line)
    notes += _name_weight_pair(columns)

    seen = {}
    for c in columns:
        key = (c.label or "", c.unit or "")
        if key == ("", ""):
            continue
        seen.setdefault(key, []).append(c)
    for (label, unit), group in seen.items():
        if len(group) > 1:
            xs = ", ".join(f"x={c.x:.0f} รวม {c.printed:,g}" for c in group)
            notes.append(
                f"{len(group)} คอลัมน์ได้ชื่อเดียวกัน '{label or unit}' ({xs}) "
                f"— แยกไม่ออกว่าคอลัมน์ไหนคืออะไร ต้องให้คนดู")
    return notes


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
    notes: list[str] = field(default_factory=list)   # ข้อสังเกตที่ไม่ถึงขั้นขัดแย้ง
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
    clean = numeric_rows(rows)
    cols = numeric_columns(clean)
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
    res.columns = column_totals(cols, ri, agree, clean)
    n_solid = sum(1 for c in res.columns if not c.trivial)
    if n_solid < MIN_COLS_AGREE:
        # ตารางที่มีบรรทัดสินค้าบรรทัดเดียว ยอดรวมย่อมเท่ากับบรรทัดนั้นเสมอ
        # เลขคณิตจึงยืนยันอะไรไม่ได้ ต้องหาหลักฐานอีกทางที่ไม่เกี่ยวกัน
        # หลักฐานนั้นคือแถวนั้นเขียนคำว่ายอดรวมไว้เอง
        # (SKM_450i26090410270 หน้า 3 — r12 ขึ้นต้นว่า "TOTAL:" ตรงกันครบ 5 คอลัมน์)
        labeled = 0 <= ri < len(clean) and clean[ri].is_total_row()
        if labeled and len(res.columns) >= MIN_COLS_AGREE:
            res.issues = cross_check(res.columns, res.texts)
            res.notes = name_columns(res.columns, res.texts, rows=clean)
            n_line = len({r for c in res.columns for r in c.line_rows})
            res.status = (
                f"ตารางมีบรรทัดสินค้า {n_line} บรรทัด ผลรวมยืนยันด้วยเลขคณิตไม่ได้ "
                f"แต่แถวนี้เขียนว่ายอดรวม และตรงกันครบ {len(res.columns)} คอลัมน์"
                + (f" | พบข้อขัดแย้ง {len(res.issues)} จุด" if res.issues else ""))
            return res
        res.total_row = None
        res.columns = []
        res.status = ("แถวรวมลงตัวจากคอลัมน์ที่มีบรรทัดเดียวเท่านั้น "
                      "และแถวนั้นไม่ได้เขียนว่ายอดรวม เชื่อไม่ได้ ต้องให้คนตรวจ")
        return res

    res.issues = cross_check(res.columns, res.texts)
    res.notes = name_columns(res.columns, res.texts, rows=clean)
    n_line = len({r for c in res.columns for r in c.line_rows})
    res.status = (f"ผลรวมลงตัว {len(res.columns)} คอลัมน์ {n_line} บรรทัด"
                  + (f" | พบข้อขัดแย้ง {len(res.issues)} จุด" if res.issues else ""))
    return res
