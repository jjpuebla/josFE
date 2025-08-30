// apps/josfe/josfe/public/js/user_location/ui_badge.js
(() => {
  const CHANNEL = "josfe_establishment";
  const SIGNAL_KEY = "josfe_establishment_signal";

  const PALETTE = [
    "#2563eb", "#059669", "#7c3aed", "#ea580c", "#0ea5e9",
    "#16a34a", "#9333ea", "#dc2626", "#f59e0b", "#475569"
  ];

  const CUSTOM_COLORS = {
  "Sucursal Primax - A": "#b6ad06ff",   // red
  "Sucursal Mariscal - A": "#459eceff", // blue
  "Sucursal Guamaní - A": "#35c116ff", // blue
  // add more if needed
  };

  function hashStr(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++) {
      h = ((h << 5) - h) + s.charCodeAt(i);
      h |= 0;
    }
    return Math.abs(h);
  }

  function getWH() {
    return (frappe.boot?.jos_selected_establishment || "").trim();
  }

  function computeTexts(full) {
    // Expect labels like "003 - Sucursal Mariscal - A"
    const code = full.split(" - ")[0];
    if (code && code.length <= 8) return { short: code, title: full };
    return { short: full, title: full };
  }

  function draw(fullText) {
    const navbar = document.querySelector(".navbar .navbar-nav") || document.querySelector(".navbar");
    if (!navbar) return;

    const old = navbar.querySelector(".josfe-badge");
    if (old) old.remove();

    if (!fullText) return;

    const { short, title } = computeTexts(fullText);
    const color = CUSTOM_COLORS[fullText] || PALETTE[hashStr(fullText) % PALETTE.length];

    const badge = document.createElement("span");
    badge.className = "josfe-badge";
    Object.assign(badge.style, {
      background: color,
      color: "#fff",
      borderRadius: "9999px",
      padding: "2px 8px",
      fontWeight: "600",
      marginRight: "8px",
      display: "inline-block",
      whiteSpace: "nowrap",
      lineHeight: "18px",
      fontSize: "12px"
    });
    badge.textContent = short;
    badge.title = title;

    navbar.prepend(badge);
  }

  function refreshFromServerAndDraw() {
    return frappe
      .call("josfe.user_location.session.get_establishment_options")
      .then((r) => {
        const latest = (r.message?.selected || "").trim();
        if (latest) {
          frappe.boot.jos_selected_establishment = latest;
          draw(latest);
        } else {
          draw(""); // clear
        }
      })
      .catch(() => {});
  }

  // initial render: use boot then ensure freshness
  frappe.after_ajax(() => {
    const bootVal = getWH();
    if (bootVal) draw(bootVal);
    refreshFromServerAndDraw();
  });

  // re-render when navbar DOM changes (forms/pages can re-render navbar)
  const mo = new MutationObserver(() => {
    const wh = getWH();
    const navbar = document.querySelector(".navbar .navbar-nav") || document.querySelector(".navbar");
    if (navbar && !navbar.querySelector(".josfe-badge")) draw(wh);
  });
  mo.observe(document.body, { childList: true, subtree: true });

  // cross-tab live updates
  if ("BroadcastChannel" in window) {
    const bc = new BroadcastChannel(CHANNEL);
    bc.onmessage = (ev) => {
      if (ev?.data?.type === "changed") {
        refreshFromServerAndDraw();
        refreshActiveView();
      }
    };
  }

  window.addEventListener("storage", (ev) => {
    if (ev.key === SIGNAL_KEY) {
      refreshFromServerAndDraw();
      refreshActiveView();
    }
  });

  // helper: refresh current list or form if open
  function refreshActiveView() {
    if (cur_list && typeof cur_list.refresh === "function") {
      cur_list.refresh();
    }
    
  }

  // expose for picker to call immediately after save (optional)
  window.injectWarehouseBadge = () => draw(getWH());
})();
