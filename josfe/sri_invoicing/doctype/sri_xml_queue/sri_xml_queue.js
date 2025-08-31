frappe.ui.form.on("SRI XML Queue", {
  refresh(frm) {
    // decorate XML file field
    if (frm.doc.xml_file) {
      frm.fields_dict.xml_file.$wrapper.html(`
        <a href="#" class="xml-preview-link" data-name="${frm.doc.name}">
          📄 Vista previa XML
        </a>
      `);
    }
    
    // click handler
    frm.fields_dict.xml_file.$wrapper.on("click", ".xml-preview-link", async function (e) {
      e.preventDefault();
      let r = await frappe.call({
        method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.get_xml_preview",
        args: { name: frm.doc.name },
      });
      if (r.message) {
        let d = new frappe.ui.Dialog({
          title: __("Vista previa XML"),
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
  },
});
