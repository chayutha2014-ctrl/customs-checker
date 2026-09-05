# -*- coding: utf-8 -*-
"""ชุดทดสอบการรวมหน้าเป็นเอกสาร + การประเมินสภาพหน้ากระดาษ

ทุกกรณีมาจากสิ่งที่เกิดขึ้นจริงกับตัวอย่าง 5 ชุด
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from customs_checker.docgroup import (identity, page_marker, same_identity, group_pages,
                      page_condition)


def pg(n, code, text, name=None):
    return {"page": n, "code": code, "name_th": name or code, "text": text}


# ---------- ดึงเลขประจำตัวเอกสาร ----------
def test_เลขเอกสารต้องไม่ถูกตัดที่ขีดกลาง():
    """doctype.normalize() แปลงขีดเป็นช่องว่าง ถ้าเอามาใช้ตรงนี้จะได้ '26SYCI' แทน"""
    v, st = identity("invoice", "INVOICE NO.: 26SYCI-RM026   DATE: 16/Jul/26")
    assert (v, st) == ("26SYCI-RM026", "ยืนยัน")
    v, st = identity("marine_policy", "Policy No. 00/2026-O0771839-CMI")
    assert v == "00/2026-O0771839-CMI"


def test_เลขเอกสารต้องไม่ข้ามบรรทัด():
    """\\s ใน regex ข้ามบรรทัดได้ ทำให้คว้าข้อความบรรทัดถัดไปมาเป็นเลขเอกสาร"""
    v, st = identity("invoice", "INVOICE NO.:\n0105540024655")
    assert v is None or st == "ไม่ชัด", (v, st)


def test_ocr_รวมคอลัมน์_ต้องไม่เชื่อเลขที่ได้():
    """OCR อ่านที่อยู่กับเลข invoice มาต่อกันเป็นบรรทัดเดียว
    เลขที่ได้อาจถูกตัดหัวหรือต่อท้ายด้วยเลขอื่น ห้ามรายงานว่าอ่านได้"""
    line = "MUANG, BANGKOK 10210 THAILAND: INV NO.: 004009112224"
    v, st = identity("invoice", line)
    assert st == "ไม่ชัด", (v, st)


def test_เลขที่เป็นตัวเลขล้วนยาวๆ_ถือว่าไม่ชัด():
    v, st = identity("invoice", "INV NO.: 01055400246551")
    assert st == "ไม่ชัด"


def test_ไม่พบเลข():
    assert identity("invoice", "COMMERCIAL INVOICE  TOTAL 100.00")[1] == "ไม่พบ"


# ---------- เทียบเลขแบบทน OCR ----------
def test_ocr_แทรกตัวอักษร_ถือว่าฉบับเดียวกัน():
    """OCR อ่าน E26MA2XUF8X60147 เป็น E26MA2XUFS8X60147 (แทรก S ความยาวเปลี่ยน)"""
    v, d = same_identity("E26MA2XUF8X60147", "E26MA2XUFS8X60147")
    assert v == "น่าจะเดียวกัน" and d == 1


def test_เลขที่ออกเรียงกัน_ต้องแยกไว้ก่อน():
    """ชุด 1 กับชุด 2 ใช้เลข ...60147 และ ...60148 ต่างกันตัวเดียวแต่ยาวเท่ากัน
    หน้าตาเหมือน OCR คลาดทุกอย่าง — เมื่อแยกไม่ออก ต้องเลือกทางที่ไม่ทำให้เอกสารหาย"""
    v, d = same_identity("E26MA2XUF8X60147", "E26MA2XUF8X60148")
    assert v == "ต้องให้คนดู" and d == 1


def test_เลขต่างกันมาก_ต่างฉบับแน่นอน():
    v, _ = same_identity("MBCIC2606005", "26SYCI-RM026")
    assert v == "ต่างกัน"


# ---------- ตัวบอกลำดับแผ่น ----------
def test_page_marker():
    assert page_marker("ใบต่อแผ่นที่ 2/2") == (2, 2, "ชัดเจน")
    assert page_marker("Page 2 of 3") == (2, 3, "ชัดเจน")
    assert page_marker("1 of  1") == (1, 1, "เปล่า")
    assert page_marker("ไม่มีอะไร") is None


def test_ตัวเลขลอยในบรรทัดยาว_ต้องไม่นับเป็นเลขหน้า():
    """เคสจริง: Form E 3 แผ่นถูกรายงานว่า 'พิมพ์ว่ามี 8 แผ่น'
    เพราะรูปแบบ '<เลข> OF <เลข>' ไปคว้าตัวเลขกลางเนื้อหามา"""
    long_line = ("THE GOODS DESCRIBED HEREIN CONSIST OF 8 PACKAGES OF "
                 "STAINLESS STEEL FITTINGS 300 OF 8 GRADE MATERIAL")
    assert page_marker(long_line) is None


def test_เลขแผ่นเกินจริง_ต้องไม่รับ():
    assert page_marker("1 of 300") is None


def test_ตัวบอกแผ่นเสมอกัน_ต้องไม่ฟันธง():
    from customs_checker.docgroup import expected_sheets
    n, why = expected_sheets([(1, 3, "เปล่า"), (2, 8, "เปล่า")])
    assert n is None and "ขัดกัน" in why


def test_ocr_อ่านเลขแผ่นผิดหนึ่งใบ_ใช้เสียงข้างมาก():
    """เคสจริง SKM_450i26090315181: Form E 3 แผ่น OCR อ่านได้ 1/8, 2/3, 3/3
    เลข 8 คือ 3 ที่อ่านผิด — เสียงข้างมากต้องชนะ"""
    from customs_checker.docgroup import expected_sheets
    n, why = expected_sheets([(1, 8, "เปล่า"), (2, 3, "เปล่า"), (3, 3, "เปล่า")])
    assert n == 3 and "เสียงข้างมาก" in why


def test_เอกสารขาดจริง_ต้องยังเตือน():
    """ถ้าทุกแผ่นบอกตรงกันว่ามี 8 แผ่น แต่ได้มา 3 ต้องเตือนว่าไม่ครบ"""
    from customs_checker.docgroup import expected_sheets
    n, why = expected_sheets([(1, 8, "เปล่า"), (2, 8, "เปล่า"), (3, 8, "เปล่า")])
    assert n == 8 and why == ""


def test_ตัวบอกแบบชัดเจนชนะแบบเปล่า():
    from customs_checker.docgroup import expected_sheets
    n, why = expected_sheets([(1, 3, "ชัดเจน"), (1, 8, "เปล่า"), (2, 3, "ชัดเจน")])
    assert n == 3 and why == ""


# ---------- รวมหน้าเป็นเอกสาร ----------
FE = "Reference No. E26MA2XUF8X60147  CERTIFICATE OF ORIGIN FORM E"

def test_form_e_สามแผ่น_ต้องรวมเป็นฉบับเดียว():
    """Form E ของ ACFTA พิมพ์หัวเรื่องซ้ำทุกแผ่น
    จะใช้ 'มีหัวเรื่อง = ขึ้นฉบับใหม่' ไม่ได้ ต้องใช้เลขเอกสารเป็นตัวตัด"""
    docs = group_pages([pg(1, "form_co", FE), pg(2, "form_co", FE), pg(3, "form_co", FE)])
    assert len(docs) == 1 and docs[0].pages == [1, 2, 3] and docs[0].status == "ยืนยัน"


def test_form_e_ที่ocr_คลาด_ยังรวมเป็นฉบับเดียว_แต่ต้องเตือน():
    bad = FE.replace("E26MA2XUF8X60147", "E26MA2XUFS8X60147")
    docs = group_pages([pg(1, "form_co", bad), pg(2, "form_co", FE), pg(3, "form_co", FE)])
    assert len(docs) == 1 and docs[0].pages == [1, 2, 3]
    assert docs[0].status == "ตรวจสอบ" and "OCR คลาด" in docs[0].note


def test_เอกสารสองฉบับติดกัน_ต้องแยก():
    a = "Reference No. E26MA2XUF8X60147 FORM E"
    b = "Reference No. E26MA2XUF8X60148 FORM E"
    docs = group_pages([pg(1, "form_co", a), pg(2, "form_co", b)])
    assert len(docs) == 2
    assert all(d.status == "ตรวจสอบ" for d in docs), "แยกแบบไม่แน่ใจ ต้องติดธงทั้งสองฉบับ"


def test_ชนิดต่างกัน_ต้องแยกเสมอ():
    docs = group_pages([pg(1, "invoice", "INVOICE NO.: A-1"),
                        pg(2, "packing_list", "INVOICE NO.: A-1")])
    assert len(docs) == 2


def test_หน้าที่จำแนกไม่ได้_ต้องไม่ถูกกลืนเข้าฉบับก่อนหน้า():
    docs = group_pages([pg(1, "invoice", "INVOICE NO.: A-1"),
                        pg(2, "unknown", "อะไรก็ไม่รู้"),
                        pg(3, "invoice", "INVOICE NO.: A-1")])
    assert len(docs) == 3 and docs[1].status == "ตรวจสอบ"


def test_form_e_สามแผ่นที่มีเลขลอยปน_ต้องไม่ฟ้องว่าขาด():
    """ยืนยันด้วยงานจริง SKM_450i26090315181: Form E 3 แผ่น ไม่ใช่ 8 แผ่น"""
    body = ("Reference No. E26MA2XUF8X60147 FORM E\n"
            "SEVEN HUNDRED AND EIGHTY CARTONS OF STAINLESS FITTINGS 300 OF 8 GRADE\n")
    docs = group_pages([pg(i, "form_co", body) for i in (1, 2, 3)])
    assert len(docs) == 1 and docs[0].pages == [1, 2, 3]
    assert "แต่ได้มา" not in docs[0].note, docs[0].note


def test_ตรวจความครบของแผ่น_ตอนจบเท่านั้น():
    """ถ้าเช็คระหว่างทางจะฟ้อง 'อาจไม่ครบ' ที่แผ่น 1 และ 2 ทั้งที่สุดท้ายครบ"""
    p = [pg(i, "import_declaration", f"PPFE000015331 ใบต่อแผ่นที่ {i}/3") for i in (1, 2, 3)]
    docs = group_pages(p)
    assert len(docs) == 1 and docs[0].status == "ยืนยัน", docs[0].note
    assert "3 แผ่น" in docs[0].note and "แต่ได้มา" not in docs[0].note


def test_แผ่นหาย_ต้องเตือน():
    p = [pg(1, "import_declaration", "PPFE000015331 ใบต่อแผ่นที่ 1/3")]
    docs = group_pages(p)
    assert docs[0].status == "ตรวจสอบ" and "แต่ได้มา 1 แผ่น" in docs[0].note


# ---------- สภาพหน้ากระดาษ ----------
def test_หน้าสะอาด():
    r = page_condition("COMMERCIAL INVOICE TOTAL 100", color_pct=0.00)
    assert r["สภาพหน้า"] == "สะอาด"


def test_หน้ามีตราประทับ():
    r = page_condition("CERTIFICATE OF ORIGIN FORM E", color_pct=1.12)
    assert r["สภาพหน้า"] == "มีตรา/ลายเซ็นทับ" and r["ร่าง/ตัวจริง"] == "ตัวจริง"


def test_โลโก้สี_ต้องไม่ถูกนับเป็นตราประทับ():
    r = page_condition("OCEAN BILL OF LADING", color_pct=0.13)
    assert r["สภาพหน้า"] == "มีสีเล็กน้อย (โลโก้?)" and r["ร่าง/ตัวจริง"] == "ไม่ทราบ"


def test_tba_ต้องเทียบทั้งคำ():
    """'TBA' ที่ฝังอยู่กลางคำอื่นเคยทำให้ใบแจ้งหนี้ประกันของชุดตัวจริง
    ถูกตัดสินเป็น 'ร่าง' ผิด ๆ"""
    assert page_condition("CONTAINER&SEAL NO.: TBA", 0.02)["ร่าง/ตัวจริง"] == "ร่าง"
    assert page_condition("POLICY NO. 00/2026-OTBAX", 0.02)["ร่าง/ตัวจริง"] == "ไม่ทราบ"


def test_มีทั้ง_draft_และตรา_ต้องบอกว่าขัดแย้ง():
    r = page_condition("DRAFT ใบขนสินค้าขาเข้า", color_pct=4.42)
    assert r["ร่าง/ตัวจริง"] == "ขัดแย้ง"


def test_ไม่ได้วัดสี_ต้องไม่เดา():
    r = page_condition("OCEAN BILL OF LADING TELEX RELEASED", color_pct=None)
    assert r["สภาพหน้า"] == "ไม่ได้วัด" and r["ร่าง/ตัวจริง"] == "ไม่ทราบ"
