"""ตัวเลขที่ใช้ช่องว่างคั่นหลักพัน

ข้อความทั้งหมดในไฟล์นี้มาจาก OCR ของเอกสารจริง ไม่ได้แต่งขึ้น
ที่มา: SHIJUN/page_001.png บรรทัดที่ 5 ของตารางสินค้า
"""
import pytest

from customs_checker.numbers import parse_number


@pytest.mark.parametrize("text, want", [
    ("18 422.00", 18422.00),        # จากเอกสารจริง 30200 x 0.61
    ("190 028.50", 190028.50),
    ("1 234 567", 1234567.0),
    ("5 000", 5000.0),
    ("18 422.00KGS", 18422.00),     # ช่องว่างคั่นหลักพัน + หน่วยต่อท้าย
])
def test_ช่องว่างคั่นหลักพันอ่านได้(text, want):
    assert parse_number(text) == pytest.approx(want)


def test_ไม่คืนแค่ตัวเลขหน้าช่องว่าง():
    """ก่อนแก้ คืน 18.0 ออกไปเหมือนเป็นจำนวนเงินเต็ม — ข้อผิดเงียบ"""
    assert parse_number("18 422.00") != 18.0


@pytest.mark.parametrize("text, want", [
    ("2 5", 2.0),            # กลุ่มหลังช่องว่างไม่ครบ 3 หลัก ไม่ใช่หลักพัน
    ("300 83", 300.0),
])
def test_กลุ่มไม่ครบสามหลักไม่ถือว่าเป็นหลักพัน(text, want):
    assert parse_number(text) == pytest.approx(want)


@pytest.mark.parametrize("text, want", [
    ("22,687.000", 22687.0),
    ("1,234,567", 1234567.0),
    ("1.234.567", 1234567.0),
    ("26.947.32", 26947.32),
    ("27526PCS", 27526.0),
    ("16123.02KGS", 16123.02),
    ("27.1800", 27.18),
])
def test_ของเดิมไม่เสีย(text, want):
    assert parse_number(text) == pytest.approx(want)


@pytest.mark.parametrize("text", ["C91542", "80BP0233TB", "2605B"])
def test_รหัสสินค้ายังถูกปฏิเสธ(text):
    assert parse_number(text) is None
