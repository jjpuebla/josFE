# josfe/ui_controls/helpers.py
import json
import frappe

def _fallback_meta(doctype: str):
    meta = frappe.get_meta(doctype)
    tabs, fields, current_tab = set(), set(), None
    for df in meta.fields:
        if df.fieldtype == "Tab Break":
            current_tab = df.fieldname
            if getattr(df, "hidden", 0):
                tabs.add(df.fieldname)
        else:
            if not current_tab:
                current_tab = "Main"
            if getattr(df, "hidden", 0):
                fields.add(df.fieldname)
    return {"tabs": sorted(tabs), "fields": sorted(fields)}

def _get_pair_doc(role: str, doctype: str):
    name = frappe.db.exists("UI Settings", {"role": role, "doctype_name": doctype})
    return frappe.get_doc("UI Settings", name) if name else None

@frappe.whitelist()
def get_fields_and_sections(doctype: str):
    """Return tabs + fields grouped by tab with meta flags."""
    meta = frappe.get_meta(doctype)
    tabs, fields_by_tab, current = [], {}, None
    for df in meta.fields:
        if df.fieldtype in ("Tab Break", "Column Break", "Section Break"):
            # handle only Tab Break explicitly
            if df.fieldtype == "Tab Break":
                current = df.fieldname
                tabs.append({
                    "fieldname": df.fieldname,
                    "label": df.label or df.fieldname,
                    "hidden": getattr(df, "hidden", 0),
                })
                fields_by_tab[current] = []
            continue  # skip column/section breaks completely
        else:
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
    return bool(frappe.get_all("UI Rule",
        filters={"role": role, "doctype_name": doctype, "is_factory": 1}, limit=1))

@frappe.whitelist()
def get_role_rules(role: str, doctype: str):
    """Prefill for matrix: Active if any, else Factory, else fallback to DocField.hidden."""
    doc = _get_pair_doc(role, doctype)
    if not doc:
        return _fallback_meta(doctype)

    actives = [r for r in (doc.rules or []) if not r.is_factory]
    factory = [r for r in (doc.rules or []) if r.is_factory]
    ruleset = actives if actives else factory

    if ruleset:
        tabs = sorted({r.section_fieldname for r in ruleset if r.section_fieldname and not r.fieldname})
        fields = sorted({r.fieldname for r in ruleset if r.fieldname})
        return {"tabs": tabs, "fields": fields}

    # ✅ Fallback to DocType meta hidden flags
    return _fallback_meta(doctype)

@frappe.whitelist()
def save_role_rules(role: str, doctype: str, payload: str, as_factory: int = 0):
    """Save rules for a role+doctype. Active requires Factory existing."""
    data = json.loads(payload) if isinstance(payload, str) else (payload or [])
    doc = _get_pair_doc(role, doctype) or frappe.get_doc({
        "doctype": "UI Settings", "role": role, "doctype_name": doctype
    }).insert(ignore_permissions=True)

    meta = frappe.get_meta(doctype)
    valid_tabs = {df.fieldname for df in meta.fields if df.fieldtype == "Tab Break"} | {"Main"}
    valid_fields = {df.fieldname for df in meta.fields}
    rows = []
    for e in data:
        sec = (e.get("section_fieldname") or "Main")
        fld = e.get("fieldname")
        if fld and fld in valid_fields:
            rows.append(("field", sec, fld))
        elif not fld and sec in valid_tabs:
            rows.append(("tab", sec, None))

    if not as_factory and not factory_exists(role, doctype):
        frappe.throw("Please save <b>Factory Defaults</b> first.")

    # keep opposite state, drop current
    keep_factory = bool(as_factory)
    doc.set("rules", [r for r in (doc.rules or []) if (r.is_factory == keep_factory)])

    for kind, sec, fld in rows:
        ch = doc.append("rules", {})
        ch.role = role
        ch.doctype_name = doctype
        ch.section_fieldname = sec
        ch.fieldname = fld
        ch.hide = 1
        ch.is_factory = 1 if as_factory else 0

    doc.save(ignore_permissions=True)

    # First Factory → seed Active
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
    doc.set("rules", [r for r in (doc.rules or []) if r.is_factory])
    for r in factory:
        ch = doc.append("rules", {})
        ch.role, ch.doctype_name = r.role, r.doctype_name
        ch.section_fieldname, ch.fieldname = r.section_fieldname, r.fieldname
        ch.hide, ch.is_factory = r.hide, 0
    doc.save(ignore_permissions=True)
    return {"ok": True}

@frappe.whitelist()
def get_ui_rules(doctype: str):
    """Runtime feed for client: effective rows for all roles on a doctype."""
    out = []
    for name in frappe.get_all("UI Settings", filters={"doctype_name": doctype}, pluck="name"):
        doc = frappe.get_doc("UI Settings", name)
        act = [r for r in (doc.rules or []) if not r.is_factory]
        base = act if act else [r for r in (doc.rules or []) if r.is_factory]
        for r in base:
            out.append({
                "role": r.role, "doctype_name": r.doctype_name,
                "section_fieldname": r.section_fieldname, "fieldname": r.fieldname, "hide": r.hide
            })
    return out
