console.log("✅ tax_utils.js started");

frappe.after_ajax(() => {
  const frm = cur_frm;
  
  if (!frm || !["Customer", "Supplier", "Company"].includes(frm.doctype)) {
    console.warn("⚠️ tax_utils.js loaded, but not on a target form");
    return;
  }
  
  console.log("🧾 tax_utils.js running for", frm.doctype);
  
  const config = {
    Customer: {
      source: "custom_jos_tax_id_validador",
      target: "tax_id",
    },
    Supplier: {
      source: "custom_jos_ruc_supplier",
      target: "tax_id",
    },
    Company: {
      source: "custom_jos_ruc",
      target: "tax_id",
    }
  };

  const { source, target } = config[frm.doctype] || {};
  if (!source || !target || !frm.fields_dict[source]) return;

  // Force-show helper (runtime only)
  const forceShowTax = () => {
    const df = frappe.meta.get_docfield(frm.doctype, target);
    if (df) df.hidden = 0;                  // unhide at meta level (runtime)
    frm.set_df_property(target, "hidden", 0); // unhide on the form
    frm.toggle_display(target, true);         // make sure it's visible
  };

  // ✅ Reset background when opening a new form
  frappe.ui.form.on(frm.doctype, {
    refresh(frm) {
      forceShowTax();
      if (frm.is_new()) {
        const $input = frm.fields_dict[source]?.$wrapper?.find("input");
        if ($input) $input.css("background-color", "");
        // Ensure fields are editable for new records
        frm.set_df_property(source, "read_only", 0);
        // frm.set_df_property(target, "read_only", 0);
      }
    },
    
    // 🔒 Make fields read-only after successful save
    after_save(frm) {
      if (frm.doc[source] && frm.doc[target]) {
        frm.set_df_property(source, "read_only", 1);
        frm.set_df_property(target, "read_only", 1);
        forceShowTax();
        console.log("🔒 Fields locked after save");
      }
    }
  });

  // 🔄 Trigger validation when field changes
  frappe.ui.form.on(frm.doctype, {
    [source](frm) {
      validateAndSync(frm);
    }
  });

  // 🚀 Trigger immediately on load
  validateAndSync(frm);
  forceShowTax();

  // 🔒 Lock if tax_id was previously saved (only for existing records)
  if (!frm.is_new() && frm.doc[source]) {
    frm.set_df_property(source, "read_only", 1);
    frm.set_df_property(target, "read_only", 1);
    forceShowTax();
  }

  function validateAndSync(frm) {
    const field = frm.fields_dict[source];
    if (!field) return;
    const $input = field.$wrapper?.find("input");
    if (!$input) return;

    const raw_input = (frm.doc[source] || "").trim().toUpperCase();

    if (!raw_input) {
      $input.css("background-color", "");
      frm.set_value(target, "");
      return;
    }

    const is_passport = raw_input.startsWith("P-");
    const id = is_passport ? raw_input.slice(2) : raw_input;

    if (is_passport) {
      $input.css("background-color", "#e2f0fb"); // blue
      frm.set_value(target, raw_input);
      // Only make read-only if record is already saved
      if (!frm.is_new()) {
        frm.set_df_property(source, "read_only", 1);
        frm.set_df_property(target, "read_only", 1);
      }
      return;
    } else if (id === "9999999999999") {
      $input.css("background-color", "#fff3cd"); // yellow
      frm.set_value(target, raw_input);
      // Only make read-only if record is already saved
      if (!frm.is_new()) {
        frm.set_df_property(source, "read_only", 1);
        frm.set_df_property(target, "read_only", 1);
      }
      return;
    } else if (validateEcuadorID(id)) {
      $input.css("background-color", "#d4edda"); // green
      frm.set_value(target, raw_input);
      // Only make read-only if record is already saved
      if (!frm.is_new()) {
        frm.set_df_property(source, "read_only", 1);
        frm.set_df_property(target, "read_only", 1);
      }
    } else {
      $input.css("background-color", "#f8d7da"); // red
      frm.set_value(target, "");
    }
  }

  function validateEcuadorID(id) {
    if (!/^\d{10}(\d{3})?$/.test(id)) return false;

    const province = parseInt(id.slice(0, 2));
    if (province < 1 || province > 24) return false;

    const third_digit = parseInt(id[2]);
    if (third_digit < 6) return validateCedula(id.slice(0, 10));
    if (third_digit === 6) return validatePublicRUC(id);
    if (third_digit === 9) return validatePrivateRUC(id);

    return false;
  }

  function validateCedula(cedula) {
    const digits = cedula.split('').map(Number);
    const check_digit = digits.pop();
    let total = 0;

    for (let i = 0; i < digits.length; i++) {
      let val = digits[i];
      if (i % 2 === 0) {
        val *= 2;
        if (val > 9) val -= 9;
      }
      total += val;
    }

    const computed = (10 - (total % 10)) % 10;
    return check_digit === computed;
  }

  function validatePublicRUC(ruc) {
    if (ruc.length !== 13 || !ruc.endsWith("0001")) return false;
    const coeffs = [3, 2, 7, 6, 5, 4, 3, 2];
    const digits = ruc.split('').map(Number);
    const total = coeffs.reduce((sum, c, i) => sum + digits[i] * c, 0);
    const check = 11 - (total % 11);
    return digits[8] === (check === 11 ? 0 : check);
  }

  function validatePrivateRUC(ruc) {
    if (ruc.length !== 13 || !ruc.endsWith("001")) return false;
    const coeffs = [4, 3, 2, 7, 6, 5, 4, 3, 2];
    const digits = ruc.split('').map(Number);
    const total = coeffs.reduce((sum, c, i) => sum + digits[i] * c, 0);
    const check = 11 - (total % 11);
    return digits[9] === (check === 11 ? 0 : check);
  }
});
