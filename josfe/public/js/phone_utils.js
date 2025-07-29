frappe.provide("josfe");

josfe.setupPhoneMaskingAndWhatsapp = function (frm) {
    console.log("📋 Form loaded for:", frm.doctype);

    const grid = frm.fields_dict.custom_jos_telefonos?.grid;
    if (!grid?.wrapper) {
        console.warn("⚠️ Grid or wrapper not found");
        return;
    }

    const $wrapper = $(grid.wrapper);
    console.log("✅ Grid 'custom_jos_telefonos' is ready");

    // 📞 Mask phone number
    $wrapper.on("input", 'input[data-fieldname="phone"]', function (e) {
        const $input = $(e.target);
        const raw = e.target.value.replace(/\D/g, "");
        e.target.value = formatWithMask(raw);
        toggleWhatsapp($input, raw);
    });

    $wrapper.on("focus", 'input[data-fieldname="phone"]', function (e) {
        const raw = e.target.value.replace(/\D/g, "");
        if (!raw) e.target.value = getDynamicMask("");
        e.target.setSelectionRange(0, 0);
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

    // ✅ WhatsApp checkbox validation — prevent mouse and keyboard check
    function validateWhatsappToggle(e, $checkbox) {
        const $row = $checkbox.closest(".grid-row");
        const $phone = $row.find('input[data-fieldname="phone"]');
        const phone = ($phone.val() || "").replace(/\D/g, "");
        const isValid = phone.startsWith("09");

        if (!isValid) {
            e.preventDefault();
            frappe.msgprint("❌ Solo teléfonos que comienzan con <b>09</b> pueden marcar WhatsApp.");
            $checkbox.prop("checked", false).prop("disabled", true).css("outline", "2px solid red");
            return false;
        }

        $checkbox.prop("disabled", false).css("outline", "2px solid green");
        return true;
    }

    // 🖱️ Block invalid WhatsApp check via mouse
    $wrapper.on("mousedown", 'input[data-fieldname="jos_whatsapp"]', function (e) {
        const $checkbox = $(e.target);
        validateWhatsappToggle(e, $checkbox);
    });

    // ⌨️ Block invalid WhatsApp check via keyboard
    $wrapper.on("keydown", 'input[data-fieldname="jos_whatsapp"]', function (e) {
        if (e.key === " " || e.key === "Spacebar") {
            const $checkbox = $(e.target);
            validateWhatsappToggle(e, $checkbox);
        }
    });

    // 🧼 Clean outline on focus
    $wrapper.on("focus", 'input[data-fieldname="jos_whatsapp"]', function (e) {
        $(e.target).css("outline", "none");
    });

    // ▶️ Initial state for existing rows
    grid.grid_rows.forEach(row => {
        const $input = $(row.row.wrapper).find('input[data-fieldname="phone"]');
        const raw = $input.val()?.replace(/\D/g, "") || "";
        toggleWhatsapp($input, raw);
    });

    // === Utilities ===
    function toggleWhatsapp($input, raw) {
        const isMobile = raw.startsWith("09");
        const $row = $input.closest(".grid-row");
        const $wa = $row.find('input[data-fieldname="jos_whatsapp"]');

        if ($wa.length) {
            $wa.prop("disabled", !isMobile);
            if (!isMobile) $wa.prop("checked", false);
        }
    }

    function getDynamicMask(digits) {
        if (digits.startsWith("09")) return "___-___-____";
        if (digits.startsWith("0") && digits[1] >= "2" && digits[1] <= "8") return "___-___-___";
        if (digits[0] >= "2" && digits[0] <= "9") return "___-____";
        return "___-___-____";
    }

    function formatWithMask(digits) {
        const mask = getDynamicMask(digits);
        let result = "", i = 0;
        for (let char of mask) {
            result += char === "_" ? digits[i++] || "_" : char;
        }
        return result;
    }
};
