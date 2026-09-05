"""รวมหน้าที่ต่อเนื่องกันของ Packing List ฉบับเดียวกัน

Packing List หลายแผ่นมีแถวรวมอยู่แผ่นสุดท้ายแผ่นเดียว
ถ้าอ่านทีละแผ่น แผ่นแรกจะหาแถวรวมไม่เจอตลอดกาล และแผ่นสุดท้ายจะมีบรรทัดไม่ครบ
(IMP26002010 หน้า 5 คือ Page 1 of 2 หน้า 6 คือ Page 2 of 2)

ใช้หลักเดียวกับที่ table_test2.py ทำกับ invoice คือต่อแถวของทุกหน้าเข้าด้วยกัน
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customs_checker.tables import to_cells, group_rows      # noqa: E402
from customs_checker.doctype import classify                 # noqa: E402

TITLE_ZONE = 0.22
PL_CODES = ("packing_list", "invoice_packing_list")
_PAGENO = re.compile(r"page_(\d+)", re.I)


def page_text(rows):
    return "\n".join(r.text() for r in rows)


def title_text(rows):
    if not rows:
        return ""
    ys = [c.y0 for r in rows for c in r.cells] + [c.y1 for r in rows for c in r.cells]
    top, bottom = min(ys), max(ys)
    cut = top + (bottom - top) * TITLE_ZONE
    return "\n".join(r.text() for r in rows if r.cy <= cut)


def _page_no(key):
    m = _PAGENO.search(key)
    return int(m.group(1)) if m else -1


def pl_documents(cache, prefix="", take_all=False, join=True):
    """คืน [(ชื่อฉบับ, [คีย์], rows ที่ต่อกันแล้ว, ข้อความทั้งฉบับ, สถานะการจำแนก)]"""
    pages = []
    for k in sorted(cache):
        if not k.startswith(prefix):
            continue
        rows = group_rows(to_cells(cache[k]))
        if not rows:
            continue
        c = classify(page_text(rows), title_text(rows))
        if c.code not in PL_CODES and not take_all:
            continue
        pages.append((k, rows, c))

    if not join:
        return [(k, [k], rows, page_text(rows), c) for k, rows, c in pages]

    docs, cur = [], []
    for item in pages:
        k = item[0]
        if cur:
            pk = cur[-1][0]
            same_file = pk.split("/")[0] == k.split("/")[0]
            next_page = _page_no(k) == _page_no(pk) + 1
            if not (same_file and next_page):
                docs.append(cur)
                cur = []
        cur.append(item)
    if cur:
        docs.append(cur)

    out = []
    for group in docs:
        keys = [k for k, _, _ in group]
        rows = []
        for _, rs, _ in group:
            rows += rs
        label = keys[0] if len(keys) == 1 else f"{keys[0]} + อีก {len(keys) - 1} แผ่น"
        out.append((label, keys, rows, page_text(rows), group[0][2]))
    return out
