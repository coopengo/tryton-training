from sql import Null
from sql.aggregate import Count
from trytond.model import ModelSQL, fields, ModelView

__all__ = [
    'Floor',
    'Room',
    'Shelf',
    'Book',
    'Exemplary'
    ]

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


class Floor(ModelSQL, ModelView):
    'Floor'
    __name__ = 'library.floor'

    rooms = fields.One2Many('library.room', 'floor', 'Rooms')
    name = fields.Char('Name', required=True, help='Name of the floor')  # TODO: checker si > 0 et autres prérequis


class Room(ModelSQL, ModelView):
    'Room'
    __name__ = 'library.room'

    floor = fields.Many2One('library.floor', 'Floor', required=True, ondelete='CASCADE')
    shelves = fields.One2Many('library.shelf', 'room', 'Shelves')
    name = fields.Char('Name', required=True, help='Name of the room')  # TODO: checker si taille OK / autres prérequis


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
