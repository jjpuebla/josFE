# apps/josfe/josfe/sri_invoicing/tests/xml_cycle.py
import os
import re
import frappe
from frappe.utils import nowdate, add_days

from josfe.sri_invoicing.queue import api as queue_api
from josfe.sri_invoicing.xml import service as xml_service

# ===================== DEFAULTS (match your UI) =====================
_DEFAULT_COMPANY = "ajptest"
_DEFAULT_CUSTOMER_ID = "1723629497"     # Customer docname or tax_id
_DEFAULT_CUSTOMER_NAME = "magal"

# UI fields you set manually on the form:
_DEFAULT_WAREHOUSE = "Sucursal Mariscal - A"        # Sucursal (3er nivel) - can be a GROUP
_DEFAULT_PE_CODE   = "002"                          # Punto de Emisión (3 dígitos, texto)

# Item + pricing (create non-stock item if missing)
_DEFAULT_ITEM_CODE = "HILCHI0000000000"
_DEFAULT_QTY = 1.0
_DEFAULT_RATE = 2.0

# Safety: no stock moves during the test
_DEFAULT_UPDATE_STOCK = 0
# ===================================================================

_SERIE_RE = re.compile(r"^(?P<est>\d{3})-(?P<pe>\d{3})-(?P<num>\d+)$")

# ===================== PATH / LOGGING HELPERS =======================
_KNOWN_STAGE_DIRS = [
    "Generados",
    "Firmados",
    "Firmados/Pendientes",
    "Firmados/Rechazados",
    "Autorizados",
    "No_Autorizados",
]

def _file_url_to_abs(file_url: str | None) -> str | None:
    """Map '/private/files/...' to absolute path under the current site."""
    if not file_url or "/private/files/" not in file_url:
        return None
    rel = file_url.split("/private/files/", 1)[1]
    return frappe.get_site_path("private", "files", rel)

def _extract_stage_folder(file_url: str | None) -> str | None:
    """Return the folder part after '/private/files/SRI/' (e.g., 'Generados', 'Autorizados')."""
    if not file_url:
        return None
    root = "/private/files/SRI/"
    if root not in file_url:
        return None
    tail = file_url.split(root, 1)[1]
    parts = tail.split("/")
    return "/".join(parts[:-1]) if len(parts) >= 2 else None

def _scan_known_locations(filename: str) -> list[dict]:
    """List existing files with this filename in known SRI stage folders."""
    base = frappe.get_site_path("private", "files", "SRI")
    found = []
    for stage in _KNOWN_STAGE_DIRS:
        abspath = os.path.join(base, *stage.split("/"), filename)
        if os.path.exists(abspath):
            found.append({
                "stage": stage,
                "abs_path": abspath,
                "url": f"/private/files/SRI/{stage}/{filename}",
            })
    return found
# ===================================================================


# ===================== MASTER-DATA HELPERS ==========================
def _ensure_company(company: str | None) -> str:
    target = company or _DEFAULT_COMPANY
    if frappe.db.exists("Company", target):
        return target
    raise frappe.ValidationError(f"No existe la Compañía '{target}'.")

def _find_customer_by_tax_or_name(tax_id: str, display_name: str):
    if frappe.db.exists("Customer", tax_id):
        return tax_id
    rows = frappe.get_all("Customer", filters={"tax_id": tax_id}, pluck="name", limit=1)
    if rows:
        return rows[0]
    rows = frappe.get_all("Customer", filters={"customer_name": display_name}, pluck="name", limit=1)
    if rows:
        return rows[0]
    return None

def _ensure_customer(customer_id: str = _DEFAULT_CUSTOMER_ID, display_name: str = _DEFAULT_CUSTOMER_NAME) -> tuple[str, bool]:
    found = _find_customer_by_tax_or_name(customer_id, display_name)
    if found:
        return found, False
    doc = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": display_name,
        "customer_type": "Individual",
        "customer_group": "All Customer Groups",
        "territory": "All Territories",
        "tax_id": customer_id,
    })
    doc.insert(ignore_permissions=True)
    return doc.name, True

def _pick_stock_uom() -> str:
    for name in ["Nos", "Unit", "Unidad", "Pcs", "Each"]:
        if frappe.db.exists("UOM", name):
            return name
    any_uom = frappe.get_all("UOM", pluck="name", limit=1)
    if any_uom:
        return any_uom[0]
    doc = frappe.get_doc({"doctype": "UOM", "uom_name": "Nos", "must_be_whole_number": 0})
    doc.insert(ignore_permissions=True)
    return doc.name

def _pick_item_group() -> str:
    if frappe.db.exists("Item Group", "All Item Groups"):
        return "All Item Groups"
    rows = frappe.get_all("Item Group", pluck="name", limit=1)
    if rows:
        return rows[0]
    raise frappe.ValidationError("No existe ningún 'Item Group'.")

def _ensure_item(code: str = _DEFAULT_ITEM_CODE) -> tuple[str, bool]:
    if frappe.db.exists("Item", code):
        return code, False
    uom = _pick_stock_uom()
    ig = _pick_item_group()
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": code,
        "item_name": code,
        "is_stock_item": 0,
        "item_group": ig,
        "stock_uom": uom,
    })
    doc.insert(ignore_permissions=True)
    return doc.name, True
# ===================================================================


# ===================== SRI SERIES (UNIQUENESS) ======================
def _guess_establishment_from_history(warehouse: str, pe_code: str) -> str:
    """Try to infer the 3-digit establishment from prior invoices; else fallback to '002' or Warehouse field."""
    # 1) Look at prior invoices with same UI fields
    rows = frappe.get_all(
        "Sales Invoice",
        filters={
            "custom_jos_level3_warehouse": warehouse,
            "custom_jos_sri_emission_point_code": pe_code,
            "custom_sri_serie": ["is", "set"],
        },
        pluck="custom_sri_serie",
        order_by="creation desc",
        limit=50,
    )
    for s in rows:
        m = _SERIE_RE.match(s or "")
        if m:
            return str(m.group("est")).zfill(3)

    # 2) Warehouse.custom_establishment_code (if set)
    est = frappe.get_value("Warehouse", warehouse, "custom_establishment_code")
    if est:
        return str(est).zfill(3)

    # 3) Fallback
    return "002"

def _max_suffix_for(est: str, pe: str) -> int:
    """Return the max numeric suffix used in SI.custom_sri_serie for this (est, pe)."""
    like = f"{est}-{pe}-%"
    rows = frappe.get_all(
        "Sales Invoice",
        filters={"custom_sri_serie": ["like", like]},
        pluck="custom_sri_serie",
        order_by="creation desc",
        limit=500,
    )
    maxn = 0
    for s in rows:
        m = _SERIE_RE.match(s or "")
        if m and m.group("est") == est and m.group("pe") == pe:
            try:
                n = int(m.group("num"))
                if n > maxn:
                    maxn = n
            except Exception:
                pass
    return maxn

def _next_unique_sri_serie(warehouse: str, pe_code: str) -> str:
    """Compute the next available 'EEE-PPP-NNNNNNNNN' and ensure it doesn't collide with SI nor Queue."""
    pe = str(pe_code).zfill(3)
    est = _guess_establishment_from_history(warehouse, pe)
    n = _max_suffix_for(est, pe) + 1 if _max_suffix_for(est, pe) else 1

    def fmt(k: int) -> str:
        return f"{est}-{pe}-{k:09d}"

    serie = fmt(n)
    # ensure uniqueness against both doctypes
    while frappe.db.exists("Sales Invoice", {"custom_sri_serie": serie}) or \
          frappe.db.exists("SRI XML Queue", {"sales_invoice": serie}):
        n += 1
        serie = fmt(n)
    return serie
# ===================================================================


# ===================== CORE FLOW (MATCH UI) ========================
def _make_and_submit_invoice(
    company: str | None = None,
    customer: str | None = None,
    item_code: str | None = None,
    qty: float = _DEFAULT_QTY,
    rate: float = _DEFAULT_RATE,
):
    """
    Create + submit a Sales Invoice using your exact UI behavior and a unique SRI series:
    - set `custom_jos_level3_warehouse` to the GROUP name
    - set `custom_jos_sri_emission_point_code` to '002'
    - set `custom_sri_serie` to the next free number for (est,pe)
    - avoid stock moves (update_stock=0)
    """
    company = _ensure_company(company)
    customer, _ = (customer, False) if customer else _ensure_customer(_DEFAULT_CUSTOMER_ID, _DEFAULT_CUSTOMER_NAME)
    item_code, _ = (item_code, False) if item_code else _ensure_item(_DEFAULT_ITEM_CODE)

    # Direct UI-style: no leaf lookup
    wh_name = _DEFAULT_WAREHOUSE
    if not frappe.db.exists("Warehouse", wh_name):
        raise frappe.ValidationError(f"No existe la Bodega '{wh_name}'.")
    ep_code = str(_DEFAULT_PE_CODE).strip().zfill(3)

    # Compute a fresh SRI series (EEE-PPP-NNNNNNNNN)
    est = frappe.get_value("Warehouse", wh_name, "custom_establishment_code") or "002"
    est = str(est).zfill(3)

    # Find max suffix for this est+pe
    like = f"{est}-{ep_code}-%"
    existing = frappe.get_all("Sales Invoice", filters={"custom_sri_serie": ["like", like]}, pluck="custom_sri_serie")
    max_n = 0
    for s in existing:
        try:
            n = int(s.split("-")[-1])
            if n > max_n:
                max_n = n
        except Exception:
            pass
    next_num = max_n + 1
    sri_serie = f"{est}-{ep_code}-{next_num:09d}"

    # Ensure uniqueness also in SRI XML Queue
    while frappe.db.exists("SRI XML Queue", {"sales_invoice": sri_serie}):
        next_num += 1
        sri_serie = f"{est}-{ep_code}-{next_num:09d}"

    # Build the invoice
    si = frappe.new_doc("Sales Invoice")
    si.company = company
    si.customer = customer
    si.posting_date = nowdate()
    si.due_date = add_days(si.posting_date, 5)
    si.set_posting_time = 1
    si.update_stock = _DEFAULT_UPDATE_STOCK

    si.custom_jos_level3_warehouse = wh_name
    si.custom_jos_sri_emission_point_code = ep_code
    si.custom_sri_serie = sri_serie

    try:
        si.custom_jos_level3_warehouse_display = wh_name
    except Exception:
        pass

    row = si.append("items", {})
    row.item_code = item_code
    row.qty = qty
    row.rate = rate
    row.warehouse = wh_name

    si.insert(ignore_permissions=True)
    si.submit()
    return si

import frappe
import re

_SERIE_RE = re.compile(r"^(?P<est>\d{3})-(?P<pe>\d{3})-(?P<num>\d+)$")

def suggest_next_sri_serie(warehouse: str, pe_code: str) -> str:
    """
    Suggest the next available custom_sri_serie (EEE-PPP-NNNNNNNNN)
    for a given warehouse + emission point, without creating anything.
    """
    est = frappe.get_value("Warehouse", warehouse, "custom_establishment_code") or "002"
    est = str(est).zfill(3)
    pe = str(pe_code).zfill(3)

    like = f"{est}-{pe}-%"
    # Collect from Sales Invoices
    si_series = frappe.get_all(
        "Sales Invoice",
        filters={"custom_sri_serie": ["like", like]},
        pluck="custom_sri_serie",
    )
    # Collect from SRI XML Queue
    q_series = frappe.get_all(
        "SRI XML Queue",
        filters={"sales_invoice": ["like", like]},
        pluck="sales_invoice",
    )

    max_n = 0
    for s in si_series + q_series:
        m = _SERIE_RE.match(s or "")
        if m and m.group("est") == est and m.group("pe") == pe:
            try:
                n = int(m.group("num"))
                if n > max_n:
                    max_n = n
            except Exception:
                pass

    next_num = max_n + 1
    return f"{est}-{pe}-{next_num:09d}"
# ===================================================================


# ===================== PUBLIC ENTRYPOINT ============================
def run(
    company: str | None = None,
    customer: str | None = None,
    item_code: str | None = None,
    qty: float = _DEFAULT_QTY,
    rate: float = _DEFAULT_RATE,
    full_cycle: int = 0,
):
    """
    Create+submit SI (defaults above) → enqueue → (optional) full sign/send.
    Returns a trace of where the XML file is saved.
    """
    trace = []

    # 1) Create & submit SI
    si = _make_and_submit_invoice(company, customer, item_code, qty, rate)

    # 2) Enqueue (Generado)
    qname = queue_api.enqueue_for_sales_invoice(si.name)
    q = frappe.get_doc("SRI XML Queue", qname)
    filename = os.path.basename(q.xml_file or "") if q.xml_file else None
    trace.append({
        "event": "after_enqueue_generado",
        "state": getattr(q, "state", None),
        "file_url": q.xml_file,
        "abs_path": _file_url_to_abs(q.xml_file),
        "stage_folder": _extract_stage_folder(q.xml_file),
        "known_locations": _scan_known_locations(filename) if filename else [],
    })

    # 3) Full pipeline (optional)
    if int(full_cycle):
        xml_service.send_to_sri(qname, is_retry=0)
        q = frappe.get_doc("SRI XML Queue", qname)
        filename = os.path.basename(q.xml_file or "") if q.xml_file else filename
        trace.append({
            "event": "after_full_cycle",
            "state": getattr(q, "state", None),
            "file_url": q.xml_file,
            "abs_path": _file_url_to_abs(q.xml_file),
            "stage_folder": _extract_stage_folder(q.xml_file),
            "known_locations": _scan_known_locations(filename) if filename else [],
        })

    return {
        "si": si.name,
        "queue": qname,
        "state": q.state,
        "xml_file": q.xml_file,
        "company": si.company,
        "customer": si.customer,
        "trace": trace,
    }
# ===================================================================
