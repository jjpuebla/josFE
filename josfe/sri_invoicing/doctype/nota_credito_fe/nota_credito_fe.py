import frappe
from frappe.model.document import Document
from frappe import _

class NotaCreditoFE(Document):
    def validate(self):
        if not self.credit_note_type:
            frappe.throw(_("Please choose Credit Note Type"))

        if self.credit_note_type == "By Products":
            if not self.source_invoice:
                frappe.throw(_("Source Invoice is required for 'By Products' credit notes"))
            if not self.return_items:
                frappe.throw(_("Add at least one row in Return Items"))
            for r in self.return_items:
                if (r.return_qty or 0) > (r.orig_qty or 0):
                    frappe.throw(_("Returned Qty cannot exceed Original Qty for item {0}").format(r.item_code))

        if self.credit_note_type == "Free-form":
            if not self.free_items:
                frappe.throw(_("Add at least one row in Free-form Items"))
            if not self.free_item_code:
                frappe.throw(_("Please set a Default Free-form Item (service)"))

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
                if not r.return_qty:
                    continue
                srcrow = frappe.db.get_value(
                    "Sales Invoice Item", r.src_rowname,
                    ["uom","conversion_factor","warehouse","income_account",
                     "cost_center","batch_no","serial_no"],
                    as_dict=True
                ) or {}
                si.append("items", {
                    "item_code": r.item_code,
                    "qty": -abs(r.return_qty),
                    "rate": r.rate or 0,
                    "uom": srcrow.get("uom"),
                    "conversion_factor": srcrow.get("conversion_factor"),
                    "warehouse": srcrow.get("warehouse"),
                    "income_account": srcrow.get("income_account"),
                    "cost_center": srcrow.get("cost_center"),
                    "batch_no": srcrow.get("batch_no"),
                    "serial_no": srcrow.get("serial_no"),
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

        si.flags.ignore_permissions = True
        si.insert()
        si.submit()
        self.db_set("linked_return_si", si.name)
