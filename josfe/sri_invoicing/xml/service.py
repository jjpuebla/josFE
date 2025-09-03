# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/xml/service.py

import os, shutil, tempfile, subprocess
import frappe
from frappe.utils import cstr, now_datetime

from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import SRIQueueState
from josfe.sri_invoicing.xml.xades_template import inject_signature_template

PRIVATE_PREFIX = "/private/files/"

def _ensure_stage_dir(stage_folder: str) -> str:
    base = frappe.get_site_path("private", "files")
    full = os.path.join(base, stage_folder)
    os.makedirs(full, exist_ok=True)
    return full

def _resolve_private_relpath(file_url: str) -> str:
    if not file_url:
        return None
    if file_url.startswith(PRIVATE_PREFIX):
        return file_url.split(PRIVATE_PREFIX, 1)[1].lstrip("/")
    frappe.throw(f"Unrecognized file_url format: {file_url}")

def _move_xml_file(old_url: str, new_stage: str) -> str:
    rel_path = _resolve_private_relpath(old_url)
    if not rel_path:
        return None

    site_files = frappe.get_site_path("private", "files")
    old_path = os.path.join(site_files, rel_path)
    if not os.path.exists(old_path):
        frappe.throw(f"Source XML file not found: {old_path}")

    new_folder = os.path.join(site_files, new_stage)
    os.makedirs(new_folder, exist_ok=True)

    filename = os.path.basename(old_path)
    new_path = os.path.join(new_folder, filename)

    shutil.move(old_path, new_path)
    return f"/private/files/{new_stage}/{filename}"

# ------------------------------
# Signing & state transition
# ------------------------------

def _process_signing(qdoc):
    if not cstr(qdoc.xml_file):
        frappe.throw("No XML file path in this SRI XML Queue row.")

    site_files = frappe.get_site_path("private", "files")
    rel_old = _resolve_private_relpath(qdoc.xml_file)
    old_path = os.path.join(site_files, rel_old)
    if not os.path.exists(old_path):
        frappe.throw(f"XML file not found on disk: {old_path}")

    # Load credentials
    cred = frappe.get_doc("Credenciales SRI", {"company": qdoc.company, "jos_activo": 1})
    priv_pem = frappe.get_site_path("private", "files", f"{cred.name}_private.pem")
    cert_pem = frappe.get_site_path("private", "files", f"{cred.name}_cert.pem")
    if not os.path.exists(priv_pem) or not os.path.exists(cert_pem):
        frappe.throw("❌ PEM files not found. Run 'Validar Firma' in Credenciales SRI.")

    # Inject signature template
    with open(old_path, "r", encoding="utf-8") as f:
        raw_xml = f.read()
    ready_xml = inject_signature_template(raw_xml, cert_pem)
    if ready_xml != raw_xml:
        with open(old_path, "w", encoding="utf-8") as f:
            f.write(ready_xml)

    # Run xmlsec1
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp_out:
        cmd = [
            "xmlsec1", "--sign",
            "--privkey-pem", f"{priv_pem},{cert_pem}",
            "--id-attr:id", "factura",
            "--output", tmp_out.name,
            old_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or b"").decode() or str(e)
            frappe.throw(f"Error running xmlsec1: {frappe.utils.escape_html(stderr)}")

        os.replace(tmp_out.name, old_path)

    # Move to Firmado
    new_url = _move_xml_file(qdoc.xml_file, "Firmado")
    if new_url:
        qdoc.db_set("xml_file", new_url)

    qdoc.db_set("last_error", "")
    qdoc.db_set("last_transition_at", now_datetime())
    qdoc.db_set("last_transition_by", frappe.session.user)

def _process_transmission(qdoc, stage_folder: str):
    if not cstr(qdoc.xml_file):
        frappe.throw("No XML file path in this SRI XML Queue row.")

    new_url = _move_xml_file(qdoc.xml_file, stage_folder)
    if new_url:
        qdoc.db_set("xml_file", new_url)

    qdoc.db_set("last_error", "")
    qdoc.db_set("last_transition_at", now_datetime())
    qdoc.db_set("last_transition_by", frappe.session.user)

def on_queue_update(doc, method=None):
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
            _process_transmission(doc, state)
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="SRI XML Queue on_update failure",
        )
