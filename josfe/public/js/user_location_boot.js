frappe.after_ajax(() => {
  const selected = frappe.boot.user.defaults.jos_selected_establishment;

  // If already set, do nothing
  if (selected) return;

  // Call server to fetch eligible establishments
  frappe.call("josfe.user_location.session.get_establishments").then(({ message: warehouses }) => {
    if (!warehouses || !warehouses.length) {
      frappe.msgprint("No active establishments found. Please contact the administrator.");
      return;
    }

    const dialog = new frappe.ui.Dialog({
      title: "Select Your Location",
      fields: [
        {
          label: "Establishment",
          fieldname: "warehouse",
          fieldtype: "Link",
          options: "Warehouse",
          reqd: 1,
          get_query: () => ({
            filters: { name: ["in", warehouses.map(w => w.name)] }
          })
        }
      ],
      primary_action_label: "Confirm",
      primary_action(values) {
        frappe.call("josfe.user_location.session.set_selected_establishment", {
          warehouse: values.warehouse
        }).then(() => {
          frappe.msgprint("Location saved. Reloading...");
          dialog.hide();
          window.location.reload();
        });
      }
    });

    dialog.show();
  });
});
