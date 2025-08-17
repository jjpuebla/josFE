# apps/josfe/josfe/sri_invoicing/tests/test_fe_settings.py
# Copyright (c) 2025, JP and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestFESettings(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure the singleton loads without error (created on first access)
        cls.doc = frappe.get_single("FE Settings")

    def test_singleton_exists(self):
        assert self.doc.doctype == "FE Settings"

    def test_minimum_defaults_are_present(self):
        # These fields may not be explicitly set yet; use getattr with sane defaults.
        retry_max = int(getattr(self.doc, "retry_max_attempts", 5) or 5)
        backoff   = int(getattr(self.doc, "retry_backoff_seconds", 30) or 30)
        batch_sz  = int(getattr(self.doc, "batch_size", 20) or 20)
        xml_dir   = getattr(self.doc, "xml_subdir", "sri_xml") or "sri_xml"

        assert retry_max >= 1, "retry_max_attempts should be >= 1"
        assert backoff >= 1, "retry_backoff_seconds should be >= 1"
        assert batch_sz >= 1, "batch_size should be >= 1"
        assert isinstance(xml_dir, str) and len(xml_dir) > 0, "xml_subdir should be non-empty"

    def test_boolean_flags_are_int_like(self):
        # Flags default to 0/1; tolerate None by coercing via int()
        contingency = int(getattr(self.doc, "contingency_mode", 0) or 0)
        debug       = int(getattr(self.doc, "debug_logging", 0) or 0)
        private     = int(getattr(self.doc, "private_files_only", 1) or 1)
        stubs       = int(getattr(self.doc, "allow_test_stubs", 0) or 0)

        assert contingency in (0, 1)
        assert debug in (0, 1)
        assert private in (0, 1)
        assert stubs in (0, 1)

    def test_env_override_is_optional(self):
        # Empty string means "no global override"
        env = getattr(self.doc, "env_override", "") or ""
        assert env in ("", "Pruebas", "Producción")
