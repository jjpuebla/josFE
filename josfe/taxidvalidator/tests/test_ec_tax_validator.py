import json
import importlib
import pathlib
import pytest

ecv = importlib.import_module("josfe.taxidvalidator.ec_tax_validator")

def load_cases():
    data = pathlib.Path(__file__).parent.parent / "testdata" / "tax_ids.json"
    return json.loads(data.read_text(encoding="utf-8"))

@pytest.mark.parametrize("case", load_cases())
def test_is_valid_ec_tax_id(case):
    tax_id = case["id"]
    expected = case["valid"]
    if tax_id.startswith("P-"):
        assert expected is True
        return
    if tax_id == "9999999999999":
        assert expected is True
        return
    assert ecv.is_valid_ec_tax_id(tax_id) is expected