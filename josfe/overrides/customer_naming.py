import frappe

def autoname_customer(doc, method):
    if doc.tax_id:
        doc.name = doc.tax_id.strip().upper()
    else:
        frappe.throw("⚠️ No se puede guardar: se requiere un Tax ID para crear el cliente.")
