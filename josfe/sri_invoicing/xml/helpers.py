# apps/josfe/josfe/sri_invoicing/xml/helpers.py
import frappe, os, base64

def _append_comment(doc, msg: str):
    """Append a comment to the doc's timeline (safe)."""
    doc.add_comment("Comment", msg)

def _db_set_state(doc, state: str):
    """Update doc.state in DB."""
    frappe.db.set_value(doc.doctype, doc.name, "state", state)
    frappe.db.commit()

def _format_msgs(prefix: str, mensajes: list[dict]) -> str:
    """Format SRI message dicts into a readable block."""
    out = [f"**{prefix}**"]
    for m in mensajes or []:
        ident = m.get("identificador")
        msg = m.get("mensaje")
        info = m.get("informacionAdicional")
        tipo = m.get("tipo")
        out.append(f"- [{ident}] {msg} — {info} ({tipo})")
    return "\n".join(out)

def _attach_private_file(doc, filename: str, content: bytes) -> str:
    """Attach content as private file and return file_url (Frappe v15-safe)."""
    filedoc = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "is_private": 1,
        "attached_to_doctype": doc.doctype,
        "attached_to_name": doc.name,
        "content": content,
        "folder": "Home/Attachments",
    }).insert(ignore_permissions=True)
    return filedoc.file_url
