"""ตัวอ่าน Form E

ข้อความมาจากเอกสารจริง กันไว้ 2 ฉบับเป็นชุดตาบอด

Form E มีตัวเลขให้ตรวจน้อย แต่มีสิ่งที่ชดเชย คือจำนวนหีบห่อเขียนทั้งตัวหนังสือ
และตัวเลขคู่กัน ซึ่งเป็นการยืนยันแบบเดียวกับจำนวนเงินในกรมธรรม์
"""
import pytest

from customs_checker.form_e import (analyze_form_e, combine_sheets,
                                    find_criteria, find_hs_codes,
                                    find_page_marker, find_reference,
                                    find_word_numbers, group_sheets,
                                    number_to_words, words_are_tail_of)

SHEET1 = [
    "Original",
    "1. Products consigned from (Exporter's business name,address, | "
    "Reference No. | E260901280070068",
    "1 | COTTO | STAINLESS WATER INLET HOSE 16 | PE | 3000PIECES",
    "HS C0DE:4009.22 | AUG.03, 202",
    "2 | STAINLESS WATER INLET HOSE 18 | 2000PIECES",
    "HS C0DE:4009.22",
    "3 | STAINLESS WATER INLET HOSE | PE | 2000PIECES",
    "TOTAL:FIVE(5)PALLETS ONL",
]

SHEET2 = [
    "Original | (PAGE 2 0F 3)",
    "1. Products consigned from | Reference No. E267516088931285",
    '6 | SIX HUNDRED AND SIXTY SEVEN (667)CARTONS | "PSR" | 8000PIECES',
    "OFC9682**T/TSET | CNY:196000.00",
    "HS C0DE:8481.80",
    "6 | ONE HUNDRED AND NINE （109)CARTONS OF C93 | PSR | 1300PIECES",
    "TOTAL: SEVEN HUNDRED AND SEVENTY SIX (776)CARTONS",
]


def test_เลขที่อ้างอิงถูกรูปแบบ():
    assert find_reference(SHEET1)[0] == "E260901280070068"


def test_OCR_อ่าน_E_เป็น_F_ต้องเลือกตัวที่ถูกรูปแบบ():
    """IMP26002010 สามแผ่นเป็นฉบับเดียวกัน แต่แผ่น 2 อ่านได้ F"""
    pick, all_ = find_reference(["Reference No.F267910376420077",
                                 "Reference No.E267910376420077"])
    assert pick == "E267910376420077"
    assert "F267910376420077" in all_


def test_พิกัดศุลกากรแม้_OCR_อ่าน_CODE_เป็น_C0DE():
    """OCR อ่าน HS CODE เป็น HS C0DE ด้วยเลขศูนย์ ทุกแผ่น"""
    assert find_hs_codes(SHEET1) == ["4009.22"]
    assert find_hs_codes(SHEET2) == ["8481.80"]


@pytest.mark.parametrize("rows, want", [
    (SHEET1, ["PE"]),
    (SHEET2, ["PSR"]),          # ในเอกสารเขียนในเครื่องหมายคำพูด
])
def test_เกณฑ์ถิ่นกำเนิดในชุดที่เป็นไปได้(rows, want):
    assert find_criteria(rows)[0] == want


def test_เลขลำดับแผ่น():
    assert find_page_marker(SHEET2) == (2, 3)
    assert find_page_marker(SHEET1) == (None, None)


@pytest.mark.parametrize("text, digits, words", [
    ("SIX HUNDRED AND SIXTY SEVEN (667)CARTONS", 667.0, 667.0),
    ("ONE HUNDRED AND NINE （109)CARTONS OF C93", 109.0, 109.0),
    ("TOTAL:FIVE(5)PALLETS ONL", 5.0, 5.0),
])
def test_ตัวหนังสือกำกับจำนวนหีบห่อ(text, digits, words):
    got = find_word_numbers([text])
    assert got
    _, d, _, v, _raw = got[0]
    assert d == pytest.approx(digits)
    assert v == pytest.approx(words)


def test_ผลบวกหีบห่อเท่ากับยอดรวม():
    r = analyze_form_e(SHEET2)
    assert any("ผลบวกหีบห่อรายรายการ" in c and "= ยอดรวม" in c for c in r.checks)
    assert not r.issues


def test_ผลบวกไม่ตรงต้องฟ้อง():
    rows = list(SHEET2)
    rows[-1] = "TOTAL: SEVEN HUNDRED AND SEVENTY SEVEN (777)CARTONS"
    r = analyze_form_e(rows)
    assert any("ไม่เท่ากับยอดรวม" in i for i in r.issues)


def test_ตัวหนังสือไม่ตรงกับตัวเลขต้องฟ้อง():
    r = analyze_form_e(["TOTAL: SEVEN HUNDRED (776)CARTONS"])
    assert any("ไม่ตรงกัน" in i for i in r.issues)


# ---------- OCR อ่านเลขศูนย์เป็นตัวอักษร O ----------
# ที่มา: IMP26002010-DIMPORT DOCS/page_012.png

@pytest.mark.parametrize("text, want", [
    ('10 ONE HUNDRED (10O)CARTONS OF CERAMIC "PE" 100PIECES', 100.0),
    ('11 ONEHUNDRED AND THIRTY （13O)CARTONS "PE" 130PIECES', 130.0),
])
def test_ตัวหนังสือแก้เลขศูนย์ที่อ่านเป็น_O(text, want):
    """เดิมทิ้งทั้งบรรทัดเพราะ 10O ไม่ใช่ตัวเลข ตัวหนังสือยืนยันว่าเป็น 100"""
    got = find_word_numbers([text])
    assert got
    _, d, _, v, raw = got[0]
    assert d == pytest.approx(want)
    assert v == pytest.approx(want)
    assert "O" in raw.upper()


def test_บอกไว้ว่าแก้เลขศูนย์เพราะอะไร():
    r = analyze_form_e(['10 ONE HUNDRED (10O)CARTONS OF CERAMIC "PE" 100PIECES'])
    assert any("แทนศูนย์" in n for n in r.notes)


# ---------- ตัวหนังสือถูก OCR ตัดหัว ----------
# ที่มา: HUNDREDANDTEN(1710)CARTONSONLY — ส่วนหน้า ONE THOUSAND SEVEN หายไป

def test_ตัวหนังสือถูกตัดหัวไม่ใช่เอกสารขัดกัน():
    r = analyze_form_e(["HUNDREDANDTEN(1710)CARTONSONLY"])
    assert not r.issues
    assert any("ไม่ครบ" in n for n in r.notes)


def test_ตัดหัวแล้วยังต้องสอดคล้องกับตัวเลขจริง():
    """ONE THOUSAND SEVEN HUNDRED AND TEN ลงท้ายด้วย HUNDRED AND TEN"""
    assert words_are_tail_of("HUNDREDANDTEN", 1710)
    assert words_are_tail_of("TOTAL HUNDREDANDTEN", 1710)
    assert not words_are_tail_of("HUNDREDANDTEN", 1720)


def test_แปลงจำนวนเป็นคำ():
    assert number_to_words(1710) == "ONE THOUSAND SEVEN HUNDRED AND TEN"
    assert number_to_words(100) == "ONE HUNDRED"
    assert number_to_words(130) == "ONE HUNDRED AND THIRTY"


def test_หน่วยยอดรวมต่างจากรายการต้องบอกว่าเทียบไม่ได้():
    """SHEET1 ยอดรวมเป็น PALLETS แต่รายการเป็น PIECES"""
    r = analyze_form_e(SHEET1)
    assert any("เทียบผลบวกไม่ได้" in n for n in r.notes)


def test_รวมแผ่นแล้วเลือกเลขที่อ้างอิงด้วยเสียงข้างมาก():
    a = analyze_form_e(["Reference No.E267910376420077", "Original (PAGE 1 0F 3)"])
    b = analyze_form_e(["Reference No.F267910376420077", "Original (PAGE 2 0F 3)"])
    c = analyze_form_e(["Reference No.E267910376420077", "Original (PAGE 3 0F 3)"])
    out = combine_sheets([a, b, c])
    assert out["reference_no"] == "E267910376420077"
    assert any("ครบทั้ง 3 แผ่น" in x for x in out["checks"])
    assert any("ไม่ตรงกันระหว่างแผ่น" in x for x in out["notes"])


def test_แผ่นขาดต้องฟ้อง():
    a = analyze_form_e(["Reference No.E267910376420077", "Original (PAGE 1 0F 3)"])
    c = analyze_form_e(["Reference No.E267910376420077", "Original (PAGE 3 0F 3)"])
    out = combine_sheets([a, c])
    assert any("แต่อ่านได้แผ่น" in i for i in out["issues"])



def test_รวมแผ่นก่อนแล้วค่อยเลือกเลขที่():
    """IMP26002010 สามแผ่น แผ่น 2 อ่านได้ F เคยแตกเป็นสองฉบับแล้วฟ้องว่าแผ่นขาดทั้งคู่"""
    a = analyze_form_e(["Reference No.E267910376420077", "Original (PAGE 1 0F 3)"])
    b = analyze_form_e(["Reference No.F267910376420077", "Original (PAGE 2 0F 3)"])
    c = analyze_form_e(["Reference No.E267910376420077", "Original (PAGE 3 0F 3)"])
    groups = group_sheets([("p10", a), ("p11", b), ("p12", c)])
    assert len(groups) == 1
    out = combine_sheets([r for _, r in groups[0]])
    assert out["reference_no"] == "E267910376420077"
    assert not out["issues"]


def test_เลขที่ต่างกันมากต้องเป็นคนละฉบับ():
    a = analyze_form_e(["Reference No.E267910376420077"])
    b = analyze_form_e(["Reference No.E260901280070068"])
    assert len(group_sheets([("p1", a), ("p2", b)])) == 2
