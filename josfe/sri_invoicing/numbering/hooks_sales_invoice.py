import frappe
# Importa el helper donde realmente está definido
from josfe.sri_invoicing.numbering.serie_autoname import _ensure_sri_fields

def si_before_submit(doc, method):
    # Última verificación/relleno antes de enviar
    _ensure_sri_fields(doc)

    missing = [
        f for f in [
            "sri_establishment_code",
            "sri_emission_point_code",
            "sri_sequential_assigned",
        ]
        if not getattr(doc, f, None)
    ]
    if missing:
        frappe.throw("No se ha asignado la serie SRI correctamente. Falta: " + ", ".join(missing))
