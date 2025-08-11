// apps/josfe/josfe/public/js/contact_html_enhancer.js
// Minimal, stable enhancer for Address & Contact (save/edit + add only)

(() => {
  // --- return flag for "save" only ---
  const FLAG_KEY = "josfe_force_enhance";
  const getFlag = () => { try { const r = sessionStorage.getItem(FLAG_KEY); return r ? JSON.parse(r) : null; } catch { return null; } };
  const setFlag = (dt, dn) => sessionStorage.setItem(FLAG_KEY, JSON.stringify({ dt, dn, action: "save", t: Date.now() }));
  const clearFlag = () => sessionStorage.removeItem(FLAG_KEY);

  // --- utils ---
  const getFrm = () => (typeof cur_frm !== "undefined" && cur_frm) || frappe?.container?.page?.frm || null;
  const isParty = (dt) => dt === "Customer" || dt === "Supplier";
  const getWrap = (frm) => frm?.fields_dict?.contact_html?.$wrapper?.get?.(0) || frm?.fields_dict?.contact_html?.wrapper || null;
  const digits = (s) => (s || "").replace(/\D/g, "");

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

  function phoneHTML(row) {
    const raw = (row.phone || "").trim();
    if (!raw) return "";
    let txt = frappe.utils.escape_html(raw);
    if (row.jos_phone_ext) txt += ` ext. ${frappe.utils.escape_html(String(row.jos_phone_ext))}`;
    if (row.jos_whatsapp) {
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
      const d = digits(r.phone || "");
      if (!d) return;
      map.set(d, r);
      if (d.length >= 10) map.set(d.slice(-10), r);
      if (d.length >= 9)  map.set(d.slice(-9), r);
    });
    return map;
  }

  async function fetchContacts(names) {
    const docs = {};
    await Promise.all(names.map(async (n) => {
      try { docs[n] = await frappe.db.get_doc("Contact", n); } catch {}
    }));
    return docs;
  }

  function injectForBox(box, doc, { force } = {}) {
    const telTags = box.querySelectorAll("a[href^='tel:']");
    const rows = doc.phone_nos || [];
    if (!telTags.length || !rows.length) return false;

    if (force) telTags.forEach(tag => { delete tag.dataset.josfe; }); // allow re-run after edit

    const idx = buildPhoneIndex(rows);
    let changed = false;

    telTags.forEach((tag, i) => {
      if (!force && tag.dataset.josfe === "1") return;
      const key = digits(tag.getAttribute("href") || "") || digits(tag.textContent || "");
      let row = key ? (idx.get(key) || idx.get(key.slice(-10)) || idx.get(key.slice(-9)) || null) : null;
      if (!row) row = rows[i];
      if (!row || !row.phone) return;

      const html = phoneHTML(row);
      if (!html) return;
      tag.innerHTML = html;
      tag.dataset.josfe = "1";
      changed = true;
    });

    return changed;
  }

  function sigFor(boxes) {
    try {
      return boxes.map((b) => {
        const nm = getBoxContactName(b) || "";
        const c = b.querySelectorAll("a[href^='tel:']").length;
        return `${nm}|${c}`;
      }).join("||");
    } catch { return String(Date.now()); }
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
      for (const b of boxes) {
        const nm = getBoxContactName(b);
        if (nm) { nameByBox.set(b, nm); names.push(nm); }
      }
      const uniq = [...new Set(names)];
      if (!uniq.length) return;

      const docs = await fetchContacts(uniq);
      for (const [b, nm] of nameByBox.entries()) {
        const doc = docs[nm];
        if (doc) injectForBox(b, doc, { force });
      }
    } finally {
      requestAnimationFrame(() => { frm.__enhancing = false; });
    }
  }

  function schedule(frm, opts) {
    if (frm.__enh_scheduled) return;
    frm.__enh_scheduled = true;
    requestAnimationFrame(() => {
      frm.__enh_scheduled = false;
      enhanceAll(frm, opts || {});
    });
  }

  function ensureObserver(frm) {
    if (frm.__contactEnhancerMO) return;
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
      if (touched) schedule(frm);
    });
    mo.observe(document.body, { childList: true, subtree: true }); // body-level so wrapper swaps are caught
    frm.__contactEnhancerMO = mo;
  }

  // --- Customer / Supplier: handle normal + "save" return ---
  function partyRefresh(frm) {
    ensureObserver(frm);

    const f = getFlag();
    if (f && f.dt === frm.doctype && f.dn === frm.doc?.name && f.action === "save") {
      // On return from Contact save/edit/add: rebuild cards then force one enhance
      if (frappe.contacts?.render_address_and_contact) {
        frappe.contacts.render_address_and_contact(frm);
      }
      schedule(frm, { force: true });
      clearFlag();
      return;
    }

    // Normal path
    schedule(frm);
  }

  frappe.ui.form.on("Customer", { refresh: partyRefresh });
  frappe.ui.form.on("Supplier", { refresh: partyRefresh });

  // --- Contact: set flag + route back on save (covers edit & add) ---
  function findPartyLink(doc) {
    const L = doc?.links || [];
    return L.find(l => l.link_doctype === "Customer") || L.find(l => l.link_doctype === "Supplier") || null;
  }

  frappe.ui.form.on("Contact", {
    after_save(frm) {
      const p =
        (frm.doc.links || []).find(l => l.link_doctype === "Customer") ||
        (frm.doc.links || []).find(l => l.link_doctype === "Supplier");
      if (!p) return;
      setFlag(p.link_doctype, p.link_name);                    // tell parent to rebuild + force one pass
      frappe.after_ajax(() => frappe.set_route("Form", p.link_doctype, p.link_name)); // route back
    }
    // Note: delete is intentionally not handled (manual refresh is acceptable per requirement)
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

  // Optional manual trigger
  window.JOSFE_runEnhancer = () => { const f = getFrm(); if (f) enhanceAll(f, { force: true }); };
})();
