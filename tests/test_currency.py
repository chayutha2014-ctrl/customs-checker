"""ชุดทดสอบสกุลเงิน — ข้อความทั้งหมดยกมาจากใบ Invoice จริง"""
import pytest
from customs_checker.currency import resolve_currency


def test_eco_xiamen_พบหลายแห่งยืนยันได้():
    t = "Unit Price (CNY¥) Amount (CNY¥) SAY TOTAL CNY SEVEN HUNDRED AND SEVENTY-FIVE THOUSAND"
    r = resolve_currency(t)
    assert r.code == "CNY" and r.status == "ยืนยัน"


def test_fujian_domoo_usd():
    t = "UNIT PRICE (FOB XIAMEN) USD TOTAL AMOUNT USD SAY TOTAL US ONE HUNDRED THOUSAND FOUR HUNDRED AND TWENTY DOLLARS"
    assert resolve_currency(t).code == "USD"


def test_voreto_us_dollar_sign():
    t = "Unit Price (US$) Amount (US$) SAY TOTAL US DOLLARS TWENTY-SIX THOUSAND"
    r = resolve_currency(t)
    assert r.code == "USD" and r.status == "ยืนยัน"


def test_shijun_cny():
    t = "Quantity (PCS) Unit Price (CNY) Total (CNY) Total Amount (FOB)"
    r = resolve_currency(t)
    assert r.code == "CNY" and r.status == "ยืนยัน"


def test_bylimase_rmb_แปลงเป็น_cny():
    """เขียน RMB ต้องได้ CNY — เคสที่ระบบเดิมหาไม่เจอ"""
    r = resolve_currency("TOTAL AMOUNT RMB 46,830.00")
    assert r.code == "CNY"


def test_italisa_ดอลลาร์เครื่องหมายกับรหัสอยู่ด้วยกัน():
    t = "FOB HAI PHONG $ 6.18 $3,090.00 SAY US DOLLARS: THREE THOUSAND AND NINETY DOLLARS ONLY A/C NO.(USD)"
    r = resolve_currency(t)
    assert r.code == "USD" and r.status == "ยืนยัน"


def test_เยนกำกวมต้องไม่เดา():
    """¥ เป็นได้ทั้ง CNY และ JPY ห้ามเดาเอง"""
    r = resolve_currency("Unit Price ¥35.70 Amount ¥35,700.00")
    assert r.code is None
    assert r.status == "ต้องให้คนยืนยัน"
    assert r.candidates == ["CNY", "JPY"]


def test_เยนกำกวมใช้ประเทศช่วยได้แต่ยังต้องยืนยัน():
    r = resolve_currency("Unit Price ¥35.70", country="CN")
    assert r.code == "CNY"
    assert r.status == "ต้องให้คนยืนยัน"      # ไม่ใช่ "ยืนยัน"


def test_ขัดแย้งต้องหยุด():
    r = resolve_currency("Unit Price (USD) ... SAY TOTAL CNY TWENTY THOUSAND")
    assert r.code is None
    assert r.status == "ขัดแย้ง"


def test_พบแห่งเดียวต้องให้คนยืนยัน():
    r = resolve_currency("TOTAL USD 1,234.00")
    assert r.code == "USD"
    assert r.status == "ต้องให้คนยืนยัน"


def test_ไม่พบต้องไม่เดาเป็น_usd():
    r = resolve_currency("TOTAL 1,234.00 QTY 10 PRICE 123.40")
    assert r.code is None
    assert r.status == "ไม่พบ"
