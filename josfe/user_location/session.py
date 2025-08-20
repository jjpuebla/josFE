import frappe

@frappe.whitelist()
def get_establishments():
    """Return warehouses marked as 'establishment'."""
    warehouses = frappe.get_all("Warehouse", filters={"custom_sri_is_establishment": 1}, fields=["name"])
    return warehouses

@frappe.whitelist()
def set_selected_establishment(warehouse):
    if not frappe.db.exists("Warehouse", warehouse):
        frappe.throw("Invalid warehouse selected")

    frappe.defaults.set_user_default("jos_selected_establishment", warehouse)
    return "OK"

def extend_boot_with_location(bootinfo):
    defaults_to_inject = [
        "jos_selected_establishment",
        "jos_cost_center",
        "jos_income_account",
        "jos_expense_account"
        # Add more as needed
    ]

    for dkey in defaults_to_inject:
        bootinfo.user["defaults"][dkey] = frappe.defaults.get_user_default(dkey)

@frappe.whitelist()
def set_selected_establishment(warehouse):
    if not frappe.db.exists("Warehouse", warehouse):
        frappe.throw("Invalid warehouse selected")

    # Store selected location
    frappe.defaults.set_user_default("jos_selected_establishment", warehouse)

    # Fetch warehouse and extract defaults
    doc = frappe.get_doc("Warehouse", warehouse)

    default_map = {
        "jos_cost_center": doc.get("custom_jos_cost_center"),
        "jos_income_account": doc.get("custom_jos_income_account"),
        "jos_expense_account": doc.get("custom_jos_expense_account"),
        # Add more here as needed
    }

    for key, value in default_map.items():
        if value:
            frappe.defaults.set_user_default(key, value)

    return "OK"