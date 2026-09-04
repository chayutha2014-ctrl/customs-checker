"""
ชุดทดสอบการอ่านตาราง — รูปทรงทั้งหมดจำลองจากใบ Invoice จริงที่เจอในการทดลอง
สร้างเซลล์เองเพื่อให้ทดสอบได้เร็วและไม่ต้องพึ่ง OCR
"""
import pytest
from customs_checker.tables import (
    Cell, Row, group_rows, numeric_columns, find_product_triple,
    reconcile, analyze_invoice)

H = 20          # ความสูงตัวอักษร
GAP = 60        # ระยะห่างระหว่างบรรทัด


def C(text, x1, r, w=70):
    """สร้างเซลล์ที่ขอบขวาอยู่ที่ x1 บรรทัดที่ r"""
    return Cell(str(text), x1 - w, r * GAP, x1, r * GAP + H)


def table(rows_spec):
    """rows_spec = [[(ข้อความ, ขอบขวา), ...], ...]  →  list[Row]"""
    cells = []
    for r, spec in enumerate(rows_spec):
        for text, x1 in spec:
            cells.append(C(text, x1, r))
    return group_rows(cells)


# ── รูปทรงพื้นฐาน: FUJIAN ─────────────────────────────────────────
BASIC = [
    [("Q'TY", 300), ("UNIT PRICE", 500), ("AMOUNT", 700)],
    [("300", 300), ("8.30", 500), ("2,490.00", 700)],
    [("235", 300), ("156.87", 500), ("36,864.45", 700)],
    [("10", 300), ("156.87", 500), ("1,568.70", 700)],
    [("TOTAL", 200), ("40,923.15", 700)],
]


def test_พบสามคอลัมน์และคำนวณยอดถูก():
    r = analyze_invoice(table(BASIC))
    assert len(r["lines"]) == 3
    assert r["computed"] == 40923.15
    assert r["printed"] == 40923.15
    assert r["status"] == "ยืนยันด้วยยอดพิมพ์"


def test_แถวยอดรวมไม่ถูกนับเป็นสินค้า():
    r = analyze_invoice(table(BASIC))
    assert all(l["amount"] != 40923.15 for l in r["lines"])


def test_ไม่อ่านหัวตารางก็ยังทำงานได้():
    """เปลี่ยนหัวคอลัมน์เป็นภาษาจีนล้วน ผลต้องเหมือนเดิม"""
    spec = [[("数量", 300), ("单价", 500), ("金额", 700)]] + BASIC[1:]
    r = analyze_invoice(table(spec))
    assert r["computed"] == 40923.15


# ── สินค้าบรรทัดเดียว: ITALISA ────────────────────────────────────
def test_สินค้าบรรทัดเดียว():
    spec = [
        [("Qty", 300), ("FOB HAI PHONG", 500), ("TOTAL", 700)],
        [("500", 300), ("6.18", 500), ("3,090.00", 700)],
        [("TOTAL", 200), ("500", 300), ("3,090.00", 700)],
    ]
    r = analyze_invoice(table(spec))
    assert len(r["lines"]) == 1
    assert r["computed"] == 3090.00


# ── บรรทัดที่อ่านปริมาณไม่ครบ: SHIJUN ─────────────────────────────
def test_กระทบยอดเติมบรรทัดที่อ่านไม่ครบ():
    spec = [
        [("Quantity", 300), ("Unit Price", 500), ("Total", 700)],
        [("52,500", 300), ("0.86", 500), ("45,150.00", 700)],
        [("30,200", 300), ("0.61", 500), ("18,422.00", 700)],
        [("16,500.00", 700)],                      # อ่านปริมาณกับราคาไม่ได้
        [("Total Amount", 200), ("80,072.00", 700)],
    ]
    r = analyze_invoice(table(spec))
    assert len(r["lines"]) == 2
    assert r["missing_lines"] == [16500.00]
    assert r["computed"] == 80072.00
    assert "เติม" in r["status"]


# ── ปริมาณเท่ากับ 1 ต้องไม่ถูกตัดทิ้ง: VORETO ─────────────────────
def test_บรรทัดที่ปริมาณเท่ากับหนึ่ง():
    spec = [
        [("Quantity", 300), ("Unit Price", 500), ("Amount", 700)],
        [("1", 300), ("118.23", 500), ("118.23", 700)],
        [("10", 300), ("27.18", 500), ("271.80", 700)],
        [("30", 300), ("27.18", 500), ("815.40", 700)],
        [("TOTAL", 200), ("1,205.43", 700)],
    ]
    r = analyze_invoice(table(spec))
    assert len(r["lines"]) == 3
    assert r["computed"] == 1205.43


# ── ตัวเลขแปลกปลอมต้องไม่ทำให้ผลเพี้ยน ────────────────────────────
def test_เลขที่เอกสารในคอลัมน์เดียวกันไม่ทำให้พลาด():
    spec = [
        [("Invoice No", 400), ("20260824", 700)],   # เลขที่เอกสาร ขอบขวาตรงกับคอลัมน์เงิน
        [("Q'TY", 300), ("PRICE", 500), ("AMOUNT", 700)],
        [("300", 300), ("8.30", 500), ("2,490.00", 700)],
        [("235", 300), ("156.87", 500), ("36,864.45", 700)],
        [("TOTAL", 200), ("39,354.45", 700)],
    ]
    r = analyze_invoice(table(spec))
    assert len(r["lines"]) == 2
    assert r["computed"] == 39354.45
    assert r["status"] == "ยืนยันด้วยยอดพิมพ์"


# ── ไม่ลงตัวต้องไม่เงียบ ──────────────────────────────────────────
def test_ยอดไม่ตรงต้องแจ้ง_ไม่ใช่ตอบมั่ว():
    spec = [
        [("Q'TY", 300), ("PRICE", 500), ("AMOUNT", 700)],
        [("300", 300), ("8.30", 500), ("2,490.00", 700)],
        [("TOTAL", 200), ("9,999.99", 700)],        # ยอดพิมพ์ไม่ตรงกับผลรวม
    ]
    r = analyze_invoice(table(spec))
    assert r["computed"] == 2490.00
    assert r["gap"] is not None
    assert r["gap"][1] == pytest.approx(7509.99)
    assert r["status"] == "ยอดพิมพ์กับยอดคำนวณไม่ตรงกัน"


def test_ตารางที่ไม่มีความสัมพันธ์ต้องไม่เดา():
    spec = [
        [("A", 300), ("B", 500), ("C", 700)],
        [("11", 300), ("22", 500), ("33", 700)],
        [("44", 300), ("55", 500), ("66", 700)],
    ]
    r = analyze_invoice(table(spec))
    assert r["lines"] == []
    assert r["computed"] is None


# ── ฟังก์ชันย่อย ─────────────────────────────────────────────────
def test_reconcile_ตรงพอดี():
    assert reconcile(100.0, [100.0]) == (100.0, [])


def test_reconcile_ต้องเติมสองบรรทัด():
    total, extra = reconcile(100.0, [130.0, 20.0, 10.0])
    assert total == 130.0
    assert sorted(extra) == [10.0, 20.0]


def test_reconcile_ไม่มีคำตอบ():
    assert reconcile(100.0, [500.0, 7.0]) == (None, [])


def test_เสนอยอดที่เป็นไปได้เมื่ออธิบายไม่ครบ():
    """มีจำนวนเงินค้างอยู่แต่ไม่มียอดพิมพ์ให้เทียบ ต้องเสนอยอดที่น่าจะเป็น"""
    spec = [
        [("Q'TY", 300), ("PRICE", 500), ("AMOUNT", 700)],
        [("10", 300), ("27.18", 500), ("271.80", 700)],
        [("30", 300), ("27.18", 500), ("815.40", 700)],
        [("118.23", 700)],                      # อ่านปริมาณกับราคาไม่ได้
    ]
    r = analyze_invoice(table(spec))
    assert r["computed"] == 1087.20
    assert r["possible_total"] == 1205.43
    assert r["unexplained"] == [118.23]
    assert r["printed"] is None                 # ยังยืนยันไม่ได้ ต้องให้คนดู
