// public/js/tax_id_utils.js
console.log("✅ tax_utils.js started");

(() => {
  // Map each Doctype to its source & target fields
  const CONFIG = {
    Customer: { source: "custom_jos_tax_id_validador", target: "tax_id" },
    Supplier: { source: "custom_jos_ruc_supplier",     target: "tax_id" },
    Company:  { source: "custom_jos_ruc",              target: "tax_id" },
  };

  // Register handlers for each doctype
  Object.entries(CONFIG).forEach(([dt, { source }]) => {
    const eventMap = {
      onload(frm) {
        bindOnce(frm);
        forceShowTax(frm);
        validateAndSync(frm);
      },
      onload_post_render(frm) {
        forceShowTax(frm);
        validateAndSync(frm);
      },
      refresh(frm) {
        forceShowTax(frm);

        // Fresh new doc → clear background & ensure editable
        if (frm.is_new()) {
          const $inp = frm.fields_dict[source]?.$wrapper?.find("input");
          if ($inp) $inp.css("background-color", "");
          frm.set_df_property(source, "read_only", 0);
        }

        validateAndSync(frm);
        maybeLockIfPersisted(frm);
      },
      before_refresh(frm) {
        // Cleanup observer if present
        if (frm.__jos_tax_observer) {
          try { frm.__jos_tax_observer.disconnect(); } catch {}
          frm.__jos_tax_observer = null;
        }
      },
      after_save(frm) {
        const map = CONFIG[frm.doctype];
        if (!map) return;
        const { source, target } = map;

        if (frm.doc[source] && frm.doc[target]) {
          frm.set_df_property(source, "read_only", 1);
          frm.set_df_property(target, "read_only", 1);
          forceShowTax(frm);
          console.log("🔒 Fields locked after save");
        }
      }
    };

    // Dynamic handler for the source field change
    eventMap[source] = function (frm) {
      validateAndSync(frm);
    };

    frappe.ui.form.on(dt, eventMap);
  });

  // One-time per form: input listener + conditional MutationObserver
  function bindOnce(frm) {
    if (frm.__jos_tax_bound) return;
    frm.__jos_tax_bound = true;

    const map = CONFIG[frm.doctype];
    if (!map) return;
    const { source } = map;

    // Repaint on typing
    const $inp = frm.fields_dict[source]?.$wrapper?.find("input");
    if ($inp && $inp.length) {
      $inp.on("input", () => validateAndSync(frm));
    } else {
      // Input not mounted yet → attach conditional observer
      attachObserverIfNeeded(frm);
    }
  }

  // Conditional, auto-disconnecting observer
  function attachObserverIfNeeded(frm) {
    if (frm.__jos_tax_observer) return;

    const map = CONFIG[frm.doctype];
    if (!map) return;
    const { source } = map;

    // Skip if input already exists
    const $now = frm.fields_dict[source]?.$wrapper?.find("input");
    if ($now && $now.length) return;

    const rootEl = frm.$wrapper && frm.$wrapper[0];
    if (!rootEl) return;

    const obs = new MutationObserver(() => {
      validateAndSync(frm);

      // If input exists now, disconnect (auto-cleanup)
      const $inp = frm.fields_dict[source]?.$wrapper?.find("input");
      if ($inp && $inp.length) {
        try { obs.disconnect(); } catch {}
        frm.__jos_tax_observer = null;
      }
    });

    obs.observe(rootEl, { childList: true, subtree: true });
    frm.__jos_tax_observer = obs;
  }

  // Ensure tax_id is visible even if hidden in meta
  function forceShowTax(frm) {
    const map = CONFIG[frm.doctype];
    if (!map) return;
    const { target } = map;

    const df = frappe.meta.get_docfield(frm.doctype, target);
    if (df) df.hidden = 0;                // runtime meta
    frm.set_df_property(target, "hidden", 0);
    frm.toggle_display(target, true);
  }

  function maybeLockIfPersisted(frm) {
    const map = CONFIG[frm.doctype];
    if (!map) return;
    const { source, target } = map;

    if (!frm.is_new() && frm.doc[source]) {
      frm.set_df_property(source, "read_only", 1);
      frm.set_df_property(target, "read_only", 1);
      forceShowTax(frm);
    }
  }

  // Core: validate, color, and sync to target
  function validateAndSync(frm) {
    const map = CONFIG[frm.doctype];
    if (!map) return;
    const { source, target } = map;

    const field = frm.fields_dict[source];
    if (!field) return;

    const $input = field.$wrapper?.find("input");
    if (!$input || !$input.length) return;

    const raw = (frm.doc[source] || "").trim().toUpperCase();

    if (!raw) {
      $input.css("background-color", "");
      frm.set_value(target, "");
      return;
    }

    // Passport format → keep as-is, paint blue
    if (raw.startsWith("P-")) {
      $input.css("background-color", "#e2f0fb");
      frm.set_value(target, raw);
      lockIfNotNew(frm, source, target);
      return;
    }

    // Generic consumer → yellow
    if (raw === "9999999999999") {
      $input.css("background-color", "#fff3cd");
      frm.set_value(target, raw);
      lockIfNotNew(frm, source, target);
      return;
    }

    const id = raw;
    if (validateEcuadorID(id)) {
      // Valid → green and sync
      $input.css("background-color", "#d4edda");
      frm.set_value(target, raw);
      lockIfNotNew(frm, source, target);
    } else {
      // Invalid → red and clear target
      $input.css("background-color", "#f8d7da");
      frm.set_value(target, "");
    }
  }

  function lockIfNotNew(frm, source, target) {
    if (!frm.is_new()) {
      frm.set_df_property(source, "read_only", 1);
      frm.set_df_property(target, "read_only", 1);
      forceShowTax(frm);
    }
  }

  // ===== Ecuador ID/RUC validators =====
  function validateEcuadorID(id) {
    if (!/^\d{10}(\d{3})?$/.test(id)) return false;

    const province = parseInt(id.slice(0, 2), 10);
    if (province < 1 || province > 24) return false;

    const third = parseInt(id[2], 10);
    if (third < 6) return validateCedula(id.slice(0, 10)); // natural person (cédula)
    if (third === 6) return validatePublicRUC(id);          // public entity
    if (third === 9) return validatePrivateRUC(id);         // private company

    return false;
  }

  function validateCedula(cedula) {
    const digits = cedula.split("").map(Number);
    const check = digits.pop();
    let total = 0;

    for (let i = 0; i < digits.length; i++) {
      let v = digits[i];
      if (i % 2 === 0) {
        v *= 2;
        if (v > 9) v -= 9;
      }
      total += v;
    }
    const computed = (10 - (total % 10)) % 10;
    return check === computed;
  }

  function validatePublicRUC(ruc) {
    if (ruc.length !== 13 || !ruc.endsWith("0001")) return false;
    const coeffs = [3, 2, 7, 6, 5, 4, 3, 2];
    const d = ruc.split("").map(Number);
    const total = coeffs.reduce((s, c, i) => s + d[i] * c, 0);
    const check = 11 - (total % 11);
    return d[8] === (check === 11 ? 0 : check);
  }

  function validatePrivateRUC(ruc) {
    if (ruc.length !== 13 || !ruc.endsWith("001")) return false;
    const coeffs = [4, 3, 2, 7, 6, 5, 4, 3, 2];
    const d = ruc.split("").map(Number);
    const total = coeffs.reduce((s, c, i) => s + d[i] * c, 0);
    const check = 11 - (total % 11);
    return d[9] === (check === 11 ? 0 : check);
  }
})();
