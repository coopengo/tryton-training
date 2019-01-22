import datetime

from sql import Null
from sql.aggregate import Count, Min

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.model import ModelSQL, ModelView, fields
from trytond.model.fields import SQL_OPERATORS
from trytond.pyson import If, Eval, Date


__all__ = [
    'User',
    'Checkout',
    'Book',
    'Exemplary',
    ]


class User(ModelSQL, ModelView):
    'Library User'
    __name__ = 'library.user'

    checkouts = fields.One2Many('library.user.checkout', 'user', 'Checkouts')
    name = fields.Char('Name', required=True)
    registration_date = fields.Date('Registration Date', domain=[
            If(~Eval('registration_date'), [],
                [('registration_date', '<=', Date())])],
        help='The date at which the user registered in the library')
    checkedout_books = fields.Function(
        fields.Integer('Checked-out books', help='The number of books a user '
            'has currently checked out'),
        'getter_checkedout_books')
    late_checkedout_books = fields.Function(
        fields.Integer('Late checked-out books', help='The number of books a '
            'user is late returning'),
        'getter_checkedout_books')
    expected_return_date = fields.Function(
        fields.Date('Expected return date', help='The date at which the user '
            'is (or was) expected to return his books'),
        'getter_checkedout_books', searcher='search_expected_return_date')

    @classmethod
    def getter_checkedout_books(cls, users, name):
        checkout = Pool().get('library.user.checkout').__table__()
        cursor = Transaction().connection.cursor()
        default_value = None
        if name not in ('checkedout_books', 'late_checkedout_books'):
            default_value = 0
        result = {x.id: default_value for x in users}
        column, where = cls._get_checkout_column(checkout, name)
        cursor.execute(*checkout.select(checkout.user, column,
                where=where & checkout.user.in_([x.id for x in users]),
                group_by=[checkout.user]))
        for user_id, value in cursor.fetchall():
            result[user_id] = value
            if name == 'expected_return_date' and value:
                result[user_id] += datetime.timedelta(days=20)
        return result

    @classmethod
    def _get_checkout_column(cls, checkout_table, name):
        column, where = None, None
        if name == 'checkedout_books':
            column = Count(checkout_table.id)
            where = checkout_table.return_date == Null
        elif name == 'late_checkedout_books':
            column = Count(checkout_table.id)
            where = (checkout_table.return_date == Null) & (
                checkout_table.date < datetime.date.today() +
                datetime.timedelta(days=20))
        elif name == 'expected_return_date':
            column = Min(checkout_table.date)
            where = checkout_table.return_date == Null
        else:
            raise Exception('Invalid function field name %s' % name)
        return column, where

    @classmethod
    def search_expected_return_date(cls, name, clause):
        user = cls.__table__()
        checkout = Pool().get('library.user.checkout').__table__()
        _, operator, value = clause
        if isinstance(value, datetime.date):
            value = value + datetime.timedelta(days=-20)
        if isinstance(value, (list, tuple)):
            value = [(x + datetime.timedelta(days=-20) if x else x)
                for x in value]
        Operator = SQL_OPERATORS[operator]

        query_table = user.join(checkout, 'LEFT OUTER',
            condition=checkout.user == user.id)

        query = query_table.select(user.id,
            where=(checkout.return_date == Null) |
            (checkout.id == Null),
            group_by=user.id,
            having=Operator(Min(checkout.date), value))
        return [('id', 'in', query)]


class Checkout(ModelSQL, ModelView):
    'Checkout'
    __name__ = 'library.user.checkout'

    user = fields.Many2One('library.user', 'User', required=True,
        ondelete='CASCADE', select=True)
    exemplary = fields.Many2One('library.book.exemplary', 'Exemplary',
        required=True, ondelete='CASCADE', select=True)
    date = fields.Date('Date', required=True, domain=[
            ('date', '<=', Date())])
    return_date = fields.Date('Return Date', domain=[
            If(~Eval('return_date'), [],
                [('return_date', '<=', Date()),
                    ('return_date', '>=', Eval('date'))])],
        depends=['date'])
    expected_return_date = fields.Function(
        fields.Date('Expected return date', help='The date at which the  '
            'exemplary is supposed to be returned'),
        'getter_expected_return_date', searcher='search_expected_return_date')

    def getter_expected_return_date(self, name):
        return self.date + datetime.timedelta(days=20)

    @classmethod
    def search_expected_return_date(cls, name, clause):
        _, operator, value = clause
        if isinstance(value, datetime.date):
            value = value + datetime.timedelta(days=-20)
        if isinstance(value, (list, tuple)):
            value = [(x + datetime.timedelta(days=-20) if x else x)
                for x in value]
        return [('date', operator, value)]


class Book(metaclass=PoolMeta):
    __name__ = 'library.book'

    is_available = fields.Function(
        fields.Boolean('Is available', help='If True, at least an exemplary '
            'of this book is currently available for borrowing'),
        'getter_is_available', searcher='search_is_available')

    @classmethod
    def getter_is_available(cls, books, name):
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = pool.get('library.book.exemplary').__table__()
        book = cls.__table__()
        result = {x.id: False for x in books}
        cursor = Transaction().connection.cursor()
        cursor.execute(*book.join(exemplary,
                condition=(exemplary.book == book.id)
                ).join(checkout, 'LEFT OUTER',
                condition=(exemplary.id == checkout.exemplary)
                ).select(book.id,
                where=(checkout.return_date != Null) | (checkout.id == Null)))
        for book_id, in cursor.fetchall():
            result[book_id] = True
        return result

    @classmethod
    def search_is_available(cls, name, clause):
        _, operator, value = clause
        if operator == '!=':
            value = not value
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = pool.get('library.book.exemplary').__table__()
        book = cls.__table__()
        query = book.join(exemplary,
            condition=(exemplary.book == book.id)
            ).join(checkout, 'LEFT OUTER',
            condition=(exemplary.id == checkout.exemplary)
            ).select(book.id,
            where=(checkout.return_date != Null) | (checkout.id == Null))
        return [('id', 'in' if value else 'not in', query)]


class Exemplary(metaclass=PoolMeta):
    __name__ = 'library.book.exemplary'

    checkouts = fields.One2Many('library.user.checkout', 'exemplary',
        'Checkouts')
    is_available = fields.Function(
        fields.Boolean('Is available', help='If True, the exemplary is '
            'currently available for borrowing'),
        'getter_is_available', searcher='search_is_available')

    @classmethod
    def getter_is_available(cls, exemplaries, name):
        checkout = Pool().get('library.user.checkout').__table__()
        cursor = Transaction().connection.cursor()
        result = {x.id: True for x in exemplaries}
        cursor.execute(*checkout.select(checkout.exemplary,
                where=(checkout.return_date == Null)
                & checkout.exemplary.in_([x.id for x in exemplaries])))
        for exemplary_id, in cursor.fetchall():
            result[exemplary_id] = False
        return result

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('identifier',) + tuple(clause[1:]),
            ('book.title',) + tuple(clause[1:]),
            ]

    @classmethod
    def search_is_available(cls, name, clause):
        _, operator, value = clause
        if operator == '!=':
            value = not value
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = cls.__table__()
        query = exemplary.join(checkout, 'LEFT OUTER',
            condition=(exemplary.id == checkout.exemplary)
            ).select(exemplary.id,
            where=(checkout.return_date != Null) | (checkout.id == Null))
        return [('id', 'in' if value else 'not in', query)]
