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
    ...frappe.user_roles.map(r =>
      frappe.call({ method: "josfe.ui_controls.helpers.get_role_rules", args: { role: r, doctype: dt } })
    )
  ])
  .then(([m, ...responses]) => {
    (m.all_fields || []).forEach(fn => frm.toggle_display(fn, true));
    const hideTabs = new Set(), hideFields = new Set();

    responses.forEach(res => {
      const eff = res.message || { tabs: [], fields: [] };
      (eff.tabs || []).forEach(t => hideTabs.add(t));
      (eff.fields || []).forEach(f => hideFields.add(f));
    });
    hideTabs.forEach(tab => {
      // Hide the entire section/tab
      const tabWrapper = cur_frm.fields_dict[tab] && cur_frm.fields_dict[tab].wrapper;
      if (tabWrapper) {
        $(tabWrapper).closest(".form-section, .form-page").hide();
      }

      // Also mark all fields in the tab as hidden (for consistency)
      (m.fields_by_tab[tab] || []).forEach(f => hideFields.add(f.fieldname));
    });

    // Finally hide fields
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
    console.log(`🔄 safeguard apply rules for ${cur_frm.doctype}`);
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
  apply_ui_rules(cur_frm);
});
