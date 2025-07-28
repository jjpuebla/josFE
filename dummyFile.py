import re
import frappe
from frappe import _

def validate_entity_phones(doc, method):
    if not hasattr(doc, "custom_jos_telefonos"):
        return

    for row in doc.custom_jos_telefonos:
        phone = (row.phone or "").strip().lower()

        # Match base + optional extension: digits only, optional x12345
        match = re.match(r'^(\d+)(x\d{1,5})?$', phone)
        if not match:
            frappe.throw(_("❌ Teléfono inválido en fila {0}: solo dígitos y 'x' opcional.").format(row.idx))

        base = match.group(1)

        if base.startswith('09'):
            if len(base) != 10:
                frappe.throw(_("❌ Celular inválido en fila {0}: debe tener 10 dígitos.").format(row.idx))

        elif base.startswith('0') and len(base) >= 2 and base[1] in "2345678":
            if len(base) != 9:
                frappe.throw(_("❌ Teléfono fijo inválido en fila {0}: debe tener 9 dígitos.").format(row.idx))

        elif base[0] in "23456789":
            if len(base) != 7:
                frappe.throw(_("❌ Número local inválido en fila {0}: debe tener 7 dígitos.").format(row.idx))
        else:
            frappe.throw(_("❌ Teléfono inválido en fila {0}: formato no reconocido.").format(row.idx))
