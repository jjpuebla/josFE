// apps/josfe/josfe/public/js/location_guard.js
// Redirect users to the location-picker until a warehouse is chosen.
// No setTimeout; safe even when router/route isn't ready yet.

(function () {
  function isPickerRoute() {
    try {
      // Prefer hash (e.g. #app/location-picker) which is always present on Desk
      const h = (window.location.hash || "").toLowerCase();
      if (h.includes("location-picker")) return true;

      // Fallbacks: path or router (guarded)
      const p = (window.location.pathname || "").toLowerCase();
      if (p.endsWith("/app/location-picker")) return true;

      if (frappe.router && typeof frappe.router.get_route === "function") {
        const r = frappe.router.get_route(); // can be null/undefined early
        if (Array.isArray(r) && r.length && String(r[0]).toLowerCase() === "location-picker") {
          return true;
        }
      }
    } catch (e) {
      // swallow — we only care about a boolean
    }
    return false;
  }

  function guard() {
    const sel = frappe.boot?.jos_selected_establishment || null;

    // If already on picker, do nothing
    if (isPickerRoute()) return true;

    // If not selected, send to picker
    if (!sel) {
      console.warn("[josfe:guard] No establishment selected. Redirecting to /app/location-picker");
      frappe.set_route("location-picker");
      return false;
    }
    return true;
  }

  // Run once after first ajax (boot loaded) and on route changes
  frappe.after_ajax(guard);

  if (frappe.router?.on) {
    frappe.router.on("change", guard);
  } else {
    window.addEventListener("hashchange", guard);
  }

    // Add a "Cambiar Establecimiento" action in the user menu
    frappe.after_ajax(() => {
    if (!frappe.app || !frappe.app.user_menu) return;
    const label = "Cambiar Establecimiento";
    const exists = frappe.app.user_menu.items?.some(i => (i.label||"") === label);
    if (exists) return;

    frappe.app.user_menu.add_item({
        label,
        action: () => frappe.set_route("location-picker")
    });
    });
})();
