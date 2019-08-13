# -*- coding: utf-8 -*-
#See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.addons.website.models import ir_http


class ResPartner(models.Model):
    _inherit = 'res.partner'

    last_website_hr_id = fields.Many2one('hotel.reservation', compute='_compute_last_website_hr_id', string='Last Online Hotel Reservation')

    @api.multi
    def _compute_last_website_hr_id(self):
        reservation = self.env['hotel.reservation']
        for partner in self:
            is_public = any([u._is_public()
                             for u in partner.with_context(active_test=False).user_ids])
#             website = ir_http.get_request_website()
            if not is_public:
#             if website and not is_public:
                partner.last_website_hr_id = reservation.search([
                    ('partner_id', '=', partner.id),
#                     ('website_id', '=', website.id),
                    ('state', '=', 'draft'),
                ], order='write_date desc', limit=1)
            else:
                partner.last_website_hr_id = reservation  # Not in a website context or public User
