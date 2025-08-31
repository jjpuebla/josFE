# -*- coding: utf-8 -*-
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from datetime import date as _date, datetime as _dt
from xml.etree.ElementTree import SubElement
from typing import Optional
from frappe.contacts.doctype.address.address import get_address_display

import frappe

TWOPLACES = Decimal("0.01")
SIXPLACES = Decimal("0.000001")

def get_company_address(company: str, prefer_title: str = None) -> str:
    """Return the address_line1 for a given Company.
       If prefer_title provided, filter by that address_title.
    """
    conditions = []
    values = [company]

    sql = """
        SELECT a.address_line1
        FROM `tabAddress` a
        JOIN `tabDynamic Link` dl ON dl.parent = a.name
        WHERE dl.link_doctype = 'Company'
          AND dl.link_name = %s
          AND a.disabled = 0
    """

    if prefer_title:
        sql += " AND a.address_title = %s"
        values.append(prefer_title)

    sql += " ORDER BY a.is_primary_address DESC, a.creation ASC LIMIT 1"

    row = frappe.db.sql(sql, values, as_dict=True)
    return row[0].address_line1 if row else ""


def get_warehouse_address(warehouse: str, prefer_title: str = None) -> str:
    """Return the address_line1 for a given Warehouse."""
    if not warehouse:
        return ""

    conditions = []
    values = [warehouse]

    sql = """
        SELECT a.address_line1
        FROM `tabAddress` a
        JOIN `tabDynamic Link` dl ON dl.parent = a.name
        WHERE dl.link_doctype = 'Warehouse'
          AND dl.link_name = %s
          AND a.disabled = 0
    """

    if prefer_title:
        sql += " AND a.address_title = %s"
        values.append(prefer_title)

    sql += " ORDER BY a.is_primary_address DESC, a.creation ASC LIMIT 1"

    row = frappe.db.sql(sql, values, as_dict=True)
    return row[0].address_line1 if row else ""

def D(val) -> Decimal:
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val or "0"))
    except Exception:
        return Decimal(0)

def money(val) -> Decimal:
    return D(val).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def qty6(val) -> Decimal:
    return D(val).quantize(SIXPLACES, rounding=ROUND_HALF_UP)

def z3(v) -> str:
    return str(v or "").strip().zfill(3)[-3:]

def z9(v) -> str:
    try:
        return f"{int(v):09d}"
    except Exception:
        return str(v or "").strip().zfill(9)[-9:]

def z8(v) -> str:
    try:
        return str(int(v)).zfill(8)[-8:]
    except Exception:
        return str(v or "").strip().zfill(8)[-8:]

def ddmmyyyy(val) -> str:
    if isinstance(val, str):
        s = val.strip()
        if '/' in s:
            return s.replace('/', '')
        if '-' in s and len(s) >= 10:
            y,m,d = s[:10].split('-')
            return d + m + y
    if isinstance(val, _dt):
        return f"{val.day:02d}{val.month:02d}{val.year:04d}"
    if isinstance(val, _date):
        return f"{val.day:02d}{val.month:02d}{val.year:04d}"
    raise ValueError("Unsupported date format for ddmmyyyy()")

def hash8_from_string(s: str) -> str:
    h = int(hashlib.sha1((s or '').encode('utf-8')).hexdigest(), 16) % (10 ** 8)
    return str(h).zfill(8)


def _text(parent, tag, val):
    """
    Safe XML helper: always create the tag and assign value as string.
    If val is None, log it and set as empty string.
    """
    el = SubElement(parent, tag)
    if val is None:
        import frappe
        frappe.logger().warning(f"[XML Builder] Tag <{tag}> received None")
        el.text = ""
    else:
        el.text = str(val)
    return el