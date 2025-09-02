// apps/josfe/josfe/sri_invoicing/doctype/sri_xml_queue/sri_xml_queue.js

frappe.ui.form.on("SRI XML Queue", {
  refresh(frm) {
    // clear wrapper
    frm.fields_dict.xml_file.$wrapper.empty();

    if (frm.doc.xml_file) {
      // Extract just the filename from file_url
      const parts = frm.doc.xml_file.split("/");
      const fname = parts[parts.length - 1];

      frm.fields_dict.xml_file.$wrapper.html(`
        <a href="#" class="xml-preview-link" data-name="${frm.doc.name}">
          📄 ${fname}
        </a>
      `);

      // click handler → preview from disk
      frm.fields_dict.xml_file.$wrapper.on("click", ".xml-preview-link", async function (e) {
        e.preventDefault();
        let r = await frappe.call({
          method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.get_xml_preview",
          args: { name: frm.doc.name },
        });
        if (r.message) {
          let d = new frappe.ui.Dialog({
            title: __("Vista previa XML - " + fname),
            size: "large",
            fields: [
              {
                fieldtype: "HTML",
                fieldname: "xml_preview",
                options: `<pre style="white-space: pre-wrap; max-height: 70vh; overflow:auto;">${
                  frappe.utils.escape_html(r.message)
                }</pre>`,
              },
            ],
          });
          d.show();
        }
      });
    }
  },
});
