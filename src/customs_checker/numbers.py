import re
_TOKEN = re.compile(r"\d[\d.,]*")
_CODE_LIKE = re.compile(r"\d\s*[-/]\s*\d|\d[A-Za-z]|[A-Za-z]\d")

# หน่วยที่พิมพ์ติดกับตัวเลขได้ เช่น 27526PCS  16123.02KGS  158.17CBM
# ถ้าไม่ยกเว้นให้ ด่านกันรหัสสินค้าจะปฏิเสธทิ้งหมด แล้วแถวรวมของ Packing List
# จะกลายเป็นแถวที่ไม่มีตัวเลขเลย
_UNITS = (r"(?:PCS|PC|PIECES|CTNS|CTN|CARTONS|CARTON|PLTS|PLT|PALLETS|PALLET|"
          r"SETS|SET|KGS|KGM|KG|CBM|M3|MTR|PKGS|PKG|BOXES|BOX|ROLLS|ROLL|"
          r"BAGS|BAG|DOZ|LTR|M|L)")
_NUM_UNIT = re.compile(rf"^\s*([\d][\d.,]*)\s*{_UNITS}\s*$", re.I)

# ตัวคั่นหลักพันที่เป็นช่องว่าง เช่น "18 422.00" ซึ่งเจอทั้งจากเอกสารที่พิมพ์แบบยุโรป
# และจาก OCR ที่แยกจุลภาคออกเป็นช่องว่าง
#
# ถ้าไม่จับ _TOKEN จะคว้าได้แค่ "18" แล้วคืนค่า 18.0 ออกไปเหมือนเป็นจำนวนเงินเต็ม
# บรรทัดนั้นจึงเข้าคู่ไม่ได้และหายไปทั้งบรรทัด (SHIJUN ขาด 18,422.00 พอดี)
# อันตรายกว่าการคืน None เพราะเป็นตัวเลขที่ดูปกติแต่ผิด
#
# บังคับให้กลุ่มหลังช่องว่างมี 3 หลักเป๊ะ "12 345" จึงอ่านเป็น 12345
# แต่ "2 5" หรือ "300 83" ไม่เข้าเงื่อนไข ตกไปตามทางเดิม
_SPACE = "[ \u00a0\u2009\u202f]"
_SPACED_NUM = re.compile(
    rf"^\s*(\d{{1,3}}(?:{_SPACE}\d{{3}})+(?:[.,]\d{{1,4}})?)\s*(?:{_UNITS})?\s*$",
    re.I)


def parse_number(text):
    s = str(text)
    m = _SPACED_NUM.match(s)
    if m:                       # ช่องว่างคั่นหลักพัน รวมกลับเป็นตัวเลขเดียว
        s = re.sub(_SPACE, "", m.group(1))
    else:
        m = _NUM_UNIT.match(s)
        if m:                   # ตัวเลขที่มีหน่วยติดมา ตัดหน่วยแล้วอ่านต่อ
            s = m.group(1)
    if _CODE_LIKE.search(s):
        return None
    m = _TOKEN.search(s)
    if not m: return None
    t = m.group(0).rstrip(".,")
    if not t or not t[0].isdigit(): return None
    seps = [i for i, ch in enumerate(t) if ch in ".,"]
    if not seps: return float(t)
    groups = []
    for n, pos in enumerate(seps):
        end = seps[n + 1] if n + 1 < len(seps) else len(t)
        groups.append(t[pos + 1:end])
    if len(seps) > 1:
        chars = {t[i] for i in seps}
        # ตัวคั่นปนกันสองชนิด = ตัวสุดท้ายคือจุดทศนิยมแน่นอน
        # 22,687.000 คือ 22687.000 ไม่ใช่ 22,687,000
        # (ใบขนไทยและ Packing List ใช้ทศนิยม 3 ตำแหน่ง กฎ "กลุ่มละ 3 หลัก = หลักพัน"
        #  จึงอ่านผิดเป็นพันเท่าแบบเงียบ ๆ)
        if len(chars) == 1 and all(len(g) == 3 for g in groups):
            return float(re.sub(r"[.,]", "", t))
        last = seps[-1]
        head = re.sub(r"[.,]", "", t[:last]) or "0"
        return float(f"{head}.{t[last + 1:]}")
    pos, sep, frac = seps[0], t[seps[0]], groups[0]
    if not frac: return float(t[:pos])
    if len(frac) == 3 and sep == ",": return float(t.replace(",", ""))
    return float(f"{t[:pos] or '0'}.{frac}")


_UNIT_ONLY = re.compile(rf"^{_UNITS}$", re.I)


def is_unit(token):
    """ข้อความนี้เป็นชื่อหน่วยล้วน ๆ หรือไม่ เช่น MTR PCS KGS

    ใช้ตอนตัดสินว่าคำที่ต่อท้ายตัวเลขเป็นหน่วยของตัวเลขนั้น (ห้ามแยก)
    หรือเป็นข้อความคนละช่องที่ OCR เชื่อมติดมา (ต้องแยก)
    """
    t = re.sub(r"[^A-Za-z0-9]", "", str(token))
    return bool(t) and bool(_UNIT_ONLY.match(t))
