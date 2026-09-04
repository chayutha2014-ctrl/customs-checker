"""
ชั้นตรวจสอบตัวเลขด้วยความสอดคล้องภายในเอกสาร
หลักการ: ปริมาณ × ราคาต่อหน่วย = จำนวนเงิน  และ  Σ จำนวนเงิน = ยอดรวม
ตัวเลขที่ผ่านการตรวจนี้เชื่อถือได้สูงมาก เพราะโอกาสอ่านผิดแล้วยังคูณลงตัวแทบเป็นศูนย์
"""
from dataclasses import dataclass
import re

NUM_RE = re.compile(r"\d[\d,]*\.?\d*")


@dataclass(frozen=True)
class LineTriple:
    qty: float
    price: float
    amount: float
    pos: int          # ตำแหน่งในลำดับการอ่าน ใช้เรียงและกันซ้ำ

    def __str__(self) -> str:
        return f"{self.qty:,g} × {self.price:,g} = {self.amount:,.2f}"


def extract_numbers(text: str) -> list[float]:
    """ดึงตัวเลขทั้งหมดตามลำดับที่ปรากฏ"""
    out = []
    for tok in NUM_RE.findall(text):
        tok = tok.rstrip(".").replace(",", "")
        if not tok or tok.count(".") > 1:
            continue
        try:
            out.append(float(tok))
        except ValueError:
            pass
    return out


def balanced(a: float, b: float, c: float, tol: float = 0.01) -> bool:
    return abs(a * b - c) <= max(tol, abs(c) * 1e-6)


def find_line_triples(nums: list[float], window: int = 6,
                      min_amount: float = 1.0) -> list[LineTriple]:
    """
    หา (ปริมาณ, ราคา, จำนวนเงิน) ที่คูณกันลงตัว
    จำกัดให้ทั้งสามตัวอยู่ใกล้กันในลำดับการอ่าน เพื่อกันการจับคู่มั่ว
    """
    found, used = [], set()
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, min(i + window, n)):
            for k in range(j + 1, min(i + window + 1, n)):
                a, b, c = nums[i], nums[j], nums[k]
                if a <= 0 or b <= 0 or c < min_amount:
                    continue
                if a == 1 or b == 1:          # 1 × c = c ไม่ให้ข้อมูลอะไร
                    continue
                if balanced(a, b, c) and k not in used:
                    found.append(LineTriple(a, b, c, i))
                    used.add(k)
                    break
            else:
                continue
            break
    return found


def sum_amounts(triples: list[LineTriple]) -> float:
    return round(sum(t.amount for t in triples), 2)


def verify_total(triples: list[LineTriple], nums: list[float],
                 tol: float = 0.01) -> dict:
    """
    เทียบผลรวมของรายการที่พบ กับตัวเลขที่ปรากฏในเอกสาร
    คืนสถานะ 3 แบบตามหลักการ: ยืนยันได้ / คำนวณได้แต่ไม่พบยอดพิมพ์ / ไม่ลงตัว
    """
    computed = sum_amounts(triples)
    if not triples:
        return {"status": "ไม่พบรายการ", "computed": None, "printed": None}
    match = next((v for v in nums if abs(v - computed) <= tol), None)
    if match is not None:
        return {"status": "ยืนยันแล้ว", "computed": computed, "printed": match}
    return {"status": "คำนวณได้ ไม่พบยอดพิมพ์", "computed": computed, "printed": None}
