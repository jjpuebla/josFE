# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from josfe.sri_invoicing.xml.factura_builder import build_factura_xml

class TestFacturaXML(FrappeTestCase):
    def setUp(self):
        # Company
        if not frappe.db.exists("Company", {"company_name": "ACME SA"}):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": "ACME SA",
                "abbr": "AC",
                "default_currency": "USD",
                "country": "Ecuador",
                "tax_id": "1790012345001",
                "custom_jos_ruc": "1790012345001"  
            }).insert(ignore_permissions=True)

        # Customer
        if not frappe.db.exists("Customer", {"customer_name": "Cliente Prueba"}):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "Cliente Prueba",
                "customer_type": "Company",
                "tax_id": "1793226797001",
            }).insert(ignore_permissions=True)

        # Item
        if not frappe.db.exists("Item", {"item_code": "ITEM-001"}):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": "ITEM-001",
                "item_name": "Producto de Prueba",
                "is_stock_item": 0,
            }).insert(ignore_permissions=True)

        # Sales Invoice
        si = frappe.get_doc({
            "doctype": "Sales Invoice",
            "company": "ACME SA",
            "customer": "Cliente Prueba",
            "posting_date": "2025-01-06",
            "items": [{
                "item_code": "ITEM-001",
                "item_name": "Producto de Prueba",
                "qty": 1,
                "rate": 25,
                "item_tax_rate": "{\"IVA 12%\": 12.0}"
            }]
        })
        si.insert(ignore_permissions=True)
        si.submit()
        self.si_name = si.name

    def test_build_factura_xml(self):
        xml, meta = build_factura_xml(self.si_name)

        # Validate claveAcceso
        self.assertEqual(len(meta.get("clave_acceso", "")), 49)

        # Validate mandatory sections
        for tag in ["<factura", "<infoTributaria>", "<infoFactura>", "<detalles>", "<totalConImpuestos>"]:
            self.assertIn(tag, xml)

        # Validate totals
        self.assertIn("<totalSinImpuestos>25.00</totalSinImpuestos>", xml)
