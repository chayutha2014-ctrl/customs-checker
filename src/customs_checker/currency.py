"""
ระบุสกุลเงินจากเอกสาร
หลักการ: ต้องพบอย่างน้อย 2 แห่งที่สอดคล้องกันจึงยืนยัน · ห้ามมีค่าเริ่มต้น ·
สัญลักษณ์ที่กำกวม (¥ $) ต้องมีรหัสสกุลชัดเจนมาช่วยเสมอ
"""
from dataclasses import dataclass, field
import re

# รหัสที่ชัดเจน ไม่กำกวม
EXPLICIT = [
    (r"\bUSD\b|\bUS\s*\$|\bUS\s*DOLLARS?\b|\bU\.S\.\s*DOLLARS?\b", "USD"),
    (r"\bRMB\b|\bCNY\b|\bYUAN\b|\bRENMINBI\b", "CNY"),
    (r"\bJPY\b|\bJAPANESE\s+YEN\b", "JPY"),
    (r"\bEUR\b|\bEURO?S?\b", "EUR"),
    (r"\bTHB\b|\bBAHT\b|\bบาท\b", "THB"),
    (r"\bGBP\b|\bSTERLING\b", "GBP"),
    (r"\bHKD\b", "HKD"),
    (r"\bSGD\b", "SGD"),
    (r"\bAUD\b", "AUD"),
    (r"\bTWD\b|\bNT\$", "TWD"),
    (r"\bVND\b", "VND"),
    (r"\bKRW\b", "KRW"),
]

# สัญลักษณ์ที่เป็นได้หลายสกุล — ใช้ยืนยันไม่ได้ด้วยตัวเอง
AMBIGUOUS = {
    "¥": ["CNY", "JPY"],
    "$": ["USD", "HKD", "SGD", "AUD", "TWD"],
    "€": ["EUR"],
    "£": ["GBP"],
    "฿": ["THB"],
}

# ใช้ช่วยตัดสินสัญลักษณ์เท่านั้น ห้ามใช้แทนรหัสที่เขียนไว้ชัด
COUNTRY_HINT = {"CN": "CNY", "JP": "JPY", "TH": "THB", "TW": "TWD",
                "HK": "HKD", "SG": "SGD", "KR": "KRW"}


@dataclass
class CurrencyResult:
    code: str | None = None
    status: str = "ไม่พบ"          # ยืนยัน / ต้องให้คนยืนยัน / ขัดแย้ง / ไม่พบ
    mentions: list = field(default_factory=list)
    candidates: list = field(default_factory=list)
    note: str = ""

    def __bool__(self):
        return self.code is not None


def find_mentions(text: str):
    """คืนรายการ (ข้อความที่พบ, รหัสสกุล) จากรหัสที่ชัดเจนเท่านั้น"""
    up = text.upper()
    out = []
    for pat, code in EXPLICIT:
        for m in re.finditer(pat, up):
            out.append((m.group(0).strip(), code))
    return out


def find_symbols(text: str):
    return [s for s in AMBIGUOUS if s in text]


def resolve_currency(text: str, country: str | None = None) -> CurrencyResult:
    mentions = find_mentions(text)
    symbols = find_symbols(text)
    codes = {c for _, c in mentions}

    if len(codes) > 1:
        return CurrencyResult(None, "ขัดแย้ง", mentions, sorted(codes),
                              f"พบสกุลเงินขัดแย้งกัน {sorted(codes)} ต้องแก้ก่อนยื่น")

    if len(codes) == 1:
        code = codes.pop()
        # สัญลักษณ์ที่พบต้องไม่ขัดกับรหัส
        for s in symbols:
            if code not in AMBIGUOUS[s]:
                return CurrencyResult(None, "ขัดแย้ง", mentions, [code],
                                      f"รหัส {code} ขัดกับสัญลักษณ์ {s}")
        n = len(mentions)
        if n >= 2:
            return CurrencyResult(code, "ยืนยัน", mentions, [code],
                                  f"พบ {n} แห่ง สอดคล้องกัน")
        return CurrencyResult(code, "ต้องให้คนยืนยัน", mentions, [code],
                              "พบเพียงแห่งเดียว ควรให้คนยืนยัน")

    if symbols:
        cands = sorted({c for s in symbols for c in AMBIGUOUS[s]})
        if len(cands) == 1:
            return CurrencyResult(cands[0], "ต้องให้คนยืนยัน", [], cands,
                                  f"พบเฉพาะสัญลักษณ์ {symbols}")
        hint = COUNTRY_HINT.get((country or "").upper())
        if hint and hint in cands:
            return CurrencyResult(hint, "ต้องให้คนยืนยัน", [], cands,
                                  f"สัญลักษณ์ {symbols} กำกวม เดาจากประเทศ {country}")
        return CurrencyResult(None, "ต้องให้คนยืนยัน", [], cands,
                              f"พบเฉพาะสัญลักษณ์ {symbols} เป็นได้ {cands}")

    return CurrencyResult(None, "ไม่พบ", [], [], "ไม่พบสกุลเงินในเอกสาร")
