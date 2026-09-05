# -*- coding: utf-8 -*-
"""รวมหน้าที่ต่อเนื่องกันให้เป็น "เอกสารหนึ่งฉบับ" และประเมินสภาพหน้ากระดาษ

ทำไมรวมด้วยชนิดเอกสารอย่างเดียวไม่ได้
  Form E ของ ACFTA พิมพ์หัวเรื่องซ้ำทุกแผ่น (ชุด 1 กิน 3 แผ่น ทุกแผ่นมีคำว่า FORM E)
  จึงใช้ "มีหัวเรื่อง = ขึ้นฉบับใหม่" ไม่ได้
  ต้องใช้ "เลขประจำตัวเอกสาร" เป็นตัวตัด — เลขต่างกันคือคนละฉบับ
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

import unicodedata


def _norm_id(text: str) -> str:
    """ตัวพิมพ์ใหญ่ + ยุบช่องว่าง แต่ **เก็บขีดกลางไว้**

    doctype.normalize() แปลงขีดเป็นช่องว่างเพื่อให้ OCEAN-BILL = OCEAN BILL
    แต่เลขเอกสารมีขีดเป็นส่วนหนึ่งของเลข (26SYCI-RM026, 00/2026-O0771839-CMI)
    ถ้าใช้ตัวเดียวกันจะตัดเลขขาดกลางคัน
    """
    t = unicodedata.normalize("NFC", text or "").upper()
    return re.sub(r"[ \t]+", " ", t.replace("\u2013", "-").replace("\u2014", "-"))

# ---------- เลขประจำตัวเอกสารของแต่ละชนิด ----------
# กลุ่มที่ 1 ของ regex คือค่าที่ใช้เป็นตัวตัด
IDENTITY: dict[str, tuple[str, ...]] = {
    # \s ห้ามใช้ — มันข้ามบรรทัดได้ ทำให้คว้าข้อความบรรทัดถัดไปมาเป็นเลขเอกสาร
    "form_co":            (r"REFERENCE[ \t]*NO\.?[ \t]*:?[ \t]*([A-Z0-9]{10,24})",),
    "invoice":            (r"INV(?:OICE)?[ \t]*NO\.?[ \t]*:?[ \t]*([A-Z0-9][A-Z0-9\-/]{3,24})",),
    "packing_list":       (r"INV(?:OICE)?[ \t]*NO\.?[ \t]*:?[ \t]*([A-Z0-9][A-Z0-9\-/]{3,24})",),
    "bill_of_lading":     (r"B[ \t]*/[ \t]*L[ \t]*NO\.?[ \t]*:?[ \t]*([A-Z0-9][A-Z0-9\-/]{5,24})",),
    "freight_invoice":    (r"INVOICE[ \t]*NO\.?[ \t]*:?[ \t]*([A-Z0-9][A-Z0-9\-/]{3,24})",
                           r"JOB[ \t]*(?:NO)?\.?[ \t]*:?[ \t]*([A-Z0-9][A-Z0-9\-/]{3,24})"),
    "marine_policy":      (r"POLICY[ \t]*NO\.?[ \t]*:?[ \t]*([A-Z0-9][A-Z0-9\-/]{5,30})",),
    "insurance_invoice":  (r"POLICY[ \t]*NO\.?[ \t]*:?[ \t]*([A-Z0-9][A-Z0-9\-/]{5,30})",
                           r"กรมธรรม์เลขที่[ \t]*:?[ \t]*([A-Z0-9][A-Z0-9\-/]{5,30})",),
    "import_declaration": (r"\b(PPFE\d{6,})\b", r"\b(A\d{15,})\b"),
}

# ---------- ตัวบอกลำดับแผ่นที่พิมพ์อยู่บนเอกสาร ----------
# แยกเป็น 2 ชั้นความน่าเชื่อถือ
#   ชัดเจน  = มีคำว่า แผ่นที่ / PAGE / SHEET กำกับ  เชื่อได้
#   เปล่า   = แค่ "2 of 3" ลอย ๆ  อาจไปคว้าตัวเลขอื่นในหน้ามาได้
PAGE_MARKERS_EXPLICIT = (
    r"ใบต่อแผ่นที่[ \t]*(\d+)[ \t]*/[ \t]*(\d+)",
    r"แผ่นที่[ \t]*(\d+)[ \t]*(?:/|จาก|OF)[ \t]*(\d+)",
    r"PAGE[ \t]*(\d+)[ \t]*(?:OF|/)[ \t]*(\d+)",
    r"SHEET[ \t]*(\d+)[ \t]*(?:OF|/)[ \t]*(\d+)",
)
PAGE_MARKERS_BARE = (
    r"\b(\d+)[ \t]+OF[ \t]+(\d+)\b",
)
MAX_SHEETS = 20          # เอกสารชุดเดียวเกินนี้ถือว่าจับตัวเลขผิด
BARE_LINE_MAX = 40       # "2 of 2" ที่เป็นเลขหน้าจริงมักอยู่บนบรรทัดสั้น ๆ ท้ายหน้า


def page_marker(text: str):
    """คืน (แผ่นที่, จากทั้งหมด, ชั้นความน่าเชื่อถือ) หรือ None

    ชั้นความน่าเชื่อถือ: 'ชัดเจน' | 'เปล่า'
    """
    n = _norm_id(text)
    for pat in PAGE_MARKERS_EXPLICIT:
        m = re.search(pat, n)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if 1 <= a <= b <= MAX_SHEETS:
                return a, b, "ชัดเจน"
    for line in n.splitlines():
        t = line.strip()
        if len(t) > BARE_LINE_MAX:
            continue                       # บรรทัดยาว = เนื้อหา ไม่ใช่เลขหน้า
        for pat in PAGE_MARKERS_BARE:
            m = re.search(pat, t)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                if 1 <= a <= b <= MAX_SHEETS:
                    return a, b, "เปล่า"
    return None


def expected_sheets(marks: list) -> tuple[int | None, str]:
    """สรุปจำนวนแผ่นที่เอกสารพิมพ์บอกไว้ จากตัวบอกทุกตัวที่เจอในฉบับนั้น

    OCR อ่านเลขผิดได้ (3 กับ 8 สลับกันบ่อย) จึงใช้เสียงข้างมาก
    ตัวอย่างจริง: Form E 3 แผ่น อ่านได้ 1/8, 2/3, 3/3 -> ตอบ 3
    แต่ถ้าไม่มีเสียงข้างมากชัดเจน ให้ตอบว่าไม่รู้ ดีกว่าฟันธงเลขที่ผิด
    """
    if not marks:
        return None, ""
    explicit = [m for m in marks if m[2] == "ชัดเจน"]
    pool = explicit or marks
    counts: dict[int, int] = {}
    for _, b, _k in pool:
        counts[b] = counts.get(b, 0) + 1
    if len(counts) == 1:
        return next(iter(counts)), ""

    top = max(counts, key=lambda k: counts[k])
    others = [v for k, v in counts.items() if k != top]
    seen = ", ".join(f"{a}/{b}" for a, b, _ in pool)
    if counts[top] >= 2 and counts[top] > max(others):
        return top, f"ตัวเลขลำดับแผ่นไม่ตรงกันทุกแผ่น ({seen}) ใช้เสียงข้างมาก"
    return None, f"ตัวเลขลำดับแผ่นในเอกสารขัดกันเอง ({seen}) เชื่อไม่ได้"


# คำที่บอกว่า OCR เอาข้อความสองคอลัมน์มาต่อกันเป็นบรรทัดเดียว
# เช่น "MUANG, BANGKOK 10210 THAILAND: INV NO.: 004009112224"
# เลขที่ได้จากบรรทัดแบบนี้เชื่อไม่ได้ เพราะอาจถูกตัดหัวหรือต่อท้ายด้วยเลขอื่น
MERGE_HINTS = ("THAILAND", "BANGKOK", "ROAD", "RD.", "MUANG", "CHINA",
               "TEL", "FAX", "TAX ID", "ADD:")


def identity(code: str, text: str) -> tuple[str | None, str]:
    """ดึงเลขประจำตัวเอกสาร คืน (เลข, สถานะ)

    สถานะ: 'ยืนยัน' | 'ไม่ชัด' | 'ไม่พบ'
    'ไม่ชัด' = หาเจอแต่บรรทัดนั้นมีร่องรอยว่า OCR รวมคอลัมน์ หรือรูปแบบไม่น่าเชื่อถือ
    """
    n = _norm_id(text)
    for pat in IDENTITY.get(code, ()):
        m = re.search(pat, n)
        if not m:
            continue
        v = m.group(1).strip(" .:-/")
        if len(v) < 4:
            continue
        line = n[n.rfind("\n", 0, m.start()) + 1:]
        line = line[:line.find("\n") if "\n" in line else len(line)]
        head = line[:m.start() - (n.rfind("\n", 0, m.start()) + 1)]
        if any(w in head for w in MERGE_HINTS):
            return v, "ไม่ชัด"          # OCR รวมคอลัมน์ — เลขอาจถูกตัดหัว/ต่อท้าย
        if v.isdigit() and len(v) >= 11:
            return v, "ไม่ชัด"          # ตัวเลขล้วนยาว ๆ มักเป็นเบอร์โทร/เลขผู้เสียภาษีที่หลุดมา
        return v, "ยืนยัน"
    return None, "ไม่พบ"


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def same_identity(a: str, b: str) -> tuple[str, int]:
    """เลขเอกสารสองตัวเป็นฉบับเดียวกันหรือไม่ คืน (คำตัดสิน, ระยะห่าง)

    คำตัดสิน: 'เดียวกัน' | 'น่าจะเดียวกัน' | 'ต้องให้คนดู' | 'ต่างกัน'

    ปัญหา: ความคลาดของ OCR กับเลขเอกสารที่ออกเรียงกัน หน้าตาเหมือนกันมาก
      OCR คลาด : E26MA2XUF8X60147 -> E26MA2XUFS8X60147   (แทรกตัวอักษร ความยาวเปลี่ยน)
      คนละฉบับ : E26MA2XUF8X60147 -> E26MA2XUF8X60148     (แทนที่ตัวท้าย ความยาวเท่าเดิม)

    จึงใช้ "ความยาวเปลี่ยนหรือไม่" เป็นตัวแยก
      ความยาวต่างกัน + ห่างน้อย  = OCR แทรก/ตกตัวอักษร -> ถือว่าฉบับเดียวกัน แต่ติดธง
      ความยาวเท่ากัน + ต่างกัน   = อาจเป็นคนละฉบับ -> **แยกไว้ก่อน** แล้วให้คนดู

    ทำไมจึงเลือกแยกเมื่อไม่แน่ใจ: การรวมเอกสารสองฉบับเป็นฉบับเดียว ทำให้เอกสาร
    หนึ่งฉบับหายไปจากการตรวจโดยไม่มีใครรู้ (ข้อผิดเงียบ) ส่วนการแยกฉบับเดียวเป็น
    สองฉบับ จะเห็นชัดว่าเอกสารไม่ครบ แก้ได้
    """
    if a == b:
        return "เดียวกัน", 0
    d = _edit_distance(a, b)
    if d > max(2, int(len(a) * 0.15)):
        return "ต่างกัน", d
    if len(a) != len(b):
        return "น่าจะเดียวกัน", d      # แทรก/ตก = ร่องรอยของ OCR
    return "ต้องให้คนดู", d            # แทนที่ = อาจเป็นเลขที่ออกเรียงกัน


# ---------- สภาพหน้ากระดาษ ----------
# วัดเพื่อบอก "ความยากในการอ่าน" เป็นหลัก
#
# ข้อสรุปจากการทดสอบกับตัวอย่าง 5 ชุด: การเดาว่าเป็นร่างหรือตัวจริงจากตัวเอกสาร
# **ยังเชื่อถือไม่ได้พอ** — ตราประทับสีบอกได้เฉพาะบางชนิดเอกสาร ส่วน B/L ตัวจริง
# ปล่อยด้วย telex จึงไม่มีตราสีเลย แยกไม่ออกจากร่าง
# ฟิลด์ "ร่าง/ตัวจริง" จึงเป็นเพียง "ข้อสังเกต" ห้ามใช้ตัดสินใจ
# ในการใช้งานจริงให้รับค่านี้เป็น input (ผู้ใช้รู้อยู่แล้วว่าเปิดชุดไหน)
COLOR_CLEAN = 0.05   # % พิกเซลที่มีสี ต่ำกว่านี้ = หน้าสะอาด
COLOR_MARK  = 0.30   # สูงกว่านี้ = มีตราประทับ/ลายเซ็นสี

DRAFT_WORDS  = ("DRAFT", "TBA", "TO BE ADVISED")
FINAL_WORDS  = ("TELEX RELEASE", "TELEX RELEASED", "SURRENDERED", "SHIPPED ON BOARD",
                "LADEN ON BOARD")


def page_condition(text: str, color_pct: float | None = None) -> dict:
    """ประเมินสภาพหน้ากระดาษ + เดาสถานะร่าง/ตัวจริงอย่างระมัดระวัง

    color_pct = สัดส่วนพิกเซลที่มีสีชัดเจน (%) ส่งมา None ได้ถ้าไม่ได้วัด
    """
    n = _norm_id(text)
    # ต้องเทียบแบบทั้งคำ — "TBA" ที่อยู่กลางคำอื่นเคยทำให้ใบแจ้งหนี้ประกันของ
    # ชุดตัวจริงถูกตัดสินเป็น "ร่าง" ผิด ๆ
    draft_hits = [w for w in DRAFT_WORDS if re.search(rf"(?<![A-Z0-9]){re.escape(w)}(?![A-Z0-9])", n)]
    final_hits = [w for w in FINAL_WORDS if re.search(rf"(?<![A-Z0-9]){re.escape(w)}(?![A-Z0-9])", n)]

    if color_pct is None:
        cond, why = "ไม่ได้วัด", []
    elif color_pct >= COLOR_MARK:
        cond, why = "มีตรา/ลายเซ็นทับ", [f"พิกเซลมีสี {color_pct:.2f}%"]
    elif color_pct <= COLOR_CLEAN:
        cond, why = "สะอาด", [f"พิกเซลมีสี {color_pct:.2f}%"]
    else:
        cond, why = "มีสีเล็กน้อย (โลโก้?)", [f"พิกเซลมีสี {color_pct:.2f}%"]

    # เดาร่าง/ตัวจริง — ต้องมีหลักฐาน 2 ทางตรงกันจึงจะยืนยัน
    stage, note = "ไม่ทราบ", "ไม่มีหลักฐานพอ"
    if draft_hits and cond != "มีตรา/ลายเซ็นทับ":
        stage, note = "ร่าง", "พบคำว่า " + ", ".join(draft_hits)
    elif cond == "มีตรา/ลายเซ็นทับ" and not draft_hits:
        stage, note = "ตัวจริง", "มีตรา/ลายเซ็นสีทับหน้า"
    elif draft_hits and cond == "มีตรา/ลายเซ็นทับ":
        stage, note = "ขัดแย้ง", "มีทั้งคำว่า DRAFT และตราประทับ ต้องให้คนดู"
    elif final_hits and cond == "สะอาด":
        stage, note = "ไม่ทราบ", "มีคำที่บอกว่าปล่อยแล้ว (" + ", ".join(final_hits[:2]) + \
                                 ") แต่ไม่มีตราสี — ตัดสินไม่ได้"

    return {"สภาพหน้า": cond, "เหตุผล": why, "ร่าง/ตัวจริง": stage, "หมายเหตุ": note}


# ---------- รวมหน้าเป็นเอกสาร ----------
@dataclass
class Doc:
    code: str
    name_th: str
    pages: list[int] = field(default_factory=list)
    ident: str | None = None
    status: str = "ยืนยัน"
    note: str = ""
    expected: int = 0        # จำนวนแผ่นที่เอกสารพิมพ์บอกไว้เอง (0 = ไม่ได้บอก)
    marks: list = field(default_factory=list)   # ตัวบอกลำดับแผ่นทุกตัวที่เจอ


def group_pages(pages: list[dict]) -> list[Doc]:
    """รวมหน้าที่ต่อเนื่องกันเป็นเอกสาร

    pages = [{'page':1,'code':'form_co','name_th':'Form CO','text':'...','status':'ยืนยัน'}, ...]
    เรียงตามเลขหน้าแล้ว
    """
    docs: list[Doc] = []
    for p in pages:
        code, txt = p["code"], p.get("text", "")
        ident, ident_ok = (identity(code, txt) if code not in ("unknown", "unreadable")
                           else (None, "ไม่พบ"))
        if ident_ok == "ไม่ชัด":
            ident = None                # ไม่เอามาใช้ตัดสิน แต่จดไว้ในหมายเหตุ
        mark = page_marker(txt)

        cur = docs[-1] if docs else None
        same = False
        why = ""

        if cur is not None and cur.code == code and code not in ("unknown", "unreadable"):
            if mark and mark[0] == 1:
                same, why = False, "หน้านี้พิมพ์ว่าเป็นแผ่นที่ 1"
            elif ident and cur.ident:
                verdict, dist = same_identity(cur.ident, ident)
                if verdict == "เดียวกัน":
                    same, why = True, "เลขเอกสารเดียวกัน"
                elif verdict == "น่าจะเดียวกัน":
                    same, why = True, (f"เลขเอกสารต่างกัน {dist} ตัวอักษรและความยาวไม่เท่ากัน"
                                       f" — น่าจะ OCR คลาด ({cur.ident} / {ident})")
                elif verdict == "ต้องให้คนดู":
                    same, why = False, (f"เลขเอกสารต่างกัน {dist} ตัวอักษรแต่ยาวเท่ากัน"
                                        f" — อาจเป็นคนละฉบับหรือ OCR คลาด"
                                        f" ({cur.ident} / {ident}) แยกไว้ก่อน")
                else:
                    same, why = False, f"เลขเอกสารต่างกัน ({cur.ident} -> {ident})"
            elif ident and not cur.ident:
                same, why = True, "แผ่นก่อนไม่มีเลข แผ่นนี้มี"
            elif not ident:
                same, why = True, "แผ่นนี้ไม่มีเลขเอกสาร ถือว่าต่อจากแผ่นก่อน"

        if same and cur is not None:
            cur.pages.append(p["page"])
            cur.ident = cur.ident or ident
            if not ident:
                cur.status = "ตรวจสอบ"
                cur.note = (cur.note + " | " if cur.note else "") + \
                           f"แผ่น {p['page']} ไม่มีเลขเอกสารยืนยัน"
            elif "OCR คลาด" in why:
                cur.status = "ตรวจสอบ"
                cur.note = (cur.note + " | " if cur.note else "") + why
        else:
            if cur is not None and "แยกไว้ก่อน" in why:
                cur.status = "ตรวจสอบ"
                cur.note = (cur.note + " | " if cur.note else "") + why
            d = Doc(code, p["name_th"], [p["page"]], ident)
            if "แยกไว้ก่อน" in why:
                d.status = "ตรวจสอบ"
                d.note = why
            if code in ("unknown", "unreadable"):
                d.status = "ตรวจสอบ"
                d.note = p.get("note", "")
            elif ident is None:
                d.status = "ตรวจสอบ"
                d.note = ("อ่านเลขเอกสารได้ไม่ชัด (OCR รวมคอลัมน์)"
                          if ident_ok == "ไม่ชัด" else
                          "ไม่พบเลขประจำตัวเอกสาร แยกฉบับไม่ยืนยัน")
            docs.append(d)

        if mark and docs:
            docs[-1].marks.append(mark)

    # ตรวจความครบ "ตอนจบ" เท่านั้น — ถ้าเช็คระหว่างทางจะฟ้องผิดทุกแผ่นที่ยังไม่ครบ
    for d in docs:
        exp, why = expected_sheets(d.marks)
        if exp:
            d.expected = exp
            d.note = (d.note + " | " if d.note else "") + f"เอกสารพิมพ์ว่ามี {exp} แผ่น"
            if why:
                d.note += f" ({why})"
            if exp != len(d.pages):
                d.status = "ตรวจสอบ"
                d.note += f" แต่ได้มา {len(d.pages)} แผ่น"
        elif why:
            d.status = "ตรวจสอบ"
            d.note = (d.note + " | " if d.note else "") + why
    return docs
