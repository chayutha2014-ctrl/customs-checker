#!/usr/bin/env python3
"""สรุปว่าทำไม Packing List แต่ละหน้าอ่านไม่ได้ แบบบีบให้เห็นรูปแบบร่วม

วิธีเดียวกับที่ใช้แก้ invoice ได้สำเร็จ: หาว่ายอดขาดไปเท่าไร
แล้วไล่หาว่าค่าที่ขาดตรงกับเซลล์ไหนในหน้านั้น

อ่าน _box_cache.json อย่างเดียว ไม่แก้ไขอะไร

ใช้:  python scripts/pl_why.py                       ทุกหน้าที่อ่านไม่ได้
      python scripts/pl_why.py SKM                   เฉพาะไฟล์ที่ขึ้นต้นด้วยคำนี้
      python scripts/pl_why.py --cells <คีย์เต็ม>     ดูเซลล์ดิบทั้งหน้า
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

sys.path.insert(0, str(ROOT / "scripts"))

from customs_checker.tables import (to_cells, group_rows, numeric_columns,  # noqa: E402
                                    _col_x)
from customs_checker.packing_list import (analyze_packing_list, numeric_rows,  # noqa: E402
                                          TOL)
from pl_pages import pl_documents                                           # noqa: E402

BOX = ROOT / "docs_out" / "_box_cache.json"
TITLE_ZONE = 0.22
HAS_DIGIT = re.compile(r"\d")


def unreadable_cells(rows):
    """เซลล์ที่มีตัวเลขอยู่ในข้อความ แต่ parse_number อ่านไม่ออก

    เซลล์พวกนี้คือผู้ต้องสงสัยอันดับแรกเสมอ เพราะมันหายไปจากคอลัมน์ทั้งใบ
    """
    out = []
    for ri, r in enumerate(rows):
        for c in r.cells:
            if HAS_DIGIT.search(c.text) and c.number() is None:
                out.append((ri, c))
    return out


def near_miss(cols, min_values=3):
    """สำหรับแต่ละคอลัมน์ หาแถวที่ 'น่าจะเป็นแถวรวม' ที่สุด แล้วบอกว่าขาดเท่าไร"""
    out = []
    for ci, col in enumerate(cols):
        nums = {ri: c.number() for ri, c in col.items() if c.number() is not None}
        if len(nums) < min_values:
            continue
        best = None
        for ri, total in nums.items():
            rest = [v for r, v in nums.items() if r < ri]
            gap = round(total - sum(rest), 4)
            score = abs(gap) / max(abs(total), 1.0)
            if best is None or score < best[0]:
                best = (score, ri, total, round(sum(rest), 4), gap)
        if best and best[3]:
            out.append((ci, _col_x(col), len(nums), *best[1:]))
    return sorted(out, key=lambda t: abs(t[6]) / max(abs(t[4]), 1.0))


def explain_gap(gap, rows, cols_used):
    """ค่าที่ขาดไปตรงกับเซลล์ไหนในหน้านี้"""
    hits = []
    g = abs(gap)
    if g <= TOL:
        return hits
    for ri, r in enumerate(rows):
        for c in r.cells:
            v = c.number()
            if v is not None and abs(abs(v) - g) <= max(TOL, g * 1e-4):
                hits.append(f"r{ri} «{c.text[:28]}» = {v:,g}")
    return hits[:4]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cache = json.loads(BOX.read_text(encoding="utf-8"))

    if "--cells" in sys.argv:
        key = args[0] if args else ""
        for k in sorted(cache):
            if key and key not in k:
                continue
            print(f"\n### {k}")
            for ri, r in enumerate(group_rows(to_cells(cache[k]))):
                print(f"  r{ri:<3} " + " | ".join(c.text for c in r.cells))
        return

    prefix = args[0] if args else ""
    n_pl = n_fail = 0

    for label, keys, rows, text, c in pl_documents(cache, prefix):
        n_pl += 1
        r = analyze_packing_list(rows, text)
        ok = r.total_row is not None and not r.issues
        ok = ok or ("ยืนยันด้วยยอดรวมที่เขียนเป็นข้อความ" in r.status and not r.issues)
        if ok:
            continue
        n_fail += 1

        print(f"\n{'=' * 78}\n{label}")
        if len(keys) > 1:
            print(f"  ต่อ {len(keys)} แผ่นเป็นฉบับเดียว")
        print(f"  {r.status}")

        clean = numeric_rows(rows)      # ต้องใช้ชุดเดียวกับตัวอ่าน เลขแถวจะได้ตรงกัน
        cols = numeric_columns(clean)
        nm = near_miss(cols)
        if not nm:
            print("  ไม่มีคอลัมน์ที่มีค่าถึง 3 บรรทัด — ตารางแตกตั้งแต่ต้น")
        for ci, x, n, ri, total, rest, gap in nm[:4]:
            tag = "ลงตัว" if abs(gap) <= TOL else f"ขาด {gap:,.2f}"
            print(f"  คอลัมน์ x={x:>6.0f} {n:>3} ค่า  "
                  f"ถ้าแถว {ri} ({total:,g}) เป็นยอดรวม  "
                  f"ผลบวกของแถวเหนือมัน {rest:,g}  -> {tag}")
            for h in explain_gap(gap, clean, cols):
                print(f"      ค่าที่ขาดตรงกับ {h}")

        bad = unreadable_cells(rows)
        if bad:
            print(f"  เซลล์ที่มีตัวเลขแต่อ่านไม่ออก {len(bad)} เซลล์")
            for ri, cell in bad[:6]:
                print(f"      r{ri:<3} «{cell.text[:46]}»")

    print(f"\n{'=' * 78}")
    print(f"Packing List {n_pl} ฉบับ · ยังอ่านไม่ได้หรือมีข้อขัดแย้ง {n_fail} ฉบับ")


if __name__ == "__main__":
    main()
