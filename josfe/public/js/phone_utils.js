console.log("✅ josfe/phone_utils.js loaded (wrapper normalized, no setTimeout)");

(function () {
  // Keep track of which DOM nodes we've bound to
  const BOUND = new WeakSet();

  // --- Utils --------------------------------------------------------------

  function getWrapperNode(grid) {
    // Normalize Frappe Grid wrapper to a real DOM Node
    if (!grid) return null;
    const w = grid.wrapper;

    // If it's already a DOM element
    if (w && w.nodeType === 1) return w;

    // jQuery-like objects
    if (w && typeof w === "object") {
      if (w[0] && w[0].nodeType === 1) return w[0];
      if (typeof w.get === "function") {
        const el = w.get(0);
        if (el && el.nodeType === 1) return el;
      }
    }

    // Some older grid versions also expose .parent or .$wrapper; try them
    if (grid.$wrapper && grid.$wrapper[0]?.nodeType === 1) return grid.$wrapper[0];
    if (grid.parent && grid.parent[0]?.nodeType === 1) return grid.parent[0];

    return null;
  }

  function getDynamicMask(digits) {
    if (digits.startsWith("09")) return "___-___-____"; // EC mobile
    if (digits.length >= 2 && digits.startsWith("0") && digits[1] >= "2" && digits[1] <= "8")
      return "___-___-___";                             // EC landline
    if (digits[0] >= "2" && digits[0] <= "9") return "___-____"; // Intl short
    return "___-___-____";
  }

  function formatWithMask(digits) {
    const mask = getDynamicMask(digits);
    let result = "", i = 0;
    for (let ch of mask) result += ch === "_" ? (digits[i++] || "_") : ch;
    return result;
  }

  function toggleWhatsapp($input, raw) {
    const isMobile = raw.startsWith("09");
    const $row = $input.closest(".grid-row");
    const $wa = $row.find('input[data-fieldname="jos_whatsapp"]');
    if (!$wa.length) return;
    if (!isMobile) {
      $wa.prop("checked", false).prop("disabled", true).css("outline", "2px solid red");
    } else {
      $wa.prop("disabled", false).css("outline", "2px solid green");
    }
  }

  function initRow($row) {
    const $input = $row.find('input[data-fieldname="phone"]');
    if (!$input.length) return;
    const raw = ($input.val() || "").replace(/\D/g, "");
    $input.val(formatWithMask(raw));
    toggleWhatsapp($input, raw);
  }

  // --- Binding ------------------------------------------------------------

  function attachDelegates(node) {
    const $wrapper = $(node);

    // Phone typing
    $wrapper.on("input", 'input[data-fieldname="phone"]', function (e) {
      const $inp = $(e.target);
      const raw = e.target.value.replace(/\D/g, "");
      e.target.value = formatWithMask(raw);
      toggleWhatsapp($inp, raw);
    });

    $wrapper.on("focus", 'input[data-fieldname="phone"]', function (e) {
      const raw = e.target.value.replace(/\D/g, "");
      if (!raw) e.target.value = getDynamicMask("");
      try { e.target.setSelectionRange(0, 0); } catch {}
    });

    $wrapper.on("blur", 'input[data-fieldname="phone"]', function (e) {
      const val = e.target.value.replace(/[-_]/g, "").trim();
      if (!val) e.target.value = "";
    });

    $wrapper.on("keydown", 'input[data-fieldname="phone"]', function (e) {
      if (e.key === "Backspace") {
        e.preventDefault();
        let raw = e.target.value.replace(/\D/g, "");
        raw = raw.slice(0, -1);
        e.target.value = formatWithMask(raw);
      }
    });

    // WhatsApp gating (must start with 09)
    function validateWhatsappToggle(e, $checkbox) {
      const $row = $checkbox.closest(".grid-row");
      const $phone = $row.find('input[data-fieldname="phone"]');
      const phone = ($phone.val() || "").replace(/\D/g, "");
      const ok = phone.startsWith("09");
      if (!ok) {
        e.preventDefault();
        frappe.msgprint("❌ Solo teléfonos que comienzan con <b>09</b> pueden marcar WhatsApp.");
        $checkbox.prop("checked", false).prop("disabled", true).css("outline", "2px solid red");
        return false;
      }
      $checkbox.prop("disabled", false).css("outline", "2px solid green");
      return true;
    }

    $wrapper.on("click", 'input[data-fieldname="jos_whatsapp"]', function (e) {
      validateWhatsappToggle(e, $(e.target));
    });

    $wrapper.on("keydown", 'input[data-fieldname="jos_whatsapp"]', function (e) {
      if (e.key === " " || e.key === "Spacebar") validateWhatsappToggle(e, $(e.target));
    });
  }

  function observeGrid(node) {
    // Initialize existing rows
    $(node).find(".grid-row").each((_, el) => initRow($(el)));

    // Watch for new rows
    const mo = new MutationObserver(muts => {
      for (const m of muts) {
        for (const n of m.addedNodes || []) {
          if (n.nodeType === 1) {
            const $n = $(n);
            if ($n.hasClass("grid-row")) initRow($n);
            $n.find(".grid-row").each((_, el) => initRow($(el)));
          }
        }
      }
    });
    mo.observe(node, { childList: true, subtree: true });

    // Save a handle for debugging/cleanup if needed
    node.__josfe_phone_mo = mo;
  }

  function bindGrid(grid) {
    const node = getWrapperNode(grid);
    if (!node) {
      console.warn("⚠️ phone_utils: grid wrapper is not a DOM node yet, skipping.");
      return false;
    }
    if (BOUND.has(node)) return true;

    console.log("📞 Binding phone mask on grid:", grid.df?.fieldname || "(unknown)");
    attachDelegates(node);
    observeGrid(node);
    BOUND.add(node);
    return true;
  }

  function bindForForm(frm) {
    if (!frm) return;
    const t1 = frm.fields_dict?.custom_jos_telefonos?.grid; // Customer/Supplier
    if (t1) bindGrid(t1);
    const t2 = frm.fields_dict?.phone_nos?.grid;            // Contact
    if (t2) bindGrid(t2);
  }

  // Hook into all three doctypes
  ["Customer", "Supplier", "Contact"].forEach(dt => {
    frappe.ui.form.on(dt, {
      onload_post_render(frm) {
        bindForForm(frm);
      },
      refresh(frm) {
        bindForForm(frm);
      }
    });
  });

  // Safety: also try after ajax when landing directly on a form
  frappe.after_ajax(() => {
    if (window.cur_frm && ["Customer", "Supplier", "Contact"].includes(cur_frm.doctype)) {
      bindForForm(cur_frm);
    }
  });
})();
