# -*- coding: utf-8 -*-
"""จำแนกชนิดเอกสารรายหน้า

หลักการ
1. ให้คะแนนทุกชนิดแข่งกัน ไม่ใช่หยุดที่คำแรกที่เจอ
   (Packing List มีคำว่า "INVOICE NO." อยู่ในหัวเอกสาร ถ้าเช็ค Invoice ก่อนจะคว้าผิด)
2. คำที่อยู่ในโซนหัวเรื่องมีน้ำหนักมากกว่าคำเดียวกันที่อยู่กลางหน้า
3. คำที่ปรากฏในเอกสารหลายชนิดมีน้ำหนักต่ำ คำที่ปรากฏชนิดเดียวมีน้ำหนักสูง
4. ไม่มั่นใจต้องบอกว่าไม่มั่นใจ — ห้ามเดา (silent error = 0)
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field

# ---------- คะแนน ----------
W_TITLE_IN_ZONE = 10.0   # คำหัวเรื่อง พบในโซนหัวเรื่อง
W_TITLE_ELSE    = 6.0    # คำหัวเรื่อง พบที่อื่นในหน้า (หัวจดหมายสูงจนหัวเรื่องหลุดโซน)
W_STRONG        = 3.0    # คำเฉพาะของชนิดนั้น
W_WEAK          = 1.0    # คำสนับสนุน
W_NEGATIVE      = -4.0   # คำที่ขัดกับชนิดนั้น
CAP_STRONG      = 9.0
CAP_WEAK        = 4.0

MIN_SCORE  = 6.0   # ต่ำกว่านี้ = ไม่มีหลักฐานพอ
MIN_MARGIN = 4.0   # ห่างอันดับสองน้อยกว่านี้ = ไม่มั่นใจ
MIN_WORDS  = 12    # น้อยกว่านี้ถือว่าอ่านหน้านี้ไม่ได้ ไม่ใช่จำแนกไม่ได้


@dataclass
class Rule:
    code: str
    name_th: str
    title: tuple[str, ...] = ()
    strong: tuple[str, ...] = ()
    weak: tuple[str, ...] = ()
    negative: tuple[str, ...] = ()


RULES: list[Rule] = [
    Rule("invoice", "Invoice",
         # ผู้ขายหลายรายเขียนหัวเรื่องแค่ "INVOICE" จึงต้องรับคำเดี่ยวด้วย
         # แต่ต้องไม่ไปจับ "INVOICE NO." (มีบน Packing List แทบทุกใบ)
         # และไม่จับ "PRE-INVOICE" / "FREIGHT INVOICE" (เป็นใบค่าระวาง)
         title=("COMMERCIAL INVOICE",
                r"re:(?<!PRE )(?<!FREIGHT )(?<!PROFORMA )(?<!TAX )"
                r"\bINVOICE\b(?!\s*(?:NO\b|NUMBER|#|DATE\b|TO\b))"),
         strong=("UNIT PRICE", "TERMS OF PAYMENT", "SAY TOTAL", "SAY U.S.DOLLARS",
                 "SAY RMB", "TOTAL AMOUNT", "AMOUNT FOREIGN", "SUBTOTAL"),
         weak=("BENEFICIARY", "SWIFT", "ADVISING BANK", "ACCOUNT NO", "PAYMENT TERMS",
               "DESCRIPTION OF GOODS", "ITEM NO"),
         # คำที่บอกว่านี่ไม่ใช่ใบกำกับราคาสินค้า — ต้องมีทั้งอังกฤษและไทย
         # เพราะใบแจ้งหนี้เบี้ยประกันของบริษัทไทยเขียนหัวเรื่องว่า Invoice เหมือนกัน
         # แต่เนื้อในเป็นภาษาไทยล้วน คำอังกฤษจึงไม่ทำงาน
         negative=("PACKING LIST", "BILL OF LADING", "CERTIFICATE OF ORIGIN",
                   "MARINE CARGO POLICY", "FREIGHT INVOICE",
                   "SUM INSURED", "STAMP DUTY", "PERIOD OF INSURANCE",
                   "เบี้ยประกันภัย", "อากรแสตมป์", "ทุนประกันภัย",
                   "กรมธรรม์", "ระยะเวลาประกันภัย")),

    Rule("packing_list", "Packing List",
         title=("PACKING LIST",),
         strong=("NET WEIGHT", "GROSS WEIGHT", "N.W.", "G.W.", "MEASUREMENT",
                 "TOTAL PACKED", "TOTAL MEASUREMENT", "TOTAL NET WEIGHT", "TOTAL GROSS WEIGHT"),
         weak=("CARTONS", "CTNS", "PALLET", "CBM", "PACKAGE", "KGS"),
         negative=("UNIT PRICE", "BILL OF LADING", "CERTIFICATE OF ORIGIN",
                   "MARINE CARGO POLICY", "FREIGHT INVOICE")),

    Rule("bill_of_lading", "B/L",
         title=("BILL OF LADING", "OCEAN BILL OF LADING", "SEA WAYBILL"),
         strong=("SHIPPED ON BOARD", "SHIPPED ON BORAD", "LADEN ON BOARD", "NOTIFY PARTY",
                 "PLACE OF DELIVERY", "NON-NEGOTIABLE", "NON NEGOTIABLE",
                 "PLACE OF RECEIPT", "PRE-CARRIAGE", "NO. OF ORIGINAL", "NO.OF ORIGINAL",
                 "TOTAL NUMBER OF CONTAINERS", "PARTICULARS DECLARED BY SHIPPER"),
         weak=("SHIPPER", "CONSIGNEE", "PORT OF DISCHARGE", "PORT OF LOADING",
               "FREIGHT COLLECT", "TELEX RELEASE", "SURRENDERED", "CONTAINER"),
         negative=("PACKING LIST", "COMMERCIAL INVOICE", "CERTIFICATE OF ORIGIN",
                   "FREIGHT INVOICE", "MARINE CARGO POLICY")),

    Rule("form_co", "Form CO",
         title=("CERTIFICATE OF ORIGIN", "FORM E", "FORM D", "FORM AK", "FORM AI",
                "FORM AJ", "FORM AANZ", "FORM RCEP"),
         strong=("PREFERENTIAL TARIFF", "ISSUED RETROACTIVELY", "ORIGIN CRITERIA",
                 "OVERLEAF NOTES", "DECLARATION BY THE EXPORTER", "FREE TRADE AREA",
                 "THIRD PARTY INVOICING", "MOVEMENT CERTIFICATE",
                 "COMBINED DECLARATION AND CERTIFICATE"),
         weak=("REFERENCE NO", "PREFERENTIAL TREATMENT", "IMPORTING COUNTRY",
               "AUTHORISED SIGNATORY", "HS NUMBER"),
         negative=("PACKING LIST", "FREIGHT INVOICE", "MARINE CARGO POLICY")),

    Rule("freight_invoice", "ใบแจ้งหนี้ค่าระวาง",
         title=("FREIGHT INVOICE",),
         strong=("OCEAN FREIGHT", "HOUSE B/L", "NEW B/L", "EXWORK CHG", "SEA FREIGHT",
                 "TOTAL AMOUNT IN USD", "TOTAL VAT EXCUSIVE", "GRAND TOTAL AMOUNT",
                 "PRE INVOICE", "SHIPMENT NO", "MASTER JOB"),
         weak=("ETD", "ETA", "TERMINAL", "SHED", "JOB NO", "FEEDER", "VESSEL",
               "NO OF PACKING", "CR. TERM", "REVENUE TONS"),
         negative=("PACKING LIST", "CERTIFICATE OF ORIGIN", "BILL OF LADING",
                   "MARINE CARGO POLICY")),

    Rule("marine_policy", "กรมธรรม์ประกันภัย",
         title=("MARINE CARGO POLICY", "CARGO POLICY SCHEDULE"),
         strong=("AMOUNT INSURED", "INSTITUTE CARGO CLAUSES", "SAILING ON OR ABOUT",
                 "NAME OF ASSURED", "SUBJECT-MATTER INSURED", "MARINE OPEN COVER",
                 "INSTITUTE WAR CLAUSES", "VALUED AT THE SAME AS AMOUNT INSURED"),
         weak=("POLICY NO", "DEDUCTIBLE", "CLAIMS", "LLOYD", "WARRANTED", "VOYAGE"),
         negative=("PACKING LIST", "COMMERCIAL INVOICE", "FREIGHT INVOICE",
                   "BILL OF LADING")),

    Rule("insurance_invoice", "ใบแจ้งหนี้เบี้ยประกัน",
         # หัวเรื่องเขียนแค่ "Invoice" เหมือน Commercial Invoice จึงใช้หัวเรื่องตัดสินไม่ได้
         # ต้องให้คำเฉพาะ (SUM INSURED / STAMP DUTY / เบี้ยประกันภัย) เป็นตัวตัดสินแทน
         # และให้ Commercial Invoice ติดลบเมื่อเจอคำเหล่านั้น (ดู negative ของ invoice)
         title=("ใบแจ้งหนี้", "ใบแจงหนี"),
         strong=("SUM INSURED", "STAMP DUTY", "PREMIUM / OTHERS", "PREMIUM/OTHERS",
                 "INSURED NAME & ADDRESS", "PERIOD OF INSURANCE",
                 "ทุนประกันภัย", "เบี้ยประกันภัย", "อากรแสตมป์"),
         weak=("POLICY NO", "TYPE OF POLICY", "CROSSED CHEQUE", "กรมธรรม์เลขที่",
               "ระยะเวลาประกันภัย", "ยอดรวม", "ประกันภัย", "INSURANCE",
               "เอาประกันภัย", "ใบแจ้งหนี้", "ใบแจงหนี"),
         negative=("MARINE CARGO POLICY", "PACKING LIST", "BILL OF LADING",
                   "INSTITUTE CARGO CLAUSES")),

    Rule("import_declaration", "ใบขนสินค้าขาเข้า",
         title=("ใบขนสินค้าขาเข้า",),
         strong=("ORIGINCRITERIA", "PACK(INV.)", "INVNO#", "ใบต่อแผ่นที่",
                 "อากรขาเข้า", "ภาษีมูลค่าเพิ่ม", "รหัสสถิติ", "เลขที่ใบขนสินค้า",
                 "รวมค่าภาษีอากรทั้งสิ้น", "ภาษีสรรพสามิต"),
         weak=("กศก", "TERM :", "TERM:", "CIF", "ประเภทพิกัด", "ราคาของ",
               "น้ำหนักสุทธิ", "อัตราแลกเปลี่ยน"),
         negative=("PACKING LIST", "BILL OF LADING", "MARINE CARGO POLICY")),
    Rule("delivery_order", "ใบแจ้งสินค้าขาเข้า (D/O)",
         # OCR ภาษาไทยมักตกวรรณยุกต์ จึงใส่ทั้งแบบมีและไม่มี
         title=("ใบแจ้งสินค้าขาเข้า", "ใบแจงสินคาขาเขา", "DELIVERY ORDER",
                "ARRIVAL NOTICE"),
         strong=("(D/O)", "หมายเลข AIR WAYBILL", "แจ้งสินค้าขาเข้า", "แจงสินคาขาเขา",
                 "ท่าอากาศยานสุวรรณภูมิ", "ทาอากาศยานสุวรรณภูม", "ขอแจ้งสินค้า"),
         weak=("AIR WAYBILL", "จำนวนหน้า", "จํานวนหนา", "เรียน", "หมายเลขแฟกซ"),
         negative=("COMMERCIAL INVOICE", "PACKING LIST", "MARINE CARGO POLICY",
                   "CERTIFICATE OF ORIGIN")),

    Rule("air_waybill", "Air Waybill",
         title=("AIR WAYBILL", "AIRWAYBILL", "AWB"),
         # ป้ายพัสดุของผู้ให้บริการมักไม่มีคำว่า AIR WAYBILL อยู่บนหน้า
         # ต้องยึดคำเฉพาะของป้ายแทน
         strong=("ORIGIN ID", "SHIP DATE", "ACTWGT", "ACT WGT", "DESC 1", "DESC-1",
                 "CAD:", "TRK#", "MASTER AIR WAYBILL", "HOUSE AIR WAYBILL"),
         weak=("EXPRESS", "REF:", "SHIPPER", "BILL SENDER", "DIM"),
         negative=("COMMERCIAL INVOICE", "PACKING LIST", "BILL OF LADING",
                   "MARINE CARGO POLICY", "CERTIFICATE OF ORIGIN")),

    Rule("permit", "ใบอนุญาต / หลักฐานการรับแจ้ง",
         title=("หลักฐานการรับแจ้ง", "หลักฐานการรับแจง", "ใบอนุญาต", "ใบอนุญาตนำเข้า"),
         strong=("PERMIT NUMBER", "TISI", "ผลิตภัณฑ์อุตสาหกรรม", "ผลิตภัณฑอุตสาหกรรม",
                 "มาตรฐานเข้ามาในราชอาณาจักร", "มาตรฐานเขามาในราชอาณาจักร",
                 "สำนักงานมาตรฐานผลิตภัณฑ", "สํานักงานมาตรฐานผลิตภัณฑ"),
         weak=("ชื่อผู้นำเข้า", "ชื่อผู้นําเข้า", "เลขที่บัญชีราคาสินค้า",
               "INVOICE NUMBER", "ด่านศุลกากร"),
         negative=("COMMERCIAL INVOICE", "PACKING LIST", "BILL OF LADING",
                   "MARINE CARGO POLICY")),
]


# ---------- เตรียมข้อความ ----------
def normalize(text: str) -> str:
    """ตัวพิมพ์ใหญ่ + ยุบช่องว่าง + แปลงขีดคั่นเป็นช่องว่าง

    ทำให้ 'OCEAN-BILL OF LADING' กับ 'OCEAN BILL OF LADING' เท่ากัน
    """
    t = unicodedata.normalize("NFC", text or "").upper()
    t = t.replace("–", "-").replace("—", "-")
    t = re.sub(r"[-_]+", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def despace(text: str) -> str:
    """ตัดช่องว่างทั้งหมด — รับมือหัวเรื่องที่เว้นวรรคทีละตัวอักษร

    'P A C K I N G   L I S T' -> 'PACKINGLIST'
    """
    return re.sub(r"\s+", "", text)


def _has(pattern: str, norm: str, flat: str) -> bool:
    """เทียบคำ  ขึ้นต้นด้วย 're:' = เทียบด้วย regex บนข้อความที่ normalize แล้ว

    ต้องมี regex เพราะคำว่า INVOICE เดี่ยว ๆ ปรากฏบนเอกสารเกือบทุกชนิด
    (Packing List มี "INVOICE NO.", ใบค่าระวางมี "PRE-INVOICE")
    ถ้าเทียบตรงตัวจะแย่งชนิดเอกสารอื่นหมด
    """
    if pattern.startswith("re:"):
        return re.search(pattern[3:], norm) is not None
    p = normalize(pattern)
    return p in norm or despace(p) in flat


# ---------- เอกสารที่รวม Invoice กับ Packing List ไว้ในใบเดียว ----------
# ผู้ขายหลายรายทำ "Invoice cum Packing List" คือตารางเดียวมีทั้งราคาและน้ำหนัก
# ผู้ใช้ยืนยันว่าเจอเป็นปกติ จึงต้องรู้จัก ไม่ใช่บังคับให้เลือกข้างใดข้างหนึ่ง
#
# ไม่ทำเป็น Rule แยกในตารางคะแนน เพราะจะไปแย่งคะแนนกับ Invoice และ Packing List
# จนทั้งสามตัวคะแนนใกล้กันแล้วกลายเป็น "ไม่มั่นใจ" ทั้งหมด
# ใช้วิธี "จำแนกตามปกติก่อน แล้วค่อยยกระดับ" เมื่อพบร่องรอยของทั้งสองฝั่ง
# คำต้องบ่งบอก "เงิน" จริง ๆ
# ห้ามใส่ SAY TOTAL / FOB / CIF เพราะ Packing List ก็มี
#   ("SAY TOTAL FIVE HUNDRED AND TWENTY (520) CTNS ONLY." / "FOB Xiamen To Thailand")
# ทดลองใส่แล้วทำให้ Packing List ธรรมดา 6 ใบถูกยกระดับผิด
PRICE_MARKS = ("UNIT PRICE", "TOTAL AMOUNT", "UNIT COST", "TOTAL VALUE",
               "U.S.DOLLARS", "US DOLLARS", "SAY RMB", "TOTAL EXW",
               "GRAND TOTAL", "AMOUNT (USD)", "AMOUNT USD", "AMOUNT RMB",
               "AMOUNT CNY", "AMOUNT FOREIGN")
# คำต้องบ่งบอก "น้ำหนัก/ปริมาตร" ซึ่ง Invoice ธรรมดาไม่มี
# ห้ามใส่ CARTONS / CTNS / PALLET เพราะ Invoice บรรยายสินค้าด้วยคำพวกนี้ได้
PACK_MARKS = ("N.W.", "G.W.", "NET WEIGHT", "GROSS WEIGHT", "MEASUREMENT",
              "CBM", "KGS", "N.W", "G.W")
MIN_MARKS_EACH = 2


def _count(marks, norm, flat) -> int:
    return sum(1 for m in marks if _has(m, norm, flat))


def is_combined(page_text: str) -> bool:
    """หน้านี้มีทั้งราคาและข้อมูลการบรรจุอยู่ในใบเดียวหรือไม่"""
    n = normalize(page_text)
    f = despace(n)
    return (_count(PRICE_MARKS, n, f) >= MIN_MARKS_EACH
            and _count(PACK_MARKS, n, f) >= MIN_MARKS_EACH)


# ---------- ผลลัพธ์ ----------
@dataclass
class Score:
    code: str
    name_th: str
    score: float
    evidence: list[str] = field(default_factory=list)


@dataclass
class DocType:
    code: str            # รหัสชนิดเอกสาร หรือ 'unknown' / 'unreadable'
    name_th: str
    status: str          # 'ยืนยัน' | 'ต้องให้คนยืนยัน' | 'อ่านหน้านี้ไม่ได้'
    score: float
    margin: float
    runner_up: str
    evidence: list[str]
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ยืนยัน"


def _score_one(rule: Rule, zone_n: str, zone_f: str, page_n: str, page_f: str) -> Score:
    s, ev = 0.0, []
    for p in rule.title:
        if _has(p, zone_n, zone_f):
            s += W_TITLE_IN_ZONE
            ev.append(f"หัวเรื่อง:{p}")
            break
    else:
        for p in rule.title:
            if _has(p, page_n, page_f):
                s += W_TITLE_ELSE
                ev.append(f"หัวเรื่อง(นอกโซน):{p}")
                break

    hit = [p for p in rule.strong if _has(p, page_n, page_f)]
    s += min(len(hit) * W_STRONG, CAP_STRONG)
    ev += [f"เฉพาะ:{p}" for p in hit[:3]]

    hit = [p for p in rule.weak if _has(p, page_n, page_f)]
    s += min(len(hit) * W_WEAK, CAP_WEAK)
    ev += [f"สนับสนุน:{p}" for p in hit[:3]]

    hit = [p for p in rule.negative if _has(p, page_n, page_f)]
    s += len(hit) * W_NEGATIVE
    ev += [f"ขัดแย้ง:{p}" for p in hit[:3]]

    return Score(rule.code, rule.name_th, s, ev)


def classify(page_text: str, title_text: str | None = None) -> DocType:
    """จำแนกชนิดเอกสารของหน้าหนึ่ง

    page_text  : ข้อความทั้งหน้า
    title_text : ข้อความเฉพาะโซนหัวเรื่อง (ราว 22% บนของหน้า)
                 ถ้าไม่ส่งมา จะใช้ 22% แรกของบรรทัดทั้งหมดแทน
    """
    page_text = page_text or ""
    if len(page_text.split()) < MIN_WORDS:
        return DocType("unreadable", "อ่านหน้านี้ไม่ได้", "อ่านหน้านี้ไม่ได้",
                       0.0, 0.0, "", [],
                       note=f"มีข้อความ {len(page_text.split())} คำ ต่ำกว่าเกณฑ์ {MIN_WORDS} คำ")

    if title_text is None:
        lines = page_text.splitlines()
        title_text = "\n".join(lines[: max(1, len(lines) * 22 // 100)])

    page_n, page_f = normalize(page_text), despace(normalize(page_text))
    zone_n, zone_f = normalize(title_text), despace(normalize(title_text))

    scores = sorted((_score_one(r, zone_n, zone_f, page_n, page_f) for r in RULES),
                    key=lambda x: x.score, reverse=True)
    best, second = scores[0], scores[1]
    margin = best.score - second.score

    # เอกสารที่รวม Invoice กับ Packing List จะทำให้สองชนิดนี้คะแนนใกล้กันเสมอ
    # (หัวเรื่องมีทั้งสองคำ ตารางมีทั้งราคาและน้ำหนัก) ต้องตัดสินก่อนถึงด่านส่วนต่าง
    # มิฉะนั้นจะกลายเป็น "ไม่มั่นใจ" ทั้งที่จริง ๆ แล้วมั่นใจว่าเป็นทั้งสองอย่าง
    if (best.score >= MIN_SCORE
            and {best.code, second.code} <= {"invoice", "packing_list"}
            and is_combined(page_text)):
        return DocType("invoice_packing_list", "Invoice + Packing List (ใบเดียวกัน)",
                       "ยืนยัน", best.score, margin, second.name_th, best.evidence)

    if best.score < MIN_SCORE:
        return DocType("unknown", "ไม่ทราบชนิด", "ต้องให้คนยืนยัน",
                       best.score, margin, second.name_th, best.evidence,
                       note=f"คะแนนสูงสุด {best.score:.0f} ต่ำกว่าเกณฑ์ {MIN_SCORE:.0f} "
                            f"(เดาว่า {best.name_th})")
    if margin < MIN_MARGIN:
        return DocType("unknown", "ไม่ทราบชนิด", "ต้องให้คนยืนยัน",
                       best.score, margin, second.name_th, best.evidence,
                       note=f"{best.name_th} {best.score:.0f} vs {second.name_th} "
                            f"{second.score:.0f} ห่างกันแค่ {margin:.0f}")
    code, name = best.code, best.name_th
    if code in ("invoice", "packing_list") and is_combined(page_text):
        code, name = "invoice_packing_list", "Invoice + Packing List (ใบเดียวกัน)"
    return DocType(code, name, "ยืนยัน",
                   best.score, margin, second.name_th, best.evidence)
