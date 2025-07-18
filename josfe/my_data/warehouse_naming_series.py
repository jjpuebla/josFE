import frappe

def handle_establecimientos(doc, method):
    if not doc.get("custom_jos_tabla_estab"):
        return

    for row in doc.custom_jos_tabla_estab:
        frappe.logger().info(f"Warehouse: {row.warehouse}, Naming Series: {row.naming_series}")
        # Example: You could validate format, or preload something here
        if not row.naming_series.endswith("-."):
            frappe.throw(f"Naming Series '{row.naming_series}' for warehouse '{row.warehouse}' must end with '-.'")
