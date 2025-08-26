// public/js/tax_id_utils.js
console.log("✅ tax_utils.js started");

(() => {
  const CONFIG = {
    Customer: { source: "custom_jos_tax_id_validador", target: "tax_id" },
    Supplier: { source: "custom_jos_ruc_supplier",     target: "tax_id" },
    Company:  { source: "custom_jos_ruc",              target: "tax_id" },
  };

  Object.entries(CONFIG).forEach(([dt, { source }]) => {
    const eventMap = {
      onload(frm) { bindOnce(frm); forceShowTax(frm); validateAndSync(frm); },
      onload_post_render(frm) { forceShowTax(frm); validateAndSync(frm); },
      refresh(frm) {
        forceShowTax(frm);
        if (frm.is_new()) {
          const $inp = frm.fields_dict[source]?.$wrapper?.find("input");
          if ($inp) $inp.css("background-color", "");
          frm.set_df_property(source, "read_only", 0);
        }
        validateAndSync(frm);
        maybeLockIfPersisted(frm);
      },
      before_refresh(frm) {
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
    eventMap[source] = function (frm) { validateAndSync(frm); };
    frappe.ui.form.on(dt, eventMap);
  });

  function bindOnce(frm) {
    if (frm.__jos_tax_bound) return;
    frm.__jos_tax_bound = true;
    const map = CONFIG[frm.doctype]; if (!map) return;
    const { source } = map;
    const $inp = frm.fields_dict[source]?.$wrapper?.find("input");
    if ($inp && $inp.length) {
      $inp.on("input", () => validateAndSync(frm));
    } else {
      attachObserverIfNeeded(frm);
    }
  }

  function attachObserverIfNeeded(frm) {
    if (frm.__jos_tax_observer) return;
    const map = CONFIG[frm.doctype]; if (!map) return;
    const { source } = map;
    const $now = frm.fields_dict[source]?.$wrapper?.find("input");
    if ($now && $now.length) return;
    const rootEl = frm.$wrapper && frm.$wrapper[0];
    if (!rootEl) return;
    const obs = new MutationObserver(() => {
      validateAndSync(frm);
      const $inp = frm.fields_dict[source]?.$wrapper?.find("input");
      if ($inp && $inp.length) { try { obs.disconnect(); } catch {}; frm.__jos_tax_observer = null; }
    });
    obs.observe(rootEl, { childList: true, subtree: true });
    frm.__jos_tax_observer = obs;
  }

  function forceShowTax(frm) {
    const map = CONFIG[frm.doctype]; if (!map) return;
    const { target } = map;
    const df = frappe.meta.get_docfield(frm.doctype, target);
    if (df) df.hidden = 0;
    frm.set_df_property(target, "hidden", 0);
    frm.toggle_display(target, true);
  }

  function maybeLockIfPersisted(frm) {
    const map = CONFIG[frm.doctype]; if (!map) return;
    const { source, target } = map;
    if (!frm.is_new() && frm.doc[source]) {
      frm.set_df_property(source, "read_only", 1);
      frm.set_df_property(target, "read_only", 1);
      forceShowTax(frm);
    }
  }

  function validateAndSync(frm) {
    const map = CONFIG[frm.doctype]; if (!map) return;
    const { source, target } = map;
    const field = frm.fields_dict[source]; if (!field) return;
    const $input = field.$wrapper?.find("input"); if (!$input || !$input.length) return;

    const raw = (frm.doc[source] || "").trim().toUpperCase();
    if (!raw) { $input.css("background-color", ""); frm.set_value(target, ""); return; }

    if (raw.startsWith("P-")) { // Pasaporte
      $input.css("background-color", "#e2f0fb");
      frm.set_value(target, raw);
      lockIfNotNew(frm, source, target);
      return;
    }

    if (raw === "9999999999999") { // Consumidor final
      $input.css("background-color", "#fff3cd");
      frm.set_value(target, raw);
      lockIfNotNew(frm, source, target);
      return;
    }

    const id = raw;
    const result = validateEcuadorID(id);

    if (result === true) {
      $input.css("background-color", "#d4edda"); // verde
      frm.set_value(target, raw);
      lockIfNotNew(frm, source, target);
    } else if (result === "SKIP") {
      $input.css("background-color", "#e2f0fb"); // azul → RUC público/privado aceptado sin módulo 11
      frm.set_value(target, raw);
      lockIfNotNew(frm, source, target);
    } else {
      $input.css("background-color", "#f8d7da"); // rojo
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

    if (third < 6) return validateCedula(id.slice(0, 10));
    if (third === 6 || third === 9) return "SKIP"; // ← nuevo: saltar módulo 11
    return false;
  }

  function validateCedula(cedula) {
    const digits = cedula.split("").map(Number);
    const check = digits.pop();
    let total = 0;
    for (let i = 0; i < digits.length; i++) {
      let v = digits[i];
      if (i % 2 === 0) { v *= 2; if (v > 9) v -= 9; }
      total += v;
    }
    const computed = (10 - (total % 10)) % 10;
    return check === computed;
  }

  // (Se dejan validatePublicRUC y validatePrivateRUC por compatibilidad si decides reactivar)
  function validatePublicRUC(ruc) { /* ya no se usa */ return true; }
  function validatePrivateRUC(ruc) { /* ya no se usa */ return true; }

})();
