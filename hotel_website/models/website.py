from odoo import api, fields, models, tools
from odoo.http import request
from odoo.addons.website.models import ir_http


class Website(models.Model):
    _inherit = 'website'

    @api.multi
    def get_hotel_reservation(self, force_create=False):
        """ Return the current reservation after mofications specified by params.
        :param bool force_create: Create hotel reservation if not already existing
        :returns: browse record for the current hotel reservation
        """
        self.ensure_one()
        reservation_obj = self.env['hotel.reservation']
        partner = self.env.user.partner_id
        hotel_reservation_id = request.session.get('hotel_reservation_id')
        if not hotel_reservation_id:
            last_booking = partner.last_website_hr_id
            # Do not reload the cart of this customer last visit if the cart uses a pricelist no longer available.
            hotel_reservation_id =  last_booking.id if last_booking else False
        
        # Test validity of the hotel_reservation_id
        hotel_reservation = reservation_obj.sudo().browse(hotel_reservation_id).exists() if hotel_reservation_id else None
        # create so if needed
        if not hotel_reservation and force_create:
            addr = partner.address_get(['delivery', 'invoice'])
            vals = {'partner_id': partner.id,
                    'pricelist_id': partner.property_product_pricelist
                    and partner.property_product_pricelist.id or False,
                    'partner_invoice_id': addr['invoice'],
                    'partner_shipping_id': addr['delivery'],
                    }
            reservation_new = reservation_obj.new(vals)
            vals.update(reservation_new.default_get(reservation_new._fields))
            
            hotel_reservation = reservation_obj.sudo().create(vals)
            request.session['hotel_reservation_id'] = hotel_reservation.id
        
        if hotel_reservation:
            # case when customer emptied the cart
            if not request.session.get('hotel_reservation_id'):
                request.session['hotel_reservation_id'] = hotel_reservation.id
        else:
            request.session['hotel_reservation_id'] = None
            return self.env['hotel.reservation']
        
        return hotel_reservation
