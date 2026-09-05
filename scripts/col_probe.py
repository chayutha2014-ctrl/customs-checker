#!/usr/bin/env python3
"""ดูว่าเซลล์ไหนถูกจัดเข้าคอลัมน์ตัวเลขไหน และแถวไหนไม่มีค่าในคอลัมน์จำนวนเงิน

อ่านจาก _box_cache.json อย่างเดียว ไม่แก้ไขอะไร

ใช้:  python scripts/col_probe.py HUANYU
      python scripts/col_probe.py HUANYU 269        เน้นแถวที่มีข้อความนี้
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customs_checker import tables as T            # noqa: E402
from customs_checker.numbers import parse_number   # noqa: E402


def box_of(cell):
    for attr in ("x0", "x1"):
        if not hasattr(cell, attr):
            return None
    return cell.x0, cell.x1


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    stem = args[0] if args else "HUANYU"
    focus = args[1] if len(args) > 1 else None

    cache = json.loads((ROOT / "docs_out" / "_box_cache.json").read_text())
    keys = sorted(k for k in cache
                  if k.split("/")[0] == stem and k.lower().endswith(".png"))

    for key in keys:
        rows = T.group_rows(T.to_cells(cache[key]))
        cols = T.numeric_columns(rows)
        print(f"\n### {key}   {len(rows)} แถว   {len(cols)} คอลัมน์ตัวเลข")

        for ci, col in enumerate(cols):
            xs = []
            for cell in col.values():
                b = box_of(cell)
                if b:
                    xs.append(b)
            if xs:
                lo = min(a for a, _ in xs)
                hi = max(b for _, b in xs)
                print(f"  คอลัมน์ {ci}: {len(col):3d} ค่า   x {lo:7.1f} - {hi:7.1f}   "
                      f"ตัวอย่าง {[parse_number(getattr(c, 'text', c)) for c in list(col.values())[:4]]}")
            else:
                print(f"  คอลัมน์ {ci}: {len(col):3d} ค่า")

        print("\n  แถวที่มีตัวเลขแต่ไม่ครบทุกคอลัมน์")
        for ri, row in enumerate(rows):
            cells = getattr(row, "cells", row)
            txt = " | ".join(str(getattr(c, "text", c)) for c in cells)
            here = {ci for ci, col in enumerate(cols) if ri in col}
            nums = [c for c in cells if parse_number(getattr(c, "text", c)) is not None]
            if not nums:
                continue
            interesting = (focus and focus in txt) or (here and len(here) < len(cols))
            if not interesting:
                continue
            mark = " <<<" if focus and focus in txt else ""
            print(f"    แถว {ri:3d} อยู่ในคอลัมน์ {sorted(here)}{mark}")
            print(f"          {txt[:110]}")
            for c in cells:
                b = box_of(c)
                v = parse_number(getattr(c, "text", c))
                if v is not None and b:
                    mid = (b[0] + b[1]) / 2
                    print(f"            {str(getattr(c, 'text', c))[:22]:<24} "
                          f"x {b[0]:7.1f} - {b[1]:7.1f}  กลาง {mid:7.1f}  ค่า {v}")


if __name__ == "__main__":
    main()
