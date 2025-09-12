// apps/josfe/josfe/sri_invoicing/doctype/sri_xml_queue/sri_xml_queue.js

frappe.ui.form.on("SRI XML Queue", {
  async refresh(frm) {
    frappe.after_ajax(async () => {
      // --- Existing XML file preview/download code (unchanged) ---
      frm.fields_dict.xml_file.$wrapper.empty();

      if (frm.doc.xml_file) {
        const fname = frm.doc.xml_file.split("/").pop() || (frm.doc.name + ".xml");

        frm.fields_dict.xml_file.$wrapper.html(`
          <div style="padding-top:10px">
              <b>Archivo XML:</b><br>
          <a href="#" class="xml-preview-link" data-name="${frm.doc.name}">
            📄 ${fname}
          </a><br>
          &nbsp;&nbsp;
          <button class="btn btn-primary btn-sm xml-download-btn" data-name="${frm.doc.name}" style="margin-bottom:20px;">
            ⬇ Descargar XML
          </button>
          </div>
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


        // Insert resend/manual send button directly under pdf_emailed field
                // === PDF Download Button (always available in Autorizado) ===
        if (frm.fields_dict.pdf_emailed) {
          const $wrap = frm.fields_dict.pdf_emailed.$wrapper;
          let $pdfSlot = $wrap.find(".pdf-download-slot");
          if (!$pdfSlot.length) {
            $wrap.append('<div class="pdf-download-slot" style="margin-top:10px;"></div>');
            $pdfSlot = $wrap.find(".pdf-download-slot");
          }
          $pdfSlot.empty().append(`
            <div class="pdf-download-block">
              <b>Archivo PDF:</b><br>
              &nbsp;&nbsp;
              <button class="btn btn-success btn-sm pdf-download-btn" data-name="${frm.doc.name}">
                ⬇ Descargar PDF
              </button>
            </div>
          `);

          // Remove old handlers before binding new one
          frm.fields_dict.pdf_emailed.$wrapper.off("click", ".pdf-download-btn");

          frm.fields_dict.pdf_emailed.$wrapper.on("click", ".pdf-download-btn", async function (e) {
            e.preventDefault();
            try {
              const resp = await frappe.call({
                method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.download_pdf",
                args: { name: frm.doc.name },
              });
              if (resp.message && resp.message.data) {
                const binary = atob(resp.message.data);
                const len = binary.length;
                const bytes = new Uint8Array(len);
                for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);

                const blob = new Blob([bytes], { type: "application/pdf" });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = resp.message.filename || (frm.doc.sales_invoice || frm.doc.name) + ".pdf";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
              } else {
                frappe.msgprint(__("No PDF available for record " + frm.doc.name));
              }
            } catch (err) {
              frappe.msgprint(__("Error downloading PDF"));
              console.error(err);
            }
          });
        }

        // === Email Button ===

        if (frm.fields_dict.pdf_emailed) {
          const label = (frm.doc.email_retry_count || 0) === 0 ? __("Envío manual") : __("Resend Email");
          const $wrap = frm.fields_dict.pdf_emailed.$wrapper;
          // dedicated slot for email actions to avoid duplicates
          let $emailSlot = $wrap.find(".email-actions-slot");
          if (!$emailSlot.length) {
            $wrap.append('<div class="email-actions-slot"></div>');
            $emailSlot = $wrap.find(".email-actions-slot");
          }
          $emailSlot.empty().append(`
            <div style="padding-top:15px">
              <b>Emails:</b><br>
              &nbsp;&nbsp;
              <button class="btn btn-primary btn-sm resend-email-btn" style="margin-top:8px;">
                📧 ${label}
              </button>
            </div>
          `);

          frm.fields_dict.pdf_emailed.$wrapper.off("click.resend", ".resend-email-btn");
          frm.fields_dict.pdf_emailed.$wrapper.on("click.resend", ".resend-email-btn", async function (e) {
            e.preventDefault();
            const $btn = $(this);

            // Disable button + show feedback
            $btn.prop("disabled", true).text("⏳ Enviando...");

            try {
              let resp = await frappe.call({
                method: "josfe.sri_invoicing.pdf_emailing.handlers.manual_resend",
                args: { queue_name: frm.doc.name },
              });
              if (!resp.exc) {
                frappe.msgprint("📧 Email triggered.");
                frm.reload_doc();
              }
            } catch (err) {
              frappe.msgprint(__("Resend handler not available."));
              console.error(err);
            } finally {
              // Re-enable button
              $btn.prop("disabled", false).text("📧 ${label}");
            }
          });
        }

      } else {
        // Hide when not Autorizado
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
