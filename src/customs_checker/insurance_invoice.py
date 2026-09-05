# -*- coding: utf-8 -*-
"""อ่านใบแจ้งหนี้เบี้ยประกันภัย

ป้ายชื่อในเอกสารชนิดนี้เป็นภาษาไทยและ OCR อ่านไม่ออกเลย
  "Bynyasnn"  "lng/aynuaspan"  "nmi56aufas"
การยึดป้ายชื่อจึงพึ่งไม่ได้ ต้องใช้เลขคณิตล้วน

โชคดีที่มีความสัมพันธ์สองข้อที่ยืนยันกันเอง และจริงทุกใบ
  เบี้ย + อากรแสตมป์ + VAT = ยอดรวม
  VAT = 7% x (เบี้ย + อากรแสตมป์)

สองสมการพร้อมกันทำให้มีคำตอบชุดเดียวในหน้า จึงระบุได้ว่าตัวเลขไหนคืออะไร
โดยไม่ต้องอ่านป้ายชื่อ และไม่ขึ้นกับว่า OCR ทำภาษาไทยพังแค่ไหน
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from customs_checker.numbers import parse_number

TOL = 0.02
VAT_RATES = (0.07, 0.0)
WHT_RATES = (0.01, 0.03)
_NUMTOK = re.compile(r"[\d][\d.,]*")


def numbers_on_page(rows):
    """ตัวเลขทุกตัวในหน้า พร้อมแถวที่พบ

    ทิ้งตัวเลขที่มีตัวอักษรติดอยู่ เพราะเป็นรหัส เช่น 00/2026-00773459-CMI
    และทิ้งวันที่ เพราะรูปแบบ dd/mm/yyyy จะถูกแยกเป็นเลขสามตัว
    """
    out = []
    for ri, r in enumerate(rows):
        t = r.text() if hasattr(r, "text") else str(r)
        t = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}", " ", t)        # ตัดวันที่ทิ้ง
        for m in _NUMTOK.finditer(t):
            before = t[m.start() - 1] if m.start() > 0 else " "
            after = t[m.end()] if m.end() < len(t) else " "
            if before.isalpha() or after.isalpha():
                continue
            v = parse_number(m.group(0))
            if v is not None and v > 0:
                out.append((ri, v, m.group(0)))
    return out


# เลขที่กรมธรรม์ของผู้รับประกันรายนี้มีรูปแบบเฉพาะ  00/2026-00773459-CMI
# OCR สลับ 0 กับ O ได้ จึงยอมรับทั้งสองตัว
_POLICY = re.compile(r"\b(\d{2}/\d{4}\s*-\s*[0-9O]{6,10}\s*-\s*[A-Z]{2,4})\b")
_DATE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")


def find_policy_no(rows):
    r"""ห้ามลบช่องว่างก่อนค้นหา

    การลบช่องว่างทำให้ "00/2026-00773459-CMI 44.38" กลายเป็น
    "00/2026-00773459-CMI44.38" แล้วขอบคำหลัง CMI หายไปเพราะติดเลข 44 ทันที
    รูปแบบมี \s* รองรับช่องว่างอยู่แล้ว ไม่ต้องลบ
    """
    for r in rows:
        t = r.text() if hasattr(r, "text") else str(r)
        m = _POLICY.search(t.upper())
        if m:
            return re.sub(r"\s+", "", m.group(1))
    return None


def find_dates(rows):
    out = []
    for r in rows:
        t = r.text() if hasattr(r, "text") else str(r)
        for m in _DATE.finditer(t):
            if m.group(1) not in out:
                out.append(m.group(1))
    return out


@dataclass
class InsuranceInvoice:
    premium: float | None = None
    stamp: float | None = None
    vat: float | None = None
    total: float | None = None
    vat_rate: float | None = None
    sum_insured: float | None = None
    wht: float | None = None
    net_payable: float | None = None
    policy_no: str | None = None
    dates: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    status: str = "ยังไม่ได้อ่าน"


def find_premium_set(values, tol=TOL):
    """หา (เบี้ย, อากรแสตมป์, VAT, ยอดรวม) ที่สอดคล้องกับสองสมการพร้อมกัน

    คืนชุดที่พบทั้งหมด ถ้าได้มากกว่าหนึ่งชุดต้องให้คนดู ไม่ใช่เลือกเอง
    """
    vals = sorted(set(values))
    found = []
    for total in vals:
        for premium in vals:
            if premium >= total:
                continue
            for stamp in vals:
                if stamp > premium:
                    continue
                vat = round(total - premium - stamp, 2)
                if vat <= 0 or vat not in {round(v, 2) for v in vals}:
                    continue
                base = premium + stamp
                for rate in VAT_RATES:
                    if rate and abs(vat - base * rate) <= tol:
                        found.append((premium, stamp, vat, total, rate))
                        break
    return found


def find_wht(values, base, total, tol=TOL):
    """ภาษีหัก ณ ที่จ่าย — ยอดรวม ลบ ภาษีหัก = ยอดที่ต้องจ่ายจริง"""
    vals = {round(v, 2) for v in values}
    for rate in WHT_RATES:
        w = round(base * rate, 2)
        if w in vals and round(total - w, 2) in vals:
            return w, round(total - w, 2), rate
    return None, None, None


def find_sum_insured(triples, total, tol=TOL):
    """ทุนประกัน — ตัวเลขที่ใหญ่กว่ายอดรวมมาก และมีทศนิยม

    ต้องมีทศนิยมเพื่อกันเลขประจำตัวผู้เสียภาษีและเลขที่เอกสาร
    ซึ่งเป็นเลขยาวแต่ไม่มีจุด
    """
    cands = [v for _, v, raw in triples if "." in raw and v > total * 2]
    return max(cands) if cands else None


def analyze_insurance_invoice(rows):
    res = InsuranceInvoice()
    res.policy_no = find_policy_no(rows)
    res.dates = find_dates(rows)
    triples = numbers_on_page(rows)
    values = [v for _, v, _ in triples]
    if not values:
        res.status = "ไม่พบตัวเลขในหน้านี้"
        return res

    sets = find_premium_set(values)
    if not sets:
        res.status = ("ไม่พบชุดตัวเลขที่ เบี้ย + อากร + VAT = ยอดรวม "
                      "และ VAT ตรงกับอัตราภาษี — อ่านไม่ได้ ต้องให้คนตรวจ")
        return res

    uniq = {(p, s, v, t) for p, s, v, t, _ in sets}
    if len(uniq) > 1:
        res.issues.append(
            f"พบชุดตัวเลขที่เข้าเงื่อนไข {len(uniq)} ชุด แยกไม่ออกว่าชุดไหนถูก: "
            + " | ".join(f"{p:,.2f}+{s:,.2f}+{v:,.2f}={t:,.2f}"
                         for p, s, v, t in sorted(uniq)))
        res.status = "มีชุดตัวเลขที่เข้าเงื่อนไขมากกว่าหนึ่งชุด ต้องให้คนดู"
        return res

    p, s, v, t, rate = sets[0]
    res.premium, res.stamp, res.vat, res.total, res.vat_rate = p, s, v, t, rate
    res.status = (f"เบี้ย {p:,.2f} + อากร {s:,.2f} + VAT {v:,.2f} = {t:,.2f} "
                  f"และ VAT ตรงกับ {rate:.0%} ของฐาน {p + s:,.2f}")

    w, net, wrate = find_wht(values, p + s, t)
    if w is not None:
        res.wht, res.net_payable = w, net
        res.notes.append(
            f"หักภาษี ณ ที่จ่าย {wrate:.0%} ของฐานก่อน VAT = {w:,.2f} "
            f"เหลือจ่ายจริง {net:,.2f}")

    res.sum_insured = find_sum_insured(triples, t)
    if res.sum_insured is None:
        res.notes.append("อ่านทุนประกันไม่ได้ ต้องให้คนกรอก")
    return res
