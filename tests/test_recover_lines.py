"""กู้บรรทัดที่เซลล์จำนวนเงินเสียรูป

ข้อความและพิกัดมาจาก OCR ของเอกสารจริง HUANYU และ VORETO ไม่ได้แต่งขึ้น
"""
import pytest

from customs_checker.tables import Cell, Row, analyze_invoice, _digits


def sheet(specs):
    """สร้างตารางจาก [(qty, price, ข้อความเซลล์จำนวนเงิน, ขอบซ้าย, ขอบขวา), ...]"""
    rows = []
    for i, (q, p, amt, ax0, ax1) in enumerate(specs):
        y = 100.0 + i * 50
        rows.append(Row([
            Cell(f"{q:.2f} MTR", 1437.9, y, 1670.4, y + 40),
            Cell(f"{p:.2f}", 1860.8, y, 1966.5, y + 40),
            Cell(amt, ax0, y, ax1, y + 40),
        ]))
    return rows


@pytest.mark.parametrize("v, want", [
    (662.70, "66270"), ("$66270", "66270"), ("170.7023", "1707023"),
    (88.0, "8800"), ("136.50 $8", "136508"),
])
def test_ตัวเลขล้วน(v, want):
    assert _digits(v) == want


def test_เลขลำดับเชื่อมท้ายโดยไม่มีช่องว่าง():
    """HUANYU: 30 x 5.69 = 170.70 แต่ OCR ให้ 170.7023 เพราะเลขลำดับ 23 ติดมา"""
    rows = sheet([
        (150.0, 1.72, "258.00", 2119.8, 2285.4),
        (300.0, 2.73, "819.00", 2119.8, 2285.4),
        (30.0, 5.69, "170.7023", 2114.5, 2373.5),
    ])
    res = analyze_invoice(rows)
    amounts = sorted(l["amount"] for l in res["lines"])
    assert amounts == [170.70, 258.00, 819.00]
    assert res["computed"] == pytest.approx(1247.70)


def test_จุดทศนิยมหาย():
    """VORETO: 15 x 44.18 = 662.70 แต่ OCR ให้ $66270"""
    rows = sheet([
        (10.0, 27.18, "$271.80", 2119.8, 2285.4),
        (3.0, 86.75, "$260.25", 2119.8, 2285.4),
        (15.0, 44.18, "$66270", 2114.5, 2290.0),
    ])
    res = analyze_invoice(rows)
    assert res["computed"] == pytest.approx(1194.75)


def test_บรรทัดที่กู้ถูกรายงานไว้เสมอ():
    """ห้ามแก้เงียบ ต้องมีร่องรอยให้คนตรวจย้อนได้"""
    rows = sheet([
        (150.0, 1.72, "258.00", 2119.8, 2285.4),
        (300.0, 2.73, "819.00", 2119.8, 2285.4),
        (30.0, 5.69, "170.7023", 2114.5, 2373.5),
    ])
    res = analyze_invoice(rows)
    assert res["repaired"], "ต้องรายงานบรรทัดที่กู้"
    r = res["repaired"][0]
    assert r["cell"] == "170.7023"
    assert r["used"] == pytest.approx(170.70)


def test_เอกสารคิดเลขผิดจริงต้องไม่ถูกกู้():
    """ถ้าจำนวนเงินในเอกสารไม่ตรงกับ จำนวน x ราคา จริง ๆ ตัวเลขจะไม่ขึ้นต้นตรงกัน
    บรรทัดนั้นต้องไม่ถูกดึงเข้ามา ไม่งั้นจะกลบข้อผิดพลาดของเอกสาร"""
    rows = sheet([
        (150.0, 1.72, "258.00", 2119.8, 2285.4),
        (300.0, 2.73, "819.00", 2119.8, 2285.4),
        (30.0, 5.69, "999.99", 2114.5, 2373.5),
    ])
    res = analyze_invoice(rows)
    assert all(l["row"] != 2 for l in res["lines"])
