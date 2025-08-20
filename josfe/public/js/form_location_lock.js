frappe.after_ajax(() => {
  const selected = frappe.boot.user.defaults.jos_selected_establishment;
  if (!selected || !cur_frm) return;

  const warehouse_fields = [
    "warehouse",
    "custom_jos_level3_warehouse",
    "custom_jos_establecimiento"
    // Add others as needed per your doctypes
  ];

  cur_frm.fields.forEach(field => {
    if (warehouse_fields.includes(field.df.fieldname)) {
      // Set default if not already
      if (!cur_frm.doc[field.df.fieldname]) {
        cur_frm.set_value(field.df.fieldname, selected);
      }

      // Disable field
      cur_frm.toggle_enable(field.df.fieldname, false);

      // Restrict query to children of selected warehouse
      cur_frm.set_query(field.df.fieldname, () => ({
        filters: {
          parent_warehouse: selected
        }
      }));
    }
  });
});
