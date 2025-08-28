// apps/josfe/josfe/public/js/user_location/location_guard.js
(() => {
  const DEBUG = false;
  const log = (...args) => DEBUG && console.log("[josfe:guard]", ...args);

  const CHANNEL = "josfe_establishment";
  const SIGNAL_KEY = "josfe_establishment_signal";

  function getWH() {
    return (frappe.boot?.jos_selected_establishment || "").trim();
  }

  // Redirect to picker if nothing selected
  function ensureSelectionOrRedirect() {
    const wh = getWH();
    const r = frappe.get_route ? frappe.get_route() : [];
    const isPicker = r && r[0] === "location-picker";
    if (!wh && !isPicker) {
      log("No selection found → redirecting to picker");
      frappe.set_route("location-picker");
    }
  }

  // Add "Cambiar Establecimiento" to user menu
  function ensureUserMenuAction() {
    // Try to find the profile dropdown menu
    const menu = document.querySelector(".navbar .dropdown-menu");
    if (!menu) return;
    if (menu.querySelector(".josfe-change-wh")) return;

    const li = document.createElement("li");
    li.className = "josfe-change-wh";
    const a = document.createElement("a");
    a.href = "#";
    a.textContent = "Cambiar Establecimiento";
    a.addEventListener("click", (e) => {
      e.preventDefault();
      frappe.set_route("location-picker");
    });
    li.appendChild(a);
    menu.appendChild(li);
  }

  // On boot
  frappe.after_ajax(() => {
    log("boot.jos_selected_establishment:", getWH());
    ensureSelectionOrRedirect();
    ensureUserMenuAction();
  });

  // Guard every route change
  if (frappe.router?.on && frappe.get_route) {
    frappe.router.on("change", () => {
      ensureSelectionOrRedirect();
      ensureUserMenuAction();
    });
  }

  // Debug before unload (optional)
  window.addEventListener("beforeunload", () => {
    if (DEBUG) console.log("[josfe:guard] beforeunload WH:", getWH());
  });

  // Listen for cross-tab signals (if selection changes in another tab)
  function onRemoteSelectionChanged() {
    // Important: do NOT trust local value. Re-fetch current selection.
    frappe
      .call("josfe.user_location.session.get_establishment_options")
      .then((r) => {
        const latest = (r.message?.selected || "").trim();
        if (!latest) return;
        // update boot mirror
        frappe.boot.jos_selected_establishment = latest;
        // optional: you could also re-run redirects here if you want
      })
      .catch(() => {});
  }

  // BroadcastChannel
  if ("BroadcastChannel" in window) {
    const bc = new BroadcastChannel(CHANNEL);
    bc.onmessage = (ev) => {
      if (ev?.data?.type === "changed") onRemoteSelectionChanged();
    };
  }

  // localStorage fallback
  window.addEventListener("storage", (ev) => {
    if (ev.key === SIGNAL_KEY) onRemoteSelectionChanged();
  });

  // Export for loader (if you still call it)
  window.runWarehouseRouteGuard = ensureSelectionOrRedirect;
})();
