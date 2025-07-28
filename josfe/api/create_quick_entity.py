import frappe

def sync_customer_supplier(doc, method):
	if doc.doctype not in ["Customer", "Supplier"]:
		return

	# Determine dynamic labels
	is_customer = doc.doctype == "Customer"
	full_name = doc.customer_name if is_customer else doc.supplier_name
	link_doctype = doc.doctype
	link_name = doc.name

	# === 1. MAIN ADDRESS SYNC ===
	city = doc.get("custom_jos_city2")
	dirc = doc.get("custom_jos_direccion")
	country = doc.get("custom_jos_country")
	main_address_title = f"Main Address for {full_name}"

	if city and dirc and country:
		# Try to find the main address by title
		addr_name = frappe.db.get_value("Address", {"address_title": main_address_title})
		if addr_name:
			addr = frappe.get_doc("Address", addr_name)
		else:
			addr = frappe.new_doc("Address")
			addr.address_title = main_address_title
			addr.address_type = "Billing"
			addr.is_primary_address = 1
			addr.links = []
			addr.append("links", {
				"link_doctype": link_doctype,
				"link_name": link_name
			})

		addr.address_line1 = dirc
		addr.city = city
		addr.country = country
		addr.is_primary_address = 1
		addr.save(ignore_permissions=True)

	# === 2. MAIN CONTACT SYNC (Customer + Supplier) ===
	emails = doc.get("custom_jos_emails", [])
	phones = doc.get("custom_jos_telefonos", [])
	main_contact_name = f"Main Contact for {full_name}"

	# Try to find the contact by name
	contact_name = frappe.db.get_value("Contact", {"first_name": main_contact_name})
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
	else:
		contact = frappe.new_doc("Contact")
		contact.first_name = main_contact_name
		contact.is_primary_contact = 1
		contact.links = []
		contact.append("links", {
			"link_doctype": link_doctype,
			"link_name": link_name
		})

	# Replace emails and phones
	contact.email_ids = []
	contact.phone_nos = []

	for i, row in enumerate(emails):
		if hasattr(row, "email_id") and row.email_id:
			contact.append("email_ids", {
				"email_id": row.email_id,
				"is_primary": 1 if i == 0 else 0
			})

	# Ojo Aqui pusimos la lógica para que se syncronice la extensión y whatsapp 
	for i, row in enumerate(phones):
		if hasattr(row, "phone") and row.phone:
			contact.append("phone_nos", {
				"phone": row.phone,
				"is_primary_phone": 1 if i == 0 else 0,
				"jos_phone_ext": getattr(row, "jos_phone_ext", None), #extension
				"jos_whatsapp": getattr(row, "jos_whatsapp", 0) #whatsapp
			})

	contact.save(ignore_permissions=True)

	# === 3. Reverse Sync (Main Address → Custom Fields) ===
	addr_name = frappe.db.get_value("Address", {"address_title": main_address_title})
	if addr_name:
		addr = frappe.get_doc("Address", addr_name)
		updated = False
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
