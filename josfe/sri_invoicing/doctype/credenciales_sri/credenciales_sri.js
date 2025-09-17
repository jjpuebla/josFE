frappe.ui.form.on('Credenciales SRI', {
  refresh(frm) {
    // quick sanity check:
    console.log('[josfe] credenciales_sri.js loaded for', frm.docname);
  }
});

(function () {
  const DT = "Credenciales SRI";
  const freeze = (msg) => frappe.dom.freeze(msg || __("Procesando…"));
  const unfreeze = () => frappe.dom.unfreeze();

  function humanizeError(e) {
    try {
      if (!e) return "Error desconocido";
      if (typeof e === "string") return e;
      if (e.message) return e.message;
      if (e._server_messages) {
        const arr = JSON.parse(e._server_messages);
        return arr.join("\n");
      }
      return JSON.stringify(e);
    } catch {
      return String(e);
    }
  }

  function render_actions(frm) {
    const fld = frm.fields_dict?.jos_sri_acciones_html;
    if (!fld || !fld.$wrapper) return;

    const html = `
      <div class="mt-3">
        <div class="form-group">
          <label class="control-label">${__("Acciones SRI")}</label>
          <div class="mb-2">
            <button type="button" class="btn btn-success w-25" id="jos_btn_save_convert">
              ${__("Validar Firma")}
            </button>
          </div>
          <div>
            <button type="button" class="btn btn-primary w-25" id="jos_btn_save_transmit">
              ${__("Probar transmisión")}
            </button>
          </div>
        </div>
      </div>
    `;
    fld.$wrapper.empty().html(html);

    const ensureSaved = async () => {
      if (!frm.doc.jos_firma_electronica) {
        frappe.msgprint(__("Sube el archivo .p12 en <b>jos_firma_electronica</b>."));
        frm.scroll_to_field("jos_firma_electronica");
        return false;
      }
      if (!frm.doc.name || frm.is_new()) {
        await frm.save();
      }
      return true;
    };

    // --- VALIDAR FIRMA ---
    fld.$wrapper.find("#jos_btn_save_convert").on("click", async () => {
      try {
        if (!(await ensureSaved())) return;

        // Create dialog for password input
        const dialog = new frappe.ui.Dialog({
          title: __("Ingrese la contraseña del certificado"),
          fields: [
            {
              label: __("Contraseña del certificado"),
              fieldname: "password",
              fieldtype: "Password"
              // IMPORTANT: no "reqd" here -> we handle validation ourselves (single popup)
            }
          ],
          primary_action_label: __("Validar"),
          primary_action(values) {
            // single validation, single popup
            const pwd = (values?.password || "").trim();
            if (!pwd) {
              frappe.msgprint(__("Debe ingresar la contraseña"));
              return; // stop here; no hidden form validation will run
            }

            // submit guard to avoid accidental double-triggers
            if (dialog.__submitting) return;
            dialog.__submitting = true;

            (async () => {
              try {
                freeze(__("Guardando y validando…"));

                const enc_password = btoa(pwd);

                const { message } = await frappe.call({
                  method: "josfe.sri_invoicing.core.signing.pem_tools.convertir_y_validar_seguro",
                  args: {
                    cred_name: frm.doc.name,
                    enc_password: enc_password
                  }
                });

                frappe.msgprint(message?.msg || __("Operación completada"));
                await frm.reload_doc();

              } catch (e) {
                frappe.msgprint(__("Error en conversión/validación: {0}", [humanizeError(e)]));
              } finally {
                dialog.__submitting = false;
                unfreeze();
                dialog.hide();
              }
            })();
          }
        });

        // Prevent Enter from triggering any hidden submit or bubbling to main form
        const pwInput = dialog.get_input("password");
        pwInput.on("keydown", (e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            dialog.get_primary_btn().trigger("click");
          }
        });

        // Extra safety: block wrapper-level Enter bubbling as well
        dialog.$wrapper.on("keydown", function (e) {
          if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
          }
        });

        dialog.show();
        // Focus password field for quick typing
        setTimeout(() => pwInput && pwInput.focus(), 50);

      } catch (e) {
        frappe.msgprint(__("Error preparando la validación: {0}", [humanizeError(e)]));
      }
    });

    // --- PROBAR TRANSMISIÓN --- 
    fld.$wrapper.find("#jos_btn_save_transmit").on("click", async () => {
      try {
        freeze(__("Guardando y transmitiendo…"));
        if (!(await ensureSaved())) return;

        const { message: m } = await frappe.call({
          method: "josfe.sri_invoicing.transmission.submitters.transmitir_dummy",
          args: { cred_name: frm.doc.name },
        });

        console.log("Dummy transmit response:", m);  // <---- ADD THIS

        if (!m) {
          frappe.msgprint(__("Sin respuesta del servidor."));
          return;
        }

        if (m.status === "error") {
          // transport-level failure (no communication with SRI)
          frappe.msgprint(__("❌ Fallo de comunicación con SRI"));
        } else {
          // communication succeeded, show estado + detalles
          const estado = m.estado || __("N/D");
          const detalles = (m.mensajes || []).join("<br>");
          frappe.msgprint(__("✅ Comunicación Exitosa<br>"));
        }

      } catch (e) {
        frappe.msgprint(__("Error transmitiendo a SRI: {0}", [humanizeError(e)]));
      } finally {
        unfreeze();
      }
    });
  } 

  frappe.ui.form.on(DT, {
    setup(frm) {},
    refresh(frm) {
      render_actions(frm);
      if (frm.is_new()) {
        frm.set_intro(__("Completa el .p12, luego usa los botones de Acciones SRI abajo."), true);
      } else {
        frm.set_intro(null);
      }
    },
    jos_firma_electronica(frm) {
      if (frm.doc.jos_firma_electronica) {
        // Prevent the sidebar from expanding
        frappe.utils.hide_sidebar();

        // Optionally scroll to actions HTML
        document.querySelector("div.layout-side-section").style.display = "none";

      }
    }
  });

  if (window.cur_frm?.doctype === DT) {
    cur_frm.trigger("refresh");
  }
})();
