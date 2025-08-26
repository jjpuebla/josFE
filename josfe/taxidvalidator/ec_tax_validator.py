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

    # Formato general
    if not raw_id.isdigit() or len(raw_id) not in [10, 13]:
        frappe.throw(_("La Identificación Fiscal debe tener 10 o 13 dígitos, o iniciar con 'P-' para pasaportes."))

    # Validar con nuestras reglas ajustadas
    if not is_valid_ec_tax_id(raw_id):
        frappe.throw(_("Identificación Fiscal inválida (ni Cédula ni RUC)."))

    # Evitar duplicados
    if frappe.db.exists(doc.doctype, {source_field: raw_id, "name": ("!=", doc.name)}):
        frappe.throw(_("Ya existe un {0} con la misma Identificación Fiscal.").format(doc.doctype))

    # Asignar valores
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
        return validate_ruc_public_skip(id)   # <- modificado
    elif third == 9:
        return validate_ruc_private_skip(id)  # <- modificado

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


# ===== RUC con "skip" del dígito verificador =====

def validate_ruc_public_skip(ruc):
    # Solo validar longitud y terminación
    return len(ruc) == 13 and ruc.endswith("0001")

def validate_ruc_private_skip(ruc):
    # Solo validar longitud y terminación
    return len(ruc) == 13 and ruc.endswith("001")


# --- utilidades ---

def _norm(v):
    return (v or "").strip().upper()

def enforce_tax_id_immutability(doc, method=None):
    if doc.is_new():
        return

    old_doc = frappe.get_doc(doc.doctype, doc.name)
    custom_field_map = {
        "Customer": "custom_jos_tax_id_validador",
        "Supplier": "custom_jos_ruc_supplier",
        "Company":  "custom_jos_ruc",
    }
    custom_field = custom_field_map.get(doc.doctype)

    if _norm(old_doc.tax_id) and _norm(doc.tax_id) != _norm(old_doc.tax_id):
        frappe.throw(_("El campo Tax ID no puede ser modificado una vez guardado."))

    if custom_field and _norm(old_doc.get(custom_field)) and _norm(doc.get(custom_field)) != _norm(old_doc.get(custom_field)):
        frappe.throw(_("El campo de identificación tributaria no puede ser modificado."))
