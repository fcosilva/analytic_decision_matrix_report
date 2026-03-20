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
    include_reversed = fields.Boolean(
        string="Incluir reversados",
        default=False,
        help="Si se activa, incluye tanto el documento original reversado como su documento de reversa.",
    )
    drilldown_document_view = fields.Boolean(
        string="Drill-down por documentos",
        default=True,
        help="Si se activa, el detalle de Ingreso/Egreso/Reasignacion se abre por documentos (account.move).",
    )
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
        totals = defaultdict(float)
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
            totals["ingreso"] += ingreso
            totals["cxc"] += cxc
            totals["reasignacion_in"] += reasignacion_in
            totals["egresos"] += egresos
            totals["cxp"] += cxp
            totals["reasignacion_out"] += reasignacion_out
            totals["saldo_devengado"] += saldo_devengado
            totals["saldo_efectivo"] += saldo_efectivo

        if new_lines:
            new_lines.append(
                (
                    0,
                    0,
                    {
                        "is_total": True,
                        "project_label": _("TOTAL GENERAL"),
                        "ingreso": totals["ingreso"],
                        "cxc": totals["cxc"],
                        "reasignacion_in": totals["reasignacion_in"],
                        "egresos": totals["egresos"],
                        "cxp": totals["cxp"],
                        "reasignacion_out": totals["reasignacion_out"],
                        "saldo_devengado": totals["saldo_devengado"],
                        "saldo_efectivo": totals["saldo_efectivo"],
                    },
                )
            )

        write_vals = {"last_compute_at": fields.Datetime.now()}
        if new_lines:
            write_vals["line_ids"] = new_lines
        self.write(write_vals)

        return {"type": "ir.actions.client", "tag": "reload"}

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

    def _sql_reversed_moves_clause(self, alias="am"):
        self.ensure_one()
        if self.include_reversed:
            return ""
        return f"""
            AND {alias}.reversed_entry_id IS NULL
            AND NOT EXISTS (
                SELECT 1
                FROM account_move am_rev
                WHERE am_rev.reversed_entry_id = {alias}.id
                  AND am_rev.state = 'posted'
            )
        """

    def _invoice_move_search_domain(self, date_to):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_invoice", "out_refund", "in_invoice", "in_refund")),
            "|",
            ("invoice_date", "<=", date_to),
            "&",
            ("invoice_date", "=", False),
            ("date", "<=", date_to),
        ]
        if not self.include_reversed:
            domain.extend(
                [
                    ("reversed_entry_id", "=", False),
                    ("reversal_move_id", "=", False),
                ]
            )
        return domain

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
                             AND (
                                 am.move_type NOT IN ('out_invoice', 'out_refund')
                                 OR am.payment_state IN ('paid', 'in_payment')
                             )
                        THEN (-aml.balance) * (ad.value::numeric / 100.0)
                        ELSE 0
                    END
                ) AS ingreso,
                SUM(
                    CASE
                        WHEN aa.account_type IN ('expense', 'expense_direct_cost', 'expense_depreciation')
                             AND (
                                 am.move_type NOT IN ('in_invoice', 'in_refund')
                                 OR am.payment_state IN ('paid', 'in_payment')
                             )
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
              {self._sql_reversed_moves_clause('am')}
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
        moves = self.env["account.move"].search(self._invoice_move_search_domain(date_to))

        for move in moves:
            # Always compute weights against the full analytic distribution of the move.
            # If we normalize only on a filtered subset, CxC/CxP can be overstated to 100%.
            all_weights = self._weights_by_analytic(move, None)
            if not all_weights:
                continue

            total_weight = sum(all_weights.values())
            if not total_weight:
                continue

            if selected_analytic_ids:
                weights = {aid: w for aid, w in all_weights.items() if aid in selected_analytic_ids}
            else:
                weights = all_weights
            if not weights:
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
                if selected_analytic_ids is not None and analytic_id not in selected_analytic_ids:
                    continue
                weights[analytic_id] += base * (float(pct) / 100.0)
        return weights


class AnalyticDecisionMatrixWizardLine(models.Model):
    _name = "analytic.decision.matrix.wizard.line"
    _description = "Linea Matriz de Decision Analitica"
    _order = "is_total, project_label, id"

    wizard_id = fields.Many2one("analytic.decision.matrix.wizard", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="wizard_id.company_id", store=False)
    currency_id = fields.Many2one(related="company_id.currency_id", store=False)
    analytic_account_id = fields.Many2one("account.analytic.account", string="Proyecto")
    is_total = fields.Boolean(default=False, readonly=True)
    project_label = fields.Char(string="Proyecto", compute="_compute_project_label", store=True)

    ingreso = fields.Monetary(currency_field="currency_id", string="Ingreso")
    cxc = fields.Monetary(currency_field="currency_id", string="Ctas x Cob")
    reasignacion_in = fields.Monetary(currency_field="currency_id", string="Reasignacion (+)")
    egresos = fields.Monetary(currency_field="currency_id", string="Egresos")
    cxp = fields.Monetary(currency_field="currency_id", string="Ctas x Pag")
    reasignacion_out = fields.Monetary(currency_field="currency_id", string="Reasignacion (-)")
    saldo_devengado = fields.Monetary(currency_field="currency_id", string="Saldo Devengado")
    saldo_efectivo = fields.Monetary(currency_field="currency_id", string="Saldo Efectivo")
    open_residual_detail_ids = fields.One2many(
        "analytic.decision.matrix.open.move",
        "wizard_line_id",
        string="Detalle Ctas x Cob/Pag",
        readonly=True,
    )

    @api.depends("analytic_account_id", "is_total")
    def _compute_project_label(self):
        for line in self:
            if line.is_total:
                line.project_label = _("TOTAL GENERAL")
            else:
                line.project_label = line.analytic_account_id.display_name or ""

    def _get_move_line_ids(self, extra_where="", extra_params=None):
        self.ensure_one()
        if self.is_total or not self.analytic_account_id:
            return []
        extra_params = extra_params or []
        wizard = self.wizard_id
        date_to = wizard._effective_date_to()
        where_date_from = ""
        params = [wizard.company_id.id, str(self.analytic_account_id.id)]

        if wizard.date_from:
            where_date_from = "AND aml.date >= %s"
            params.append(wizard.date_from)

        params.extend(extra_params)
        params.append(date_to)
        self.env.cr.execute(
            f"""
            SELECT aml.id
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            LEFT JOIN account_journal aj ON aj.id = aml.journal_id
            WHERE am.state = 'posted'
              {wizard._sql_reversed_moves_clause('am')}
              AND aml.company_id = %s
              AND COALESCE(aml.analytic_distribution, '{{}}'::jsonb) ? %s
              {where_date_from}
              {extra_where}
              AND aml.date <= %s
            ORDER BY aml.date DESC, aml.id DESC
            """,
            tuple(params),
        )
        return [row[0] for row in self.env.cr.fetchall()]

    def _get_move_ids(self, extra_where="", extra_params=None):
        self.ensure_one()
        if self.is_total or not self.analytic_account_id:
            return []
        extra_params = extra_params or []
        wizard = self.wizard_id
        date_to = wizard._effective_date_to()
        where_date_from = ""
        params = [wizard.company_id.id, str(self.analytic_account_id.id)]

        if wizard.date_from:
            where_date_from = "AND aml.date >= %s"
            params.append(wizard.date_from)

        params.extend(extra_params)
        params.append(date_to)
        self.env.cr.execute(
            f"""
            SELECT DISTINCT am.id
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            LEFT JOIN account_journal aj ON aj.id = aml.journal_id
            WHERE am.state = 'posted'
              {wizard._sql_reversed_moves_clause('am')}
              AND aml.company_id = %s
              AND COALESCE(aml.analytic_distribution, '{{}}'::jsonb) ? %s
              {where_date_from}
              {extra_where}
              AND aml.date <= %s
            ORDER BY am.id DESC
            """,
            tuple(params),
        )
        return [row[0] for row in self.env.cr.fetchall()]

    def _open_move_lines_action(self, action_name, move_line_ids):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": action_name,
            "res_model": "account.move.line",
            "view_mode": "list,form",
            "domain": [("id", "in", move_line_ids)],
            "context": {
                "search_default_group_by_move": 1,
                "search_default_posted": 1,
            },
            "target": "current",
        }

    def _get_open_invoice_move_ids(self, target_key):
        self.ensure_one()
        if self.is_total or not self.analytic_account_id:
            return []
        wizard = self.wizard_id
        date_to = wizard._effective_date_to()
        move_ids = []
        moves = self.env["account.move"].search(wizard._invoice_move_search_domain(date_to))
        for move in moves:
            weights = wizard._weights_by_analytic(move, None)
            if not weights.get(self.analytic_account_id.id):
                continue
            if not abs(wizard._residual_signed_at_date(move, date_to)):
                continue
            if target_key == "cxc" and move.move_type in ("out_invoice", "out_refund"):
                move_ids.append(move.id)
            if target_key == "cxp" and move.move_type in ("in_invoice", "in_refund"):
                move_ids.append(move.id)
        return move_ids

    def _prepare_open_invoice_drilldown_vals(self, target_key):
        self.ensure_one()
        if self.is_total or not self.analytic_account_id:
            return []
        wizard = self.wizard_id
        date_to = wizard._effective_date_to()
        vals_list = []
        total_residual_amount = 0.0
        total_analytic_amount = 0.0
        moves = self.env["account.move"].search(wizard._invoice_move_search_domain(date_to))
        for move in moves:
            weights = wizard._weights_by_analytic(move, None)
            analytic_weight = weights.get(self.analytic_account_id.id)
            if not analytic_weight:
                continue

            total_weight = sum(weights.values())
            if not total_weight:
                continue

            residual_signed = wizard._residual_signed_at_date(move, date_to)
            residual_abs = abs(residual_signed)
            if not residual_abs:
                continue

            if target_key == "cxc" and move.move_type == "out_invoice":
                residual_total = residual_abs
            elif target_key == "cxc" and move.move_type == "out_refund":
                residual_total = -residual_abs
            elif target_key == "cxp" and move.move_type == "in_invoice":
                residual_total = residual_abs
            elif target_key == "cxp" and move.move_type == "in_refund":
                residual_total = -residual_abs
            else:
                continue

            analytic_ratio = analytic_weight / total_weight
            vals_list.append(
                {
                    "wizard_line_id": self.id,
                    "target_key": target_key,
                    "move_id": move.id,
                    "move_label": move.name or move.ref or "",
                    "amount_residual_total": residual_total,
                    "analytic_ratio": analytic_ratio * 100.0,
                    "amount_residual_analytic": residual_total * analytic_ratio,
                }
            )
            total_residual_amount += residual_total
            total_analytic_amount += residual_total * analytic_ratio
        if vals_list:
            vals_list.append(
                {
                    "wizard_line_id": self.id,
                    "target_key": target_key,
                    "is_total": True,
                    "move_label": _("TOTAL GENERAL"),
                    "amount_residual_total": total_residual_amount,
                    "amount_residual_analytic": total_analytic_amount,
                }
            )
        return vals_list

    def _open_moves_action(self, action_name, move_ids):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": action_name,
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", move_ids)],
            "context": {"search_default_posted": 1},
            "target": "current",
        }

    def _open_document_drilldown_action(self, action_name, move_ids):
        """In document mode, prefer expense sheets when moves come from hr.expense.sheet."""
        self.ensure_one()
        move_ids = [int(mid) for mid in (move_ids or []) if mid]
        if not move_ids:
            return self._open_moves_action(action_name, move_ids)

        sheets = self.env["hr.expense.sheet"].search([("account_move_ids", "in", move_ids)])
        if not sheets:
            return self._open_moves_action(action_name, move_ids)

        linked_move_ids = set(sheets.mapped("account_move_ids").ids)
        if set(move_ids).issubset(linked_move_ids):
            return {
                "type": "ir.actions.act_window",
                "name": action_name,
                "res_model": "hr.expense.sheet",
                "view_mode": "list,form",
                "domain": [("id", "in", sheets.ids)],
                "target": "current",
            }
        return self._open_moves_action(action_name, move_ids)

    def action_open_documents(self):
        self.ensure_one()
        if self.wizard_id.drilldown_document_view:
            move_ids = self._get_move_ids()
            return self._open_document_drilldown_action(
                _("Detalle documentos - %s") % (self.analytic_account_id.display_name,),
                move_ids,
            )
        move_line_ids = self._get_move_line_ids()
        return self._open_move_lines_action(
            _("Detalle documentos - %s") % (self.analytic_account_id.display_name,),
            move_line_ids,
        )

    def action_open_ingreso_documents(self):
        self.ensure_one()
        if self.wizard_id.drilldown_document_view:
            move_ids = self._get_move_ids(
                extra_where="""
                    AND aa.account_type IN ('income', 'income_other')
                    AND (
                        am.move_type NOT IN ('out_invoice', 'out_refund')
                        OR am.payment_state IN ('paid', 'in_payment')
                    )
                """
            )
            return self._open_document_drilldown_action(
                _("Detalle ingreso - %s") % (self.analytic_account_id.display_name,),
                move_ids,
            )
        move_line_ids = self._get_move_line_ids(
            extra_where="""
                AND aa.account_type IN ('income', 'income_other')
                AND (
                    am.move_type NOT IN ('out_invoice', 'out_refund')
                    OR am.payment_state IN ('paid', 'in_payment')
                )
            """
        )
        return self._open_move_lines_action(
            _("Detalle ingreso - %s") % (self.analytic_account_id.display_name,),
            move_line_ids,
        )

    def action_open_egresos_documents(self):
        self.ensure_one()
        if self.wizard_id.drilldown_document_view:
            move_ids = self._get_move_ids(
                extra_where="""
                    AND aa.account_type IN ('expense', 'expense_direct_cost', 'expense_depreciation')
                    AND (
                        am.move_type NOT IN ('in_invoice', 'in_refund')
                        OR am.payment_state IN ('paid', 'in_payment')
                    )
                """
            )
            return self._open_document_drilldown_action(
                _("Detalle egresos - %s") % (self.analytic_account_id.display_name,),
                move_ids,
            )
        move_line_ids = self._get_move_line_ids(
            extra_where="""
                AND aa.account_type IN ('expense', 'expense_direct_cost', 'expense_depreciation')
                AND (
                    am.move_type NOT IN ('in_invoice', 'in_refund')
                    OR am.payment_state IN ('paid', 'in_payment')
                )
            """
        )
        return self._open_move_lines_action(
            _("Detalle egresos - %s") % (self.analytic_account_id.display_name,),
            move_line_ids,
        )

    def action_open_reasignacion_in_documents(self):
        self.ensure_one()
        if self.wizard_id.drilldown_document_view:
            move_ids = self._get_move_ids(
                extra_where="AND aj.code = %s AND aml.debit > 0",
                extra_params=[self.wizard_id.reasignacion_journal_code],
            )
            return self._open_document_drilldown_action(
                _("Detalle reasignacion (+) - %s") % (self.analytic_account_id.display_name,),
                move_ids,
            )
        move_line_ids = self._get_move_line_ids(
            extra_where="AND aj.code = %s AND aml.debit > 0",
            extra_params=[self.wizard_id.reasignacion_journal_code],
        )
        return self._open_move_lines_action(
            _("Detalle reasignacion (+) - %s") % (self.analytic_account_id.display_name,),
            move_line_ids,
        )

    def action_open_reasignacion_out_documents(self):
        self.ensure_one()
        if self.wizard_id.drilldown_document_view:
            move_ids = self._get_move_ids(
                extra_where="AND aj.code = %s AND aml.credit > 0",
                extra_params=[self.wizard_id.reasignacion_journal_code],
            )
            return self._open_document_drilldown_action(
                _("Detalle reasignacion (-) - %s") % (self.analytic_account_id.display_name,),
                move_ids,
            )
        move_line_ids = self._get_move_line_ids(
            extra_where="AND aj.code = %s AND aml.credit > 0",
            extra_params=[self.wizard_id.reasignacion_journal_code],
        )
        return self._open_move_lines_action(
            _("Detalle reasignacion (-) - %s") % (self.analytic_account_id.display_name,),
            move_line_ids,
        )

    def action_open_cxc_documents(self):
        self.ensure_one()
        self.open_residual_detail_ids.filtered(lambda r: r.target_key == "cxc").unlink()
        vals_list = self._prepare_open_invoice_drilldown_vals("cxc")
        detail_records = self.env["analytic.decision.matrix.open.move"].create(vals_list)
        return {
            "type": "ir.actions.act_window",
            "name": _("Detalle Ctas x Cob - %s") % (self.analytic_account_id.display_name,),
            "res_model": "analytic.decision.matrix.open.move",
            "view_mode": "list,form",
            "domain": [("id", "in", detail_records.ids)],
            "target": "current",
        }

    def action_open_cxp_documents(self):
        self.ensure_one()
        self.open_residual_detail_ids.filtered(lambda r: r.target_key == "cxp").unlink()
        vals_list = self._prepare_open_invoice_drilldown_vals("cxp")
        detail_records = self.env["analytic.decision.matrix.open.move"].create(vals_list)
        return {
            "type": "ir.actions.act_window",
            "name": _("Detalle Ctas x Pag - %s") % (self.analytic_account_id.display_name,),
            "res_model": "analytic.decision.matrix.open.move",
            "view_mode": "list,form",
            "domain": [("id", "in", detail_records.ids)],
            "target": "current",
        }


class AnalyticDecisionMatrixOpenMove(models.Model):
    _name = "analytic.decision.matrix.open.move"
    _description = "Detalle Ctas x Cob/Pag por Cuenta Analitica"
    _order = "is_total, invoice_date desc, move_id desc, id desc"

    wizard_line_id = fields.Many2one(
        "analytic.decision.matrix.wizard.line",
        required=True,
        ondelete="cascade",
    )
    wizard_id = fields.Many2one(related="wizard_line_id.wizard_id", store=True, readonly=True)
    company_id = fields.Many2one(related="wizard_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    analytic_account_id = fields.Many2one(
        related="wizard_line_id.analytic_account_id",
        store=True,
        readonly=True,
    )
    target_key = fields.Selection(
        [("cxc", "Ctas x Cob"), ("cxp", "Ctas x Pag")],
        required=True,
        readonly=True,
    )
    move_id = fields.Many2one("account.move", readonly=True)
    move_label = fields.Char(string="Documento", readonly=True)
    is_total = fields.Boolean(default=False, readonly=True)
    partner_id = fields.Many2one(related="move_id.partner_id", store=True, readonly=True)
    invoice_date = fields.Date(related="move_id.invoice_date", store=True, readonly=True)
    date = fields.Date(related="move_id.date", store=True, readonly=True)
    amount_residual_total = fields.Monetary(currency_field="currency_id", readonly=True)
    analytic_ratio = fields.Float(string="% Analitica", digits=(16, 2), readonly=True)
    amount_residual_analytic = fields.Monetary(
        currency_field="currency_id",
        string="Residual Analitica",
        readonly=True,
    )
