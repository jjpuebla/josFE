# apps/josfe/josfe/sri_invoicing/tests/smoke_exec.py
import frappe
from typing import Any

def smoke() -> dict[str, Any]:
    """Minimal proof that bench execute can import & run code."""
    return {
        "ok": True,
        "site": getattr(frappe.local, "site", None),
        "user": frappe.session.user,
        "app": "josfe",
    }

def echo(msg: str = "hello", n: int = 1) -> dict[str, Any]:
    """Echo back a message n times to test --kwargs parsing."""
    return {"echo": msg * int(n)}

def probe() -> dict[str, Any]:
    """Touch the DB safely to prove we can read doctypes."""
    return {
        "companies": frappe.get_all("Company", pluck="name"),
        "customers_count": frappe.db.count("Customer"),
    }

def crash() -> None:
    """Intentionally raise to check error reporting."""
    raise Exception("smoke_exec.crash: intentional exception for testing")
