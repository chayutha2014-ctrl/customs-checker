"""กวาดค่ากำพร้า — ค่าที่ปรากฏในเอกสารแต่ไม่มีตัวอ่านไหนอ้างถึง

ปิดรากของข้อผิดพลาดที่กฎทั้งหมดมองไม่เห็น
  ค่าที่ไม่มีใครคิดจะอ่าน
  ตัวอ่านบอกว่าช่องนั้นไม่มีค่า ทั้งที่ค่าอยู่ตรงนั้น
"""
import pytest

from customs_checker.orphan import orphan_scan, tokenize

FORM_E = [
    "Reference No. E260901280070068",
    "1 | COTTO | STAINLESS WATER INLET HOSE | PE | 3000PIECES | WLKL-CTSW-2605B",
    "HS C0DE:4009.22 | AUG.03, 2026",
    "TOTAL:FIVE(5)PALLETS ONL",
    "Departure date AUG. 15,2026 | Vessel KHUNA BHUM V.085S",
    "INSTITUTE CARGO CLAUSES (A) 1/1/09, CL370 10/11/03",
    "FOB NINGBO 12,345.67",
]
CLAIMED = ["E260901280070068", 4009.22, 5.0, 3000.0, "WLKL-CTSW-2605B", "PE"]


def test_ค่าที่ตัวอ่านอ้างถึงแล้วต้องไม่เป็นกำพร้า():
    r = orphan_scan(FORM_E, CLAIMED)
    texts = [t.text for t in r.tokens]
    assert "E260901280070068" not in texts
    assert "4009.22" not in texts
    assert not any(t.startswith("WLKL") for t in texts)


def test_ตัวเลขที่มีหน่วยต่อท้ายนับตามตัวเลข():
    """3000PIECES ไม่ใช่กำพร้า เพราะ 3000 ถูกอ้างถึงแล้ว"""
    r = orphan_scan(FORM_E, CLAIMED)
    assert not any("PIECES" in t.text for t in r.tokens)


def test_ค่าที่ไม่มีใครอ้างถึงต้องขึ้นเป็นกำพร้า():
    r = orphan_scan(FORM_E, CLAIMED)
    assert any(t.text == "12,345.67" for t in r.tokens)


def test_วันที่ที่ยังไม่มีตัวอ่านไหนอ่านต้องขึ้น():
    """ตัวอ่าน Form E ยังไม่ได้อ่านวันที่ออกเรือกับวันที่ใบกำกับ"""
    r = orphan_scan(FORM_E, CLAIMED)
    dates = [t.text for t in r.by_kind("วันที่")]
    assert len(dates) == 2


def test_ข้อความมาตรฐานของฟอร์มไม่ใช่ค่ากำพร้า():
    """เลขในข้อความเงื่อนไขกรมธรรม์ไม่ใช่ข้อมูลของงาน แต่ต้องนับไว้ ไม่ทิ้งเงียบ"""
    r = orphan_scan(FORM_E, CLAIMED)
    assert r.boilerplate > 0
    assert not any("1/1/09" in t.text for t in r.tokens)


def test_เลขสั้นต้องไม่ถูกตัดทิ้ง():
    """จำนวนหีบห่อเกือบทุกเคสอยู่ในช่วง 1-3 หลัก"""
    toks = [t.text for t in tokenize(["TOTAL 4 PALLETS", "28 CARTONS"])]
    assert "4" in toks
    assert "28" in toks


def test_ค่าเดียวกันหลายที่นับครั้งเดียว():
    r = orphan_scan(["X 999.00", "Y 999.00", "Z 999.00"], [])
    assert len([t for t in r.tokens if t.text == "999.00"]) == 1


def test_ชนกับช่องที่ตัวอ่านบอกว่าไม่มี():
    """ถ้าบอกว่าไม่พบตัวเลข แต่มีตัวเลขกำพร้าอยู่ นั่นคือสัญญาณว่าอ่านผิดช่อง"""
    r = orphan_scan(FORM_E, CLAIMED, absent_kinds=("ตัวเลข",))
    assert r.suspects
    assert "อาจอ่านผิดช่อง" in r.suspects[0]


def test_ไม่มีค่ากำพร้าก็ไม่ต้องมีข้อสงสัย():
    r = orphan_scan(["TOTAL 100"], [100.0], absent_kinds=("ตัวเลข",))
    assert not r.tokens
    assert not r.suspects


def test_ค่ากำพร้าเป็นข้อสังเกตไม่ใช่ข้อบกพร่อง():
    """เอกสารมีตัวเลขที่ไม่เกี่ยวข้องเสมอ หน้าที่คือชี้จุดให้คนดู ไม่ใช่ตัดสิน"""
    r = orphan_scan(FORM_E, CLAIMED)
    assert not hasattr(r, "issues")
    assert r.notes and "ค่ากำพร้า" in r.notes[0]


# ---------- จัดชั้นความสำคัญ ----------
# เอกสารมีตัวเลขที่ไม่ใช่ข้อมูลของงานเสมอ ถ้าเทกองรวมกันหมดรายงานจะท่วม
# (รอบแรกได้ 1,277 ตัวใน 47 หน้า เฉลี่ยหน้าละ 27 ตัว ไม่มีใครอ่านไหว)
# แต่ห้ามทิ้งเงียบ จึงจัดชั้นแล้วนับชั้นล่างไว้

from customs_checker.orphan import rank  # noqa: E402

ADDRESS_LINES = [
    "97,99DevesInsuranceBuilding,Ratchadamnoen",
    "77 Moo 5, Nong Pla Mo,Nong Khae, Saraburi 18140, Thailand",
    "29TH FLOOR,UNIT NO.2900,NEW PETCHBURI RD.,",
    "NO.207SOISAENGUTHAI,SUKHUMVIT50ROAD,",
]


@pytest.mark.parametrize("line", ADDRESS_LINES)
def test_บรรทัดที่อยู่ถูกจัดชั้นล่างสุด(line):
    r = orphan_scan([line], [])
    assert not r.tokens          # ไม่ขึ้นในรายการที่ควรดู
    assert r.minor               # แต่ยังนับไว้ ไม่ทิ้งเงียบ


def test_จำนวนที่มีทศนิยมอยู่ชั้นหนึ่ง():
    """46.21 CBM ที่ยังไม่มีใครอ่าน คือสิ่งที่ต้องเห็น"""
    r = orphan_scan(["B/LCHANGE:275196085 QTY 40': 1 HC CBM 40' 46.21"], [])
    top = [t for t in r.tokens if t.tier == 1]
    assert any(t.text == "46.21" for t in top)


def test_วันที่อยู่ชั้นสอง():
    r = orphan_scan(["JOB NO:1076249912-0096 TERM: FOB HAI PHONG DATE: 3-Sep-26"], [])
    assert any(t.tier == 2 for t in r.tokens)


def test_จำนวนเต็มในบรรทัดที่มีหน่วยอยู่ชั้นสาม():
    """จำนวนหีบห่อเป็นเลข 1-3 หลักไม่มีทศนิยม ต้องไม่ตกชั้นล่าง"""
    r = orphan_scan(["TOTAL 332 CARTONS"], [])
    assert any(t.text == "332" and t.tier == 3 for t in r.tokens)


def test_จำนวนเต็มลอยไม่มีหน่วยอยู่ชั้นสี่():
    r = orphan_scan(["SHED 7 TERMINAL 1"], [])
    assert not r.tokens
    assert r.minor


def test_ชั้นสี่ยังถูกนับในสรุป():
    r = orphan_scan(ADDRESS_LINES, [])
    assert r.notes
    assert "ชั้น4" in r.notes[0]


@pytest.mark.parametrize("line, want", [
    ("TOTAL 1,234.56 KGS", 1),
    ("DATE: 3-Sep-26", 2),
    ("332 CARTONS", 3),
    ("SUKHUMVIT 50 ROAD", 4),
])
def test_ชั้นของแต่ละแบบ(line, want):
    from customs_checker.orphan import tokenize
    toks = [t for t in tokenize([line])]
    assert toks
    assert min(rank(t)[0] for t in toks) == want
