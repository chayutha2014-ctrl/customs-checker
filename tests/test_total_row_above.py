"""แถวรวมคือผลบวกของบรรทัดที่อยู่เหนือมัน ไม่ใช่ทุกบรรทัดในหน้า

ค่าที่ใช้มาจาก VORETO/page_001.png ซึ่งมีเลขรุ่นเอกสารอยู่ท้ายกระดาษ
ใต้แถวรวม แล้วถูกจัดเข้าคอลัมน์น้ำหนักสุทธิพอดี
"""
from customs_checker.packing_list import find_total_row, column_totals
from customs_checker.tables import Cell


def col(vals, x=100.0):
    return {ri: Cell(str(v), x - 50, ri * 10.0, x, ri * 10.0 + 8)
            for ri, v in vals.items()}


def test_แถวรวมล่างสุดยังทำงานเหมือนเดิม():
    cols = [col({0: 10, 1: 20, 2: 30}), col({0: 1, 1: 2, 2: 3}, 200.0)]
    assert find_total_row(cols) == (2, [0, 1])


def test_ตัวเลขใต้แถวรวมต้องไม่ถูกนับ():
    """版本号：1.1 ท้ายกระดาษเคยทำให้ผลบวกเกินยอดรวม 1.10"""
    cols = [col({0: 10, 1: 20, 2: 30, 5: 1.1}),
            col({0: 1, 1: 2, 2: 3, 5: 1}, 200.0)]
    assert find_total_row(cols) == (2, [0, 1])


def test_ยอดรวมของคอลัมน์ไม่รวมค่าที่อยู่ใต้แถวรวม():
    cols = [col({0: 10, 1: 20, 2: 30, 5: 1.1}),
            col({0: 1, 1: 2, 2: 3, 5: 1}, 200.0)]
    ri, agree = find_total_row(cols)
    totals = column_totals(cols, ri, agree)
    assert [t.computed for t in totals] == [30.0, 3.0]
    assert all(5 not in t.line_rows for t in totals)


def test_แถวแรกเป็นแถวรวมไม่ได้():
    """ไม่มีบรรทัดเหนือมัน จึงไม่ใช่แถวรวม แม้ค่าจะบังเอิญตรง"""
    cols = [col({0: 0, 1: 5, 2: 5}), col({0: 0, 1: 1, 2: 1}, 200.0)]
    ri, _ = find_total_row(cols)
    assert ri != 0
