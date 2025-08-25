// apps/josfe/josfe/public/js/contact_html_enhancer.js
// Stable enhancer for Address & Contact (save/edit + add)
// - Coalescing scheduler (forced runs always win).
// - Enhances from Contact.phone_nos.
// - For Customer/Supplier Main Contact, merges <Doctype>.custom_jos_telefonos.
// - Forces re-enhance on party after_save.
// - "Force burst" after Contact/Address save to beat late re-renders.
// - Fresh server fetch (bypass locals) for Contacts.
// - Burst cache reuses fresh docs for subsequent RAF passes (no extra RPC).

(() => {
  // --- return flag for Contact/Address "save" only ---
  const FLAG_KEY = "josfe_force_enhance";
  const getFlag  = () => { try { const r = sessionStorage.getItem(FLAG_KEY); return r ? JSON.parse(r) : null; } catch { return null; } };
  const setFlag  = (dt, dn) => sessionStorage.setItem(FLAG_KEY, JSON.stringify({ dt, dn, action: "save", t: Date.now() }));
  const clearFlag= () => sessionStorage.removeItem(FLAG_KEY);

  // --- utils ---
  const getFrm = () => (typeof cur_frm !== "undefined" && cur_frm) || frappe?.container?.page?.frm || null;
  const isParty = (dt) => dt === "Customer" || dt === "Supplier";
  const getWrap = (frm) =>
    frm?.fields_dict?.contact_html?.$wrapper?.get?.(0) ||
    frm?.fields_dict?.contact_html?.wrapper || null;

  const reNonDigit = /\D/g;
  const digits = (s) => (s || "").replace(reNonDigit, "");

  function getBoxContactName(box) {
    const a =
      box.querySelector('a[data-doctype="Contact"][data-name]') ||
      box.querySelector('a[href*="/app/contact/"]') ||
      box.querySelector('a[href*="#Form/Contact/"]');
    if (!a) return null;
    if (a.dataset?.name) return a.dataset.name;
    const href = a.getAttribute("href") || "";
    const m = href.match(/\/contact\/([^\/#?]+)/i) || href.match(/#Form\/Contact\/([^\/#?]+)/i);
    return m ? decodeURIComponent(m[1]) : null;
  }

  // Accessors (support custom rows)
  const rowPhone    = (r) => r.phone ?? r.telefono ?? r.jos_phone ?? r.number ?? "";
  const rowExt      = (r) => r.jos_phone_ext ?? r.ext ?? r.extension ?? "";
  const rowWhatsapp = (r) => Boolean(r.jos_whatsapp ?? r.whatsapp ?? r.is_whatsapp);

  function phoneHTML(row) {
    const raw = String(rowPhone(row) || "").trim();
    if (!raw) return "";
    let txt = frappe.utils.escape_html(raw);
    const ext = rowExt(row);
    if (ext) txt += ` ext. ${frappe.utils.escape_html(String(ext))}`;
    if (rowWhatsapp(row)) {
      const d = digits(raw);
      const intl = d.startsWith("0") ? d.slice(1) : d; // Ecuador: drop leading 0
      if (intl) {
        const href = `https://wa.me/593${intl}`;
        return `<a href="${href}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;color:inherit">
                  ${txt}
                  <img alt="WhatsApp" src="https://cdn-icons-png.flaticon.com/24/733/733585.png" style="height:14px;margin-left:4px">
                </a>`;
      }
    }
    return txt;
  }

  function buildPhoneIndex(rows) {
    const map = new Map();
    (rows || []).forEach((r) => {
      const d = digits(String(rowPhone(r) || ""));
      if (!d) return;
      map.set(d, r);
      if (d.length >= 10) map.set(d.slice(-10), r);
      if (d.length >= 9)  map.set(d.slice(-9), r);
    });
    return map;
  }

  // ====== FRESH fetch from server (no locals cache) + burst cache reuse ======
  async function fetchContacts(names, { frm, burst = false } = {}) {
    const now = Date.now();
    const cacheActive = burst && frm && frm.__enh_doccache && now < frm.__enh_doccache.until;
    if (cacheActive && sameNameSet(frm.__enh_doccache.names, names)) {
      return frm.__enh_doccache.docs;
    }

    const docs = {};
    await Promise.all(
      names.map(async (n) => {
        try {
          // drop any cached copy in locals to avoid stale reads
          try {
            if (frappe.model?.remove_from_locals) {
              frappe.model.remove_from_locals("Contact", n);
            }
          } catch {}

          // fetch fresh from server
          const res = await frappe.call({
            method: "frappe.client.get",
            args: { doctype: "Contact", name: n }
          });
          const d = res?.message || null;
          if (d) docs[n] = d;
        } catch {}
      })
    );

    // store burst cache for ~1s, only if we are in a burst
    if (burst && frm) {
      frm.__enh_doccache = { names: [...names], docs, until: now + 1000 };
    }
    return docs;
  }

  function sameNameSet(a, b) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    const A = [...a].sort().join("|"); const B = [...b].sort().join("|");
    return A === B;
  }

  // Base + (if main card on Customer/Supplier) merge <Doctype>.custom_jos_telefonos
  function getRowsForBox(contactDoc, frm, boxContactName) {
    const base = Array.isArray(contactDoc?.phone_nos) ? [...contactDoc.phone_nos] : [];
    let extras = [];

    if ((frm?.doctype === "Customer" || frm?.doctype === "Supplier") && typeof boxContactName === "string") {
      const party = frm.doc?.name || "";

      // Match your naming convention for main contacts
      const expectedMain =
        frm.doctype === "Customer"
          ? `Main Contact Clte-${party}-${party}`
          : `Main Contact Prov-${party}-${party}`;

      const isMain = boxContactName === expectedMain;

      if (isMain) {
        const custom = Array.isArray(frm.doc?.custom_jos_telefonos) ? frm.doc.custom_jos_telefonos : [];
        extras = custom.map((r) => {
          const phone =
            r.phone ?? r.telefono ?? r.jos_phone ?? r.number ?? r.mobile ?? r.mobile_no ?? r.phone_no ?? r.tel ?? "";
          if (!phone) return null;
          const jos_phone_ext =
            r.jos_phone_ext ?? r.ext ?? r.extension ?? r.phone_ext ?? r.anexo ?? r.extension_no ?? "";
          const jos_whatsapp = Boolean(
            r.jos_whatsapp ?? r.whatsapp ?? r.is_whatsapp ?? r.is_whats ?? r.whatsapp_enabled
          );
          return { phone: String(phone), jos_phone_ext, jos_whatsapp };
        }).filter(Boolean);
      }
    }

    return [...base, ...extras];
  }

  function injectForBox(box, doc, frm, boxContactName, { force } = {}) {
    const telTags = box.querySelectorAll("a[href^='tel:']");
    const rows = getRowsForBox(doc, frm, boxContactName);
    if (!telTags.length || !rows.length) return false;

    if (force) telTags.forEach(tag => { delete tag.dataset.josfe; });

    const idx = buildPhoneIndex(rows);
    let changed = false;

    telTags.forEach((tag, i) => {
      if (!force && tag.dataset.josfe === "1") return;

      const key = digits(tag.getAttribute("href") || "") || digits(tag.textContent || "");
      let row = key ? (idx.get(key) || idx.get(key.slice(-10)) || idx.get(key.slice(-9)) || null) : null;
      if (!row) row = rows[i];
      if (!row || !rowPhone(row)) return;

      const html = phoneHTML(row);
      if (!html) return;

      if (force || tag.innerHTML !== html) {
        tag.innerHTML = html;
        tag.dataset.josfe = "1";
        changed = true;
      }
    });

    return changed;
  }

  function sigFor(boxes) {
    try {
      return boxes.map((b, idx) => {
        const nm = getBoxContactName(b) || "";
        const c = b.querySelectorAll("a[href^='tel:']").length;
        return `${idx}:${nm}|${c}`;
      }).join("||");
    } catch {
      return String(Date.now());
    }
  }

  async function enhanceAll(frm, { force = false } = {}) {
    if (frm.__enhancing) return;
    frm.__enhancing = true;

    try {
      const w = getWrap(frm);
      if (!w) return;
      const boxes = Array.from(w.querySelectorAll(".address-box"));
      if (!boxes.length) return;

      const sig = sigFor(boxes);
      if (!force && frm.__enh_lastSig === sig) return;
      frm.__enh_lastSig = sig;

      const nameByBox = new Map();
      const names = [];
      boxes.forEach((b) => {
        const nm = getBoxContactName(b);
        if (nm) { nameByBox.set(b, nm); names.push(nm); }
      });
      const uniq = [...new Set(names)];
      if (!uniq.length) return;

      const docs = await fetchContacts(uniq, { frm, burst: !!frm.__enh_force_burst });
      for (const [b, nm] of nameByBox.entries()) {
        const doc = docs[nm];
        if (doc) injectForBox(b, doc, frm, nm, { force });
      }
    } finally {
      requestAnimationFrame(() => {
        frm.__enhancing = false;

        // If we're in a "force burst", schedule another forced pass.
        if (frm.__enh_force_burst && frm.__enh_force_burst > 0) {
          frm.__enh_force_burst -= 1;
          schedule(frm, { force: true });
        }
      });
    }
  }

  // --- Coalescing scheduler: if ANY caller asks for force, we force on the next run.
  function schedule(frm, opts) {
    if (opts && opts.force) frm.__enh_pending_force = true;
    if (frm.__enh_scheduled) return;

    frm.__enh_scheduled = true;
    requestAnimationFrame(() => {
      frm.__enh_scheduled = false;
      const force = !!((opts && opts.force) || frm.__enh_pending_force);
      frm.__enh_pending_force = false;
      enhanceAll(frm, { force });
    });
  }

  function ensureObserver(frm) {
    if (frm.__contactEnhancerMO) return;

    const root = frm.$wrapper && frm.$wrapper[0];
    if (!root) return;

    const mo = new MutationObserver((muts) => {
      if (frm.__enhancing) return;
      let touched = false;
      for (const m of muts) {
        if (m.type !== "childList") continue;
        const nodes = [...(m.addedNodes || []), ...(m.removedNodes || [])];
        for (const n of nodes) {
          if (n.nodeType !== 1) continue;
          if (n.matches?.(".address-box") || n.querySelector?.(".address-box")) { touched = true; break; }
        }
        if (touched) break;
      }
      if (touched) {
        if (frm.__enh_force_burst && frm.__enh_force_burst > 0) schedule(frm, { force: true });
        else schedule(frm);
        // auto-disconnect once address UI is present
        const box = root.querySelector(".address-box");
        if (box) { try { mo.disconnect(); } catch {} frm.__contactEnhancerMO = null; }
      }
    });

    mo.observe(root, { childList: true, subtree: true });
    frm.__contactEnhancerMO = mo;

    // also disconnect on refresh
    frappe.ui.form.on(frm.doctype, { before_refresh() { try { mo.disconnect(); } catch {} frm.__contactEnhancerMO = null; }});
  }

  // --- Customer / Supplier: handle normal + Contact/Address-save return ---
  function partyRefresh(frm) {
    ensureObserver(frm);

    const f = getFlag();
    const match = f && f.dt === frm.doctype && f.dn === frm.doc?.name && f.action === "save";

    if (match) {
      if (frappe.contacts?.render_address_and_contact) {
        frappe.contacts.render_address_and_contact(frm);
      }
      // Start a small force burst to beat late re-renders (no timers).
      frm.__enh_force_burst = 2; // bump to 3-4 if needed
      // Clear any previous burst cache; the first forced pass will refresh it.
      frm.__enh_doccache = null;
      schedule(frm, { force: true });
      clearFlag();
      return;
    }

    schedule(frm);
  }

  // --- Unified function for after_save enhancement (Customer + Supplier) ---
  function common_after_save(frm) {
    if (frappe.contacts?.render_address_and_contact) {
      frappe.contacts.render_address_and_contact(frm);
    }
    frm.__enh_force_burst = Math.max(frm.__enh_force_burst || 0, 1);
    frm.__enh_doccache = null;
    schedule(frm, { force: true });
  }

  // --- Hooks for party doctypes ---
  frappe.ui.form.on("Customer", {
    refresh: partyRefresh,
    after_save: common_after_save
  });

  frappe.ui.form.on("Supplier", {
    refresh: partyRefresh,
    after_save: common_after_save
  });

  // --- Contact: set flag + route back on save (covers edit & add) ---
  frappe.ui.form.on("Contact", {
    after_save(frm) {
      const p =
        (frm.doc.links || []).find(l => l.link_doctype === "Customer") ||
        (frm.doc.links || []).find(l => l.link_doctype === "Supplier");
      if (!p) return;
      setFlag(p.link_doctype, p.link_name);
      frappe.after_ajax(() => {
        frappe.set_route("Form", p.link_doctype, p.link_name);
      });
    }
  });

  // --- Address: set flag + route back on save ---
  frappe.ui.form.on("Address", {
    after_save(frm) {
      const p =
        (frm.doc.links || []).find(l => l.link_doctype === "Customer") ||
        (frm.doc.links || []).find(l => l.link_doctype === "Supplier");
      if (!p) return;
      setFlag(p.link_doctype, p.link_name);
      frappe.after_ajax(() => {
        frappe.set_route("Form", p.link_doctype, p.link_name);
      });
    }
  });

  // --- bootstrap ---
  (function init() {
    const frm = getFrm();
    if (frm && isParty(frm.doctype)) {
      ensureObserver(frm);
      schedule(frm);
    }
  })();

  if (frappe?.router?.on) {
    frappe.router.on("change", () => {
      const frm = getFrm();
      if (frm && isParty(frm.doctype)) {
        ensureObserver(frm);
        schedule(frm);
      }
    });
  }

  // Manual helper
  window.JOSFE_runEnhancer = () => {
    const f = getFrm();
    if (f) enhanceAll(f, { force: true });
  };
})();
