"""ตั้งชื่อคอลัมน์ Packing List ด้วยเลขคณิต ไม่ใช่ด้วยคำในหัวตาราง

หัวตารางที่ OCR อ่านมามักเพี้ยนจนเทียบคำไม่ได้
  SKM_450i26090315172  QTY(PCS) | CTNS | N.W. | G.W. | VOLUME     อ่านได้
  VORETO               Quendlry | UnktPrice | Weig(KGS)           เพี้ยน

แต่ยอดรวมที่เขียนเป็นข้อความใต้ตารางบอกทั้งค่าและความหมาย
จับคู่ด้วยค่า จึงไม่ขึ้นกับการสะกด
"""
import pytest

from customs_checker.packing_list import analyze_packing_list, _is_name
from customs_checker.tables import Cell, Row

CHAR_W = 25.0
LINE_H = 30.0


def at(text, right, y):
    num = text
    for i, ch in enumerate(text):
        if ch.isalpha():
            num = text[:i]
            break
    x0 = right - len(num) * CHAR_W
    return Cell(text, x0, y, x0 + len(text) * CHAR_W, y + LINE_H)


QTY_X, CTNS_X, NW_X, GW_X = 1400.0, 1600.0, 1900.0, 2200.0


def line(y, q, c, n, g):
    return Row([Cell("A", 100.0, y, 300.0, y + LINE_H),
                at(q, QTY_X, y), at(c, CTNS_X, y),
                at(n, NW_X, y), at(g, GW_X, y)])


def sheet(text):
    rows = [
        line(200, "1000", "167", "1767.33", "2034.00"),
        line(300, "800", "134", "1378.86", "1562.44"),
        line(400, "200", "99", "853.81", "903.56"),
        Row([Cell("TOTAL", 100.0, 500.0, 260.0, 530.0),
             at("2000PCS", QTY_X, 500.0), at("400CTNS", CTNS_X, 500.0),
             at("4000.00KGS", NW_X, 500.0), at("4500.00KGS", GW_X, 500.0)]),
    ]
    return analyze_packing_list(rows, text)


def by_x(res):
    return {round(c.x): (c.label, c.unit) for c in res.columns}


def test_หน่วยในแถวรวมตั้งชื่อคอลัมน์ได้เอง():
    """ไม่ต้องมีข้อความใต้ตารางก็ได้หน่วยมาแล้ว"""
    got = by_x(sheet(""))
    assert got[QTY_X][1] == "PCS"
    assert got[CTNS_X][1] == "CTNS"
    assert got[NW_X][1] == "KGS"


def test_ข้อความใต้ตารางแยกน้ำหนักสุทธิกับน้ำหนักรวม():
    """สองคอลัมน์หน่วย KGS เหมือนกัน หน่วยอย่างเดียวแยกไม่ออก"""
    got = by_x(sheet("TOTAL NET WEIGHT: 4000.00KGS\n"
                     "TOTAL GROSS WEIGHT: 4500.00KGS"))
    assert got[NW_X][0] == "NET WEIGHT"
    assert got[GW_X][0] == "GROSS WEIGHT"


def test_คู่น้ำหนักถูกแยกด้วยกฎ_ไม่ค้างเป็นชื่อซ้ำ():
    """เดิมสองคอลัมน์ KGS ขึ้นหมายเหตุว่าแยกไม่ออก
    ตอนนี้แยกได้ด้วยกฎน้ำหนักรวมมากกว่าสุทธิ จึงต้องไม่มีหมายเหตุชื่อซ้ำแล้ว"""
    res = sheet("")
    got = by_x(res)
    assert got[NW_X][0] == "NET WEIGHT"
    assert got[GW_X][0] == "GROSS WEIGHT"
    assert not any("ได้ชื่อเดียวกัน" in n for n in res.notes)
    assert any("น้ำหนักรวมมากกว่าสุทธิเสมอ" in n for n in res.notes)


def test_ชื่อซ้ำที่ไม่ใช่น้ำหนักยังต้องขึ้นหมายเหตุ():
    """สองคอลัมน์หน่วยเดียวกันที่ไม่มีกฎมาช่วยแยก ต้องบอกว่าแยกไม่ออก
    ของจริง Scan2026-09-03_182617 มีสองคอลัมน์ที่รวมได้ 196 เท่ากันทั้งคู่"""
    rows = [
        Row([Cell("A", 100.0, 200.0, 300.0, 230.0),
             at("30", QTY_X, 200.0), at("30", CTNS_X, 200.0)]),
        Row([Cell("A", 100.0, 300.0, 300.0, 330.0),
             at("61", QTY_X, 300.0), at("61", CTNS_X, 300.0)]),
        Row([Cell("A", 100.0, 400.0, 300.0, 430.0),
             at("105", QTY_X, 400.0), at("105", CTNS_X, 400.0)]),
        Row([Cell("TOTAL", 100.0, 500.0, 260.0, 530.0),
             at("196PCS", QTY_X, 500.0), at("196PCS", CTNS_X, 500.0)]),
    ]
    res = analyze_packing_list(rows, "")
    assert any("ได้ชื่อเดียวกัน" in n for n in res.notes)


def test_ไม่มีหมายเหตุเมื่อแยกออกแล้ว():
    res = sheet("TOTAL NET WEIGHT: 4000.00KGS\nTOTAL GROSS WEIGHT: 4500.00KGS")
    assert not res.notes


@pytest.mark.parametrize("label, want", [
    ("GROSS WEIGHT", True), ("TOTAL MEASUREMENT", True), ("NET WEIGHT", True),
    ("FOUR HUNDRED", False), ("TWO THOUSAND AND SIX", False),
])
def test_ไม่เอาการสะกดจำนวนเป็นตัวหนังสือมาเป็นชื่อ(label, want):
    """SAY TOTAL FOUR HUNDRED (400) CTNS ONLY. ไม่ใช่ชื่อคอลัมน์"""
    assert _is_name(label) is want


def test_ชื่อไม่หลุดไปคอลัมน์ที่ค่าไม่ตรง():
    got = by_x(sheet("TOTAL NET WEIGHT: 4000.00KGS"))
    assert got[GW_X][0] == ""
