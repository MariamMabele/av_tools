import json
import os

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


folder = "../patches/custom_fields/custom_fields_json"


def load_json(file):
    CURR_DIR = os.path.abspath(os.path.dirname(__file__))
    json_file_path = os.path.join(CURR_DIR, folder, file)
    with open(json_file_path, "r") as f:
        return json.load(f)


def create_fields_from_json(custom_fields_obj):
    disallowed_fields = [
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "idx",
        "is_system_generated",
        "__last_sync_on",
    ]

    doctype_custom_fields_dict = {}
    for custom_field in custom_fields_obj:
        doctype = custom_field["dt"]
        if not frappe.db.exists("DocType", doctype):
            continue

        all_fields = frappe.get_meta("Custom Field").get_valid_columns()
        field_list = set(all_fields).difference(disallowed_fields)
        custom_field_dict = {
            field_name: custom_field.get(field_name) for field_name in field_list
        }

        # Ensure module exists to avoid LinkValidationError
        module_name = custom_field_dict.get("module")
        if module_name and not frappe.db.exists("Module Def", module_name):
            frappe.get_doc({
                "doctype": "Module Def",
                "module_name": module_name,
                "app_name": "av_tools"
            }).insert(ignore_permissions=True)

        doctype_custom_fields_dict.setdefault(doctype, []).append(custom_field_dict)

    create_custom_fields(doctype_custom_fields_dict, update=True)


def execute():
    folder_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), folder)
    if not os.path.isdir(folder_path):
        return

    files = sorted(f for f in os.listdir(folder_path) if f.endswith(".json"))
    for file in files:
        data = load_json(file)
        create_fields_from_json(data)
