"""แยกน้ำหนักสุทธิกับน้ำหนักรวม และชื่อจากแถวหน่วยในหัวตาราง

หน่วย KGS อย่างเดียวแยกสองคอลัมน์น้ำหนักไม่ออก
ต้องอาศัยหลักฐานอื่น เรียงจากแข็งไปอ่อน
  1. ข้อความใต้ตาราง  TOTAL GROSS WEIGHT: 4500.00KGS   จับคู่ด้วยค่า
  2. กฎทางกายภาพ      น้ำหนักรวม > น้ำหนักสุทธิ เสมอ
  3. แถวหน่วยหัวตาราง  KGS | KGS | CBM                  อาศัยตำแหน่ง
"""
from customs_checker.packing_list import analyze_packing_list
from customs_checker.tables import Cell, Row

CHAR_W, LINE_H = 25.0, 30.0
QTY_X, CTNS_X, A_X, B_X = 1400.0, 1600.0, 1900.0, 2200.0


def at(text, right, y):
    num = text
    for i, ch in enumerate(text):
        if ch.isalpha():
            num = text[:i]
            break
    x0 = right - len(num) * CHAR_W
    return Cell(text, x0, y, x0 + len(text) * CHAR_W, y + LINE_H)


def sheet(a_lines, b_lines, a_total, b_total, text="", head=None):
    """สร้างตารางที่ตัวเลขสอดคล้องกันจริง — ผลบวกของบรรทัดต้องเท่ากับยอดรวม"""
    assert abs(sum(a_lines) - float(a_total.rstrip("KGSkgs"))) < 0.01
    assert abs(sum(b_lines) - float(b_total.rstrip("KGSkgs"))) < 0.01
    rows = [] if head is None else [head]
    qty = [1000, 800, 200]
    ctn = [167, 134, 99]
    for i, (q, c, a, b) in enumerate(zip(qty, ctn, a_lines, b_lines)):
        y = 200.0 + i * 100
        rows.append(Row([Cell("A", 100.0, y, 300.0, y + LINE_H),
                         at(f"{q}", QTY_X, y), at(f"{c}", CTNS_X, y),
                         at(f"{a:.2f}", A_X, y), at(f"{b:.2f}", B_X, y)]))
    rows.append(Row([Cell("TOTAL", 100.0, 500.0, 260.0, 530.0),
                     at("2000PCS", QTY_X, 500.0), at("400CTNS", CTNS_X, 500.0),
                     at(a_total, A_X, 500.0), at(b_total, B_X, 500.0)]))
    return analyze_packing_list(rows, text)


NET = [1767.33, 1378.86, 853.81]      # รวม 4000.00
GROSS = [2034.00, 1562.44, 903.56]    # รวม 4500.00


def names(res):
    return {round(c.x): (c.label or c.unit) for c in res.columns}


def test_น้ำหนักรวมมากกว่าสุทธิเสมอ():
    got = names(sheet(NET, GROSS, "4000.00KGS", "4500.00KGS"))
    assert got[A_X] == "NET WEIGHT"
    assert got[B_X] == "GROSS WEIGHT"


def test_บอกที่มาของการแยกไว้ในหมายเหตุ():
    """ผู้ตรวจต้องรู้ว่าชื่อนี้มาจากกฎ ไม่ได้อ่านจากเอกสาร"""
    res = sheet(NET, GROSS, "4000.00KGS", "4500.00KGS")
    assert any("ไม่ได้อ่านจากป้ายชื่อในเอกสาร" in n for n in res.notes)


def test_ค่าเท่ากันต้องไม่เดา():
    same = [2000.00, 1000.00, 1000.00]    # รวม 4000.00 เท่ากัน
    res = sheet(NET, same, "4000.00KGS", "4000.00KGS")
    assert len([c for c in res.columns if c.unit == "KGS"]) == 2
    assert all(c.label not in ("NET WEIGHT", "GROSS WEIGHT") for c in res.columns)
    assert any("แยกสุทธิกับรวมไม่ได้" in n for n in res.notes)


def test_ข้อความใต้ตารางมาก่อนกฎน้ำหนัก():
    """ถ้าเอกสารบอกเองแล้ว ต้องเชื่อเอกสาร ไม่ใช่เชื่อกฎ"""
    res = sheet(NET, GROSS, "4000.00KGS", "4500.00KGS",
                text="TOTAL NET WEIGHT: 4000.00KGS\n"
                     "TOTAL GROSS WEIGHT: 4500.00KGS")
    assert names(res)[A_X] == "NET WEIGHT"
    assert not any("จากกฎที่ว่า" in n for n in res.notes)


def test_แถวหน่วยในหัวตารางตั้งชื่อได้():
    """SKM_450i26090410270 มีแถว KGS | KGS ใต้หัวตาราง ส่วนยอดรวมเป็นตัวเลขเปล่า"""
    head = Row([Cell("KGS", A_X - 40, 50.0, A_X + 40, 80.0),
                Cell("KGS", B_X - 40, 50.0, B_X + 40, 80.0)])
    res = sheet(GROSS, NET, "4500.00", "4000.00", head=head)
    assert any("แถวหน่วยในหัวตาราง" in n for n in res.notes)
    got = names(res)
    assert got[A_X] == "GROSS WEIGHT"     # 4500 มากกว่า จึงเป็นน้ำหนักรวม
    assert got[B_X] == "NET WEIGHT"


def test_แถวที่ปนตัวเลขไม่ถือว่าเป็นแถวหน่วย():
    head = Row([Cell("KGS", A_X - 40, 50.0, A_X + 40, 80.0),
                Cell("12", B_X - 40, 50.0, B_X + 40, 80.0)])
    res = sheet(GROSS, NET, "4500.00", "4000.00", head=head)
    assert not any("แถวหน่วยในหัวตาราง" in n for n in res.notes)
