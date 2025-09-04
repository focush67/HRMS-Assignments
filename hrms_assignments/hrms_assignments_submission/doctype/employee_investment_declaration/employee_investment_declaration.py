import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
from typing import Dict, Tuple, List


class EmployeeInvestmentDeclaration(Document):
    CAP_80C_DEFAULT = 150000.0
    PREVENTIVE_CAP_DEFAULT = 5000.0

    SELF_FAMILY_SET = {"Self", "Spouse", "Children"}

    NONCASH_TOKENS = {"non-cash", "cashless", "card", "upi"}

    def autoname(self):
        self.name = f"{self.employee}-{self.fiscal_year}"

    def _has_declared_80c(self):
        return bool(
            frappe.db.exists(
                "Employee Investment Line",
                {
                    "parent": self.name,
                    "parenttype": self.doctype,
                    "section_code": "80C",
                    "amount_declared": [">", 0],
                },
            )
        )

    def _has_declared_80d(self):
        return bool(
            frappe.db.exists(
                "Medical Insurance Line",
                {
                    "parent": self.name,
                    "parenttype": self.doctype,
                    "amount_declared": [">", 0],
                },
            )
        )

    def validate(self):
        if self._is_locked() and not frappe.has_permission(
            doctype=self.doctype, ptype="submit"
        ):
            frappe.throw("This declaration is Locked and cannot be edited.")

        regime_str = (self.tax_regime or "").strip().lower()
        if "old" not in regime_str:
            frappe.throw(
                "Investment Declarations are only applicable under the Old Tax Regime."
            )

        self._ensure_only_80c_in_investment_lines()
        self._validate_80d_payment_modes()

        total_decl, total_verf, _ = self._compute_totals_for_doc()
        self.total_declared = total_decl
        self.total_verified = total_verf

        old = self.get_doc_before_save()
        old_status = (old.declaration_status if old else "") or ""
        new_status = self.declaration_status or ""

        if new_status in ("Submitted", "Verified", "Locked"):
            self._enforce_manual_caps()

        if self._transition(old_status, new_status, "Submitted", "Verified"):
            has_80c = self._has_declared_80c()
            has_80d = self._has_declared_80d()

            if not (has_80c and has_80d):
                frappe.throw(
                    "To proceed under the Old Tax Regime, add at least one 80C investment "
                    "and one 80D medical insurance entry with a positive declared amount."
                )

            if not getattr(self, "verified_by", None):
                self.verified_by = frappe.session.user
            if hasattr(self, "verified_on") and not getattr(self, "verified_on", None):
                self.verified_on = now_datetime()

        if self._transition(old_status, new_status, "Verified", "Locked"):
            from hrms_assignments.utilities.employee import sync_to_eted_from_custom

            if not getattr(self, "locked_on", None):
                self.locked_on = now_datetime()
            if "old" in (self.tax_regime or "").strip().lower():
                sync_to_eted_from_custom(doc=self)

    def _compute_totals_for_doc(self) -> Tuple[float, float, Dict[str, float]]:
        inv80c, med80d = self._fetch_children()

        cap_80c = self._resolve_80c_cap()
        decl_80c = sum(
            float(r.get("amount_declared") or 0)
            for r in inv80c
            if (r.get("section_code") or "").strip() == "80C"
        )
        verf_80c = sum(
            float(r.get("amount_verified") or 0)
            for r in inv80c
            if (r.get("section_code") or "").strip() == "80C"
        )
        decl_80c_capped = min(decl_80c, cap_80c)
        verf_80c_capped = min(verf_80c, cap_80c)

        caps = self._resolve_80d_caps()

        def bucket_key(insured_for: str) -> str:
            return (
                "SelfFamily"
                if (insured_for or "").strip() in self.SELF_FAMILY_SET
                else "Parents"
            )

        def gather(use_verified: bool):
            sums = {
                ("SelfFamily", 0): {"total": 0.0, "preventive": 0.0},
                ("SelfFamily", 1): {"total": 0.0, "preventive": 0.0},
                ("Parents", 0): {"total": 0.0, "preventive": 0.0},
                ("Parents", 1): {"total": 0.0, "preventive": 0.0},
            }
            for r in med80d:
                grp = bucket_key(r.get("insured_for"))
                senior = 1 if int(r.get("is_a_senior_citizen") or 0) else 0
                amt = float(
                    (
                        r.get("amount_verified")
                        if use_verified
                        else r.get("amount_declared")
                    )
                    or 0
                )
                sums[(grp, senior)]["total"] += amt
                if int(r.get("preventive_health_checkup") or 0) == 1:
                    sums[(grp, senior)]["preventive"] += amt
            return sums

        def apply_caps(sums: Dict[Tuple[str, int], Dict[str, float]]) -> float:
            total = 0.0
            for key, agg in sums.items():
                c = caps.get(key) or caps.get((key[0], 0))
                if not c:
                    continue
                prev_allow = min(
                    max(agg["preventive"], 0.0), float(c["preventive_cap"])
                )
                overflow_prev = max(agg["preventive"] - prev_allow, 0.0)
                normal_amt = max(agg["total"] - agg["preventive"], 0.0) + overflow_prev
                total += min(prev_allow + normal_amt, float(c["cap"]))
            return total

        decl_80d_capped = apply_caps(gather(use_verified=False))
        verf_80d_capped = apply_caps(gather(use_verified=True))

        sectionwise = {
            "80C_declared": decl_80c_capped,
            "80C_verified": verf_80c_capped,
            "80D_declared": decl_80d_capped,
            "80D_verified": verf_80d_capped,
        }
        return (
            decl_80c_capped + decl_80d_capped,
            verf_80c_capped + verf_80d_capped,
            sectionwise,
        )

    def _enforce_manual_caps(self):
        errors = []
        invc80 = frappe.get_all(
            "Employee Investment Line",
            filters={
                "parent": self.name,
                "parenttype": self.doctype,
                "section_code": "80C",
            },
            fields=["subcategory", "amount_verified"],
        )
        v80c = sum(float(r.get("amount_verified") or 0) for r in invc80)

        if v80c > 150000.0 + 0.001:
            errors.append(
                f"80C verified total ₹{v80c:,.2f} exceeds the cap ₹1,50,000. "
                f"Please reduce one or more 80C lines so sum ≤ 1,50,000."
            )

        med = frappe.get_all(
            "Medical Insurance Line",
            filters={"parent": self.name, "parenttype": self.doctype},
            fields=[
                "insured_for",
                "is_a_senior_citizen",
                "amount_verified",
                "preventive_health_checkup",
            ],
        )

        agg = {
            ("SF", 0): {"prem": 0.0, "prev": 0.0, "cap": 25000.0, "prev_cap": 5000.0},
            ("SF", 1): {"prem": 0.0, "prev": 0.0, "cap": 50000.0, "prev_cap": 5000.0},
            ("Parents", 0): {
                "prem": 0.0,
                "prev": 0.0,
                "cap": 25000.0,
                "prev_cap": 5000.0,
            },
            ("Parents", 1): {
                "prem": 0.0,
                "prev": 0.0,
                "cap": 50000.0,
                "prev_cap": 5000.0,
            },
        }

        for r in med:
            insured_for = r.get("insured_for")
            g = (
                "SF"
                if (insured_for or "").strip() in {"Self", "Spouse", "Children"}
                else "Parents"
            )
            s = 1 if int(r.get("is_a_senior_citizen") or 0) else 0
            amt = float(r.get("amount_verified") or 0)
            is_prev = int(r.get("preventive_health_checkup") or 0) == 1
            if is_prev:
                agg[(g, s)]["prev"] += amt
            else:
                agg[(g, s)]["prem"] += amt

        for (g, s), v in agg.items():
            if v["prev"] > v["prev_cap"] + 0.001:
                bucket = "Self/Family" if g == "SF" else "Parents"
                senior = " (Senior)" if s == 1 else ""
                errors.append(
                    f"80D {bucket}{senior}: Preventive verified ₹{v['prev']:,.2f} exceeds ₹{v['prev_cap']:,.0f}."
                )

            total = v["prev"] + v["prem"]
            if total > v["cap"] + 0.001:
                bucket = "Self/Family" if g == "SF" else "Parents"
                senior = " (Senior)" if s == 1 else ""
                errors.append(
                    f"80D {bucket}{senior}: Total verified ₹{total:,.2f} exceeds cap ₹{v['cap']:,.0f}."
                )

        if errors:
            frappe.throw("<br>".join(errors))

    def _ensure_only_80c_in_investment_lines(self):
        bad = frappe.get_all(
            "Employee Investment Line",
            filters={
                "parent": self.name,
                "parenttype": self.doctype,
                "section_code": ["not in", ["", "80C"]],
            },
            pluck="name",
        )
        if bad:
            frappe.throw(
                f"Only section_code = 80C is allowed in Employee Investment Line. Invalid rows: {', '.join(bad)}"
            )

    def _validate_80d_payment_modes(self):
        """
        Preventive checkup can be Cash; premiums should be non-cash (cashless/card/upi).
        We warn (msgprint) rather than throw; switch to throw if you want strict enforcement.
        """
        rows = frappe.get_all(
            "Medical Insurance Line",
            filters={"parent": self.name, "parenttype": self.doctype},
            fields=["name", "payment_mode", "preventive_health_checkup"],
        )
        for r in rows:
            mode_raw = (r.get("payment_mode") or "").strip()
            mode = mode_raw.lower()
            is_prev = int(r.get("preventive_health_checkup") or 0) == 1
            is_noncash = (mode in self.NONCASH_TOKENS) or ("cash" not in mode)
            if not is_prev and not is_noncash:
                frappe.throw(
                    f"Note: 80D premium in row {r['name']} is marked Cash. "
                    f"Only preventive health checkup is typically allowed in Cash.",
                    alert=True,
                    indicator="orange",
                )

    def _fetch_children(self):
        inv80c = frappe.get_all(
            "Employee Investment Line",
            filters={"parent": self.name, "parenttype": self.doctype},
            fields=[
                "name",
                "section_code",
                "subcategory",
                "amount_declared",
                "amount_verified",
            ],
            order_by="idx asc",
        )
        med80d = frappe.get_all(
            "Medical Insurance Line",
            filters={"parent": self.name, "parenttype": self.doctype},
            fields=[
                "name",
                "insured_for",
                "is_a_senior_citizen",
                "payment_mode",
                "amount_declared",
                "amount_verified",
                "preventive_health_checkup",
            ],
            order_by="idx asc",
        )
        return inv80c, med80d

    def _load_section_rule(self, section: str) -> Dict:
        row = frappe.get_all(
            "Investment Section Rule",
            filters={"section": section, "is_active": 1},
            fields=["name", "section", "computation_type", "absolute_cap"],
            order_by="modified desc",
            limit=1,
        )
        return row[0] if row else {}

    def _load_80d_variants(self, parent_rule_name: str) -> List[Dict]:
        if not parent_rule_name:
            return []
        return frappe.get_all(
            "Investment Rule Variant",
            filters={"parent": parent_rule_name},
            fields=[
                "beneficiary_group",
                "senior_only",
                "absolute_cap",
                "preventive_health_checkup_cap",
            ],
            order_by="idx asc, modified desc",
        )

    def _resolve_80c_cap(self) -> float:
        rule = self._load_section_rule("80C")
        cap = float(rule.get("absolute_cap") or 0)
        return cap if cap > 0 else self.CAP_80C_DEFAULT

    def _resolve_80d_caps(self) -> Dict[Tuple[str, int], Dict[str, float]]:
        """
        Build cap map keyed by (bucket, senior_flag) → {cap, preventive_cap}
        bucket ∈ {"SelfFamily","Parents"}; senior_flag ∈ {0,1}
        """
        rule = self._load_section_rule("80D")
        variants = self._load_80d_variants(rule.get("name"))
        caps: Dict[Tuple[str, int], Dict[str, float]] = {}

        def map_bucket(beneficiary_group: str) -> str:
            g = (beneficiary_group or "").strip()
            if g in self.SELF_FAMILY_SET:
                return "SelfFamily"
            if g == "Parents":
                return "Parents"
            return "SelfFamily"

        for v in variants:
            key = (
                map_bucket(v.get("beneficiary_group") or ""),
                int(v.get("senior_only") or 0),
            )
            cap = float(v.get("absolute_cap") or 0)
            prev_raw = v.get("preventive_health_checkup_cap")
            prev_cap = float(prev_raw or self.PREVENTIVE_CAP_DEFAULT)
            if key not in caps or cap > caps[key]["cap"]:
                caps[key] = {"cap": cap, "preventive_cap": max(prev_cap, 0.0)}

        if not caps:
            caps[("SelfFamily", 0)] = {
                "cap": 25000.0,
                "preventive_cap": self.PREVENTIVE_CAP_DEFAULT,
            }
            caps[("Parents", 0)] = {
                "cap": 25000.0,
                "preventive_cap": self.PREVENTIVE_CAP_DEFAULT,
            }
            caps[("Parents", 1)] = {
                "cap": 50000.0,
                "preventive_cap": self.PREVENTIVE_CAP_DEFAULT,
            }
        return caps

    def _transition(self, old: str, new: str, from_state: str, to_state: str) -> bool:
        return (old or "").strip() == from_state and (new or "").strip() == to_state

    def _is_locked(self) -> bool:
        return (self.declaration_status or "").strip().lower() == "locked"


@frappe.whitelist()
def get_sectionwise_verified(employee: str, fiscal_year: str) -> Dict[str, float]:
    """
    Return verified, capped totals per section (80C, 80D) and combined total for an employee+FY.
    """
    name = frappe.db.get_value(
        "Employee Investment Declaration",
        {"employee": employee, "fiscal_year": fiscal_year},
        "name",
    )
    if not name:
        return {"80C": 0.0, "80D": 0.0, "total": 0.0}

    doc = frappe.get_doc("Employee Investment Declaration", name)
    total_decl, total_verf, sectionwise = doc._compute_totals_for_doc()
    return {
        "80C": float(sectionwise["80C_verified"]),
        "80D": float(sectionwise["80D_verified"]),
        "total": float(total_verf),
    }
