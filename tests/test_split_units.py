"""แยกหน่วยออกจากตัวเลขก่อนจัดคอลัมน์

บรรทัดสินค้าเขียนตัวเลขเปล่า แต่แถวรวมเขียนหน่วยติดมาด้วย
เซลล์แถวรวมจึงกว้างกว่าและขอบขวาเลื่อนไปตรงกับคอลัมน์ถัดไป

ข้อความและโครงตารางมาจาก SKM_450i26090315172/page_008.png ของจริง
"""
import pytest

from customs_checker.packing_list import split_units, analyze_packing_list
from customs_checker.tables import Cell, Row

CHAR_W = 25.0     # ความกว้างตัวอักษรโดยประมาณ ใช้วางพิกัดให้สมจริง
LINE_H = 30.0


def at(text, right, y):
    """วางเซลล์โดยให้ **ส่วนที่เป็นตัวเลข** ชิดขวาที่ตำแหน่ง right

    เอกสารจริงจัดตัวเลขชิดขวา หน่วยจึงล้นออกไปทางขวาของคอลัมน์
    ซึ่งเป็นสาเหตุที่ขอบขวาของเซลล์แถวรวมไปตรงกับคอลัมน์ถัดไป
    """
    num = text
    for i, ch in enumerate(text):
        if ch.isalpha():
            num = text[:i]
            break
    x0 = right - len(num) * CHAR_W
    return Cell(text, x0, y, x0 + len(text) * CHAR_W, y + LINE_H)


def cell(t, x0, x1, y=100.0):
    return Cell(t, x0, y, x1, y + LINE_H)


def test_หน่วยถูกแยกและกล่องหดตามสัดส่วน():
    r = Row([cell("27526PCS", 1300.0, 1460.0)])
    got = split_units([r])[0].cells
    assert [c.text for c in got] == ["27526", "PCS"]
    assert got[0].x1 == pytest.approx(1400.0)


@pytest.mark.parametrize("text, num", [
    ("27526PCS", "27526"), ("2006CTNS", "2006"),
    ("16123.02KGS", "16123.02"), ("158.17CBM", "158.17"),
    ("300PCS", "300"), ("75CTNS", "75"),
])
def test_รูปแบบที่เจอจริงในเอกสาร(text, num):
    got = split_units([Row([cell(text, 1000.0, 1200.0)])])[0].cells
    assert got[0].text == num


@pytest.mark.parametrize("text", [
    "1,767.33",          # ตัวเลขเปล่า ไม่มีอะไรให้แยก
    "B248-SSI3",         # รหัสสินค้า
    "12200S-W-SSI1",
    "TOTAL",
])
def test_ที่ต้องไม่แตะ(text):
    got = split_units([Row([cell(text, 1000.0, 1200.0)])])[0].cells
    assert [c.text for c in got] == [text]


def test_ขอบขวาของตัวเลขกลับมาตรงคอลัมน์หลังแยกหน่วย():
    """หัวใจของเรื่อง — ก่อนแยก ขอบขวาอยู่ที่ปลายหน่วย ไม่ใช่ปลายตัวเลข"""
    c = at("2006CTNS", 1600.0, 100.0)
    assert c.x1 > 1600.0                       # ก่อนแยก ล้นออกไปทางขวา
    got = split_units([Row([c])])[0].cells
    assert got[0].x1 == pytest.approx(1600.0)  # หลังแยก ตรงคอลัมน์พอดี


QTY_X, CTNS_X, NW_X = 1400.0, 1600.0, 1900.0


def line(y, qty, ctns, nw):
    return Row([Cell("A", 100.0, y, 300.0, y + LINE_H),
                at(qty, QTY_X, y), at(ctns, CTNS_X, y), at(nw, NW_X, y)])


def test_แถวรวมที่เขียนหน่วยกลับมาตรงคอลัมน์():
    """ก่อนแก้ แถวรวมทั้งแถวเลื่อนไปหนึ่งคอลัมน์ ระบบจึงหาแถวรวมไม่เจอ"""
    rows = [
        line(200, "1000", "167", "1767.33"),
        line(300, "800", "134", "1378.86"),
        line(400, "200", "99", "853.81"),
        Row([Cell("TOTAL", 100.0, 500.0, 260.0, 530.0),
             at("2000PCS", QTY_X, 500.0),
             at("400CTNS", CTNS_X, 500.0),
             at("3999.99KGS", NW_X, 500.0)]),
    ]
    r = analyze_packing_list(rows, "")
    assert r.total_row == 3
    assert sorted(c.printed for c in r.columns) == [400.0, 2000.0, 3999.99]


def test_ถ้าไม่แยกหน่วยจะหาแถวรวมไม่เจอ():
    """เทียบให้เห็นว่าปัญหาอยู่ที่เรขาคณิตจริง ไม่ใช่ที่ตัวเลข"""
    rows = [
        line(200, "1000", "167", "1767.33"),
        line(300, "800", "134", "1378.86"),
        line(400, "200", "99", "853.81"),
        Row([Cell("TOTAL", 100.0, 500.0, 260.0, 530.0),
             at("2000PCS", QTY_X, 500.0),
             at("400CTNS", CTNS_X, 500.0),
             at("3999.99KGS", NW_X, 500.0)]),
    ]
    from customs_checker.tables import numeric_columns
    from customs_checker.packing_list import find_total_row
    raw_cols = numeric_columns(rows)          # ไม่ผ่าน split_units
    assert find_total_row(raw_cols)[0] is None
