"""ชุดทดสอบตัวแปลงวันที่ — ทุกรูปแบบมาจากเอกสารจริงที่เจอในการทดลอง"""
from datetime import date
import pytest
from customs_checker.dates import parse_date

REF = date(2026, 9, 4)


@pytest.mark.parametrize("raw,expect", [
    ("2026-8-17",        date(2026, 8, 17)),   # FIRSTAR
    ("2026-08-17",       date(2026, 8, 17)),
    ("27 August 2026",   date(2026, 8, 27)),   # SCG
    ("27August 2026",    date(2026, 8, 27)),
    ("24/8/2026",        date(2026, 8, 24)),   # ECO Xiamen
    ("3-Aug-26",         date(2026, 8, 3)),    # Bylimase (ปีสองหลัก ค.ศ.)
    ("03-Aug-26",        date(2026, 8, 3)),
    ("25/07/69",         date(2026, 7, 25)),   # พ.ศ. สองหลัก
    ("30/08/69",         date(2026, 8, 30)),   # พ.ศ. สองหลัก
    ("30/08/2569",       date(2026, 8, 30)),   # พ.ศ. สี่หลัก
    ("3 ส.ค. 69",        date(2026, 8, 3)),    # เดือนไทย
    ("15 กันยายน 2569",  date(2026, 9, 15)),
])
def test_parse(raw, expect):
    got = parse_date(raw, ref=REF)
    assert got.value == expect, f"{raw} -> {got.value} (คาดว่า {expect})"


def test_be_two_digit_not_read_as_2069():
    """69 ต้องเป็น พ.ศ.2569 = ค.ศ.2026 ไม่ใช่ ค.ศ.2069 หรือ 1969"""
    got = parse_date("30/08/69", ref=REF)
    assert got.value.year == 2026
    assert got.era == "BE"


def test_ce_two_digit_stays_ce():
    """26 ต้องเป็น ค.ศ.2026 ไม่ใช่ พ.ศ.2526"""
    got = parse_date("3-Aug-26", ref=REF)
    assert got.value.year == 2026
    assert got.era == "CE"


def test_ambiguous_flagged_not_guessed():
    """10/8/2026 กำกวมจริง ต้องติดธงให้คนดู ไม่ใช่เดาเงียบๆ"""
    got = parse_date("10/8/2026", ref=REF)
    assert got.ambiguous is True
    assert got.value == date(2026, 8, 10)


def test_unambiguous_not_flagged():
    got = parse_date("24/8/2026", ref=REF)
    assert got.ambiguous is False


def test_garbage_returns_none():
    assert parse_date("886-2-2369", ref=REF).value is None
    assert not parse_date("", ref=REF)


@pytest.mark.parametrize("junk", [
    "886-2-2369",      # เบอร์โทร ไต้หวัน (thingnario)
    "86-20-8351",      # เบอร์โทร จีน (SCG)
    "81-6-6633",       # เบอร์โทร ญี่ปุ่น (Descente)
    "MARKS 530",
    "5230000677",      # เลขที่ Invoice
])
def test_junk_never_crashes(junk):
    """ข้อความปนที่ OCR อ่านได้จริง ต้องไม่ทำให้ระบบพัง"""
    got = parse_date(junk, ref=REF)
    assert got.value is None or abs(got.value.year - REF.year) <= 20


@pytest.mark.parametrize("raw,expect", [
    ("AUG.,24TH,2026",   date(2026, 8, 24)),   # FUJIAN — จุด จุลภาค และลำดับที่
    ("AUG.,24TH, 2026",  date(2026, 8, 24)),
    ("DEC.,31ST2026",    date(2026, 12, 31)),
    ("1ST SEP 2026",     date(2026, 9, 1)),
    ("2ND OCT 26",       date(2026, 10, 2)),
    ("3RD NOV 2026",     date(2026, 11, 3)),
])
def test_ordinal_suffix(raw, expect):
    """วันที่มีคำต่อท้ายลำดับที่ 24TH 31ST 2ND 3RD"""
    assert parse_date(raw, ref=REF).value == expect
