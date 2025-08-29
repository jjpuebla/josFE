import frappe

def _selected_wh():
    """Return the warehouse currently stored on the User record."""
    return frappe.db.get_value("User", frappe.session.user, "custom_jos_selected_warehouse") or ""

def _clause(doctype: str, warehouse_field: str):
    """Helper to build SQL clause restricting by warehouse."""
    wh = _selected_wh()
    if not wh:
        # No selection → show nothing, force user to pick
        return "1=0"
    wh_esc = frappe.db.escape(wh)
    return f"`tab{doctype}`.`{warehouse_field}` = {wh_esc}"

# Sales Invoice: restrict lists/standard reports
def si_query(user):
    return _clause("Sales Invoice", "custom_jos_level3_warehouse")

# Prevent opening docs from other warehouses
def si_has_permission(doc, user=None):
    wh = _selected_wh()
    return bool(wh and getattr(doc, "custom_jos_level3_warehouse", None) == wh)

# SRI XML Queue: restrict lists/standard reports
def xml_query(user):
    return _clause("SRI XML Queue", "custom_jos_level3_warehouse")

# Prevent opening XML docs from other warehouses
def xml_has_permission(doc, user=None):
    wh = _selected_wh()
    return bool(wh and getattr(doc, "custom_jos_level3_warehouse", None) == wh)

