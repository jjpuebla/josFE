# -*- coding: utf-8 -*-
import json
import functools
import frappe
from pymysql.err import OperationalError
from frappe.utils import now_datetime, has_common
from frappe.exceptions import DuplicateEntryError

# =========================
# Constants & simple utils
# =========================
FIELD_BY_TYPE = {
    "Factura": "seq_factura",
    "Nota de Crédito": "seq_nc",
    "Nota de Débito": "seq_nd",
    "Comprobante Retención": "seq_ret",
    "Liquidación Compra": "seq_liq",
    "Guía de Remisión": "seq_gr",
    # 🔑 aliases for short codes
    "FC": "Nota Credito FE",
    "NC": "seq_nc",
}

PRIV_ROLES = {"System Manager", "Accounts Manager"}
CHILD_DOCTYPE = "SRI Puntos Emision"
CHILD_TABLE = f"`tab{CHILD_DOCTYPE}`"
WAREHOUSE = "Warehouse"

# Candidate child-table fieldnames on Warehouse
WAREHOUSE_CHILD_FIELDS = (
    "custom_jos_SRI_puntos_emision",
    "custom_jos_Sri_puntos_emision",
    "custom_sri_puntos_emision",
)

SELECT_COLS = """
    name, parent, emission_point_code, estado,
    seq_factura, seq_nc, seq_nd, seq_ret, seq_liq, seq_gr, initiated
"""

def _zpad3(s: str) -> str:
    return str(s or "").strip().zfill(3)


# =========================
# Cached metadata helpers
# =========================
@functools.lru_cache(maxsize=1)
def _active_estado_value() -> str:
    """Return the exact 'active' option for CHILD_DOCTYPE.estado (cached)."""
    try:
        meta = frappe.get_meta(CHILD_DOCTYPE)
        fld = meta.get_field("estado")
        opts = [(o or "").strip() for o in (fld.options or "").splitlines() if (o or "").strip()]
        for cand in opts:
            if cand.lower() in ("activo", "activa", "active"):
                return cand
        return opts[0] if opts else "Activo"
    except Exception:
        return "Activo"

@functools.lru_cache(maxsize=1)
def _has_last_adjust_note() -> bool:
    try:
        return bool(frappe.get_meta(CHILD_DOCTYPE).get_field("last_adjust_note"))
    except Exception:
        return False

@functools.lru_cache(maxsize=1)
def _choose_parentfield_for_wh() -> str:
    """Pick the real child table field on Warehouse that points to CHILD_DOCTYPE (cached)."""
    meta = frappe.get_meta(WAREHOUSE)
    for f in WAREHOUSE_CHILD_FIELDS:
        df = meta.get_field(f)
        if df and df.fieldtype == "Table" and (df.options or "").strip() == CHILD_DOCTYPE:
            return f
    return WAREHOUSE_CHILD_FIELDS[0]  # fallback


# =========================
# Permissions & Warehouse
# =========================
def _require_privileged():
    roles = set(frappe.get_roles(frappe.session.user))
    if not has_common(list(PRIV_ROLES), list(roles)):
        frappe.throw("You do not have permission to adjust sequentials. Contact a System Manager.")

def _get_establishment_code(warehouse_name: str) -> str:
    est = (frappe.get_cached_value(WAREHOUSE, warehouse_name, "custom_establishment_code") or "").strip()
    if not est:
        frappe.throw(f"Warehouse '{warehouse_name}' has no establishment code (custom_establishment_code).")
    return _zpad3(est)

def _intended_child_name(warehouse_name: str, emission_point_code: str) -> str:
    """Global-unique, human-friendly: <EST>-<EP>."""
    return f"{_get_establishment_code(warehouse_name)}-{_zpad3(emission_point_code)}"


# =========================
# DB helpers (with locking)
# =========================
def _row_by_name_locked(row_name: str):
    if not row_name:
        return None
    rows = frappe.db.sql(
        f"SELECT {SELECT_COLS} FROM {CHILD_TABLE} WHERE name=%s FOR UPDATE",
        (row_name,),
        as_dict=True,
    )
    return rows[0] if rows else None

def _find_row_in_same_warehouse_locked(warehouse_name: str, emission_point_code: str):
    """Find one row for this Warehouse + EP and lock it."""
    pf = _choose_parentfield_for_wh()
    target = _zpad3(emission_point_code)
    rows = frappe.db.sql(
        f"""
        SELECT {SELECT_COLS}
        FROM {CHILD_TABLE}
        WHERE parent=%s
          AND parenttype='{WAREHOUSE}'
          AND parentfield=%s
          AND LPAD(TRIM(emission_point_code), 3, '0')=%s
        FOR UPDATE
        """,
        (warehouse_name, pf, target),
        as_dict=True,
    )
    return rows[0] if rows else None

def _get_active_row_by_parent_code_locked(warehouse_name: str, emission_point_code: str):
    pf = _choose_parentfield_for_wh()
    target = _zpad3(emission_point_code)
    rows = frappe.db.sql(
        f"""
        SELECT {SELECT_COLS}
        FROM {CHILD_TABLE}
        WHERE parent=%s
          AND parenttype='{WAREHOUSE}'
          AND parentfield=%s
          AND LPAD(TRIM(emission_point_code), 3, '0')=%s
          AND UPPER(TRIM(estado))='ACTIVO'
        FOR UPDATE
        """,
        (warehouse_name, pf, target),
        as_dict=True,
    )
    if not rows:
        frappe.throw(f"No active emission point {target} in Warehouse {warehouse_name}.")
    return rows[0]


# =========================
# Insert / Upsert logic
# =========================
def _insert_child_row(warehouse_name: str, emission_point_code: str):
    """
    Insert child row for THIS Warehouse with name = "<EST>-<EP>".
    If the name exists:
      - If it already belongs to this Warehouse, reuse it.
      - Else append a short hash suffix and keep it.
    """
    pf = _choose_parentfield_for_wh()
    target = _zpad3(emission_point_code)
    intended_name = _intended_child_name(warehouse_name, target)

    child = frappe.get_doc({
        "doctype": CHILD_DOCTYPE,
        "name": intended_name,
        "parent": warehouse_name,
        "parenttype": WAREHOUSE,
        "parentfield": pf,
        "emission_point_code": target,
        "estado": _active_estado_value(),
        "seq_factura": 0, "seq_nc": 0, "seq_nd": 0, "seq_ret": 0, "seq_liq": 0, "seq_gr": 0,
        "initiated": 0,
    })
    child.flags.name_set = True  # enforce our own name (bypass autoname)

    try:
        child.insert(ignore_permissions=True)
        return _row_by_name_locked(child.name)
    except DuplicateEntryError:
        # First, see if a row with the same (Warehouse + EP) already exists — reuse it.
        existing_same_parent = _find_row_in_same_warehouse_locked(warehouse_name, emission_point_code)
        if existing_same_parent:
            return existing_same_parent
        # Otherwise, conflict on name only (e.g., reused name). Create a unique name.
        child.name = f"{intended_name}-{frappe.generate_hash(length=8)}"
        child.flags.name_set = True
        child.insert(ignore_permissions=True)
        return _row_by_name_locked(child.name)

def _get_or_create_row_by_parent_code_locked(warehouse_name: str, emission_point_code: str):
    return _find_row_in_same_warehouse_locked(warehouse_name, emission_point_code) or \
           _insert_child_row(warehouse_name, emission_point_code)


# =========================
# Logging & retries
# =========================
def _log(warehouse, emission_point_code, doc_type, action, old_val, new_val, note=""):
    frappe.get_doc({
        "doctype": "SRI Secuencial Log",
        "warehouse": warehouse,
        "emission_point_code": emission_point_code,
        "doc_type": doc_type,           # Factura, Retención, etc.
        "action": action,               # INIT / EDIT / AUTO
        "old_value": int(old_val),
        "new_value": int(new_val),
        "note": note,
        "by_user": frappe.session.user,
        "when": now_datetime(),
    }).insert(ignore_permissions=True)

def _with_retry(fn, *args, **kwargs):
    """Retry on deadlock/lock-wait (1205/1213)."""
    for attempt in range(3):
        try:
            return fn(*args, **kwargs)
        except OperationalError as e:
            code = e.args[0] if e.args else None
            if code in (1205, 1213) and attempt < 2:
                frappe.db.rollback()
                continue
            raise


# =========================
# Public APIs
# =========================
@frappe.whitelist()
def initiate_or_edit(
    warehouse_name: str,
    row_name: str | None = None,
    updates_dict=None,
    note: str = "",
    emission_point_code: str | None = None,
    establishment_code: str | None = None,
):
    """
    INIT (initiated=0): set provided seq_* and mark initiated=1 (UI enforces all six ≥ 1).
    EDIT (initiated=1): allow equal, block lower.
    If row_name is missing (brand-new UI row), resolve/create by (warehouse, emission point).
    """
    _require_privileged()

    if isinstance(updates_dict, str):
        updates_dict = json.loads(updates_dict or "{}")
    updates_dict = updates_dict or {}

    #**********log************/
    frappe.log_error(
    title="SRI DEBUG RAW INPUT",
    message=f"Received updates_dict={updates_dict}"
)
    #**********log************/

    # Ensure Warehouse has establishment_code
    if establishment_code:
        establishment_code = (establishment_code or "").strip()
        if establishment_code.isdigit() and len(establishment_code) == 3:
            current = (frappe.get_cached_value("Warehouse", warehouse_name, "custom_establishment_code") or "").strip()
            if not current:
                frappe.db.set_value("Warehouse", warehouse_name, "custom_establishment_code", establishment_code, update_modified=False)
                frappe.clear_document_cache("Warehouse", warehouse_name)

    def inner():
        row = _row_by_name_locked(row_name) if row_name else None
        if not row:
            if not emission_point_code:
                frappe.throw("Emission point row not found (missing emission_point_code).")
            row = _get_or_create_row_by_parent_code_locked(warehouse_name, emission_point_code)

        if row["parent"] != warehouse_name:
            frappe.throw("The selected row does not belong to this Warehouse.")

        action = "EDIT" if int(row.get("initiated") or 0) else "INIT"
        updates = {}

        for doc_type, new_val in updates_dict.items():
            field = FIELD_BY_TYPE.get(doc_type)
            if not field:
                frappe.throw(f"Unsupported doc_type: {doc_type}")

            try:
                next_val = int(new_val)
            except Exception:
                frappe.throw(f"{doc_type}: value must be an integer.")

            if next_val < 1:
                frappe.throw(f"{doc_type}: next value must be ≥ 1.")

            # "next to issue" in UI → store "current" internally
            proposed_current = next_val
            old_val = int(row.get(field) or 0)

            if action == "EDIT":
                if proposed_current < old_val:
                    frappe.throw(f"{doc_type}: new value {next_val} would lower current to {proposed_current} (< {old_val}).")
                if proposed_current == old_val:
                    continue

            updates[field] = proposed_current
            _log(warehouse_name, row.get("emission_point_code"), doc_type, action, old_val, proposed_current, note)

        frappe.log_error(
            title="SRI DEBUG initiate_or_edit",
            message=f"Row={row['name']} Action={action} Updates={updates}"
        )


        # Apply updates
        if updates:
            for field, new_current in updates.items():
                frappe.db.set_value(CHILD_DOCTYPE, row["name"], field, new_current, update_modified=False)

        frappe.log_error(
            title="SRI DEBUG initiate_or_edit",
            message=f"DB.set_value applied for {row['name']} Fields={list(updates.keys())}"
        )



        # Always mark as initiated
        frappe.db.set_value(CHILD_DOCTYPE, row["name"], "initiated", 1, update_modified=False)

        # Do NOT force estado to Activo — keep whatever the row already has.
        # Only normalize empty/null values to "Inactivo".
        current_estado = (row.get("estado") or "").strip().lower()
        if current_estado in ("", "none", "null"):
            frappe.db.set_value(CHILD_DOCTYPE, row["name"], "estado", "Inactivo", update_modified=False)

        #********LOG
        latest = _row_by_name_locked(row["name"])
        frappe.log_error(
            title="SRI DEBUG initiate_or_edit",
            message=f"Returning row values: {latest}"
        )
        return latest


        # Return the fresh row
        return _row_by_name_locked(row["name"])

    # ✅ FIX: actually run inner() inside retry wrapper
    return _with_retry(inner)


@frappe.whitelist()
def next_sequential(warehouse_name: str, emission_point_code: str, doc_type: str) -> int:
    """
    Allocate the next sequential (post-increment semantics):

    - Stored field (seq_*) means "next to issue".
    - We return the CURRENT stored value as the assigned number,
      then increment the stored value by +1.
    """
    field = FIELD_BY_TYPE.get(doc_type)
    if not field:
        frappe.throw(f"Unsupported doc_type: {doc_type}")

    def inner():
        row = _get_active_row_by_parent_code_locked(warehouse_name, emission_point_code)

        # If somehow empty/zero, treat as 1 (first issue)
        current_next = int(row.get(field) or 1)

        # Assign this one
        assigned = current_next

        # And move the counter forward
        new_next = current_next + 1
        frappe.db.set_value(CHILD_DOCTYPE, row["name"], field, new_next, update_modified=False)

        _log(
            warehouse_name,
            row.get("emission_point_code"),
            doc_type,
            "AUTO",
            current_next,           # old "next to issue"
            new_next,               # new "next to issue"
            "issue & post-increment"
        )
        return assigned

    return _with_retry(inner)

@frappe.whitelist()
def peek_next(warehouse_name: str, emission_point_code: str, doc_type: str) -> int:
    """
    Read-only preview: returns the stored "next to issue" without writing.
    Requires emission point ACTIVO.
    """
    field = FIELD_BY_TYPE.get(doc_type)
    if not field:
        frappe.throw(f"Unsupported doc_type: {doc_type}")

    row = _get_active_row_by_parent_code_locked(warehouse_name, emission_point_code)

    # If unset/zero, consider the first issue will be 1
    return int(row.get(field) or 1)

@frappe.whitelist()
def level3_warehouse_link_query(doctype, txt, searchfield, start, page_len, filters):
    """
    Link search for Sales Invoice -> custom_jos_level3_warehouse.
    Criteria:
      - custom_sri_is_establishment = 1 (your flag)
      - has Establishment Code (EC)
      - has at least one ACTIVE/ACTIVO PE row (estado normalized)
      - text search on name/warehouse_name
    NOTE: We do NOT filter on is_group; level-3 may be groups (parents of level-4).
    """
    return frappe.db.sql("""
        SELECT w.name
        FROM `tabWarehouse` w
        WHERE COALESCE(w.custom_sri_is_establishment, 0) = 1
          AND COALESCE(w.custom_establishment_code, '') <> ''
          AND EXISTS (
                SELECT 1
                FROM `tabSRI Puntos Emision` pe
                WHERE pe.parent = w.name
                  AND TRIM(UPPER(COALESCE(pe.estado,''))) IN ('ACTIVO','ACTIVE')
          )
          AND (w.name LIKE %(kw)s OR w.warehouse_name LIKE %(kw)s)
        ORDER BY w.modified DESC
        LIMIT %(start)s, %(page_len)s
    """, {
        "kw": f"%{txt or ''}%",
        "start": start, "page_len": page_len
    })


@frappe.whitelist()
def list_active_emission_points(warehouse_name: str):
    if not warehouse_name:
        return []

    rows = frappe.get_all(
        "SRI Puntos Emision",
        filters={
            "parent": warehouse_name,
            "estado": ["in", ["Activo", "ACTIVO", "ACTIVE"]],
        },
        fields=["emission_point_code"]  # ← only this; 'descripcion' doesn't exist
    )

    out = []
    for r in rows:
        code = str(r.get("emission_point_code") or "").strip().zfill(3)
        out.append({"code": code})  # ← no label; simple and safe
    return out