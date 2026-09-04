"""
ตัวแปลงวันที่สำหรับเอกสารศุลกากร
รองรับ: ค.ศ./พ.ศ. · ปีสองหลัก/สี่หลัก · เดือนเป็นตัวเลข/ชื่อ อังกฤษ/ไทย · ลำดับ วัน-เดือน สลับ
เมื่อกำกวมจริงจะไม่เดา แต่คืนค่าพร้อมธง ambiguous ให้คนตัดสิน
"""
from dataclasses import dataclass, field
from datetime import date
import re

BE_OFFSET = 543

EN_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "SEPT": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
TH_MONTHS = {
    "ม.ค.": 1, "มกราคม": 1, "ก.พ.": 2, "กุมภาพันธ์": 2, "มี.ค.": 3, "มีนาคม": 3,
    "เม.ย.": 4, "เมษายน": 4, "พ.ค.": 5, "พฤษภาคม": 5, "มิ.ย.": 6, "มิถุนายน": 6,
    "ก.ค.": 7, "กรกฎาคม": 7, "ส.ค.": 8, "สิงหาคม": 8, "ก.ย.": 9, "กันยายน": 9,
    "ต.ค.": 10, "ตุลาคม": 10, "พ.ย.": 11, "พฤศจิกายน": 11, "ธ.ค.": 12, "ธันวาคม": 12,
}


@dataclass
class ParsedDate:
    value: date | None = None
    era: str = ""                       # "CE" หรือ "BE"
    ambiguous: bool = False             # วัน/เดือน สลับกันได้ ต้องให้คนดู
    alternatives: tuple = ()
    raw: str = ""
    note: str = ""

    def __bool__(self) -> bool:
        return self.value is not None


def resolve_year(n: int, ref: date) -> tuple[int, str]:
    """แปลงเลขปีเป็น ค.ศ. พร้อมบอกว่าต้นทางเป็น ค.ศ. หรือ พ.ศ."""
    if n >= 2400:                                   # 2569 = พ.ศ. ชัดเจน
        return n - BE_OFFSET, "BE"
    if 1900 <= n <= 2199:                           # 2026 = ค.ศ. ชัดเจน
        return n, "CE"
    if n < 100:                                     # สองหลัก — ต้องเดาจากบริบท
        cands = [(2000 + n, "CE"), (2500 + n - BE_OFFSET, "BE")]
        cands.sort(key=lambda c: abs(c[0] - ref.year))
        return cands[0]
    raise ValueError(f"ปีไม่สมเหตุสมผล: {n}")


def _build(y: int, m: int, d: int, era: str, raw: str,
           ambiguous: bool = False, alt: tuple = (), note: str = "") -> ParsedDate:
    try:
        return ParsedDate(date(y, m, d), era, ambiguous, alt, raw, note)
    except ValueError:
        return ParsedDate(None, raw=raw, note="วันที่ไม่มีอยู่จริง")


def _parse(raw: str, ref: date | None = None) -> ParsedDate:
    ref = ref or date.today()
    s = raw.strip()
    if not s:
        return ParsedDate(raw=raw, note="ว่าง")
    up = re.sub(r"\s+", " ", s.upper())

    # --- เดือนเป็นชื่อไทย: 3 ส.ค. 69 / 3 สิงหาคม 2569 ---
    for name, mon in TH_MONTHS.items():
        if name in s:
            nums = re.findall(r"\d+", s.replace(name, "|"))
            if len(nums) >= 2:
                d, yn = int(nums[0]), int(nums[-1])
                y, era = resolve_year(yn, ref)
                return _build(y, mon, d, era, raw)

    # --- เดือนเป็นชื่ออังกฤษ: 27 AUGUST 2026 / 3-AUG-26 / AUG 17, 2026 ---
    m = re.search(r"([A-Z]{3,9})", up)
    if m:
        token = m.group(1)
        mon = next((v for k, v in EN_MONTHS.items() if token.startswith(k)), None)
        if mon:
            nums = [int(x) for x in re.findall(r"\d+", up)]
            if len(nums) >= 2:
                before = up[:m.start()]
                d, yn = (nums[0], nums[-1]) if re.search(r"\d", before) else (nums[0], nums[-1])
                if not re.search(r"\d", before):     # AUG 17, 2026
                    d, yn = nums[0], nums[-1]
                y, era = resolve_year(yn, ref)
                return _build(y, mon, d, era, raw)

    # --- ตัวเลขล้วน ---
    nums = re.findall(r"\d+", up)
    if len(nums) != 3:
        return ParsedDate(raw=raw, note="ไม่เข้ารูปแบบวันที่")
    a, b, c = (int(x) for x in nums)

    if len(nums[0]) == 4:                            # 2026-8-17 (ปีนำ)
        y, era = resolve_year(a, ref)
        return _build(y, b, c, era, raw)

    y, era = resolve_year(c, ref)
    if a > 12 and b <= 12:                           # 24/8/2026
        return _build(y, b, a, era, raw)
    if b > 12 and a <= 12:                           # 8/24/2026
        return _build(y, a, b, era, raw, note="ลำดับ เดือน/วัน")
    if a <= 12 and b <= 12:                          # 10/8/2026 — กำกวมจริง
        dm = _build(y, b, a, era, raw, ambiguous=True)
        md = date(y, a, b) if _build(y, a, b, era, raw) else None
        return ParsedDate(dm.value, era, True, (dm.value, md), raw,
                          "วัน/เดือน สลับกันได้ ต้องให้คนยืนยัน")
    return ParsedDate(raw=raw, note="ค่าวันหรือเดือนเกินช่วง")


def parse_date(raw: str, ref: date | None = None) -> ParsedDate:
    """
    จุดเข้าใช้งานหลัก — ไม่โยน exception ไม่ว่าอินพุตจะเป็นอะไร
    ข้อความที่ไม่ใช่วันที่ (เบอร์โทร เลขที่เอกสาร) จะคืน value=None พร้อมเหตุผล
    """
    try:
        return _parse(raw, ref)
    except (ValueError, TypeError, IndexError) as e:
        return ParsedDate(raw=raw, note=f"ไม่ใช่วันที่: {e}")
