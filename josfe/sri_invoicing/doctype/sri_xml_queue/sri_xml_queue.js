// apps/josfe/josfe/sri_invoicing/doctype/sri_xml_queue/sri_xml_queue.js

frappe.ui.form.on("SRI XML Queue", {
  async refresh(frm) {
    frappe.after_ajax(async () => {
      // --- Existing XML file preview/download code (unchanged) ---
      frm.fields_dict.xml_file.$wrapper.empty();

      if (frm.doc.xml_file) {
        const fname = frm.doc.xml_file.split("/").pop() || (frm.doc.name + ".xml");

        frm.fields_dict.xml_file.$wrapper.html(`
          <div style="padding-top:10px"  >
              <b> Archivo XML:</b><br>
          <a href="#" class="xml-preview-link" data-name="${frm.doc.name}">
            📄 ${fname}
          </a><br>
          &nbsp;&nbsp;
          <button class="btn btn-primary btn-sm xml-download-btn" data-name="${frm.doc.name}" style="margin-bottom:20px;">
            ⬇ Descargar XML
          </button>
          <span class="pdf-slot"></span>
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

        // --- PDF Download (server-driven; blob method) ---
        try {
          const pdfResp = await frappe.call({
            method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.get_pdf_url",
            args: { name: frm.doc.name },
          });
          const pdfUrl = pdfResp && pdfResp.message;

          if (pdfUrl && frm.fields_dict.pdf_emailed) {
            const pdfName = (frm.doc.name || "document") + ".pdf";

            // Append PDF name + button BELOW pdf_emailed field, keep checkbox visible
            frm.fields_dict.pdf_emailed.$wrapper.append(`
              <div class="pdf-download-block" style="margin-top:10px;">
                <b>Archivo PDF:</b><br>
                📄 ${pdfName}<br>&nbsp;&nbsp;
                <button class="btn btn-success btn-sm pdf-download-btn" data-name="${frm.doc.name}">
                  ⬇ Descargar PDF
                </button>
              </div>
            `);

            // Bind click handler on the correct wrapper
            frm.fields_dict.pdf_emailed.$wrapper.off("click", ".pdf-download-btn");
            frm.fields_dict.pdf_emailed.$wrapper.on("click", ".pdf-download-btn", async function (e) {
              e.preventDefault();
              const fname = (frm.doc.name || "document") + ".pdf";

              try {
                let resp = await frappe.call({
                  method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.get_pdf_content",
                  args: { name: frm.doc.name },
                });
                if (resp.message) {
                  const binary = atob(resp.message);
                  const len = binary.length;
                  const bytes = new Uint8Array(len);
                  for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);

                  const blob = new Blob([bytes], { type: "application/pdf" });
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = fname;
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                  window.URL.revokeObjectURL(url);
                }
              } catch (err) {
                frappe.msgprint(__("Error downloading PDF"));
                console.error(err);
              }
            });
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

        // Decide button label based on retry count
        let resendLabel = __("Resend Email");
        if ((frm.doc.email_retry_count || 0) === 0) {
          resendLabel = __("Envío manual");
        }

        // Insert resend/manual send button directly under pdf_emailed field
        if (frm.fields_dict.pdf_emailed) {
          const label = (frm.doc.email_retry_count || 0) === 0 ? __("Envío manual") : __("Resend Email");

          frm.fields_dict.pdf_emailed.$wrapper.empty().append(`
            <br>            
            <div style="padding-top:15px">
            <b>Emails:</b><br>
              &nbsp;&nbsp;
            <button class="btn btn-primary btn-sm resend-email-btn" style="margin-top:8px;">
              📧 ${label}
            </button>
            </div>
          `);

          // Remove old handlers first
          frm.fields_dict.pdf_emailed.$wrapper.off("click", ".resend-email-btn");

          // Bind new handler
          frm.fields_dict.pdf_emailed.$wrapper.on("click", ".resend-email-btn", async function (e) {
            e.preventDefault();
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
            }
          });
        }

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
