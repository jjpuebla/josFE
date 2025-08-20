import frappe

def get_user_selected_warehouse(user=None):
    user = user or frappe.session.user
    return frappe.defaults.get_user_default("jos_selected_establishment", user)

def get_child_warehouses(parent):
    if not parent:
        return []
    return frappe.get_all("Warehouse", filters={"parent_warehouse": parent}, pluck="name") + [parent]

# For Sales Invoice
def get_permission_query_conditions(user):
    selected = get_user_selected_warehouse(user)
    if not selected:
        return "1=0"

    children = get_child_warehouses(selected)
    if not children:
        return "1=0"

    warehouse_list = "', '".join(children)
    return f"""(`tabSales Invoice`.`custom_jos_level3_warehouse` IN ('{warehouse_list}'))"""

def has_permission(doc, user):
    selected = get_user_selected_warehouse(user)
    return doc.custom_jos_level3_warehouse in get_child_warehouses(selected)
