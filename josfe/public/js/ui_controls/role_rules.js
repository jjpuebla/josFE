// josfe/ui_controls/role_rules.js
console.log("✅ role_rules.js (minimal v1)");

function apply_ui_rules(frm){
  const dt = frm.doctype;
  if (!dt || dt === "UI Settings") return;

  frappe.call({ method:"josfe.ui_controls.helpers.get_ui_rules", args:{ doctype: dt } })
    .then(r=>{
      const rules = (r.message||[]).filter(x => frappe.user_roles.includes(x.role));
      if (!rules.length) return;

      // Start visible
      frm.meta.fields.forEach(df => frm.toggle_display(df.fieldname, true));

      // Group by tab
      const byTab = {};
      rules.forEach(x => {
        const tab = x.section_fieldname || "Main";
        byTab[tab] = byTab[tab] || { tab:0, fields:[] };
        if (x.fieldname) byTab[tab].fields.push(x.fieldname);
        else byTab[tab].tab = 1;
      });

      // Hide tabs (by hiding all fields under that tab)
      Object.keys(byTab).forEach(tab=>{
        const t = byTab[tab];
        if (t.tab){
          frm.meta.fields
            .filter(df => (df.fieldtype!=="Tab Break") && (df.parent || true)) // safety
            .forEach(df => {
              // crude mapping: if meta order assigns df to tab, backend already did it;
              // minimal v1 → just hide all fields when tab is marked hidden.
              frm.toggle_display(df.fieldname, false);
            });
        } else {
          t.fields.forEach(fn => frm.toggle_display(fn, false));
        }
      });
    });
}

frappe.ui.form.on("*", {
  refresh(frm){ try{ apply_ui_rules(frm); }catch(e){} },
});
