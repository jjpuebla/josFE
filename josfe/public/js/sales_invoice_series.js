frappe.ui.form.on("Sales Invoice", {
  onload(frm) {
    applyWarehouseQuery(frm);
    forceHideNamingSeries(frm);
    ensureSerieField(frm);
  },

  onload_post_render(frm) {
    // after the UI builds, hide again in case core showed it
    forceHideNamingSeries(frm);
    ensureSerieField(frm);
    paintSeriePreview(frm);
  },

  refresh(frm) {
    forceHideNamingSeries(frm);
    applyWarehouseQuery(frm);          // re-assert query on refresh
    maybe_load_pe_options(frm, false); // if warehouse already selected
    ensureSerieField(frm);
    paintSeriePreview(frm);
  },

  custom_jos_level3_warehouse(frm) {
    maybe_load_pe_options(frm, true);
    paintSeriePreview(frm);
  },
  custom_jos_sri_emission_point_code(frm) {
    paintSeriePreview(frm);
  }
});

function forceHideNamingSeries(frm) {
  const f = frm.get_field("naming_series");
  if (!f) return;

  // 1) Meta-level: make it hidden & not required
  f.df.hidden = 1;
  f.df.reqd = 0;
  f.refresh();

  // 2) API-level (some scripts rely on set_df_property)
  frm.set_df_property("naming_series", "hidden", 1);
  frm.set_df_property("naming_series", "reqd", 0);
  frm.toggle_display("naming_series", false);

  // 3) DOM-level (belt and suspenders)
  if (f.wrapper) $(f.wrapper).hide();

  // 4) One-time CSS rule to keep it hidden regardless of later toggles
  if (!window.__jos_hide_series_css__) {
    frappe.dom.set_style(
      `[data-fieldname="naming_series"]{display:none!important;}`
    );
    window.__jos_hide_series_css__ = true;
  }

  // Optional: on brand-new docs, clear any default value
  if (frm.is_new() && frm.doc.naming_series) {
    frm.set_value("naming_series", "");
  }
}

function applyWarehouseQuery(frm) {
  const fld = frm.fields_dict.custom_jos_level3_warehouse;
  if (!fld) return;

  const q = () => ({
    query: "josfe.sri_invoicing.numbering.state.level3_warehouse_link_query",
    filters: { company: frm.doc.company || null }
  });

  // Pin the query in all three places (defensive against late overrides)
  fld.get_query = q;                                 // runtime resolver
  fld.df.get_query = q;                              // definition-level
  frm.set_query("custom_jos_level3_warehouse", q);   // API path

  // Existing-only: hide “create new” (+)
  frm.set_df_property("custom_jos_level3_warehouse", "only_select", 1);
}

function maybe_load_pe_options(frm, clear) {
  const wh = frm.doc.custom_jos_level3_warehouse;
  const target = "custom_jos_sri_emission_point_code";

  if (!wh) {
    frm.set_df_property(target, "options", [""]);
    frm.set_value(target, "");
    return;
  }

  frappe.call({
    method: "josfe.sri_invoicing.numbering.state.list_active_emission_points",
    args: { warehouse_name: wh }
  }).then(r => {
    const rows = r.message || [];
    const opts = rows.map(x => x.code);
    frm.set_df_property(target, "options", opts.length ? opts : [""]);
    if (clear) frm.set_value(target, "");
  });
}
// --- ensure the field is always visible & read-only ---
function ensureSerieField(frm) {
  const fn = "custom_sri_serie";
  const f = frm.get_field(fn);
  if (!f) return;

  // Force properties at both df + API levels
  f.df.hidden = 0;
  f.df.read_only = 1;
  f.df.reqd = 0;
  frm.set_df_property(fn, "hidden", 0);
  frm.set_df_property(fn, "read_only", 1);
  frm.set_df_property(fn, "reqd", 0);
  frm.toggle_display(fn, true);
  f.refresh();
}

// zero-pad helper
function z3(v) { v = String(v || "").trim(); return v ? v.padStart(3, "0") : ""; }

// --- live preview without allocating a number ---
async function paintSeriePreview(frm) {
  ensureSerieField(frm);

  const wh = frm.doc.custom_jos_level3_warehouse;
  const peRaw = (frm.doc.custom_jos_sri_emission_point_code || "").trim();
  const peCode = (peRaw.split(" - ", 1)[0] || "").trim();

  if (!wh || !peCode) {
    frm.set_value("custom_sri_serie", "");
    return;
  }

  try {
    const { message } = await frappe.call({
      method: "josfe.api.naming_series.peek_next_si_series",
      args: { warehouse: wh, pe_code: peCode }
    });
    frm.set_value("custom_sri_serie", message || "");
  } catch (e) {
    frm.set_value("custom_sri_serie", "");
  }
}

function tagSerieForStyling(frm) {
  const w = frm.get_field("custom_sri_serie")?.$wrapper;
  if (w && !w.hasClass("josfe-sri-serie")) w.addClass("josfe-sri-serie");
}

function ensureSerieField(frm) {
  const fn = "custom_sri_serie";
  const f = frm.get_field(fn);
  if (!f) return;

  f.df.hidden = 0;
  f.df.read_only = 1;
  f.df.reqd = 0;

  frm.set_df_property(fn, "hidden", 0);
  frm.set_df_property(fn, "read_only", 1);
  frm.set_df_property(fn, "reqd", 0);
  frm.toggle_display(fn, true);

  f.refresh();
  tagSerieForStyling(frm);  // <-- add this
}
