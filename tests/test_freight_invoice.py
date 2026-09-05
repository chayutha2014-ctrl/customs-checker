"""ตัวอ่านใบแจ้งหนี้ค่าระวาง

ข้อความทั้งหมดมาจาก OCR ของเอกสารจริง 4 ใบ จากผู้ให้บริการ 3 ราย
กันไว้เป็นชุดตาบอด 2 ใบตั้งแต่ต้น ผู้พัฒนายังไม่เคยเห็น

ความสัมพันธ์เชิงเลขอยู่ใน **บรรทัดเดียวกัน** ไม่ใช่ในคอลัมน์ จึงไม่ต้องใช้พิกัด
"""
import pytest

from customs_checker.freight_invoice import (analyze_freight_invoice,
                                             find_charge, numbers_in,
                                             read_fields, unit_in_line)

EXTRA = """Extra MaritimeCo.,Ltd.(HEAD OFFICE)
FREIGHTINVOICE
BILLTONAMEANDADRESS | (100968) | INVOICENO. | ：SLI26080580
VESSEL | IRENESRAINBOWV.034S | ORIGIN | ：XIAMEN,CHINA
ETD | 27AUG2026 | ETA | ：01SEP2026
B/LNo. | JWFEM26080409 | B/LTYPE | ：
NO OFPACKAGE | 1,772CARTONS | GROSSWEIGHT | 26,110.000 KGS.
CONTAINERNO. | 1X20'DC,1X40HC | CBM | ：80.1800M3
OCEANFREIGHT | 300.00 | USD | 1.00 | 20'DC | 300.00
OCEANFREIGHT | 490.00 | USD | 1.00 | 40'HC | 490.00
Note:Pleaseverify... | TotalAmount | USD | 790.00""".splitlines()

BUGATTI = """BUGATTIFREIGHT INT'L(THAILAND) CO., LTD.
BILLTONAMEANDADDRESS | (109034)INVOICENO.: | PRE-INSI26095266
VESSEL: | JARUBHUMV.176S | CURRENCY: | USD
FEEDER: | JARUBHUMV.176S | B/LNO | LNBBKK264846
SHED: | 7 | TERMINAL:1 | VOL:0.220CBM. | ETA: | 01/09/2026
PORT: | NINGBO,CHINA | G.W.:81.000KGS. | QUANTITY: | 10.00CARTONS
NEWB/LNO | NGBCB26030045M | CNTRNO | REGU5192727/40HQ
SEAFREIGHT | 1.000 | CBM | USD | 1.00 | 1.00
EBS&CIC | 1.000 | CBM | USD | 6.50 | 6.50
GRANDTOTALAMOUNT | 7.50""".splitlines()

XTRIM_A = """XTRIM LOGISTICS CO., LTD.
FREIGHTINVOICE | JOB NO : SI260305
VESSEL | : KHUNA BHUM V.085S | PLACE OF RECEIPT : NINGBO,CHINA
HOUSE B/L | :ODIN26082516 | Q'TY | : 5 PALLETS
NEW B/L | :CULVNGB2631482-032 | GROSS WEIGHT | : 1,120.000 KGS
CONTAINER NO: | CBM | : 7.500 M3
SEA FREIGHT [USD 1.000 X 7.500 ] | USD | 7.50
TOTALAM | 7.50""".splitlines()

XTRIM_B = """XTRIM LOGISTICS CO., LTD.
FREIGHTINVOICE | JOB NO : SI260324
HOUSE B/L | :ODIN26082527 | Q'TY | : 2,006 CARTONS
NEW B/L | : 0OLU2335161990 | GROSS WEIGHT | : 20,364.160 KGS
CONTAINER NO: CSNU8949668/ /40'HQ | CBM | :158.170 M3
CCLU7892127//40'HQ | SHED | :8 | : TERMINAL : 2
FFAU7630771//40'HQ
SEA FREIGHT [USD 520.000 X 3.000 ] | USD | 1,560.00
TOTALAMOUNT | 1,560.00""".splitlines()


@pytest.mark.parametrize("rows, total, n", [
    (EXTRA, 790.00, 2), (BUGATTI, 7.50, 2),
    (XTRIM_A, 7.50, 1), (XTRIM_B, 1560.00, 1),
])
def test_ผลบวกบรรทัดค่าใช้จ่ายตรงกับยอดรวมท้ายใบ(rows, total, n):
    r = analyze_freight_invoice(rows)
    assert len(r.charges) == n
    assert r.computed == pytest.approx(total)
    assert r.total == pytest.approx(total)
    assert "ตรงกับยอดรวมท้ายใบ" in r.status


def test_การคูณที่ซ่อนในวงเล็บของคำบรรยาย():
    """XTRIM เขียน SEA FREIGHT [USD 520.000 X 3.000 ] ซึ่งเป็น a x b = c เหมือนกัน"""
    c = find_charge("SEA FREIGHT [USD 520.000 X 3.000 ] | USD | 1,560.00")
    assert {c.f1, c.f2} == {520.0, 3.0}
    assert c.amount == pytest.approx(1560.00)


def test_รหัสที่มีตัวเลขปนต้องไม่ถูกอ่านเป็นจำนวน():
    """ETD | 27AUG2026 | ETA | ：01SEP2026 เคยถูกอ่านเป็น 2026 x 1 = 2026"""
    assert numbers_in("ETD | 27AUG2026 | ETA | ：01SEP2026") == []
    assert find_charge("ETD | 27AUG2026 | ETA | ：01SEP2026") is None


@pytest.mark.parametrize("text", [
    "HOUSE B/L | :ODIN26082516",
    "NEW B/L | : 0OLU2335161990",
    "FREIGHTINVOICE | JOB NO : SI260324",
    "VESSEL | : KHUNA BHUM V.085S",
])
def test_บรรทัดที่มีแต่รหัสไม่ใช่บรรทัดค่าใช้จ่าย(text):
    assert find_charge(text) is None


def test_ฐานที่ใช้คิดตรงกับปริมาตรในใบ():
    r = analyze_freight_invoice(XTRIM_A)
    assert r.charges[0].basis == "ปริมาตร CBM"
    assert r.charges[0].basis_value == pytest.approx(7.5)


def test_ฐานที่ใช้คิดตรงกับจำนวนตู้():
    """520 x 3 โดยในใบมีเลขตู้ 3 ตู้"""
    r = analyze_freight_invoice(XTRIM_B)
    assert r.quantities["จำนวนตู้"] == 3
    assert r.charges[0].basis == "จำนวนตู้"


def test_คิดขั้นต่ำถูกรายงานเป็นหมายเหตุ_ไม่ใช่ความผิด():
    """Bugatti คิด 1.000 CBM ทั้งที่สินค้ามี 0.220 CBM ซึ่งเป็นการคิดขั้นต่ำตามปกติ"""
    r = analyze_freight_invoice(BUGATTI)
    assert not r.issues
    assert any("อาจเป็นการคิดขั้นต่ำ" in n for n in r.notes)
    assert r.quantities["ปริมาตร CBM"] == pytest.approx(0.22)


@pytest.mark.parametrize("rows, key, want", [
    (EXTRA, "house_bl", "JWFEM26080409"),
    (EXTRA, "invoice_no", "SLI26080580"),
    (EXTRA, "gross_weight", "26,110.000 KGS."),
    (BUGATTI, "new_bl", "NGBCB26030045M"),
    (BUGATTI, "cbm", "0.220CBM"),
    (XTRIM_A, "new_bl", "CULVNGB2631482-032"),
    (XTRIM_B, "packages", "2,006 CARTONS"),
])
def test_อ่านช่องที่มีป้ายชื่อกำกับ(rows, key, want):
    assert read_fields(rows).get(key) == want


def test_ป้ายที่ยาวกว่าชนะ():
    """NEWB/LNO ต้องไม่ถูกจับด้วยป้าย B/LNO"""
    f = read_fields(["NEWB/LNO | NGBCB26030045M | CNTRNO | REGU5192727/40HQ"])
    assert f.get("new_bl") == "NGBCB26030045M"
    assert f.get("house_bl") != "NGBCB26030045M"


@pytest.mark.parametrize("text, unit", [
    ("SEAFREIGHT | 1.000 | CBM | USD | 1.00 | 1.00", "CBM"),
    ("SEA FREIGHT [USD 1.000 X 7.500 ] | USD | 7.50", ""),
    ("OCEANFREIGHT | 300.00 | USD | 1.00 | 20'DC | 300.00", ""),
])
def test_หน่วยที่เขียนในบรรทัดค่าใช้จ่าย(text, unit):
    assert unit_in_line(text) == unit


XTRIM_C = """XTRIM LOGISTICS CO., LTD.
FREIGHT INVOICE
JOB NO : SI260322
VESSEL | :IRENES RAINBOW V.26034S | PLACE OF RECEIPT : XIAMEN,CHINA
FEEDER | :IRENES RAINBOW V.034S | PORT OF LOADING | : XIAMEN,CHINA
HOUSE B/L | ：ODIN26082525 | Q'TY | : 2,031 CARTONS
NEW B/L | ：OOLU2334855880 | GROSS WEIGHT | : 25,934.140 KGS
CONTAINER N0: O0CU5987454/ /40'HQ | CBM | :192.920 M3
SEA FREIGHT [USD520.000 X 3.000 ] | USD | 1,560.00
TOTAAMOUNT USD | 1,560.00""".splitlines()


def test_สกุลเงินติดกับตัวเลขโดยไม่มีช่องว่าง():
    """USD520.000 คือจำนวนเงิน ไม่ใช่รหัส — เคยถูกทิ้งไปทั้งบรรทัด"""
    c = find_charge("SEA FREIGHT [USD520.000 X 3.000 ] | USD | 1,560.00")
    assert c is not None
    assert {c.f1, c.f2} == {520.0, 3.0}


def test_ใบที่เขียนสกุลเงินติดตัวเลขยังอ่านได้ครบ():
    r = analyze_freight_invoice(XTRIM_C)
    assert r.computed == pytest.approx(1560.00)
    assert r.total == pytest.approx(1560.00)


@pytest.mark.parametrize("text, want", [
    ("REGU5192727/40HQ", []),          # เลขตู้
    ("V.26034S", []),                  # เลขเที่ยวเรือ
    ("ODIN26082525", []),              # เลข B/L
    ("VOL:0.220CBM.", [0.22]),         # หน่วยต่อท้าย ยังอ่านได้
    ("USD 1.000 X 7.500", [1.0, 7.5]),
])
def test_แยกรหัสออกจากจำนวน(text, want):
    assert [v for _, v in numbers_in(text)] == want


def test_ช่องว่างเปล่าต้องไม่หยิบป้ายชื่อช่องถัดไปมาเป็นค่า():
    """FEEDER | DESTINATION | ：LATKRABANG เคยได้ feeder=DESTINATION"""
    f = read_fields(["FEEDER | DESTINATION | ：LATKRABANG,THAILAND"])
    assert "feeder" not in f
    assert f.get("destination") == "LATKRABANG,THAILAND"


def test_ช่องเลขตู้ว่างต้องไม่ได้ค่าเป็น_CBM():
    f = read_fields(["CONTAINER NO: | CBM | : 7.500 M3"])
    assert "container" not in f
    assert f.get("cbm") == "7.500 M3"


# ---------- ค่าใช้จ่ายคงที่ที่ไม่มีการคูณ ----------
# ใบแจ้งหนี้ค่าระวางมีค่าใช้จ่ายคงที่เสมอ เช่นค่า B/L ค่า THC ค่าเอกสาร
# เขียนเป็นจำนวนเงินเดี่ยว ๆ ไม่มี อัตรา x ปริมาณ ให้จับ

FLAT = """ACME SHIPPING
FREIGHT INVOICE | JOB NO : X1
HOUSE B/L | :ABC123 | Q'TY | : 6 PALLETS
OCEAN FREIGHT [USD 125.21 X 3.000 ] | USD | 375.63
B/L FEE | 40.00
DOCUMENT FEE | 24.22
TOTAL AMOUNT | 439.85""".splitlines()


def test_เติมค่าใช้จ่ายคงที่แล้วลงตัวพอดี():
    r = analyze_freight_invoice(FLAT)
    assert r.computed == pytest.approx(439.85)
    assert r.total == pytest.approx(439.85)
    assert sum(1 for c in r.charges if c.flat) == 2


def test_บอกด้วยว่าบรรทัดไหนเป็นค่าใช้จ่ายคงที่():
    """ผู้ตรวจต้องเห็นว่าบรรทัดไหนได้มาจากการเติม ไม่ใช่จากการคูณ"""
    r = analyze_freight_invoice(FLAT)
    assert "ค่าใช้จ่ายคงที่" in r.status
    flat = [c.text for c in r.charges if c.flat]
    assert any("B/L FEE" in t for t in flat)
    assert any("DOCUMENT FEE" in t for t in flat)


def test_เติมแล้วไม่ลงตัวต้องไม่เติม():
    """ห้ามเดาว่าบรรทัดไหนน่าจะเป็นค่าใช้จ่าย ต้องลงตัวพอดีเท่านั้น"""
    rows = FLAT[:-1] + ["TOTAL AMOUNT | 500.00"]
    r = analyze_freight_invoice(rows)
    assert all(not c.flat for c in r.charges)
    assert r.computed == pytest.approx(375.63)
    assert r.issues


def test_ใบที่ไม่มีค่าใช้จ่ายคงที่ต้องไม่ถูกเติมมั่ว():
    """XTRIM_A ลงตัวอยู่แล้วด้วยบรรทัดเดียว ต้องไม่มีบรรทัดคงที่โผล่มา"""
    r = analyze_freight_invoice(XTRIM_A)
    assert len(r.charges) == 1
    assert not r.charges[0].flat


# ---------- อัตราที่พิมพ์แบบปัดเศษ ----------
# ที่มา: SKM_450i26090410270/page_004.png (INDIGO LINE)

INDIGO = """INDIGO LINE
PRE-INVOICE ( USD)
INVOICE TO : x | PRE-INVOICENO.:PS2609-0002
HB/L No.:LLLLCB26814251SZ | QUANTITY:6PALLET(S) | WEIGHT:790KGS.
DESCRIPTION | RATE | QTY | UNIT | AMOUNT
FRT | SEAFREIGHTCHARGES | 7.55 USD | 8.51 | M3 | 64.22
EXW | EX-WORKSERVICECHARGES | 375.63USD | 1.00 | SHP | 375.63
TOTALAMOUNT: | USD | 439.85""".splitlines()


def test_อัตราที่ถูกปัดเศษยังจับคู่ได้():
    """7.55 x 8.51 = 64.2505 แต่ใบเขียน 64.22 เพราะอัตราจริงคือ 7.5464 แล้วถูกปัด"""
    c = find_charge("FRT | SEAFREIGHTCHARGES | 7.55 USD | 8.51 | M3 | 64.22")
    assert c is not None
    assert c.amount == pytest.approx(64.22)


def test_ค่ายอมรับโตตามปริมาณ():
    """อัตราแสดง 2 ตำแหน่ง คลาดได้ครึ่งหน่วยสุดท้าย คูณด้วยปริมาณ"""
    from customs_checker.freight_invoice import rounding_tol
    assert rounding_tol(7.55, 8.51, "7.55", "8.51", 64.22) > 0.031
    assert rounding_tol(7.55, 1.0, "7.55", "1.00", 7.55) < 0.03


def test_ใบที่อัตราถูกปัดเศษอ่านได้ครบ():
    r = analyze_freight_invoice(INDIGO)
    assert len(r.charges) == 2
    assert r.computed == pytest.approx(439.85)
    assert r.total == pytest.approx(439.85)


# ---------- ใบที่แบ่งค่าใช้จ่ายเป็นหลายหมวด ----------
# ที่มา: Scan2026-09-03_182617/page_007.png (Kuehne+Nagel)

KN = """FREIGHT INVOICE
KUEHNE+NAGELLTD.
OCEAN FREIGHT | RATE | UNIT | VOLUME | CURRENCY | AMOUNT
SEAFREIGHT | 70.000 | SHIPMENT | 1 | USD | 70.000
EMERGENCYBUNKERSURCHARGE(EBS) | 270.00 | SHIPMENT | 1 | USD | 270.00
ORIGIN CHARGES | RATE | UNIT | VOLUME | CURRENCY | AMOUNT
DESTINATION LOCAL CHARGE | RATE | LINN | VOLUME | CURRENCY | AMOUNT
TOTAL OCEAN FREIGHT:USD | 340.000""".splitlines()


def test_หมวดที่ไม่มีรายการต้องถูกรายงาน():
    """ยอด 340 เป็นยอดของหมวดค่าระวางเท่านั้น
    ถ้าไม่บอกว่ามีอีกสองหมวดที่ว่าง จะกลายเป็นข้อผิดเงียบเมื่อเจอใบที่หมวดนั้นมีรายการ"""
    r = analyze_freight_invoice(KN)
    assert any("3 หมวด" in n for n in r.notes)
    assert sum(1 for n in r.notes if "ไม่มีรายการที่อ่านได้" in n) == 2


def test_หัวตารางหมวดต้องไม่กลายเป็นค่าของช่อง():
    """ORIGIN CHARGES | RATE | UNIT | AMOUNT เคยให้ origin=CHARGES"""
    r = analyze_freight_invoice(KN)
    assert r.fields.get("origin") is None
    assert r.fields.get("destination") is None


def test_หัวตารางต้องไม่ถูกจับเป็นบรรทัดค่าใช้จ่าย():
    r = analyze_freight_invoice(KN)
    assert len(r.charges) == 2
    assert r.computed == pytest.approx(340.00)


def test_ใบหมวดเดียวไม่ต้องมีหมายเหตุเรื่องหมวด():
    r = analyze_freight_invoice(INDIGO)
    assert not any("หมวด" in n for n in r.notes)
