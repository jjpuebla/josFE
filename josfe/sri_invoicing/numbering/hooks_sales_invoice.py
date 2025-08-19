import frappe
from josfe.sri_invoicing.numbering.state import next_sequential

# def si_before_submit(doc, method):
#     # Adjust these fieldnames to your reality:
#     warehouse = getattr(doc, "set_warehouse", None) or getattr(doc, "warehouse", None)
#     emission_point = getattr(doc, "sri_emission_point", None)  # you provide this in UI/logic

#     if not warehouse or not emission_point:
#         frappe.throw("Missing Warehouse or Emission Point on Sales Invoice.")

#     seq = next_sequential(warehouse, emission_point, "Factura")

#     # Persist for audit / XML build
#     doc.sri_establishment_code = frappe.db.get_value("Warehouse", warehouse, "custom_establishment_code")
#     doc.sri_emission_point_code = emission_point
#     doc.sri_sequential_assigned = seq

def si_before_submit(doc, method):
    for f in ["sri_establishment_code", "sri_emission_point_code", "sri_sequential_assigned"]:
        if not getattr(doc, f, None):
            frappe.throw("No se ha asignado la serie SRI correctamente. Falta: " + f)