# -*- coding: utf-8 -*-
"""ใส่ด่านกันข้อผิดพลาดแบบเงียบกลับเข้า tables.py
ตรวจสอบทุกขั้นตอน ถ้าแก้ไม่สำเร็จจะหยุดพร้อมบอกเหตุผล ไม่แก้เงียบแล้วบอกว่าสำเร็จ"""
import sys, io

PATH = sys.argv[1] if len(sys.argv) > 1 else "src/customs_checker/tables.py"

GUARD = '''
def _guard_single_line(res, cols, ai, min_rows=3):
    """ด่านกันข้อผิดพลาดแบบเงียบ — ห้ามยืนยันเมื่อจับได้บรรทัดเดียวจากตารางใหญ่

    ถ้าคอลัมน์จำนวนเงินมีตัวเลขหลายแถว แต่จับความสัมพันธ์
    ปริมาณ x ราคา = จำนวนเงิน ได้เพียงบรรทัดเดียว แปลว่าน่าจะระบุคอลัมน์ผิด
    แล้วไปเจอคู่ที่คูณกันลงตัวโดยบังเอิญ ห้ามรายงานว่า "ยืนยัน" เด็ดขาด

    ที่มา: เคส VORETO ราคาต่อหน่วย 4 ทศนิยม (27.1800) ถูก parser รุ่นเก่าอ่านเป็น
    271,800 ตารางจึงยุบเหลือคู่บังเอิญคู่เดียว แล้วระบบรายงานว่า
    "ยืนยันด้วยยอดพิมพ์ 3.00" ทั้งที่ยอดจริงคือ 118.23
    เป็นข้อผิดพลาดแบบเงียบเพียงครั้งเดียวของโปรเจกต์นี้
    """
    if len(res["lines"]) == 1 and len(cols.get(ai) or {}) > min_rows:
        res["printed"] = None
        res["missing_lines"] = []
        res["computed"] = round(sum(l["amount"] for l in res["lines"]), 2)
        res["status"] = ("จับได้เพียงบรรทัดเดียวจากตารางหลายแถว "
                         "อาจอ่านคอลัมน์ผิด ต้องให้คนตรวจ")
        res["guard"] = "single_line_in_big_table"
    return res
'''

A_DEF = "def analyze_invoice(rows):"
A_END = '            res["status"] = "ไม่พบยอดพิมพ์ให้เทียบ"\n    return res'
NEW   = ('            res["status"] = "ไม่พบยอดพิมพ์ให้เทียบ"\n'
         '    _guard_single_line(res, cols, ai)\n'
         '    return res')

s = io.open(PATH, encoding="utf-8").read()
if "_guard_single_line" in s:
    print("ข้ามการแก้: มีด่านอยู่แล้ว"); sys.exit(0)
assert A_DEF in s, "หา analyze_invoice ไม่เจอ"
assert A_END in s, "หาท้ายฟังก์ชันไม่เจอ — ไฟล์ต่างจากที่คาด หยุดก่อน"
assert s.count(A_END) == 1, "เจอท้ายฟังก์ชันมากกว่าหนึ่งที่ หยุดก่อน"
out = s.replace(A_DEF, GUARD.strip("\n") + "\n\n\n" + A_DEF, 1).replace(A_END, NEW, 1)
assert out != s and "_guard_single_line(res, cols, ai)" in out
assert out.count("def _guard_single_line") == 1
compile(out, PATH, "exec")
io.open(PATH + ".bak", "w", encoding="utf-8").write(s)
io.open(PATH, "w", encoding="utf-8").write(out)
print("แก้สำเร็จ สำรองไฟล์เดิมไว้ที่", PATH + ".bak")
