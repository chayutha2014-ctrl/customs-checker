# -*- coding: utf-8 -*-
"""กวาดค่ากำพร้า — ค่าที่ปรากฏในเอกสารแต่ไม่มีตัวอ่านไหนอ้างถึง

ตัวอ่านทุกตัวมองหาเฉพาะสิ่งที่รู้ว่าต้องมี ไม่มีตัวไหนถามว่า
"มีค่าอะไรบนหน้านี้ที่ยังไม่มีใครอ้างถึงบ้าง"

ค่ากำพร้าปิดรากของข้อผิดพลาดที่กฎทั้งหมดมองไม่เห็น สองแบบ
  ค่าที่ไม่มีใครคิดจะอ่าน      ไม่อยู่ใน checklist ของกฎข้อใดเลย
  อ่านผิดช่อง                 ตัวอ่านบอกว่าช่องนั้นไม่มีค่า ทั้งที่ค่าอยู่ตรงนั้น

ข้อสองสำคัญกว่า — ถ้าตัวอ่านบอกว่า "ไม่พบน้ำหนัก" แต่มีตัวเลขกำพร้าที่หน้าตา
เหมือนน้ำหนักอยู่ในหน้า นั่นคือสัญญาณว่าอ่านผิดช่อง ไม่ใช่ว่าเอกสารไม่มี

ค่ากำพร้าเป็น **ข้อสังเกต** ไม่ใช่ข้อบกพร่อง เพราะเอกสารมีตัวเลขที่ไม่เกี่ยวข้องเสมอ
หน้าที่ของมันคือชี้จุดให้คนดู ไม่ใช่ตัดสิน
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from customs_checker.numbers import parse_number

TOL = 0.01

# ต้องเป็น {1,} ไม่ใช่ {2,} หรือ {3,}
# จำนวนหีบห่อเกือบทุกเคสอยู่ในช่วง 1-3 หลัก การตัดเลขสั้นทิ้งคือการตัดสิ่งที่ต้องการหา
_NUM = re.compile(r"(?<![\d.,])(\d[\d,]*(?:\.\d+)?)(?![\d.,])")
_CODE = re.compile(r"\b(?=[A-Z0-9/\-]*\d)(?=[A-Z0-9/\-]*[A-Z])[A-Z0-9][A-Z0-9/\-]{4,}\b")
_MONTH = (r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
          r"(?:UARY|RUARY|CH|IL|E|Y|UST|TEMBER|OBER|EMBER)?")
_DATE = re.compile(
    r"\b(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}"                    # 03/09/2026
    rf"|{_MONTH}\.?\s*\d{{1,2}},?\s*\d{{2,4}}"                  # AUG. 15,2026
    rf"|\d{{1,2}}\s*[-/\s]\s*{_MONTH}\.?\s*[-/\s]\s*\d{{2,4}}"  # 3-Sep-26
    rf"|\d{{1,2}}\s*{_MONTH}\.?\s*\d{{4}})\b", re.I)           # 27AUG2026

# บรรทัดที่เป็นข้อความมาตรฐานของฟอร์ม ไม่ใช่ข้อมูลของงาน
_BOILER = re.compile(
    r"INSTITUTE|CLAUSE|EXCLUSION|NUCLEAR|RADIOACTIVE|ELECTROMAGNETIC|"
    r"COMMUNICABLE|TERRORISM|SANCTION|WARRANT|SUBJECT\s*TO|TERMS\s*AND|"
    r"E-?MAIL|TEL\b|FAX\b|WWW\.|HTTP|@|OVERLEAF|DECLARATION\s*BY|"
    r"UNDERSIGNED|HEREBY|CERTIFY|CERTIFIED|LLOYD|AGENTS|SIGNATURE|"
    r"IN\s*WITNESS|AUTHORIZED|REV\.", re.I)


# บรรทัดที่อยู่และข้อมูลติดต่อ ไม่ใช่ข้อมูลของงาน
# ไม่ใช้ขอบคำ เพราะ OCR เชื่อมคำติดกัน "DevesInsuranceBuilding"
_ADDRESS = re.compile(
    r"ROAD|\bRD\.?|MOO|\bSOI|FLOOR|BUILDING|BLDG|DISTRICT|PROVINCE|AVENUE|"
    r"STREET|ESTATE|BANGKOK|THAILAND|CHINA|VIETNAM|TAIWAN|KOREA|JAPAN|"
    r"SINGAPORE|TAX\s*ID|POSTAL|ZIPCODE|INSURANCEBUILDING", re.I)

# หน่วยที่บอกว่าเลขตัวนั้นเป็นปริมาณหรือน้ำหนัก
_UNIT_NEAR = re.compile(
    r"\b(KGS?|KGM|CBM|M3|CTNS?|CARTONS?|PALLETS?|PLTS?|PCS|PIECES?|SETS?|"
    r"USD|THB|CNY|RMB|EUR|JPY)\b", re.I)


@dataclass
class Token:
    text: str
    kind: str            # ตัวเลข · รหัส · วันที่
    value: float | None
    row: int
    line: str
    boilerplate: bool = False
    tier: int = 4          # 1 สำคัญที่สุด · 4 แทบไม่เกี่ยวข้อง
    why: str = ""


@dataclass
class OrphanReport:
    tokens: list = field(default_factory=list)      # ค่ากำพร้าที่น่าสนใจ (ชั้น 1-3)
    minor: list = field(default_factory=list)       # ชั้น 4 นับไว้ ไม่ทิ้งเงียบ
    boilerplate: int = 0                            # ค่ากำพร้าในข้อความมาตรฐาน
    matched: int = 0                                # ค่าที่ตัวอ่านอ้างถึงแล้ว
    suspects: list = field(default_factory=list)    # ชนกับช่องที่บอกว่าไม่มี
    notes: list = field(default_factory=list)

    def by_kind(self, kind):
        return [t for t in self.tokens if t.kind == kind]

    def by_tier(self, tier):
        return [t for t in self.tokens + self.minor if t.tier == tier]


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def tokenize(texts):
    """ดึงค่าที่มีสาระออกจากทุกบรรทัด"""
    out = []
    for ri, raw in enumerate(texts):
        line = str(raw)
        boiler = bool(_BOILER.search(line))
        seen = set()
        for m in _DATE.finditer(line):
            t = m.group(0).strip()
            seen.add((m.start(), m.end()))
            out.append(Token(t, "วันที่", None, ri, line, boiler))
        for m in _NUM.finditer(line):
            if any(a <= m.start() < b for a, b in seen):
                continue
            out.append(Token(m.group(1), "ตัวเลข", parse_number(m.group(1)),
                             ri, line, boiler))
        for m in _CODE.finditer(line.upper()):
            if any(a <= m.start() < b for a, b in seen):
                continue
            out.append(Token(m.group(0), "รหัส", None, ri, line, boiler))
    return out


def _claimed_sets(claimed):
    nums, strs = set(), set()
    for c in claimed:
        if c is None:
            continue
        if isinstance(c, (int, float)):
            nums.add(round(float(c), 4))
            continue
        v = parse_number(str(c))
        if v is not None:
            nums.add(round(v, 4))
        n = _norm(c)
        if n:
            strs.add(n)
    return nums, strs


_LEAD_NUM = re.compile(r"^(\d[\d,]*(?:\.\d+)?)([A-Z].*)?$")


def _is_claimed(tok, nums, strs):
    if tok.value is not None:
        if any(abs(tok.value - n) <= TOL for n in nums):
            return True
    n = _norm(tok.text)
    if not n:
        return True
    if n in strs:
        return True
    if any(n in s for s in strs if len(s) >= len(n)):
        return True
    # รหัสที่ขึ้นต้นด้วยตัวเลขแล้วตามด้วยหน่วย เช่น 3000PIECES
    # ถ้าตัวเลขนั้นถูกอ้างถึงแล้ว ก็ไม่ใช่ค่ากำพร้า
    m = _LEAD_NUM.match(n)
    if m:
        v = parse_number(m.group(1))
        if v is not None and any(abs(v - x) <= TOL for x in nums):
            return True
    return False


def rank(tok):
    """จัดชั้นความสำคัญของค่ากำพร้า

    เอกสารมีตัวเลขที่ไม่ใช่ข้อมูลของงานเสมอ — ที่อยู่ รหัสไปรษณีย์ เบอร์ตึก
    ถ้าเทกองรวมกันหมด รายงานจะท่วมจนไม่มีใครอ่าน (เคยได้ 27 ตัวต่อหน้า)
    แต่ห้ามทิ้งเงียบ จึงจัดชั้นแล้วนับชั้นล่างไว้

    1  จำนวนที่มีทศนิยมหรือคั่นหลักพัน หรือมีหน่วยอยู่ในบรรทัดเดียวกัน
    2  วันที่
    3  จำนวนเต็มในบรรทัดที่มีหน่วยหรือคำบ่งชี้สินค้า
    4  ที่เหลือ — ที่อยู่ เบอร์โทร รหัสไปรษณีย์ ชื่อบริษัทที่มีตัวเลข
    """
    if _ADDRESS.search(tok.line):
        return 4, "อยู่ในบรรทัดที่อยู่หรือข้อมูลติดต่อ"
    has_unit = bool(_UNIT_NEAR.search(tok.line))
    if tok.kind == "วันที่":
        return 2, "วันที่ที่ยังไม่มีตัวอ่านไหนอ่าน"
    if tok.kind == "ตัวเลข":
        t = tok.text
        if "." in t or "," in t:
            return 1, "มีทศนิยมหรือคั่นหลักพัน น่าจะเป็นจำนวนหรือน้ำหนัก"
        if has_unit:
            return 3, "จำนวนเต็มในบรรทัดที่มีหน่วย"
        return 4, "จำนวนเต็มที่ไม่มีหน่วยกำกับ"
    if has_unit:
        return 3, "รหัสในบรรทัดที่มีหน่วย"
    return 4, "รหัสทั่วไป"


def orphan_scan(texts, claimed, absent_kinds=()):
    """คืนค่าที่ปรากฏในเอกสารแต่ไม่มีตัวอ่านไหนอ้างถึง

    claimed      ค่าที่ตัวอ่านรายงานออกมาแล้ว ทั้งตัวเลขและข้อความ
    absent_kinds ชนิดของช่องที่ตัวอ่านบอกว่าไม่มีค่า เช่น ("ตัวเลข",)
                 ถ้ามีค่ากำพร้าชนิดเดียวกัน จะขึ้นเป็นข้อสงสัยว่าอ่านผิดช่อง
    """
    nums, strs = _claimed_sets(claimed)
    res = OrphanReport()
    for tok in tokenize(texts):
        if _is_claimed(tok, nums, strs):
            res.matched += 1
            continue
        if tok.boilerplate:
            res.boilerplate += 1
            continue
        # ค่าเดียวกันที่ปรากฏหลายที่ นับครั้งเดียวพอ ไม่งั้นรายงานจะท่วม
        if any(t.text == tok.text and t.kind == tok.kind
               for t in res.tokens + res.minor):
            continue
        tok.tier, tok.why = rank(tok)
        (res.minor if tok.tier >= 4 else res.tokens).append(tok)

    for kind in absent_kinds:
        hit = res.by_kind(kind)
        if hit:
            res.suspects.append(
                f"ตัวอ่านบอกว่าไม่พบค่าชนิด {kind} แต่มีค่ากำพร้าชนิดเดียวกัน "
                f"{len(hit)} ตัว: "
                + ", ".join(t.text for t in hit[:5])
                + " — อาจอ่านผิดช่อง ไม่ใช่เอกสารไม่มี")

    if res.tokens or res.minor:
        res.notes.append(
            f"ค่ากำพร้าที่ควรดู {len(res.tokens)} ตัว "
            f"(ชั้น1 {len(res.by_tier(1))} · ชั้น2 {len(res.by_tier(2))} · "
            f"ชั้น3 {len(res.by_tier(3))}) "
            f"· ชั้น4 ที่อยู่และรหัสทั่วไป {len(res.minor)} ตัว "
            f"· ในข้อความมาตรฐาน {res.boilerplate} ตัว")
    return res
