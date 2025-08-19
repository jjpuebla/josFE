# apps/josfe/josfe/sri_invoicing/warehouse_guards.py
import frappe

def prevent_deleting_emission_point(doc, method=None):
    """Hard-block deletion of SRI Puntos Emision. Use Estado=Inactivo instead."""
    frappe.throw("No elimines Puntos de Emisión. Establece el campo Estado en 'Inactivo'.")
