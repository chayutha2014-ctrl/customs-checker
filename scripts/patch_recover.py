#!/usr/bin/env python3
"""เพิ่มการกู้บรรทัดที่เซลล์จำนวนเงินเสียรูป เข้า analyze_invoice

หลักการ: ไม่เดาค่าที่อ่านไม่ออก แต่ยอมรับเมื่อ 'ตัวเลขล้วน' ของเซลล์นั้น
ขึ้นต้นตรงกับ จำนวน x ราคา ซึ่งเป็นการยืนยันจากสองทางที่ไม่เกี่ยวกัน
และรายงานทุกบรรทัดที่กู้ไว้ใน res["repaired"] เสมอ ไม่แก้เงียบ

ตรวจสอบตัวเองทุกขั้น สำรอง .bak2 ก่อนเขียน ถ้าจุดยึดไม่ตรงจะหยุดโดยไม่แตะไฟล์
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "customs_checker" / "tables.py"

HELPERS = '''

def _digits(v):
    """ตัวเลขล้วนของค่าหนึ่ง  662.70 -> "66270"   "$66270" -> "66270"   """
    import re as _re
    return _re.sub(r"\\D", "", v if isinstance(v, str) else f"{float(v):.2f}")


def recover_lines(rows, cols, qi, pi, ai, hits, min_digits=3, max_extra=3):
    """แถวที่อ่าน จำนวน กับ ราคา ได้ แต่เซลล์จำนวนเงินเสียรูป

    เสียรูปที่เจอจริงสองแบบ
      170.7023   เลขลำดับ 23 ถูกเชื่อมท้ายโดยไม่มีช่องว่าง (HUANYU)
      $66270     จุดทศนิยมหาย ของจริงคือ $662.70 (VORETO)

    ทั้งสองแบบ 'ตัวเลขล้วน' ยังขึ้นต้นตรงกับ จำนวน x ราคา
    จึงยืนยันได้โดยไม่ต้องเชื่อ OCR ของเซลล์ที่เสีย
    ส่วนกรณีที่เอกสารคิดเลขผิดจริง ตัวเลขจะไม่ขึ้นต้นตรงกัน แล้วจะไม่ถูกกู้
    การตรวจจับข้อผิดพลาดของเอกสารจึงไม่เสียไป
    """
    out = []
    for ri in sorted(set(cols[qi]) & set(cols[pi])):
        if ri in hits:
            continue
        q, p = cols[qi][ri].number(), cols[pi][ri].number()
        if not q or not p:
            continue
        amt = round(q * p, 2)
        want = _digits(amt)
        if len(want) < min_digits:
            continue
        for c in rows[ri].cells:
            if c.number() is None:
                continue
            got = _digits(c.text)
            if got.startswith(want) and 0 <= len(got) - len(want) <= max_extra:
                out.append({"row": ri, "qty": q, "price": p, "amount": amt,
                            "amount_read": c.number(), "cell": c.text,
                            "recovered": True})
                break
    return out
'''

OLD = '''    qi, pi, ai, hits = found
    for ri in sorted(hits):
        res["lines"].append({"row": ri,
                             "qty": cols[qi][ri].number(),
                             "price": cols[pi][ri].number(),
                             "amount": cols[ai][ri].number()})
    computed = round(sum(l["amount"] for l in res["lines"]), 2)
    res["computed"] = computed
    outside = [c.number() for ri, c in cols[ai].items()
               if ri not in hits and c.number()]
    res["other_totals"] = sorted(set(outside), reverse=True)[:5]'''

NEW = '''    qi, pi, ai, hits = found
    res["repaired"] = []
    for ri in sorted(hits):
        q, p = cols[qi][ri].number(), cols[pi][ri].number()
        read = cols[ai][ri].number()
        amt = round(q * p, 2)
        # ใช้ผลคูณเป็นจำนวนเงิน เพราะเป็นเลขคณิตที่แน่นอน
        # ส่วนเซลล์ที่อ่านมาอาจมีอักขระอื่นติดท้าย เช่น 415.802 ที่จริงคือ 415.80
        res["lines"].append({"row": ri, "qty": q, "price": p,
                             "amount": amt, "amount_read": read})
        if read is not None and abs(read - amt) > 0.005:
            res["repaired"].append({"row": ri, "cell": cols[ai][ri].text,
                                    "read": read, "used": amt,
                                    "why": "เซลล์จำนวนเงินมีอักขระอื่นติดมา"})

    got = recover_lines(rows, cols, qi, pi, ai, hits)
    for line in got:
        res["lines"].append(line)
        res["repaired"].append({"row": line["row"], "cell": line["cell"],
                                "read": line["amount_read"], "used": line["amount"],
                                "why": "จำนวนเงินเสียรูป ยืนยันด้วย จำนวน x ราคา"})
    res["lines"].sort(key=lambda l: l["row"])
    used = set(hits) | {l["row"] for l in got}
    computed = round(sum(l["amount"] for l in res["lines"]), 2)
    res["computed"] = computed
    outside = [c.number() for ri, c in cols[ai].items()
               if ri not in used and c.number()]
    res["other_totals"] = sorted(set(outside), reverse=True)[:5]'''


def main():
    if not TARGET.exists():
        sys.exit(f"ไม่พบไฟล์ {TARGET}")
    src = TARGET.read_text(encoding="utf-8")

    if "def recover_lines" in src:
        sys.exit("มี recover_lines อยู่แล้ว ไม่ทำอะไร")
    if "def split_glued" not in src:
        sys.exit("ต้องรัน patch_split.py ก่อน หยุดโดยไม่แตะไฟล์")

    lines = src.split("\n")

    # หาช่วงที่จะแทน ด้วยบรรทัดหัวและบรรทัดท้าย ไม่ยึดข้อความทั้งบล็อก
    starts = [i for i, l in enumerate(lines)
              if l.strip() == "qi, pi, ai, hits = found"]
    if len(starts) != 1:
        sys.exit(f"หาบรรทัด 'qi, pi, ai, hits = found' ได้ {len(starts)} แห่ง "
                 "ต้องได้ 1 แห่ง หยุดโดยไม่แตะไฟล์")
    a = starts[0]

    ends = [i for i in range(a, min(a + 30, len(lines)))
            if 'res["other_totals"]' in lines[i]]
    if not ends:
        sys.exit("ไม่พบบรรทัด res[\"other_totals\"] ภายใน 30 บรรทัดถัดไป "
                 "หยุดโดยไม่แตะไฟล์")
    b = ends[0]

    block = "\n".join(lines[a:b + 1])
    need = ['cols[qi][ri].number()', 'cols[pi][ri].number()',
            'cols[ai][ri].number()', 'res["computed"] = computed']
    missing = [n for n in need if n not in block]
    if missing:
        sys.exit(f"บล็อกที่จะแทนไม่มี {missing} หยุดโดยไม่แตะไฟล์")

    print("จะแทนบล็อกนี้ (บรรทัด "
          f"{a + 1}-{b + 1})\n" + "-" * 60)
    print(block)
    print("-" * 60)

    new_lines = lines[:a] + NEW.split("\n") + lines[b + 1:]
    new = "\n".join(new_lines)

    anchor = "def analyze_invoice(rows):"
    if anchor not in new:
        sys.exit("ไม่พบ analyze_invoice หยุดโดยไม่แตะไฟล์")
    new = new.replace(anchor, HELPERS.strip("\n") + "\n\n\n" + anchor, 1)

    compile(new, str(TARGET), "exec")

    TARGET.with_suffix(".py.bak2").write_text(src, encoding="utf-8")
    TARGET.write_text(new, encoding="utf-8")
    print(f"\nแก้ {TARGET} แล้ว  สำรองก่อนแก้ไว้ที่ {TARGET.with_suffix('.py.bak2')}")

    sys.path.insert(0, str(ROOT / "src"))
    from customs_checker.tables import _digits    # noqa: E402
    assert _digits(662.70) == "66270", _digits(662.70)
    assert _digits("$66270") == "66270"
    assert _digits("170.7023") == "1707023"
    print("ตรวจสอบหลังแก้: ผ่าน")


if __name__ == "__main__":
    main()
