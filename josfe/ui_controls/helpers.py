# josfe/ui_controls/helpers.py
import json
import frappe
from frappe import _
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

def role_has_doctype(role, doctype):
    return frappe.db.exists("DocPerm", {"role": role, "parent": doctype}) or \
           frappe.db.exists("Custom DocPerm", {"role": role, "parent": doctype})

@frappe.whitelist()
def get_role_rules(role, doctype):
    """Return the CURRENTLY editable set for the pair as plain lists of names.

    - If the role lost access → mark Inactive, but STILL return saved hides
      so the matrix reflects reality (checkboxes stay unchecked for hidden).
    - If it has access → mark Active and return the active set (if any),
      else the factory set, else the meta fallback.
    """
    name = frappe.db.get_value("UI Settings", {"role": role, "doctype_name": doctype}, "name")

    # Pair doesn't exist → just show meta fallback (everything shown unless core-hidden)
    if not name:
        base = _fallback_meta(doctype)
        base["inactive"] = False
        return base

    inactive = not role_has_doctype(role, doctype)
    frappe.db.set_value("UI Settings", name, "status", "Inactive" if inactive else "Active")

    # Pull rows once
    rows = frappe.get_all(
        "UI Rule",
        filters={"parent": name},
        fields=["section_fieldname", "fieldname", "hide", "is_factory"],
    )

    # Decide which layer to show in the matrix:
    # - Prefer Active if any Active rows exist
    # - Else use Factory rows
    actives = [r for r in rows if not r.is_factory]
    base = actives if actives else [r for r in rows if r.is_factory]

    if base:
        tabs   = sorted({r.section_fieldname for r in base if r.section_fieldname and not r.fieldname and r.hide})
        fields = sorted({r.fieldname        for r in base if r.fieldname and r.hide})
        return {"inactive": inactive, "tabs": tabs, "fields": fields}

    # Nothing saved yet → fall back to DocType meta
    meta_fallback = _fallback_meta(doctype)
    meta_fallback["inactive"] = inactive
    return meta_fallback

@frappe.whitelist()
def save_role_rules(role: str, doctype: str, payload: str, as_factory: int = 0):
    """
    Save rules for a role+doctype.
    - payload: list of {section_fieldname, fieldname (optional), hide:1}
    - as_factory: 1 to overwrite Factory, 0 to overwrite Active.

    Guarantees:
    - Active cannot be saved before Factory.
    - Saving Factory with an empty payload will still mark Factory as "set"
      by inserting a harmless anchor row (mandatory/core-hidden), which
      runtime will ignore. This allows the banner to flip to blue and
      the UI pair fields to lock.
    """
    data = json.loads(payload) if isinstance(payload, str) else (payload or [])

    meta = frappe.get_meta(doctype)
    valid_tabs = {df.fieldname for df in meta.fields if df.fieldtype == "Tab Break"} | {"Main"}
    valid_fields = {df.fieldname for df in meta.fields}

    mandatory_fields = {df.fieldname for df in meta.fields if df.reqd}
    core_hidden_fields = {df.fieldname for df in meta.fields if df.hidden}

    rows, invalid = [], []

    # validate/collect payload
    for e in data:
        sec = (e.get("section_fieldname") or "Main")
        fld = e.get("fieldname")

        if fld:
            if fld not in valid_fields:
                continue  # stale
            if fld in mandatory_fields:
                invalid.append({"field": fld, "reason": "mandatory"})
                continue
            if fld in core_hidden_fields:
                frappe.log_error(f"{doctype}.{fld}", "Skipped core-hidden field in UI Rule save")
                continue
            rows.append(("field", sec, fld))
        else:
            if sec not in valid_tabs:
                continue
            # tabs cannot be hidden if contain mandatory fields
            tab_fields = [df.fieldname for df in meta.fields if df.parent == doctype and df.parentfield == sec]
            if any(fn in mandatory_fields for fn in tab_fields):
                invalid.append({"tab": sec, "reason": "contains mandatory"})
                continue
            # if a tab only has core-hidden fields, skip silently
            if tab_fields and all(fn in core_hidden_fields for fn in tab_fields):
                frappe.log_error(f"{doctype}.{sec}", "Skipped core-hidden-only tab in UI Rule save")
                continue
            rows.append(("tab", sec, None))

    if invalid:
        details = "\n".join([f"- {e.get('field') or e.get('tab')}: {e['reason']}" for e in invalid])
        frappe.throw(f"Some rules are invalid and cannot be saved:\n{details}", title="Invalid UI Rules")

    # Guard: Active needs Factory first
    if not as_factory and not factory_exists(role, doctype):
        frappe.throw("Please save <b>Factory Defaults</b> first.")

    # Create/get parent doc only when allowed
    doc = _get_pair_doc(role, doctype)
    if not doc:
        if as_factory:
            doc = frappe.get_doc({
                "doctype": "UI Settings",
                "role": role,
                "doctype_name": doctype
            }).insert(ignore_permissions=True)
        else:
            # Should never happen due to guard
            frappe.throw("Please save <b>Factory Defaults</b> first.")

    # Replace only the targeted set
    if as_factory:
        doc.set("rules", [r for r in (doc.rules or []) if not r.is_factory])
    else:
        doc.set("rules", [r for r in (doc.rules or []) if r.is_factory])

    # Write collected rows
    for _, sec, fld in rows:
        ch = doc.append("rules", {})
        ch.role = role
        ch.doctype_name = doctype
        ch.section_fieldname = sec
        ch.fieldname = fld
        ch.hide = 1
        ch.is_factory = 1 if as_factory else 0

    doc.save(ignore_permissions=True)

    # If Factory save resulted in 0 factory rows, insert a harmless anchor row
    if as_factory and not any(r for r in (doc.rules or []) if r.is_factory):
        anchor_field = next(iter(mandatory_fields), None) or next(iter(core_hidden_fields), None)
        if anchor_field:
            ch = doc.append("rules", {})
            ch.role = role
            ch.doctype_name = doctype
            ch.section_fieldname = "Main"
            ch.fieldname = anchor_field
            ch.hide = 1
            ch.is_factory = 1
            doc.save(ignore_permissions=True)
            frappe.log_error(f"{doctype}.{anchor_field}", "UI Settings: inserted anchor factory row (empty payload)")

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
        ch.hide, ch.is_factory = r.hide, 0   # active clone

    doc.save(ignore_permissions=True)
    return {"ok": True}


@frappe.whitelist()
def get_effective_rules(doctype: str):
    """Return merged (union) UI rules for the current user across all their roles.

    Only consider parents with status != 'Inactive'.
    Also validate: never hide mandatory or core-hidden fields/tabs.
    """
    roles = frappe.get_roles(frappe.session.user)
    out = {"tabs": [], "fields": []}

    # validation context
    meta = frappe.get_meta(doctype)
    mandatory_fields  = {df.fieldname for df in meta.fields if df.reqd}
    core_hidden_fields = {df.fieldname for df in meta.fields if df.hidden}

    # 1) fetch ACTIVE parents (UI Settings docs)
    parents = frappe.get_all(
        "UI Settings",
        filters={"role": ["in", roles], "doctype_name": doctype, "status": ["!=", "Inactive"]},
        pluck="name",
    )
    if not parents:
        return out

    # 2) fetch child rules only from those parents
    rules = frappe.get_all(
        "UI Rule",
        filters={"parent": ["in", parents]},
        fields=["section_fieldname", "fieldname", "hide"],
    )

    for r in rules:
        if not r.get("hide"):
            continue
        if r.get("fieldname"):
            fn = r["fieldname"]
            if fn in mandatory_fields:
                frappe.log_error(f"{doctype}.{fn}", "UI Rule attempted to hide mandatory field")
                continue
            if fn in core_hidden_fields:
                frappe.log_error(f"{doctype}.{fn}", "UI Rule attempted to re-hide core-hidden field")
                continue
            out["fields"].append(fn)
        else:
            tab = r["section_fieldname"]
            # Determine tab's fields to ensure no mandatory fields inside
            tab_fields = [df.fieldname for df in meta.fields
                          if df.fieldtype not in ("Tab Break", "Column Break", "Section Break")]
            # Only block if the tab contains mandatory fields
            if any(fn in mandatory_fields for fn in tab_fields):
                frappe.log_error(f"{doctype}.{tab}", "UI Rule attempted to hide tab with mandatory fields")
                continue
            out["tabs"].append(tab)

    return out

@frappe.whitelist()
def get_ui_rules(doctype: str, role: str=None):
    # Compatibility wrapper
    from . import helpers_new  # or your new module
    return helpers_new.get_role_rules(role or frappe.session.user, doctype)

@frappe.whitelist()
def list_ui_settings():
    """Return all UI Settings rows (raw)."""
    return frappe.get_all("UI Settings", fields=["name", "role", "doctype_name"])

@frappe.whitelist()
def get_doctypes_for_role(doctype, txt="", searchfield=None, start=0, page_len=20, filters=None):
    """Return doctypes accessible by the given role, excluding system doctypes"""

    role = None
    if filters and isinstance(filters, dict):
        role = filters.get("role")

    if not role:
        return []

    # Step 1: base list from DocPerms (explicit permissions)
    doctypes = frappe.get_all("Custom DocPerm", filters={"role": role}, fields=["parent"], distinct=True)
    core = frappe.get_all("DocPerm", filters={"role": role}, fields=["parent"], distinct=True)
    out = {d["parent"] for d in doctypes + core}

    # Step 2: if Administrator → fallback to all doctypes
    if role == "Administrator":
        all_doctypes = frappe.get_all(
            "DocType",
            filters={
                "issingle": 0,
                "istable": 0,
                "hide_toolbar": 0
            },
            fields=["name"],
        )
        out = {d["name"] for d in all_doctypes}

    # Step 3: apply blacklist of system doctypes
    BLACKLIST = {
        "DocType", "Property Setter", "Patch Log", "Recorder", "Version",
        "Module Def", "Page", "Domain", "Custom Field", "Client Script",
        "Dashboard Chart Source", "Homepage", "RQ Job", "Transaction Log",
        "Website Theme"
    }
    out = sorted(d for d in out if d not in BLACKLIST)

    # Step 4: filter by txt if provided
    if not txt:
        return [(d, d) for d in out]

    txt = str(txt).lower()
    return [(d, d) for d in out if txt in d.lower()]

def role_has_doctype(role, doctype):
    return frappe.db.exists("DocPerm", {"role": role, "parent": doctype}) or \
           frappe.db.exists("Custom DocPerm", {"role": role, "parent": doctype})
