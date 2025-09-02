# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/xml/service.py

import os, shutil
import frappe
from frappe.utils import cstr, now_datetime

# ⬇️ Switch to the deterministic builder (no other imports touched)
from josfe.sri_invoicing.xml.builders import build_factura_xml
from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import SRIQueueState

# ------------------------------
# Stage folder management helpers
# ------------------------------

# Map queue states → subfolder names (mirror your business states)
STATE_DIR_MAP = {
    "Generado": "Generado",
    "Firmado": "Firmado",
    "Enviado": "Enviado",
    "Autorizado": "Autorizado",
    "Devuelto": "Devuelto",
    "Cancelado": "Cancelado",
    "Error": "Error",
}

def _ensure_stage_dir(stage_folder: str) -> str:
    """Ensure /private/files/<stage_folder> exists; return absolute path."""
    base = frappe.get_site_path("private", "files")
    full = os.path.join(base, stage_folder)
    os.makedirs(full, exist_ok=True)
    return full

def _write_xml_to_stage(filename: str, xml: str, stage_folder: str) -> str:
    """
    Write XML as a real file under /private/files/<stage_folder>/<filename>.
    Return file_url (/private/files/<stage_folder>/<filename>).
    """
    full_dir = _ensure_stage_dir(stage_folder)
    full_path = os.path.join(full_dir, filename)
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(xml)
    return f"/private/files/{stage_folder}/{filename}"

def _move_xml_file(old_file_url: str, new_stage: str) -> str:
    """
    Move the same file to another stage folder. Return new file_url.
    If old_file_url missing or file not found, return it unchanged.
    """
    if not old_file_url:
        return old_file_url

    site_files = frappe.get_site_path("private", "files")
    rel_old = old_file_url.lstrip("/private/files/")  # e.g. Generado/002-002-000000065.xml
    old_path = os.path.join(site_files, rel_old)
    if not os.path.exists(old_path):
        return old_file_url

    filename = os.path.basename(old_path)
    new_dir = _ensure_stage_dir(new_stage)
    new_path = os.path.join(new_dir, filename)

    if os.path.abspath(old_path) != os.path.abspath(new_path):
        shutil.move(old_path, new_path)

    return f"/private/files/{new_stage}/{filename}"

def _retarget_file_doc_url_for_queue(queue_name: str, new_url: str) -> None:
    """
    Update the single File doc attached to this queue row to point to new_url.
    (We keep exactly ONE File per queue row.)
    """
    if not new_url:
        return
    for fname in frappe.get_all(
        "File",
        filters={"attached_to_doctype": "SRI XML Queue", "attached_to_name": queue_name},
        pluck="name",
    ):
        frappe.db.set_value("File", fname, "file_url", new_url)

# ------------------------------
# Signing & state transition
# ------------------------------

def _process_signing(qdoc):
    """
    Triggered when the queue state is set to 'Firmado'.
    - Assumes XML already exists (built in 'Generado')
    - TODO: Replace the file content with signed XML (XAdES-BES)
    - Moves the physical file to /Firmado and keeps the same File doc
    """
    if not cstr(qdoc.xml_file):
        frappe.throw("No existe XML para firmar en esta fila de la cola.")

    # TODO: plug real signing here (read qdoc.xml_file, sign, overwrite same path before moving)

    # Move the physical file to /Firmado
    new_url = _move_xml_file(qdoc.xml_file, STATE_DIR_MAP[SRIQueueState.Firmado.value])
    if new_url and new_url != qdoc.xml_file:
        _retarget_file_doc_url_for_queue(qdoc.name, new_url)
        qdoc.db_set("xml_file", new_url)

    # Do NOT change state here (the user already set it to 'Firmado')
    qdoc.db_set("last_error", "")
    qdoc.db_set("last_transition_at", now_datetime())
    qdoc.db_set("last_transition_by", frappe.session.user)

def _process_transmission(qdoc):
    """
    Triggered when state is set to 'Autorizado' or 'Devuelto' (or 'Enviado').
    - Move the file to the corresponding folder.
    - If 'Autorizado', you may generate/attach PDF to the Sales Invoice.
    """
    if not cstr(qdoc.xml_file):
        return

    stage_folder = STATE_DIR_MAP.get(qdoc.state)
    if stage_folder:
        new_url = _move_xml_file(qdoc.xml_file, stage_folder)
        if new_url and new_url != qdoc.xml_file:
            _retarget_file_doc_url_for_queue(qdoc.name, new_url)
            qdoc.db_set("xml_file", new_url)

    if qdoc.state == SRIQueueState.Autorizado.value:
        # TODO: generate PDF for the linked Sales Invoice and attach it there (not to the Queue)
        # Example (pseudo):
        # pdf_content = frappe.get_print("Sales Invoice", qdoc.sales_invoice, print_format="Your Format", as_pdf=True)
        # frappe.get_doc({
        #     "doctype": "File",
        #     "file_name": f"{qdoc.sales_invoice}.pdf",
        #     "content": pdf_content,
        #     "is_private": 1,
        #     "attached_to_doctype": "Sales Invoice",
        #     "attached_to_name": qdoc.sales_invoice,
        # }).insert(ignore_permissions=True)
        pass

    qdoc.db_set("last_transition_at", now_datetime())
    qdoc.db_set("last_transition_by", frappe.session.user)

# ------------------------------
# Hook
# ------------------------------

def on_queue_update(doc, method=None):
    """
    Hook: called whenever SRI XML Queue is updated.
    - If state == 'Firmado'         → perform signing (placeholder) and move to /Firmado.
    - If state in {'Enviado','Autorizado','Devuelto','Cancelado','Error'}
                                    → move the file to the matching folder.
    - Otherwise (e.g. 'Generado')   → nothing to do here; initial build happens in queue/api.py.
    """
    try:
        state = cstr(doc.state)

        if state == SRIQueueState.Firmado.value:
            _process_signing(doc)

        elif state in {
            SRIQueueState.Enviado.value,
            SRIQueueState.Autorizado.value,
            SRIQueueState.Devuelto.value,
            SRIQueueState.Cancelado.value,
            SRIQueueState.Error.value,
        }:
            _process_transmission(doc)

        # 'Generado' is handled by build step in queue/api.py; no move here.

    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="SRI XML Queue on_update failure",
        )
