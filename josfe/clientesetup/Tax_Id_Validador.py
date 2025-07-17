# server_side_tax_id_validation.py

import frappe
from frappe import _

def validate_tax_id(doc, method):
    raw_id = (doc.get("custom_jos_tax_id_validador") or "").strip().upper()

    if not raw_id:
        frappe.throw(_("Identificación Fiscal es obligatoria."))

    # Consumidor Final (valid dummy RUC)
    if raw_id == "9999999999999":
        doc.tax_id = raw_id
        doc.customer_type = "Individual"
        return

    # Pasaporte extranjero
    if raw_id.startswith("P-"):
        doc.tax_id = raw_id[2:]
        doc.customer_type = "Individual"
        return

    # Validate digit structure
    if not raw_id.isdigit() or len(raw_id) not in [10, 13]:
        frappe.throw(_("La Identificación Fiscal debe tener 10 o 13 dígitos, o iniciar con 'P-' para pasaportes."))

    # Validate Ecuadorian ID
    if not is_valid_ec_tax_id(raw_id):
        frappe.throw(_("Identificación Fiscal inválida (ni Cédula ni RUC)."))

    # Check for duplicate Tax ID
    if frappe.db.exists("Customer", {
        "custom_jos_tax_id_validador": raw_id,
        "name": ("!=", doc.name)
    }):
        frappe.throw(_("Ya existe un cliente con la misma Identificación Fiscal."))

    # Assign validated Tax ID and Customer Type
    doc.tax_id = raw_id
    third_digit = int(raw_id[2])
    doc.customer_type = "Individual" if third_digit < 6 else "Company"


def is_valid_ec_tax_id(id):
    province = int(id[:2])
    if province < 1 or province > 24:
        return False

    third = int(id[2])

    if third < 6:
        return validate_cedula(id[:10])
    elif third == 6:
        return validate_ruc_public(id)
    elif third == 9:
        return validate_ruc_private(id)

    return False


def validate_cedula(cedula):
    digits = list(map(int, cedula))
    check = digits.pop()
    total = 0
    for i, d in enumerate(digits):
        val = d * 2 if i % 2 == 0 else d
        if val > 9:
            val -= 9
        total += val
    return check == (10 - total % 10) % 10


def validate_ruc_public(ruc):
    if len(ruc) != 13 or not ruc.endswith("0001"):
        return False
    coeffs = [3, 2, 7, 6, 5, 4, 3, 2]
    digits = list(map(int, ruc))
    total = sum(d * c for d, c in zip(digits[:8], coeffs))
    check = 11 - (total % 11)
    return digits[8] == (0 if check == 11 else check)


def validate_ruc_private(ruc):
    if len(ruc) != 13 or not ruc.endswith("001"):
        return False
    coeffs = [4, 3, 2, 7, 6, 5, 4, 3, 2]
    digits = list(map(int, ruc))
    total = sum(d * c for d, c in zip(digits[:9], coeffs))
    check = 11 - (total % 11)
    return digits[9] == (0 if check == 11 else check)
