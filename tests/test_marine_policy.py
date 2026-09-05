"""ตัวอ่านกรมธรรม์ประกันภัยขนส่งสินค้าทางทะเล

เอกสารชนิดนี้มีหลักฐานยืนยันตัวเองครบที่สุด บรรทัดเดียวให้การตรวจสามชั้น
ข้อความมาจากเอกสารจริง 4 ใบ อีก 3 ใบกันไว้เป็นชุดตาบอด
"""
import pytest

from customs_checker.marine_policy import (analyze_marine_policy, find_packages,
                                           find_voyage, read_labels)

P1 = """SCHEDULE | PolicyNo.00/2026-00773459-CMI
NameofAsSured:SIAMSANITARYWAREINDUSTRYCO.,LTD.
VeSSeI:IRENESRAINBOWV.26034S | Sailingonorabout:27/08/2026
Voyage: | AtandfromXIAMEN,CHINATOBANGKOKTHENCETOINSURED'SWAREHOUSE
AmountInsuredhereunder:Equalto（432,705.00+10.00%)CNY475,975.50@4.9435
(CNY(CHINA):FourHundredandSeventy-FiveThousandNineHundredandSeventy-FiveAnd50/100)
1,772 CARTONS （26,110.00 KGS.）(1X40'HQ,1X20'GP)
INVOICE NO.SCG INTERNATIONAL CHINA (GUANGZHOU) CO.,LTD
5230000677
JOBNO.IMP26002010""".splitlines()

P2 = """SCHEDULE | PolicyNo.00/2026-00773910-CMI
NameofAsSured:THESIAMSANITARYFITTINGSCO.,LTD.
VeSSel:JARUBHUMV.176S | Sailingonorabout:21/08/2026
Voyage: | AtandfromNINGBO,CHINATOBANGKOKTHENCETOINSURED'SWAREHOUSE
AmountInsuredhereunder:Equalto（1,998.00+10.00%)UsD2,197.80@33.4765
(USDOLLARS:TwoThousandOneHundredandNinety-SevenAnd80/100)
10 CARTONS (81.00 KGS.）(40'HQ)
INVOICE NO.NINGBO WANHAI CARTRIDGE TECHNOLOGY CO.,LTD
WHSCG2608-6844-AUG""".splitlines()

P3 = """SCHEDULE | Policy No. 00/2026-00773924-CMI
Name of Assured : SIAM SANITARY WARE INDUSTRY CO., LTD.
VeSSeI:KHUNABHUMV.085S | Sailing on or about : 15/08/2026
Voyage :At and from NINGBO, CHINA TO BANGKOK THENCE TO INSURED'S WAREHOUSE
AmountInsuredhereunder:Equalto(46,830.00+10.00%)CNY51,513.00@4.9960
(CNY (CHINA) : Fifty-One Thousand Five Hundred and Thirteen Only)
5 PALLETS (1,120.00 KGS)
INVOICE NO.FOSHAN BYLIMASE TRADE CO.,LTD.
WLKL-CTSW-2605B&06&7B""".splitlines()

P4 = """MARINE CARGO POLICY | Policy No. 00/2026-00773917-CMI
Name of AsSured : SIAM SANITARY WARE INDUSTRY CO., LTD.
VeSSeI:IRENESRAINBOWV.26034S | Sailing on or about: 27/08/2026
Amount Insured hereunder:Equal to(775,329.74+10.00%) CNY 852,862.71@4.9960
(CNY (CHINA) : Eight Hundred and Fifty-Two Thousand Eight Hundred and Sixty-Two And 71/100)
2,006 CARTONS (20,364.16 KGS.)(3X40'HQ)
INVOICE NO.ECO (XIAMEN)TECHNOLOGY INC
20260822SSI""".splitlines()

ALL = [P1, P2, P3, P4]


@pytest.mark.parametrize("rows, base, amount, rate", [
    (P1, 432705.00, 475975.50, 4.9435),
    (P2, 1998.00, 2197.80, 33.4765),
    (P3, 46830.00, 51513.00, 4.9960),
    (P4, 775329.74, 852862.71, 4.9960),
])
def test_ราคาสินค้าบวกกำไรสมมติสิบเปอร์เซ็นต์(rows, base, amount, rate):
    r = analyze_marine_policy(rows)
    assert r.goods_value == pytest.approx(base)
    assert r.uplift_pct == pytest.approx(10.0)
    assert r.amount_insured == pytest.approx(amount)
    assert r.exchange_rate == pytest.approx(rate)
    assert any("ลงตัว" in c for c in r.checks)


@pytest.mark.parametrize("rows", ALL)
def test_ตัวหนังสือกำกับยืนยันตัวเลขได้(rows):
    """หลักฐานอิสระ ถ้า OCR อ่านตัวเลขผิด ตัวหนังสือจะไม่ตรง"""
    r = analyze_marine_policy(rows)
    assert r.amount_in_words == pytest.approx(r.amount_insured)
    assert any("ตัวหนังสือ" in c for c in r.checks)


@pytest.mark.parametrize("rows, thb", [
    (P1, 2352984.88), (P2, 73574.65), (P3, 257358.95), (P4, 4260902.10),
])
def test_ทุนประกันคิดเป็นบาทตรงกับใบแจ้งหนี้(rows, thb):
    """ค่านี้ต้องเท่ากับทุนประกันที่อ่านได้จากใบแจ้งหนี้เบี้ยประกันในไฟล์เดียวกัน"""
    assert analyze_marine_policy(rows).thb_value == pytest.approx(thb)


@pytest.mark.parametrize("rows", ALL)
def test_ไม่มีข้อขัดแย้งในเอกสารจริง(rows):
    assert not analyze_marine_policy(rows).issues


def test_ตัวเลขไม่ตรงกับตัวหนังสือต้องฟ้อง():
    rows = list(P3)
    rows[4] = ("AmountInsuredhereunder:Equalto(46,830.00+10.00%)"
               "CNY51,513.00@4.9960")
    rows[5] = "(CNY (CHINA) : Fifty-One Thousand Five Hundred and Fourteen Only)"
    r = analyze_marine_policy(rows)
    assert any("ไม่ตรงกัน" in i for i in r.issues)


def test_บวกสิบเปอร์เซ็นต์ไม่ลงตัวต้องฟ้อง():
    rows = list(P3)
    rows[4] = ("AmountInsuredhereunder:Equalto(46,830.00+10.00%)"
               "CNY99,999.00@4.9960")
    r = analyze_marine_policy(rows)
    assert any("ควรได้" in i for i in r.issues)


@pytest.mark.parametrize("rows, want", [
    (P1, "IRENESRAINBOWV.26034S"),      # OCR เขียน VeSSeI ด้วยตัว I
    (P2, "JARUBHUMV.176S"),
    (P3, "KHUNABHUMV.085S"),
])
def test_ชื่อเรือแม้ป้ายจะสะกดเพี้ยน(rows, want):
    assert read_labels(rows).get("vessel") == want


@pytest.mark.parametrize("rows, n, unit, kg", [
    (P1, 1772, "CARTONS", 26110.00),
    (P2, 10, "CARTONS", 81.00),
    (P3, 5, "PALLETS", 1120.00),
    (P4, 2006, "CARTONS", 20364.16),
])
def test_จำนวนหีบห่อและน้ำหนัก(rows, n, unit, kg):
    got_n, got_u, got_kg = find_packages(rows)
    assert (got_n, got_u) == (n, unit)
    assert got_kg == pytest.approx(kg)


def test_ต้นทางปลายทาง():
    assert find_voyage(P1) == ("XIAMEN,CHINA", "BANGKOK")


def test_ไม่พบบรรทัดทุนประกันต้องบอกว่าอ่านไม่ได้():
    r = analyze_marine_policy(["MARINE CARGO POLICY", "SCHEDULE"])
    assert r.amount_insured is None
    assert "อ่านไม่ได้" in r.status


# ---------- ใช้ตัวหนังสือนำทางหาตัวเลข ----------
# ใช้เมื่อรูปแบบบรรทัดไม่ตรงกับที่รู้จัก ซึ่งเกิดได้เพราะผู้รับประกันแต่ละราย
# และแต่ละงานเขียนไม่เหมือนกัน ตัวหนังสือระบุจำนวนไว้ชัดอยู่แล้ว

UNKNOWN_FORM = [
    "MARINE CARGO POLICY",
    "Sum insured : THB 1,234,567.89",
    "(THB : One Million Two Hundred and Thirty-Four Thousand "
    "Five Hundred and Sixty-Seven And 89/100)",
]


def test_รูปแบบที่ไม่รู้จักยังอ่านได้ด้วยตัวหนังสือ():
    r = analyze_marine_policy(UNKNOWN_FORM)
    assert r.amount_insured == pytest.approx(1234567.89)
    assert any("หาด้วยตัวหนังสือ" in c for c in r.checks)


def test_บอกด้วยว่าหาด้วยวิธีสำรอง():
    """ผู้ตรวจต้องรู้ว่าหลักฐานมาจากทางไหน"""
    r = analyze_marine_policy(UNKNOWN_FORM)
    assert any("รูปแบบบรรทัดไม่ตรงกับที่รู้จัก" in c for c in r.checks)


def test_ไม่มีอัตราแลกเปลี่ยนต้องบอกว่าเทียบใบแจ้งหนี้ไม่ได้():
    r = analyze_marine_policy(UNKNOWN_FORM)
    assert r.thb_value is None
    assert any("เทียบกับใบแจ้งหนี้ไม่ได้" in n for n in r.notes)


def test_ตัวหนังสือไม่ตรงกับตัวเลขต้องฟ้องว่าขัดแย้ง():
    """มีตัวเลขอยู่แต่ไม่ตรงกับตัวหนังสือ = ความขัดแย้งในเอกสาร
    ไม่ใช่เหตุให้เชื่อตัวหนังสือ และไม่ใช่แค่ 'อ่านไม่ได้'"""
    rows = ["MARINE CARGO POLICY", "Sum insured : THB 999.00",
            "(THB : One Million Only)"]
    r = analyze_marine_policy(rows)
    assert r.amount_insured is None
    assert any("ไม่ตรงกัน" in i for i in r.issues)


# ---------- รูปแบบของผู้รับประกันรายอื่น ----------
# ที่มา: SKM_450i26090410270/page_008.png (Tokio Marine) และ
#        Scan2026-09-03_182617/page_005.png (Deves ที่บรรทัดตัวเลขหายไป)

TOKIO = [
    "MARINECARGOPOLICY",
    "The others of the same tenor and date unpaid | Policy No...DR-90-69/000258",
    "NAME OFASSURED: | BELMEXTHAI CO.,LTD.",
    "VESSEL : | PIYA BHUM V.094S | SAILING ON OR ABOUT: 30/08/2026",
    "VOYAGE:AtandfromSHENZHEN,CHINA TOLAEM CHABANG/CHONBURI,THAILAND",
    "(EX.@ 33.3000=Bht129,934.94)",
    "6PALLETS",
]

DEVES_NO_DIGITS = [
    "MARINE CARGO POLICY | Policy No. 00/2026-00773023-CMI",
    "VeSSeI:NORTHERNGUARDV.634S | Sailing on or about : 22/08/2026",
    "Voyage :At and from HAIPHONG, VIETNAM TO BANGKOK THENCE TO INSURED'S WAREHOUSE",
    "(US DOLLARS : Thirty-One Thousand Two Hundred and Thirty-Seven And 22/100)",
    "196 CARTONS (9,706.00 KGS.)(40'HC)",
]


def test_ยอดบาทกับอัตราแลกเปลี่ยนในบรรทัดเดียว():
    """Tokio Marine เขียน (EX.@ 33.3000=Bht129,934.94) ไม่เขียนทุนประกันสกุลต่างประเทศ"""
    r = analyze_marine_policy(TOKIO)
    assert r.thb_value == pytest.approx(129934.94)
    assert r.exchange_rate == pytest.approx(33.30)
    assert r.amount_insured == pytest.approx(3901.95)


def test_บอกว่าทุนประกันมาจากการคำนวณ():
    """ผู้ตรวจต้องรู้ว่าตัวเลขนี้ไม่ได้อยู่ในเอกสารโดยตรง"""
    r = analyze_marine_policy(TOKIO)
    assert any("มาจากการคำนวณ" in n for n in r.notes)


def test_เลขที่กรมธรรม์รูปแบบผู้รับประกันรายอื่น():
    assert analyze_marine_policy(TOKIO).policy_no == "DR-90-69/000258"


def test_จำนวนหีบห่อที่ไม่มีน้ำหนักในวงเล็บ():
    r = analyze_marine_policy(TOKIO)
    assert (r.packages, r.package_unit) == (6.0, "PALLETS")
    assert r.gross_weight is None


def test_บรรทัดตัวเลขหายไปแต่มีตัวหนังสือ():
    """OCR ไม่ได้อ่านบรรทัดทุนประกันมาเลย เหลือแต่ตัวหนังสือกำกับ"""
    r = analyze_marine_policy(DEVES_NO_DIGITS)
    assert r.amount_insured == pytest.approx(31237.22)
    assert "ไม่มีหลักฐานยืนยัน" in r.status
    assert any("ทางเดียว" in n for n in r.notes)


@pytest.mark.parametrize("text, want", [
    ("VeSSeI:KHUNABHUMV.085S Sailing on or about : 15/08/2026", "KHUNABHUMV.085S"),
    ("VeSSeI:IRENESRAINBOWV.26034S Sailing on or about: 27/08/2026",
     "IRENESRAINBOWV.26034S"),
])
def test_ชื่อเรือต้องไม่ลากป้ายชื่อถัดไปมาด้วย(text, want):
    """เคยได้ 'KHUNABHUMV.085S Sailing on or about : 15/08/2026'"""
    assert read_labels([text]).get("vessel") == want


def test_บอกว่าติดที่คำไหนเมื่อตัวหนังสืออ่านไม่ออก():
    """แทนที่จะบอกแค่ว่าอ่านไม่ได้ ต้องบอกว่าต้องไปดูอะไร"""
    r = analyze_marine_policy([
        "MARINE CARGO POLICY", "Sum insured : CNY 51,513.00",
        "(CNY (CHINA) : Ffty-One Thousand Fve Hundred and Thirteen Only)"])
    assert r.amount_insured is None
    assert any("ติดที่คำว่า" in n for n in r.notes)
