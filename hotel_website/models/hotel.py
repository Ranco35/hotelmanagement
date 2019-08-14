
from odoo import api, fields, models, tools


class RoomReview(models.Model):
    _name = "room.review"

    room_id = fields.Many2one('hotel.room', 'Hotel Room')
    name = fields.Char('Name')
    email = fields.Char('Email')
    comment = fields.Text('Comment')
    review_dt = fields.Date('Reviewed On')
    star_rating = fields.Selection([('0', 'zero'),
                                    ('1', 'one'),
                                    ('2', 'two'),
                                    ('3', 'three'),
                                    ('4', 'four'),
                                    ('5', 'five')], 'Star Rating',
                                    default='0')


class HotelRoomExtend(models.Model):
    _inherit = "hotel.room"

    room_review_ids = fields.One2many('room.review', 'room_id', 'Reviews')