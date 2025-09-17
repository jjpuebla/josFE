frappe.listview_settings['UI Settings'] = {
  add_fields: ["role", "doctype_name"],

  get_indicator: function (doc) {
    if (doc.inactive || doc.status === "Inactive") {
      return [__("Inactive"), "red", "inactive,=,1"];
    } else {
      return [__("Active"), "green", "inactive,=,0"];
    }
  }
};
