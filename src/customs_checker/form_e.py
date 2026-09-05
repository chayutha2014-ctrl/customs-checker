# -*- coding: utf-8 -*-
"""อ่าน Form E — หนังสือรับรองถิ่นกำเนิดสินค้า ACFTA (อาเซียน-จีน)

Form E มีตัวเลขให้ตรวจน้อยกว่าเอกสารอื่น แต่มีสิ่งที่ชดเชย
**จำนวนหีบห่อเขียนทั้งตัวหนังสือและตัวเลขคู่กัน**

  SIX HUNDRED AND SIXTY SEVEN (667)CARTONS
  TOTAL:FIVE(5)PALLETS ONL

เป็นการยืนยันแบบเดียวกับจำนวนเงินตัวหนังสือในกรมธรรม์ ใช้ตัวแปลงเดิมได้เลย

สิ่งที่ตรวจได้เองในใบเดียว
  1. เลขที่อ้างอิง E + ตัวเลข 15 หลัก และทุกแผ่นของฉบับเดียวกันต้องตรงกัน
  2. จำนวนหีบห่อ ตัวหนังสือตรงกับตัวเลขในวงเล็บ
  3. ผลบวกหีบห่อรายรายการ = ยอดรวมท้ายตาราง
  4. พิกัดศุลกากร รูปแบบ 4 หลัก จุด 2 หลัก
  5. เกณฑ์ถิ่นกำเนิด ต้องเป็นค่าในชุดที่เป็นไปได้

ข้อ 4 กับ 5 เป็น "ชุดค่าที่เป็นไปได้" ซึ่งอยู่เฟส 1 เพราะทำให้อ่านแม่นขึ้น
ส่วนการตรวจว่าเกณฑ์ที่กรอกถูกต้องกับสินค้านั้นหรือไม่ เป็นเฟส 2
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from customs_checker.amount_words import words_to_number
from customs_checker.numbers import parse_number

# เลขที่อ้างอิง Form E ขึ้นต้นด้วย E แล้วตามด้วยตัวเลข 15 หลัก
# OCR อ่าน E เป็น F ได้ จึงยอมรับไว้ก่อนแล้วรายงานว่าผิดรูปแบบ
_REF = re.compile(r"\b([EF])\s?(\d{15})\b")

# OCR อ่าน CODE เป็น C0DE ด้วยเลขศูนย์ทุกแผ่น จึงต้องไม่ยึดคำ
_HS = re.compile(r"HS\s*C[O0]DE\s*[:：]?\s*(\d{4})\s*[.\s]\s*(\d{2})", re.I)

# จำนวนที่เขียนตัวหนังสือแล้วตามด้วยตัวเลขในวงเล็บ
# OCR อ่านเลขศูนย์เป็นตัวอักษร O ได้  (10O) ที่จริงคือ (100)
# จึงรับ O ไว้ในกลุ่มตัวเลขแล้วแปลงกลับ ตัวหนังสือกำกับจะเป็นตัวยืนยันว่าแก้ถูก
_WORD_NUM = re.compile(
    r"([A-Z][A-Z\s\-]{2,60})\s*[（(]\s*([\dOo][\dOo,]*)\s*[)）]\s*"
    r"(CARTONS?|PALLETS?|PIECES?|PCS|SETS?|CASES?|PKGS?)", re.I)

_QTY = re.compile(r"(\d[\d,]*)\s*(PIECES?|PCS|SETS?|CARTONS?|PALLETS?)", re.I)
_VALUE = re.compile(r"([A-Z]{3})\s*[:：]\s*([\d,]+\.\d{2})")
_PAGE = re.compile(r"PAGE\s*(\d+)\s*[O0]F\s*(\d+)", re.I)

# เกณฑ์ถิ่นกำเนิดที่เป็นไปได้ของ Form E
ORIGIN_CRITERIA = ("WO", "PE", "PSR", "CTH", "RVC40", "RVC 40",
                   "RVC(40)", "CC", "WO-AK")
_CRIT_CLEAN = re.compile(r"[^A-Z0-9()]+")


@dataclass
class Item:
    number: int | None = None
    hs_code: str | None = None
    origin_criterion: str | None = None
    quantity: float | None = None
    quantity_unit: str | None = None
    value: float | None = None
    currency: str | None = None
    packages: float | None = None
    packages_unit: str | None = None
    packages_in_words: float | None = None


@dataclass
class FormE:
    reference_no: str | None = None
    ref_variants: list = field(default_factory=list)
    page: int | None = None
    pages_total: int | None = None
    items: list = field(default_factory=list)
    total_packages: float | None = None
    total_unit: str | None = None
    hs_codes: list = field(default_factory=list)
    criteria: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    status: str = "ยังไม่ได้อ่าน"


def texts_of(rows):
    out = []
    for r in rows:
        if isinstance(r, str):
            out.append(r)
        elif hasattr(r, "text"):
            out.append(r.text())
        else:
            out.append(" ".join(str(x) for x in r))
    return out


def find_reference(texts):
    """เลขที่อ้างอิง พร้อมรูปแบบที่อ่านได้ทั้งหมด

    คืน (ค่าที่ควรใช้, [รูปแบบที่พบทั้งหมด])
    ถ้าอ่านได้ขึ้นต้นด้วย F ให้รู้ว่าผิดรูปแบบ แต่ยังคืนไว้ให้เห็น
    """
    found = []
    for t in texts:
        for m in _REF.finditer(str(t).upper().replace(" ", "")):
            v = m.group(1) + m.group(2)
            if v not in found:
                found.append(v)
    good = [v for v in found if v.startswith("E")]
    return (good[0] if good else (found[0] if found else None)), found


def find_page_marker(texts):
    for t in texts:
        m = _PAGE.search(str(t))
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def clean_criterion(s):
    return _CRIT_CLEAN.sub("", str(s).upper())


def find_criteria(texts):
    """เกณฑ์ถิ่นกำเนิดที่ปรากฏ พร้อมค่าที่ไม่อยู่ในชุดที่เป็นไปได้"""
    ok, bad = [], []
    allow = {clean_criterion(c) for c in ORIGIN_CRITERIA}
    for t in texts:
        for tok in re.findall(r'["“”]?([A-Z][A-Z0-9()\- ]{0,7})["“”]?', str(t)):
            c = clean_criterion(tok)
            if not c:
                continue
            if c in allow:
                if c not in ok:
                    ok.append(c)
    return ok, bad


def find_hs_codes(texts):
    out = []
    for t in texts:
        for m in _HS.finditer(str(t)):
            code = f"{m.group(1)}.{m.group(2)}"
            if code not in out:
                out.append(code)
    return out


UNITS_W = ("", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN",
           "EIGHT", "NINE", "TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN",
           "FIFTEEN", "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN")
TENS_W = ("", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY",
          "EIGHTY", "NINETY")


def _under_thousand(n):
    out = []
    if n >= 100:
        out += [UNITS_W[n // 100], "HUNDRED"]
        n %= 100
        if n:
            out.append("AND")
    if n >= 20:
        out.append(TENS_W[n // 10])
        n %= 10
        if n:
            out.append(UNITS_W[n])
    elif n:
        out.append(UNITS_W[n])
    return out


def number_to_words(n):
    """เขียนจำนวนเต็มเป็นคำ ใช้ตรวจว่าตัวหนังสือที่อ่านได้เป็นส่วนท้ายของจำนวนหรือไม่"""
    n = int(n)
    if n == 0:
        return "ZERO"
    parts = []
    for scale, name in ((1_000_000, "MILLION"), (1_000, "THOUSAND")):
        if n >= scale:
            parts += _under_thousand(n // scale) + [name]
            n %= scale
    if n:
        if parts and n < 100:
            parts.append("AND")
        parts += _under_thousand(n)
    return " ".join(p for p in parts if p)


def _letters(s):
    return re.sub(r"[^A-Z]", "", str(s).upper())


def words_are_tail_of(words, number):
    """ตัวหนังสือที่อ่านได้เป็นส่วนท้ายของจำนวนนั้นหรือไม่

    ใช้แยก "OCR อ่านตัวหนังสือมาไม่ครบ" ออกจาก "เอกสารเขียนไม่ตรงกัน"
    ของจริง HUNDREDANDTEN(1710) — ส่วนหน้า ONE THOUSAND SEVEN หายไปจาก OCR
    ONE THOUSAND SEVEN HUNDRED AND TEN ลงท้ายด้วย HUNDRED AND TEN จึงสอดคล้องกัน
    """
    if number is None or not words:
        return False
    try:
        full = _letters(number_to_words(number))
    except (ValueError, TypeError):
        return False
    # คำที่จับมามักมีคำอื่นติดหน้า จึงลองตัดคำหน้าออกทีละคำเช่นเดียวกับ words_value
    toks = [t for t in re.split(r"\s+", str(words).strip()) if t]
    for i in range(len(toks)):
        got = _letters(" ".join(toks[i:]))
        if got and len(got) >= 6 and full.endswith(got):
            return True
    return False


def words_value(text):
    """แปลงตัวหนังสือเป็นจำนวน โดยยอมให้มีคำอื่นนำหน้า

    ข้อความที่จับมามักมีคำอื่นติดหน้า เช่น "TOTAL" หรือรหัสสินค้า
    จึงลองตัดคำหน้าออกทีละคำ แล้วใช้ส่วนท้ายที่ยาวที่สุดที่แปลงได้
    ไม่ตัดจนเหลือคำเดียว เพราะจะกลายเป็นการเดา
    """
    toks = [t for t in re.split(r"\s+", str(text or "").strip()) if t]
    for i in range(len(toks)):
        v = words_to_number(" ".join(toks[i:]))
        if v is not None:
            return v
    return None


def find_word_numbers(texts):
    """จำนวนที่เขียนตัวหนังสือแล้วตามด้วยตัวเลขในวงเล็บ

    คืน [(คำ, ตัวเลข, หน่วย, ค่าที่แปลงจากตัวหนังสือ, ข้อความตัวเลขดิบ)]
    ค่าที่แปลงเป็น None แปลว่าแปลงไม่ได้ ไม่ใช่ว่าไม่ตรง
    """
    out = []
    for t in texts:
        for m in _WORD_NUM.finditer(str(t)):
            words = m.group(1).strip()
            raw = m.group(2)
            digits = parse_number(raw.upper().replace("O", "0"))
            unit = m.group(3).upper()
            out.append((words, digits, unit, words_value(words), raw))
    return out


TOL = 0.001


def analyze_form_e(rows):
    """อ่าน Form E หนึ่งแผ่น"""
    res = FormE()
    texts = texts_of(rows)

    res.reference_no, res.ref_variants = find_reference(texts)
    if res.reference_no:
        bad = [v for v in res.ref_variants if not v.startswith("E")]
        if bad and res.reference_no.startswith("E"):
            res.notes.append(
                f"อ่านเลขที่อ้างอิงได้ {', '.join(bad)} ซึ่งไม่ใช่รูปแบบของ Form E "
                f"แต่แผ่นนี้อ่านได้ {res.reference_no} ด้วย จึงใช้ค่านั้น")
        elif bad:
            res.issues.append(
                f"เลขที่อ้างอิง {', '.join(bad)} ไม่ขึ้นต้นด้วย E "
                "ซึ่งเป็นรูปแบบของ Form E — อาจอ่านผิดหรือไม่ใช่ Form E")
        else:
            res.checks.append(f"เลขที่อ้างอิง {res.reference_no} ถูกรูปแบบ")
    else:
        res.notes.append("อ่านเลขที่อ้างอิงไม่ได้")

    res.page, res.pages_total = find_page_marker(texts)
    res.hs_codes = find_hs_codes(texts)
    res.criteria, _ = find_criteria(texts)

    if res.hs_codes:
        res.checks.append(
            f"พิกัดศุลกากร {len(res.hs_codes)} รายการ ถูกรูปแบบทั้งหมด: "
            + ", ".join(res.hs_codes))
    if res.criteria:
        res.checks.append(
            "เกณฑ์ถิ่นกำเนิดอยู่ในชุดที่เป็นไปได้: " + ", ".join(res.criteria))

    # จำนวนหีบห่อ ตัวหนังสือเทียบตัวเลข
    items, total = [], None
    for t in texts:
        for e in find_word_numbers([t]):
            if "TOTAL" in str(t).upper():
                total = e
            else:
                items.append(e)

    n_ok = n_fix = n_tail = 0
    for w, d, u, v, raw in items + ([total] if total else []):
        fixed = d is not None and raw.upper() != raw.upper().replace("O", "0")
        if v is None:
            res.notes.append(
                f"จำนวน {d if d is None else format(d, ',g')} {u} "
                f"มีตัวหนังสือกำกับแต่แปลงไม่ได้ «{w[:36]}» "
                "จึงไม่มีหลักฐานยืนยันตัวเลข")
        elif d is not None and abs(v - d) <= TOL:
            n_ok += 1
            if fixed:
                n_fix += 1
                res.notes.append(
                    f"OCR อ่านตัวเลขเป็น «{raw}» ซึ่งมีตัวอักษร O แทนศูนย์ "
                    f"ตัวหนังสือ «{w[:30]}» ยืนยันว่าเป็น {d:,g}")
        elif words_are_tail_of(w, d):
            n_tail += 1
            res.notes.append(
                f"ตัวหนังสือ «{w[:36]}» = {v:,g} เป็นส่วนท้ายของ {d:,g} "
                "แปลว่า OCR อ่านตัวหนังสือมาไม่ครบ ไม่ใช่เอกสารขัดกัน "
                "แต่การยืนยันอ่อนลง")
        else:
            res.issues.append(
                f"ตัวหนังสือ «{w[:36]}» = {v:,g} "
                f"แต่ตัวเลขในวงเล็บคือ {d} ไม่ตรงกัน")
    if n_ok:
        res.checks.append(
            f"จำนวนหีบห่อ {n_ok} จุด ตัวหนังสือตรงกับตัวเลข"
            + (f" (ในนั้น {n_fix} จุด ตัวหนังสือแก้เลขศูนย์ที่ OCR อ่านเป็น O)"
               if n_fix else ""))
    if n_tail:
        res.notes.append(f"อีก {n_tail} จุด ตัวหนังสือถูกตัดหัว ยืนยันได้บางส่วน")

    if total:
        res.total_packages, res.total_unit = total[1], total[2]
        same = [d for _, d, u, _, _ in items if u == total[2] and d is not None]
        if len(same) >= 2:
            s = round(sum(same), 3)
            if abs(s - total[1]) <= TOL:
                res.checks.append(
                    f"ผลบวกหีบห่อรายรายการ {s:,g} = ยอดรวม {total[1]:,g}")
            else:
                res.issues.append(
                    f"ผลบวกหีบห่อรายรายการ {s:,g} ไม่เท่ากับยอดรวม "
                    f"{total[1]:,g} ต่างกัน {s - total[1]:,g}")
        elif same:
            res.notes.append(
                f"มีรายการหน่วย {total[2]} เพียงรายการเดียว ผลบวกยืนยันอะไรไม่ได้")
        else:
            res.notes.append(
                f"ยอดรวมเป็นหน่วย {total[2]} แต่รายการเป็นหน่วยอื่น เทียบผลบวกไม่ได้")

    res.status = (f"ตรวจผ่าน {len(res.checks)} ข้อ"
                  + (f" พบข้อขัดแย้ง {len(res.issues)} จุด" if res.issues else ""))
    return res


def combine_sheets(results):
    """รวมผลของทุกแผ่นในฉบับเดียวกัน

    เลขที่อ้างอิงต้องตรงกันทุกแผ่น ใช้เสียงข้างมากเมื่อแผ่นใดแผ่นหนึ่งอ่านเพี้ยน
    เป็นหลักการเดียวกับที่ใช้กับเลขลำดับแผ่นใน docgroup.py
    """
    refs = {}
    for r in results:
        for v in r.ref_variants:
            refs[v] = refs.get(v, 0) + 1
    out = {"reference_no": None, "sheets": len(results),
           "checks": [], "issues": [], "notes": []}
    if not refs:
        out["notes"].append("ไม่มีแผ่นไหนอ่านเลขที่อ้างอิงได้")
        return out

    good = {k: v for k, v in refs.items() if k.startswith("E")}
    pick = max(good or refs, key=lambda k: (refs[k], k.startswith("E")))
    out["reference_no"] = pick
    others = [k for k in refs if k != pick]
    if others:
        out["notes"].append(
            f"เลขที่อ้างอิงอ่านได้ไม่ตรงกันระหว่างแผ่น ใช้ {pick} "
            f"({refs[pick]} แผ่น) ส่วนที่ต่างคือ "
            + ", ".join(f"{k} ({refs[k]} แผ่น)" for k in others))
    else:
        out["checks"].append(
            f"เลขที่อ้างอิง {pick} ตรงกันทุกแผ่น {refs[pick]} แผ่น")

    seen = [(r.page, r.pages_total) for r in results if r.page]
    if seen:
        totals = {t for _, t in seen if t}
        if len(totals) == 1:
            n = totals.pop()
            got = sorted(p for p, _ in seen)
            if got == list(range(1, n + 1)):
                out["checks"].append(f"ครบทั้ง {n} แผ่น")
            else:
                out["issues"].append(
                    f"เอกสารระบุ {n} แผ่น แต่อ่านได้แผ่น {got}")
        else:
            out["notes"].append(
                f"จำนวนแผ่นที่พิมพ์ไว้ไม่ตรงกัน: {sorted(totals)}")
    return out


def _dist(a, b):
    if a == b:
        return 0
    if len(a) != len(b):
        return 99
    return sum(1 for x, y in zip(a, b) if x != y)


def group_sheets(pairs, max_diff=1):
    """จัดแผ่นเป็นฉบับ โดยถือว่าเลขที่ต่างกันไม่เกินหนึ่งตัวอักษรคือฉบับเดียวกัน

    ต้องรวมก่อนแล้วค่อยเลือกเลขที่ ไม่ใช่จัดกลุ่มด้วยเลขที่ที่ยังไม่ได้แก้
    ไม่งั้นแผ่นที่ OCR อ่านเลขที่เพี้ยนจะกลายเป็นคนละฉบับ แล้วฟ้องว่าแผ่นขาดทั้งสองฉบับ
    (IMP26002010 สามแผ่น แผ่น 2 อ่านได้ F จึงแตกเป็น [1,3] กับ [2])

    pairs = [(ชื่อหน้า, FormE)]  คืน [[(ชื่อหน้า, FormE), ...], ...]
    """
    groups = []
    for key, r in pairs:
        ref = r.reference_no
        for g in groups:
            refs = [x.reference_no for _, x in g if x.reference_no]
            if ref is None and not refs:
                g.append((key, r))
                break
            if ref and any(_dist(ref, o) <= max_diff for o in refs):
                g.append((key, r))
                break
        else:
            groups.append([(key, r)])
    return groups
