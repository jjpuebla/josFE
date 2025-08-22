// --------------------------------------------
// session_ws_selector.js
// apps/josfe/josfe/public/js/user_location/session_ws_selector.js
// --------------------------------------------

(() => {
  const STORAGE_KEY = "josfe_selected_establishment";

  function getStoredSelection() {
    try {
      return localStorage.getItem(STORAGE_KEY)?.trim() || null;
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

  // Patch logout to clear localStorage across tabs
  const patchLogout = () => {
    const fn = frappe?.app?.logout;
    if (typeof fn !== "function" || window.__josfe_logout_patch_applied) return;
    window.__josfe_logout_patch_applied = true;
    frappe.app.logout = function (...args) {
      try { localStorage.removeItem(STORAGE_KEY); } catch {}
      return fn.apply(this, args);
    };
    console.log("[josfe:logout] patch installed");
  };

  patchLogout();
  new MutationObserver(() => patchLogout()).observe(document.body, { childList: true, subtree: true });

  // Guard: enforce warehouse selection
  function isPickerRoute() {
    const h = (window.location.hash || "").toLowerCase();
    const p = (window.location.pathname || "").toLowerCase();
    const r = frappe.router?.get_route?.();
    return h.includes("location-picker") || p.endsWith("/app/location-picker") || (Array.isArray(r) && r[0]?.toLowerCase() === "location-picker");
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

  frappe.after_ajax(() => {
    const bootSel = frappe.boot?.jos_selected_establishment ?? null;
    if (bootSel) setStoredSelection(bootSel);
    guardLocationSelection();

    if (frappe.ui?.form?.on) {
      frappe.ui.form.on("*", {
        setup(frm) {
          if (frm.doctype !== "DocType") {
            const map = window.__josfe_script_map || {};
            (map[frm.doctype] || []).forEach(src => frappe.require(src));
          }
        }
      });
    }

    if (frappe.router?.on && frappe.get_route) {
      frappe.router.on("change", () => {
        const r = frappe.get_route();
        if (guardLocationSelection() === false) return;
        if (r?.[0] === "Form" && r[1] && r[1] !== "DocType") {
          const map = window.__josfe_script_map || {};
          (map[r[1]] || []).forEach(src => frappe.require(src));
        }
      });
    } else {
      window.addEventListener("hashchange", () => {
        if (guardLocationSelection() === false) return;
      });
    }

    // Handle session-expired + logout in another tab
    function handleUnauthorized() {
      frappe.show_alert({ message: "Sesión terminada. Redirigiendo al login…", indicator: "orange" });
      console.warn("[josfe] Session expired. Redirecting to /login");
      setTimeout(() => { window.location.href = "/login"; }, 800);
    }

    if (Array.isArray(frappe.ajax_error_handlers)) {
      frappe.ajax_error_handlers.push((xhr) => {
        const expired = xhr?.getResponseHeader("X-ERPNext-Session-Expired");
        if (xhr.status === 403 && expired === "1") {
          handleUnauthorized();
          return true;
        }
      });
    }

    window.addEventListener("storage", (e) => {
      if (e.key === STORAGE_KEY && e.newValue === null) {
        console.warn("[josfe] Logout detected in another tab");
        handleUnauthorized();
      }
    });
  });
})();

