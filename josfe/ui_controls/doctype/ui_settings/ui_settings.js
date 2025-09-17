// josfe/ui_controls/ui_settings.js
console.log("✅ ui_settings.js (production)");

// ---------- utils ----------
const esc = s => (s || "").replace(/[&<>"']/g, m => ({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
}[m]));

// prefer transient selectors first
const pair = frm => ({
  role: frm.doc.selected_role || frm.doc.role || "",
  dt:   frm.doc.selected_doctype || frm.doc.doctype_name || ""
});

// ---------- buttons ----------
function clearAndBuildButtons(frm, hasFactory) {
  frm.clear_custom_buttons();

  // 1) Save Active (only if Factory exists)
  if (hasFactory) {
    frm.add_custom_button(
      __("Save Active"),
      () => saveRules(frm, 0),
      "UI Settings"
    )
      .addClass("btn-primary")
      .css("font-weight", "bold");
  }

  // 2) Reset to Factory Defaults (only if Factory exists)
  if (hasFactory) {
    frm.add_custom_button(
      __("Reset to Factory Defaults"),
      () => resetRules(frm),
      "UI Settings"
    );
  }

  // 3) Save as Factory Defaults (always last)
  if (!hasFactory) {
    frm.add_custom_button(
      __("Save as Factory Defaults"),
      () => saveRules(frm, 1),
      "UI Settings"
    );
  } else {
    frm.add_custom_button(
      __("Save as Factory Defaults"),
      () => {
        frappe.confirm(
          "Are you sure you want to overwrite Factory Defaults?",
          () => saveRules(frm, 1)
        );
      },
      "UI Settings"
    );
  }
}


function hideNativeSaveCompletely(frm) {
  frm.disable_save();
  frm.page.wrapper.find(".standard-actions .primary-action").hide();
  frm.page.set_primary_action("", null);
}

// ---------- matrix container ----------
function matrixBody(frm){
  let $b = frm.$wrapper.find("#jos-ui-matrix-body");
  if (!$b.length){
    const html = `<div id="jos-ui-matrix" style="margin-top:8px">
      <div id="jos-factory-note" style="margin-bottom:6px; font-size:0.9em;"></div>
      <div style="margin-bottom:6px; font-size:0.9em;">
        <span style="color:green; font-weight:bold;">■ Mandatory</span> 
        <span style="background:#ffa726;color:white;font-weight: bold;padding:2px 4px;border-radius:4px">■ Core Hidden</span>
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
function render(frm, meta, pre, hasFactory) {
  const $b = matrixBody(frm);
  const hiddenTabs   = new Set(pre?.tabs   || []);
  const hiddenFields = new Set(pre?.fields || []);

  const orangeStyle = "background:#ffa726;color:white;font-weight: bold;padding:2px 4px;border-radius:4px";
  const orangeField = "background:#ffa726;color:white;font-weight: bold;padding:2px 4px;border-radius:4px";

  let html = "";
  (meta.tabs || []).forEach(t => {
    const tfn = t.fieldname || "Main";
    const tlabel = t.label || tfn;
    const metaHiddenTab = !!t.hidden;

    const containsMandatory = (meta.fields_by_tab[tfn] || []).some(f => f.reqd);
    console.log("[UI Settings] tab check", { tab: tfn, containsMandatory, metaHiddenTab, hasFactory });

    // Header row (no tab checkbox anymore)
    html += `<div class="card" style="margin:8px 0"><div class="card-body" style="padding:10px 12px">
      <div class="flex" style="justify-content:space-between;align-items:center;margin-bottom:6px">
        <div>
          <b style="${metaHiddenTab ? orangeStyle : ""}">${esc(tlabel)}</b>
          <span class="text-muted">(${esc(tfn)})</span>
        </div>
        <div style="display:flex; align-items:center; gap:12px">
          <a href="#" class="jos-toggle-tab" data-tab="${esc(tfn)}" data-mandatory="${containsMandatory ? 1 : 0}" style="font-size:12px">
            Select All
          </a>
        </div>
      </div><div class="row">`;

    (meta.fields_by_tab[tfn] || []).forEach(f => {
      const metaHidden = !!f.hidden;
      const isHidden   = hiddenFields.has(f.fieldname) || metaHidden;
      const checked    = isHidden ? "" : "checked";
      let disabled = "", style = "", title = "";

      if (f.reqd) {
        html += `<div class="col-sm-4" style="margin-bottom:6px">
          <div title="Mandatory field"
              style="display:inline-block;padding:6px 10px;border-radius:6px;background:#2e7d32;color:#fff;font-weight:600;">
            ${esc(f.label)} <span class="text-muted" style="color:#ccc !important;">(${esc(f.fieldname)})</span>
          </div>
        </div>`;
        return;
      } else if (metaHidden) {
        style = orangeField;
        disabled = hasFactory ? "disabled" : "";
        title = hasFactory ? 'title="Core hidden (locked)"' : 'title="Core hidden"';
      }

      html += `<div class="col-sm-4" style="margin-bottom:6px; word-break:break-word; white-space:normal">
        <label style="${style}; display:block" ${title}>
          <input type="checkbox" class="jos-field" data-tab="${esc(tfn)}" data-field="${esc(f.fieldname)}" ${checked} ${disabled}>
          <span style="margin-left:6px">${esc(f.label)}</span>
          <span class="text-muted" style="color:#777 !important;">(${esc(f.fieldname)})</span>
        </label>
      </div>`;
    });

    html += `</div></div></div>`;
  });

  $b.html(html);

  // --- Select All / Deselect All link handler ---
  $b.find(".jos-toggle-tab").off("click").on("click", function(e){
    e.preventDefault();
    const tab = $(this).data("tab");
    const $fields = $b.find(`.jos-field[data-tab="${tab}"]:not(:disabled)`);
    const hasMandatory = $(this).data("mandatory") === 1;

    const allChecked = $fields.length && $fields.filter(":checked").length === $fields.length;

    console.log("[UI Settings] toggle clicked", {
      tab,
      totalFields: $fields.length,
      checkedFields: $fields.filter(":checked").length,
      allChecked,
      hasMandatory,
      toggleLink: this
    });

    if (allChecked) {
      if (hasMandatory) {
        frappe.msgprint("This tab contains mandatory fields and cannot be fully hidden.");
        console.warn("[UI Settings] ❌ Blocked Deselect All on mandatory tab", tab);
        return;
      }
      // Deselect all
      $fields.prop("checked", false);
      $(this).text("Select All");
      console.log("[UI Settings] ✅ Deselect All in tab", tab);
    } else {
      // Select all
      $fields.prop("checked", true);
      $(this).text("Deselect All");
      console.log("[UI Settings] ✅ Select All in tab", tab);
    }
  });
}


// ---------- collect (unchecked ⇒ hidden) ----------
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
function draw(frm) {
  const { role, dt } = pair(frm);
  const $note = frm.$wrapper.find("#jos-factory-note");

  if (!role || !dt) {
    matrixBody(frm).html(`<div class="text-muted">Select Role and Doctype.</div>`);
    clearAndBuildButtons(frm, false);
    $note.empty();
    // unlock when pair not set
    frm.set_df_property("role", "read_only", 0);
    frm.set_df_property("doctype_name", "read_only", 0);
    return;
  }

  Promise.all([
    frappe.call({ method: "josfe.ui_controls.helpers.get_fields_and_sections", args: { doctype: dt } }),
    frappe.call({ method: "josfe.ui_controls.helpers.get_role_rules", args: { role, doctype: dt } }),
    frappe.call({ method: "josfe.ui_controls.helpers.factory_exists", args: { role, doctype: dt } })
  ]).then(([m, p, f]) => {
    const meta       = m.message || { tabs: [], fields_by_tab: {} };
    const pre        = p.message || { tabs: [], fields: [], inactive: false };
    const hasFactory = !!f.message;

    console.log("[UI Settings] draw()", { role, dt, hasFactory, pre });

    // --- if inactive, prepend a warning but KEEP rendering the matrix ---
    if (pre.inactive) {
      matrixBody(frm).prepend(`<div class="text-danger" style="margin-bottom:6px">
        ⚠️ This UI Setting is inactive because role <b>${esc(role)}</b> has no permission for <b>${esc(dt)}</b>.<br>
        <span style="color:red">Safe to delete or repurpose.</span>
      </div>`);
      clearAndBuildButtons(frm, false);

      // unlock so admin can fix or delete
      frm.set_df_property("role", "read_only", 0);
      frm.set_df_property("doctype_name", "read_only", 0);

      $note.empty();
    } else {
    clearAndBuildButtons(frm, hasFactory);

    // lock/unlock pair strictly from hasFactory
    frm.set_df_property("role", "read_only", hasFactory ? 1 : 0);
    frm.set_df_property("doctype_name", "read_only", hasFactory ? 1 : 0);

    if (hasFactory) {
      $note.html(
        `✔ Factory Defaults are set for <b>${esc(role)}</b> + <b>${esc(dt)}</b>.<br>` +
        `<span style="color:green">You can now save <b>Active</b> rules on top.</span>`
      ).css({ color: "blue" });
    } else {
      $note.html(
        `✖ Factory Defaults not yet set for <b>${esc(role)}</b> + <b>${esc(dt)}</b>.<br>` +
        `<span style="color:red">Saving now will create Factory Defaults (baseline).</span>`
      ).css({ color: "red" });
      }
    }

    // always render matrix so saved hides show correctly
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
    args: { role, doctype: dt, payload: JSON.stringify(payload), as_factory: asFactory ? 1 : 0 }
  }).then(r => {
    try {
      localStorage.setItem("josfe_ui_controls_update", JSON.stringify({ ts: Date.now(), doctype: dt, role }));
      console.log("[UI Settings] broadcast set", { dt, role });
    } catch(e) { console.warn("broadcast failed", e); }

    if (r.message?.factory_created) {
      console.log("[UI Settings] Factory Defaults saved & Active seeded", r.message);
      frappe.msgprint("Factory Defaults saved (Active seeded).");
    } else {
      console.log("[UI Settings] Active rules saved", r.message);
      frappe.show_alert({ message: "Active rules saved", indicator: "green" });
    }
    draw(frm); // re-check factory_exists and re-render banner + lock fields
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
    }).then(()=> {
      frappe.show_alert({ message: "Reset done", indicator: "blue" });
      draw(frm);
    });
  });
}

// ---------- bindings ----------
frappe.ui.form.on("UI Settings", {
  setup(frm) {
    frm.set_query("doctype_name", () => {
      const role = frm.doc.role || frm.doc.selected_role || "";
      console.log("[UI Settings] get_query for doctype_name → role:", role);
      if (role) {
        return {
          query: "josfe.ui_controls.helpers.get_doctypes_for_role",
          filters: { role }
        };
      }
      return {};
    });
  },

  refresh(frm) {
    hideNativeSaveCompletely(frm);
    draw(frm);
  },

  role(frm) {
    draw(frm);
    frm.refresh_field("doctype_name");
  },

  selected_role(frm) {
    draw(frm);
    frm.refresh_field("doctype_name");
  },

  selected_doctype(frm){ draw(frm); },
  doctype_name(frm){ draw(frm); },
});