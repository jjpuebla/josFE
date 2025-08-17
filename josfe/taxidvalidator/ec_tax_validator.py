import frappe
from frappe import _

def validate_and_assign_tax_id(doc, source_field, assign_tax_id=True, assign_customer_type=False):
    raw_id = (doc.get(source_field) or "").strip().upper()

    if not raw_id:
        frappe.throw(_("Identificación Fiscal es obligatoria."))

    # Consumidor Final
    if raw_id == "9999999999999":
        if assign_tax_id:
            doc.tax_id = raw_id
        if assign_customer_type:
            set_entity_type(doc, "Individual")
        return

    # Pasaporte extranjero
    if raw_id.startswith("P-"):
        passport_value = raw_id[2:]
        if assign_tax_id:
            doc.tax_id = passport_value
        if assign_customer_type:
            set_entity_type(doc, "Individual")
        return

    if not raw_id.isdigit() or len(raw_id) not in [10, 13]:
        frappe.throw(_("La Identificación Fiscal debe tener 10 o 13 dígitos, o iniciar con 'P-' para pasaportes."))

    if not is_valid_ec_tax_id(raw_id):
        frappe.throw(_("Identificación Fiscal inválida (ni Cédula ni RUC)."))

    if frappe.db.exists(doc.doctype, {source_field: raw_id, "name": ("!=", doc.name)}):
        frappe.throw(_("Ya existe un {0} con la misma Identificación Fiscal.").format(doc.doctype))

    if assign_tax_id:
        doc.tax_id = raw_id

    if assign_customer_type:
        third_digit = int(raw_id[2])
        entity_type = "Individual" if third_digit < 6 else "Company"
        set_entity_type(doc, entity_type)

def set_entity_type(doc, value):
    if doc.doctype == "Customer":
        doc.customer_type = value
    elif doc.doctype == "Supplier":
        doc.supplier_type = value

def is_valid_ec_tax_id(id):
    province = int(id[:2])
    if province < 1 or province > 24:
        return False

    try:
        third = int(id[2])
    except (IndexError, ValueError):
        frappe.throw(_("La Identificación Fiscal no tiene un formato válido."))

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

def _norm(v):
    return (v or "").strip().upper()

def enforce_tax_id_immutability(doc, method=None):
    # New doc? Nothing to enforce.
    if doc.is_new():
        return

    # Reload old to compare
    old_doc = frappe.get_doc(doc.doctype, doc.name)

    # Map your custom field per Doctype
    custom_field_map = {
        "Customer": "custom_jos_tax_id_validador",
        "Supplier": "custom_jos_ruc_supplier",
        "Company":  "custom_jos_ruc",
    }
    custom_field = custom_field_map.get(doc.doctype)

    # Core tax_id cannot change after save
    if _norm(old_doc.tax_id) and _norm(doc.tax_id) != _norm(old_doc.tax_id):
        frappe.throw(_("El campo Tax ID no puede ser modificado una vez guardado."))

    # Custom tax field cannot change after save
    if custom_field and _norm(old_doc.get(custom_field)) and _norm(doc.get(custom_field)) != _norm(old_doc.get(custom_field)):
        frappe.throw(_("El campo de identificación tributaria no puede ser modificado."))