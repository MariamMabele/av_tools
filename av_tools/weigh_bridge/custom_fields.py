import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup_custom_fields():
    custom_fields = {
        "Vehicle": [
            {
                "fieldname": "default_tare_weight",
                "label": "Default Tare Weight",
                "fieldtype": "Float",
                "insert_after": "license_plate",
            }
        ],
    }

    create_custom_fields(custom_fields, update=True)
