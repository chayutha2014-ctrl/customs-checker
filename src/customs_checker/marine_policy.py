# -*- coding: utf-8 -*-
"""อ่านกรมธรรม์ประกันภัยขนส่งสินค้าทางทะเล (Marine Cargo Policy)

เอกสารชนิดนี้มีหลักฐานยืนยันตัวเองครบที่สุดในบรรดาเอกสารทั้งหมด
บรรทัดเดียวให้การตรวจสามชั้น

  Amount Insured hereunder: Equal to (432,705.00 + 10.00%) CNY 475,975.50 @ 4.9435
  (CNY (CHINA) : Four Hundred and Seventy-Five Thousand Nine Hundred and Seventy-Five And 50/100)

  1. 432,705.00 x 1.10 = 475,975.50        ราคาสินค้าบวกกำไรสมมติ
  2. ตัวหนังสือกำกับตรงกับตัวเลข            หลักฐานอิสระที่อยู่ในเอกสารเอง
  3. 475,975.50 x 4.9435 = 2,352,984.88    ตรงกับทุนประกันในใบแจ้งหนี้

ชั้นที่ 2 สำคัญที่สุด เพราะถ้า OCR อ่านตัวเลขผิด ตัวหนังสือจะไม่ตรง
เป็นวิธียืนยันว่าอ่านถูกโดยไม่ต้องมีคนมาตรวจ
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from customs_checker.numbers import parse_number
from customs_checker.amount_words import (words_to_number,
                                          unknown_words,
                                          looks_like_amount_words)

TOL = 0.02

# เลขที่กรมธรรม์มีหลายรูปแบบตามผู้รับประกัน
#   Deves         00/2026-00773459-CMI
#   Tokio Marine  DR-90-69/000258
_POLICIES = (
    re.compile(r"\b(\d{2}/\d{4}\s*-\s*[0-9O]{6,10}\s*-\s*[A-Z]{2,4})\b"),
    re.compile(r"\b([A-Z]{2}\s*-\s*\d{2}\s*-\s*\d{2}\s*/\s*\d{4,8})\b"),
)

# ผู้รับประกันบางรายเขียนอัตราแลกเปลี่ยนกับยอดบาทไว้บรรทัดเดียว
#   (EX.@ 33.3000=Bht129,934.94)
_EX_THB = re.compile(r"EX\.?@?([\d,.]+)=BHT([\d,.]+)")
_AMOUNT = re.compile(
    r"EQUALTO\(?([\d,.]+)\+([\d,.]+)%\)?([A-Z]{2,4})([\d,.]+)@([\d,.]+)")
_PACKAGES = re.compile(
    r"([\d,.]+)\s*(CARTONS?|PALLETS?|PKGS?|CTNS?|PCS|BAGS?|ROLLS?|SETS?|CASES?)"
    r"(?:\s*\(\s*([\d,.]+)\s*(KGS?|KGM))?")
_LABEL = {
    "assured": ("NAMEOFASSURED",),
    "vessel": ("VESSEL",),
    "sailing": ("SAILINGONORABOUT",),
    "job_no": ("JOBNO",),
}


def flat(text):
    """ทำให้เทียบง่าย — ตัวพิมพ์ใหญ่ ไม่มีช่องว่าง วงเล็บเป็นแบบครึ่งความกว้าง"""
    return (str(text or "").upper()
            .replace("（", "(").replace("）", ")")
            .replace("：", ":")
            .replace(" ", ""))


@dataclass
class MarinePolicy:
    policy_no: str | None = None
    assured: str | None = None
    vessel: str | None = None
    sailing: str | None = None
    voyage_from: str | None = None
    voyage_to: str | None = None
    goods_value: float | None = None      # ราคาสินค้าก่อนบวกกำไรสมมติ
    uplift_pct: float | None = None
    currency: str | None = None
    amount_insured: float | None = None
    exchange_rate: float | None = None
    amount_in_words: float | None = None
    thb_value: float | None = None        # ทุนประกันคิดเป็นบาท
    packages: float | None = None
    package_unit: str | None = None
    gross_weight: float | None = None
    invoice_no: str | None = None
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


def find_amount_line(texts):
    """บรรทัด Amount Insured hereunder — หัวใจของเอกสาร"""
    for i, t in enumerate(texts):
        m = _AMOUNT.search(flat(t))
        if m:
            return i, m
    return None, None


def find_voyage(texts):
    for t in texts:
        f = flat(t)
        m = re.search(r"ATANDFROM(.+?)TO(.+?)(THENCE|$)", f)
        if m:
            return m.group(1), m.group(2)
    return None, None


def find_packages(texts):
    for t in texts:
        m = _PACKAGES.search(flat(t))
        if m:
            kg = parse_number(m.group(3)) if m.group(3) else None
            return parse_number(m.group(1)), m.group(2), kg
    return None, None, None


def find_invoice_no(texts):
    """เลขที่ใบกำกับอยู่บรรทัดถัดจากคำว่า INVOICE NO. เสมอ

    บรรทัดที่มีคำว่า INVOICE NO. เก็บชื่อผู้ขายไว้ ไม่ใช่เลขที่
      INVOICE NO.SCG INTERNATIONAL CHINA (GUANGZHOU) CO.,LTD
      5230000677
    """
    for i, t in enumerate(texts):
        if "INVOICENO" in flat(t) and i + 1 < len(texts):
            nxt = texts[i + 1].strip()
            if nxt and len(nxt.split()) <= 3:
                return nxt
    return None


# OCR สลับตัวอักษรที่หน้าตาเหมือนกันเป็นประจำ  VeSSeI แทน Vessel
# จับคู่ป้ายชื่อโดยยุบตัวที่สับสนกันให้เป็นตัวเดียว ใช้กับทั้งสองฝั่ง
_CONFUSE = str.maketrans({"I": "1", "L": "1", "O": "0", "S": "5"})


def loose(s):
    return str(s).translate(_CONFUSE)


def read_labels(texts):
    out = {}
    for t in texts:
        f = loose(flat(t))
        for key, aliases in _LABEL.items():
            if key in out:
                continue
            for a in aliases:
                a = loose(a)
                pos = f.find(a)
                if pos < 0:
                    continue
                # หาตำแหน่งเดียวกันในข้อความต้นฉบับ โดยนับอักขระที่ไม่ใช่ช่องว่าง
                raw = str(t)
                seen = 0
                cut = None
                for j, ch in enumerate(raw):
                    if ch == " ":
                        continue
                    seen += 1
                    if seen == pos + len(a):
                        cut = j + 1
                        break
                if cut is None:
                    continue
                val = raw[cut:].split("|")[0]
                # ตัดเมื่อเจอป้ายชื่อถัดไป ไม่งั้นชื่อเรือจะลากเอา
                # "Sailing on or about : 15/08/2026" มาด้วย
                lv = loose(flat(val))
                stop = len(val)
                for other in (a2 for k2, al in _LABEL.items()
                              for a2 in al if k2 != key):
                    q = lv.find(loose(other))
                    if q < 0:
                        continue
                    seen2, at = 0, None
                    for j2, ch2 in enumerate(val):
                        if ch2 == " ":
                            continue
                        if seen2 == q:
                            at = j2
                            break
                        seen2 += 1
                    if at is not None:
                        stop = min(stop, at)
                val = val[:stop].strip(" :：.-")
                if val:
                    out[key] = val.strip()
                break
    return out


_NUM = re.compile(r"[\d][\d,.]*")


def find_amount_by_words(texts, window=3):
    """หาทุนประกันโดยใช้ตัวหนังสือเป็นตัวนำทาง

    ใช้เมื่อรูปแบบบรรทัดไม่ตรงกับที่รู้จัก ซึ่งเกิดได้เพราะผู้รับประกันแต่ละราย
    และแต่ละงานเขียนไม่เหมือนกัน

    ตัวหนังสือระบุจำนวนไว้ชัดเจนอยู่แล้ว จึงใช้มันหาตัวเลขที่ตรงกันในบรรทัดใกล้ ๆ
    วิธีนี้ไม่ขึ้นกับรูปแบบการเขียนเลย และยังได้การยืนยันสองทางเหมือนเดิม

    คืน (เลขแถวของตัวเลข, จำนวน, อัตราแลกเปลี่ยนถ้ามี, จำนวนจากตัวหนังสือ)
    """
    for wi, t in enumerate(texts):
        want = words_to_number(t)
        if want is None:
            continue
        lo = max(0, wi - window)
        for i in range(wi - 1, lo - 1, -1):
            f = flat(texts[i])
            for m in _NUM.finditer(f):
                v = parse_number(m.group(0))
                if v is None or abs(v - want) > TOL:
                    continue
                rate = None
                rm = re.search(r"@([\d,.]+)", f[m.end():])
                if rm:
                    rate = parse_number(rm.group(1))
                return i, v, rate, want
    return None, None, None, None


def analyze_marine_policy(rows):
    res = MarinePolicy()
    texts = texts_of(rows)

    for t in texts:
        for pat in _POLICIES:
            m = pat.search(str(t).upper())
            if m:
                res.policy_no = re.sub(r"\s+", "", m.group(1))
                break
        if res.policy_no:
            break

    lbl = read_labels(texts)
    res.assured = lbl.get("assured")
    res.vessel = lbl.get("vessel")
    res.sailing = lbl.get("sailing")
    res.voyage_from, res.voyage_to = find_voyage(texts)
    res.packages, res.package_unit, res.gross_weight = find_packages(texts)
    res.invoice_no = find_invoice_no(texts)

    i, m = find_amount_line(texts)
    if m is None:
        # รูปแบบบรรทัดไม่ตรง ลองให้ตัวหนังสือนำทางแทน
        i, v, rate, want = find_amount_by_words(texts)

        if v is None:
            # ทางที่ 3 บางรายเขียนอัตราแลกเปลี่ยนกับยอดบาทไว้บรรทัดเดียว
            for t2 in texts:
                em = _EX_THB.search(flat(t2))
                if not em:
                    continue
                rate2 = parse_number(em.group(1))
                thb = parse_number(em.group(2))
                if not rate2 or not thb:
                    continue
                res.exchange_rate, res.thb_value = rate2, thb
                res.amount_insured = round(thb / rate2, 2)
                res.checks.append(
                    f"ยอดบาท {thb:,.2f} หารด้วยอัตรา {rate2:g} "
                    f"= ทุนประกัน {res.amount_insured:,.2f}")
                res.notes.append(
                    "เอกสารเขียนยอดบาทกับอัตราแลกเปลี่ยนไว้ ไม่ได้เขียนทุนประกัน"
                    "สกุลต่างประเทศ ตัวเลขนี้จึงมาจากการคำนวณ ไม่ใช่จากเอกสารโดยตรง")
                res.status = f"ผ่านการตรวจ {len(res.checks)} ข้อ"
                return res

        if v is None:
            # ทางที่ 4 มีแต่ตัวหนังสือ ไม่มีบรรทัดตัวเลขให้เทียบ
            #
            # ใช้ได้เฉพาะเมื่อ **ไม่มีตัวเลขให้เทียบจริง ๆ** เท่านั้น
            # ถ้ามีตัวเลขอยู่เหนือบรรทัดตัวหนังสือแต่ไม่ตรงกัน นั่นคือความขัดแย้ง
            # ต้องฟ้อง ไม่ใช่เหตุให้เชื่อตัวหนังสือ
            for wi, t2 in enumerate(texts):
                w = words_to_number(t2)
                if w is None or not looks_like_amount_words(t2):
                    continue
                near = []
                for j in range(max(0, wi - 2), wi):
                    for mm in _NUM.finditer(flat(texts[j])):
                        raw = mm.group(0)
                        if "." not in raw or len(raw.split(".")[-1]) != 2:
                            continue
                        n2 = parse_number(raw)
                        if n2 is not None and n2 >= 100:
                            near.append(n2)
                if near:
                    res.amount_in_words = w
                    res.issues.append(
                        f"ตัวหนังสือระบุ {w:,.2f} แต่ตัวเลขเหนือบรรทัดนั้นคือ "
                        + ", ".join(f"{x:,.2f}" for x in near[:3])
                        + " ไม่ตรงกัน")
                    res.status = "ตัวหนังสือกับตัวเลขไม่ตรงกัน ต้องให้คนตรวจ"
                    return res
                res.amount_insured = w
                res.amount_in_words = w
                res.notes.append(
                    f"อ่านทุนประกัน {w:,.2f} จากตัวหนังสือเพียงทางเดียว "
                    "ไม่พบบรรทัดตัวเลขมายืนยัน ต้องให้คนตรวจซ้ำ")
                res.status = "อ่านได้จากตัวหนังสือทางเดียว ไม่มีหลักฐานยืนยัน"
                return res

        if v is None:
            # บอกให้ชัดว่าติดตรงไหน ผู้ตรวจจะได้รู้ว่าต้องดูอะไร
            for t2 in texts:
                if words_to_number(t2) is not None:
                    continue
                if not looks_like_amount_words(t2):
                    continue
                bad = unknown_words(t2)
                if bad:
                    res.notes.append(
                        "บรรทัดที่น่าจะเป็นจำนวนเงินตัวหนังสือแปลงไม่ได้ "
                        f"ติดที่คำว่า {', '.join(repr(b) for b in bad[:4])}")
                    break
            res.status = "ไม่พบบรรทัดทุนประกัน อ่านไม่ได้ ต้องให้คนตรวจ"
            return res
        res.amount_insured, res.exchange_rate = v, rate
        res.amount_in_words = want
        res.checks.append(
            f"ตัวหนังสือกำกับตรงกับตัวเลข {v:,.2f} "
            f"(หาด้วยตัวหนังสือ เพราะรูปแบบบรรทัดไม่ตรงกับที่รู้จัก)")
        # ลองหาราคาสินค้าก่อนบวกกำไรสมมติจากตัวเลขในบรรทัดเดียวกัน
        for mm in _NUM.finditer(flat(texts[i])):
            b = parse_number(mm.group(0))
            if b and abs(round(b * 1.1, 2) - v) <= TOL:
                res.goods_value, res.uplift_pct = b, 10.0
                res.checks.append(
                    f"ราคาสินค้า {b:,.2f} + 10% = {v:,.2f} ลงตัว")
                break
        else:
            res.notes.append("ไม่พบราคาสินค้าก่อนบวกกำไรสมมติในบรรทัดเดียวกัน")
        if res.exchange_rate:
            res.thb_value = round(v * res.exchange_rate, 2)
            res.notes.append(
                f"ทุนประกันคิดเป็นบาท {v:,.2f} x {res.exchange_rate:g} "
                f"= {res.thb_value:,.2f} (ต้องตรงกับทุนประกันในใบแจ้งหนี้)")
        else:
            res.notes.append("ไม่พบอัตราแลกเปลี่ยน เทียบกับใบแจ้งหนี้ไม่ได้")
        res.status = f"ผ่านการตรวจ {len(res.checks)} ข้อ"
        return res

    res.goods_value = parse_number(m.group(1))
    res.uplift_pct = parse_number(m.group(2))
    res.currency = m.group(3)
    res.amount_insured = parse_number(m.group(4))
    res.exchange_rate = parse_number(m.group(5))

    if None in (res.goods_value, res.uplift_pct, res.amount_insured):
        res.status = "อ่านตัวเลขในบรรทัดทุนประกันไม่ครบ"
        return res

    want = round(res.goods_value * (1 + res.uplift_pct / 100.0), 2)
    if abs(want - res.amount_insured) <= max(TOL, abs(want) * 1e-6):
        res.checks.append(
            f"ราคาสินค้า {res.goods_value:,.2f} + {res.uplift_pct:g}% "
            f"= {res.amount_insured:,.2f} ลงตัว")
    else:
        res.issues.append(
            f"ราคาสินค้า {res.goods_value:,.2f} + {res.uplift_pct:g}% "
            f"ควรได้ {want:,.2f} แต่เอกสารเขียน {res.amount_insured:,.2f}")

    # ตัวหนังสือกำกับจำนวนเงิน — หลักฐานอิสระจากตัวเลข
    for t in texts[i:i + 3]:
        v = words_to_number(t)
        if v is not None:
            res.amount_in_words = v
            break
    if res.amount_in_words is None:
        res.notes.append("อ่านจำนวนเงินที่เขียนเป็นตัวหนังสือไม่ได้ "
                         "จึงไม่มีหลักฐานอิสระยืนยันตัวเลข")
    elif abs(res.amount_in_words - res.amount_insured) <= TOL:
        res.checks.append(
            f"ตัวหนังสือกำกับตรงกับตัวเลข {res.amount_insured:,.2f}")
    else:
        res.issues.append(
            f"ตัวหนังสือระบุ {res.amount_in_words:,.2f} "
            f"แต่ตัวเลขเขียน {res.amount_insured:,.2f} ไม่ตรงกัน")

    if res.exchange_rate:
        res.thb_value = round(res.amount_insured * res.exchange_rate, 2)
        res.notes.append(
            f"ทุนประกันคิดเป็นบาท {res.amount_insured:,.2f} x "
            f"{res.exchange_rate:g} = {res.thb_value:,.2f} "
            f"(ต้องตรงกับทุนประกันในใบแจ้งหนี้)")

    res.status = (f"ผ่านการตรวจ {len(res.checks)} ข้อ"
                  + (f" พบข้อขัดแย้ง {len(res.issues)} จุด" if res.issues else ""))
    return res
