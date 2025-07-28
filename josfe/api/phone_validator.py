import re
import frappe
from frappe import _

def validate_entity_phones(doc, method):
    if not hasattr(doc, "custom_jos_telefonos"):
        return

    for row in doc.custom_jos_telefonos:
        phone = re.sub(r'\D', '', (row.phone or "").strip())

        # Must be all digits
        if not phone.isdigit():
            frappe.throw(_("❌ Teléfono inválido en fila {0}: solo se permiten números.").format(row.idx))

        # Rule 1: Mobile (starts with 09) => 10 digits
        if phone.startswith('09'):
            if len(phone) != 10:
                frappe.throw(_("❌ Teléfono móvil inválido en fila {0}: debe tener 10 dígitos.").format(row.idx))

        # Rule 2: Landline (starts with 02–08) => 9 digits
        elif phone.startswith('0') and len(phone) >= 2 and phone[1] in '2345678':
            if len(phone) != 9:
                frappe.throw(_("❌ Teléfono fijo inválido en fila {0}: debe tener 9 dígitos.").format(row.idx))

        # Rule 3: Short/local (starts with 2–9) => 7 digits
        elif phone[0] in '23456789':
            if len(phone) != 7:
                frappe.throw(_("❌ Teléfono local inválido en fila {0}: debe tener 7 dígitos.").format(row.idx))

        else:
            frappe.throw(_("❌ Teléfono inválido en fila {0}: formato no reconocido.").format(row.idx))

def validate_contact_phones(doc, method):
    if not hasattr(doc, "phone_nos"):
        return

    for row in doc.phone_nos:
        phone = re.sub(r'\D', '', (row.phone or "").strip())

        # Must be all digits
        if not phone.isdigit():
            frappe.throw(_("❌ Teléfono inválido en fila {0}: solo se permiten números.").format(row.idx))

        # Rule 1: Mobile (starts with 09) => 10 digits
        if phone.startswith('09'):
            if len(phone) != 10:
                frappe.throw(_("❌ Teléfono móvil inválido en fila {0}: debe tener 10 dígitos.").format(row.idx))

        # Rule 2: Landline (starts with 02–08) => 9 digits
        elif phone.startswith('0') and len(phone) >= 2 and phone[1] in '2345678':
            if len(phone) != 9:
                frappe.throw(_("❌ Teléfono fijo inválido en fila {0}: debe tener 9 dígitos.").format(row.idx))

        # Rule 3: Short/local (starts with 2–9) => 7 digits
        elif phone[0] in '23456789':
            if len(phone) != 7:
                frappe.throw(_("❌ Teléfono local inválido en fila {0}: debe tener 7 dígitos.").format(row.idx))

        else:
            frappe.throw(_("❌ Teléfono inválido en fila {0}: formato no reconocido.").format(row.idx))