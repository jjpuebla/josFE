# apps/josfe/josfe/user_location/session.py
from __future__ import annotations
import frappe
from frappe import _
from typing import Optional

SESSION_KEY = "jos_selected_establishment"
CONSOLIDADO_MAGIC = "__CONSOLIDADO__"

# ---------- internal helpers ----------

def _get_session_selected() -> Optional[str]:
    return frappe.local.session.data.get(SESSION_KEY)

def _set_session_selected(value: Optional[str]) -> None:
    """Store the selection in the session dict and flush so subsequent requests see it."""
    if value:
        frappe.local.session.data[SESSION_KEY] = value
    else:
        frappe.local.session.data.pop(SESSION_KEY, None)
    if getattr(frappe.local, "session_obj", None):
        frappe.local.session_obj.update()

def _allowed_establishments_for_user(user: Optional[str] = None) -> list[dict]:
    """Return establishments the current user can pick.
    Default: all Warehouses with custom_sri_is_establishment = 1 and not disabled."""
    user = user or frappe.session.user

    warehouses = frappe.get_all(
        "Warehouse",
        filters={"custom_sri_is_establishment": 1, "disabled": 0},
        fields=["name", "warehouse_name as label"],
        order_by="warehouse_name asc",
    )

    # expose a consolidated option if you want it available
    allow_consolidado = True
    return warehouses, allow_consolidado

# ---------- public API (whitelisted) ----------

@frappe.whitelist()
def get_establishment_options() -> dict:
    """Load pickable establishments for the current user."""
    warehouses, allow_consolidado = _allowed_establishments_for_user()
    return {
        "warehouses": warehouses,
        "allow_consolidado": allow_consolidado,
        "selected": _get_session_selected(),
    }

@frappe.whitelist()
def set_selected_establishment(warehouse: Optional[str] = None) -> dict:
    if not warehouse:
        _set_session_selected(None)
        return {"ok": True, "selected": None}

    if warehouse != CONSOLIDADO_MAGIC:
        if not frappe.db.exists("Warehouse", warehouse):
            frappe.throw(_("Warehouse {0} does not exist").format(frappe.bold(warehouse)))
        is_est = frappe.db.get_value("Warehouse", warehouse, "custom_sri_is_establishment") == 1
        if not is_est:
            frappe.throw(_("Warehouse {0} is not flagged as Establishment").format(frappe.bold(warehouse)))

    _set_session_selected(warehouse)

    # ✅ Invalidate session + boot cache for this user
    frappe.clear_cache(user=frappe.session.user)

    return {"ok": True, "selected": warehouse}

# ---------- hooks ----------

def extend_bootinfo(bootinfo: dict):
    """hooks.boot_session → inject our selection into frappe.boot."""
    bootinfo["jos_selected_establishment"] = _get_session_selected()

def on_login_redirect(login_manager):
    """If user has no selection, land them on the picker first."""
    try:
        if "System Manager" in (frappe.get_roles() or []):
            return
        if _get_session_selected():
            return
        frappe.local.response["home_page"] = "/app/location-picker"
    except Exception:
        frappe.log_error("JOSFE on_login_redirect error")

def on_logout(user=None):
    """Server-side logging on logout. (Uncomment clear to wipe selection on logout.)"""
    try:
        val = _get_session_selected()
        frappe.logger("josfe").info(f"logout {frappe.session.user}, selected={val}")
        # _set_session_selected(None)  # ← uncomment if you want to clear on logout
    except Exception:
        pass


