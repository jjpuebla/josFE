from josfe.taxidvalidator.ec_tax_validator import validate_and_assign_tax_id
import frappe

def validate_tax_id(doc, method):
    validate_and_assign_tax_id(doc, "custom_jos_ruc", assign_tax_id=True, assign_customer_type=False)

def sync_company_name(doc, method=None):
    src = (doc.get("custom_jos_razon_social") or "").strip()
    if src and doc.get("company_name") != src:
        doc.company_name = src