import frappe
from josfe.sri_invoicing.numbering import state

def test_initiate_or_edit():
    # Make sure you replace with a real warehouse name that has sri_is_establishment=1
    warehouse_name = "Sucursal Mariscal - A"

    # Simulate INIT: Factura=1
    res = state.initiate_or_edit(
        warehouse_name=warehouse_name,
        row_name=None,
        emission_point_code="001",
        establishment_code="001",
        updates_dict={"Factura": 1},
        note="Test INIT"
    )
    print("INIT result:", res)

    # Simulate issuing 182 invoices (i.e., manually set next available to 183)
    res = state.initiate_or_edit(
        warehouse_name=warehouse_name,
        emission_point_code="001",
        establishment_code="001",
        updates_dict={"Factura": 183},
        note="Test jump to 183"
    )
    print("After 182 invoices, next available =", res)

    # Simulate trying to go backwards
    try:
        res = state.initiate_or_edit(
            warehouse_name=warehouse_name,
            emission_point_code="001",
            establishment_code="001",
            updates_dict={"Factura": 150},
            note="Test invalid back"
        )
        print("Unexpected success:", res)
    except Exception as e:
        print("Correctly blocked lowering:", str(e))
