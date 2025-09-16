// josfe/ui_controls/ui_settings.js
// ✅ fixes:
// - fully hide native Save button / avoid dirty state
// - dynamic legend with real role + doctype
// - only show “Save Active” after Factory exists
// - remove “Refresh Matrix” (redundant)
// - never mutate frm.doc for transient flags

console.log("✅ ui_settings.js (fixed—no native save, dynamic legend, conditional buttons)");

// ---------- small utils ----------
const esc = s => (s || "").replace(/[&<>"']/g, m => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[m]));

// prefer transient selectors (selected_*) then saved fields (role/doctype_name)
const pair = frm => ({
  role: frm.doc.selected_role || frm.doc.role || "",
  dt:   frm.doc.selected_doctype || frm.doc.doctype_name || ""
});

// ---------- buttons ----------
function clearAndBuildButtons(frm, hasFactory) {
  frm.clear_custom_buttons();

  // Save as Factory (show only when factory not yet defined) — or show with confirm if you want to allow overwrite
  if (!hasFactory) {
    frm.add_custom_button("Save as Factory Defaults", () => saveRules(frm, 1), "UI Settings");
  } else {
    frm.add_custom_button("Save as Factory Defaults", () => {
      frappe.confirm("Are you sure you want to overwrite Factory Defaults?", () => saveRules(frm, 1));
    }, "UI Settings");
  }

  // Save Active (only after factory exists)  ← (Note a)
  if (hasFactory) {
    frm.add_custom_button("Save Active", () => saveRules(frm, 0), "UI Settings");
  }

  // Reset to Factory (only after factory exists)
  if (hasFactory) {
    frm.add_custom_button("Reset to Factory Defaults", () => resetRules(frm), "UI Settings");
  }

  // ❌ Removed: “Refresh Matrix” (was just draw(frm))  ← (Note b)
}

function hideNativeSaveCompletely(frm) {
  // remove/disable native “Save” affordances to prevent confusion
  frm.disable_save(); // hides primary save
  // extra hard-hide in case theme/erpnext re-attaches actions
  frm.page.wrapper.find(".standard-actions .primary-action").hide();
  frm.page.set_primary_action("", null); // no-op
}

// ---------- matrix container ----------
function matrixBody(frm){
  let $b = frm.$wrapper.find("#jos-ui-matrix-body");
  if (!$b.length){
    const html = `<div id="jos-ui-matrix" style="margin-top:8px">
        <div id="jos-factory-note" style="margin-bottom:6px; font-size:0.9em;"></div>
        <div style="margin-bottom:6px; font-size:0.9em;">
          <span style="color:green; font-weight:bold;">■ Mandatory</span> 
          <span style="background-color:orange; padding:2px 4px; border-radius:4px; margin-left:8px;">■ Core Hidden</span>
          <span style="margin-left:8px;">☑ Visible</span> 
          <span style="margin-left:4px;">☐ Hidden</span>
        </div>
        <div id="jos-ui-matrix-body"></div>
      </div>`;
    frm.$wrapper.find(".form-layout").append(html);
    $b = frm.$wrapper.find("#jos-ui-matrix-body");
  }
  return $b;
}

// ---------- render ----------
function render(frm, meta, pre, hasFactory){
  const $b = matrixBody(frm);
  const hiddenTabs   = new Set(pre?.tabs   || []);
  const hiddenFields = new Set(pre?.fields || []);

  const orangeStyle = "background-color: orange; padding:2px 4px; border-radius:4px;";
  const orangeField = "background-color: orange; padding:1px 3px; border-radius:3px;";
  const greenStyle  = "color: green; font-weight: bold;";

  let html = "";
  (meta.tabs||[]).forEach(t=>{
    const tfn = t.fieldname || "Main";
    const tlabel = t.label || tfn;

    const metaHiddenTab = !!t.hidden;
    const isHiddenTab   = hiddenTabs.has(tfn) || metaHiddenTab;

    const tabChecked = isHiddenTab ? "" : "checked";       // reversed logic: checked=visible
    const tabLocked  = (hasFactory && metaHiddenTab) ? "disabled" : "";
    const tabTitle   = metaHiddenTab ? 'title="Core hidden tab"' : "";

    html += `<div class="card" style="margin:8px 0"><div class="card-body" style="padding:10px 12px">
      <div class="flex" style="justify-content:space-between;align-items:center;margin-bottom:6px">
        <div><b style="${metaHiddenTab ? orangeStyle : ""}">${esc(tlabel)}</b> <span class="text-muted">(${esc(tfn)})</span></div>
        <label ${tabTitle}>
          <input type="checkbox" class="jos-tab" data-tab="${esc(tfn)}" ${tabChecked} ${tabLocked}>
          <span>Visible</span>
        </label>
      </div><div class="row">`;

    (meta.fields_by_tab[tfn]||[]).forEach(f=>{
      const metaHidden = !!f.hidden;
      const isHidden   = hiddenFields.has(f.fieldname) || metaHidden;
      const checked    = isHidden ? "" : "checked";        // reversed

      let disabled = "";
      let style = "";
      let title = "";
      if (f.reqd) {
        disabled = "disabled";
        style = greenStyle;
        title = 'title="Mandatory field"';
      } else if (metaHidden) {
        style = orangeField;
        if (hasFactory) {
          disabled = "disabled";
          title = 'title="Core hidden (locked after Factory)"';
        } else {
          title = 'title="Core hidden (can be changed before Factory)"';
        }
      }

      html += `<div class="col-sm-4" style="margin-bottom:6px">
        <label style="${style}" ${title}>
          <input type="checkbox" class="jos-field" data-tab="${esc(tfn)}" data-field="${esc(f.fieldname)}" ${checked} ${disabled}>
          <span style="margin-left:6px">${esc(f.label)}</span>
          <span class="text-muted">(${esc(f.fieldname)})</span>
        </label>
      </div>`;
    });

    html += `</div></div></div>`;
  });

  $b.html(html);
}

// ---------- collect (reversed: unchecked ⇒ hidden) ----------
function collect(frm){
  const $b = matrixBody(frm);
  const out = [];

  $b.find("input.jos-field").each(function(){
    if (!this.checked){
      out.push({ section_fieldname: this.dataset.tab || "Main", fieldname: this.dataset.field, hide: 1 });
    }
  });

  $b.find("input.jos-tab").each(function(){
    if (!this.checked){
      out.push({ section_fieldname: this.dataset.tab || "Main", fieldname: null, hide: 1 });
    }
  });

  return out;
}

// ---------- load & draw ----------
function draw(frm){
  const { role, dt } = pair(frm);
  const $note = frm.$wrapper.find("#jos-factory-note");

  if (!role || !dt){
    matrixBody(frm).html(`<div class="text-muted">Select Role and Doctype.</div>`);
    clearAndBuildButtons(frm, /*hasFactory*/ false);
    $note.empty();
    return;
  }

  Promise.all([
    frappe.call({method:"josfe.ui_controls.helpers.get_fields_and_sections", args:{ doctype: dt }}),
    frappe.call({method:"josfe.ui_controls.helpers.get_role_rules",          args:{ role, doctype: dt }}),
    frappe.call({method:"josfe.ui_controls.helpers.factory_exists",          args:{ role, doctype: dt }})
  ]).then(([m,p,f])=>{
    const meta       = m.message || { tabs: [], fields_by_tab: {} };
    const pre        = p.message || { tabs: [], fields: [] };
    const hasFactory = !!f.message;

    clearAndBuildButtons(frm, hasFactory);

    // dynamic legend (with real names)
    if (hasFactory) {
      $note
        .html(`✔ Factory Defaults are set for <b>${esc(role)}</b> + <b>${esc(dt)}</b>.<br><span style="color:green">You can now save <b>Active</b> rules on top.</span>`)
        .css({ color: "blue" });
    } else {
      $note
        .html(`✖ Factory Defaults not yet set for <b>${esc(role)}</b> + <b>${esc(dt)}</b>.<br><span style="color:red">Saving now will create Factory Defaults (baseline).</span>`)
        .css({ color: "red" });
    }

    render(frm, meta, pre, hasFactory);
  });
}

// ---------- save / reset ----------
function saveRules(frm, asFactory){
  const { role, dt } = pair(frm);
  if (!role || !dt) return frappe.msgprint("Select Role and Doctype first.");

  const payload = collect(frm);
  frappe.call({
    method: "josfe.ui_controls.helpers.save_role_rules",
    freeze: true,
    freeze_message: asFactory ? "Saving Factory Defaults…" : "Saving Active rules…",
    args: { role, doctype: dt, payload: JSON.stringify(payload), as_factory: asFactory?1:0 }
  }).then(r=>{
    console.log("📥 saveRules response:", r.message);  // debug log
    if (r.message?.factory_created) {
      frappe.msgprint("Factory Defaults saved (Active seeded).");
      // no frm.reload_doc() — avoid marking doc dirty/“Not Saved”
      draw(frm);
    } else {
      frappe.show_alert({ message: "Active rules saved", indicator: "green" });
      draw(frm);
    }
  });
}

function resetRules(frm){
  const { role, dt } = pair(frm);
  if (!role || !dt) return frappe.msgprint("Select Role and Doctype first.");
  frappe.confirm("Reset Active rules to Factory Defaults?", ()=>{
    frappe.call({
      method: "josfe.ui_controls.helpers.reset_role_rules",
      freeze: true, freeze_message: "Resetting…",
      args: { role, doctype: dt }
    }).then(()=>{
      frappe.show_alert({ message: "Reset done", indicator: "blue" });
      draw(frm);
    });
  });
}

// ---------- bindings ----------
frappe.ui.form.on("UI Settings", {
  refresh(frm) {
    hideNativeSaveCompletely(frm);
    draw(frm);
  },
  selected_role(frm){ draw(frm); },
  selected_doctype(frm){ draw(frm); },
  role(frm){ draw(frm); },
  doctype_name(frm){ draw(frm); },
});
