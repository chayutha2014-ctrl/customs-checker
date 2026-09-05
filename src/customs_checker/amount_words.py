# -*- coding: utf-8 -*-
"""แปลงจำนวนเงินที่เขียนเป็นตัวหนังสือภาษาอังกฤษ กลับเป็นตัวเลข

ใช้ยืนยันตัวเลขที่ OCR อ่านมา — ถ้าอ่านตัวเลขผิด ตัวหนังสือจะไม่ตรง
เป็นหลักฐานอิสระที่อยู่ในเอกสารเอง ไม่ต้องมีคนมาบอก

รูปแบบที่พบจริงในกรมธรรม์
  Four Hundred and Seventy-Five Thousand Nine Hundred and Seventy-Five And 50/100
  Fifty-One Thousand Five Hundred and Thirteen Only
  Two Thousand One Hundred and Ninety-Seven And 80/100
"""
from __future__ import annotations

import re

UNITS = {
    "ZERO": 0, "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5,
    "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9, "TEN": 10,
    "ELEVEN": 11, "TWELVE": 12, "THIRTEEN": 13, "FOURTEEN": 14,
    "FIFTEEN": 15, "SIXTEEN": 16, "SEVENTEEN": 17, "EIGHTEEN": 18,
    "NINETEEN": 19,
}
TENS = {"TWENTY": 20, "THIRTY": 30, "FORTY": 40, "FOURTY": 40, "FIFTY": 50,
        "SIXTY": 60, "SEVENTY": 70, "EIGHTY": 80, "NINETY": 90}
SCALES = {"HUNDRED": 100, "THOUSAND": 1_000, "MILLION": 1_000_000,
          "BILLION": 1_000_000_000}
SKIP = {"AND", "ONLY", "OF", "BAHT", "SATANG", "DOLLARS", "DOLLAR",
        "CENTS", "CENT", "USD", "CNY", "THB", "RMB", "EUR", "YEN"}

_FRACTION = re.compile(r"(\d{1,2})\s*/\s*100")

# คำทั้งหมดที่รู้จัก ใช้ตอนแยกคำที่ OCR เชื่อมติดกัน
_VOCAB = tuple(sorted(set(UNITS) | set(TENS) | set(SCALES) | {"AND", "ONLY"},
                      key=len, reverse=True))


def _segment(word):
    """แยกคำที่เชื่อมติดกันเป็นคำที่รู้จัก

    OCR ในกรมธรรม์เชื่อมคำติดกันหมดในบางใบ
      FourHundredandSeventy-FiveThousandNineHundredandSeventy-Five
    คืน None ถ้าแยกไม่ลงตัวทั้งคำ — ไม่เดา
    """
    n = len(word)
    best = [None] * (n + 1)
    best[0] = []
    for i in range(1, n + 1):
        for w in _VOCAB:
            k = len(w)
            if k <= i and best[i - k] is not None and word[i - k:i] == w:
                best[i] = best[i - k] + [w]
                break
    return best[n]


def unknown_words(text):
    """คำที่อ่านไม่ออกในข้อความที่น่าจะเป็นจำนวนเงินตัวหนังสือ

    ใช้บอกผู้ตรวจว่าติดตรงไหน แทนที่จะบอกแค่ว่าอ่านไม่ได้
    OCR มักอ่านผิดทีละตัวอักษร เช่น Ffty แทน Fifty
    """
    if not text:
        return []
    s = str(text).upper()
    s = _FRACTION.sub(" ", s)
    s = s.replace("(", " ").replace(")", " ")
    if ":" in s:
        s = s.rsplit(":", 1)[1]
    s = re.sub(r"[^A-Z\- ]+", " ", s)
    bad = []
    for w in re.split(r"[\s\-]+", s):
        if not w or w in UNITS or w in TENS or w in SCALES or w in SKIP:
            continue
        if _segment(w) is None:
            bad.append(w)
    return bad


def looks_like_amount_words(text, min_known=2):
    """ข้อความนี้น่าจะเป็นจำนวนเงินตัวหนังสือหรือไม่

    ใช้แยกบรรทัดที่ตั้งใจเขียนจำนวนเงิน ออกจากข้อความทั่วไปที่บังเอิญมีคำพวกนี้
    """
    if not text:
        return False
    s = re.sub(r"[^A-Z\- ]+", " ", str(text).upper())
    n = sum(1 for w in re.split(r"[\s\-]+", s)
            if w and (w in UNITS or w in TENS or w in SCALES
                      or _segment(w) is not None))
    return n >= min_known


def words_to_number(text):
    """คืนจำนวนที่ตัวหนังสือระบุ หรือ None ถ้าอ่านไม่ออก

    ไม่เดา — ถ้ามีคำที่ไม่รู้จักปนอยู่จะคืน None
    เพราะการเดาผิดในหน้าที่ยืนยันตัวเลข อันตรายกว่าการบอกว่าอ่านไม่ได้
    """
    if not text:
        return None
    s = str(text).upper()

    cents = 0.0
    m = _FRACTION.search(s)
    if m:
        cents = int(m.group(1)) / 100.0
        s = s[:m.start()]

    # ลบเฉพาะตัววงเล็บ ไม่ลบข้อความข้างใน
    # เพราะจำนวนทั้งก้อนมักอยู่ในวงเล็บ  (CNY(CHINA):Four...Only)
    # ถ้าลบข้อความในวงเล็บ จะเหลือแต่ความว่างเปล่า
    s = s.replace("(", " ").replace(")", " ")
    if ":" in s:                                   # ตัดชื่อสกุลเงินหน้าเครื่องหมาย
        s = s.rsplit(":", 1)[1]
    s = re.sub(r"[^A-Z\- ]+", " ", s)
    raw = [w for w in re.split(r"[\s\-]+", s) if w]

    words = []
    for w in raw:
        if w in UNITS or w in TENS or w in SCALES or w in SKIP:
            words.append(w)
            continue
        part = _segment(w)                          # OCR เชื่อมคำติดกัน
        if part is None:
            return None
        words.extend(part)
    words = [w for w in words if w not in SKIP]
    if not words:
        return None

    total = 0
    group = 0
    seen = False
    for w in words:
        if w in UNITS:
            group += UNITS[w]
            seen = True
        elif w in TENS:
            group += TENS[w]
            seen = True
        elif w == "HUNDRED":
            group = (group or 1) * 100
            seen = True
        elif w in SCALES:
            total += (group or 1) * SCALES[w]
            group = 0
            seen = True
        else:
            return None                            # มีคำที่ไม่รู้จัก ไม่เดา
    if not seen:
        return None
    return round(total + group + cents, 2)
