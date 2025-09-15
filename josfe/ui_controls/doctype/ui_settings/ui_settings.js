// josfe/ui_controls/ui_settings.js
console.log("✅ ui_settings.js (minimal v1)");

const esc = s => (s||"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
const pair = frm => ({ role: frm.doc.selected_role || frm.doc.role, dt: frm.doc.selected_doctype || frm.doc.doctype_name });

function ensureButtons(frm) {
  frm.clear_custom_buttons();
  frm.__btns = {
    saveActive: frm.add_custom_button("Save Active", () => saveRules(frm, 0), "UI Settings"),
    saveFactory: frm.add_custom_button("Save as Factory Defaults", () => saveRules(frm, 1), "UI Settings"),
    reset: frm.add_custom_button("Reset to Factory Defaults", () => resetRules(frm), "UI Settings"),
    refresh: frm.add_custom_button("Refresh Matrix", () => draw(frm), "UI Settings"),
  };
}
function setButtons(frm, hasFactory){
  frm.__btns?.saveFactory?.prop("disabled", false);
  frm.__btns?.saveActive?.prop("disabled", !hasFactory);
  hasFactory ? frm.__btns?.reset?.show() : frm.__btns?.reset?.hide();
}

function matrixBody(frm){
  
  let $b = frm.$wrapper.find("#jos-ui-matrix-body");
  if (!$b.length){
    const html = `<div id="jos-ui-matrix" style="margin-top:8px">
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

function render(frm, meta, pre){
  const $b = matrixBody(frm);
  const hiddenTabs = new Set(pre?.tabs||[]);
  const hiddenFields = new Set(pre?.fields||[]);

  let html = "";
  (meta.tabs||[]).forEach(t=>{
    const tfn = t.fieldname || "Main";
    const tlabel = t.label || tfn;
    const baseHidden = !!t.hidden; // core hidden
    const checked = hiddenTabs.has(tfn) || baseHidden ? "checked" : "";
    const locked = baseHidden && frm.doc.__isfactory ? "disabled" : "";
    const style = baseHidden ? "background-color: orange; padding:2px 4px; border-radius:4px;" : "";

    html += `<div class="card" style="margin:8px 0"><div class="card-body" style="padding:10px 12px">
      <div class="flex" style="justify-content:space-between;align-items:center;margin-bottom:6px">
        <div><b style="${style}">${esc(tlabel)}</b> <span class="text-muted">(${esc(tfn)})</span></div>
        <label><input type="checkbox" class="jos-tab" data-tab="${esc(tfn)}" ${checked} ${locked}> <span>Hide tab</span></label>
      </div><div class="row">`;

    (meta.fields_by_tab[tfn]||[]).forEach(f=>{
      const isHidden = hiddenFields.has(f.fieldname) || f.hidden;
      const checked = isHidden ? "" : "checked";   // ✅ reverse logic      let disabled = "";
      let style = "";
      if (f.reqd) {
        disabled = "disabled";
        style = "color: green; font-weight: bold;";
      } else if (f.hidden) {
        style = "background-color: orange; padding:1px 3px; border-radius:3px;";
        if (frm.doc.__isfactory) { // mark doc has Factory saved
          disabled = "disabled";
        }
      }
      html += `<div class="col-sm-4" style="margin-bottom:6px">
        <label style="${style}">
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

function collect(frm){
  const $b = matrixBody(frm);
  const out = [];
  $b.find("input.jos-field").each(function(){
    const hidden = !this.checked;   // ✅ reverse logic
    if (hidden){
      out.push({ section_fieldname: this.dataset.tab || "Main", fieldname: this.dataset.field, hide: 1 });
    }
  });

  $b.find("input.jos-tab").each(function(){
    const hidden = !this.checked;   // ✅ reverse logic
    if (hidden){
      out.push({ section_fieldname: this.dataset.tab || "Main", fieldname: null, hide: 1 });
    }
  });
  return out;
}

function draw(frm){
  const { role, dt } = pair(frm);
  if (!role || !dt){
    matrixBody(frm).html(`<div class="text-muted">Select Role and Doctype.</div>`);
    setButtons(frm, false);
    return;
  }
  Promise.all([
    frappe.call({method:"josfe.ui_controls.helpers.get_fields_and_sections",args:{doctype:dt}}),
    frappe.call({method:"josfe.ui_controls.helpers.get_role_rules",args:{role, doctype:dt}}),
    frappe.call({method:"josfe.ui_controls.helpers.factory_exists",args:{role, doctype:dt}})
  ]).then(([m,p,f])=>{
    const meta = m.message || {tabs:[], fields_by_tab:{}};
    const pre = p.message || {tabs:[], fields:[]};

    frm.doc.__isfactory = !!f.message;   // ✅ add this
    setButtons(frm, frm.doc.__isfactory);
    render(frm, meta, pre);
  });
}

function saveRules(frm, asFactory){
  const { role, dt } = pair(frm);
  if (!role || !dt) return frappe.msgprint("Select Role and Doctype first.");
  const payload = collect(frm);
  frappe.call({
    method:"josfe.ui_controls.helpers.save_role_rules",
    freeze:true,
    freeze_message: asFactory ? "Saving Factory Defaults…" : "Saving Active rules…",
    args:{ role, doctype:dt, payload: JSON.stringify(payload), as_factory: asFactory?1:0 }
  }).then(r=>{
    if (r.message?.factory_created) {
      frappe.msgprint("Factory Defaults saved (Active seeded).");
    } else {
      frappe.show_alert({message:"Rules saved", indicator:"green"});
    }
    draw(frm);
  });
}

function resetRules(frm){
  const { role, dt } = pair(frm);
  if (!role || !dt) return frappe.msgprint("Select Role and Doctype first.");
  frappe.confirm("Reset Active rules to Factory Defaults?", ()=>{
    frappe.call({
      method:"josfe.ui_controls.helpers.reset_role_rules",
      freeze:true, freeze_message:"Resetting…",
      args:{ role, doctype:dt }
    }).then(()=>{
      frappe.show_alert({message:"Reset done", indicator:"blue"});
      draw(frm);
    });
  });
}

frappe.ui.form.on("UI Settings", {
  refresh(frm){ ensureButtons(frm); draw(frm); },
  selected_role(frm){ draw(frm); }, selected_doctype(frm){ draw(frm); },
  role(frm){ draw(frm); }, doctype_name(frm){ draw(frm); },
});
