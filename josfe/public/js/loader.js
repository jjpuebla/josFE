console.log("🧠 doctypes_loader.js initialized");

function loadScriptOnce(src) {
  if ([...document.scripts].some(s => s.src.includes(src))) {
    console.log("⏩ Already loaded:", src);
    return;
  }

  console.log("📥 Injecting script:", src);

  const script = document.createElement("script");
  script.src = src;
  script.defer = true;
  script.onload = () => console.log("✅ Loaded:", src);
  script.onerror = () => console.error("❌ Failed to load:", src);
  document.head.appendChild(script);
}

function getCurrentDoctype() {
  try {
    return cur_frm?.doctype || frappe._cur_route?.split("/")?.[1] || null;
  } catch {
    return null;
  }
}

function waitForDoctypeAndInject() {
  const doctype = getCurrentDoctype();
  if (!doctype) return setTimeout(waitForDoctypeAndInject, 200);

  console.log("📄 Detected Doctype:", doctype);

  const scriptMap = {
    Customer: [
      "/assets/josfe/js/phone_utils.js",
      "/assets/josfe/js/tax_id_utils.js"
    ],
    Supplier: [
      "/assets/josfe/js/phone_utils.js",
      "/assets/josfe/js/tax_id_utils.js"
    ],
    Contact: [
      "/assets/josfe/js/phone_utils.js"
    ],
    Company: [
      "/assets/josfe/js/tax_id_utils.js"
    ]
  };

  const scripts = scriptMap[doctype] || [];

  if (scripts.length === 0) {
    console.log("⚠️ No scripts to load for Doctype:", doctype);
    return;
  }

  scripts.forEach(loadScriptOnce);
}

// Trigger after page is fully loaded
frappe.after_ajax(() => {
  setTimeout(waitForDoctypeAndInject, 0);
});
