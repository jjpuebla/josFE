# apps/josfe/josfe/sri_invoicing/pdf_emailing/emailer.py
# -*- coding: utf-8 -*-

import os
import frappe
from typing import Optional, List, Tuple

from josfe.sri_invoicing.pdf_emailing.pdf_builder import build_invoice_pdf
from josfe.sri_invoicing.xml import paths as xml_paths


# -------------------------------
# Public API
# -------------------------------

def send_invoice_email(qdoc, pdf_url: Optional[str] = None) -> None:
    """
    Send AUTORIZADO XML + PDF to the customer's primary email.

    - qdoc: SRI XML Queue document (DocType instance)
      Expected fields:
        - sales_invoice OR (reference_doctype == 'Sales Invoice' and reference_name)
        - xml_file: '/private/files/SRI/.../xxx.xml' (URL)
        - posting_date: used indirectly by pdf_builder (invoice.posting_date)
    - pdf_url: if provided, used directly; if None, PDF is (re)built.

    Raises frappe.ValidationError if recipient cannot be determined.
    Logs any non-critical issues and proceeds safely where possible.
    """

    inv = _get_linked_sales_invoice(qdoc)
    if not inv:
        frappe.throw("No Sales Invoice linked to this SRI XML Queue row.")

    # Resolve recipient
    recipient = _resolve_customer_primary_email(inv.customer)
    if not recipient:
        # fallback to invoice fields
        recipient = inv.get("contact_email") or inv.get("contact_email_id") or inv.get("customer_email")
    if not recipient:
        frappe.throw(f"No email found for customer {inv.customer}")

    # Ensure PDF exists / get URL
    if not pdf_url:
        try:
            pdf_url = build_invoice_pdf(qdoc)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "PDF build failed")
            pdf_url = None

    # Collect attachments (dicts for sendmail)
    urls = _collect_existing_urls([qdoc.get("xml_file"), pdf_url])
    attachments = [{"file_url": u} for u in urls]

    # Compose subject/body
    subject = _format_subject(inv)
    message = _default_body(inv)

    # Send
    frappe.sendmail(
        recipients=[recipient],
        subject=subject,
        message=message,
        attachments=attachments,
    )


# -------------------------------
# Helpers
# -------------------------------

def _get_linked_sales_invoice(qdoc):
    """Return the linked Sales Invoice doc, supporting multiple linking patterns."""
    # Preferred explicit link
    si_name = qdoc.get("sales_invoice")
    if si_name:
        return frappe.get_doc("Sales Invoice", si_name)

    # Common generic link pattern
    ref_dt = qdoc.get("reference_doctype")
    ref_nm = qdoc.get("reference_name")
    if ref_dt == "Sales Invoice" and ref_nm:
        return frappe.get_doc("Sales Invoice", ref_nm)

    # Last resort: try a field named 'invoice' or similar
    for key in ("invoice", "sales_invoice_name", "si_name"):
        val = qdoc.get(key)
        if val:
            try:
                return frappe.get_doc("Sales Invoice", val)
            except Exception:
                pass

    return None


def _resolve_customer_primary_email(customer_name: str) -> Optional[str]:
    """
    Find the primary email of the Customer's main Contact.

    Priority:
      1) Contact linked to Customer (Dynamic Link), primary Contact if available
      2) Contact's primary email in `tabContact Email` (is_primary DESC)
      3) Contact.email_id (legacy top-level field)
    Returns the email string or None.
    """
    # 1) find a Contact linked to the Customer (prefer primary contact)
    contact_name = _find_primary_contact_name(customer_name)
    if not contact_name:
        return None

    # 2) contact's primary email from child table
    email = frappe.db.get_value(
        "Contact Email",
        {"parent": contact_name, "is_primary": 1},
        "email_id",
    )
    if email:
        return email

    # 3) fallback to legacy top-level email field on Contact
    email = frappe.db.get_value("Contact", contact_name, "email_id")
    return email


def _find_primary_contact_name(customer_name: str) -> Optional[str]:
    """
    Locate a Contact linked to the given Customer via Dynamic Link.
    Prefer `is_primary_contact = 1` when available, then newest modified.
    """
    # Try to get a primary contact first
    rows = frappe.db.sql(
        """
        SELECT c.name
        FROM `tabContact` c
        INNER JOIN `tabDynamic Link` dl ON dl.parent = c.name
        WHERE dl.link_doctype = 'Customer'
          AND dl.link_name = %s
        ORDER BY c.is_primary_contact DESC, c.modified DESC
        LIMIT 1
        """,
        (customer_name,),
        as_dict=True,
    )
    return rows[0].name if rows else None


def _collect_existing_urls(urls: List[Optional[str]]) -> List[str]:
    """
    From a list of (possibly None) URLs, keep only those that map to an existing file.
    Accepts only '/private/files/...' URLs and verifies their presence on disk.
    """
    out: List[str] = []
    for u in urls:
        if not u:
            continue
        abs_path = _url_to_abs_private_path(u)
        if abs_path and os.path.exists(abs_path):
            out.append(u)
        else:
            frappe.log_error(f"Attachment not found on disk: {u}", "Missing Attachment")
    return out


def _url_to_abs_private_path(url: str) -> Optional[str]:
    """
    Convert '/private/files/....' URL into an absolute filesystem path.
    Returns None if the URL is not under /private/files/.
    """
    prefix = "/private/files/"
    if not url or not url.startswith(prefix):
        return None
    # Absolute: sites/<site>/private/files/...
    return frappe.get_site_path("private", "files", url[len(prefix):])


def _format_subject(inv) -> str:
    """Subject like: 'Factura Electrónica 002-002-000000123' (falls back to inv.name)."""
    # If you store the human-readable number in naming series fields, adjust here.
    return f"Factura Electrónica {inv.get('name')}"


def _default_body(inv) -> str:
    """Plain body; customize or template as desired."""
    return frappe._(
        f"Adjunto encontrará su factura electrónica {inv.get('name')} (XML y PDF).\n\n"
        f"Gracias por su preferencia."
    )
