// josfe/ui_controls/role_rules.js
console.log("✅ role_rules.js (production ready)");

// cache: { [doctype]: { fields_by_tab, all_fields } }
const __JOS_UI_MAP__ = {};
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

  Promise.all([
    load_doctype_map(dt),
    frappe.call({ method: "josfe.ui_controls.helpers.get_effective_rules", args: { doctype: dt } })
  ])
  .then(([m, res]) => {
    // Reset all visible
    (m.all_fields || []).forEach(fn => frm.toggle_display(fn, true));

    const eff = res.message || { tabs: [], fields: [] };
    const hideTabs = new Set(eff.tabs || []);
    const hideFields = new Set(eff.fields || []);

    // Expand tab hides into field hides + hide tab containers fast
    hideTabs.forEach(tab => {
      const tabWrapper = frm.fields_dict[tab] && frm.fields_dict[tab].wrapper;
      if (tabWrapper) {
        $(tabWrapper).closest(".form-section, .form-page").css("display", "none");
      }
      (m.fields_by_tab[tab] || []).forEach(f => hideFields.add(f.fieldname));
    });

    // Hide fields
    hideFields.forEach(fn => frm.toggle_display(fn, false));
  })
  .catch(e => console.warn("apply_ui_rules error on", dt, e));
}
// Hooks per doctype from UI Settings
frappe.call({ method: "josfe.ui_controls.helpers.list_ui_settings" })
  .then(r => {
    const doctypes = [...new Set((r.message || []).map(row => row.doctype_name))];
    console.log("📋 Joselito Dynamic doctypes:", doctypes);

    doctypes.forEach(dt => {
      frappe.ui.form.on(dt, {
        refresh(frm) { apply_ui_rules(frm); },
        onload_post_render(frm) { apply_ui_rules(frm); }
      });
    });
  });

// Safeguard after reload
frappe.after_ajax(() => {
  if (cur_frm && cur_frm.doctype && !cur_frm.__jos_rules_applied) {
    console.log(`🔄 Safeguard running apply_ui_rules for ${cur_frm.doctype}`);
    apply_ui_rules(cur_frm);
    cur_frm.__jos_rules_applied = true;
  }
});

// Broadcast update
window.addEventListener("storage", e => {
  if (e.key !== "josfe_ui_controls_update") return;
  if (!cur_frm) return;

  const data = JSON.parse(e.newValue || "{}");
  if (!data.doctype || data.doctype !== cur_frm.doctype) return;

  console.log(`🔄 Broadcast: reapplying rules for ${cur_frm.doctype}`);
  apply_ui_rules(cur_frm);
});
