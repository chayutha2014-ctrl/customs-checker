# -*- coding: utf-8 -*-
"""ชุดทดสอบตัวจำแนกชนิดเอกสาร

ทุกกรณีมาจากเอกสารตัวอย่างจริง 5 ชุด — ไม่ใช่ข้อความสมมติ
บทเรียนจาก tables.py: โค้ดที่ไม่มีเทสต์จะถอยหลังเสมอ
"""
import sys, os, pytest
_here = os.path.dirname(os.path.abspath(__file__))
for _p in ("..", os.path.join("..", "src")):
    sys.path.insert(0, os.path.abspath(os.path.join(_here, _p)))
from customs_checker.doctype import classify, normalize, despace


# ---------- กับดักที่ทำให้ตัวจำแนกแบบคำแรกชนะพลาด ----------
PACKING_LIST = """
FOSHAN XINYANG CERAMICS CO.,LTD.
PACKING LIST
TO: SCG CERAMICS PUBLIC COMPANY LIMITED
INVOICE NO.: 26SYCI-RM026
DATE: 16/Jul/26
PO No. 4102016367 / 4102016370
NO. Container NO. Description of goods Quantity Package Unit Pallets Net weight Gross weight
1 SPC DECO FILM JS21024-11 8 8150 M
TOTAL: 20 20465 M 2 1991.00 KGS 2051.00 KGS
"""

def test_packing_list_ไม่ถูกจำแนกเป็น_invoice():
    """Packing List มีคำว่า INVOICE NO. อยู่ในหัวเอกสาร
    ตัวจำแนกแบบ 'เจอคำแรกชนะ' เคยคว้าผิดเป็น Invoice"""
    r = classify(PACKING_LIST, title_text="FOSHAN XINYANG CERAMICS CO.,LTD.\nPACKING LIST")
    assert r.code == "packing_list", r
    assert r.status == "ยืนยัน"


INVOICE = """
MONTE-BIANCO DIAMOND APPLICATIONS CO., LTD.
COMMERCIAL INVOICE
TO: SOSUCO CERAMIC CO., LTD.
INVOICE NO.: MBCIC2606005   DATE: AUG.06,2026
TERMS OF PAYMENT: T/T AT 30 DAYS FROM B/L DATE.
ITEM NO. DESCRIPTION OF GOODS SPECIFICATIONS QUANTITY UNIT PRICE AMOUNT
1 DRY SILICON CARBIDE CHAMFERING WHEEL-MY3 150# RIGHT 36 1.28 46.08
TOTAL EXW,CHINA AMOUNT: 184.32
TOTAL AMOUNT: SAY U.S.DOLLARS ONE HUNDRED AND EIGHTY-FOUR AND CENTS THIRTY-TWO ONLY.
BENEFICIARY NAME: MONTE-BIANCO DIAMOND APPLICATIONS CO., LTD
"""

def test_invoice():
    r = classify(INVOICE, title_text="MONTE-BIANCO DIAMOND APPLICATIONS CO., LTD.\nCOMMERCIAL INVOICE")
    assert r.code == "invoice" and r.status == "ยืนยัน", r


# ---------- หัวเรื่องเป็นภาพ ไม่ใช่ข้อความ ----------
BL_TEXT_LAYER_ONLY = """
LSZPAT2607607
MONTE-BIANCO DIAMOND APPLICATIONS CO., LTD.
NO.7,8TH XINGYE ROAD, CHENCUN INDUSTRIAL ZONE,
SOSUCO CERAMIC CO., LTD.
33/2 M.2, RIM-KLONG RAPEEPAT RD.,NONGPLING,
MASS POWER LOGISTICS CO., LTD
SAME AS CONSIGNEE
FOSHAN,CHINA
SHENZHEN,CHINA
BANGKOK,THAILAND
1 PALLET
125.000KGS
DRY SILICON CARBIDE CHAMFERING WHEEL-MY3
"""

def test_bl_ที่หัวเรื่องเป็นภาพ_ต้องไม่เดา():
    """B/S ของชุด 3 และ 5 วางหัวเรื่องเป็นภาพ text layer จึงมีแต่ที่อยู่
    ระบบต้องบอกว่าไม่มั่นใจ ไม่ใช่เดาเป็น Packing List"""
    r = classify(BL_TEXT_LAYER_ONLY, title_text="LSZPAT2607607")
    assert r.status == "ต้องให้คนยืนยัน", r
    assert r.code == "unknown"


BL_FULL = """
OCEAN-BILL OF LADING
Shipper ZHEJIANG HENGYUAN SANITARY WARE CO., LTD
B/L NO ODIN26082502
XIAMEN ODIN LOGISTICS CO. LTD
Consignee SIAM SANITARY WARE INDUSTRY CO., LTD.
Notify party SAME AS CONSIGNEE
Pre-Carriage by   Place of receipt
Ocean Vessel Voy No. COSCO TAICANG V.110W
Port of loading NINGBO ,CHINA
Port of discharge LAEM CHABANG, THAILAND
Place of delivery LAT KRABANG, THAILAND
SHIPPED ON BORAD AUG 07, 2026
Total No.of Containers or Packages (in words) SAY TOTAL:ONE TWENTY FT. GP CONTAINER ONLY.
FREIGHT COLLECT
No.of original B(s)/L THREE (3)
NON-NEGOTIABLE
"""

def test_bl_เมื่ออ่านหัวเรื่องได้():
    """ชื่อเรื่องเขียน OCEAN-BILL OF LADING (มีขีด) ต้องเทียบติดกับ OCEAN BILL OF LADING"""
    r = classify(BL_FULL, title_text="OCEAN-BILL OF LADING\nShipper")
    assert r.code == "bill_of_lading" and r.status == "ยืนยัน", r


FORM_E = """
Original
1.Products consigned from(Exporter's business name,address, country)
Reference No. E26MA51WHNF70244
ASEAN-CHINA FREE TRADE AREA
PREFERENTIAL TARIFF
CERTIFICATE OF ORIGIN
(Combined Declaration and Certificate)
FORM E
Issued in THE PEOPLE'S REPUBLIC OF CHINA
See Overleaf Notes
5.Item number 6.Marks and numbers on packages 7.Number and type of packages
8.Origin criteria (see Overleaf Notes)
11.Declaration by the exporter
13. Issued Retroactively   Exhibition   Movement Certificate   Third Party Invoicing
"""

def test_form_co():
    r = classify(FORM_E, title_text="Original\nReference No. E26MA51WHNF70244\nCERTIFICATE OF ORIGIN\nFORM E")
    assert r.code == "form_co" and r.status == "ยืนยัน", r


FREIGHT = """
MASS POWER LOGISTICS CO.,LTD.
FREIGHT INVOICE
Please delivery to Messrs. SCG CERAMICS PUBLIC COMPANY LIMITED
VESSEL : RESURGENCE V.2614S    PORT OF LOADING : NINGBO,CHINA
ETD : 25/07/2026   ETA : 10/08/2026   DESTINATION : BANGKOK,THAILAND
HOUSE B/L : NBXCL2607114   NEW B/L : SITGNBBKC507397D
NO OF PACKING : 2 PALLETS   CBM : 2.850   TERM : FOB
OCEAN FREIGHT 5.70
Total Amount In USD 5.70
"""

def test_freight_invoice_ไม่ถูกจำแนกเป็น_invoice():
    """ใบค่าระวางมีคำว่า INVOICE เหมือนกัน ต้องแยกออกจาก Commercial Invoice ได้"""
    r = classify(FREIGHT, title_text="MASS POWER LOGISTICS CO.,LTD.\nFREIGHT INVOICE")
    assert r.code == "freight_invoice" and r.status == "ยืนยัน", r


POLICY = """
THE DEVES INSURANCE PUBLIC COMPANY LIMITED
MARINE CARGO POLICY SCHEDULE
Policy No. 00/2026-O0771839-CMI
Name of Assured : SCG CERAMICS PUBLIC COMPANY LIMITED
Vessel : RESURGENCE V.2614S   Sailing on or about : 02/08/2026
Voyage : At and from NINGBO, CHINA TO BANGKOK
Amount Insured hereunder : Equal to (324,409.52+10.00%) THB 356,850.47@1.0000
Subject-matter insured: 2 PALLETS (2,051.00 GS.)
INSTITUTE CARGO CLAUSES (A) 1/1/09, INSTITUTE WAR CLAUSES
Valued at the same as Amount insured.
"""

def test_marine_policy():
    r = classify(POLICY, title_text="THE DEVES INSURANCE PUBLIC COMPANY LIMITED\nMARINE CARGO POLICY SCHEDULE")
    assert r.code == "marine_policy" and r.status == "ยืนยัน", r


INS_INVOICE = """
THE DEVES INSURANCE PUBLIC COMPANY LIMITED
Invoice
Insured Name & Address
SCG CERAMICS PUBLIC COMPANY LIMITED
Date 13/08/2026
Sum Insured 356,850.47
Premium / Others 500.00
Stamp Duty 2.00
VAT 35.14
Total 537.14
Period of Insurance From 02/08/2026
INVOICE NO.26SYCI-RM026
"""

def test_ใบแจ้งหนี้เบี้ยประกัน_ไม่ถูกจำแนกเป็นกรมธรรม์():
    r = classify(INS_INVOICE, title_text="THE DEVES INSURANCE PUBLIC COMPANY LIMITED\nInvoice")
    assert r.code == "insurance_invoice" and r.status == "ยืนยัน", r


# ---------- ชนิดเอกสารที่เพิ่มจากงานจริงชุดที่สอง ----------
# ข้อความทั้งหมดคัดมาจากผล OCR จริง รวมทั้งที่ภาษาไทยตกวรรณยุกต์

INVOICE_TITLE_ONLY = """
HUANYU HOSE CO.,LTD.
No.367, Sec. 3, Zhongshan Rd., Tanzi Dist., Taichung City 427,Taiwan (R.O.C.)
INVOICE No. 260817 - HUANYU HOSE   Dated: August 17, 2026
INVOICE of AS BELOW
ATTN: Mrs.Wongchantra  31/5 M.6 T.LADSAWAI, LUMLUKKA, PATHUMTHANI 12150 THAILAND
DESCRIPTION OF GOODS   QUANTITY   UNIT PRICE   AMOUNT
"""

def test_invoice_ที่หัวเรื่องเขียนแค่_INVOICE():
    """ผู้ขายหลายรายไม่เขียนคำว่า COMMERCIAL หัวเรื่องเป็น INVOICE เฉย ๆ"""
    r = classify(INVOICE_TITLE_ONLY,
                 title_text="HUANYU HOSE CO.,LTD.\nINVOICE No. 260817 - HUANYU HOSE")
    assert r.code == "invoice" and r.status == "ยืนยัน", r


def test_หัวเรื่องหลุดโซนเพราะหัวจดหมายสูง():
    """หัวจดหมายยาวจนคำว่า COMMERCIAL INVOICE ตกลงไปใต้โซนหัวเรื่อง
    ยังต้องจำแนกได้ เพราะไม่มีเอกสารชนิดอื่นใช้วลีนี้"""
    txt = ("NINGBO WANHAI CARTRIDGE TECHNOLOGY CO., LTD\n"
           "XIACHEN DEVELOPMENT ZONE,CHUNHU ,FENGHUA,NINGBO,CHINA\n"
           "TEL: 0086-574-56372919 FAX: 0086-574-88762638\n"
           "COMMERCIAL INVOICE\n2026/8/5\nINVOICE NO:WHSCG2608-6844-AUG\n"
           "TO: THE SIAM SANITARY FITTINGS CO., LTD Branch No, 00004\n")
    r = classify(txt, title_text="NINGBO WANHAI CARTRIDGE TECHNOLOGY CO., LTD")
    assert r.code == "invoice" and r.status == "ยืนยัน", r


DO_THAI = """
ใบแจงสินคาขาเขา (D/O)  หมายเลข Air Waybill: 876555946507
เรียน: SCG LIVING AND HOUSING SOLUTION
บรษท: SCG LIVING AND HOUSING SOLUTION CO., LTD.
หมายเลขแฟกซ:  จํานวนหนา: 3 (รวมเอกสารฉบับนี่)
บริษัท เฟดเดอรัล เอ็กซเพรส (ประเทศไทย) จํากัด ขอแจงสินคาขาเขา ณ ทาอากาศยานสุวรรณภูม
"""

def test_ใบแจ้งสินค้าขาเข้า_do():
    r = classify(DO_THAI, title_text="ใบแจงสินคาขาเขา (D/O) หมายเลข Air Waybill: 876555946507")
    assert r.code == "delivery_order" and r.status == "ยืนยัน", r


AWB = """
02353231102, 876555946507, FX6159, 02-09-26, 2KG, 1
From: 88623695855  Origin ID: TREA   Ship Date: 01SEP26
Abbie KAO  ActWgt: 2,00 KG
thingnario Co, Ltd, Express | CAD: 2510800141NET4535
7F., No. 81, Sec. 2, Nanchang Rd., Zhongzheng Dist.,  REF: ES009199
TAIPEI CITY, 100   DESC-1: data logger
"""

def test_ป้ายพัสดุทางอากาศ():
    """ป้ายของผู้ให้บริการไม่มีคำว่า AIR WAYBILL อยู่บนหน้า ต้องยึดคำเฉพาะของป้ายแทน"""
    r = classify(AWB, title_text="02353231102, 876555946507, FX6159, 02-09-26, 2KG, 1")
    assert r.code == "air_waybill" and r.status == "ยืนยัน", r


PERMIT_TISI = """
TISI  Permit Number : 20260826040000028220
หลักฐานการรับแจงขอมูลการนําเขาผลิตภัณฑอุตสาหกรรมที่มีกฎหมาย
กําหนดใหตองเปนไปตามมาตรฐานเขามาในราชอาณาจักร
ชื่อผู้นําเข้า : บริษัท โตโต (ประเทศไทย) จํากัด
เลขที่บัญชีราคาสินค้า : INVHY-260265 (Invoice Number)
"""

def test_หลักฐานการรับแจ้ง_มอก():
    r = classify(PERMIT_TISI,
                 title_text="TISI Permit Number : หลักฐานการรับแจงขอมูลการนําเขาผลิตภัณฑอุตสาหกรรม")
    assert r.code == "permit" and r.status == "ยืนยัน", r


TOKIO = """
Tokio Marine Safety Insurance (Thailand) PCL.
บมจ. โตเกียวมารีนประกันภัย (ประเทศไทย)
S&A Building, No. 302, Silom Road, Khwaeng Suriyawong, Khet Bangrak, Bangkok 10500
กรมธรรม์เลขที่ Policy No. P-0-90-60/000008
เบี้ยประกันภัย  อากรแสตมป์  ภาษีมูลค่าเพิ่ม  ยอดรวม
ระยะเวลาประกันภัย
"""

def test_ใบแจ้งหนี้ประกันของบริษัทอื่น():
    """บริษัทประกันแต่ละรายใช้ฟอร์มคนละแบบ ต้องไม่ผูกกับ Deves รายเดียว"""
    r = classify(TOKIO, title_text="Tokio Marine Safety Insurance (Thailand) PCL.")
    assert r.code == "insurance_invoice" and r.status == "ยืนยัน", r


def test_ใบแจ้งหนี้ประกันภาษาไทย_ที่หัวเรื่องเขียนว่า_Invoice():
    """หลังเพิ่ม INVOICE เป็นคำหัวเรื่องของ Commercial Invoice
    ใบแจ้งหนี้เบี้ยประกันภาษาไทยเกือบถูกแย่งไป ต้องมีคำขัดแย้งภาษาไทยกัน"""
    txt = TOKIO + "\nInvoice / ใบแจ้งหนี้\nจำนวนเงินรวม 1,234.56"
    r = classify(txt, title_text="Tokio Marine Safety Insurance (Thailand) PCL.  Invoice")
    assert r.code == "insurance_invoice" and r.status == "ยืนยัน", r



# ---------- คำว่า INVOICE เดี่ยว ๆ ต้องไม่ไปแย่งชนิดเอกสารอื่น ----------
# ทั้งสองเคสเป็นการถอยหลังจริงที่เกิดขึ้นตอนเพิ่ม INVOICE เป็นคำหัวเรื่อง

PL_WITH_INVOICE_NO = """
SHANGHAI YUSON INDUSTRY CO., LTD.
F1 Floor, Building 9, No. 1568 Changyang Road, 200082, Shanghai, China
PACKING LIST
TO : THE SIAM SANITARY FITTINGS CO., LTD. (Branch No. 00004)
INVOICE NO. : INV2609134   PAYMENT TERMS : T/T
DESCRIPTION OF GOODS   CARTONS   PALLET
"""

def test_packing_list_ที่มี_INVOICE_NO_ในโซนหัวเรื่อง():
    """Packing List แทบทุกใบมี INVOICE NO. อยู่หัวเอกสาร
    คำว่า INVOICE เดี่ยว ๆ จึงต้องไม่จับ 'INVOICE NO.'"""
    r = classify(PL_WITH_INVOICE_NO,
                 title_text="SHANGHAI YUSON INDUSTRY CO., LTD.\nPACKING LIST\nINVOICE NO. : INV2609134")
    assert r.code == "packing_list" and r.status == "ยืนยัน", r


PRE_INVOICE = """
MANDIGE LINE COMPANY LIMITED
PRE-INVOICE ( USD )
INVOICE TO: บริษัท เบลเมกส์ไทย จำกัด
PRE-INVOICE NO. : 282609-0002   DATE : 02/09/2026
SHIPMENT NO. : 812609-0010-01   MASTER JOB NO. : 812609-0010
SEA FREIGHT   ETD   ETA   FEEDER   TOTAL AMOUNT
"""

def test_ใบแจ้งหนี้ค่าระวางล่วงหน้า_ต้องไม่กลายเป็น_invoice():
    """PRE-INVOICE ของสายเรือ เคยถูกจำแนกถูกอยู่แล้ว
    แล้วถอยหลังตอนเพิ่ม INVOICE เป็นคำหัวเรื่อง"""
    r = classify(PRE_INVOICE, title_text="MANDIGE LINE COMPANY LIMITED  PRE-INVOICE ( USD )")
    assert r.code == "freight_invoice" and r.status == "ยืนยัน", r


# ---------- เอกสารที่รวม Invoice กับ Packing List ----------
COMBINED = """
VORETO INDUSTRY CO., LTD.
COMMERCIAL INVOICE AND PACKING LIST
INVOICE NO.: VRT-2608   DATE: 24/08/2026
ITEM  DESCRIPTION  QTY  UNIT PRICE  AMOUNT  CTNS  N.W.(KGS)  G.W.(KGS)  CBM
1  BASIN MIXER  100  27.1800  2,718.00  10  120.50  135.00  1.20
TOTAL  304  1602  $26,947.32  3,841.26  4,750.64  24.27
SAY TOTAL U.S.DOLLARS TWENTY SIX THOUSAND ...
"""

def test_เอกสารที่รวม_invoice_กับ_packing_list():
    """ผู้ขายหลายรายทำใบเดียวมีทั้งราคาและน้ำหนัก ผู้ใช้ยืนยันว่าเจอเป็นปกติ
    ต้องไม่บังคับให้เลือกข้างใดข้างหนึ่ง"""
    r = classify(COMBINED, title_text="VORETO INDUSTRY CO., LTD.\nCOMMERCIAL INVOICE AND PACKING LIST")
    assert r.code == "invoice_packing_list" and r.status == "ยืนยัน", r


def test_invoice_ธรรมดา_ต้องไม่ถูกยกระดับ():
    r = classify(INVOICE, title_text="MONTE-BIANCO DIAMOND APPLICATIONS CO., LTD.\nCOMMERCIAL INVOICE")
    assert r.code == "invoice", r


def test_packing_list_ธรรมดา_ต้องไม่ถูกยกระดับ():
    r = classify(PACKING_LIST, title_text="FOSHAN XINYANG CERAMICS CO.,LTD.\nPACKING LIST")
    assert r.code == "packing_list", r


# ---------- หน้าที่อ่านไม่ได้ ต้องไม่ถูกเดา ----------
def test_หน้าว่าง():
    r = classify("")
    assert r.code == "unreadable" and r.status == "อ่านหน้านี้ไม่ได้"


def test_ข้อความน้อยเกินไป():
    r = classify("INVOICE 12345 TOTAL 100")
    assert r.code == "unreadable"


def test_ไม่มีหลักฐานพอ_ต้องไม่เดา():
    txt = " ".join(["บริษัท เอบีซี จำกัด 123 ถนนสุขุมวิท กรุงเทพมหานคร 10110"] * 5)
    r = classify(txt)
    assert r.status == "ต้องให้คนยืนยัน" and r.code == "unknown"


DECLARATION = """
DRAFT
ใบขนสินค้าขาเข้าพร้อมแบบแสดงรายการภาษีสรรพสามิตและภาษีมูลค่าเพิ่ม
กศก. 99/1   PPFE000015331   ใบต่อแผ่นที่ 2/2
รายการที่ ประเภทพิกัด ราคาของเงินตราต่างประเทศ อัตราอากรขาเข้า ฐานภาษีมูลค่าเพิ่ม
3920.43.10  CNY 12,903.75  รหัสสถิติ 090/KGM  น้ำหนักสุทธิ 392.557 KGM
Pack(Inv.)= CNY 354.90 = THB 1,783.23   F= USD 1.12 = THB 37.91   I= THB 105.91
invno# 26SYCI-RM026   OriginCriteria. PE
CIF รวม CNY 65,446.15   TERM : FOB   รวมค่าภาษีอากรทั้งสิ้น 23,069.96
"""


def test_ใบขนสินค้าขาเข้า():
    r = classify(DECLARATION, title_text="DRAFT\nใบขนสินค้าขาเข้าพร้อมแบบแสดงรายการภาษีสรรพสามิตและภาษีมูลค่าเพิ่ม")
    assert r.code == "import_declaration" and r.status == "ยืนยัน", r


def test_ใบขน_อ่านได้แม้ไม่มีภาษาไทย():
    """OCR ที่ไม่มีชุดภาษาไทยจะได้แต่ข้อความละติน — ต้องยังจำแนกได้"""
    latin_only = """
    DRAFT  PPFE000015331  A0170690800911
    3920.43.10  CNY 12,903.75  090/KGM  392.557 KGM  4,035.000 MTR
    Pack(Inv.)= CNY 354.90 = THB 1,783.23  F= USD 1.12 = THB 37.91  I= THB 105.91
    invno# 26SYCI-RM026   OriginCriteria. PE   CIF  TERM : FOB
    E26MA51WHNF70244  SPC DECO FILM JS21080-1
    """
    r = classify(latin_only, title_text="DRAFT PPFE000015331")
    assert r.code == "import_declaration", r


# ---------- ฟังก์ชันช่วย ----------
def test_normalize_ขีดคั่น():
    assert normalize("OCEAN-BILL OF LADING") == "OCEAN BILL OF LADING"
    assert normalize("  ocean   bill  ") == "OCEAN BILL"


def test_despace_หัวเรื่องเว้นวรรคทีละตัว():
    assert despace(normalize("P A C K I N G   L I S T")) == "PACKINGLIST"


def test_ทุกชนิดเอกสารมีเทสต์():
    """กันลืม: ถ้าเพิ่มชนิดเอกสารใหม่ใน RULES ต้องเพิ่มเทสต์ด้วย"""
    from customs_checker.doctype import RULES
    covered = {"invoice", "packing_list", "bill_of_lading", "form_co",
               "freight_invoice", "marine_policy", "insurance_invoice",
               "import_declaration", "delivery_order", "air_waybill", "permit"}
    assert {r.code for r in RULES} == covered, "มีชนิดเอกสารใหม่ที่ยังไม่มีเทสต์"
