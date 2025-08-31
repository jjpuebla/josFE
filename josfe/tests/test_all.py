# -*- coding: utf-8 -*-
"""
Aggregate runner to ensure all josfe.sri_invoicing tests are picked up,
even when running `bench run-tests --app josfe`.
"""

import unittest
import logging

# Import our test modules
from .test_access_key import TestAccessKey
from .test_factura_xml import TestFacturaXML

# Configure a simple logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestLog(unittest.TestCase):
    def test_log_exists(self):
        """Simple sanity check that logging works."""
        logger.info("josfe.sri_invoicing test suite is running…")
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
