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

# Taxes — dynamic per item (IVA/ICE/IRBPNR)
# -----------------------------------------

def _round_pct(p):
    try:
        return int(Decimal(str(p)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0

def _sri_codes_for_tax_row(tax_row, pct: D):
    """
    Map ERP tax row + percentage into SRI (codigo, codigoPorcentaje, tarifa).
    pct = percentage (Decimal).
    """
    head = (getattr(tax_row, "account_head", "") or "").upper()
    desc = (getattr(tax_row, "description", "") or "").upper()
    pct_i = int(round(float(pct)))

    # IVA (codigo "2")
    if "IVA" in head or "IVA" in desc:
        # Detect Exento / No Objeto
        if "EXENTO" in desc or "EXENTO" in head:
            return "2", "7", "0.00"
        if "NO OBJETO" in desc or "NO OBJETO" in head:
            return "2", "6", "0.00"

        # Standard by percentage
        if pct_i == 0:
            return "2", "0", "0.00"
        if pct_i == 5:
            return "2", "5", "5.00"
        if pct_i == 8:
            return "2", "8", "8.00"
        if pct_i == 12:
            return "2", "2", "12.00"
        if pct_i == 13:
            return "2", "10", "13.00"
        if pct_i == 14:
            return "2", "3", "14.00"
        if pct_i == 15:
            return "2", "4", "15.00"

        # Fallback → treat as 0%
        return "2", "0", "0.00"

    # ICE (codigo "3")
    if "ICE" in head or "ICE" in desc:
        # SRI expects sub-codes depending on tariff; assume generic
        return "3", "0", f"{pct:.2f}"

    # IRBPNR (codigo "5")
    if "IRBPNR" in head or "IRBPNR" in desc:
        return "5", "0", f"{pct:.2f}"

    # Default → IVA 0%
    return "2", "0", "0.00"


def _iter_item_tax_splits(si, item):
    """
    Read ERPNext Sales Taxes & Charges per-item split:
      tax.item_wise_tax_detail[item_code] -> [amount, rate]
    """
    out = []
    for tax in (si.taxes or []):
        details = getattr(tax, "item_wise_tax_detail", None)
        if not details:
            continue
        try:
            d = frappe.parse_json(details) or {}
        except Exception:
            d = {}
        key = item.item_code or item.item_name or item.name
        val = d.get(key) or d.get(item.name)
        if val is None:
            continue
        tax_rate   = D(val[0]) if isinstance(val, (list, tuple)) and len(val) >= 1 else D(getattr(tax, "rate", 0) or 0)
        tax_amount = D(val[1]) if isinstance(val, (list, tuple)) and len(val) >= 2 else D("0")

        out.append({"row": tax, "rate": tax_rate, "amount": tax_amount})
    return out


def map_tax_invoice(si) -> list[dict]:
    """
    Aggregate invoice totals per (codigo, codigoPorcentaje).
    Output: list of totalImpuesto dicts (SRI doesn't require <tarifa> at invoice level).
    """
    from collections import defaultdict
    buckets = defaultdict(lambda: D("0"))
    bases   = defaultdict(lambda: D("0"))

    for it in (si.items or []):
        base = D(getattr(it, "net_amount", getattr(it, "amount", 0)) or 0)
        for split in _iter_item_tax_splits(si, it):
            codigo, codigoPorcentaje, _ = _sri_codes_for_tax_row(split["row"], split["rate"])
            key = (codigo, codigoPorcentaje)
            buckets[key] += D(split["amount"] or 0)
            bases[key]   += base

    if not buckets:
        return [{
            "codigo": "2",
            "codigoPorcentaje": "0",
            "baseImponible": money(D(getattr(si, "net_total", 0) or 0)),
            "valor": money(D("0")),
        }]

    out = []
    for (codigo, codigoPorcentaje), val in buckets.items():
        out.append({
            "codigo": codigo,
            "codigoPorcentaje": codigoPorcentaje,
            "baseImponible": money(bases[(codigo, codigoPorcentaje)]),
            "valor": money(val),
        })
    return out


def map_tax_item(si, it) -> list[dict]:
    """
    Build list of <impuesto> dicts for a Sales Invoice item.
    Uses ERPNext's item_wise_tax_detail directly.
    - <tarifa>  = percentage (val[0])
    - <valor>   = monetary amount (val[1])
    - <baseImponible> = it.net_amount
    """
    base = D(it.net_amount or it.amount or 0)
    impuestos = []

    # Walk ERP tax splits for this item
    for split in _iter_item_tax_splits(si, it):
        row = split["row"]

        # Reparse to be safe → ERP stores [rate, amount]
        raw = frappe.parse_json(row.item_wise_tax_detail or "{}") or {}
        val = raw.get(it.item_code) or raw.get(it.name) or raw.get(it.item_name)

        if not (isinstance(val, (list, tuple)) and len(val) >= 2):
            continue

        rate_pct = D(val[0])    # % (e.g. 15.0)
        amount_val = D(val[1])  # money (e.g. 65217.39)

        codigo, codigoPorcentaje, _ = _sri_codes_for_tax_row(row, rate_pct)

        impuestos.append({
            "codigo": codigo,
            "codigoPorcentaje": codigoPorcentaje,
            "tarifa": f"{rate_pct:.2f}",        # percentage
            "baseImponible": money(base),
            "valor": money(amount_val),         # money
        })

    # If ERP gave no tax splits → fallback to 0%/Exento/No Objeto
    if not impuestos:
        porc_code = "0"  # default 0%
        for tax in (si.taxes or []):
            desc = (tax.description or "").upper()
            acc  = (tax.account_head or "").upper()
            if "EXENTO" in desc or "EXENTO" in acc:
                porc_code = "7"
                break
            if "NO OBJETO" in desc or "NO OBJETO" in acc:
                porc_code = "6"
                break
        impuestos.append({
            "codigo": "2",
            "codigoPorcentaje": porc_code,
            "tarifa": "0.00",
            "baseImponible": money(base),
            "valor": money(D("0")),
        })

    return impuestos


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

# --- XML formatting helpers (unify all stages) ---
from lxml import etree

def format_xml_string(xml_text: str) -> str:
    """
    Take an XML string, return a pretty-printed UTF-8 string with real accents (é, ñ, á),
    avoiding numeric entities like &#xE9;.
    """
    root = etree.fromstring(xml_text.encode("utf-8"))
    return etree.tostring(
        root,
        pretty_print=True,
        encoding="utf-8",
        xml_declaration=False
    ).decode("utf-8")


def format_xml_bytes(xml_bytes: bytes) -> bytes:
    """
    Take XML bytes, return pretty-printed UTF-8 bytes with real accents (é, ñ, á).
    """
    root = etree.fromstring(xml_bytes)
    return etree.tostring(
        root,
        pretty_print=True,
        encoding="utf-8",
        xml_declaration=False
    )
