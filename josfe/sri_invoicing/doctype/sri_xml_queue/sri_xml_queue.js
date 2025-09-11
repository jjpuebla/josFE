// apps/josfe/josfe/sri_invoicing/doctype/sri_xml_queue/sri_xml_queue.js

frappe.ui.form.on("SRI XML Queue", {
  async refresh(frm) {
    frappe.after_ajax(async () => {
      // --- Existing XML file preview/download code (unchanged) ---
      frm.fields_dict.xml_file.$wrapper.empty();

      if (frm.doc.xml_file) {
        const fname = frm.doc.xml_file.split("/").pop() || (frm.doc.name + ".xml");

        frm.fields_dict.xml_file.$wrapper.html(`
          <a href="#" class="xml-preview-link" data-name="${frm.doc.name}">
            📄 ${fname}
          </a>
          &nbsp;&nbsp;
          <button class="btn btn-dark btn-sm xml-download-btn" data-name="${frm.doc.name}" style="margin-bottom:20px;">
            ⬇ Download
          </button>
          <span class="pdf-slot"></span>
        `);

        // Remove old handlers before binding new ones
        frm.fields_dict.xml_file.$wrapper.off("click", ".xml-preview-link");
        frm.fields_dict.xml_file.$wrapper.off("click", ".xml-download-btn");

        // Preview click
        frm.fields_dict.xml_file.$wrapper.on("click", ".xml-preview-link", async function (e) {
          e.preventDefault();
          let resp = await frappe.call({
            method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.get_xml_preview",
            args: { name: frm.doc.name },
          });
          if (resp.message) {
            new frappe.ui.Dialog({
              title: __("XML Preview - " + fname),
              size: "large",
              fields: [
                {
                  fieldtype: "HTML",
                  fieldname: "xml_preview",
                  options: `<pre style="white-space: pre-wrap; max-height: 70vh; overflow:auto;">${frappe.utils.escape_html(resp.message)}</pre>`,
                },
              ],
            }).show();
          }
        });

        // Download click
        frm.fields_dict.xml_file.$wrapper.on("click", ".xml-download-btn", async function (e) {
          e.preventDefault();
          let resp = await frappe.call({
            method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.get_xml_preview",
            args: { name: frm.doc.name },
          });
          if (resp.message) {
            const blob = new Blob([resp.message], { type: "application/xml;charset=utf-8" });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = fname.endsWith(".xml") ? fname : fname + ".xml";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
          }
        });

        // --- PDF Preview/Download (server-driven; no path guessing in JS) ---
        try {
          const pdfResp = await frappe.call({
            method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.get_pdf_url",
            args: { name: frm.doc.name },
          });
          const pdfUrl = pdfResp && pdfResp.message;
          if (pdfUrl) {
            const pdfName = (frm.doc.name || "document") + ".pdf";
            frm.fields_dict.xml_file.$wrapper.find(".pdf-slot").html(`
              <br>
              <a href="${pdfUrl}" target="_blank" class="pdf-preview-link">
                📄 ${pdfName}
              </a>
              &nbsp;&nbsp;
              <a class="btn btn-dark btn-sm" href="${pdfUrl}" download>
                ⬇ Download PDF
              </a>
            `);
          }
        } catch (e) {
          console.warn("PDF URL check failed:", e);
        }
      }

      // --- State = Autorizado: show extra fields + always show 'Resend Email' button ---
      const isAutorizado = ((frm.doc.state || "") + "").toLowerCase() === "autorizado";

      if (isAutorizado) {
        // Unhide pdf_emailed + email_retry_count fields (mark them Read Only in Customize Form)
        if (frm.fields_dict.pdf_emailed) {
          frm.set_df_property("pdf_emailed", "hidden", 0);
        }
        if (frm.fields_dict.email_retry_count) {
          frm.set_df_property("email_retry_count", "hidden", 0);
        }

        // Always offer manual resend while Autorizado
        frm.add_custom_button(
          __("Resend Email"),
          function () {
            frappe.call({
              method: "josfe.sri_invoicing.pdf_emailing.handlers.manual_resend",
              args: { queue_name: frm.doc.name },
              callback: function (r) {
                if (!r.exc) {
                  frappe.msgprint("📧 Email resend triggered.");
                  frm.reload_doc(); // refresh form after resend
                }
              },
            }).catch((e) => {
              frappe.msgprint(__("Resend handler is not available."));
              console.warn(e);
            });
          },
          __("Actions")
        );
      } else {
        // Hide fields when not Autorizado
        if (frm.fields_dict.pdf_emailed) {
          frm.set_df_property("pdf_emailed", "hidden", 1);
        }
        if (frm.fields_dict.email_retry_count) {
          frm.set_df_property("email_retry_count", "hidden", 1);
        }
      }
    });
  },
});
