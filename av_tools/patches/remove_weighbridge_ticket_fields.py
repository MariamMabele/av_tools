import frappe

def execute():
    doctypes = [
        "Sales Invoice",
        "Delivery Note",
        "Sales Order",
        "Purchase Invoice",
        "Purchase Order",
        "Purchase Receipt"
    ]
    
    for dt in doctypes:
        custom_field = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": "weighbridge_ticket"})
        if custom_field:
            frappe.delete_doc("Custom Field", custom_field, force=1)
            
    frappe.clear_cache()
