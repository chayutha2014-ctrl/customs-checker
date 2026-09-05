#!/usr/bin/env python3
"""ลบคีย์ซ้ำของหน้าเดียวกันใน _box_cache.json

ท่อเดิมตั้งคีย์ตามชื่อไฟล์ภาพจริง (.jpg/.jpeg) ส่วน build_boxes.py ตั้งเป็น .png เสมอ
cache จึงมีสองคีย์ของหน้าเดียวกันได้ แล้ว table_test2.py ซึ่งรวมทุกคีย์
ที่ขึ้นต้นด้วยชื่อไฟล์ จะนับตารางซ้ำสองรอบ ยอดรวมกลายเป็นสองเท่า (FUJIAN)

เก็บ .png ไว้ ลบนามสกุลอื่นของหน้าเดียวกัน  สำรองไฟล์เดิมเป็น .bak ก่อนเขียน

ใช้:  python scripts/clean_cache.py            ดูอย่างเดียว ไม่เขียน
      python scripts/clean_cache.py --write    เขียนจริง
"""
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOX = ROOT / "docs_out" / "_box_cache.json"


def main():
    if not BOX.exists():
        sys.exit(f"ไม่พบ {BOX}")
    cache = json.loads(BOX.read_text(encoding="utf-8"))

    groups = defaultdict(list)
    for k in cache:
        stem, _, name = k.partition("/")
        base = name.rsplit(".", 1)[0]
        groups[(stem, base)].append(k)

    drop = []
    for (stem, base), ks in sorted(groups.items()):
        if len(ks) < 2:
            continue
        keep = next((k for k in sorted(ks) if k.lower().endswith(".png")),
                    sorted(ks)[0])
        for k in sorted(ks):
            if k != keep:
                drop.append(k)
                print(f"  ซ้ำ {stem}/{base}: เก็บ {Path(keep).name}  "
                      f"ลบ {Path(k).name} ({len(cache[k])} เซลล์)")

    if not drop:
        print("ไม่พบคีย์ซ้ำ")
        return

    print(f"\nพบคีย์ซ้ำ {len(drop)} คีย์ จากทั้งหมด {len(cache)} คีย์")
    if "--write" not in sys.argv:
        print("ยังไม่เขียน  เติม --write เพื่อเขียนจริง")
        return

    shutil.copy2(BOX, BOX.with_suffix(".json.bak"))
    for k in drop:
        del cache[k]
    BOX.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"เขียนแล้ว เหลือ {len(cache)} คีย์  สำรองเดิมไว้ที่ {BOX.with_suffix('.json.bak')}")


if __name__ == "__main__":
    main()
