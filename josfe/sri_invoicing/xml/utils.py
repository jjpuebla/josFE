# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import hashlib
from datetime import date as _date, datetime as _dt
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from xml.etree.ElementTree import SubElement

import frappe
from frappe.contacts.doctype.address.address import get_address_display

TWOPLACES = Decimal("0.01")
SIXPLACES = Decimal("0.000001")

# ------------------------------
# Generic numeric / date helpers
# ------------------------------

def D(val) -> Decimal:
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val or "0"))
    except Exception:
        return Decimal(0)

def money(val) -> Decimal:
    """Quantize to 2 decimals, stringified later by _text()."""
    return D(val).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def qty6(val) -> Decimal:
    """Quantize to 6 decimals."""
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
        if "/" in s:
            return s.replace("/", "")
        if "-" in s and len(s) >= 10:
            y, m, d = s[:10].split("-")
            return d + m + y
    if isinstance(val, _dt):
        return f"{val.day:02d}{val.month:02d}{val.year:04d}"
    if isinstance(val, _date):
        return f"{val.day:02d}{val.month:02d}{val.year:04d}"
    raise ValueError("Unsupported date format for ddmmyyyy()")

def hash8_from_string(s: str) -> str:
    h = int(hashlib.sha1((s or "").encode("utf-8")).hexdigest(), 16) % (10**8)
    return str(h).zfill(8)

# ------------------------------
# XML safe text helper
# ------------------------------

def _text(parent, tag, val):
    """
    Safe XML helper: always create the tag and assign value as string.
    If val is None, log and set as empty string.
    """
    el = SubElement(parent, tag)
    if val is None:
        frappe.logger().warning(f"[XML Builder] Tag <{tag}> received None")
        el.text = ""
    else:
        el.text = str(val)
    return el

# ------------------------------
# Address helpers
# ------------------------------

def get_company_address(company: str, prefer_title: str = None) -> str:
    """Return address_line1 for a given Company; optional title filter."""
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
    return row[0].get("address_line1") if row else ""

def get_warehouse_address(warehouse: str, prefer_title: str = None) -> str:
    """Return address_line1 for a given Warehouse."""
    if not warehouse:
        return ""
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
    return row[0].get("address_line1") if row else ""

# ------------------------------
# Company flags
# ------------------------------

def get_obligado_contabilidad(company: str) -> str:
    """
    Your bench probe showed Company.custom_jos_contabilidad = 1/0.
    SRI expects 'SI'/'NO'.
    """
    val = frappe.db.get_value("Company", company, "custom_jos_contabilidad")
    return "SI" if val in ("1", 1, True, "SI") else "NO"

# ------------------------------
# Establishment / Point / Sequential
# ------------------------------

def get_ce_pe_seq(si) -> dict:
    """
    Given a Sales Invoice doc (or name), return CE, PE, and sequencial (9d).
    Prefer explicit fields if your workflow stores them; otherwise split from si.name.
    """
    if isinstance(si, str):
        si = frappe.get_doc("Sales Invoice", si)
    # Try explicit fields first (if your workflow fills them)
    ce = getattr(si, "sri_establishment_code", None)
    pe = getattr(si, "sri_emission_point_code", None)
    seq = getattr(si, "sri_sequential_assigned", None)

    if not (ce and pe and seq):
        parts = (si.name or "").split("-")
        if len(parts) == 3:
            ce, pe, seq = parts
    return {"ce": z3(ce), "pe": z3(pe), "secuencial": z9(seq)}

# ------------------------------
# Buyer ID type helper
# ------------------------------

def buyer_id_type(tax_id: Optional[str]) -> str:
    """
    04 = RUC (13)
    05 = Cédula (10)
    06 = Pasaporte / Otros
    """
    if not tax_id:
        return "06"
    s = str(tax_id).strip()
    if len(s) == 13:
        return "04"
    if len(s) == 10:
        return "05"
    return "06"

# ------------------------------
# Forma de pago (codes only)
# ------------------------------

_SRI_FALLBACK_WORDMAP = {
    "EFECTIVO": "01",
    "TRANSFEREN": "20",  # catch 'Transferencias'
    "CHEQUE": "20",
    "DEP"    : "20",     # 'Depósitos'
    "DÉBITO": "16", "DEBITO": "16",
    "CRÉDITO": "19", "CREDITO": "19",
}

def _extract_payment_code(val: str) -> Optional[str]:
    """Accept '01', '01 - Efectivo', or even 'Efectivo' → return '01'."""
    if not val:
        return None
    s = str(val).strip()
    # Code only
    if re.fullmatch(r"\d{2}", s):
        return s
    # '01 - Efectivo'
    m = re.match(r"^\s*(\d{2})\b", s)
    if m:
        return m.group(1)
    # Words only (fallback from old data)
    up = s.upper()
    for key, code in _SRI_FALLBACK_WORDMAP.items():
        if key in up:
            return code
    return None

def get_forma_pago(si) -> list[dict]:
    """
    Return pagos as list of dicts: [{'formaPago': '01', 'total': 12.34}, ...]
    For Sales Invoice we expect a single code in custom_jos_forma_pago.
    For POS you can extend this to read pos_doc.payments (not here).
    """
    code = _extract_payment_code(getattr(si, "custom_jos_forma_pago", None))
    if not code:
        return []
    return [{"formaPago": code, "total": money(D(si.grand_total or 0))}]

# ------------------------------
# Taxes (IVA 15% baseline)
# ------------------------------

def map_tax_invoice(si) -> dict:
    """
    Build the invoice-level <totalImpuesto> for IVA 15%.
    At this level, SRI XSD does NOT expect <tarifa>, only:
    codigo, codigoPorcentaje, descuentoAdicional?, baseImponible, valor
    """
    base = D(getattr(si, "net_total", 0))
    total = D(getattr(si, "grand_total", 0))
    iva_val = total - base
    return {
        "codigo": "2",               # IVA
        "codigoPorcentaje": "4",     # 15%
        # "tarifa": "15.00",
        "baseImponible": money(base),
        "valor": money(iva_val),
    }

def map_tax_item(it) -> dict:
    """
    Build the item-level <impuesto> for IVA 15%.
    Uses item.net_amount as you printed in bench console.
    """
    base = D(getattr(it, "net_amount", getattr(it, "amount", 0)))
    return {
        "codigo": "2",
        "codigoPorcentaje": "4",
        "tarifa": "15.00",
        "baseImponible": money(base),
        "valor": money(base * D("0.15")),
    }

# ------------------------------
# Info Adicional
# ------------------------------

def get_info_adicional(si) -> list[dict]:
    """Return [{'nombre': 'Dirección', 'valor': '...'}, ...]"""
    out = []
    try:
        if si.customer_address:
            addr = frappe.get_doc("Address", si.customer_address)
            if addr.address_line1:
                out.append({"nombre": "Dirección", "valor": addr.address_line1})
        if si.contact_person:
            c = frappe.get_doc("Contact", si.contact_person)
            if c.email_id:
                out.append({"nombre": "Email", "valor": c.email_id})
            if c.phone:
                out.append({"nombre": "Teléfono", "valor": c.phone})
    except Exception:
        # Don't break XML if optional info is missing
        pass
    return out
