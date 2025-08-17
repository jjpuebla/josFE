frappe.ui.form.on('Company', {
  onload_post_render: function(frm) {
    set_series_on_all_rows(frm);
  }
});

frappe.ui.form.on('Jos_Establecimientos', {
  jos_warehouse: function(frm, cdt, cdn) {
    set_series_options(frm, cdt, cdn);
  }
});

function set_series_on_all_rows(frm) {
  const rows = frm.doc.custom_jos_tabla_estab || [];
  for (let i = 0; i < rows.length; i++) {
    set_series_options(frm, "Jos_Establecimientos", rows[i].name);
  }
}

function set_series_options(frm, cdt, cdn) {
  frappe.call({
    method: "josfe.api.naming_series.get_naming_series_options_for",
    args: { doctype: "Sales Invoice" },
    callback: function(res) {
      if (!res.message) return;
      const options = res.message.map(r => r.name).join("\n");

      const grid = frm.fields_dict.custom_jos_tabla_estab.grid;
      const grid_row = grid.grid_rows_by_docname[cdn];

      if (grid_row && grid_row.fields_dict && grid_row.fields_dict.jos_naming_series) {
        const field = grid_row.fields_dict.jos_naming_series;
        field.df.options = options;
        field.refresh();
        console.log("Naming series options set for row:", cdn);
      } else {
        console.warn("Could not find field jos_naming_series in row:", cdn);
      }
    }
  });
}
