// apps/josfe/josfe/public/js/user_location/user_menu.js
(() => {
  const LABEL = "Cambia Sucursal";
  const ID = "josfe-change-establishment";
  const DEBUG = false;
  const log = (...a) => DEBUG && console.log("[josfe:user_menu]", ...a);

  // Keep STORAGE_KEY consistent with ui_badge.js
  const STORAGE_KEY = "josfe_selected_establishment";

  // Optional mini-helper: allow any selector page to set & refresh in one call
  // Usage from your location-picker: window.josfeSetEstablishment("Sucursal Guamaní - A")
  window.josfeSetEstablishment = function (newWarehouse) {
    try {
      localStorage.setItem(STORAGE_KEY, newWarehouse);
      // Immediate UI sync without relying on other hooks
      window.josfeBadge?.refresh?.();
      log("josfeSetEstablishment() set & refreshed:", newWarehouse);
    } catch (err) {
      console.error("[josfe:user_menu] josfeSetEstablishment error:", err);
    }
  };

  function makeItem(onclick) {
    const li = document.createElement("li");
    li.role = "presentation";
    const a = document.createElement("a");
    a.id = ID;
    a.role = "menuitem";
    a.href = "javascript:void(0)";
    // Use innerHTML to style; no need to set textContent as well
    a.innerHTML = `<span style="font-weight: 600; margin-left: 6px;">${LABEL}</span>`;

    a.addEventListener("click", (e) => {
      e.preventDefault();
      try { onclick?.(); } catch (err) { console.error(err); }
    });
    li.appendChild(a);
    return li;
  }

  function onClick() {
    log("clicked:", LABEL);

    // One-time storage listener: when location-picker writes STORAGE_KEY,
    // we refresh the badge immediately (works across tabs/iframes/routes).
    const once = (e) => {
      if (e.key === STORAGE_KEY) {
        log("storage change detected for", STORAGE_KEY, "→ refreshing badge");
        window.josfeBadge?.refresh?.();
        window.removeEventListener("storage", once);
      }
    };
    window.addEventListener("storage", once, { once: true });

    // Navigate to selector page
    frappe.set_route("location-picker");
  }

  function tryDOMInjectUserMenu(root = document) {
    const menus = root.querySelectorAll(
      ".navbar .dropdown-menu, .navbar .menu, .dropdown-menu"
    );
    for (const menu of menus) {
      const hasLogout =
        !!menu.querySelector('a[href*="/api/method/logout"]') ||
        /log\s?out|cerrar sesi\u00f3n/i.test(menu.textContent || "");
      if (!hasLogout) continue;

      // Already injected?
      if (menu.querySelector(`#${CSS.escape(ID)}`)) return true;

      const listContainer = menu.querySelector("ul") || menu;

      const logoutItem =
        menu.querySelector('a[href*="/api/method/logout"]') ||
        Array.from(menu.querySelectorAll("a")).find((a) =>
          /log\s?out|cerrar sesi\u00f3n/i.test(a.textContent || "")
        );

      // Create divider
      const divider = document.createElement("li");
      divider.role = "presentation";
      divider.innerHTML = `<hr style="margin: 8px 12px; border-top: 1px solid #ccc;">`;

      // Create menu item
      const item = makeItem(onClick);

      if (logoutItem?.parentElement?.parentElement === listContainer) {
        listContainer.insertBefore(divider, logoutItem.parentElement);
        listContainer.insertBefore(item, logoutItem.parentElement);
      } else if (logoutItem && listContainer === menu) {
        menu.insertBefore(divider, logoutItem);
        menu.insertBefore(item, logoutItem);
      } else {
        listContainer.appendChild(divider);
        listContainer.appendChild(item);
      }

      log("menu item injected via DOM");
      return true;
    }
    return false;
  }

  frappe.after_ajax(() => {
    tryDOMInjectUserMenu(document);

    const observer = new MutationObserver((records) => {
      for (const r of records) {
        for (const n of r.addedNodes) {
          if (!(n instanceof Element)) continue;
          if (
            n.matches?.(".dropdown-menu, .menu, .navbar, [role='menu']") ||
            n.querySelector?.(".dropdown-menu, .menu, .navbar, [role='menu']")
          ) {
            tryDOMInjectUserMenu(n);
          }
        }
      }
      tryDOMInjectUserMenu(document);
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });

    window.addEventListener("beforeunload", () => observer.disconnect());
  });
})();
