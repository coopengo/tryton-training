from sql import Null
from sql.aggregate import Count
from trytond.model import ModelSQL, fields, ModelView, Unique
from enum import Enum

__all__ = [
    'Floor',
    'Room',
    'Shelf',
    'Book',
    'Exemplary'
    ]

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


class Status(Enum):
    UNDEFINED = 'undefined'
    IN_RESERVE = 'in_reserve'
    IN_SHELF = 'in_shelf'
    BORROWED = 'borrowed'


class Floor(ModelSQL, ModelView):
    'Floor'
    __name__ = 'library.floor'

    rooms = fields.One2Many('library.room', 'floor', 'Rooms')
    name = fields.Char('Name', required=True, help='Name of the floor')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('name_uniq', Unique(t, t.name),
                'The floor must be unique!'),
            ]


class Room(ModelSQL, ModelView):
    'Room'
    __name__ = 'library.room'

    floor = fields.Many2One('library.floor', 'Floor', required=True, ondelete='CASCADE')
    shelves = fields.One2Many('library.shelf', 'room', 'Shelves')
    name = fields.Char('Name', required=True, help='Name of the room')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('name_uniq', Unique(t, t.floor, t.name),
                'The room must be unique in its floor!'),
            ]


class Shelf(ModelSQL, ModelView):
    'Shelf'
    __name__ = 'library.shelf'

    room = fields.Many2One('library.room', 'Room', required=True, ondelete='CASCADE')
    exemplaries = fields.One2Many('library.book.exemplary', 'shelf', 'Exemplaries')
    floor = fields.Function(fields.Many2One('library.floor', 'Floor'),
                            'getter_floor')
    name = fields.Char('Name', required=True, help='Name of the shelf')
    number_of_exemplaries = fields.Function(fields.Integer('Number of exemplaries'),
                                            'getter_number_of_exemplaries')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('name_uniq', Unique(t, t.room, t.name),
                'The shelf must be unique in its room!'),
            ]

    @fields.depends('exemplaries')
    def on_change_with_number_of_exemplaries(self):
        return len(self.exemplaries or [])

    def getter_floor(self, name):
        return self.room.floor.id if self.room and self.room.floor else None

    @classmethod
    def getter_number_of_exemplaries(cls, shelves, name):
        result = {x.id: 0 for x in shelves}
        Exemplary = Pool().get('library.book.exemplary')
        exemplary = Exemplary.__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(*exemplary.select(exemplary.shelf, Count(exemplary.id),
                where=exemplary.shelf.in_([x.id for x in shelves]),
                group_by=[exemplary.shelf]))
        for shelf_id, count in cursor.fetchall():
            result[shelf_id] = count
        return result


class Book(metaclass=PoolMeta):
    __name__ = 'library.book'

    is_in_reserve = fields.Function(fields.Boolean('In reserve', help='If True, this book as at least one exemplary in reserve'),
                                    'getter_is_in_reserve', searcher='search_is_in_reserve')

    @classmethod
    def default_exemplaries(cls):
        return []  # needed to avoid default creation of one exemplary with no identifier

    @classmethod
    def getter_is_in_reserve(cls, books, name):
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = pool.get('library.book.exemplary').__table__()
        book = cls.__table__()
        result = {x.id: False for x in books}
        cursor = Transaction().connection.cursor()
        cursor.execute(*book
                       .join(exemplary, condition=(exemplary.book == book.id))
                       .join(checkout, 'LEFT OUTER', condition=(exemplary.id == checkout.exemplary))
                       .select(book.id, where=((checkout.return_date != Null) | (checkout.id == Null)) & (exemplary.shelf == Null)))
        for book_id, in cursor.fetchall():
            result[book_id] = True
        return result

    @classmethod
    def search_is_in_reserve(cls, name, clause):
        _, operator, value = clause
        if operator == '!=':
            value = not value
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = pool.get('library.book.exemplary').__table__()
        book = cls.__table__()
        query = (book.join(exemplary, condition=(exemplary.book == book.id))
                 .join(checkout, 'LEFT OUTER', condition=(exemplary.id == checkout.exemplary))
                 .select(book.id, where=((checkout.return_date != Null) | (checkout.id == Null)) & (exemplary.shelf == Null)))
        return [('id', 'in' if value else 'not in', query)]


class Exemplary(metaclass=PoolMeta):
    __name__ = 'library.book.exemplary'

    shelf = fields.Many2One('library.shelf', 'Shelf', ondelete='SET NULL')  # exemplaries are moved to reserve if shelf is deleted
    room = fields.Function(fields.Many2One('library.room', 'Room'),
                           'getter_room')
    floor = fields.Function(fields.Many2One('library.floor', 'Floor'),
                            'getter_floor')
    is_in_reserve = fields.Function(fields.Boolean('In reserve', help='If True, this exemplary is in reserve'),
                                    'getter_is_in_reserve', searcher='search_is_in_reserve')

    status = fields.Function(fields.Selection([
        (Status.IN_RESERVE.value, 'IN RESERVE'),
        (Status.IN_SHELF.value, 'IN SHELF'),
        (Status.BORROWED.value, 'BORROWED'),
        (Status.UNDEFINED.value, 'UNDEFINED')],
        'Status', readonly=True),
        'on_change_with_status')

    @fields.depends('shelf', 'is_available', 'is_in_reserve')
    def on_change_with_status(self, name=None):
        status = Status.UNDEFINED
        if self.shelf is not None:
            status = Status.IN_SHELF
        if self.shelf is None and self.is_available is False:
            status = Status.BORROWED
        if self.is_in_reserve is True:
            status = Status.IN_RESERVE
        return status.value

    def getter_room(self, name):
        return self.shelf.room.id if self.shelf and self.shelf.room else None

    def getter_floor(self, name):
        return self.room.floor.id if self.room and self.room.floor else None

    @classmethod
    def getter_is_in_reserve(cls, exemplaries, name):
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = cls.__table__()
        result = {x.id: False for x in exemplaries}
        cursor = Transaction().connection.cursor()
        cursor.execute(*exemplary
                       .join(checkout, 'LEFT OUTER', condition=(exemplary.id == checkout.exemplary))
                       .select(exemplary.id, where=((checkout.return_date != Null) | (checkout.id == Null)) & (exemplary.shelf == Null)))
        for exemplary_id, in cursor.fetchall():
            result[exemplary_id] = True
        return result

    @classmethod
    def search_is_in_reserve(cls, name, clause):
        _, operator, value = clause
        if operator == '!=':
            value = not value
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = cls.__table__()
        query = (exemplary
                 .join(checkout, 'LEFT OUTER', condition=(exemplary.id == checkout.exemplary))
                 .select(exemplary.id, where=((checkout.return_date != Null) | (checkout.id == Null)) & (exemplary.shelf == Null)))
        return [('id', 'in' if value else 'not in', query)]
