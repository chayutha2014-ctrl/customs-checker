"""Packing List ที่มีบรรทัดสินค้าบรรทัดเดียว

ยอดรวมย่อมเท่ากับบรรทัดนั้นเสมอ เลขคณิตจึงยืนยันอะไรไม่ได้
ต้องอาศัยหลักฐานอีกทางคือแถวนั้นเขียนคำว่ายอดรวมไว้เอง

ข้อความและโครงตารางมาจาก SKM_450i26090410270/page_003.png ของจริง
"""
from customs_checker.packing_list import analyze_packing_list
from customs_checker.tables import Cell, Row


def row(y, *cells):
    return Row([Cell(t, x0, y, x1, y + 30) for t, x0, x1 in cells])


HEAD = row(100, ("ITEM NO.", 100, 300), ("G.W.", 1400, 1500),
           ("N.W.", 1700, 1800), ("VOL", 2000, 2100))
LINE = row(200, ("H-MC9330", 100, 300), ("75CTNS", 600, 750),
           ("300PCS", 1000, 1150), ("790.00", 1380, 1500),
           ("640.00", 1680, 1800), ("8.506", 1990, 2100))


def total_row(label):
    return row(300, (label, 100, 260), ("75CTNS=6PLTS", 600, 800),
               ("300PCS", 1000, 1150), ("790.00", 1380, 1500),
               ("640.00", 1680, 1800), ("8.506", 1990, 2100))


def test_แถวที่เขียนว่ายอดรวมถูกยอมรับ():
    r = analyze_packing_list([HEAD, LINE, total_row("TOTAL:")], "PACKING LIST")
    assert r.total_row == 2
    assert [c.printed for c in r.columns] == [300.0, 790.0, 640.0, 8.506]


def test_สถานะบอกชัดว่ายืนยันด้วยเลขคณิตไม่ได้():
    """คนอ่านรายงานต้องรู้ว่าหลักฐานมาจากป้ายชื่อ ไม่ใช่จากการคำนวณ"""
    r = analyze_packing_list([HEAD, LINE, total_row("TOTAL:")], "")
    assert "ยืนยันด้วยเลขคณิตไม่ได้" in r.status
    assert "เขียนว่ายอดรวม" in r.status


def test_แถวที่ไม่ได้เขียนว่ายอดรวมยังถูกปฏิเสธ():
    """สองแถวที่ค่าเท่ากันเฉย ๆ ไม่ใช่หลักฐานว่าแถวหลังเป็นยอดรวม"""
    r = analyze_packing_list([HEAD, LINE, total_row("X")], "")
    assert r.total_row is None
    assert "เชื่อไม่ได้" in r.status


def test_คำว่ายอดรวมภาษาไทยก็ใช้ได้():
    r = analyze_packing_list([HEAD, LINE, total_row("รวม")], "")
    assert r.total_row == 2
