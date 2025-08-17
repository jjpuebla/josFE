import frappe

def sync_customer_supplier(doc, method):
    # Show confirmation that the hook was triggered
    frappe.msgprint("✅ sync_customer_supplier called")

    # Only apply this logic for Customer or Supplier Doctypes
    if doc.doctype not in ["Customer", "Supplier"]:
        return

    # Determine the entity type and relevant names
    is_customer = doc.doctype == "Customer"
    full_name = doc.customer_name if is_customer else doc.supplier_name
    link_doctype = doc.doctype
    link_name = doc.name

    # === 1. MAIN ADDRESS SYNC ===
    city = doc.get("custom_jos_city2")
    dirc = doc.get("custom_jos_direccion")
    country = doc.get("custom_jos_country")
    main_address_title = f"Main Address for {full_name}"

    # Debug info for address fields
    frappe.msgprint(f"📦 Address fields → City: {city}, Dir: {dirc}, Country: {country}")

    # Only proceed if all address fields are provided
    if city and dirc and country:
        # Try to find an existing address with this title
        addr_name = frappe.db.get_value("Address", {"address_title": main_address_title})
        if addr_name:
            addr = frappe.get_doc("Address", addr_name)
            frappe.msgprint("🛠️ Updating existing address")
        else:
            # Create a new address
            addr = frappe.new_doc("Address")
            addr.address_title = main_address_title
            addr.address_type = "Billing"
            addr.is_primary_address = 1
            addr.links = []
            addr.append("links", {
                "link_doctype": link_doctype,
                "link_name": link_name
            })
            frappe.msgprint("➕ Creating new address")

        # Update address content
        addr.address_line1 = dirc
        addr.city = city
        addr.country = country
        addr.is_primary_address = 1
        addr.save(ignore_permissions=True)
    else:
        frappe.msgprint("❌ No se creará dirección. Falta uno de los campos obligatorios.")

    # === 2. MAIN CONTACT SYNC ===
    emails = doc.get("custom_jos_emails", [])
    phones = doc.get("custom_jos_telefonos", [])
    main_contact_name = f"Main Contact for {full_name}"

    # Debug info for contact data
    frappe.msgprint(f"📞 Contact data → Emails: {len(emails)}, Phones: {len(phones)}")

    # Try to find an existing contact
    contact_name = frappe.db.get_value("Contact", {"first_name": main_contact_name})
    if contact_name:
        contact = frappe.get_doc("Contact", contact_name)
        frappe.msgprint("🛠️ Updating existing contact")
    else:
        # Create a new contact
        contact = frappe.new_doc("Contact")
        contact.first_name = main_contact_name
        contact.is_primary_contact = 1
        contact.links = []
        contact.append("links", {
            "link_doctype": link_doctype,
            "link_name": link_name
        })
        frappe.msgprint("➕ Creating new contact")

    # Clear any existing emails and phone numbers
    contact.email_ids = []
    contact.phone_nos = []

    # Add new email rows
    for i, row in enumerate(emails):
        if hasattr(row, "email_id") and row.email_id:
            contact.append("email_ids", {
                "email_id": row.email_id,
                "is_primary": 1 if i == 0 else 0
            })

    # Add new phone rows including extension and WhatsApp flag
    for i, row in enumerate(phones):
        if hasattr(row, "phone") and row.phone:
            contact.append("phone_nos", {
                "phone": row.phone,
                "is_primary_phone": 1 if i == 0 else 0,
                "jos_phone_ext": getattr(row, "jos_phone_ext", None),
                "jos_whatsapp": getattr(row, "jos_whatsapp", 0)
            })

    contact.save(ignore_permissions=True)

    # === 3. REVERSE SYNC (Address → Custom Fields) ===
    addr_name = frappe.db.get_value("Address", {"address_title": main_address_title})
    if addr_name:
        addr = frappe.get_doc("Address", addr_name)
        updated = False

        # Update doc fields if different from stored address
        if addr.city and addr.city != doc.get("custom_jos_city2"):
            doc.custom_jos_city2 = addr.city
            updated = True
        if addr.address_line1 and addr.address_line1 != doc.get("custom_jos_direccion"):
            doc.custom_jos_direccion = addr.address_line1
            updated = True
        if addr.country and addr.country != doc.get("custom_jos_country"):
            doc.custom_jos_country = addr.country
            updated = True

        if updated:
            doc.db_update()
            frappe.msgprint("🔄 Campos custom actualizados desde la dirección principal")
