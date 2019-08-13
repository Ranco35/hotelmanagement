from odoo import api, fields, models, tools
from odoo.http import request
from odoo.addons.website.models import ir_http
from datetime import datetime


class HotelReservation(models.Model):
    _inherit = 'hotel.reservation'
    
    website_reservation_line = fields.One2many(
        'hotel_reservation.line',
        compute='_compute_website_reservation_line',
        string='Reservation Lines displayed on Website',
        help='Reservation Lines to be displayed on the website. They should not be used for computation purpose.',
    )
    cart_quantity = fields.Integer(compute='_compute_room_cart_info', string='Room Cart Quantity')

    @api.one
    def _compute_website_reservation_line(self):
        self.website_reservation_line = self.reservation_line

    @api.multi
    @api.depends('website_reservation_line.qty', 'website_reservation_line.room_id')
    def _compute_room_cart_info(self):
        for reservation in self:
            reservation.cart_quantity = int(sum(reservation.mapped('website_reservation_line.qty')))

    @api.multi
    def _reservation_cart_update(self, room_id=None, line_id=None, check_in=None, check_out=None, **kwargs):
        """ Add or Remove Rooms"""
        
        ReservationLineSudo = request.env['hotel_reservation.line']
        reservation_line = False
        if self.state != 'draft':
            request.session['hotel_reservation_id'] = None
            raise UserError(_('It is forbidden to modify a hotel reservation which is not in draft status.'))
        if line_id:
            domain = [('reservation_id', '=', self.id), ('id', '=', line_id)]
            reservation_line = ReservationLineSudo.sudo().search(domain)
            reservation_line.unlink()
        else:
            # Create line if no line with product_id can be located
            start_dt = datetime.strptime(check_in, '%m/%d/%Y').date()
            end_dt = datetime.strptime(check_out, '%m/%d/%Y').date()
            line_values = {
                    'room_id': room_id,
                    'checkin': start_dt,
                    'checkout': end_dt,
                    'qty': 1.0,
                    'reservation_id': self.id,
                }
            # Initiating a new reservation line record object
            reservation_line = ReservationLineSudo.new(line_values)
            line_values.update(reservation_line.sudo().default_get(
                reservation_line.default_get(reservation_line._fields)))
            line_values.update(reservation_line.sudo()._convert_to_write(
                {name: reservation_line[name] for name in reservation_line._cache}))
            if not line_values.get('name') and room_id:
                line_values.update({'name': reservation_line.room_id.name})

            if self.pricelist_id and self.partner_id:
                if reservation_line.get_price_from_rateplan(reservation_line.room_id):
                    line_values['price_unit'] = self.env[
                        'account.tax'].sudo()._fix_tax_included_price_company(
                            reservation_line.get_price_from_rateplan(reservation_line.room_id),
                        reservation_line.room_id.taxes_id, reservation_line.tax_id,
                        request.env.user.company_id.id)
                else:
                    line_values['price_unit'] = self.env[
                        'account.tax'].sudo()._fix_tax_included_price_company(
                            reservation_line._get_display_price(reservation_line.room_id),
                        reservation_line.room_id.taxes_id, reservation_line.tax_id,
                        request.env.user.company_id.id)
            reservation_line = ReservationLineSudo.sudo().create(line_values)
            reservation_line.sudo()._compute_tax_id()
        return {'room_qty': len(self.reservation_line),
                'checkin': self.checkin,
                'checkout': self.checkout,
                'total': self.amount_total,
                'untaxed':self.amount_untaxed,
                'tax': self.amount_tax}

