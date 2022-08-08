from ast import And
import datetime
from urllib.parse import _NetlocResultMixinBytes

from sql import Null
from sql.operators import Concat
from sql.aggregate import Count, Min

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.model import ModelSQL, ModelView, fields, Unique
from trytond.model.fields import SQL_OPERATORS
from trytond.pyson import If, Eval, Date, Bool, And



__all__ = [
    'Room',
    'Shelf',
    'Exemplary',
    'ExemplaryDisplayer',
    ]


class Room(ModelSQL, ModelView):
    'Library Room'
    __name__ = 'library.room'

    shelves = fields.One2Many('library.room.shelf', 'room', 'Shelves')
    name = fields.Char('Name')
    number_of_shelves = fields.Function(
        fields.Integer('Number of shelves'),
        'getter_number_of_shelves')
    
    @classmethod
    def __setup__(cls):
        super().__setup__()
        # t = cls.__table__()
        cls._buttons.update({
                'create_shelves': {},
                })

    
    @classmethod
    def getter_number_of_shelves(cls, rooms, name):
        result = {x.id: 0 for x in rooms}
        Shelf = Pool().get('library.room.shelf')
        shelf = Shelf.__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(*shelf.select(shelf.room, Count(shelf.id),
                where=shelf.room.in_([x.id for x in rooms]),
                group_by=[shelf.room]))
        for room_id, count in cursor.fetchall():
            result[room_id] = count
        return result
    
    @classmethod
    @ModelView.button_action('library_organize.act_create_shelves')
    def create_shelves(cls, rooms):
        pass


class Shelf(ModelSQL, ModelView):
    'Shelf'
    __name__ = 'library.room.shelf'
    _rec_name = 'identifier'
   
    
    room = fields.Many2One('library.room', 'Room', ondelete='CASCADE')
    identifier = fields.Char('Identifier')
    capacity = fields.Integer('Capacity')
    exemplaries = fields.One2Many('library.book.exemplary', 'shelf', 'Exemplaries')
    
    # @classmethod
    # def __setup__(cls):
    #     super().__setup__()
    #     t = cls.__table__()
    #     cls._sql_constraints += [
    #         ('identifier_uniq', Unique(t, t.identifier),
    #             'The identifier must be unique!'),
    #         ]
    
    def get_rec_name(self, name):
        return '%s: %s' % (self.room.rec_name, self.identifier)
    

class Exemplary(metaclass=PoolMeta):
    __name__ = 'library.book.exemplary'
    
    # room = fields.Function(fields.Many2One('library.room', 'Room'), 'getter_room') 
    room = fields.Many2One('library.room', 'Room')
    shelf = fields.Many2One('library.room.shelf', 'Shelf', states={'required': And(Bool(~Eval('in_storage', 'False')), Bool(~Eval('quarantine_on', 'False')), Bool(~Eval('quarantine_off', 'False'))) },
        depends=['in_storage'])
    
    in_storage = fields.Boolean('Is stored', help='If True, the exemplary is '
            'currently in storage and not available for borrow')
    
    quarantine_on = fields.Function(
        fields.Boolean('Quarantine On', help='If True, the exemplary is still in quarantine area, so not available for borrow'),
        'getter_quarantine_on', searcher='search_quarantine_on')
    
    quarantine_off = fields.Function(
        fields.Boolean('Quarantine Off', help='The exemplary is located in the quarantine area'),
        'getter_quarantine_off', searcher='search_quarantine_off')


    # overriden 
    @classmethod
    def getter_is_available(cls, exemplaries, name):
        checkout = Pool().get('library.user.checkout').__table__()
        cursor = Transaction().connection.cursor()
        result = {x.id: True if (not x.in_storage and not x.quarantine_on and not x.quarantine_off) else False for x in exemplaries}
        cursor.execute(*checkout.select(checkout.exemplary,
                where=(checkout.return_date == Null)
                & checkout.exemplary.in_([x.id for x in exemplaries])))
        for exemplary_id, in cursor.fetchall():
            result[exemplary_id] = False
        return result
    
   
    @classmethod
    def getter_quarantine_on(cls, exemplaries, name):
        checkout = Pool().get('library.user.checkout').__table__()
        cursor = Transaction().connection.cursor()
        result = {x.id: False for x in exemplaries}
        cursor.execute(*checkout.select(checkout.exemplary,
                where=((checkout.return_date != Null) & (checkout.return_date + datetime.timedelta(days=7) >= datetime.datetime.today()))
                & checkout.exemplary.in_([x.id for x in exemplaries])))
        for exemplary_id, in cursor.fetchall():
            result[exemplary_id] = True
        return result
    
    @classmethod
    def search_quarantine_on(cls, name, clause):
        _, operator, value = clause
        if operator == '!=':
            value = not value
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = cls.__table__()
        query = exemplary.join(checkout, 'LEFT OUTER',
            condition=(exemplary.id == checkout.exemplary)
            ).select(exemplary.id,
            where=((checkout.return_date != Null) & (checkout.return_date + datetime.timedelta(days=7) >= datetime.datetime.today())))
        return [('id', 'in' if value else 'not in', query)]
    
    @classmethod
    def getter_quarantine_off(cls, exemplaries, name):
        checkout = Pool().get('library.user.checkout').__table__()
        cursor = Transaction().connection.cursor()
        result = {x.id: False for x in exemplaries}
        cursor.execute(*checkout.select(checkout.exemplary,
                where=((checkout.return_date != Null) & (checkout.return_date + datetime.timedelta(days=7) < datetime.datetime.today()))
                & checkout.exemplary.in_([x.id for x in exemplaries])))
        for exemplary_id, in cursor.fetchall():
            result[exemplary_id] = True
        return result
    
    @classmethod
    def search_quarantine_off(cls, name, clause):
        _, operator, value = clause
        if operator == '!=':
            value = not value
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = cls.__table__()
        query = exemplary.join(checkout, 'LEFT OUTER',
            condition=(exemplary.id == checkout.exemplary)
            ).select(exemplary.id,
            where=((checkout.return_date != Null) & (checkout.return_date + datetime.timedelta(days=7) < datetime.datetime.today())))
        return [('id', 'in' if value else 'not in', query)]
                                    

    def getter_room(self, name):
        if self.shelf:
            return self.shelf.room
          
    @fields.depends('in_storage')
    def on_change_with_is_available(self):
        return not self.in_storage
    
    @fields.depends('in_storage')
    def on_change_with_shelf(self):
        return None
    
    @fields.depends('in_storage')
    def on_change_with_room(self):
        return None
    

class ExemplaryDisplayer(ModelView):
    'Exemplary Displayer'
    __name__ = 'library.book.exemplary.displayer'
    _rec_name = 'identifier'
    
    book = fields.Many2One('library.book', 'Book')
    identifier = fields.Char('Identifier')
    acquisition_date = fields.Date('Acquisition Date')
    acquisition_price = fields.Numeric('Acquisition Price', digits=(16, 2),
        domain=['OR', ('acquisition_price', '=', None),
            ('acquisition_price', '>', 0)])
    in_storage = fields.Boolean('Is stored', help='If True, the exemplary is '
            'currently in storage and not available for borrow')
    
    def get_rec_name(self, name):
        return '%s: %s' % (self.book.rec_name, self.identifier)
    
  

