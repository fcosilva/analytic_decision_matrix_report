from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_open_business_doc_current(self):
        self.ensure_one()
        action = self.action_open_business_doc()
        if action:
            action["target"] = "current"
        return action

    def action_open_business_doc_modal(self):
        self.ensure_one()
        action = self.action_open_business_doc()
        if action:
            action["target"] = "new"
        return action

    def action_back_to_analytic_matrix(self):
        wizard_id = self.env.context.get("analytic_matrix_wizard_id")
        if not wizard_id:
            return False
        action = self.env["ir.actions.actions"]._for_xml_id(
            "analytic_decision_matrix_report.action_analytic_decision_matrix_wizard"
        )
        action.update({"res_id": wizard_id, "view_mode": "form", "views": [(False, "form")], "target": "current"})
        return action


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def action_open_business_doc_current(self):
        self.ensure_one()
        action = self.action_open_business_doc()
        if action:
            action["target"] = "current"
        return action

    def action_open_business_doc_modal(self):
        self.ensure_one()
        action = self.action_open_business_doc()
        if action:
            action["target"] = "new"
        return action

    def action_back_to_analytic_matrix(self):
        wizard_id = self.env.context.get("analytic_matrix_wizard_id")
        if not wizard_id:
            return False
        action = self.env["ir.actions.actions"]._for_xml_id(
            "analytic_decision_matrix_report.action_analytic_decision_matrix_wizard"
        )
        action.update({"res_id": wizard_id, "view_mode": "form", "views": [(False, "form")], "target": "current"})
        return action
