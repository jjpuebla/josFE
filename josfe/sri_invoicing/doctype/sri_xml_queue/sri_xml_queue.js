// apps/josfe/josfe/sri_invoicing/doctype/sri_xml_queue/sri_xml_queue.js

frappe.ui.form.on("SRI XML Queue", {
  async refresh(frm) {
    frappe.after_ajax(async () => {
      frm.fields_dict.xml_file.$wrapper.empty();

      if (frm.doc.xml_file) {
        const fname = frm.doc.xml_file.split("/").pop() || (frm.doc.name + ".xml");

        frm.fields_dict.xml_file.$wrapper.html(`
          <a href="#" class="xml-preview-link" data-name="${frm.doc.name}">
            📄 ${fname}
          </a>
          &nbsp;&nbsp;
          <button class="btn btn-dark btn-sm xml-download-btn" data-name="${frm.doc.name}">
            ⬇ Download
          </button>
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
    });
  },
});
