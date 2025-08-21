// apps/josfe/josfe/user_location/page/location_picker/location_picker.js
frappe.pages['location-picker'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'Selecciona tu Establecimiento',
    single_column: true
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

  const $select = $(page.body).find('#josfe-loc-select');
  const $btnConfirm = $(page.body).find('#josfe-confirm');
  const $btnClear = $(page.body).find('#josfe-clear');
  const $msg = $(page.body).find('#josfe-msg');

  let selected = null;

  function showMsg(text, isErr=false) {
    if (!text) return $msg.hide();
    $msg.text(text).css('color', isErr ? '#c0392b' : '#6c757d').show();
  }

  // log what boot thinks at load
  console.log("[josfe:picker] boot.jos_selected_establishment at load:", frappe.boot?.jos_selected_establishment ?? null);

  // load options
  showMsg('Cargando opciones...');
  frappe.call('josfe.user_location.session.get_establishment_options')
    .then((r) => {
      const msg = r.message || {};
      const whs = msg.warehouses || [];
      const allowConsolidado = !!msg.allow_consolidado;
      const preselected = msg.selected || null;

      whs.forEach((w) => {
        const opt = document.createElement('option');
        opt.value = w.name;
        opt.textContent = w.label || w.name;
        $select.append(opt);
      });

      if (allowConsolidado) {
        const opt = document.createElement('option');
        opt.value = "__CONSOLIDADO__";
        opt.textContent = "Consolidado";
        $select.append(opt);
      }

      if (preselected) {
        $select.val(preselected);
        selected = preselected;
        $btnConfirm.prop('disabled', false);
      }

      showMsg('');
    })
    .catch((e) => {
      console.error(e);
      showMsg('Error al cargar opciones.', true);
    });

  // selection change
  $select.on('change', function () {
    selected = this.value || null;
    console.log("[josfe:picker] user changed selection to:", selected);
    $btnConfirm.prop('disabled', !selected);
  });

  // confirm (no full reload)
  $btnConfirm.on('click', function () {
    if (!selected) return;
    console.log("[josfe:picker] confirming selection:", selected);

    frappe.call('josfe.user_location.session.set_selected_establishment', { warehouse: selected })
      .then((r) => {
        const val = (r.message || {}).selected || null;
        console.log("[josfe:picker] saved selection:", val);

        // 1) update boot in-memory so guards/forms pass immediately
        if (!frappe.boot) frappe.boot = {};
        frappe.boot.jos_selected_establishment = val;

        // 2) persist for new tabs
        try { localStorage.setItem("josfe_selected_establishment", val || ""); } catch {}

        frappe.show_alert('Establecimiento seleccionado');

        // go to Desk home (or any target)
        frappe.set_route("");
      })
      .catch((e) => {
        console.error(e);
        showMsg('No se pudo guardar la selección.', true);
      });
  });
  
  // clear (local, not saved)
  $btnClear.on('click', function () {
    $select.val('');
    selected = null;
    $btnConfirm.prop('disabled', true);
    console.log("[josfe:picker] cleared pending selection (not saved)");
  });
};
