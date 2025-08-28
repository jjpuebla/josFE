frappe.after_ajax(() => {
  const sel = frappe.boot?.jos_selected_establishment || null;
  console.log("[josfe:session] boot.jos_selected_establishment (desk):", sel);

  function tryPatchLogout() {
    if (!frappe.app || typeof frappe.app.logout !== "function") {
      console.log("[josfe:session] waiting for frappe.app.logout...");
      return setTimeout(tryPatchLogout, 300);
    }

    const origLogout = frappe.app.logout;
    frappe.app.logout = function (...args) {
      console.log("[josfe:logout] jos_selected_establishment at logout:", frappe.boot.jos_selected_establishment);
      return origLogout.apply(this, args);
    };

    console.log("[josfe:session] logout patched ✅");
  }

  tryPatchLogout();
});
