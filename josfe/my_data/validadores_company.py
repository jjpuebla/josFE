from josfe.taxidvalidator.ec_tax_validator import validate_and_assign_tax_id
import frappe

def validate_tax_id(doc, method):
    validate_and_assign_tax_id(doc, "custom_jos_ruc", assign_tax_id=True, assign_customer_type=False)

