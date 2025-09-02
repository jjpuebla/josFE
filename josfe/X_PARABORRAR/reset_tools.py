import frappe

@frappe.whitelist()
def reset_invoices_and_xml():
    """Dangerous reset: delete all Sales Invoices and SRI XML Queue docs."""
    # Delete XML Queue first
    for q in frappe.get_all("SRI XML Queue", pluck="name"):
        frappe.delete_doc("SRI XML Queue", q, force=True, ignore_permissions=True)

    # Delete Invoices
    for si in frappe.get_all("Sales Invoice", pluck="name"):
        frappe.delete_doc("Sales Invoice", si, force=True, ignore_permissions=True)

    frappe.db.commit()
    return {"status": "ok", "msg": "All Sales Invoices and SRI XML Queues deleted"}
