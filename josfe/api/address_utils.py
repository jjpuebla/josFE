import frappe

@frappe.whitelist()
def get_linked_address(doctype, name):
    result = frappe.db.sql("""
        SELECT parent
        FROM `tabDynamic Link`
        WHERE parenttype = 'Address'
        AND link_doctype = %s
        AND link_name = %s
        LIMIT 1
    """, (doctype, name), as_dict=True)

    return result[0].parent if result else None
