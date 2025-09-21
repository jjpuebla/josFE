import frappe
from frappe.model.document import Document
from frappe import _

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

                exists_on_source = frappe.db.exists(
                    "Sales Invoice Item", {"parent": self.source_invoice, "item_code": r.item_code}
                )
                if exists_on_source:
                    cap = _remaining_qty_for_item(self.source_invoice, r.item_code)
                    if rq > cap:
                        frappe.throw(
                            _("Row #{idx}: Returned Qty {rq} exceeds remaining {cap} for item {code} on {si}.")
                            .format(idx=r.idx, rq=rq, cap=cap, code=(r.item_code or ""), si=self.source_invoice)
                        )
                    if cap and not r.orig_qty:
                        r.orig_qty = cap
                else:
                    # make it explicit in UI that source has no qty baseline
                    if r.orig_qty is None:
                        r.orig_qty = 0

        if self.credit_note_type == "Free-form":
            if not self.free_items:
                frappe.throw(_("Add at least one row in Free-form Items"))
            if not self.free_item_code:
                frappe.throw(_("Please set a Default Free-form Item (service)"))

        # Always ensure Sucursal & PE are present
        _prefill_numbering_from_source(self)

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

                si_row = _pick_any_si_row_for_item(self.source_invoice, r.item_code)
                si.append("items", {
                    "item_code": (si_row.get("item_code") if si_row else r.item_code),
                    "qty": -abs(rq),
                    "rate": r.rate or 0,
                    "uom": (si_row.get("uom") if si_row else getattr(r, "uom", None)),
                    "conversion_factor": (si_row.get("conversion_factor") if si_row else None),
                    "warehouse": (si_row.get("warehouse") if si_row else getattr(self, "custom_jos_level3_warehouse", None)),
                    "income_account": (si_row.get("income_account") if si_row else None),
                    "cost_center": (si_row.get("cost_center") if si_row else None),
                    "batch_no": (si_row.get("batch_no") if si_row else None),
                    "serial_no": (si_row.get("serial_no") if si_row else None),
                })

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
        si.insert()
        si.submit()
        self.db_set("linked_return_si", si.name)
