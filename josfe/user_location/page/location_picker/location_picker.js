// apps/josfe/josfe/user_location/page/location_picker/location_picker.js
frappe.pages["location-picker"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Selecciona tu Establecimiento",
    single_column: true,
  });

  const tpl = `
    <div id="josfe-loc-container" style="max-width:720px;padding:12px;">
      <p class="text-muted" style="margin:0 0 12px 0;">
        Esta selección aplica a toda tu sesión (impacta facturación electrónica).
      </p>

      <div class="form-group">
        <label for="josfe-loc-select"><strong>Establecimiento</strong></label>
        <select id="josfe-loc-select" class="form-control">
          <option value="">— Selecciona —</option>
        </select>
      </div>

      <div style="margin-top:16px;display:flex;gap:8px;">
        <button id="josfe-confirm" class="btn btn-primary" disabled>Confirmar</button>
        <button id="josfe-clear" class="btn btn-default">Limpiar</button>
      </div>

      <div id="josfe-msg" class="text-muted" style="margin-top:12px;display:none;"></div>
    </div>
  `;
  $(page.body).html(tpl);

  const $select = $(page.body).find("#josfe-loc-select");
  const $btnConfirm = $(page.body).find("#josfe-confirm");
  const $btnClear = $(page.body).find("#josfe-clear");
  const $msg = $(page.body).find("#josfe-msg");

  let selected = null;

  function showMsg(text, isErr = false) {
    if (!text) return $msg.hide();
    $msg.text(text).css("color", isErr ? "#c0392b" : "#6c757d").show();
  }

  // log boot value at load (debug aid)
  // eslint-disable-next-line no-console
  console.log(
    "[josfe:picker] boot.jos_selected_establishment at load:",
    frappe.boot?.jos_selected_establishment ?? null
  );

  // Load options from server
  showMsg("Cargando opciones...");
  frappe
    .call("josfe.user_location.session.get_establishment_options")
    .then((r) => {
      const msg = r.message || {};
      const whs = msg.warehouses || [];
      const allowConsolidado = !!msg.allow_consolidado;
      const preselected = msg.selected || null;

      whs.forEach((w) => {
        const opt = document.createElement("option");
        opt.value = w.name;
        opt.textContent = w.label || w.name;
        $select.append(opt);
      });

      if (allowConsolidado) {
        const opt = document.createElement("option");
        opt.value = "__CONSOLIDADO__";
        opt.textContent = "Consolidado";
        $select.append(opt);
      }

      if (preselected) {
        $select.val(preselected);
        selected = preselected;
        $btnConfirm.prop("disabled", false);
      }

      showMsg("");
    })
    .catch((e) => {
      // eslint-disable-next-line no-console
      console.error(e);
      showMsg("Error al cargar opciones.", true);
    });

  // Handle selection change
  $select.on("change", function () {
    selected = this.value || null;
    // eslint-disable-next-line no-console
    console.log("[josfe:picker] user changed selection to:", selected);
    $btnConfirm.prop("disabled", !selected);
  });

  // Confirm (no full reload — deterministic navigation)
  $btnConfirm.on("click", function () {
    if (!selected) return;

    // eslint-disable-next-line no-console
    console.log("[josfe:picker] confirming selection:", selected);

    // Avoid double click during save
    $btnConfirm.prop("disabled", true);
    $btnClear.prop("disabled", true);
    showMsg("Guardando selección...");

    $btnConfirm.prop("disabled", true);
    $btnClear.prop("disabled", true);
    showMsg("Guardando selección...");

    frappe.call('josfe.user_location.session.set_selected_establishment', { warehouse: selected })
      .then((r) => {
        const val = (r.message || {}).selected || null;
        console.log("[josfe:picker] saved selection:", val);

        frappe.boot.jos_selected_establishment = val;
        try {
          localStorage.setItem("josfe_selected_establishment", val || "");

          // 🔁 fire synthetic storage event in this tab (helps badge rerender instantly)
          window.dispatchEvent(new StorageEvent("storage", {
            key: "josfe_selected_establishment",
            newValue: val
          }));
        } catch {}
        if (typeof window.josfeSetEstablishment === "function") {
          try { window.josfeSetEstablishment(val); } catch {}
        }

        frappe.show_alert("Establecimiento seleccionado");
        frappe.set_route("app");  // ✅ safe route
      })
      .catch((e) => {
        console.error(e);
        showMsg("No se pudo guardar la selección.", true);
      })
      .then(() => {  // ✅ cleanup here
        $btnConfirm.prop("disabled", !selected);
        $btnClear.prop("disabled", false);
      });

  });

  // Clear (local, not saved)
  $btnClear.on("click", function () {
    $select.val("");
    selected = null;
    $btnConfirm.prop("disabled", true);
    // eslint-disable-next-line no-console
    console.log("[josfe:picker] cleared pending selection (not saved)");
  });
};
