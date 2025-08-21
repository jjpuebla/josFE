# apps/josfe/josfe/user_location/permissions.py
import frappe

SESSION_KEY = "jos_selected_establishment"

def _session_selection(user=None):
    # always the current session; ignore 'user'
    return frappe.local.session.data.get(SESSION_KEY)

def _children_of(parent):
    """Return list of allowed warehouses (parent + direct children)."""
    if not parent:
        return []
    children = frappe.get_all("Warehouse", filters={"parent_warehouse": parent}, pluck="name")
    return [parent] + children

# ---- Sales Invoice ----
def get_permission_query_conditions(user):
    selected = _session_selection()
    if not selected or selected == "__CONSOLIDADO__":
        # No restriction when Consolidado or nothing selected (you may prefer 1=0 if nothing)
        return None

    wh_list = _children_of(selected)
    if not wh_list:
        return "1=0"
    wh_sql = "', '".join(wh_list)
    return f"`tabSales Invoice`.`custom_jos_level3_warehouse` in ('{wh_sql}')"

def has_permission(doc, user):
    selected = _session_selection()
    if not selected or selected == "__CONSOLIDADO__":
        return True
    return (getattr(doc, "custom_jos_level3_warehouse", None) in _children_of(selected))
