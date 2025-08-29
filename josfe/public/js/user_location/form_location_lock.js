// apps/josfe/josfe/public/js/user_location/form_location_lock.js
(() => {
  const CHANNEL = "josfe_establishment";
  const SIGNAL_KEY = "josfe_establishment_signal";

  // --- Server fetch for current warehouse selection ---
  async function fetchSelectedWH() {
    try {
      const r = await frappe.call("josfe.user_location.session.get_establishment_options");
      const srvVal = (r.message?.selected || "").trim();
      if (srvVal) frappe.boot.jos_selected_establishment = srvVal;
      return srvVal;
    } catch (e) {
      return (frappe.boot?.jos_selected_establishment || "").trim();
    }
  }

  // --- Fetch active PE code for a given Warehouse ---
  async function fetchActivePE(warehouse) {
    if (!warehouse) {
      console.warn("[josfe:lock] fetchActivePE called without warehouse");
      return null;
    }
    try {
      const r = await frappe.call({
        method: "frappe.client.get",
        args: { doctype: "Warehouse", name: warehouse }
      });
      const doc = r.message;

      if (!doc || !doc.custom_sri_puntos_emision) return null;

      // Find the row with estado = "Activo"
      const active = (doc.custom_sri_puntos_emision || []).find(
        (row) => row.estado === "Activo"
      );

      return active ? active.emission_point_code : null;  // ✅ fixed
    } catch (e) {
      console.error("[josfe:lock] fetchActivePE error", e);
      return null;
    }
  }

  function lockFields(frm) {
    // 1) Always keep the real Link (custom_jos_level3_warehouse) hidden, but set + save its value
    if (frm.fields_dict.custom_jos_level3_warehouse) {
      frm.set_df_property("custom_jos_level3_warehouse", "hidden", 1);
      // keep it read-only too (safety)
      frm.set_df_property("custom_jos_level3_warehouse", "read_only", 1);
    }

    // 2) Mirror the value into the display-only Data field (no hyperlink)
    if (frm.fields_dict.custom_jos_level3_warehouse_display) {
      const wh_val = frm.doc.custom_jos_level3_warehouse || "";
      if (frm.doc.custom_jos_level3_warehouse_display !== wh_val) {
        frm.set_value("custom_jos_level3_warehouse_display", wh_val);
      }
      frm.set_df_property("custom_jos_level3_warehouse_display", "read_only", 1);
      frm.refresh_field("custom_jos_level3_warehouse_display");
    }

    // 3) Keep PE read-only (it’s already working)
    if (frm.fields_dict.custom_jos_sri_emission_point_code) {
      frm.set_df_property("custom_jos_sri_emission_point_code", "read_only", 1);
    }
  }
  async function applyToForm(frm, wh) {

    if (!wh) {
      frappe.show_alert({ message: "Debes seleccionar un Establecimiento", indicator: "red" });
      frappe.set_route("location-picker");
      return;
    }

  // Set the REAL Link field (DB value)
  if (frm.doc.custom_jos_level3_warehouse !== wh) {
    frm.set_value("custom_jos_level3_warehouse", wh);
  }

  // Always refresh PE from active row for this WH (and block if none)
  if (frm.doctype === "Sales Invoice") {
    const pe = await fetchActivePE(wh);
    if (!pe) {
      frappe.throw(
        __("No hay Puntos de Emisión Activos en la Sucursal {0}", [wh])
      );
    }
    if (frm.doc.custom_jos_sri_emission_point_code !== pe) {
      frm.set_value("custom_jos_sri_emission_point_code", pe);
    }
  }

  // Mirror to display-only Data field (no hyperlink)
  if (frm.fields_dict.custom_jos_level3_warehouse_display) {
    if (frm.doc.custom_jos_level3_warehouse_display !== wh) {
      frm.set_value("custom_jos_level3_warehouse_display", wh);
    }
    frm.set_df_property("custom_jos_level3_warehouse_display", "read_only", 1);
    frm.refresh_field("custom_jos_level3_warehouse_display");
  }

  // Lock/hide the real Link and keep PE read-only
  lockFields(frm);

    // Default for "set_warehouse" field (if exists)
    const fld = frm.fields_dict?.set_warehouse;
    if (fld && fld.df) {
      fld.df.default = wh;
      try { frm.refresh_field("set_warehouse"); } catch (e) {}
    }

    // Lock item warehouses to current WH
    if (frm.fields_dict.items) {
      const grid = frm.fields_dict.items.grid;
      const whField = grid.get_field("warehouse");
      if (whField) {
        whField.get_query = () => ({ filters: { name: wh } });
      }
    }

  }


  async function enforce(frm) {
    const wh = await fetchSelectedWH();
    await applyToForm(frm, wh);
  }

  // --- Hooks per Doctype ---
  frappe.ui.form.on("Sales Invoice", {
    async onload_post_render(frm) { await enforce(frm); },
    async refresh(frm)           { await enforce(frm); }
  });

  frappe.ui.form.on("Delivery Note", {
    async onload_post_render(frm) { await enforce(frm); },
    async refresh(frm)           { await enforce(frm); }
  });

  // --- Cross-tab sync: update open forms immediately ---
  function onRemoteChanged() {
    const frm = cur_frm;
    if (!frm) return;
    enforce(frm);
  }

  if ("BroadcastChannel" in window) {
    const bc = new BroadcastChannel(CHANNEL);
    bc.onmessage = (ev) => { if (ev?.data?.type === "changed") onRemoteChanged(); };
  }
  window.addEventListener("storage", (ev) => {
    if (ev.key === SIGNAL_KEY) onRemoteChanged();
  });
})();
