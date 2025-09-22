frappe.ui.form.on("Sales Invoice", {
  onload(frm) {
    forceHideNamingSeries(frm);
    ensureSerieField(frm);
  },

  onload_post_render(frm) {
    // after the UI builds, hide again in case core showed it
    forceHideNamingSeries(frm);
    ensureSerieField(frm);
    ensureMountedThen(() => paintSeriePreview(frm), frm, 'input[data-fieldname="naming_series"]');
    warnIfNoCustomerBeforeWarehouseSelection(frm);
  },

  refresh(frm) {
    // Naming Series controls
    forceHideNamingSeries(frm);
    maybe_load_pe_options(frm, false); // if warehouse already selected
    ensureSerieField(frm);
    ensureMountedThen(() => paintSeriePreview(frm), frm, 'input[data-fieldname="naming_series"]');

    // Render Forma de Pago buttons
    renderFormaPagoButtons(frm);
  },

  custom_jos_level3_warehouse(frm) {
    maybe_load_pe_options(frm, true);
    paintSeriePreview(frm);
  },

  custom_jos_sri_emission_point_code(frm) {
    paintSeriePreview(frm);
  }
});

function ensureMountedThen(fn, frm, selector) {
  const root = frm.$wrapper && frm.$wrapper[0];
  if (!root) return fn();  // fallback

  if (root.querySelector(selector)) return fn();  // already mounted

  const mo = new MutationObserver(() => {
    if (root.querySelector(selector)) {
      try { mo.disconnect(); } catch {}
      fn();
    }
  });

  mo.observe(root, { childList: true, subtree: true });
}

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

function maybe_load_pe_options(frm, clear) {
  const wh = frm.doc.custom_jos_level3_warehouse;
  const target = "custom_jos_sri_emission_point_code";

  if (!wh) {
    frm.set_df_property(target, "options", [""]);
    frm.set_value(target, "");
    return;
  }

  frappe.call({
    method: "josfe.sri_invoicing.core.numbering.state.list_active_emission_points",
    args: { warehouse_name: wh }
  }).then(r => {
    const rows = r.message || [];
    const opts = rows.map(x => x.code);
    frm.set_df_property(target, "options", opts.length ? opts : [""]);
    if (clear) frm.set_value(target, "");
  });
}

// --- live preview without allocating a number ---
async function paintSeriePreview(frm) {
  ensureSerieField(frm);

  // ⛔ Don't preview once the document has a real name (i.e., saved)
  if (!frm.is_new()) {
    return;
  }

  const wh = frm.doc.custom_jos_level3_warehouse;
  const peRaw = (frm.doc.custom_jos_sri_emission_point_code || "").trim();
  const peCode = (peRaw.split(" - ", 1)[0] || "").trim();

  if (!wh || !peCode) {
    frm.set_value("custom_sri_serie", "");
    return;
  }

  const myReq = ++__seriePreviewReq;
  try {
    const { message } = await frappe.call({
      method: "josfe.sri_invoicing.core.numbering.state.peek_next",
      args: { warehouse: wh, pe_code: peCode }
    });
    if (myReq !== __seriePreviewReq) return;
    frm.set_value("custom_sri_serie", message || "");
  } catch {
    if (myReq !== __seriePreviewReq) return;
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

// Avoid overlapping previews; only apply the latest response
let __seriePreviewReq = 0;

function warnIfNoCustomerBeforeWarehouseSelection(frm) {
  const fieldname = "custom_jos_level3_warehouse";
  const $input = frm.get_field(fieldname)?.$wrapper?.find("input[data-fieldname]");

  if (!$input || !$input.length) return;

  // Prevent duplicate binding
  if ($input.data("warn-bound")) return;
  $input.data("warn-bound", true);

  $input.on("mousedown", function (e) {
    if (!frm.doc.customer) {
      // Prevent dropdown opening
      e.preventDefault();
      e.stopImmediatePropagation();

      frappe.msgprint({
        title: __("Missing Customer"),
        message: __("Please specify: <b>Customer</b>. It is needed to fetch Warehouse options."),
        indicator: "orange"
      });
    }
  });
}

function renderFormaPagoButtons(frm) {
  const field = frm.fields_dict["custom_jos_forma_pago"];
  if (!field) return;

  // Avoid duplicate rendering
  if (field.$wrapper.find(".jos-pago-buttons").length) return;

  // Ordered mapping
  const opts = [
    ["01", "Efectivo"],
    ["20", "Transferencias, Chqs"],
    ["19", "Tarjeta de Crédito"],
    ["16", "Tarjeta de Débito"]
  ];

  // Build HTML
  let html = `
    <label class="control-label" style="margin-bottom:6px; display:block;">
      ${field.df.label}
    </label>
    <div class="jos-pago-buttons"></div>
  `;

  field.$wrapper.html(html);
  const container = field.$wrapper.find(".jos-pago-buttons");

  // Inject buttons in correct order
  opts.forEach(([code, label]) => {
    const active = frm.doc.custom_jos_forma_pago === code ? "jos-active" : "";
    container.append(`
      <button type="button" class="jos-pago-btn ${active}" data-code="${code}">
        ${label}
      </button>
    `);
  });

  // Style buttons: slimmer, 2 per row
  frappe.dom.set_style(`
    .jos-pago-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .jos-pago-btn {
      background-color: #777;
      color: #fff;
      border: none;
      border-radius: 6px;
      padding: 3px 6px;   /* thinner */
      flex: 1 1 calc(50% - 8px); /* 2 per row */
      text-align: center;
    }
    .jos-pago-btn.jos-active {
      background-color: #000;
      color: #fff;
    }
  `);

  // Handle clicks
  container.on("click", ".jos-pago-btn", function () {
    const code = $(this).data("code");
    frm.set_value("custom_jos_forma_pago", code);

    // Update states
    container.find(".jos-pago-btn").removeClass("jos-active");
    $(this).addClass("jos-active");
  });
}
