from trytond.model import ModelSQL, fields, ModelView

__all__ = [
    'Floor',
    'Room',
    'Shelf',
    'Book',
    'Exemplary'
    ]

from trytond.pool import PoolMeta


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
    name = fields.Char('Name', required=True, help='Name of the shelf')
    exemplaries = fields.One2Many('library.book.exemplary', 'shelf', 'Exemplaries')


class Book(metaclass=PoolMeta):
    __name__ = 'library.book'

    @classmethod
    def default_exemplaries(cls):
        return []  # needed to avoid default creation of one exemplary with no identifier


class Exemplary(metaclass=PoolMeta):
    __name__ = 'library.book.exemplary'

    shelf = fields.Many2One('library.shelf', 'Shelf', ondelete='RESTRICT')  # exemplaries must be moved from shelf before deletion
