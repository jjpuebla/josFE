// apps/josfe/josfe/public/js/loader.js
(() => {
  if (window.__josfe_loader_initialized) return;
  window.__josfe_loader_initialized = true;

  const DEBUG = true;
  const log = (...args) => DEBUG && console.log("[josfe:loader]", ...args);
  const STORAGE_KEY = "josfe_selected_establishment";

  // ------------------------------------------
  // 1. Debug: Show selection from boot
  // ------------------------------------------
  frappe.after_ajax(() => {
    const bootSel = frappe.boot?.jos_selected_establishment ?? null;
    log("boot.jos_selected_establishment:", bootSel);
    const current = (localStorage.getItem(STORAGE_KEY) || "").trim();
    if (!current && bootSel) {
    localStorage.setItem(STORAGE_KEY, bootSel);
    }

    
    // ✅ Redirect if still nothing selected
    if (!bootSel && !current) {
      log("No selection found. Redirecting to location-picker.");
      frappe.set_route("location-picker");
    }
  });

  // ------------------------------------------
  // 2. Patch logout to clear localStorage
  // ------------------------------------------
  frappe.require("/assets/josfe/js/user_location/session_ws_selector.js", () => {
    if (typeof patchLogoutClearWarehouse === "function") {
      patchLogoutClearWarehouse();
    }
  
  });

  // ------------------------------------------
  // 3. Guard: block navigation if no warehouse
  // ------------------------------------------
  frappe.after_ajax(() => {
    frappe.require("/assets/josfe/js/user_location/session_ws_selector.js", () => {
      if (typeof runWarehouseRouteGuard === "function") {
        runWarehouseRouteGuard();
      }
    });
  });

  // ------------------------------------------
  // 4. Inject badge in navbar
  // ------------------------------------------
  frappe.after_ajax(() => {
    frappe.require("/assets/josfe/js/user_location/ui_badge.js");
    frappe.require("/assets/josfe/js/user_location/ui_user_menu.js");
  });

  // ------------------------------------------
  // 5. Lazy-load extra scripts per Doctype
  // ------------------------------------------
  const scriptMap = {
    Customer: ["/assets/josfe/js/phone_utils.js", "/assets/josfe/js/tax_id_utils.js", "/assets/josfe/js/contact_html_enhancer.js"],
    Supplier: ["/assets/josfe/js/phone_utils.js", "/assets/josfe/js/tax_id_utils.js", "/assets/josfe/js/contact_html_enhancer.js"],
    Contact: ["/assets/josfe/js/phone_utils.js", "/assets/josfe/js/contact_html_enhancer.js"],
    Company: ["/assets/josfe/js/tax_id_utils.js"],
    "Credenciales SRI": ["/assets/josfe/js/sri_credential.js"],
    "Sales Invoice": ["/assets/josfe/js/form_location_lock.js"],
    "Nota de Crédito": ["/assets/josfe/js/form_location_lock.js"],
    "Nota de Débito": ["/assets/josfe/js/form_location_lock.js"],
    "Comprobante de Retención": ["/assets/josfe/js/form_location_lock.js"],
    "Liquidación de Compra": ["/assets/josfe/js/form_location_lock.js"],
    "Guía de Remisión": ["/assets/josfe/js/form_location_lock.js"]
  };

  function loadForDoctype(doctype) {
    const list = scriptMap[doctype] || [];
    if (!list.length) return;
    log("Doctype detected → loading scripts:", doctype, list);
    list.forEach(src => frappe.require(src));
  }

  // Load on form setup or route change
  frappe.after_ajax(() => {
    if (frappe.ui?.form?.on) {
      frappe.ui.form.on("*", {
        setup(frm) {
          if (frm.doctype === "DocType") return;
          loadForDoctype(frm.doctype);
        }
      });
    }

    if (frappe.router?.on && frappe.get_route) {
      frappe.router.on("change", () => {
        const r = frappe.get_route();
        log("route change:", r);
        if (r?.[0] === "Form" && r[1] && r[1] !== "DocType") {
          loadForDoctype(r[1]);
        }
      });
    } else {
      window.addEventListener("hashchange", () => {
        log("route change (hash):", window.location.hash);
      });
    }
  });


  // ------------------------------------------
  // 6. Final debug on unload
  // ------------------------------------------
  window.addEventListener("beforeunload", () => {
    const bootSel = frappe.boot?.jos_selected_establishment ?? null;
    console.log("[josfe:loader] beforeunload, jos_selected_establishment:", bootSel);
  });
})();
