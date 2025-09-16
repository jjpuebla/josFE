# josfe/ui_controls/helpers.py
import json
import frappe

# -------------------------------
# Internal helpers (single source)
# -------------------------------

def _get_pair_doc(role: str, doctype: str):
    name = frappe.db.exists("UI Settings", {"role": role, "doctype_name": doctype})
    return frappe.get_doc("UI Settings", name) if name else None

def _fallback_meta(doctype: str):
    """Return default-hidden tabs/fields from DocType meta."""
    meta = frappe.get_meta(doctype)
    tabs, fields, current_tab = set(), set(), None
    for df in meta.fields:
        if df.fieldtype == "Tab Break":
            current_tab = df.fieldname
            if getattr(df, "hidden", 0):
                tabs.add(df.fieldname)
        elif df.fieldtype in ("Column Break", "Section Break"):
            # ignore entirely
            continue
        else:
            if not current_tab:
                current_tab = "Main"
            if getattr(df, "hidden", 0):
                fields.add(df.fieldname)
    return {"tabs": sorted(tabs), "fields": sorted(fields)}

def _effective_rules(role: str, doctype: str):
    """
    Single source of truth:
    - If Active rows exist → use Active
    - Else if Factory rows exist → use Factory
    - Else → fallback to meta (hidden=1)
    Returns: {"tabs": [...], "fields": [...]}
    """
    doc = _get_pair_doc(role, doctype)
    if not doc:
        return _fallback_meta(doctype)

    actives = [r for r in (doc.rules or []) if not r.is_factory]
    base = actives if actives else [r for r in (doc.rules or []) if r.is_factory]

    if base:
        tabs = sorted({r.section_fieldname for r in base if r.section_fieldname and not r.fieldname})
        fields = sorted({r.fieldname for r in base if r.fieldname})
        return {"tabs": tabs, "fields": fields}

    return _fallback_meta(doctype)

# -------------------------------
# Public API
# -------------------------------

@frappe.whitelist()
def get_fields_and_sections(doctype: str):
    """
    Return tabs + fields grouped by tab with meta flags.
    NOTE: we only expose Tab Breaks + real fields. Column/Section breaks are skipped.
    """
    meta = frappe.get_meta(doctype)
    tabs, fields_by_tab, current = [], {}, None

    for df in meta.fields:
        if df.fieldtype in ("Tab Break", "Column Break", "Section Break"):
            if df.fieldtype == "Tab Break":
                current = df.fieldname
                tabs.append({
                    "fieldname": df.fieldname,
                    "label": df.label or df.fieldname,
                    "hidden": getattr(df, "hidden", 0),
                })
                fields_by_tab[current] = []
            # skip Column/Section breaks entirely
            continue

        # Normal field
        if not current:
            current = "Main"
            if "Main" not in fields_by_tab:
                tabs.append({"fieldname": "Main", "label": "Main", "hidden": 0})
                fields_by_tab["Main"] = []
        fields_by_tab[current].append({
            "fieldname": df.fieldname,
            "label": df.label or df.fieldname,
            "reqd": getattr(df, "reqd", 0),
            "hidden": getattr(df, "hidden", 0),
        })

    return {"tabs": tabs, "fields_by_tab": fields_by_tab}

@frappe.whitelist()
def factory_exists(role=None, doctype=None):
    role = role or frappe.form_dict.get("role")
    doctype = doctype or frappe.form_dict.get("doctype")
    if not role or not doctype:
        return False
    # factory exists iff there is at least one factory UI Rule for the pair
    return bool(frappe.get_all(
        "UI Rule",
        filters={"role": role, "doctype_name": doctype, "is_factory": 1},
        limit=1
    ))

@frappe.whitelist()
def get_role_rules(role: str, doctype: str):
    """
    Prefill for matrix:
    Always return the effective hidden sets (tabs/fields) using a single function.
    """
    return _effective_rules(role, doctype)

@frappe.whitelist()
def save_role_rules(role: str, doctype: str, payload: str, as_factory: int = 0):
    """
    Save rules for a role+doctype. Active requires Factory existing.
    - payload: list of {section_fieldname, fieldname (optional), hide:1} where hide=1 means "hidden"
    - as_factory: 1 to overwrite Factory, 0 to overwrite Active.
    Behavior:
    - When saving Active without Factory → block.
    - When saving Factory first time → seed Active to persist matrix on reload.
    - Always validate against current meta; skip stale fields/tabs.
    """
    data = json.loads(payload) if isinstance(payload, str) else (payload or [])
    doc = _get_pair_doc(role, doctype) or frappe.get_doc({
        "doctype": "UI Settings",
        "role": role,
        "doctype_name": doctype
    }).insert(ignore_permissions=True)

    meta = frappe.get_meta(doctype)
    valid_tabs = {df.fieldname for df in meta.fields if df.fieldtype == "Tab Break"} | {"Main"}
    valid_fields = {df.fieldname for df in meta.fields}

    rows = []
    for e in data:
        sec = (e.get("section_fieldname") or "Main")
        fld = e.get("fieldname")
        if fld:
            if fld in valid_fields:
                rows.append(("field", sec, fld))
        else:
            if sec in valid_tabs:
                rows.append(("tab", sec, None))

    if not as_factory and not factory_exists(role, doctype):
        frappe.throw("Please save <b>Factory Defaults</b> first.")

    # preserve the other set, drop only the one we are replacing
    if as_factory:
        doc.set("rules", [r for r in (doc.rules or []) if not r.is_factory])
    else:
        doc.set("rules", [r for r in (doc.rules or []) if r.is_factory])


    for _, sec, fld in rows:
        ch = doc.append("rules", {})
        ch.role = role
        ch.doctype_name = doctype
        ch.section_fieldname = sec
        ch.fieldname = fld
        ch.hide = 1  # persisted as hidden entries only
        ch.is_factory = 1 if as_factory else 0

    doc.save(ignore_permissions=True)

    # First Factory → seed Active so selections persist
    if as_factory and not any(r for r in (doc.rules or []) if not r.is_factory):
        for r in [r for r in (doc.rules or []) if r.is_factory]:
            ch = doc.append("rules", {})
            ch.role, ch.doctype_name = r.role, r.doctype_name
            ch.section_fieldname, ch.fieldname = r.section_fieldname, r.fieldname
            ch.hide, ch.is_factory = r.hide, 0
        doc.save(ignore_permissions=True)

    return {"ok": True, "factory_created": bool(as_factory)}

@frappe.whitelist()
def reset_role_rules(role: str, doctype: str):
    """Drop actives and clone factory to active."""
    doc = _get_pair_doc(role, doctype)
    if not doc:
        return {"ok": False, "msg": "No Factory Defaults defined."}

    factory = [r for r in (doc.rules or []) if r.is_factory]
    if not factory:
        return {"ok": False, "msg": "No Factory Defaults defined."}

    # keep only factory rows
    doc.set("rules", [r for r in (doc.rules or []) if r.is_factory])

    # clone factory -> active
    for r in factory:
        ch = doc.append("rules", {})
        ch.role, ch.doctype_name = r.role, r.doctype_name
        ch.section_fieldname, ch.fieldname = r.section_fieldname, r.fieldname
        ch.hide, ch.is_factory = r.hide, 0   # <-- fix here

    doc.save(ignore_permissions=True)
    return {"ok": True}

@frappe.whitelist()
def get_ui_rules(doctype: str, role: str=None):
    # Compatibility wrapper
    from . import helpers_new  # or your new module
    return helpers_new.get_role_rules(role or frappe.session.user, doctype)