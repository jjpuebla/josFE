// sri_endpoint_list.js
frappe.listview_settings['SRI Endpoint'] = {
  get_indicator(doc) {
    console.log("🧪 get_indicator triggered for:", doc.name);
    console.log("🟡 active =", doc.active);

    if (doc.active === 1) {
      console.log("🟢 Returning: Activo - Green");
      return ["Activo", "green", "active"];
    } else if (doc.active === 0) {
      console.log("🔴 Returning: Inactivo - Red");
      return ["Inactivo", "red", "active"];
    }
    console.log("⚪️ No match, no indicator");
    return null;
  }
};
