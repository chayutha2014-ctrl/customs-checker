"""ตัวอ่านใบแจ้งหนี้เบี้ยประกันภัย

ป้ายชื่อในเอกสารชนิดนี้เป็นภาษาไทยและ OCR อ่านไม่ออกเลย
  "Bynyasnn"  "lng/aynuaspan"  "nmi56aufas"
จึงระบุตัวเลขด้วยเลขคณิตล้วน ไม่อ่านป้ายชื่อ

ข้อความทั้งหมดมาจาก OCR ของเอกสารจริง 4 ใบ
อีก 2 ใบกันไว้เป็นชุดตาบอด ผู้พัฒนายังไม่เคยเห็น
"""
import pytest

from customs_checker.insurance_invoice import (analyze_insurance_invoice,
                                               find_policy_no, find_premium_set,
                                               find_wht, numbers_on_page)

DEVES_1 = """THEDEVESINSURANCEPUBLICCOMPANYLIMITED
5:0-2080-1599001:12911575:0-2280-0399 | Tel:0-2080-1599Hotline:1291Fax:0-2280-0399
auavagianlnuu Insured Name &Address | No.
SIAM SANITARYWAREINDUSTRY CO.,LTD.nuj | Bun | Date | 03/09/2026
11 | Bynyasnn | 2,352,984.88
SumInsured
lng/aynuaspan | 630.00
Premium/others
g/ | TypeofPolicy/Others | CMI-an | Stamp Duty | 4.00
00/2026-00773459-CMI | 44.38
PolicyNo. | VAT
Bynyasieeianag | ULe | 27/08/2026 | 678.38
PeriodofInsurance | From | To | Total
INVOICENO.5230000677
0105532055202""".splitlines()

DEVES_2 = """THEDEVESINSURANCEPUBLICCOMPANYLIMITED
THESIAMSANITARYFITTINGSCO.,LTD.1UM00004 | bun | Date | 03/09/2026
NAVANAKORNINDUSTRIALESTATE999/21MOO1MITTRAPHWu | 73,574.65
SumInsured
Premium/others | 500.00
TypeofPolicy/Others | Stamp Duty | 2.00
00/2026-00773910-CMI | rEMILUeRRLU | 35.14
Policy No. | VAT
ULC | 21/08/2026 | 537.14
PeriodofInsurance | From | To | Total
0105530023885""".splitlines()

DEVES_3 = """THE DEVESINSURANCEPUBLIC COMPANY LIMITED
516a50107537002478 | Invoice
SIAM SANITARY WARE INDUSTRY CO., LTD. | jun | Date | 03/09/2026
36/11 n. w! | 257,358.95
Sum Insured
nw 10210 | lmg/nynyaspng | 500.00
Premium / others
ng/regrsucenuuiasn | CMI-nsuuaigaufinnnsainin | 3.00
TypeofPolicy/Others | stamp Duty
00/2026-00773924-CMI | mehyainnn | 35.21
Policy No. | VAT
ULe | 15/08/2026 | 538.21
Period ofInsurance | From | To | Total
25100105532055202""".splitlines()

DEVES_4 = """THEDEVESINSURANCEPUBLIC COMPANY LIMITED
a21516u08an50107537002478 | Tuuaoud
SIAM SANITARY WARE INDUSTRY CO., LTD. | Bun | Date | 03/09/2026
Sum Insured | 4,260,902.10
W10210 | Lng/nymuaspnp | 1,141.00
Premium / others
Jsstnnuansu6i | Type of Policy/ Others | CMI-nuumu | Stamp Duty | 6.00
00/2026-O0773917-CMI | 80.29
Policy No. | VAT
27/08/2026 | rtcsuen | 1,227.29
PeriodofInsurance | From | To | Total
nmi56aufas 0107537002478 | 1,227.29
m u 1% | 11.47
0105532055202 | 1,215.82""".splitlines()


@pytest.mark.parametrize("rows, premium, stamp, vat, total", [
    (DEVES_1, 630.00, 4.00, 44.38, 678.38),
    (DEVES_2, 500.00, 2.00, 35.14, 537.14),
    (DEVES_3, 500.00, 3.00, 35.21, 538.21),
    (DEVES_4, 1141.00, 6.00, 80.29, 1227.29),
])
def test_ระบุตัวเลขได้จากเลขคณิตล้วน(rows, premium, stamp, vat, total):
    r = analyze_insurance_invoice(rows)
    assert r.premium == pytest.approx(premium)
    assert r.stamp == pytest.approx(stamp)
    assert r.vat == pytest.approx(vat)
    assert r.total == pytest.approx(total)


@pytest.mark.parametrize("rows, want", [
    (DEVES_1, 2352984.88), (DEVES_2, 73574.65),
    (DEVES_3, 257358.95), (DEVES_4, 4260902.10),
])
def test_ทุนประกัน(rows, want):
    assert analyze_insurance_invoice(rows).sum_insured == pytest.approx(want)


def test_ทั้งสองสมการต้องจริงพร้อมกัน():
    """VAT ต้องเท่ากับ 7% ของฐาน ไม่ใช่แค่บวกแล้วลงตัว"""
    r = analyze_insurance_invoice(DEVES_1)
    assert r.vat_rate == pytest.approx(0.07)
    assert r.vat == pytest.approx((r.premium + r.stamp) * 0.07, abs=0.02)


def test_ภาษีหักณที่จ่าย():
    """1,227.29 - 11.47 = 1,215.82 โดย 11.47 คือ 1% ของฐานก่อน VAT"""
    r = analyze_insurance_invoice(DEVES_4)
    assert r.wht == pytest.approx(11.47)
    assert r.net_payable == pytest.approx(1215.82)


def test_ใบที่ไม่มีภาษีหักณที่จ่ายต้องไม่แต่งขึ้นมา():
    assert analyze_insurance_invoice(DEVES_1).wht is None


@pytest.mark.parametrize("rows, want", [
    (DEVES_1, "00/2026-00773459-CMI"),
    (DEVES_2, "00/2026-00773910-CMI"),
    (DEVES_4, "00/2026-O0773917-CMI"),      # OCR สลับ 0 เป็น O
])
def test_เลขที่กรมธรรม์(rows, want):
    assert find_policy_no(rows) == want


def test_วันที่ถูกตัดออกจากตัวเลขที่นำมาคำนวณ():
    """03/09/2026 ต้องไม่กลายเป็นเลข 3, 9, 2026"""
    vals = [v for _, v, _ in numbers_on_page(["Date | 03/09/2026 | 678.38"])]
    assert vals == [678.38]


def test_ไม่พบชุดที่เข้าเงื่อนไขต้องบอกว่าอ่านไม่ได้():
    """ห้ามเดา ต้องบอกว่าอ่านไม่ได้"""
    r = analyze_insurance_invoice(["ใบแจ้งหนี้", "ยอดรวม | 1,000.00"])
    assert r.total is None
    assert "อ่านไม่ได้" in r.status


def test_มีหลายชุดที่เข้าเงื่อนไขต้องให้คนดู():
    """ถ้าแยกไม่ออกว่าชุดไหนถูก ต้องไม่เลือกเอง

    สองชุดนี้จริงทั้งคู่ตามสมการ
      100 + 2 + 7.14  = 109.14   และ 7.14  = 7% ของ 102
      200 + 4 + 14.28 = 218.28   และ 14.28 = 7% ของ 204
    """
    vals = [100.0, 2.0, 7.14, 109.14, 200.0, 4.0, 14.28, 218.28]
    uniq = {(p, s, v, t) for p, s, v, t, _ in find_premium_set(vals)}
    assert len(uniq) >= 2

    r = analyze_insurance_invoice([f"x | {v:,.2f}" for v in vals])
    assert r.total is None
    assert r.issues
    assert "ต้องให้คนดู" in r.status


def test_หาภาษีหักณที่จ่ายไม่เจอต้องคืนค่าว่าง():
    assert find_wht([100.0, 200.0], 500.0, 535.0) == (None, None, None)
