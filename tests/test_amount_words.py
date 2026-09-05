"""แปลงจำนวนเงินที่เขียนเป็นตัวหนังสือกลับเป็นตัวเลข

ใช้ยืนยันตัวเลขที่ OCR อ่านมา ถ้าอ่านผิดตัวหนังสือจะไม่ตรง
ข้อความทั้งหมดมาจากกรมธรรม์จริง รวมทั้งใบที่ OCR เชื่อมคำติดกันหมด
"""
import pytest

from customs_checker.amount_words import words_to_number


@pytest.mark.parametrize("text, want", [
    ("(CNY(CHINA):FourHundredandSeventy-FiveThousandNineHundred"
     "andSeventy-FiveAnd50/100)", 475975.50),
    ("(USDOLLARS:TwoThousandOneHundredandNinety-SevenAnd80/100)", 2197.80),
    ("(CNY (CHINA) : Fifty-One Thousand Five Hundred and Thirteen Only)", 51513.00),
    ("(CNY (CHINA) : Eight Hundred and Fifty-Two Thousand Eight Hundred "
     "and Sixty-Two And 71/100)", 852862.71),
])
def test_ข้อความจากกรมธรรม์จริง(text, want):
    assert words_to_number(text) == pytest.approx(want)


def test_คำที่เชื่อมติดกันถูกแยกออก():
    """OCR ในบางใบเชื่อมคำติดกันหมด ต้องแยกได้"""
    assert words_to_number("FourHundredandSeventy-Five") == pytest.approx(475)


@pytest.mark.parametrize("text, want", [
    ("One Million Two Hundred Thousand Only", 1200000.0),
    ("Ninety-Nine And 99/100", 99.99),
    ("Ten Only", 10.0),
])
def test_รูปแบบอื่นที่ควรอ่านได้(text, want):
    assert words_to_number(text) == pytest.approx(want)


@pytest.mark.parametrize("text", [
    "CNY : Somethingelse Only",      # มีคำที่ไม่รู้จัก
    "CNY : Fifty-Qne Thousand",      # OCR อ่าน O เป็น Q
    "(CNY: 51,513.00)",              # เป็นตัวเลข ไม่ใช่ตัวหนังสือ
    "",
    None,
])
def test_ไม่แน่ใจต้องคืนค่าว่าง_ไม่เดา(text):
    """หน้าที่ของฟังก์ชันนี้คือยืนยัน การเดาผิดอันตรายกว่าการบอกว่าอ่านไม่ได้"""
    assert words_to_number(text) is None


# ---------- บอกว่าติดที่คำไหน ----------
# ผู้ตรวจต้องรู้ว่าต้องไปดูอะไร ไม่ใช่แค่รู้ว่าอ่านไม่ได้

def test_บอกคำที่อ่านไม่ออก():
    from customs_checker.amount_words import unknown_words
    bad = unknown_words("(CNY (CHINA) : Ffty-One Thousand Fve Hundred and Thirteen Only)")
    assert bad == ["FFTY", "FVE"]


def test_ข้อความที่อ่านออกหมดต้องไม่มีคำติด():
    from customs_checker.amount_words import unknown_words
    assert unknown_words("(CNY (CHINA) : Fifty-One Thousand Five Hundred and Thirteen Only)") == []


@pytest.mark.parametrize("text, want", [
    ("(CNY : Fifty-One Thousand Only)", True),
    ("(USDOLLARS:TwoThousandOneHundredandNinety-SevenAnd80/100)", True),
    ("MARINE CARGO POLICY", False),
    ("INSTITUTE CARGO CLAUSES (A) 1/1/09", False),
])
def test_แยกบรรทัดที่ตั้งใจเขียนจำนวนเงินตัวหนังสือ(text, want):
    from customs_checker.amount_words import looks_like_amount_words
    assert looks_like_amount_words(text) is want
