// apps/josfe/josfe/public/js/test_user_menu_probe.js
(() => {
  const LABEL = "Cambiar Establecimiento";
  const ID = "josfe-change-establishment";
  const log = (...a) => console.log("[test:user_menu]", ...a);
  const warn = (...a) => console.warn("[test:user_menu]", ...a);

  log("probe started");

  // --- util: make menu item DOM node
  function makeItem(onclick) {
    const li = document.createElement("li");
    li.role = "presentation";
    const a = document.createElement("a");
    a.id = ID;
    a.role = "menuitem";
    a.href = "javascript:void(0)";
    a.textContent = LABEL;
    a.addEventListener("click", (e) => {
      e.preventDefault();
      try { onclick?.(); } catch (err) { console.error(err); }
    });
    li.appendChild(a);
    return li;
  }

  // --- ACTION handler
  function onClick() {
    log("clicked:", LABEL);
    if (window.frappe?.set_route) {
      frappe.set_route("location-picker");
    } else {
      location.hash = "#location-picker";
    }
  }

  // --- attempt A: older-ish API hooks (v12–v13 style; sometimes present via compatibility)
  function tryHelpAPI() {
    const t = frappe?.ui?.toolbar;
    if (!t) return false;

    // Some builds expose add_dropdown_button('Help', ...)
    if (typeof t.add_dropdown_button === "function") {
      log("found toolbar.add_dropdown_button; adding to Help");
      t.add_dropdown_button("Help", LABEL, onClick, false);
      return true;
    }

    // Some builds expose a help menu object
    if (t.help_menu?.add_item && typeof t.help_menu.add_item === "function") {
      log("found toolbar.help_menu.add_item; adding");
      t.help_menu.add_item({ label: LABEL, action: onClick });
      return true;
    }

    log("toolbar present but no known add_* API");
    return false;
  }

  // --- attempt B: DOM inject when user dropdown is actually in the DOM
  function tryDOMInjectUserMenu(root = document) {
    // Find any navbar dropdown-menu that contains "Log out" or "/api/method/logout"
    const menus = root.querySelectorAll(".navbar .dropdown-menu, .navbar .menu, .dropdown-menu");
    for (const menu of menus) {
      // Heuristic: does this dropdown look like the user menu?
      const hasLogout =
        !!menu.querySelector('a[href*="/api/method/logout"]') ||
        /log\s?out|cerrar sesi\u00f3n/i.test(menu.textContent || "");

      if (!hasLogout) continue;

      // Avoid re-adding
      if (menu.querySelector(`#${CSS.escape(ID)}`)) {
        log("menu item already present in detected user menu");
        return true;
      }

      // Prefer <ul> structure if present
      let listContainer =
        menu.querySelector("ul") || menu;

      const item = makeItem(onClick);

      // Insert before logout if we can find it; else append.
      const logoutItem =
        menu.querySelector('a[href*="/api/method/logout"]') ||
        Array.from(menu.querySelectorAll("a")).find(a => /log\s?out|cerrar sesi\u00f3n/i.test(a.textContent || ""));

      if (logoutItem?.parentElement?.parentElement === listContainer) {
        listContainer.insertBefore(item, logoutItem.parentElement);
      } else if (logoutItem && listContainer === menu) {
        // Some menus are flat anchors without <ul>/<li>
        menu.insertBefore(item, logoutItem);
      } else {
        listContainer.appendChild(item);
      }

      log("injected into user menu via DOM observer");
      return true;
    }
    return false;
  }

  // --- Global observer
  const observer = new MutationObserver((records) => {
    // Batch once per microtask
    let userInjected = false;

    // Try DOM inject on any added subtree
    for (const r of records) {
      // Only check if nodes were added
      if (r.addedNodes && r.addedNodes.length) {
        for (const n of r.addedNodes) {
          if (!(n instanceof Element)) continue;
          // Fast path: if a dropdown/menu appeared, try to inject
          if (
            n.matches?.(".dropdown-menu, .menu, .navbar, [role='menu']") ||
            n.querySelector?.(".dropdown-menu, .menu, .navbar, [role='menu']")
          ) {
            userInjected = tryDOMInjectUserMenu(n) || userInjected;
          }
        }
      }
    }

    // Also try once per batch against full document, in case the menu
    // is rendered elsewhere (portals/teleports)
    if (!userInjected) {
      tryDOMInjectUserMenu(document);
    }
  });

  // Start once Desk has loaded its first ajax cycle
  frappe?.after_ajax?.(() => {
    log("after_ajax fired. Probing…");

    // 1) Try the API path (if any)
    const apiAdded = tryHelpAPI();
    if (apiAdded) log("added item via toolbar API");

    // 2) Try immediate DOM injection (in case menu is already present)
    const nowAdded = tryDOMInjectUserMenu(document);
    if (nowAdded) log("added item via immediate DOM pass");

    // 3) Observe future changes to catch lazy-rendered dropdowns
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true
    });
    log("observer connected");
  });

  // Safety: stop observing if we navigate away from Desk entirely
  window.addEventListener("beforeunload", () => {
    observer.disconnect();
    log("observer disconnected");
  });
})();
