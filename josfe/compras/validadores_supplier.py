from josfe.taxidvalidator.ec_tax_validator import validate_and_assign_tax_id

def validate_tax_id(doc, method):
    validate_and_assign_tax_id(doc, "custom_jos_ruc_supplier", assign_tax_id=True, assign_customer_type=True)

