import frappe

@frappe.whitelist()
def set_selected_warehouse(warehouse: str, set_user_permission: int = 0):
    """Persist user's selected warehouse in User and optionally flip a User Permission."""
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw("Not logged in")

    # Validate: only allow warehouses flagged as establishments
    if not frappe.db.exists(
        "Warehouse",
        {"name": warehouse, "custom_sri_is_establishment": 1}
    ):
        frappe.throw(f"Warehouse {warehouse} is not a valid establishment")

    # Save selected WH into User
    frappe.db.set_value("User", frappe.session.user, "custom_jos_selected_warehouse", warehouse)
    frappe.db.commit()

    # If flag is set, also update User Permissions
    if int(set_user_permission or 0):
        _upsert_user_permission_for_wh(frappe.session.user, warehouse)

    return {"ok": True, "warehouse": warehouse}

def inject_selected_warehouse(bootinfo):
    """Inject user's selected warehouse into frappe.boot"""
    wh = frappe.db.get_value("User", frappe.session.user, "custom_jos_selected_warehouse")
    bootinfo.jos_selected_establishment = wh


def _upsert_user_permission_for_wh(user: str, warehouse: str):
    """Optional: keep exactly one Warehouse User Permission for this user."""
    # Delete existing permissions
    for name in frappe.get_all("User Permission",
                               filters={"user": user, "allow": "Warehouse"},
                               pluck="name"):
        frappe.delete_doc("User Permission", name, ignore_permissions=True)

    # Insert fresh one
    up = frappe.new_doc("User Permission")
    up.user = user
    up.allow = "Warehouse"
    up.for_value = warehouse
    # Leave applicable_for blank to apply broadly, or set to DocTypes like "Sales Invoice"
    up.insert(ignore_permissions=True)

@frappe.whitelist()
def get_establishment_options():
    """Return only Warehouses flagged as establishments + current selection."""
    user = frappe.session.user
    selected = frappe.db.get_value("User", user, "custom_jos_selected_warehouse")

    # Only warehouses with establishment flag
    whs = frappe.get_all(
        "Warehouse",
        filters={"custom_sri_is_establishment": 1},
        fields=["name", "warehouse_name as label", "custom_establishment_code"]
    )

    # Optional: you can format label to include code
    for w in whs:
        if w.get("custom_establishment_code"):
            w["label"] = f"{w['custom_establishment_code']} - {w['label']}"

    return {
        "warehouses": whs,
        "allow_consolidado": False,  # flip if you want the "Consolidado" option
        "selected": selected,
    }

def on_login_redirect(login_manager):
    """Server-side login hook.
    We don't force a redirect here; the client-side route guard handles it.
    Keep this as a light log to avoid interfering with Desk boot."""
    try:
        frappe.logger("josfe").info(f"[login] user={frappe.session.user}")
    except Exception:
        pass

def on_logout(login_manager=None, user=None, *args, **kwargs):
    """
    Frappe calls this with keyword `login_manager`.
    Resolve the username robustly and clear the selected warehouse.
    """
    try:
        usr = user or getattr(login_manager, "user", None) or frappe.session.user
        if not usr:
            return
        frappe.db.set_value("User", usr, "custom_jos_selected_warehouse", None)
        frappe.db.commit()
        frappe.logger("josfe").info(f"[logout] cleared selection for user={usr}")
    except Exception as e:
        frappe.log_error(f"on_logout error: {e}", "josfe.user_location.session.on_logout")