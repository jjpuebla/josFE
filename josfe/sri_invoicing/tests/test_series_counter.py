import frappe
from frappe.tests.utils import FrappeTestCase
from josfe.sri_invoicing.core.numbering.state import peek_next, next_sequential

class TestSeriesCounter(FrappeTestCase):
    def test_post_increment_semantics(self):
        wh = frappe.get_all("Warehouse", filters={}, pluck="name")[0]
        pe_code = "001"

        # Set "next to issue" to 1
        rowname = frappe.db.get_value("SRI Puntos Emision",
            {"parent": wh, "emission_point_code": pe_code}, "name")
        self.assertTrue(rowname, "PE row not found")
        frappe.db.set_value("SRI Puntos Emision", rowname, "seq_factura", 1, update_modified=False)

        self.assertEqual(peek_next(wh, pe_code, "Factura"), 1)
        self.assertEqual(next_sequential(wh, pe_code, "Factura"), 1)  # assign 1
        self.assertEqual(peek_next(wh, pe_code, "Factura"), 2)
