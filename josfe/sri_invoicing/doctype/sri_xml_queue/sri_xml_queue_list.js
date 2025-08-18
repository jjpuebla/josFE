frappe.listview_settings["SRI XML Queue"] = {
  onload(listview) {
    // Only for FE Admin
    if (!frappe.user_roles.includes("FE Admin")) return;

    // Action 1: En Cola → Firmando (already added earlier)
    listview.page.add_action_item(__("→ Firmando"), () => {
      const selected = listview.get_checked_items();
      if (!selected.length) return frappe.msgprint(__("Select at least one row."));
      const names = selected.map(d => d.name);

      frappe.confirm(
        __(`Move ${names.length} item(s) to "Firmando"?`),
        async () => {
          frappe.show_progress(__("Updating"), 0, names.length);
          let done = 0, failures = [];
          for (const n of names) {
            try {
              await frappe.call({
                method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.transition",
                args: { name: n, to_state: "Firmando" },
              });
              frappe.show_progress(__("Updating"), ++done, names.length);
            } catch (e) { failures.push(`${n}: ${e.message || e}`); }
          }
          frappe.hide_progress();
          if (failures.length) {
            frappe.msgprint(__("Some items failed:") + "<br>" + failures.join("<br>"));
          } else {
            frappe.show_alert({ message: __("Updated successfully"), indicator: "green" });
          }
          listview.refresh();
        }
      );
    });

    // Action 2: Firmando → Listo para Transmitir
    listview.page.add_action_item(__("→ Listo para Transmitir"), () => {
      const selected = listview.get_checked_items();
      if (!selected.length) return frappe.msgprint(__("Select at least one row."));
      const names = selected.map(d => d.name);

      frappe.confirm(
        __(`Move ${names.length} item(s) to "Listo para Transmitir"?`),
        async () => {
          frappe.show_progress(__("Updating"), 0, names.length);
          let done = 0, failures = [];
          for (const n of names) {
            try {
              await frappe.call({
                method: "josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue.transition",
                args: { name: n, to_state: "Listo para Transmitir" },
              });
              frappe.show_progress(__("Updating"), ++done, names.length);
            } catch (e) { failures.push(`${n}: ${e.message || e}`); }
          }
          frappe.hide_progress();
          if (failures.length) {
            frappe.msgprint(__("Some items failed:") + "<br>" + failures.join("<br>"));
          } else {
            frappe.show_alert({ message: __("Updated successfully"), indicator: "green" });
          }
          listview.refresh();
        }
      );
    });
  },
};
