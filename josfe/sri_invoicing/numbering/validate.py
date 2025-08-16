import frappe

def daily_check():
    """
    Minimal sanity scan:
      - Every active row must have non-negative integers.
      - initiated rows should not be empty.
    Extend to compare against issued docs if you want deeper integrity checks.
    """
    table = "`tabSRI Puntos Emision`"
    rows = frappe.db.sql(
        f"""SELECT name, parent, emission_point_code, estado, initiated,
                   seq_factura, seq_nc, seq_nd, seq_ret, seq_liq, seq_gr
            FROM {table}
            WHERE UPPER(TRIM(estado))='ACTIVO'""",
        as_dict=True,
    )
    bad = []
    for r in rows:
        for f in ("seq_factura","seq_nc","seq_nd","seq_ret","seq_liq","seq_gr"):
            val = int(r.get(f) or 0)
            if val < 0:
                bad.append(f"{r['parent']}:{r['emission_point_code']} {f} < 0")
        if int(r.get("initiated") or 0) == 0:
            bad.append(f"{r['parent']}:{r['emission_point_code']} not initiated")
    if bad:
        frappe.log_error("\n".join(bad), "SRI daily_check")
