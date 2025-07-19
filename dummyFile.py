/**
 * Company Form - Naming Series + Warehouse Address Script
 * -------------------------------------------------------
 * This script enhances the custom child table `Jos_Establecimientos`
 * (fieldname: `custom_jos_tabla_estab`) inside the `Company` doctype.
 * 
 * Features:
 * 1. Dynamically loads naming series options (from the backend)
 * 2. Automatically assigns the first address linked to the selected warehouse
 * 
 * Dependencies:
 * - Server methods defined in `josfe.api.naming_series`:
 *    - get_naming_series_options_for(doctype)
 *    - get_address_for_warehouse(warehouse)
 */

// Trigger when the Company form loads
frappe.ui.form.on('Company', {
  onload: function(frm) {
    // When the user clicks on the child table,
    // refresh naming series options for all rows
    frm.fields_dict.custom_jos_tabla_estab.grid.wrapper.on('click', function () {
    console.log("Clicked on child table wrapper");  // ✅ add this
      set_series_on_all_rows(frm);
    });
  }
});

// Trigger logic when warehouse is selected in a child row
frappe.ui.form.on('Jos_Establecimientos', {
  jos_warehouse: function(frm, cdt, cdn) {
    // Set naming series options dynamically
    set_series_options(frm, cdt, cdn);

    // Automatically assign address linked to the selected warehouse
    set_address_for_warehouse(frm, cdt, cdn);
  }
});

/**
 * Loop through all rows in the child table and apply naming series options.
 */
function set_series_on_all_rows(frm) {
  let rows = frm.doc.custom_jos_tabla_estab || [];
  for (let i = 0; i < rows.length; i++) {
    set_series_options(frm, "Jos_Establecimientos", rows[i].name);
  }
}

/**
 * Call backend to fetch naming series options for "Sales Invoice"
 * and apply them to the jos_naming_series select field.
 */
function set_series_options(frm, cdt, cdn) {
  frappe.call({
    method: "josfe.api.naming_series.get_naming_series_options_for",
    args: { doctype: "Sales Invoice" },
    callback: function(res) {
      if (!res.message) return;

      const options = res.message.map(r => r.name).join("\n");

      const grid = frm.fields_dict.custom_jos_tabla_estab.grid;
      const row = frappe.get_doc(cdt, cdn);
      const grid_row = grid.grid_rows_by_docname[row.name];

      // Delay execution to ensure row is fully rendered
      setTimeout(() => {
        if (grid_row && grid_row.fields_dict && grid_row.fields_dict.jos_naming_series) {
          const field = grid_row.fields_dict.jos_naming_series;
          field.df.options = options;
          field.refresh();
          console.log("Dropdown options updated for row:", row.name);
        } else {
          console.warn("Field jos_naming_series not found in rendered grid row:", row.name);
        }
      }, 100); // wait 100ms to let UI render
    }
  });
}
/**
 * Call backend to fetch the first Address linked to the selected Warehouse.
 * If found, populate the jos_address field.
 */
function set_address_for_warehouse(frm, cdt, cdn) {
  const row = locals[cdt][cdn];
  if (!row.jos_warehouse) return;

  // Reset current address field
  frappe.model.set_value(cdt, cdn, "jos_address", null);

  frappe.call({
    method: "josfe.api.naming_series.get_address_for_warehouse",
    args: {
      warehouse: row.jos_warehouse
    },
    callback: function(res) {
      if (res.message) {
        frappe.model.set_value(cdt, cdn, "jos_address", res.message);
      } else {
        frappe.msgprint(`No address found for warehouse ${row.jos_warehouse}`);
      }
    }
  });
}
