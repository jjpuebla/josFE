// apps/josfe/josfe/public/js/loader.js
(() => {
  // --- one-time guard (avoids double registration on hot reload) ---
  if (window.__josfe_loader_initialized) return;
  window.__josfe_loader_initialized = true;

  // Toggle for console logs in dev
  const DEBUG = true;
  const log = (...a) => DEBUG && console.log("[josfe:loader]", ...a);

  // Map: exact Doctype names (as stored in DB / shown in cur_frm.doctype)
  const scriptMap = {
    Customer: [
      "/assets/josfe/js/phone_utils.js",
      "/assets/josfe/js/tax_id_utils.js",
      "/assets/josfe/js/contact_html_enhancer.js"
    ],
    Supplier: [
      "/assets/josfe/js/phone_utils.js",
      "/assets/josfe/js/tax_id_utils.js",
      "/assets/josfe/js/contact_html_enhancer.js"
    ],
    Contact: [
      "/assets/josfe/js/phone_utils.js",
      "/assets/josfe/js/contact_html_enhancer.js"
    ],
    Company: [
      "/assets/josfe/js/tax_id_utils.js"
    ],
    "Credenciales SRI": [
      "/assets/josfe/js/sri_credential.js"
    ],

    // 👇 Add these
    "Sales Invoice": [
      "/assets/josfe/js/user_location_boot.js",
      "/assets/josfe/js/form_location_lock.js"
    ],
    "Nota de Crédito": [
      "/assets/josfe/js/user_location_boot.js",
      "/assets/josfe/js/form_location_lock.js"
    ],
    "Nota de Débito": [
      "/assets/josfe/js/user_location_boot.js",
      "/assets/josfe/js/form_location_lock.js"
    ],
    "Comprobante de Retención": [
      "/assets/josfe/js/user_location_boot.js",
      "/assets/josfe/js/form_location_lock.js"
    ],
    "Liquidación de Compra": [
      "/assets/josfe/js/user_location_boot.js",
      "/assets/josfe/js/form_location_lock.js"
    ],
    "Guía de Remisión": [
      "/assets/josfe/js/user_location_boot.js",
      "/assets/josfe/js/form_location_lock.js"
    ]
  };

  // Loader: rely on frappe.require (deduped, cached)
  function loadForDoctype(dt) {
    const list = scriptMap[dt] || [];
    if (!list.length) return;
    log("Doctype detected → loading scripts:", dt, list);
    list.forEach(src => frappe.require(src));
  }

  // Register after desk boot (no timers)
  frappe.after_ajax(() => {
    // 1) Form lifecycle: inject during setup (before refresh)
    if (frappe.ui?.form?.on) {
      frappe.ui.form.on("*", {
        setup(frm) {
          // Ignore the DocType editor itself (/app/doctype/...)
          if (frm.doctype === "DocType") return;
          loadForDoctype(frm.doctype);
        }
      });
    }

    // 2) Route navigations (e.g., List→Form): load when landing on a Form
    if (frappe.router?.on && frappe.get_route) {
      frappe.router.on("change", () => {
        const r = frappe.get_route(); // e.g., ["Form","Customer","CUST-0001"]
        if (r && r[0] === "Form" && r[1] && r[1] !== "DocType") {
          loadForDoctype(r[1]);
        }
      });
    }

    log("doctypes_loader initialized");
  });
})();
