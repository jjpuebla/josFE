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
  const CHANNEL = "josfe_establishment";
  const SIGNAL_KEY = "josfe_establishment_signal";

  function showMsg(text, isErr = false) {
    if (!text) return $msg.hide();
    $msg.text(text).css("color", isErr ? "#c0392b" : "#6c757d").show();
  }

  // Load options
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
      console.error(e);
      showMsg("Error al cargar opciones.", true);
    });

  $select.on("change", function () {
    selected = this.value || null;
    $btnConfirm.prop("disabled", !selected);
  });

  // Confirm → save, update boot, broadcast to other tabs, update badge, go home
  $btnConfirm.on("click", function () {
    if (!selected) return;

    $btnConfirm.prop("disabled", true);
    $btnClear.prop("disabled", true);
    showMsg("Guardando selección...");

    frappe
      .call("josfe.user_location.session.set_selected_warehouse", {
        warehouse: selected,
        set_user_permission: 0,
      })
      .then((r) => {
        const val = (r.message || {}).warehouse || selected;

        // Mirror in this tab
        frappe.boot.jos_selected_establishment = val;

        // BroadcastChannel
        try {
          if ("BroadcastChannel" in window) {
            const bc = new BroadcastChannel(CHANNEL);
            bc.postMessage({ type: "changed", value: val, at: Date.now() });
          }
        } catch {}

        // localStorage signal (fallback, signal only)
        try {
          localStorage.setItem(
            SIGNAL_KEY,
            JSON.stringify({ value: val, at: Date.now() })
          );
        } catch {}

        // Update UI
        if (typeof window.injectWarehouseBadge === "function") {
          window.injectWarehouseBadge();
        }
        frappe.show_alert("Establecimiento seleccionado");
        frappe.set_route("desk");
      })
      .catch((e) => {
        console.error(e);
        showMsg("No se pudo guardar la selección.", true);
      })
      .then(() => {
        $btnConfirm.prop("disabled", !selected);
        $btnClear.prop("disabled", false);
      });
  });

  $btnClear.on("click", function () {
    $select.val("");
    selected = null;
    $btnConfirm.prop("disabled", true);
  });
};
