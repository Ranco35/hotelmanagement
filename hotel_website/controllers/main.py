# See LICENSE file for full copyright and licensing details
# import json
import re
from datetime import datetime, date
from odoo import fields, http, tools, _
from odoo.http import request, content_disposition
from odoo.exceptions import ValidationError, AccessError, MissingError, UserError
from odoo.addons.payment.controllers.portal import PaymentProcessing
from odoo.addons.website.controllers.main import Website
from odoo.addons.http_routing.models.ir_http import slug
import werkzeug.utils


class WebsiteHomepage(Website):

    @http.route()
    def index(self, **kw):
        """Render the Homepage."""
        room_type = request.env['hotel.room'].sudo().search([])
        return request.render('website.homepage', {'room_type': room_type})

class HotelManagement(http.Controller):
    
    MANDATORY_BILLING_FIELDS = ["name", "mobile", "email", "street", "country_id", "city"]
    OPTIONAL_BILLING_FIELDS = ["zipcode", "state_id", "street2", "phone"]

    @http.route('/room-search', type='http', auth="public",
                csrf=False, website=True)
    def check_room_avilability(self, **kw):
        reservation = request.website.get_hotel_reservation()
        if reservation and reservation.state != 'draft':
            request.session['hotel_reservation_id'] = None
            reservation = request.website.get_hotel_reservation()
        cr = request.env.cr
        room_obj = request.env['hotel.room']
        reservation_line = request.env['hotel_reservation.line']
        room_type = room_obj.sudo().search([])
        rooms = []
        room_price_lst = {}
        domain = [('status', '=', 'available'),
                  ('rooms_qty', '>=', 1)]
        if kw.get('room_type'):
            domain += [('id', '=', int(kw.get('room_type')))]
        room_list = room_obj.search(domain).ids
        if kw.get('checkin_date') and kw.get('departure_date'):
            start_dt = datetime.strptime(kw.get('checkin_date'), '%m/%d/%Y').date()
            end_dt = datetime.strptime(kw.get('departure_date'), '%m/%d/%Y').date()
            for room_id in room_list:
                room = room_obj.browse(room_id)
                cr.execute("""SELECT room_id, sum(room_qty) as qty FROM
                                hotel_room_move WHERE state != 'cancel' AND
                                room_id=%s AND (%s,%s) OVERLAPS
                                (check_in, check_out)
                                AND company_id=%s
                                GROUP BY room_id""",
                                 (room_id, start_dt, end_dt,
                                  request.env.user.company_id.id))
                data = cr.dictfetchone()
                room_qty = room.rooms_qty
                if reservation_line.check_room_closing_status(room, start_dt,
                                                              end_dt):
                    room_list.remove(room_id)
                elif reservation_line.get_qty_from_avaliability(
                        room, start_dt, end_dt):
                    room_qty = reservation_line.get_qty_from_avaliability(
                        room, start_dt, end_dt)
                if data is not None and room_qty <= data.get('qty'):
                    room_list.remove(room_id)
            rooms = request.env['hotel.room'].sudo().search([('id', 'in', room_list)])
        if kw.get('room_type'):
            kw['room_type'] = int(kw.get('room_type'))
        for room in rooms:
            rate_plan = 00.00
            cr.execute(
                """SELECT AVG(room_price) FROM room_pricelist_line
                WHERE room_id=%s AND date BETWEEN %s AND %s
                AND company_id=%s""",
                (room.id, start_dt, end_dt,
                 request.env.user.company_id.id))
            rate_plan = cr.fetchone()[0]
            if not rate_plan:
                rate_plan = room.list_price
            room_price_lst['%s' % room.id] = rate_plan
        data = {
            'room_type': room_type,
            'rooms': rooms,
            'kw': kw,
            'website_hotel_reservation': reservation,
            'room_price_lst': room_price_lst,
        }
        return request.render('hotel_website.hotel_book_layout', data)

    @http.route(['/hotel_review'], type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def post_customer_review(self, **kw):
        ReviewObj = request.env['room.review']
        HotelRoom=request.env['hotel.room']
        room=HotelRoom.search([('id','=',int(kw.get('room_id')))])
        value = {'name': kw.get('user'),
                 'email': kw.get('email'),
                 'comment': kw.get('comment'),
                 'room_id': int(kw.get('room_id')),
                 'review_dt': str(date.today()),
                 'star_rating': str(kw.get('star_rating')) if kw.get('star_rating') else '0'
                }
        ReviewObj.sudo().create(value)
        pager_url = "/room-detail/%s" % slug(room)
        return werkzeug.utils.redirect(pager_url)

    @http.route('/gallary', type='http', auth="public", website=True)
    def hotel_gallarypage(self, **post):
        """Render the Gallary Page."""
        return request.render('hotel_website.hotel_gallary_layout', {})
    
    @http.route(['/update_room_cart'], type='json', auth="public", website=True)
    def update_room_cart(self, room_id=None, check_in=None, line_id=None, check_out=None, **kw):
        reservation = request.website.get_hotel_reservation(force_create=True)
        if reservation.state != 'draft':
            request.session['hotel_reservation_id'] = None
            reservation = request.website.get_hotel_reservation(force_create=True)
        line = reservation._reservation_cart_update(
            room_id = int(room_id) if room_id else None,
            line_id = int(line_id) if line_id else None,
            check_in=check_in if check_in else None,
            check_out=check_out if check_out else None,
        )
        return line

    @http.route(['/room/cart'], type='http', auth="public", website=True)
    def cart(self, access_token=None, revive='', **post):
        reservation = request.website.get_hotel_reservation()
        values = {}
        if reservation and reservation.state != 'draft':
            request.session['hotel_reservation_id'] = None
            reservation = request.website.get_hotel_reservation()
        values.update({
            'website_hotel_reservation': reservation,
            'date': fields.Date.today(),
            'post': post,
        })
        if post.get('type') == 'popover':
            # force no-cache so IE11 doesn't cache this XHR
            return request.render("hotel_website.room_cart_popover", values, headers={'Cache-Control': 'no-cache'})
        values.update({'checkout': False})
        return request.render("hotel_website.room_cart", values)

    @http.route(['/room-detail/<model("hotel.room"):room>'], type='http', auth="public", website=True)
    def hotel_room_detail(self, room, **post):
        data = {
            'room': room,
        }
        return request.render('hotel_website.hotel_room_detail_layout', data)
    
    def customer_form_validate(self, data):
        error = dict()
        error_message = []

        # Validation
        for field_name in self.MANDATORY_BILLING_FIELDS:
            if not data.get(field_name):
                error[field_name] = 'missing'

        # email validation
        if data.get('email') and not tools.single_email_re.match(data.get('email')):
            error["email"] = 'error'
            error_message.append(_('Invalid Email! Please enter a valid email address.'))

        # error message for empty required fields
        if [err for err in error.values() if err == 'missing']:
            error_message.append(_('Some required fields are empty.'))

        unknown = [k for k in data if k not in self.MANDATORY_BILLING_FIELDS + self.OPTIONAL_BILLING_FIELDS]
        if unknown:
            error['common'] = 'Unknown field'
            error_message.append("Unknown field '%s'" % ','.join(unknown))
        return error, error_message
    
    @http.route(['/room/checkout'], type='http', auth="public",
                csrf=False, website=True)
    def checkout(self, **post):
        partner_obj = request.env['res.partner']
        reservation = request.website.get_hotel_reservation()
        if reservation and 'addition_info' in post:
            if post.get('addition_info'):
                reservation.sudo().write({'remarks': post.get('addition_info')})
            list(map(post.pop, ['addition_info']))
        existing_customer = False
        
        values = {'error': {},
                    'error_message': [],
                    'website_hotel_reservation': reservation,
                    'checkout': True,
                    'countries': request.env['res.country'].sudo().search([]),
                    'states': request.env['res.country.state'].sudo().search([]),
                    'old_user': post.get('old_customer') or '',
                    'existing_customer': existing_customer}
        if post:
            if post.get('old_customer'):
                partner = partner_obj.sudo().search(
                    [('email', '=', post.get('old_customer'))], limit=1)
                if partner:
                    values.update({'partner': partner, 'existing_customer': True})
                list(map(post.pop, ['old_customer']))
            else:
                hotel_policy = post.get('hotel_policy')
                list(map(post.pop, ['hotel_policy', 'csrf_token']))
                error, error_message = self.customer_form_validate(post)
                values.update({'error': error, 'error_message': error_message, 'post': post})
                if not error:
                    vals = {key: post[key] for key in self.MANDATORY_BILLING_FIELDS}
                    vals.update({key: post[key] for key in self.OPTIONAL_BILLING_FIELDS if key in post})
                    vals.update({'zip': vals.pop('zipcode', ''),
                                 'is_hotel_guest': True})
                    partner = partner_obj.sudo().search(
                    [('email', '=', vals.get('email'))], limit=1)
                    if partner:
                        partner.sudo().write(vals)
                    else:
                        partner=partner_obj.sudo().create(vals)
                    reservation.sudo().write({'partner_id': partner.id,
                                              'partner_invoice_id': partner.id,
                                              'hotel_policy': hotel_policy})
                    try:
                        reservation.sudo().confirmed_reservation()
                    except ValidationError as e:
                        values.update({'room_error': e.args[0]})
                        return request.render("hotel_website.room_checkout", values)
                    template = request.env.ref(
                    'hotel_reservation.mail_template_hotel_reservation')
                    template.sudo().send_mail(reservation.id, force_send=True)
                    invoice_id = reservation.sudo().action_invoice_create()
                    invoice_rec = request.env['account.invoice'].sudo().browse(
                        invoice_id)
                    invoice_rec.sudo().action_invoice_open()
                    request.session.update({'hotel_reservation_id': False})
                    return request.redirect('/customer/invoice/'+str(invoice_rec.id))

        return request.render("hotel_website.room_checkout", values)

    def _document_check_access(self, model_name, document_id, access_token=None):
        document = request.env[model_name].browse([document_id])
        document_sudo = document.sudo().exists()
        if not document_sudo:
            raise MissingError("This document does not exist.")
        try:
            document.check_access_rights('read')
            document.check_access_rule('read')
        except AccessError:
            if not access_token or not consteq(document_sudo.access_token, access_token):
                raise
        return document_sudo
    
    def _show_report(self, model, report_type, report_ref, download=False):
        if report_type not in ('html', 'pdf', 'text'):
            raise UserError("Invalid report type: %s" % report_type)

        report_sudo = request.env.ref(report_ref).sudo()

        if not isinstance(report_sudo, type(request.env['ir.actions.report'])):
            raise UserError("%s is not the reference of a report" % report_ref)

        method_name = 'render_qweb_%s' % (report_type)
        report = getattr(report_sudo, method_name)([model.id], data={'report_type': report_type})[0]
        reporthttpheaders = [
            ('Content-Type', 'application/pdf' if report_type == 'pdf' else 'text/html'),
            ('Content-Length', len(report)),
        ]
        if report_type == 'pdf' and download:
            filename = "%s.pdf" % (re.sub('\W+', '-', model._get_report_base_filename()))
            reporthttpheaders.append(('Content-Disposition', content_disposition(filename)))
        return request.make_response(report, headers=reporthttpheaders)

    def _invoice_get_page_view_values(self, invoice, access_token, **kwargs):
        values = {'invoice': invoice}
        payment_inputs = request.env['payment.acquirer']._get_available_payment_input(company=invoice.company_id)
        # if not connected (using public user), the method _get_available_payment_input will return public user tokens
        is_public_user = request.env.user._is_public()
        if is_public_user:
            # we should not display payment tokens owned by the public user
            payment_inputs.pop('pms', None)
            token_count = request.env['payment.token'].sudo().search_count([('acquirer_id.company_id', '=', invoice.company_id.id),
                                                                      ('partner_id', '=', invoice.partner_id.id),
                                                                    ])
            values['existing_token'] = token_count > 0
        values.update(payment_inputs)
        # if the current user is connected we set partner_id to his partner otherwise we set it as the invoice partner
        # we do this to force the creation of payment tokens to the correct partner and avoid token linked to the public user
        values['partner_id'] = invoice.partner_id if is_public_user else request.env.user.partner_id,
        return values

    @http.route(['/customer/invoice/<int:invoice_id>'], type='http', auth="public", website=True)
    def customer_invoice_detail(self, invoice_id, access_token=None, report_type=None, download=False, **kw):
        try:
            invoice_sudo = self._document_check_access('account.invoice', invoice_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/')

        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(model=invoice_sudo, report_type=report_type, report_ref='account.account_invoices', download=download)

        values = self._invoice_get_page_view_values(invoice_sudo, access_token, **kw)
        PaymentProcessing.remove_payment_transaction(invoice_sudo.transaction_ids)
        return request.render("hotel_website.customer_invoice", values)

    @http.route('/room/confirmation', type='http', auth="public", website=True)
    def room_confirmation(self, **post):
        """Render the Confirmation."""
        return request.render("hotel_website.booking_confirm", {})
