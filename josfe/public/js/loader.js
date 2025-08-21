// apps/josfe/josfe/public/js/loader.js
(() => {
  if (window.__josfe_loader_initialized) return;
  window.__josfe_loader_initialized = true;

  const DEBUG = true;
  const log = (...args) => DEBUG && console.log("[josfe:loader]", ...args);
  const STORAGE_KEY = "josfe_selected_establishment";

  // ------------------------------------------
  // 1. LocalStorage Helpers
  // ------------------------------------------
  function getStoredSelection() {
    try {
      const val = localStorage.getItem(STORAGE_KEY);
      return val?.trim() || null;
    } catch {
      return null;
    }
  }

  function setStoredSelection(val) {
    try {
      if (val) localStorage.setItem(STORAGE_KEY, val);
      else localStorage.removeItem(STORAGE_KEY);
    } catch {}
  }

  // ------------------------------------------
  // 2. Patch logout (reliable across tabs)
  // ------------------------------------------
  (() => {
    const patchLogout = () => {
      const fn = frappe?.app?.logout;
      if (typeof fn !== "function") return;
      if (window.__josfe_logout_patch_applied) return;

      window.__josfe_logout_patch_applied = true;

      frappe.app.logout = function (...args) {
        try {
          localStorage.removeItem(STORAGE_KEY);
          console.log("[josfe:logout] cleared localStorage");
        } catch {}
        return fn.apply(this, args);
      };

      console.log("[josfe:logout] patch installed");
    };

    patchLogout();

    const obs = new MutationObserver(() => patchLogout());
    obs.observe(document.body, { childList: true, subtree: true });
  })();

  // ------------------------------------------
  // 3. Route guard to enforce warehouse selection
  // ------------------------------------------
  function isPickerRoute() {
    try {
      const h = (window.location.hash || "").toLowerCase();
      const p = (window.location.pathname || "").toLowerCase();
      const r = frappe.router?.get_route?.();

      return (
        h.includes("location-picker") ||
        p.endsWith("/app/location-picker") ||
        (Array.isArray(r) && r[0]?.toLowerCase() === "location-picker")
      );
    } catch {
      return false;
    }
  }

  function guardLocationSelection() {
    let sel = frappe.boot?.jos_selected_establishment || null;
    const localSel = getStoredSelection();

    if (!sel && localSel && !isPickerRoute()) {
      console.warn("[josfe:guard] boot empty, rehydrating from localStorage:", localSel);
      if (!frappe.boot) frappe.boot = {};
      frappe.boot.jos_selected_establishment = localSel;
      sel = localSel;

      frappe.call('josfe.user_location.session.set_selected_establishment', { warehouse: localSel })
        .then(() => console.log("[josfe:guard] server re-sync OK"))
        .catch(e => console.warn("[josfe:guard] server re-sync failed", e));
    }

    if (!sel && !isPickerRoute()) {
      console.warn("[josfe:guard] No establishment selected. Redirecting to /app/location-picker");
      frappe.set_route("location-picker");
      return false;
    }

    return true;
  }

  // ------------------------------------------
  // 4. Inject warehouse badge in navbar
  // ------------------------------------------
  function injectWarehouseBadge(selected) {
    if (!selected) return;

    const styleMap = {
      "Sucursal Guamaní - A": { letter: "G", color: "#27ae60" },
      "Sucursal Mariscal - A": { letter: "M", color: "#f1c40f" },
      "Sucursal Primax - A": { letter: "P", color: "#3498db" },
      "__CONSOLIDADO__": { letter: "T", color: "#2c3e50" }
    };
    const map = styleMap[selected] || { letter: "?", color: "#7f8c8d" };

    const $logo = document.querySelector(".navbar-home");
    if ($logo && !document.querySelector("#jos-warehouse-icon")) {
      const el = document.createElement("span");
      el.id = "jos-warehouse-icon";
      el.innerHTML = `&nbsp;<span style="
        font-weight:700; font-size:18px; color:${map.color};
        display:inline-flex; align-items:center; justify-content:center;
        width:22px; height:22px; border-radius:4px; background:${map.color}20;">
        ${map.letter}
      </span>`;
      $logo.appendChild(el);
      log("Badge injected:", map.letter, "for", selected);
    }
  }

  // ------------------------------------------
  // 5. JS script map by Doctype
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

  // ------------------------------------------
  // 6. Main app boot hook
  // ------------------------------------------
  frappe.after_ajax(() => {
    const bootSel = frappe.boot?.jos_selected_establishment ?? null;
    log("boot.jos_selected_establishment:", bootSel);

    if (bootSel) setStoredSelection(bootSel);
    guardLocationSelection();

    frappe.ui?.form?.on?.("*", {
      setup(frm) {
        if (frm.doctype === "DocType") return;
        loadForDoctype(frm.doctype);
      }
    });

    if (frappe.router?.on && frappe.get_route) {
      frappe.router.on("change", () => {
        const r = frappe.get_route();
        log("route change:", r);
        if (guardLocationSelection() === false) return;
        if (r?.[0] === "Form" && r[1] && r[1] !== "DocType") {
          loadForDoctype(r[1]);
        }
      });
    } else {
      window.addEventListener("hashchange", () => {
        if (guardLocationSelection() === false) return;
        log("route change (hash):", window.location.hash);
      });
    }

    // Add user menu option
    if (frappe.app?.user_menu) {
      const label = "Cambiar Establecimiento";
      const exists = frappe.app.user_menu.items?.some(i => (i.label || "") === label);
      if (!exists) {
        frappe.app.user_menu.add_item({ label, action: () => frappe.set_route("location-picker") });
      }
    }

    injectWarehouseBadge(bootSel);
    log("doctypes_loader initialized");
  });

  // ------------------------------------------
  // 7. Global redirect to login on expired session
  // ------------------------------------------
  frappe.after_ajax(() => {
    function handleUnauthorized() {
      frappe.show_alert({ message: "Sesión terminada. Redirigiendo al login…", indicator: "orange" });
      console.warn("[josfe] Session expired or logged out. Redirecting to /login");
      setTimeout(() => { window.location.href = "/login"; }, 800);
    }

    // A) Catch 403 errors only if our custom header is set
    if (Array.isArray(frappe.ajax_error_handlers)) {
      frappe.ajax_error_handlers.push((xhr) => {
        const expired = xhr?.getResponseHeader("X-ERPNext-Session-Expired");
        if (xhr.status === 403 && expired === "1") {
          handleUnauthorized();
          return true;
        }
      });
    }

    // B) React to logout in another tab
    window.addEventListener("storage", (e) => {
      if (e.key === STORAGE_KEY && e.newValue === null) {
        console.warn("[josfe] Logout detected in another tab via localStorage");
        handleUnauthorized();
      }
    });
  });

  // ------------------------------------------
  // 8. Final debug on tab close
  // ------------------------------------------
  window.addEventListener("beforeunload", () => {
    const bootSel = frappe.boot?.jos_selected_establishment ?? null;
    console.log("[josfe:loader] beforeunload, jos_selected_establishment:", bootSel);
  });
})();
