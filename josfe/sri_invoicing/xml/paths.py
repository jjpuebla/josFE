# apps/josfe/josfe/sri_invoicing/xml/paths.py
from __future__ import annotations
import os
import frappe

# Root under /private/files
ROOT_FOLDER_NAME = "SRI"

# Short names per your spec
GEN = "GENERADOS"
SIGNED = "FIRMADOS"
SIGNED_SENT_PENDING = os.path.join(SIGNED, "PENDIENTES")
SIGNED_REJECTED = os.path.join(SIGNED, "Rechazados")  # Capital R, rest lowercase
AUTH = "AUTORIZADOS"
NOT_AUTH = "NO_AUTORIZADOS"

def _root_abs() -> str:
    base = frappe.get_site_path("private", "files", ROOT_FOLDER_NAME)
    os.makedirs(base, exist_ok=True)
    return base

def ensure_all_dirs() -> None:
    """Create the full directory tree if missing."""
    for rel in [GEN, SIGNED, SIGNED_SENT_PENDING, SIGNED_REJECTED, AUTH, NOT_AUTH]:
        os.makedirs(os.path.join(_root_abs(), rel), exist_ok=True)

def rel_for_state(state: str, *, origin: str | None = None) -> str:
    """
    Map queue state to a relative folder.
    origin: "Recepción" or "Autorización" when state == 'Devuelto'.
    """
    s = (state or "").strip().lower()
    if s == "generado":   return GEN
    if s == "firmado":    return SIGNED
    if s == "enviado":    return SIGNED_SENT_PENDING
    if s == "autorizado": return AUTH
    if s == "devuelto":
        # Recepción DEVUELTA => Rechazados (esquemas/permiso)
        # Autorización NO AUTORIZADO => NO_AUTORIZADOS
        return NOT_AUTH if (origin or "").lower().startswith("autoriz") else SIGNED_REJECTED
    return GEN  # fallback

def abs_path(rel_dir: str, filename: str) -> str:
    return os.path.join(_root_abs(), rel_dir, filename)

def to_file_url(rel_dir: str, filename: str) -> str:
    rel = os.path.join(ROOT_FOLDER_NAME, rel_dir, filename).replace("\\", "/")
    return f"/private/files/{rel}"

def strip_private_prefix(file_url: str) -> str:
    return (file_url or "").replace("/private/files/", "", 1).lstrip("/")
