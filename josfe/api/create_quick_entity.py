import frappe

def sync_customer_supplier(doc, method):
	# frappe.msgprint("✅ sync_customer_supplier called")

	if doc.doctype not in ["Customer", "Supplier"]:
		return

	is_customer = doc.doctype == "Customer"
	full_name = doc.customer_name if is_customer else doc.supplier_name
	link_doctype = doc.doctype
	link_name = doc.name
	prefix = "Clte" if is_customer else "Prov"

	# === 1. MAIN ADDRESS ===
	city = doc.get("custom_jos_city2")
	dirc = doc.get("custom_jos_direccion")
	country = doc.get("custom_jos_country")
	main_address_title = f"Main Dir. para {prefix}-{link_name}"
	# frappe.msgprint(f"📦 Address fields → City: {city}, Dir: {dirc}, Country: {country}")

	if city and dirc and country:
		addr_name = frappe.db.get_value("Address", {"address_title": main_address_title})
		if addr_name:
			addr = frappe.get_doc("Address", addr_name)
			# frappe.msgprint("🛠️ Updating existing address")
		else:
			addr = frappe.new_doc("Address")
			addr.address_title = main_address_title
			addr.address_type = "Billing"
			addr.is_primary_address = 1
			addr.append("links", {"link_doctype": link_doctype, "link_name": link_name})
			# frappe.msgprint("➕ Creating new address")

		addr.address_line1 = dirc
		addr.city = city
		addr.country = country
		addr.is_primary_address = 1
		addr.flags.ignore_permissions = True
		addr.save()

	# === 2. MAIN CONTACT ===
	emails = doc.get("custom_jos_emails", [])
	phones = doc.get("custom_jos_telefonos", [])
	main_contact_name = f"Main Contact {prefix}-{link_name}"
	# frappe.msgprint(f"📞 Contact data → Emails: {len(emails)}, Phones: {len(phones)}")

	contact_name = frappe.db.get_value("Contact", {"first_name": main_contact_name})
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		# frappe.msgprint("🛠️ Updating existing contact")
	else:
		contact = frappe.new_doc("Contact")
		contact.first_name = main_contact_name
		contact.is_primary_contact = 1
		contact.append("links", {"link_doctype": link_doctype, "link_name": link_name})
		# frappe.msgprint("➕ Creating new contact")

	contact.email_ids = []
	contact.phone_nos = []

	for i, row in enumerate(emails):
		if hasattr(row, "email_id") and row.email_id:
			contact.append("email_ids", {
				"email_id": row.email_id,
				"is_primary": 1 if i == 0 else 0
			})

	for i, row in enumerate(phones):
		if hasattr(row, "phone") and row.phone:
			contact.append("phone_nos", {
				"phone": row.phone,
				"is_primary_phone": 1 if i == 0 else 0,
				"jos_phone_ext": getattr(row, "jos_phone_ext", None),
				"jos_whatsapp": getattr(row, "jos_whatsapp", 0)
			})

	contact.flags.ignore_permissions = True
	contact.save()

	# === 3. SYNC BACK TO CUSTOM FIELDS ===
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
			# frappe.msgprint("🔁 Syncing address back to custom fields")
			doc.db_update()
