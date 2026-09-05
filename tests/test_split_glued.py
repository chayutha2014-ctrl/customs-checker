"""แยกเซลล์ที่ OCR เชื่อมติดกัน

ข้อความทั้งหมดมาจาก OCR ของเอกสารจริง HUANYU/page_002.png และ page_001.png
พร้อมพิกัดจริงที่วัดได้ ไม่ได้แต่งขึ้น
"""
import pytest

from customs_checker.numbers import is_unit
from customs_checker.tables import Cell, Row, split_glued


def row(*specs):
    return Row([Cell(t, x0, 100.0, x1, 140.0) for t, x0, x1 in specs])


def texts(r):
    return [c.text for c in r.cells]


def test_เลขลำดับที่ติดมากับจำนวนเงินถูกแยกออก():
    r = row(("269.00 26", 2114.5, 2399.9))
    assert texts(split_glued([r])[0]) == ["269.00", "26"]


def test_กล่องของจำนวนเงินหดลงหลังแยก():
    """ขอบขวาต้องเลื่อนกลับมาใกล้คอลัมน์จำนวนเงิน ไม่ใช่ค้างที่คอลัมน์เลขลำดับ"""
    r = split_glued([row(("269.00 26", 2114.5, 2399.9))])[0]
    money = r.cells[0]
    assert money.text == "269.00"
    assert money.x1 < 2320.0


def test_ตัวเลขที่มีหน่วยกำกับไม่ถูกแยก():
    """150.00 MTR คือตัวเลขเดียวที่มีหน่วย ไม่ใช่สองช่องติดกัน"""
    r = row(("150.00 MTR", 1437.9, 1670.4))
    assert texts(split_glued([r])[0]) == ["150.00 MTR"]


@pytest.mark.parametrize("text, want", [
    ("154.00 20", ["154.00", "20"]),
    ("1,056.00 22", ["1,056.00", "22"]),
    ("149.40 2", ["149.40", "2"]),
    ("136.50 $8", ["136.50", "$8"]),
    ("819.00 4", ["819.00", "4"]),
    ("696.60 16", ["696.60", "16"]),
])
def test_รูปแบบที่เจอจริงในเอกสาร(text, want):
    assert texts(split_glued([row((text, 2100.0, 2380.0))])[0]) == want


@pytest.mark.parametrize("text", [
    "170.7023",        # ไม่มีช่องว่างคั่น แยกไม่ได้ ต้องปล่อยไว้
    "88.0030",
    "20.00 MTR",
    "10.00 PCS",
    "3805",
])
def test_ที่ต้องไม่แตะ(text):
    assert texts(split_glued([row((text, 2100.0, 2300.0))])[0]) == [text]


def test_เซลล์ถูกเรียงจากซ้ายไปขวาหลังแยก():
    r = split_glued([row(("269.00 26", 2114.5, 2399.9),
                         ("13.45", 1837.8, 1963.0))])[0]
    xs = [c.x0 for c in r.cells]
    assert xs == sorted(xs)


@pytest.mark.parametrize("token, want", [
    ("MTR", True), ("PCS", True), ("KGS", True), ("kg", True),
    ("26", False), ("3.", False), ("$8", False), ("2S", False),
])
def test_รู้จักชื่อหน่วย(token, want):
    assert is_unit(token) is want
