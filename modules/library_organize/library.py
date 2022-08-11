import datetime
from sql import Null, Literal, Cast
from sql.aggregate import Count
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.model import ModelSQL, ModelView, fields, Unique
from trytond.pyson import Eval, Bool, And
from sql.operators import Not


__all__ = [
    'Room',
    'Shelf',
    'Exemplary',
]


class Room(ModelSQL, ModelView):
    'Library Room'
    __name__ = 'library.room'

    shelves = fields.One2Many('library.room.shelf', 'room', 'Shelves')
    name = fields.Char('Name', required=True)
    number_of_shelves = fields.Function(
        fields.Integer('Number of shelves'),
        'getter_number_of_shelves')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._buttons.update({
            'create_shelves': {},
        })

        cls._sql_constraints += [
            ('name_uniq', Unique(t, t.name),
                'The room name must be unique!'),
        ]

    @classmethod
    def getter_number_of_shelves(cls, rooms, name):
        result = {x.id: 0 for x in rooms}
        Shelf = Pool().get('library.room.shelf')
        shelf = Shelf.__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(*shelf.select(shelf.room, Count(shelf.id),
                                     where=shelf.room.in_(
                                         [x.id for x in rooms]),
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

    room = fields.Many2One('library.room', 'Room',
                           required=True, ondelete='CASCADE', select=True)
    identifier = fields.Integer('Identifier')
    exemplaries = fields.One2Many(
        'library.book.exemplary', 'shelf', 'Exemplaries')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('identifier_uniq', Unique(t, t.room, t.identifier),
                'The identifier must be unique!'),
        ]

    @classmethod
    def search_rec_name(cls, name, clause):
        try:
            value = int(clause[2][1:len(clause[2])-1])
        except:
            cls.raise_user_error('The shelf identifier must be numeric')
        return [
                ('identifier', '=',  value),
                ]

    def get_rec_name(self, name):
        return '%s: %s' % (self.room.rec_name, self.identifier)


class Exemplary(metaclass=PoolMeta):
    __name__ = 'library.book.exemplary'

    shelf = fields.Many2One('library.room.shelf', 'Shelf', states={'required': And(Bool(~Eval('in_storage', 'False')), Bool(~Eval('quarantine_on', 'False')), Bool(~Eval('quarantine_off', 'False')))},
                            depends=['in_storage'], select=True)

    in_storage = fields.Boolean('Is stored', help='If True, the exemplary is '
                                'currently in storage and not available for borrow')

    quarantine_on = fields.Function(
        fields.Boolean(
            'Quarantine On', help='If True, the exemplary is still in quarantine area, so not available for borrow'),
        'getter_exemplary_state', searcher='search_quarantine_on')

    quarantine_off = fields.Function(
        fields.Boolean('Quarantine Off',
                       help='The exemplary is located in the quarantine area'),
        'getter_exemplary_state', searcher='search_quarantine_off')

    return_to_shelf_date = fields.Date('Exposure date')

    @classmethod
    def default_return_to_shelf_date(cls):
        return datetime.date.today()

    @classmethod
    def _get_availability_result(self, exemplaries, name):
        result = {x.id: True if (
            not x.in_storage and x.return_to_shelf_date != None) else False for x in exemplaries}
        return result

    @classmethod
    def _get_availibility_query(cls, exemplary, checkout, name):
        Exemplary = Pool().get('library.book.exemplary')
        exemplaries = Exemplary.search(
            [('in_storage', '=', False), ('return_to_shelf_date', '!=', None)])
        query = exemplary.join(checkout, 'LEFT OUTER',
                               condition=(exemplary.id == checkout.exemplary)).select(exemplary.id, where=(((checkout.return_date != Null) | (checkout.id == Null)) & exemplary.id.in_([x.id for x in exemplaries])))
        return query

    @classmethod
    def getter_exemplary_state(cls, exemplaries, name):
        checkout = Pool().get('library.user.checkout').__table__()
        cursor = Transaction().connection.cursor()
        result, where, expected_result = cls._get_exemplary_state(
            exemplaries, checkout, name)
        cursor.execute(*checkout.select(checkout.exemplary,
                                        where=where & checkout.exemplary.in_([x.id for x in exemplaries])))
        for exemplary_id, in cursor.fetchall():
            result[exemplary_id] = expected_result
        return result

    @classmethod
    def _get_exemplary_state(cls, exemplaries, checkout, name):
        result, where, expected_result = {}, Literal(True), False
        if name == 'quarantine_on':
            result = {x.id: False for x in exemplaries}
            where = ((checkout.return_date != Null) & (
                checkout.return_date + datetime.timedelta(days=7) >= datetime.datetime.today()))
            expected_result = True
        elif name == 'quarantine_off':
            result = {x.id: True if (
                x.return_to_shelf_date == None and not x.in_storage) else False for x in exemplaries}
            where = ((checkout.return_date == Null) | (
                checkout.return_date + datetime.timedelta(days=7) > datetime.datetime.today()))
            expected_result = False
        else:
            raise Exception('Invalid function field name %s' % name)
        return result, where, expected_result

    @classmethod
    def search_quarantine_on(cls, name, clause):
        _, operator, value = clause
        if operator == '!=':
            value = not value
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = cls.__table__()
        Exemplary = pool.get('library.book.exemplary')
        exemplaries = Exemplary.search(
            [('in_storage', '=', False), ('return_to_shelf_date', '=', None)])
        _, where, _ = cls._get_exemplary_state(exemplaries, checkout, name)
        query = exemplary.join(checkout, 'LEFT OUTER',
                               condition=(exemplary.id == checkout.exemplary)
                               ).select(exemplary.id,
                                        where=where)
        return [('id', 'in' if value else 'not in', query)]

    @classmethod
    def search_quarantine_off(cls, name, clause):
        _, operator, value = clause
        if operator == '!=':
            value = not value
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = cls.__table__()
        Exemplary = pool.get('library.book.exemplary')
        exemplaries = Exemplary.search(
            [('in_storage', '=', False), ('return_to_shelf_date', '=', None)])
        _, where, _ = cls._get_exemplary_state(exemplaries, checkout, name)
        query = exemplary.join(checkout, 'LEFT OUTER',
                               condition=(exemplary.id == checkout.exemplary)
                               ).select(exemplary.id,
                                        where=(Not(where)))
        return [('id', 'in' if value else 'not in', query)]

    @fields.depends('in_storage')
    def on_change_with_return_to_shelf_date(self):
        if not self.in_storage:
            return datetime.date.today()

    @fields.depends('in_storage')
    def on_change_in_storage(self):
        if self.in_storage:
            self.shelf = None
            self.shelf.room = None
            self.is_available = True
