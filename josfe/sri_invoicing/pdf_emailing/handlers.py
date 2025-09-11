import frappe
from frappe.utils.background_jobs import enqueue
from josfe.sri_invoicing.pdf_emailing.pdf_builder import build_invoice_pdf
from josfe.sri_invoicing.pdf_emailing.emailer import send_invoice_email

def on_queue_update(doc, event):
    """Triggered when SRI XML Queue is updated"""
    if doc.state == "AUTORIZADO" and not doc.get("pdf_emailed"):
        try:
            from josfe.sri_invoicing.pdf_emailing.pdf_builder import build_invoice_pdf
            build_invoice_pdf(doc)  # generate PDF only
            # don’t call _process_email here in dev
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Initial PDF build failed")

def _process_email(queue_name):
    """Main logic to build PDF and send email"""
    doc = frappe.get_doc("SRI XML Queue", queue_name)
    pdf_file = build_invoice_pdf(doc)
    send_invoice_email(doc, pdf_file)
    doc.db_set("pdf_emailed", 1)
    frappe.msgprint(f"✅ PDF generated and emailed for {doc.name}")

def schedule_retry(doc):
    """Schedule a one-time retry if allowed"""
    retry_count = doc.get("email_retry_count") or 0
    if retry_count < 1:  # allow 1 retry max
        doc.db_set("email_retry_count", retry_count + 1)
        enqueue(
            "josfe.sri_invoicing.pdf_emailing.handlers._process_email",
            queue="short",
            job_name=f"retry_email_{doc.name}",
            timeout=300,
            enqueue_after_commit=True,
            queue_name="default",
            is_async=True,
            now=False,
            at_front=False,
            kwargs={"queue_name": doc.name},
        )
        frappe.msgprint(f"⚠️ Scheduled retry for {doc.name} in background.")

@frappe.whitelist()
def manual_resend(queue_name):
    """Manual resend trigger for Accounts Manager."""
    doc = frappe.get_doc("SRI XML Queue", queue_name)

    try:
        _process_email(queue_name)
        return {"status": "ok"}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Manual Resend Failed")
        frappe.throw("Manual resend failed. Check error log.")
