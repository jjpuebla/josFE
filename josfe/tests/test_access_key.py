# -*- coding: utf-8 -*-
import unittest
from josfe.sri_invoicing.validations.access_key import generate_access_key

class TestAccessKey(unittest.TestCase):
    def test_sample_key(self):
        """Check that claveAcceso is 49 digits and ends with correct DV."""
        clave = generate_access_key(
            fecha_emision_ddmmyyyy="06012016",
            cod_doc="01",
            ruc="1760013210001",
            ambiente="1",
            estab="001",
            pto_emi="123",
            secuencial_9d="000000008",
            codigo_numerico_8d="12345678",
            tipo_emision="1",
        )
        self.assertEqual(len(clave), 49)
        self.assertTrue(clave.endswith("7"))
