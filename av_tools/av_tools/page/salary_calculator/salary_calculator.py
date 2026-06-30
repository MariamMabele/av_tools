"""Salary Calculator page backend.

Uses HRMS ``make_salary_slip`` (for_preview=1) when an employee is provided,
giving the full formula context (employee fields, payment days, tax handling).
Falls back to a lightweight resilient engine when no employee is selected.
"""
from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt


# ── Public API ───────────────────────────────────────────────────────

@frappe.whitelist()
def get_salary_structure_components(salary_structure):
    """Return earnings/deductions for a salary structure with unique keys."""
    structure = frappe.get_cached_doc("Salary Structure", salary_structure)

    def serialize(rows, prefix):
        return [
            {
                "key": f"{prefix}-{i}",
                "salary_component": row.salary_component,
                "abbr": row.abbr,
                "amount": flt(row.amount),
                "amount_based_on_formula": row.amount_based_on_formula,
                "formula": row.formula or "",
                "condition": row.condition or "",
                "do_not_include_in_total": row.do_not_include_in_total,
                "statistical_component": row.statistical_component,
            }
            for i, row in enumerate(rows)
        ]

    return {
        "earnings": serialize(structure.earnings, "E"),
        "deductions": serialize(structure.deductions, "D"),
        "currency": structure.currency or "",
    }


@frappe.whitelist()
def run_calculation(
    salary_structure, calculate_based_on, gross_pay=0, net_pay=0,
    selected_components=None, earning_overrides=None, employee=None,
):
    """Calculate salary. Uses HRMS when employee provided, else lightweight fallback."""
    if isinstance(selected_components, str):
        selected_components = json.loads(selected_components)
    if isinstance(earning_overrides, str):
        earning_overrides = json.loads(earning_overrides)

    overrides = earning_overrides or {}
    target_field = "gross_pay" if calculate_based_on == "Gross Pay" else "net_pay"
    target_amount = flt(gross_pay if target_field == "gross_pay" else net_pay)

    if target_amount <= 0:
        return _empty_result()

    if employee:
        try:
            return _solve_via_hrms(salary_structure, employee, target_field, target_amount, overrides)
        except Exception:
            pass  # Fall through to fallback

    selected = list(dict.fromkeys(selected_components or []))
    structure = frappe.get_cached_doc("Salary Structure", salary_structure)
    precision = 0 if cstr(structure.currency) == "TZS" else 2
    return _fallback_solve(structure, target_field, flt(target_amount, precision), precision, selected, overrides)


@frappe.whitelist()
def get_salary_slip_preview(
    salary_structure, base, gross_pay, net_pay,
    earnings_data, deductions_data, employee=None,
):
    """Render a salary slip preview from calculated data."""
    if isinstance(earnings_data, str):
        earnings_data = json.loads(earnings_data)
    if isinstance(deductions_data, str):
        deductions_data = json.loads(deductions_data)

    emp = frappe.get_cached_doc("Employee", employee) if employee else None
    currency = frappe.get_cached_value("Salary Structure", salary_structure, "currency") or "TZS"
    fmt = (lambda a: format(flt(a), ",.0f")) if currency == "TZS" else (lambda a: format(flt(a), ",.2f"))

    # CTC = Gross Pay + employer-cost contributions (deduction components flagged
    # do_not_include_in_total, e.g. employer NSSF/pension/SDL/WCF).
    ctc = flt(gross_pay)
    comp_names = [d.get("salary_component") for d in deductions_data if d.get("salary_component")]
    if comp_names:
        employer_comps = set(
            frappe.get_all(
                "Salary Component",
                filters={"name": ["in", comp_names], "do_not_include_in_total": 1},
                pluck="name",
            )
        )
        for d in deductions_data:
            if d.get("salary_component") in employer_comps:
                ctc += flt(d.get("amount"))

    return frappe.render_template(
        "av_tools/av_tools/page/salary_calculator/salary_slip_preview.html",
        {
            "employee": employee or "",
            "employee_name": emp.employee_name if emp else "",
            "department": (emp.department or "") if emp else "",
            "designation": (emp.designation or "") if emp else "",
            "company": emp.company if emp else "",
            "salary_structure": salary_structure,
            "currency": currency,
            "base": flt(base),
            "gross_pay": flt(gross_pay),
            "net_pay": flt(net_pay),
            "ctc": flt(ctc),
            "total_earning": sum(flt(e.get("amount")) for e in earnings_data),
            "total_deduction": sum(flt(d.get("amount")) for d in deductions_data),
            "earnings": earnings_data,
            "deductions": deductions_data,
            "format_amount": fmt,
        },
    )


@frappe.whitelist()
def create_salary_structure_assignment(employee, salary_structure, from_date, base=0):
    """Create and submit a Salary Structure Assignment."""
    if frappe.db.exists(
        "Salary Structure Assignment",
        {"employee": employee, "salary_structure": salary_structure, "from_date": from_date, "docstatus": ["!=", 2]},
    ):
        frappe.throw(
            _("Salary Structure Assignment already exists for {0} with {1} from {2}").format(
                frappe.bold(employee), frappe.bold(salary_structure), frappe.bold(from_date),
            )
        )

    ssa = frappe.new_doc("Salary Structure Assignment")
    ssa.employee = employee
    ssa.salary_structure = salary_structure
    ssa.from_date = from_date
    ssa.base = flt(base)
    ssa.company = frappe.get_cached_value("Employee", employee, "company")
    ssa.save()
    ssa.submit()
    return ssa.name


# ── HRMS-based Calculation ───────────────────────────────────────────

def _empty_result():
    return {"base": 0, "gross_pay": 0, "net_pay": 0, "total_deductions": 0, "earnings": [], "deductions": []}


def _make_preview_slip(salary_structure, employee, base_override=None, earning_overrides=None):
    """Create an in-memory salary slip using HRMS, optionally overriding base/earnings."""
    from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip

    ss = make_salary_slip(salary_structure, employee=employee, for_preview=1)

    if base_override is not None:
        ss._salary_structure_assignment["base"] = flt(base_override)
        ss.set("earnings", [])
        ss.set("deductions", [])
        ss.process_salary_structure(for_preview=1)

    if earning_overrides:
        changed = False
        for row in ss.earnings:
            if row.salary_component in earning_overrides:
                row.amount = flt(earning_overrides[row.salary_component])
                row.default_amount = row.amount
                changed = True
        if changed:
            ss.calculate_net_pay()

    return ss


def _format_slip_result(ss):
    """Extract a result dict from a salary slip object."""
    currency = cstr(getattr(ss, "currency", ""))
    precision = 0 if currency == "TZS" else 2
    base = flt(ss._salary_structure_assignment.get("base", 0), precision) if hasattr(ss, "_salary_structure_assignment") else 0
    return {
        "base": base,
        "gross_pay": flt(ss.gross_pay, precision),
        "net_pay": flt(ss.net_pay, precision),
        "total_deductions": flt(ss.total_deduction, precision),
        "earnings": [
            {"salary_component": r.salary_component, "amount": flt(r.amount)}
            for r in ss.earnings
        ],
        "deductions": [
            {"salary_component": r.salary_component, "amount": flt(r.amount)}
            for r in ss.deductions
        ],
    }


def _solve_via_hrms(salary_structure, employee, target_field, target_amount, earning_overrides=None):
    """Binary-search for the base that produces the target gross/net using HRMS."""
    lo, hi = 0.0, max(target_amount * 3, 1)
    best, best_val = None, None

    # Suppress repeated msgprint calls during binary search iterations
    original_messages = frappe.local.message_log[:]
    frappe.flags.mute_messages = True
    try:
        for i in range(60):
            mid = (lo + hi) / 2
            ss = _make_preview_slip(salary_structure, employee, base_override=mid, earning_overrides=earning_overrides)
            val = flt(ss.gross_pay) if target_field == "gross_pay" else flt(ss.net_pay)

            if best is None or abs(val - target_amount) < abs(best_val - target_amount):
                best, best_val = ss, val

            if abs(val - target_amount) <= 1:
                break
            if i > 2 and val == 0:
                return _empty_result()
            if val < target_amount:
                lo = mid
            else:
                hi = mid
    finally:
        frappe.flags.mute_messages = False
        frappe.local.message_log = original_messages

    return _format_slip_result(best) if best else _empty_result()


# ── Fallback Engine (no employee) ────────────────────────────────────

_SAFE_GLOBALS = {"int": int, "float": float, "round": round, "abs": abs, "min": min, "max": max, "flt": flt}


def _fallback_solve(structure, target_field, target_amount, precision, selected, overrides=None):
    overrides = overrides or {}
    tol = 1 if precision == 0 else 0.05
    lo, hi = 0.0, max(target_amount, 1)
    best, best_diff = None, None

    for i in range(20):
        r = _fallback_calc(structure, hi, precision, selected, overrides)
        val = flt(r[target_field], precision)
        if val >= target_amount:
            best, best_diff = r, abs(val - target_amount)
            break
        if i > 2 and val == 0:
            return _empty_result()
        hi *= 2
    else:
        best = r
        best_diff = abs(flt(r[target_field], precision) - target_amount)

    for _ in range(60):
        mid = (lo + hi) / 2
        r = _fallback_calc(structure, mid, precision, selected, overrides)
        diff = flt(r[target_field], precision) - target_amount
        if abs(diff) < (best_diff or float("inf")):
            best, best_diff = r, abs(diff)
        if abs(diff) <= tol:
            break
        if diff < 0:
            lo = mid
        else:
            hi = mid

    base_int = int(round(flt(best["base"], precision)))
    for offset in range(-3, 4):
        cand = base_int + offset
        if cand < 0:
            continue
        r = _fallback_calc(structure, cand, precision, selected, overrides)
        d = abs(flt(r[target_field], precision) - target_amount)
        if d < best_diff or (d == best_diff and flt(r[target_field], precision) >= flt(best[target_field], precision)):
            best, best_diff = r, d

    return best


def _fallback_calc(structure, base_amount, precision, selected, overrides=None):
    overrides = overrides or {}
    rows = {
        "earnings": [_norm_row(r, "Earning", precision) for r in structure.earnings],
        "deductions": [_norm_row(r, "Deduction", precision) for r in structure.deductions],
    }
    gross_pay = net_pay = total_ded = 0.0
    prev = None

    for _ in range(10):
        ctx = {"base": flt(base_amount, precision), "gross_pay": gross_pay, "net_pay": net_pay, "total_deductions": total_ded}
        for r in rows["earnings"] + rows["deductions"]:
            if r.abbr:
                ctx[r.abbr] = flt(r.amount, precision)
                ctx[f"{r.abbr}_amount"] = flt(r.amount, precision)
        _add_missing_ctx(ctx, rows["earnings"] + rows["deductions"])

        earnings = _eval_rows(rows["earnings"], ctx, precision, selected, overrides)
        gross_pay = flt(sum(r.amount for r in earnings if _incl_earning(r, selected)), precision)
        ctx["gross_pay"] = gross_pay
        for r in earnings:
            if r.abbr:
                ctx[r.abbr] = flt(r.amount, precision)
                ctx[f"{r.abbr}_amount"] = flt(r.amount, precision)

        deductions = _eval_rows(rows["deductions"], ctx, precision, selected)
        total_ded = flt(sum(r.amount for r in deductions if _incl_deduction(r, selected)), precision)
        net_pay = flt(gross_pay - total_ded, precision)

        state = (gross_pay, total_ded, net_pay, tuple(r.amount for r in earnings + deductions))
        rows = {"earnings": earnings, "deductions": deductions}
        if state == prev:
            break
        prev = state

    # Sum amounts by component name (handles duplicates like PAYE tiers)
    amounts = {}
    comp_types = {}
    for r in earnings + deductions:
        name = cstr(r.salary_component)
        if name:
            amounts[name] = flt(amounts.get(name, 0) + flt(r.amount, precision), precision)
            comp_types[name] = r.component_type

    # Always include all selected components so they appear in the preview
    seen = set()
    result_earnings, result_deductions = [], []
    for c in selected:
        if c in seen:
            continue
        seen.add(c)
        entry = {"salary_component": c, "amount": flt(amounts.get(c, 0), precision)}
        if comp_types.get(c) == "Earning":
            result_earnings.append(entry)
        elif comp_types.get(c) == "Deduction":
            result_deductions.append(entry)

    return {
        "base": flt(base_amount, precision),
        "gross_pay": gross_pay,
        "net_pay": net_pay,
        "total_deductions": total_ded,
        "earnings": result_earnings,
        "deductions": result_deductions,
    }


def _norm_row(row, ctype, precision):
    return frappe._dict(
        salary_component=cstr(row.salary_component), abbr=cstr(row.abbr), component_type=ctype,
        condition=cstr(row.condition), formula=cstr(row.formula),
        amount=flt(row.amount, precision), amount_based_on_formula=cint(row.amount_based_on_formula),
        do_not_include_in_total=cint(row.do_not_include_in_total), statistical_component=cint(row.statistical_component),
    )


def _add_missing_ctx(ctx, rows):
    """Default any undefined variable referenced in conditions/formulas.

    Condition variables (used in boolean expressions like ``x == 1``) default
    to 1 so that components are assumed applicable when no employee context is
    available.  Formula-only variables default to 0 so they don't inflate
    amounts.
    """
    # Collect all tokens used in conditions vs formulas
    cond_tokens = set()
    formula_tokens = set()
    for r in rows:
        if r.condition:
            cond_tokens.update(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", r.condition))
        if r.formula:
            formula_tokens.update(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", r.formula))

    # Python keywords and safe_eval builtins to skip
    skip = {"and", "or", "not", "if", "else", "True", "False", "None",
            "int", "float", "round", "abs", "min", "max", "flt"}

    for tok in cond_tokens:
        if tok not in skip:
            ctx.setdefault(tok, 1)  # assume applicable

    for tok in formula_tokens - cond_tokens:
        if tok not in skip:
            ctx.setdefault(tok, 0)  # don't inflate amounts


def _eval_rows(rows, base_ctx, precision, selected, overrides=None):
    overrides = overrides or {}
    ctx = frappe._dict(base_ctx.copy())
    result = []
    for row in rows:
        comp = cstr(row.salary_component)
        if comp in overrides and row.component_type == "Earning" and not _is_base(row):
            amt = flt(overrides[comp], precision)
        elif not _should_eval(row, selected):
            amt = 0
        elif row.condition and not _safe_eval_cond(row.condition, ctx):
            amt = 0
        elif row.amount_based_on_formula and row.formula:
            amt = _safe_eval_formula(row.formula, ctx, precision)
        else:
            amt = row.amount if not row.amount_based_on_formula else 0
        row.amount = flt(amt, precision)
        result.append(row)
        if row.abbr:
            ctx[row.abbr] = row.amount
            ctx[f"{row.abbr}_amount"] = row.amount
    return result


def _safe_eval_formula(formula, ctx, precision):
    try:
        return flt(frappe.safe_eval(cstr(formula).strip(), eval_globals=_SAFE_GLOBALS, eval_locals=ctx), precision)
    except Exception:
        return 0


def _safe_eval_cond(condition, ctx):
    try:
        return cint(frappe.safe_eval(cstr(condition).strip(), eval_globals=_SAFE_GLOBALS, eval_locals=ctx))
    except Exception:
        return False


def _is_base(row):
    f = cstr(row.formula).replace(" ", "").lower()
    return row.abbr == "B" or cstr(row.salary_component).lower() == "basic" or f == "base"


def _should_eval(row, selected):
    return row.statistical_component or _is_base(row) or cstr(row.salary_component) in set(selected)


def _incl_earning(row, selected):
    if row.component_type != "Earning" or row.do_not_include_in_total or row.statistical_component:
        return False
    return _is_base(row) or cstr(row.salary_component) in set(selected)


def _incl_deduction(row, selected):
    if row.component_type != "Deduction" or row.do_not_include_in_total or row.statistical_component:
        return False
    return cstr(row.salary_component) in set(selected)
