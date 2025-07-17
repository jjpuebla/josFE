import frappe

def create_linked_address(doc, method):
    # ========= 1. CREATE ADDRESS IF NOT LINKED ==========
    if doc.custom_jos_city2 and doc.custom_jos_direccion and doc.custom_jos_country:
        if not frappe.db.exists("Dynamic Link", {
            "link_doctype": "Customer",
            "link_name": doc.name,
            "parenttype": "Address"
        }):
            address = frappe.get_doc({
                "doctype": "Address",
                "address_title": doc.customer_name or "Auto",
                "address_type": "Billing",
                "city": doc.custom_jos_city2,
                "address_line1": doc.custom_jos_direccion,
                "country": doc.custom_jos_country,
                "links": [{
                    "link_doctype": "Customer",
                    "link_name": doc.name
                }]
            })
            address.insert(ignore_permissions=True)

    # ========= 2. SYNC ADDRESS → CUSTOMER CUSTOM FIELDS ==========
    address_links = frappe.get_all(
        "Dynamic Link",
        filters={
            "link_doctype": "Customer",
            "link_name": doc.name,
            "parenttype": "Address"
        },
        fields=["parent"],
        limit=1
    )

    updated = False

    if address_links:
        address = frappe.get_doc("Address", address_links[0]["parent"])

        if address.city and doc.custom_jos_city2 != address.city:
            doc.custom_jos_city2 = address.city
            updated = True

        if address.address_line1 and doc.custom_jos_direccion != address.address_line1:
            doc.custom_jos_direccion = address.address_line1
            updated = True

        if address.country and doc.custom_jos_country != address.country:
            doc.custom_jos_country = address.country
            updated = True

    # ========= 3. SYNC customer_name → custom_jos_nombre_cliente ==========
    if doc.customer_name and doc.custom_jos_nombre_cliente != doc.customer_name:
        doc.custom_jos_nombre_cliente = doc.customer_name
        updated = True

    if updated:
        doc.db_update()

    # ========= 4. CREATE CONTACT IF NOT LINKED ==========
    if not frappe.db.exists("Dynamic Link", {
        "link_doctype": "Customer",
        "link_name": doc.name,
        "parenttype": "Contact"
    }):
        contact = frappe.get_doc({
            "doctype": "Contact",
            "first_name": doc.customer_name,
            "is_primary_contact": 1,
            "links": [{
                "link_doctype": "Customer",
                "link_name": doc.name
            }],
            "email_ids": [],
            "phone_nos": []
        })

        # ========= 5. COPY EMAILS FROM custom_jos_emails ==========
        for row in doc.get("custom_jos_emails") or []:
            if hasattr(row, 'email_id') and row.email_id:
                contact.append("email_ids", {
                    "email_id": row.email_id,
                    "is_primary": 1 if len(contact.email_ids) == 0 else 0
                })

        # ========= 6. COPY PHONES FROM custom_jos_telefonos ==========
        for row in doc.get("custom_jos_telefonos") or []:
            if hasattr(row, 'phone') and row.phone:
                contact.append("phone_nos", {
                    "phone": row.phone,
                    "is_primary_phone": 1 if len(contact.phone_nos) == 0 else 0
                })

        contact.insert(ignore_permissions=True)
