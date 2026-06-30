frappe.pages["salary-calculator"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Salary Calculator",
		single_column: true,
	});
	frappe.breadcrumbs.add("HR");
	new SalaryCalculatorPage(page);
};

class SalaryCalculatorPage {
	constructor(page) {
		this.page = page;
		this.state = {
			salary_structure: "",
			employee: "",
			calculate_based_on: "Net Pay",
			gross_pay: 0,
			net_pay: 0,
		};
		this.structure_data = null;
		this.active_keys = new Set();
		this.earning_overrides = {};
		this.result = null;
		this.currency = "TZS";
		this._calc_timer = null;

		this.render_layout();
		this.create_fields();
	}

	// ── Layout ──────────────────────────────────────────────────────────

	render_layout() {
		this.page.main.addClass("salary-calculator-page").html(`
			<div class="sc-container">
				<div class="sc-left-panel">
					<div class="sc-card">
						<div class="sc-card-header">
							<h3 class="sc-card-title">Calculator Inputs</h3>
						</div>
						<div class="sc-card-body sc-fields"></div>
					</div>
					<div class="sc-card sc-components-card" style="display:none">
						<div class="sc-card-header">
							<h3 class="sc-card-title">Salary Components</h3>
							<div class="sc-header-right">
								<span class="sc-badge sc-count-badge">0 active</span>
								<button class="btn btn-xs btn-default sc-add-btn" style="display:none">+ Add</button>
							</div>
						</div>
						<div class="sc-card-body">
							<div class="sc-section">
								<div class="sc-section-label"><span class="sc-dot sc-dot-green"></span> Earnings</div>
								<div class="sc-list sc-earnings-list"></div>
							</div>
							<div class="sc-section">
								<div class="sc-section-label"><span class="sc-dot sc-dot-red"></span> Deductions</div>
								<div class="sc-list sc-deductions-list"></div>
							</div>
						</div>
					</div>
				</div>
				<div class="sc-right-panel">
					<div class="sc-card sc-preview-card">
						<div class="sc-card-header">
							<h3 class="sc-card-title">Salary Slip Preview</h3>
							<div class="sc-preview-actions"></div>
						</div>
						<div class="sc-card-body">
							<div class="sc-placeholder">
								<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--gray-400)" stroke-width="1.5">
									<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
									<polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>
									<line x1="16" y1="17" x2="8" y2="17"/>
								</svg>
								<p>Select a salary structure and enter an amount to begin</p>
							</div>
							<div class="sc-preview-content" style="display:none"></div>
						</div>
					</div>
				</div>
			</div>
		`);
	}

	// ── Fields ───────────────────────────────────────────────────────────

	create_fields() {
		const $fields = this.page.main.find(".sc-fields");
		this.fields = {};

		const defs = [
			{
				fieldtype: "Link", fieldname: "salary_structure", label: "Salary Structure",
				options: "Salary Structure", reqd: 1,
				get_query: () => ({ filters: { is_active: "Yes", docstatus: 1 } }),
				change: () => this.on_structure_change(),
			},
			{
				fieldtype: "Link", fieldname: "employee", label: "Employee",
				options: "Employee",
				get_query: () => ({ filters: { status: "Active" } }),
				change: () => { this.state.employee = this.val("employee"); this.schedule_calc(); },
			},
			{
				fieldtype: "Select", fieldname: "calculate_based_on", label: "Calculate Based On",
				options: ["Net Pay", "Gross Pay"], default: "Net Pay", reqd: 1,
				change: () => { this.state.calculate_based_on = this.val("calculate_based_on"); this.apply_field_states(); this.schedule_calc(); },
			},
		];

		for (const df of defs) {
			const $w = $('<div class="sc-field-wrap"></div>').appendTo($fields);
			this.fields[df.fieldname] = frappe.ui.form.make_control({ df, parent: $w, render_input: true });
		}
		this.fields.calculate_based_on.set_value("Net Pay");

		const $row = $('<div class="sc-amount-row"></div>').appendTo($fields);
		for (const name of ["gross_pay", "net_pay"]) {
			const $w = $('<div class="sc-field-wrap sc-field-half"></div>').appendTo($row);
			this.fields[name] = frappe.ui.form.make_control({
				df: {
					fieldtype: "Currency", fieldname: name, precision: 0,
					label: name === "gross_pay" ? "Gross Pay" : "Net Pay",
					change: () => {
						this.state.gross_pay = flt(this.val("gross_pay"));
						this.state.net_pay = flt(this.val("net_pay"));
						this.schedule_calc();
					},
				},
				parent: $w, render_input: true,
			});
		}

		this.apply_field_states();
	}

	val(name) { return this.fields[name]?.get_value(); }

	apply_field_states() {
		const is_net = this.state.calculate_based_on === "Net Pay";
		for (const [name, disabled] of [["gross_pay", is_net], ["net_pay", !is_net]]) {
			const f = this.fields[name];
			if (f?.$input) {
				f.$input.prop("disabled", disabled);
				f.$wrapper.toggleClass("sc-field-disabled", disabled);
			}
		}
	}

	// ── Structure Change ────────────────────────────────────────────────

	on_structure_change() {
		const value = this.val("salary_structure");
		this.state.salary_structure = value;

		if (!value) {
			this.structure_data = null;
			this.active_keys = new Set();
			this.earning_overrides = {};
			this.result = null;
			this.$(".sc-components-card").hide();
			this.show_placeholder();
			return;
		}

		frappe.xcall(
			"av_tools.av_tools.page.salary_calculator.salary_calculator.get_salary_structure_components",
			{ salary_structure: value },
		).then((data) => {
			this.structure_data = data;
			this.currency = data.currency || "TZS";
			this.earning_overrides = {};

			this.active_keys = new Set();
			for (const comp of [...data.earnings, ...data.deductions]) {
				if (!comp.statistical_component && !comp.do_not_include_in_total) {
					this.active_keys.add(comp.key);
				}
			}

			this.render_components();
			this.$(".sc-components-card").show();
			this.schedule_calc();
		});
	}

	// ── Components UI ───────────────────────────────────────────────────

	render_components() {
		if (!this.structure_data) return;
		this.render_component_list(this.$(".sc-earnings-list"), this.structure_data.earnings, true);
		this.render_component_list(this.$(".sc-deductions-list"), this.structure_data.deductions, false);
		this.update_counts();
	}

	render_component_list($list, components, is_earning) {
		$list.empty();
		let has_rows = false;
		const seen = new Set();

		for (const comp of components) {
			if (comp.statistical_component || comp.do_not_include_in_total) continue;
			if (!this.active_keys.has(comp.key)) continue;

			// Deduplicate deductions by salary_component name (e.g. 5 PAYE tiers → 1 row)
			if (!is_earning) {
				if (seen.has(comp.salary_component)) continue;
				seen.add(comp.salary_component);
			}

			has_rows = true;
			$list.append(this.build_component_row(comp, is_earning));
		}

		if (!has_rows) {
			$list.append('<div class="sc-empty-msg text-muted">None</div>');
		}
	}

	build_component_row(comp, is_earning) {
		const is_base = this.is_base(comp);
		const hint = comp.formula
			? `Formula: ${comp.formula}`
			: comp.amount ? `Amount: ${comp.amount}` : "";
		const esc = frappe.utils.escape_html;

		const $row = $(`
			<div class="sc-comp-row" data-key="${comp.key}">
				<div class="sc-comp-info">
					<span class="sc-comp-name">${esc(comp.salary_component)}</span>
					${is_base ? '<span class="sc-tag">Base</span>' : ""}
					${hint ? `<span class="sc-comp-hint">${esc(hint)}</span>` : ""}
				</div>
				${is_earning && !is_base ? '<div class="sc-comp-amount"></div>' : ""}
				${!is_base ? '<button class="btn btn-xs sc-remove-btn" title="Remove">&times;</button>' : ""}
			</div>
		`);

		// Editable amount input for non-base earnings
		if (is_earning && !is_base) {
			const $wrap = $row.find(".sc-comp-amount");
			const comp_name = comp.salary_component;
			const ctrl = frappe.ui.form.make_control({
				df: {
					fieldtype: "Currency", fieldname: `ovr_${comp.key}`,
					placeholder: "Amount", precision: 0,
					change: () => {
						const v = flt(ctrl.get_value());
						if (v > 0) {
							this.earning_overrides[comp_name] = v;
						} else {
							delete this.earning_overrides[comp_name];
						}
						this.schedule_calc();
					},
				},
				parent: $wrap, render_input: true,
			});
			const existing = this.earning_overrides[comp_name];
			if (existing !== undefined) ctrl.set_value(existing);
		}

		// Remove button
		if (!is_base) {
			$row.find(".sc-remove-btn").on("click", () => {
				if (is_earning) {
					this.active_keys.delete(comp.key);
					delete this.earning_overrides[comp.salary_component];
				} else {
					// Remove ALL keys for this salary_component (handles dupes like PAYE)
					for (const c of this.structure_data.deductions) {
						if (c.salary_component === comp.salary_component) {
							this.active_keys.delete(c.key);
						}
					}
				}
				this.render_components();
				this.schedule_calc();
			});
		}

		return $row;
	}

	is_base(comp) {
		const f = (comp.formula || "").replace(/\s/g, "").toLowerCase();
		return comp.abbr === "B" || (comp.salary_component || "").toLowerCase() === "basic" || f === "base";
	}

	get_inactive_components() {
		if (!this.structure_data) return [];
		const seen = new Set();
		return [...this.structure_data.earnings, ...this.structure_data.deductions].filter((c) => {
			if (c.statistical_component || c.do_not_include_in_total || this.is_base(c)) return false;
			if (this.active_keys.has(c.key)) return false;
			if (seen.has(c.salary_component)) return false;
			seen.add(c.salary_component);
			return true;
		});
	}

	update_counts() {
		this.$(".sc-count-badge").text(`${this.active_keys.size} active`);
		const inactive = this.get_inactive_components();
		const $btn = this.$(".sc-add-btn");
		if (inactive.length) {
			$btn.show().off("click").on("click", () => this.show_add_dialog());
		} else {
			$btn.hide();
		}
	}

	show_add_dialog() {
		const inactive = this.get_inactive_components();
		if (!inactive.length) return;

		const d = new frappe.ui.Dialog({
			title: __("Add Salary Component"),
			fields: [{
				fieldtype: "Select", fieldname: "key", label: "Component", reqd: 1,
				options: inactive.map((c) => ({ label: c.salary_component, value: c.key })),
			}],
			primary_action_label: __("Add"),
			primary_action: ({ key }) => {
				d.hide();
				const selected = inactive.find((c) => c.key === key);
				if (selected) {
					// Re-activate ALL rows with same salary_component (handles deduction dupes)
					for (const c of [...this.structure_data.earnings, ...this.structure_data.deductions]) {
						if (c.salary_component === selected.salary_component) {
							this.active_keys.add(c.key);
						}
					}
				}
				this.render_components();
				this.schedule_calc();
			},
		});
		d.show();
	}

	// ── Calculation ─────────────────────────────────────────────────────

	get_selected_names() {
		if (!this.structure_data) return [];
		const names = [];
		for (const comp of [...this.structure_data.earnings, ...this.structure_data.deductions]) {
			if (this.active_keys.has(comp.key) && !comp.statistical_component && !comp.do_not_include_in_total) {
				names.push(comp.salary_component);
			}
		}
		return names;
	}

	schedule_calc() {
		if (this._applying_result) return;
		clearTimeout(this._calc_timer);
		this._calc_timer = setTimeout(() => this.run_calculation(), 300);
	}

	run_calculation() {
		const ss = this.state.salary_structure;
		const mode = this.state.calculate_based_on;
		if (!ss || !mode) return;

		const target = mode === "Net Pay" ? flt(this.val("net_pay")) : flt(this.val("gross_pay"));
		if (!target) {
			this.result = null;
			this.show_placeholder();
			return;
		}

		frappe.xcall(
			"av_tools.av_tools.page.salary_calculator.salary_calculator.run_calculation",
			{
				salary_structure: ss,
				calculate_based_on: mode,
				gross_pay: this.state.gross_pay,
				net_pay: this.state.net_pay,
				selected_components: this.get_selected_names(),
				earning_overrides: this.earning_overrides,
				employee: this.state.employee || undefined,
			},
		).then((r) => {
			if (!r) return;
			this.result = r;

			// Update computed field without retriggering calculation
			this._applying_result = true;
			if (mode === "Net Pay") {
				this.fields.gross_pay.set_value(r.gross_pay);
			} else {
				this.fields.net_pay.set_value(r.net_pay);
			}
			this._applying_result = false;

			this.refresh_preview();
		}).catch((err) => {
			this.result = null;
			frappe.show_alert({ message: __("Calculation error: {0}", [err?.message || err]), indicator: "orange" }, 5);
		});
	}

	// ── Preview ──────────────────────────────────────────────────────────

	refresh_preview() {
		const ss = this.state.salary_structure;
		const r = this.result;

		if (!ss || !r) {
			this.show_placeholder();
			return;
		}

		// HRMS path returns earnings/deductions directly; use them as-is
		const earnings = r.earnings || [];
		const deductions = r.deductions || [];

		const emp = this.state.employee;
		frappe.xcall(
			"av_tools.av_tools.page.salary_calculator.salary_calculator.get_salary_slip_preview",
			{
				salary_structure: ss,
				base: r.base,
				gross_pay: r.gross_pay,
				net_pay: r.net_pay,
				earnings_data: earnings,
				deductions_data: deductions,
				employee: emp || undefined,
			},
		).then((html) => {
			this.$(".sc-placeholder").hide();
			this.$(".sc-preview-content").html(html).show();
			this.render_preview_actions();
		});
	}

	show_placeholder() {
		this.$(".sc-placeholder").show();
		this.$(".sc-preview-content").hide();
		this.$(".sc-preview-actions").empty();
	}

	// ── Assignment ───────────────────────────────────────────────────────

	render_preview_actions() {
		const $a = this.$(".sc-preview-actions").empty();
		if (!this.state.employee || !this.result) return;

		$('<button class="btn btn-primary btn-sm">Create Assignment</button>')
			.appendTo($a)
			.on("click", () => this.show_assign_dialog());
	}

	show_assign_dialog() {
		const d = new frappe.ui.Dialog({
			title: __("Create Salary Structure Assignment"),
			fields: [
				{ fieldtype: "Link", fieldname: "employee", label: "Employee", options: "Employee", default: this.state.employee, read_only: 1 },
				{ fieldtype: "Link", fieldname: "salary_structure", label: "Salary Structure", options: "Salary Structure", default: this.state.salary_structure, read_only: 1 },
				{ fieldtype: "Currency", fieldname: "base", label: "Base Amount", default: this.result?.base || 0, precision: 0, description: "Calculated base salary" },
				{ fieldtype: "Date", fieldname: "from_date", label: "From Date", reqd: 1, default: frappe.datetime.get_today() },
			],
			primary_action_label: __("Create & Submit"),
			primary_action: (v) => {
				d.hide();
				frappe.xcall(
					"av_tools.av_tools.page.salary_calculator.salary_calculator.create_salary_structure_assignment",
					{ employee: v.employee, salary_structure: v.salary_structure, from_date: v.from_date, base: v.base },
				).then((name) => {
					frappe.show_alert({
						message: __("Assignment {0} created", [`<a href="/app/salary-structure-assignment/${name}">${name}</a>`]),
						indicator: "green",
					}, 7);
				});
			},
		});
		d.show();
	}

	// ── Helpers ──────────────────────────────────────────────────────────

	$(selector) { return this.page.main.find(selector); }

	fmt(amount) {
		return format_number(flt(amount), null, this.currency === "TZS" ? 0 : 2);
	}
}
