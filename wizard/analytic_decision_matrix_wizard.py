from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AnalyticDecisionMatrixWizard(models.Model):
    _name = "analytic.decision.matrix.wizard"
    _description = "Matriz de Decision Analitica"
    _rec_name = "name"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, default=lambda self: _("Nuevo Reporte"))
    last_compute_at = fields.Datetime(string="Ultimo Calculo", readonly=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date()
    date_to = fields.Date(default=fields.Date.context_today)
    analytic_plan_id = fields.Many2one("account.analytic.plan", string="Plan Analitico")
    analytic_account_ids = fields.Many2many(
        "account.analytic.account",
        "analytic_decision_matrix_wizard_account_rel",
        "wizard_id",
        "analytic_account_id",
        string="Cuentas Analiticas",
        domain="[('company_id', 'in', [False, company_id])]",
    )
    reasignacion_journal_code = fields.Char(required=True, default="REASIG-ANA")
    line_ids = fields.One2many(
        "analytic.decision.matrix.wizard.line",
        "wizard_id",
        string="Resultados",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("Nuevo Reporte"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("analytic.decision.matrix.wizard")
                    or _("Reporte Matriz Analitica")
                )
        return super().create(vals_list)

    def action_compute(self):
        self.ensure_one()
        self._validate_dates()
        self.line_ids.unlink()
        selected_analytic_ids = self._selected_analytic_ids()

        amounts_by_project = defaultdict(lambda: defaultdict(float))
        self._load_move_line_amounts(amounts_by_project, selected_analytic_ids)
        self._load_open_residuals(amounts_by_project, selected_analytic_ids)

        new_lines = []
        analytic_accounts = self.env["account.analytic.account"].browse(amounts_by_project.keys()).exists()
        for analytic in analytic_accounts.sorted(lambda a: (a.name or "").lower()):
            row = amounts_by_project.get(analytic.id, {})
            ingreso = row.get("ingreso", 0.0)
            cxc = row.get("cxc", 0.0)
            reasignacion_in = row.get("reasignacion_in", 0.0)
            egresos = row.get("egresos", 0.0)
            cxp = row.get("cxp", 0.0)
            reasignacion_out = row.get("reasignacion_out", 0.0)

            saldo_devengado = (ingreso + cxc + reasignacion_in) - (egresos + cxp + reasignacion_out)
            saldo_efectivo = (ingreso + reasignacion_in) - (egresos + reasignacion_out)

            if not any(
                abs(v) >= 0.005
                for v in (
                    ingreso,
                    cxc,
                    reasignacion_in,
                    egresos,
                    cxp,
                    reasignacion_out,
                    saldo_devengado,
                    saldo_efectivo,
                )
            ):
                continue

            new_lines.append(
                (
                    0,
                    0,
                    {
                        "analytic_account_id": analytic.id,
                        "ingreso": ingreso,
                        "cxc": cxc,
                        "reasignacion_in": reasignacion_in,
                        "egresos": egresos,
                        "cxp": cxp,
                        "reasignacion_out": reasignacion_out,
                        "saldo_devengado": saldo_devengado,
                        "saldo_efectivo": saldo_efectivo,
                    },
                )
            )

        write_vals = {"last_compute_at": fields.Datetime.now()}
        if new_lines:
            write_vals["line_ids"] = new_lines
        self.write(write_vals)

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }

    def action_print_pdf(self):
        self.ensure_one()
        self._validate_dates()
        if not self.line_ids:
            self.action_compute()
        return self.env.ref(
            "analytic_decision_matrix_report.action_report_analytic_decision_matrix"
        ).report_action(self)

    def _validate_dates(self):
        self.ensure_one()
        if self.date_from and self._effective_date_to() and self.date_from > self._effective_date_to():
            raise ValidationError(_("La fecha desde no puede ser mayor que la fecha hasta."))

    def _effective_date_to(self):
        self.ensure_one()
        return self.date_to or fields.Date.context_today(self)

    def _selected_analytic_ids(self):
        self.ensure_one()
        domain = [("company_id", "in", [False, self.company_id.id])]
        if self.analytic_plan_id:
            domain.append(("plan_id", "=", self.analytic_plan_id.id))
        if self.analytic_account_ids:
            domain.append(("id", "in", self.analytic_account_ids.ids))
        return set(self.env["account.analytic.account"].search(domain).ids)

    def _load_move_line_amounts(self, amounts_by_project, selected_analytic_ids):
        self.ensure_one()
        date_to = self._effective_date_to()
        where_date_from = ""
        params = [
            self.reasignacion_journal_code,
            self.reasignacion_journal_code,
            self.company_id.id,
        ]
        if self.date_from:
            where_date_from = "AND aml.date >= %s"
            params.append(self.date_from)
        params.append(date_to)
        self.env.cr.execute(
            f"""
            SELECT
                ad.key::int AS analytic_id,
                SUM(
                    CASE
                        WHEN aa.account_type IN ('income', 'income_other')
                        THEN (-aml.balance) * (ad.value::numeric / 100.0)
                        ELSE 0
                    END
                ) AS ingreso,
                SUM(
                    CASE
                        WHEN aa.account_type IN ('expense', 'expense_direct_cost', 'expense_depreciation')
                        THEN aml.balance * (ad.value::numeric / 100.0)
                        ELSE 0
                    END
                ) AS egresos,
                SUM(
                    CASE
                        WHEN aj.code = %s AND aml.debit > 0
                        THEN aml.debit * (ad.value::numeric / 100.0)
                        ELSE 0
                    END
                ) AS reasignacion_in,
                SUM(
                    CASE
                        WHEN aj.code = %s AND aml.credit > 0
                        THEN aml.credit * (ad.value::numeric / 100.0)
                        ELSE 0
                    END
                ) AS reasignacion_out
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            LEFT JOIN account_journal aj ON aj.id = aml.journal_id
            JOIN LATERAL jsonb_each_text(aml.analytic_distribution) ad ON TRUE
            WHERE am.state = 'posted'
              AND aml.company_id = %s
              {where_date_from}
              AND aml.date <= %s
              AND aml.analytic_distribution IS NOT NULL
              AND aml.analytic_distribution != '{{}}'::jsonb
            GROUP BY ad.key::int
            """,
            tuple(params),
        )

        for analytic_id, ingreso, egresos, reasignacion_in, reasignacion_out in self.env.cr.fetchall():
            if selected_analytic_ids and analytic_id not in selected_analytic_ids:
                continue
            row = amounts_by_project[analytic_id]
            row["ingreso"] += float(ingreso or 0.0)
            row["egresos"] += float(egresos or 0.0)
            row["reasignacion_in"] += float(reasignacion_in or 0.0)
            row["reasignacion_out"] += float(reasignacion_out or 0.0)

    def _load_open_residuals(self, amounts_by_project, selected_analytic_ids):
        self.ensure_one()
        date_to = self._effective_date_to()
        moves = self.env["account.move"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("state", "=", "posted"),
                ("move_type", "in", ("out_invoice", "out_refund", "in_invoice", "in_refund")),
                "|",
                ("invoice_date", "<=", date_to),
                "&",
                ("invoice_date", "=", False),
                ("date", "<=", date_to),
            ]
        )

        for move in moves:
            weights = self._weights_by_analytic(move, selected_analytic_ids)
            if not weights:
                continue

            total_weight = sum(weights.values())
            if not total_weight:
                continue

            move_type = move.move_type
            residual_signed = self._residual_signed_at_date(move, date_to)
            residual_abs = abs(residual_signed)
            if not residual_abs:
                continue

            if move_type == "out_invoice":
                base_amount = residual_abs
                target_key = "cxc"
            elif move_type == "out_refund":
                base_amount = -residual_abs
                target_key = "cxc"
            elif move_type == "in_invoice":
                base_amount = residual_abs
                target_key = "cxp"
            else:
                base_amount = -residual_abs
                target_key = "cxp"

            for analytic_id, weight in weights.items():
                ratio = weight / total_weight
                amounts_by_project[analytic_id][target_key] += base_amount * ratio

    @api.model
    def _residual_signed_at_date(self, move, cutoff_date):
        """Compute residual in company currency as of cutoff_date."""
        receivable_payable_lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
            and l.display_type not in ("line_section", "line_note")
        )
        if not receivable_payable_lines:
            return 0.0

        residual = 0.0
        for line in receivable_payable_lines:
            line_residual = line.balance
            matched_debit = line.matched_debit_ids.filtered(lambda p: p.max_date and p.max_date <= cutoff_date)
            matched_credit = line.matched_credit_ids.filtered(lambda p: p.max_date and p.max_date <= cutoff_date)
            line_residual += sum(matched_debit.mapped("amount"))
            line_residual -= sum(matched_credit.mapped("amount"))
            residual += line_residual
        return residual

    @api.model
    def _weights_by_analytic(self, move, selected_analytic_ids):
        weights = defaultdict(float)
        lines = move.invoice_line_ids.filtered(
            lambda l: l.analytic_distribution and l.display_type not in ("line_section", "line_note")
        )
        for line in lines:
            base = abs(line.balance)
            if not base:
                continue
            for key, pct in (line.analytic_distribution or {}).items():
                try:
                    analytic_id = int(key)
                except (TypeError, ValueError):
                    continue
                if selected_analytic_ids and analytic_id not in selected_analytic_ids:
                    continue
                weights[analytic_id] += base * (float(pct) / 100.0)
        return weights


class AnalyticDecisionMatrixWizardLine(models.Model):
    _name = "analytic.decision.matrix.wizard.line"
    _description = "Linea Matriz de Decision Analitica"
    _order = "analytic_account_id"

    wizard_id = fields.Many2one("analytic.decision.matrix.wizard", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="wizard_id.company_id", store=False)
    currency_id = fields.Many2one(related="company_id.currency_id", store=False)
    analytic_account_id = fields.Many2one("account.analytic.account", string="Proyecto", required=True)

    ingreso = fields.Monetary(currency_field="currency_id", string="Ingreso")
    cxc = fields.Monetary(currency_field="currency_id", string="Ctas x Cob")
    reasignacion_in = fields.Monetary(currency_field="currency_id", string="Reasignacion (+)")
    egresos = fields.Monetary(currency_field="currency_id", string="Egresos")
    cxp = fields.Monetary(currency_field="currency_id", string="Ctas x Pag")
    reasignacion_out = fields.Monetary(currency_field="currency_id", string="Reasignacion (-)")
    saldo_devengado = fields.Monetary(currency_field="currency_id", string="Saldo Devengado")
    saldo_efectivo = fields.Monetary(currency_field="currency_id", string="Saldo Efectivo")
