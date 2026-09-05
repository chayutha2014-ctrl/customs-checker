# -*- coding: utf-8 -*-
"""อ่านใบแจ้งหนี้ค่าระวาง (Freight Invoice)

ต่างจาก Invoice และ Packing List ตรงที่ความสัมพันธ์เชิงเลขอยู่ใน **บรรทัดเดียวกัน**
ไม่ใช่ในคอลัมน์ จึงไม่ต้องใช้พิกัด อ่านจากข้อความของแต่ละแถวได้เลย

หลักฐานสามชั้นเหมือนเดิม เรียงจากแข็งไปอ่อน
  1. อัตรา x ปริมาณ = จำนวนเงิน   ในแต่ละบรรทัดค่าใช้จ่าย
  2. ผลบวกทุกบรรทัด = ยอดรวมท้ายใบ
  3. ป้ายชื่อ                      สำหรับช่องที่ไม่มีเลขคณิตให้ยึด

รูปแบบที่พบจริงในตัวอย่าง 5 ใบ จากผู้ให้บริการ 3 ราย
  Extra    OCEANFREIGHT | 300.00 | USD | 1.00 | 20'DC | 300.00
  Bugatti  EBS&CIC | 1.000 | CBM | USD | 6.50 | 6.50
  XTRIM    SEA FREIGHT [USD 520.000 X 3.000 ] | USD | 1,560.00
ทั้งสามคือ a x b = c เหมือนกัน ต่างแค่ที่วางตัวเลข
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations

from customs_checker.numbers import parse_number

TOL = 0.02
MIN_AMOUNT = 0.009          # เล็กกว่านี้ถือว่าไม่ใช่จำนวนเงิน

_NUMTOK = re.compile(r"[\d][\d.,]*")
SECTION_WORDS = ("RATE", "UNIT", "AMOUNT", "CURRENCY", "VOLUME", "QTY",
                 "QTYS", "DESCRIPTION", "UOM")
MIN_SECTION_WORDS = 3
TOTAL_WORDS = ("TOTAL", "TOTA", "GRANDTOTAL", "AMOUNT", "ยอดรวม", "รวมทั้งสิ้น")
SKIP_WORDS = ("VAT", "ภาษีมูลค่าเพิ่ม")


def norm(s):
    return re.sub(r"[\s.:：;,\-]+", "", str(s or "")).upper()


# ตัวอักษรที่ติดกับตัวเลขได้โดยไม่ทำให้มันกลายเป็นรหัส
OK_PREFIX = ("USD", "THB", "CNY", "RMB", "EUR", "JPY", "SGD", "HKD", "$")
OK_SUFFIX = ("KGS", "KGM", "KG", "CBM", "M3", "CTNS", "CTN", "PCS", "SETS",
             "PLTS", "PLT", "MT", "M", "USD", "THB")


def _run_before(t, i):
    j = i
    while j > 0 and t[j - 1].isalpha():
        j -= 1
    return t[j:i].upper()


def _run_after(t, i):
    j = i
    while j < len(t) and t[j].isalpha():
        j += 1
    return t[i:j].upper()


def numbers_in(text, strict=True):
    """ตัวเลขทุกตัวในข้อความ เรียงซ้ายไปขวา

    strict=True ทิ้งตัวเลขที่มีตัวอักษรติดอยู่ เพราะนั่นคือรหัส ไม่ใช่จำนวน
      27AUG2026  ->  ทิ้งทั้ง 27 และ 2026   (เคยถูกอ่านเป็น 2026 x 1 = 2026)
      ODIN26082516, V.085S, SI260305, 40HC  ->  ทิ้งทั้งหมด
      1.000 X 7.500  ->  เก็บทั้งคู่ เพราะมีช่องว่างคั่น
    """
    t = str(text or "")
    out = []
    for m in _NUMTOK.finditer(t):
        if strict:
            pre = _run_before(t, m.start())
            suf = _run_after(t, m.end())
            # USD520.000 คือจำนวนเงิน ไม่ใช่รหัส   27AUG2026 คือวันที่ ไม่ใช่จำนวน
            if pre and pre not in OK_PREFIX:
                continue
            if suf and suf not in OK_SUFFIX:
                continue
        v = parse_number(m.group(0))
        if v is not None:
            out.append((m.start(), v))
    return out


@dataclass
class Charge:
    row: int
    text: str
    f1: float                # สองตัวที่คูณกันได้จำนวนเงิน
    f2: float                # การคูณสลับที่ได้ จึงไม่อ้างว่าตัวไหนคืออัตรา
    amount: float
    flat: bool = False       # ค่าใช้จ่ายคงที่ ไม่มีการคูณ เช่นค่า B/L ค่าเอกสาร
    basis: str = ""          # ฐานที่ใช้คิด ตรงกับปริมาณไหนในใบเดียวกัน
    basis_value: float | None = None


@dataclass
class FreightInvoice:
    charges: list = field(default_factory=list)
    total: float | None = None
    computed: float | None = None
    quantities: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    fields: dict = field(default_factory=dict)
    status: str = "ยังไม่ได้อ่าน"


def numbers_in_raw(text, strict=True):
    """เหมือน numbers_in แต่คืนข้อความต้นฉบับของตัวเลขมาด้วย

    ต้องใช้ข้อความต้นฉบับเพื่อรู้ว่าพิมพ์ทศนิยมไว้กี่ตำแหน่ง
    "1.00" กับ "1" เป็นค่าเดียวกันแต่บอกความละเอียดต่างกัน
    """
    t = str(text or "")
    out = []
    for m in _NUMTOK.finditer(t):
        if strict:
            pre = _run_before(t, m.start())
            suf = _run_after(t, m.end())
            if (pre and pre not in OK_PREFIX) or (suf and suf not in OK_SUFFIX):
                continue
        v = parse_number(m.group(0))
        if v is not None:
            out.append((m.start(), v, m.group(0)))
    return out


def _decimals(raw):
    t = str(raw).rstrip(".,")
    return len(t.split(".")[-1]) if "." in t else 0


MAX_REL_TOL = 0.002      # เพดาน 0.2% ของจำนวนเงิน


def rounding_tol(a, b, ra=None, rb=None, c=None, floor=TOL):
    """ค่ายอมรับที่คิดจากการปัดเศษของตัวเลขที่พิมพ์ไว้

    ใบแจ้งหนี้พิมพ์อัตราแบบปัดแล้ว เช่นอัตราจริง 7.5464 พิมพ์เป็น 7.55
    ผลคูณจึงคลาดจากจำนวนเงินที่พิมพ์ได้ตามสัดส่วน
      7.55 x 8.51 = 64.2505  แต่ใบเขียน 64.22   ต่างกัน 0.03

    อัตราแสดง 2 ตำแหน่ง คลาดได้ +-0.005 คูณด้วยปริมาณ 8.51 = +-0.043 ซึ่งครอบพอดี
    ใช้ค่าคงที่ไม่ได้ เพราะปริมาณยิ่งมาก ความคลาดยิ่งมากตามสัดส่วน
    """
    est = (0.5 * 10 ** -_decimals(ra if ra is not None else a) * abs(b)
           + 0.5 * 10 ** -_decimals(rb if rb is not None else b) * abs(a))
    if c is not None:
        est = min(est, abs(c) * MAX_REL_TOL)     # กันค่ายอมรับบานจนจับคู่ผิดได้
    return max(floor, est)


def is_section_header(text):
    """แถวหัวตารางของหมวดค่าใช้จ่าย เช่น DESCRIPTION | RATE | UNIT | AMOUNT"""
    up = re.sub(r"[^A-Z]+", " ", str(text).upper()).split()
    return sum(1 for w in SECTION_WORDS if w in up) >= MIN_SECTION_WORDS


def find_charge(text, row=0, tol=TOL):
    """หา a x b = c ในบรรทัดเดียว

    ยอมรับเมื่อจำนวนเงินเป็นตัวเลข **ตัวสุดท้าย** ของบรรทัด
    เพราะใบแจ้งหนี้ทุกแบบวางจำนวนเงินไว้ขวาสุด
    ถ้าไม่บังคับข้อนี้ ตัวเลขอย่างเลขตู้หรือเลขที่งานจะจับคู่กันเองได้โดยบังเอิญ
    """
    raw = numbers_in_raw(text)
    if len(raw) < 3:
        return None
    nums = [v for _, v, _ in raw]
    toks = [t for _, _, t in raw]
    c = nums[-1]
    if abs(c) < MIN_AMOUNT:
        return None
    best = None
    for i in range(len(nums) - 1):
        for j in range(i + 1, len(nums) - 1):
            a, b = nums[i], nums[j]
            if a == 0 or b == 0:
                continue
            lim = rounding_tol(a, b, toks[i], toks[j], c, tol)
            if abs(a * b - c) <= max(lim, abs(c) * 1e-6):
                # เลือกคู่ที่ไม่ใช่ 1 x c ก่อน เพราะให้ข้อมูลมากกว่า
                trivial = (a == 1 or b == 1)
                score = (trivial, -(i + j))
                if best is None or score < best[0]:
                    best = (score, Charge(row, str(text), a, b, c))
    return best[1] if best else None


LABELS = {
    "invoice_no": ("INVOICENO", "INVNO"),
    "invoice_date": ("INVOICEDATE",),
    "job_no": ("JOBNO",),
    "vessel": ("VESSEL",),
    "feeder": ("FEEDER",),
    "etd": ("ETD",),
    "eta": ("ETA",),
    "house_bl": ("HOUSEB/L", "B/LNO", "B/LNo"),
    "new_bl": ("NEWB/L", "NEWB/LNO"),
    "gross_weight": ("GROSSWEIGHT", "GW"),
    "cbm": ("CBM", "VOL"),
    "packages": ("Q'TY", "QTY", "NOOFPACKAGE", "QUANTITY"),
    "container": ("CONTAINERNO", "CNTRNO"),
    "origin": ("ORIGIN", "PORTOFLOADING", "PLACEOFRECEIPT", "PORT"),
    "destination": ("DESTINATION", "PORTOFDISCHARGE", "PLACEOFDILIVERY",
                    "PLACEOFDELIVERY"),
}
# ป้ายที่ยาวกว่าชนะ กัน NEWB/L ถูกจับด้วย B/LNO
_ALIASES = sorted(((k, a) for k, al in LABELS.items() for a in al),
                  key=lambda t: -len(norm(t[1])))


def cells_of(r):
    """ข้อความของแต่ละเซลล์ในแถว รองรับทั้ง Row จริงและข้อความเปล่า"""
    if hasattr(r, "cells"):
        return [c.text for c in r.cells]
    if isinstance(r, str):
        return [p.strip() for p in r.split("|")]
    if hasattr(r, "text"):
        return [p.strip() for p in r.text().split("|")]
    return [str(x) for x in r]


def _is_label(text):
    """ข้อความนี้เป็นป้ายชื่อช่อง ไม่ใช่ค่า"""
    n = norm(text)
    return bool(n) and any(n == norm(a) for _, a in _ALIASES)


def _norm_map(raw):
    """ทำข้อความให้เทียบง่าย พร้อมเก็บว่าอักขระแต่ละตัวมาจากตำแหน่งไหนในต้นฉบับ

    ต้องเก็บตำแหน่งไว้ เพราะหลังจับป้ายชื่อได้แล้วต้องตัดค่าจาก **ต้นฉบับ**
    ไม่ใช่จากข้อความที่ทำให้เทียบง่ายแล้ว
    """
    out, idx = [], []
    for i, ch in enumerate(str(raw or "")):
        if ch in " \t.:：;,-":
            continue
        out.append(ch.upper())
        idx.append(i)
    return "".join(out), idx


def read_fields(rows):
    """อ่านช่องที่มีป้ายชื่อกำกับ — หลักฐานชั้นที่ 3 อ่อนที่สุด ใช้เมื่อไม่มีเลขคณิต

    ในหนึ่งเซลล์เลือกป้ายที่อยู่ซ้ายสุด ถ้าเริ่มที่เดียวกันเลือกป้ายที่ยาวกว่า
    กัน PORT ไปชนะ PORTOFLOADING และกัน CBM ไปชนะ VOL ใน "VOL:0.220CBM."
    """
    out = {}
    for r in rows:
        cells = cells_of(r)
        if is_section_header(" ".join(cells)):
            # ORIGIN CHARGES | RATE | UNIT | AMOUNT เคยให้ origin=CHARGES
            continue
        for i, raw in enumerate(cells):
            n, idx = _norm_map(raw)
            if not n:
                continue
            hits = []
            for key, alias in _ALIASES:
                a = norm(alias)
                pos = n.find(a)
                if pos >= 0:
                    hits.append((pos, -len(a), key, len(a)))
            if not hits:
                continue
            hits.sort()
            pos, _, key, alen = hits[0]
            if key in out:
                continue
            end = idx[pos + alen - 1] + 1
            val = str(raw)[end:].strip(" :：;.-")
            if not val and i + 1 < len(cells):
                nxt = str(cells[i + 1]).strip(" :：;")
                # ช่องว่างเปล่าแล้วเซลล์ถัดไปเป็นป้ายชื่อของช่องอื่น ไม่ใช่ค่า
                # (FEEDER | DESTINATION | ：LATKRABANG  เคยได้ feeder=DESTINATION)
                val = "" if _is_label(nxt) else nxt
            if val:
                out[key] = val
    return out



_CNTR = re.compile(r"\b[A-Z0O]{4}\s?\d{7}\b")


def container_count(text):
    """นับตู้จากเลขตู้ หรือจากตัวคูณแบบ 1X20'DC,1X40HC"""
    n = len(set(_CNTR.findall(str(text).upper().replace(" ", ""))))
    if n:
        return n
    mult = re.findall(r"(\d+)\s*[Xx]\s*\d{2}", str(text))
    return sum(int(m) for m in mult) if mult else 0


def stated_quantities(fields, page_text):
    """ปริมาณที่ระบุไว้ในใบนี้ ใช้เป็นฐานเทียบว่าคิดเงินจากอะไร"""
    q = {}
    for key, name in (("cbm", "ปริมาตร CBM"), ("gross_weight", "น้ำหนักรวม"),
                      ("packages", "จำนวนหีบห่อ")):
        v = fields.get(key)
        if not v:
            continue
        # ค่าของช่องเหล่านี้มีหน่วยติดมาเสมอ เช่น 0.220CBM  2,006 CARTONS
        # parse_number ตัดหน่วยให้อยู่แล้ว จึงส่งทั้งก้อนเข้าไป ไม่ต้องแยกโทเคน
        n = parse_number(str(v).strip(" ."))
        if n is None:
            hit = numbers_in(v, strict=False)
            n = hit[0][1] if hit else None
        if n is not None:
            q[name] = n
    n = container_count(page_text)
    if n:
        q["จำนวนตู้"] = float(n)
    return q


UNIT_TO_QTY = {
    "CBM": "ปริมาตร CBM", "M3": "ปริมาตร CBM",
    "KGS": "น้ำหนักรวม", "KG": "น้ำหนักรวม", "W/M": "ปริมาตร CBM",
    "CTNS": "จำนวนหีบห่อ", "CTN": "จำนวนหีบห่อ", "CARTON": "จำนวนหีบห่อ",
    "CARTONS": "จำนวนหีบห่อ", "PALLET": "จำนวนหีบห่อ", "PALLETS": "จำนวนหีบห่อ",
}


def unit_in_line(text):
    """หน่วยที่เขียนอยู่ในบรรทัดค่าใช้จ่าย บอกว่าผู้ให้บริการคิดจากฐานอะไร"""
    up = re.sub(r"[^A-Z0-9/]+", " ", str(text).upper())
    for u in sorted(UNIT_TO_QTY, key=len, reverse=True):
        if re.search(rf"(?<![A-Z0-9]){re.escape(u)}(?![A-Z0-9])", up):
            return u
    return ""


def basis_of(qty, quantities, tol=TOL):
    for name, v in quantities.items():
        if abs(v - qty) <= max(tol, abs(v) * 1e-6):
            return name
    if abs(qty - 1.0) <= tol:
        return "หน่วยเดียว"
    return ""


def row_texts(rows):
    out = []
    for r in rows:
        if isinstance(r, str):
            out.append(r)
        elif hasattr(r, "text"):
            out.append(r.text())
        elif hasattr(r, "cells"):
            out.append(" ".join(c.text for c in r.cells))
        else:
            out.append(" ".join(str(x) for x in r))
    return out


def _total_candidates(texts, used, computed):
    out = []
    for i, t in enumerate(texts):
        if i in used:
            continue
        nums = [v for _, v in numbers_in(t)]
        if nums and abs(max(nums) - computed) <= TOL:
            out.append((i, max(nums), t))
    return out


def _add_flat_charges(res, texts, used, computed, max_extra=4, max_pool=10):
    """เติมบรรทัดค่าใช้จ่ายคงที่ที่ไม่มีการคูณ

    ใบแจ้งหนี้ค่าระวางมีค่าใช้จ่ายคงที่เสมอ เช่นค่า B/L ค่า THC ค่าเอกสาร
    เขียนเป็นจำนวนเงินเดี่ยว ๆ ไม่มี อัตรา x ปริมาณ ให้จับ

    วิธียืนยัน: ต้องหาชุดบรรทัดที่เติมเข้าไปแล้ว **ลงตัวพอดี** กับยอดรวมท้ายใบ
    ไม่ใช่เดาว่าบรรทัดไหนน่าจะเป็นค่าใช้จ่าย
    ถ้าหาชุดที่ลงตัวไม่ได้ จะไม่เติมอะไรเลย แล้วรายงานว่ายอดไม่ตรงตามเดิม

    คืน (ยอดรวมใหม่, [บรรทัดที่เติม]) หรือ (ยอดเดิม, [])
    """
    if not res.charges:
        return computed, []
    lo = min(c.row for c in res.charges)

    # ยอดรวมท้ายใบที่เป็นไปได้ = ตัวเลขที่มากกว่าผลบวกปัจจุบัน
    targets = []
    for i, t in enumerate(texts):
        if i in used:
            continue
        for _, v in numbers_in(t):
            if v > computed + TOL:
                targets.append((i, v))
    if not targets:
        return computed, []

    pool = []
    for i, t in enumerate(texts):
        if i in used or i < lo:
            continue
        nums = [v for _, v in numbers_in(t)]
        if not nums or not re.search(r"[A-Za-zก-๙]", t):
            continue
        v = max(nums)
        if v <= 0 or v > computed * 50 + 1e6:
            continue
        pool.append((i, v, t))
    pool = pool[:max_pool]

    for _, target in sorted(targets, key=lambda t: t[1]):
        gap = round(target - computed, 2)
        for k in range(1, max_extra + 1):
            for combo in combinations(pool, k):
                if abs(sum(v for _, v, _ in combo) - gap) <= TOL:
                    return round(computed + gap, 2), list(combo)
    return computed, []


def analyze_freight_invoice(rows):
    res = FreightInvoice()
    texts = row_texts(rows)
    res.fields = read_fields(rows)
    res.quantities = stated_quantities(res.fields, "\n".join(texts))

    sections = [i for i, t in enumerate(texts) if is_section_header(t)]
    for i, t in enumerate(texts):
        if i in sections or any(w in norm(t) for w in SKIP_WORDS):
            continue
        ch = find_charge(t, row=i)
        if ch:
            res.charges.append(ch)

    if not res.charges:
        res.status = "ไม่พบบรรทัดค่าใช้จ่ายที่ อัตรา x ปริมาณ = จำนวนเงิน"
        return res

    computed = round(sum(c.amount for c in res.charges), 2)
    res.computed = computed

    # หายอดรวม — ยึดเลขคณิตก่อน ไม่ยึดคำ
    # เพราะ OCR ทำคำว่า TOTAL หายตัวอักษรได้ (พบจริง "TOTAAMOUNT USD | 1,560.00")
    # หลักฐานที่แท้จริงคือ "มีตัวเลขที่เท่ากับผลบวกพอดี" ไม่ใช่ "มีคำว่ารวม"
    used = {c.row for c in res.charges}
    last = max(used)
    exact = []
    for i, t in enumerate(texts):
        if i in used:
            continue
        nums = [v for _, v in numbers_in(t)]
        if nums and abs(max(nums) - computed) <= TOL:
            exact.append((i, max(nums), t))
    if not exact:
        computed, added = _add_flat_charges(res, texts, used, computed)
        if added:
            for i, v, t in added:
                res.charges.append(Charge(i, t, v, 1.0, v, flat=True))
            res.charges.sort(key=lambda c: c.row)
            res.computed = computed
            exact = [e for e in _total_candidates(texts, used, computed)]
    if exact:
        after = [e for e in exact if e[0] > last]
        i, v, t = (after or exact)[0]
        res.total = v
        res.notes.append(f"ยอดรวมท้ายใบอ่านจากบรรทัด '{t[:46]}'")
        n_flat = sum(1 for c in res.charges if c.flat)
        res.status = (f"ผลบวก {len(res.charges)} บรรทัด ตรงกับยอดรวมท้ายใบ"
                      + (f" (รวมค่าใช้จ่ายคงที่ {n_flat} บรรทัด)" if n_flat else ""))
    else:
        cands = []
        for i, t in enumerate(texts):
            if i in used or not any(w in norm(t) for w in TOTAL_WORDS):
                continue
            for _, v in numbers_in(t):
                cands.append((i, v))
        if cands:
            best = max(cands, key=lambda t: t[1])
            res.total = best[1]
            res.issues.append(
                f"ยอดรวมท้ายใบ {best[1]:,.2f} ไม่ตรงกับผลบวกของบรรทัดค่าใช้จ่าย "
                f"{computed:,.2f} ต่างกัน {best[1] - computed:,.2f}")
            res.status = "ยอดรวมท้ายใบไม่ตรงกับผลบวก"
        else:
            res.status = (f"อ่านบรรทัดค่าใช้จ่ายได้ {len(res.charges)} บรรทัด "
                          f"รวม {computed:,.2f} แต่ไม่พบยอดรวมท้ายใบให้เทียบ")

    # ใบที่แบ่งค่าใช้จ่ายเป็นหลายหมวด ต้องบอกว่าหมวดไหนไม่มีรายการ
    # ถ้าไม่บอก แล้วยอดที่จับได้เป็นยอดของหมวดเดียว จะกลายเป็นข้อผิดเงียบ
    if len(sections) > 1:
        empty = []
        for n, start in enumerate(sections):
            end = sections[n + 1] if n + 1 < len(sections) else len(texts)
            if not any(start < c.row < end for c in res.charges):
                empty.append(texts[start][:40])
        res.notes.append(
            f"ใบนี้แบ่งค่าใช้จ่ายเป็น {len(sections)} หมวด")
        for e in empty:
            res.notes.append(
                f"หมวด '{e}' ไม่มีรายการที่อ่านได้ "
                f"ต้องยืนยันว่าไม่มีค่าใช้จ่ายในหมวดนี้จริง")

    for c in res.charges:
        # ถ้าบรรทัดเขียนหน่วยไว้ ให้เชื่อหน่วยนั้นก่อน แล้วเทียบกับปริมาณจริงในใบ
        # นี่คือจุดที่จับการคิดเงินเกินได้ เช่นคิด 1.000 CBM ทั้งที่ใบระบุ 0.220 CBM
        u = unit_in_line(c.text)
        want = UNIT_TO_QTY.get(u)
        if want and want in res.quantities:
            real = res.quantities[want]
            near = min((c.f1, c.f2), key=lambda v: abs(v - real))
            c.basis, c.basis_value = want, near
            if abs(near - real) > max(TOL, abs(real) * 1e-6):
                # สูงกว่าปริมาณจริง = คิดขั้นต่ำ เป็นเรื่องปกติของธุรกิจ
                # ต่ำกว่าปริมาณจริง = น่าสงสัยว่าเป็นใบของงานอื่น
                why = ("อาจเป็นการคิดขั้นต่ำ" if near > real
                       else "ต่ำกว่าปริมาณจริง ควรตรวจว่าเป็นใบของงานนี้หรือไม่")
                res.notes.append(
                    f"บรรทัด '{c.text[:40]}' คิดจาก {near:,g} {u} "
                    f"แต่ใบนี้ระบุ{want} {real:,g} — {why}")
            continue
        for v in (c.f2, c.f1):          # ไม่มีหน่วยเขียนไว้ เทียบด้วยค่าอย่างเดียว
            b = basis_of(v, res.quantities)
            if b and b != "หน่วยเดียว":
                c.basis, c.basis_value = b, v
                break
        else:
            for v in (c.f2, c.f1):
                if basis_of(v, res.quantities) == "หน่วยเดียว":
                    c.basis, c.basis_value = "หน่วยเดียว", v
                    break
        if not c.basis:
            res.notes.append(
                f"บรรทัด '{c.text[:44]}' คิดจาก {c.f1:,g} x {c.f2:,g} "
                f"ซึ่งไม่มีตัวไหนตรงกับปริมาณที่ระบุในใบนี้ ต้องให้คนดู")
    return res
