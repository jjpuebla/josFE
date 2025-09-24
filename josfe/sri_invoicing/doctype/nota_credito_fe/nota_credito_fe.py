import frappe
from frappe.model.document import Document
from frappe import _
from datetime import date, timedelta

def _prefill_numbering_from_source(self):
    """Ensure Sucursal (warehouse) and Punto de Emisión exist on the NC.
    If Source Invoice is provided, copy from it.
    """
    if getattr(self, "source_invoice", None):
        si_src = frappe.get_doc("Sales Invoice", self.source_invoice)
        if not getattr(self, "custom_jos_level3_warehouse", None) and getattr(si_src, "custom_jos_level3_warehouse", None):
            self.custom_jos_level3_warehouse = si_src.custom_jos_level3_warehouse
        if not getattr(self, "custom_jos_sri_emission_point_code", None) and getattr(si_src, "custom_jos_sri_emission_point_code", None):
            self.custom_jos_sri_emission_point_code = si_src.custom_jos_sri_emission_point_code

    if not getattr(self, "custom_jos_level3_warehouse", None) or not getattr(self, "custom_jos_sri_emission_point_code", None):
        frappe.throw(_("Seleccione Sucursal (3er nivel) y Punto de Emisión en la Nota de Crédito."))

def _remaining_qty_for_item(source_si: str, item_code: str) -> float:
    if not (source_si and item_code):
        return 0.0
    src_qty = frappe.db.sql(
        "SELECT COALESCE(SUM(qty),0) FROM `tabSales Invoice Item` WHERE parent=%s AND item_code=%s",
        (source_si, item_code),
    )[0][0] or 0.0
    if not src_qty:
        return 0.0
    ret_qty = frappe.db.sql(
        """
        SELECT COALESCE(SUM(ABS(sii.qty)),0)
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus=1 AND si.is_return=1 AND si.return_against=%s
          AND sii.item_code=%s
        """,
        (source_si, item_code),
    )[0][0] or 0.0
    remaining = float(src_qty) - float(ret_qty)
    return max(0.0, remaining)

def _pick_any_si_row_for_item(source_si: str, item_code: str):
    if not (source_si and item_code):
        return None
    return frappe.db.get_value(
        "Sales Invoice Item",
        {"parent": source_si, "item_code": item_code},
        ["item_code", "uom", "conversion_factor", "warehouse",
         "income_account", "cost_center", "batch_no", "serial_no"],
        as_dict=True
    )

class NotaCreditoFE(Document):
    def validate(self):
        if not self.credit_note_type:
            frappe.throw(_("Please choose Credit Note Type"))

        if self.credit_note_type == "By Products":
            if not self.source_invoice:
                frappe.throw(_("Source Invoice is required for 'By Products' credit notes"))
            if not self.return_items:
                frappe.throw(_("Add at least one row in Return Items"))

            # Simple mode: no per-row linkage required; cap only if item exists on source
            for r in self.return_items:
                rq = float(r.return_qty or 0)
                if rq < 0:
                    rq = -rq
                    r.return_qty = rq

        if self.credit_note_type == "Free-form":
            if not self.free_items:
                frappe.throw(_("Add at least one row in Free-form Items"))
            if not self.free_item_code:
                frappe.throw(_("Please set a Default Free-form Item (service)"))

        # Always ensure Sucursal & PE are present
        _prefill_numbering_from_source(self)

        self._normalize_qty()

    def _normalize_qty(self):
        """Convert UI positive Return Qty into negative qty for ERPNext core compatibility."""
        for r in self.return_items:
            rq = (r.return_qty or 0)
            if rq > 0:
                r.qty = -1 * rq
            else:
                r.qty = rq



    def on_submit(self):
        self.create_return_invoice()

    def on_cancel(self):
        if self.linked_return_si and frappe.db.exists("Sales Invoice", self.linked_return_si):
            si = frappe.get_doc("Sales Invoice", self.linked_return_si)
            if si.docstatus == 1:
                si.cancel()

    def create_return_invoice(self):
        """Create and submit a Sales Invoice Return and link it back to Nota Credito FE"""
        si_src = None
        if self.credit_note_type == "By Products":
            si_src = frappe.get_doc("Sales Invoice", self.source_invoice)
            if si_src.docstatus != 1 or getattr(si_src, "is_return", 0):
                frappe.throw(_("Source Sales Invoice must be submitted and not a return"))

        si = frappe.new_doc("Sales Invoice")
        si.is_return = 1
        if self.credit_note_type == "By Products":
            si.return_against = self.source_invoice
        si.company = self.company
        si.customer = self.customer
        si.posting_date = self.posting_date
        si.set_posting_time = 1

        # mirror currency/rates from source if available
        if si_src:
            for f in ["update_stock","debit_to","currency","conversion_rate",
                      "selling_price_list","price_list_currency","plc_conversion_rate"]:
                if hasattr(si_src, f):
                    setattr(si, f, getattr(si_src, f))

        # map items
        if self.credit_note_type == "By Products":
            for r in self.return_items:
                rq = float(r.return_qty or 0)
                if rq <= 0:
                    continue

                # ✅ fetch original SI row to copy all needed fields
                si_row = frappe.db.get_value(
                    "Sales Invoice Item",
                    {"parent": self.source_invoice, "item_code": r.item_code},
                    ["name", "item_code", "uom", "conversion_factor", "warehouse",
                     "income_account", "cost_center", "batch_no", "serial_no", "rate"],
                    as_dict=True
                )

                if not si_row:
                    frappe.throw(_("Item {0} not found in source invoice {1}")
                                 .format(r.item_code, self.source_invoice))

                si.append("items", {
                    "item_code": si_row.item_code or r.item_code,
                    "qty": -abs(rq),
                    "rate": r.rate or si_row.rate or 0,
                    "uom": si_row.uom or r.uom,
                    "conversion_factor": si_row.conversion_factor,
                    "warehouse": si_row.warehouse or self.custom_jos_level3_warehouse,
                    "income_account": si_row.income_account,
                    "cost_center": si_row.cost_center,
                    "batch_no": si_row.batch_no,
                    "serial_no": si_row.serial_no,
                    # 🔑 Critical link for ERPNext core validation
                    "sales_invoice_item": si_row.name,
                })

            # copy taxes from source
            if si_src:
                si.set("taxes", [])
                for tx in si_src.get("taxes", []):
                    si.append("taxes", {
                        "charge_type": tx.charge_type,
                        "account_head": tx.account_head,
                        "rate": tx.rate,
                        "description": tx.description,
                        "cost_center": tx.cost_center,
                    })

            # best-effort flags to avoid auto-reconcile
            try:
                setattr(si, "allocate_advances_automatically", 0)
                setattr(si, "update_outstanding_for_self", 0)
                setattr(si, "do_not_update_outstanding", 1)
            except Exception:
                pass

        elif self.credit_note_type == "Free-form":
            default_item = self.free_item_code
            for r in self.free_items:
                qty = r.qty or 0
                rate = r.rate or 0
                if not qty and not rate:
                    continue
                si.append("items", {
                    "item_code": default_item,
                    "qty": -abs(qty if qty else 1),
                    "rate": abs(rate),
                    "description": r.description,
                })

        # numbering context BEFORE insert()
        si.custom_jos_level3_warehouse = (
            getattr(si_src, "custom_jos_level3_warehouse", None)
            or getattr(self, "custom_jos_level3_warehouse", None)
        )
        si.custom_jos_sri_emission_point_code = (
            getattr(si_src, "custom_jos_sri_emission_point_code", None)
            or getattr(self, "custom_jos_sri_emission_point_code", None)
        )
        if not si.custom_jos_level3_warehouse or not si.custom_jos_sri_emission_point_code:
            frappe.throw(_("Seleccione Sucursal (3er nivel) y Punto de Emisión antes de guardar."))

        for it in si.items:
            if not it.warehouse:
                it.warehouse = si.custom_jos_level3_warehouse

        si.flags.ignore_permissions = True


#******************************************************** CHANGE NAME****************************************************************
        # --- force the Sales Invoice name to match this NC's name ---
        desired_si_name = self.name  # e.g. "002-002-000000050"
        if frappe.db.exists("Sales Invoice", desired_si_name):
            frappe.throw(_("A Sales Invoice already exists with name {0}.").format(desired_si_name))

        si.name = desired_si_name
        si.flags.name_set = True  # tell Frappe we're explicitly setting the name

        # persist + submit
        si.insert(ignore_permissions=True)
        si.submit()

        # link back to NC (will now be exactly the CN number)
        self.db_set("linked_return_si", si.name)


#******************************************************** CHANGE NAME****************************************************************

        # Nudge SI list to refresh (UI)
        try:
            frappe.publish_realtime("list_update", {"doctype": "Sales Invoice"})
        except Exception:
            pass



@frappe.whitelist()
def si_last_12mo(doctype, txt, searchfield, start, page_len, filters):
    """Link field query:
    Only invoices for the selected Customer & Company, last 365 days,
    matching Warehouse & Emission Point. Exclude returns/cancelled."""
    customer = (filters or {}).get("customer")
    company  = (filters or {}).get("company")
    wh       = (filters or {}).get("custom_jos_level3_warehouse")
    ep_code  = (filters or {}).get("custom_jos_sri_emission_point_code")

    if not (customer and company and wh and ep_code):
        return []

    # Normalize EP to 3-digit prefix ("002" from "002 - Front Desk")
    ep_prefix = (ep_code or "").split(" - ", 1)[0].strip()

    since = (date.today() - timedelta(days=365)).isoformat()
    rows = frappe.db.sql(
        """
        SELECT si.name
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND IFNULL(si.is_return, 0) = 0
          AND si.status NOT IN ('Cancelled')
          AND si.company = %s
          AND si.customer = %s
          AND si.posting_date >= %s
          AND si.custom_jos_level3_warehouse = %s
          AND LEFT(IFNULL(si.custom_jos_sri_emission_point_code,''), 3) = %s
        ORDER BY si.posting_date DESC, si.name DESC
        LIMIT %s OFFSET %s
        """,
        (company, customer, since, wh, ep_prefix, page_len, start),
    )
    return rows

@frappe.whitelist()
def get_source_invoice_items(source_invoice: str):
    """Return item rows with 'available_to_return' per source SI line."""
    if not source_invoice:
        return []

    # All sell lines on the source SI
    src_rows = frappe.db.sql(
        """
        SELECT item_code, item_name, uom, qty, rate
        FROM `tabSales Invoice Item`
        WHERE parent = %s
        """,
        (source_invoice,),
        as_dict=True,
    )

    # Sum of returns per item_code on return SIs against this SI
    returned = frappe.db.sql(
        """
        SELECT sii.item_code, ABS(SUM(sii.qty)) AS returned_qty
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
         AND IFNULL(si.is_return,0) = 1
          AND si.return_against = %s
        GROUP BY sii.item_code
        """,
        (source_invoice,),
        as_dict=True,
    )
    ret_by_code = {r.item_code: float(r.returned_qty or 0) for r in returned}

    out = []
    for r in src_rows:
        sold = float(r.qty or 0)
        already = float(ret_by_code.get(r.item_code, 0))
        avail = max(0, sold - already)
        out.append({
            "item_code": r.item_code,
            "item_name": r.item_name,
            "uom": r.uom,
            "orig_qty": avail,                 # shows "Available to Return"
            "rate": float(r.rate or 0),
            "amount": 0,
            "return_qty": 0,
        })
    return out