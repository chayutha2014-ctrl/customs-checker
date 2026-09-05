#!/usr/bin/env python3
"""กวาดค่ากำพร้าในทุกเอกสารที่มีตัวอ่านแล้ว

ถามคำถามที่ตัวอ่านไม่เคยถาม — มีค่าอะไรบนหน้านี้ที่ยังไม่มีใครอ้างถึงบ้าง
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from customs_checker.tables import to_cells, group_rows                    # noqa: E402
from customs_checker.doctype import classify                               # noqa: E402
from customs_checker.orphan import orphan_scan                             # noqa: E402
from customs_checker.packing_list import analyze_packing_list              # noqa: E402
from customs_checker.freight_invoice import analyze_freight_invoice        # noqa: E402
from customs_checker.insurance_invoice import analyze_insurance_invoice    # noqa: E402
from customs_checker.marine_policy import analyze_marine_policy            # noqa: E402
from customs_checker.form_e import analyze_form_e                          # noqa: E402

BOX = ROOT / "docs_out" / "_box_cache.json"
TITLE_ZONE = 0.22


def page_text(rows):
    return "\n".join(r.text() for r in rows)


def title_text(rows):
    if not rows:
        return ""
    ys = [c.y0 for r in rows for c in r.cells] + [c.y1 for r in rows for c in r.cells]
    top, bottom = min(ys), max(ys)
    cut = top + (bottom - top) * TITLE_ZONE
    return "\n".join(r.text() for r in rows if r.cy <= cut)


def claimed_of(code, rows, text):
    """ค่าที่ตัวอ่านของชนิดนั้นรายงานออกมา"""
    out = []
    if code in ("packing_list", "invoice_packing_list"):
        r = analyze_packing_list(rows, text)
        for c in r.columns:
            out += [c.printed, c.computed, c.label, c.unit] + list(c.values)
        if code == "invoice_packing_list":
            # ใบรวมสองอย่าง ต้องรันทั้งสองตัวอ่าน ไม่งั้นครึ่งเอกสารไม่มีใครอ่าน
            from customs_checker.tables import analyze_invoice
            iv = analyze_invoice(rows)
            out += [iv.get("computed"), iv.get("printed")]
            for ln in iv.get("lines", []):
                out += [ln.get("qty"), ln.get("price"), ln.get("amount"),
                        ln.get("amount_read")]
    elif code == "freight_invoice":
        r = analyze_freight_invoice(rows)
        out += [r.total, r.computed] + list(r.fields.values())
        for c in r.charges:
            out += [c.f1, c.f2, c.amount]
        out += list(r.quantities.values())
    elif code == "insurance_invoice":
        r = analyze_insurance_invoice(rows)
        out += [r.premium, r.stamp, r.vat, r.total, r.sum_insured,
                r.wht, r.net_payable, r.policy_no] + list(r.dates)
    elif code == "marine_policy":
        r = analyze_marine_policy(rows)
        out += [r.goods_value, r.uplift_pct, r.amount_insured, r.exchange_rate,
                r.thb_value, r.packages, r.gross_weight, r.policy_no,
                r.vessel, r.sailing, r.voyage_from, r.voyage_to, r.invoice_no,
                r.assured]
    elif code == "form_co":
        r = analyze_form_e(rows)
        out += [r.reference_no, r.total_packages] + r.hs_codes + r.criteria
        out += r.ref_variants
        from customs_checker.form_e import find_word_numbers
        for w, d, u, v, raw in find_word_numbers([t for t in text.splitlines()]):
            out += [d, raw, w]
    else:
        return None
    return out


def main(prefix="", limit=8):
    cache = json.loads(BOX.read_text(encoding="utf-8"))
    n_page = n_orph = 0
    for k in sorted(cache):
        if not k.startswith(prefix):
            continue
        rows = group_rows(to_cells(cache[k]))
        if not rows:
            continue
        code = classify(page_text(rows), title_text(rows)).code
        text = page_text(rows)
        claimed = claimed_of(code, rows, text)
        if claimed is None:
            continue
        n_page += 1
        r = orphan_scan(text.splitlines(), claimed)
        if not r.tokens:
            continue
        n_orph += len(r.tokens)
        print(f"\n{'=' * 78}\n{k}  ({code})")
        print(f"  {r.notes[0] if r.notes else ''}")
        for t in sorted(r.tokens, key=lambda x: x.tier)[:limit]:
            print(f"    ชั้น{t.tier} [{t.kind}] {t.text:<16} «{t.line[:48]}»")
        if len(r.tokens) > limit:
            print(f"    ... อีก {len(r.tokens) - limit} ตัว")
    print(f"\n{'=' * 78}")
    print(f"หน้าที่มีตัวอ่าน {n_page} หน้า · ค่ากำพร้ารวม {n_orph} ตัว")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "")
