// josfe/ui_controls/role_rules.js
// ✅ fixed version
// - correct API call (get_role_rules)
// - union across all frappe.user_roles
// - debug logging so you see what’s happening

console.log("✅ role_rules.js (union of roles + correct API call)");

const __JOS_UI_MAP__ = {}; // cache: { [doctype]: { fields_by_tab, all_fields } }

function load_doctype_map(dt) {
  if (__JOS_UI_MAP__[dt]) return Promise.resolve(__JOS_UI_MAP__[dt]);
  return frappe.call({
    method: "josfe.ui_controls.helpers.get_fields_and_sections",
    args: { doctype: dt }
  }).then(r => {
    const meta = r.message || { fields_by_tab: {} };
    const all_fields = [];
    Object.values(meta.fields_by_tab || {}).forEach(arr =>
      arr.forEach(f => all_fields.push(f.fieldname))
    );
    __JOS_UI_MAP__[dt] = { fields_by_tab: meta.fields_by_tab || {}, all_fields };
    return __JOS_UI_MAP__[dt];
  });
}

function apply_ui_rules(frm) {
  const dt = frm.doctype;
  if (!dt || dt === "UI Settings") return;

  console.log("🔎 apply_ui_rules triggered on", dt, "for roles:", frappe.user_roles);

  // Load metadata map + collect rules for all roles of this user
  Promise.all([
    load_doctype_map(dt),
    ...frappe.user_roles.map(r =>
      frappe.call({
        method: "josfe.ui_controls.helpers.get_role_rules",
        args: { role: r, doctype: dt }
      })
    )
  ])
    .then(([m, ...responses]) => {
      // Start visible for all fields
      (m.all_fields || []).forEach(fn => frm.toggle_display(fn, true));

      // Union tabs + fields from all role responses
      const hideTabs = new Set();
      const hideFields = new Set();

      responses.forEach(res => {
        const eff = res.message || { tabs: [], fields: [] };
        (eff.tabs || []).forEach(t => hideTabs.add(t));
        (eff.fields || []).forEach(f => hideFields.add(f));
      });

      // Expand tab hides into field hides
      hideTabs.forEach(tab => {
        (m.fields_by_tab[tab] || []).forEach(f => hideFields.add(f.fieldname));
      });

      // Finally hide fields
      hideFields.forEach(fn => {
        frm.toggle_display(fn, false);
        console.log("🚫 hiding field:", fn);
      });
    })
    .catch(e => {
      console.warn("apply_ui_rules error on", dt, e);
    });
}

frappe.ui.form.on("*", {
  refresh(frm) {
    try {
      apply_ui_rules(frm);
    } catch (e) {
      console.warn("apply_ui_rules failed", e);
    }
  }
});
