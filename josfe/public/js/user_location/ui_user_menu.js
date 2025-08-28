// apps/josfe/josfe/public/js/user_location/ui_user_menu.js
(() => {
  const DEBUG = false;
  const log = (...a) => DEBUG && console.log("[josfe:user-menu]", ...a);

  function norm(s) {
    return (s || "").toLowerCase().trim();
  }

  function isUserMenu(el) {
    if (!el) return false;
    const items = el.querySelectorAll("a, .dropdown-item");
    for (const a of items) {
      const t = norm(a.textContent);
      if (t === "log out" || t === "logout" || t === "cerrar sesión") {
        return true;
      }
    }
    return false;
  }

  function alreadyInjected(el) {
    return !!el.querySelector(".josfe-change-wh");
  }

  function buildLink(existingItemForClass) {
    let cls = "dropdown-item";
    if (existingItemForClass && existingItemForClass.className) {
      cls = existingItemForClass.className;
    }
    const a = document.createElement("a");
    a.href = "#";
    a.textContent = "Cambiar Sucursal";
    a.className = cls + " josfe-change-wh";
    a.style.fontWeight = "700"; // bold
    a.addEventListener("click", (e) => {
      e.preventDefault();
      frappe.set_route("location-picker");
    });
    return a;
  }

  function injectIntoMenu(menu) {
    if (!menu || alreadyInjected(menu)) return;

    const firstAnchor = menu.querySelector("a, .dropdown-item");
    const logOutItem =
      Array.from(menu.querySelectorAll("a, .dropdown-item")).find(
        (a) => ["log out", "logout", "cerrar sesión"].includes(norm(a.textContent))
      );

    // divider
    const divider = document.createElement("div");
    divider.className = "dropdown-divider josfe-change-wh";

    // link
    const link = buildLink(firstAnchor);

    if (logOutItem && logOutItem.parentElement) {
      // append after logout
      if (logOutItem.parentElement.tagName === "LI") {
        // UL/LI structure
        const liDivider = document.createElement("li");
        liDivider.className = "divider josfe-change-wh";
        logOutItem.parentElement.insertAdjacentElement("afterend", liDivider);

        const li = document.createElement("li");
        li.className = "josfe-change-wh";
        li.appendChild(link);
        liDivider.insertAdjacentElement("afterend", li);
      } else {
        // DIV + anchors structure
        logOutItem.insertAdjacentElement("afterend", link);
        logOutItem.insertAdjacentElement("afterend", divider);
      }
    } else {
      // fallback: just append at end
      menu.appendChild(divider);
      menu.appendChild(link);
    }

    log("Injected after Log out");
  }

  function tryInjectOnce() {
    const candidates = document.querySelectorAll(
      ".navbar .dropdown-menu, .navbar .dropdown-menu-right, .navbar .dropdown-menu-end"
    );
    for (const el of candidates) {
      if (isUserMenu(el)) {
        injectIntoMenu(el);
        return true;
      }
    }
    return false;
  }

  function setup() {
    if (tryInjectOnce()) return;

    const mo = new MutationObserver(() => {
      if (tryInjectOnce()) mo.disconnect();
    });
    mo.observe(document.body, { childList: true, subtree: true });

    if (frappe.router?.on && frappe.get_route) {
      frappe.router.on("change", () => {
        setTimeout(tryInjectOnce, 0);
      });
    }

    document.addEventListener(
      "click",
      () => {
        setTimeout(tryInjectOnce, 0);
      },
      true
    );
  }

  frappe.after_ajax(setup);
})();
