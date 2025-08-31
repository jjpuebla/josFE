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

def get_party_address_name(link_doctype: str, link_name: str) -> Optional[str]:
    """Return name of the primary Address linked to (link_doctype, link_name) via Dynamic Link."""
    # prefer primary address; else first linked
    names = frappe.get_all(
        "Dynamic Link",
        filters={
            "link_doctype": link_doctype,
            "link_name": link_name,
            "parenttype": "Address",
        },
        fields=["parent"],
        order_by="idx asc",
        limit=10,
        pluck="parent",
    )
    if not names:
        return None
    # try to pick is_primary_address if present
    addr_flags = frappe.get_all("Address", filters={"name": ["in", names]}, fields=["name","is_primary_address"], limit=len(names))
    primary = next((a["name"] for a in addr_flags if a.get("is_primary_address")), None)
    return primary or names[0]

def get_party_address_display(link_doctype: str, link_name: str) -> str:
    """Return formatted address (same as ERPNext UI) for a linked party (Company, Warehouse, etc.)."""
    addr = get_party_address_name(link_doctype, link_name)
    return get_address_display(addr) if addr else ""

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