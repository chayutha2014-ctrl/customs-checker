"""
แยกวิเคราะห์ตัวเลขจากข้อความในเซลล์

กฎตัวคั่น:
- ตัวคั่นเดียว + 3 หลัก + เป็นจุลภาค  → หลักพัน (1,000 = 1000)
- ตัวคั่นเดียว + 3 หลัก + เป็นจุด      → ทศนิยม (500.000 = 500.0 ตามรูปแบบใบขนไทย)
- ตัวคั่นเดียว + หลักอื่น              → ทศนิยม (27.1800 = 27.18)
- หลายตัวคั่น + ทุกกลุ่ม 3 หลัก        → หลักพันล้วน (1.234.567 = 1234567)
- หลายตัวคั่น + กลุ่มท้ายไม่ใช่ 3 หลัก → ตัวท้ายเป็นทศนิยม (26.947.32 = 26947.32)
"""
import re

_TOKEN = re.compile(r"\d[\d.,]*")
_CODE_LIKE = re.compile(r"\d\s*[-/]\s*\d|\d[A-Za-z]|[A-Za-z]\d")


def parse_number(text: str):
    s = str(text)
    if _CODE_LIKE.search(s):          # รหัสสินค้า เลขที่เอกสาร เบอร์โทร
        return None

    m = _TOKEN.search(s)
    if not m:
        return None
    t = m.group(0).rstrip(".,")
    if not t or not t[0].isdigit():
        return None

    seps = [i for i, ch in enumerate(t) if ch in ".,"]
    if not seps:
        return float(t)

    groups = []
    for n, pos in enumerate(seps):
        end = seps[n + 1] if n + 1 < len(seps) else len(t)
        groups.append(t[pos + 1:end])

    if len(seps) > 1:
        if all(len(g) == 3 for g in groups):
            return float(re.sub(r"[.,]", "", t))
        last = seps[-1]
        head = re.sub(r"[.,]", "", t[:last]) or "0"
        return float(f"{head}.{t[last + 1:]}")

    pos, sep, frac = seps[0], t[seps[0]], groups[0]
    if not frac:
        return float(t[:pos])
    if len(frac) == 3 and sep == ",":
        return float(t.replace(",", ""))
    return float(f"{t[:pos] or '0'}.{frac}")
