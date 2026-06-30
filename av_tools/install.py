import frappe


def before_install():
	"""
	Some modules were previously owned by csf_tz. They have been moved to av_tools.
	On sites where csf_tz was installed first, these Module Defs (e.g. AuthOTP, Feedback)
	already exist in the database. Delete them here so Frappe can re-register them
	cleanly under av_tools without hitting a duplicate primary key error.

	On fresh sites where they do not exist yet, this is a no-op.
	"""
	try:
		modules = frappe.get_module_list("av_tools")
	except Exception:
		modules = ["Av Tools", "Weigh Bridge", "AuthOTP", "Feedback", "AI Integration", "Compliance", "Trade In"]

	for module in modules:
		if frappe.db.exists("Module Def", module):
			frappe.db.delete("Module Def", {"name": module})
			
	frappe.db.commit()
