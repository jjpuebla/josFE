// josfe/ui_controls/role_rules.js
// ✅ fixed version
// - correct API call (get_role_rules)
// - union across all frappe.user_roles
// - debug logging so you see what’s happening

console.log("✅ role_rules.js (union of roles + correct API call)");

// TESTING TESTING TESTING TESTING TESTING TESTING TESTING TESTING TESTING TESTING

// Load all UI Settings rows once
const __UI_ROWS_PROMISE__ = frappe.call({
  method: "josfe.ui_controls.helpers.list_ui_settings"
}).then(r => r.message || []);

// Helper to log rules
function log_rules(dt) {
  __UI_ROWS_PROMISE__.then(rows => {
    const relevant = rows.filter(row => row.doctype_name === dt);
    if (!relevant.length) {
      console.log(`📋 Joselito: no UI Settings rows for ${dt}`);
      return;
    }
    relevant.forEach(row => {
      frappe.call({
        method: "josfe.ui_controls.helpers.get_role_rules",
        args: { role: row.role, doctype: dt }
      }).then(r => {
        console.log(`📦 Joselito Rules for role=${row.role}, doctype=${dt}:`, r.message);
      });
    });
  });
}

// Attach hooks per doctype
__UI_ROWS_PROMISE__.then(rows => {
  const doctypes = [...new Set(rows.map(row => row.doctype_name))];
  console.log("📋 Joselito Dynamic doctypes:", doctypes);

  doctypes.forEach(dt => {
frappe.ui.form.on(dt, {
  refresh(frm) {
    try { apply_ui_rules(frm); } catch (e) {
      console.warn(`apply_ui_rules failed for ${dt}`, e);
    }
  },
  onload_post_render(frm) {
    try { apply_ui_rules(frm); } catch (e) {
      console.warn(`apply_ui_rules failed for ${dt}`, e);
    }
  }
});
  });
});

// 🔄 Immediate safeguard: only run if cur_frm exists AND hooks haven’t run yet
frappe.after_ajax(() => {
  if (cur_frm && cur_frm.doctype && !cur_frm.__jos_rules_applied) {
    console.log(`🔄 Joselito safeguard after reload for ${cur_frm.doctype}`);
    log_rules(cur_frm.doctype);
    cur_frm.__jos_rules_applied = true;  // mark so hooks won’t duplicate
  }
});
// TESTING TESTING TESTING TESTING TESTING TESTING TESTING TESTING TESTING TESTING






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
        // console.log("📦 Response", res, ":", res.message);
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

// frappe.ui.form.on("*", {
//   refresh(frm) {
//     try {
//       apply_ui_rules(frm);
//     } catch (e) {
//       console.warn("apply_ui_rules failed on refresh", e);
//     }
//   },
//   onload_post_render(frm) {
//     try {
//       apply_ui_rules(frm);
//     } catch (e) {
//       console.warn("apply_ui_rules failed on onload_post_render", e);
//     }
//   }
// });


window.addEventListener("storage", e => {
  if (e.key !== "josfe_ui_controls_update") return;
  if (!cur_frm) return;

  const data = JSON.parse(e.newValue || "{}");
  if (!data.doctype) return;
  if (data.doctype !== cur_frm.doctype) return;

  console.log("📡 Broadcast received for", data.doctype, "→ reapplying rules");

  try {
    apply_ui_rules(cur_frm);
  } catch(err) {
    console.warn("apply_ui_rules failed on broadcast", err);
  }
});





// ---------- Debug: force hide gender for Administrator on Customer ----------
// # TESTING TESTING TESTING TESTING TESTING TESTING TESTING TESTING TESTING TESTING

// ---------- Debug hook: list all UI Settings rows ----------

// frappe.call({
//   method: "josfe.ui_controls.helpers.list_ui_settings"
// }).then(r => {
//   const rows = r.message || [];
//   const doctypes = [...new Set(rows.map(row => row.doctype_name))];

//   console.log("📋 Dynamic doctypes from UI Settings:", doctypes);

//   doctypes.forEach(dt => {
// doctypes.forEach(dt => {
//   frappe.ui.form.on(dt, {
//     refresh(frm) {
//       console.log(`🔎 Joselito Refresh hook running for ${dt}`);

//       // fetch rules for this doctype + all current roles
//       frappe.user_roles.forEach(role => {
//         frappe.call({
//           method: "josfe.ui_controls.helpers.get_role_rules",
//           args: { role: role, doctype: dt }
//         }).then(r => {
//           console.log(`📦 Joselito Rules for role=${role}, doctype=${dt}:`, r.message);
//         });
//       });

//       // still run your existing applier if you want
//       try {
//         apply_ui_rules(frm);
//       } catch (e) {
//         console.warn(`Joselito apply_ui_rules failed for ${dt}`, e);
//       }
//     },
//     onload_post_render(frm) {
//       console.log(`🔎 Joselito onload_post_render hook running for ${dt}`);

//       frappe.user_roles.forEach(role => {
//         frappe.call({
//           method: "josfe.ui_controls.helpers.get_role_rules",
//           args: { role: role, doctype: dt }
//         }).then(r => {
//           console.log(`📦 Joselito Rules for role=${role}, doctype=${dt}:`, r.message);
//         });
//       });

//       try {
//         apply_ui_rules(frm);
//       } catch (e) {
//         console.warn(`Joselito apply_ui_rules failed for ${dt}`, e);
//       }
//     }
//   });
// });
//   });
// });


// frappe.ui.form.on("Customer", {
//   refresh(frm) {
//     console.log("📋 Testing")
//     frappe.call({
//       method: "josfe.ui_controls.helpers.list_ui_settings"
//     }).then(r => {
//       console.log("📋 All UI Settings rows:", r.message);
//     });
//   }
// });

// frappe.ui.form.on("Customer", { 
//   refresh(frm) { 
//     if (frappe.user_roles.includes("Administrator")) 
//       { console.log("✅ Debug: working — gender hidden for Administrator on Customer"); } 
//   } 
// });

// Always re-fetch rules on every page load

