// apps/josfe/josfe/public/js/user_location/ui_badge.js
(() => {
  if (window.__JOSFE_BADGE_INSTALLED__) return;
  window.__JOSFE_BADGE_INSTALLED__ = true;

  const DEBUG = false;
  const log = (...a) => DEBUG && console.log("[josfe:badge]", ...a);

  const STORAGE_KEY = "josfe_selected_establishment";
  const NAV_SELECTORS = [".navbar-home", ".navbar .navbar-brand", ".navbar"];

  const STYLE_MAP = {
    "Sucursal Guamaní - A": { letter: "G", color: "#27ae60" },
    "Sucursal Mariscal - A": { letter: "M", color: "#f1c40f" },
    "Sucursal Primax - A":  { letter: "P", color: "#3498db" },
    "__CONSOLIDADO__":      { letter: "T", color: "#2c3e50" }
  };

  // Public mini-API
  window.josfeBadge = {
    setStyleMap(obj) {
      Object.assign(STYLE_MAP, obj || {});
      rerender();
    },
    refresh: rerender
  };

  function hexToRgba(hex, alpha = 0.16) {
    if (typeof hex !== "string" || !/^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(hex)) {
      return `rgba(127,140,141,${alpha})`;
    }
    let r, g, b;
    if (hex.length === 4) {
      r = parseInt(hex[1] + hex[1], 16);
      g = parseInt(hex[2] + hex[2], 16);
      b = parseInt(hex[3] + hex[3], 16);
    } else {
      r = parseInt(hex.slice(1,3), 16);
      g = parseInt(hex.slice(3,5), 16);
      b = parseInt(hex.slice(5,7), 16);
    }
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function ensureStyleTag() {
    const ID = "josfe-badge-style";
    if (document.getElementById(ID)) return;
    const s = document.createElement("style");
    s.id = ID;
    s.textContent = `
      .jos-badge {
        display:inline-flex; align-items:center; justify-content:center;
        font-weight:700; font-size:13px; line-height:1;
        width:22px; height:22px; border-radius:6px; margin-left:6px;
        user-select:none; box-shadow:0 1px 2px rgba(0,0,0,.08);
        color: var(--jos-badge-fg, #7f8c8d);
        background: var(--jos-badge-bg-soft, rgba(127,140,141,.14));
      }
    `;
    document.head.appendChild(s);
  }

  function getSelection() {
    try {
      const localVal = (localStorage.getItem(STORAGE_KEY) || "").trim();
      const bootVal = (frappe?.boot?.jos_selected_establishment || "").trim();

      if (localVal) return localVal;
      if (bootVal) return bootVal;
      return null;
    } catch {
      return null;
    }
  }


  function findNavbarTarget() {
    for (const sel of NAV_SELECTORS) {
      const el = document.querySelector(sel);
      if (el) return el;
    }
    return null;
  }

  function makeBadge(letter, color, titleText) {
    ensureStyleTag();
    const wrap = document.createElement("span");
    wrap.id = "jos-warehouse-icon";

    const badge = document.createElement("span");
    badge.className = "jos-badge";
    badge.title = titleText || letter;
    badge.style.setProperty("--jos-badge-fg", color || "#7f8c8d");
    badge.style.setProperty("--jos-badge-bg-soft", hexToRgba(color || "#7f8c8d", 0.16));
    badge.textContent = letter;

    wrap.appendChild(document.createTextNode("\u00A0"));
    wrap.appendChild(badge);
    return wrap;
  }

  function injectBadge(selected) {
    if (!selected) return false;

    const target = findNavbarTarget();
    if (!target) return false;

    // Always rebuild to avoid stale letter/color after a switch
    const existing = document.getElementById("jos-warehouse-icon");
    if (existing?.parentNode) existing.parentNode.removeChild(existing);

    const map = STYLE_MAP[selected] || { letter: "?", color: "#7f8c8d" };
    const el = makeBadge(map.letter, map.color, selected);
    target.appendChild(el);

    document.body.dataset.establishment = selected;
    log("badge injected:", map.letter, "for", selected);
    return true;
  }

  let badgeDone = false;

  function work() {
    const selected = getSelection();
    if (!badgeDone) badgeDone = injectBadge(selected);
    return badgeDone;
  }

  function rerender() {
    const old = document.getElementById("jos-warehouse-icon");
    if (old?.parentNode) old.parentNode.removeChild(old);
    badgeDone = false;
    work();
  }

  function connectDomObserver() {
    const observer = new MutationObserver(() => {
      if (work()) observer.disconnect();
    });
    observer.observe(document.documentElement || document.body, { childList: true, subtree: true });
    window.addEventListener("pagehide", () => observer.disconnect(), { once: true });
  }

  function connectSelectionHooks() {
    const origSetItem = localStorage.setItem?.bind(localStorage);
    if (origSetItem) {
      try {
        localStorage.setItem = function (k, v) {
          const r = origSetItem(k, v);
          if (k === STORAGE_KEY) rerender();
          return r;
        };
      } catch (err) {
        log("setItem override failed", err);
      }
    }

    window.addEventListener("storage", (e) => {
      if (e.key !== STORAGE_KEY) return;

      const el = document.getElementById("jos-warehouse-icon");
      if (el?.parentNode) el.parentNode.removeChild(el);
      badgeDone = false;
      rerender();
    });
  }

  frappe.after_ajax(() => {
    if (!work()) {
      connectDomObserver();
      connectSelectionHooks();

      // Failsafe: ensure a re-run once the next frame paints
      requestAnimationFrame(() => rerender());
    } else {
      connectSelectionHooks();
    }
  });
})();
