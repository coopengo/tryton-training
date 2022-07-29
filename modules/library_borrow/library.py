from shutil import ExecError
from sql import Null
from sql.aggregate import Count, Min
from sql.operators import Concat
import datetime
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, ModelView, fields
from trytond.transaction import Transaction
from trytond.model.fields import SQL_OPERATORS



__all__ = [
    'User',
    'Checkout',
    'Exemplary',
    'Book',
    ]


class User(ModelSQL, ModelView):
    'Library User'
    __name__ = 'library.user'
    
    checkouts = fields.One2Many('library.user.checkout', 'user', 'Checkouts')
    first_name = fields.Char('First Name', required=True)
    last_name = fields.Char('Last Name', required=True)
    address = fields.Char('Address')
    birth_date = fields.Date('Birth Date')
    phone_number = fields.Char('Phone Number')
    registration_date = fields.Date('Registration Date', required=True)
    checkedout_books = fields.Function(fields.Integer('Checked-out books', help='The number of books a user has currently checked out'), 'getter_checkedout_books')
    late_checkedout_books = fields.Function(fields.Integer('Late checked-out books', help='The number of books a user is late returning'), 'getter_checkedout_books')
    expected_return_date = fields.Function(fields.Date('Expected return date'), 'getter_checkedout_books', searcher='search_expected_return_date')


    @classmethod
    def getter_checkedout_books(cls, users, name):
        result = {x.id: None for x in users}
        Checkout = Pool().get('library.user.checkout')
        checkout = Checkout.__table__()
        
        cursor = Transaction().connection.cursor()
        default_value = None
        if name not in ('checkedout_books', 'late_checkedout_books'):
            default_value = 0
        
        if name == 'checkedout_books':
            column = Count(checkout.id)
            where = checkout.return_date == Null
        elif name == 'late_checkedout_books':
            column = Count(checkout.id)
            where = (checkout.return_date == Null) & (checkout.date < datetime.date.today() + datetime.timedelta(days=20))
        elif name == 'expected_return_date':
            column =  Min(checkout.date)
            where = checkout.return_date == Null
        else:
            raise Exception('Invalid function field name %s' % name)
        
        cursor.execute(*checkout.select(checkout.user, column, where=where & checkout.user._in([x.id for x in users])))
        
        for user_id, value in cursor.fetchall():
            result[user_id] = value
            if name == 'expected_return_date' and name:
                value += datetime.timedelta(days=20)

        return result         
        

    
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
    
    user = fields.Many2One('library.user', 'User', required=True, ondelete='CASCADE', select=True)
    exemplary = fields.Many2One('library.book.exemplary', 'Exemplary', required=True, ondelete='CASCADE', select=True)
    date = fields.Date('Checkout date', required=True)
    return_date = fields.Date('Checkout_return_date')
    expected_return_date = fields.Function(fields.Date('Expected return date'), 'getter_expected_return_date', searcher='search_expected_return_date')
    
    def getter_expected_return_date(self, name):
        delta = datetime.timedelta(days=20)
        return self.date + delta

    @classmethod
    def search_expected_return_date(cls, name, clause):
        _, operator, operand = clause
        if isinstance(operand, datetime.date):
            operand = operand + datetime.timedelta(days=-20)
        if isinstance(operand, (list,tuple)):
            operand = [(x + datetime.timedelta(days=-20) if x else x) for x in operand]
        return [('date', operator, operand)]
    

class Book(metaclass=PoolMeta):
    __name__= 'library.book'
    
    is_available = fields.Function(fields.Boolean('Is available', help='If True, at least one exemplary of this book is currently available for borrowing'), 'getter_is_available', searcher='search_is_available')

    @classmethod
    def getter_is_available(cls, books, name):
        result = {x.id: False for x in books}
        
        pool = Pool()
        checkout = pool.Checkout.__table__()
        exemplary = pool.Exemplary.__table__()
        
        book = cls.__table__()
        cursor = Transaction().connection.cursor()
        
        cursor.execute(*book.join(exemplary, condition=(exemplary.book==book.id)
                    ).join(checkout, 'LEFT_OUTER', 
                    condition=(checkout.exemplary == exemplary.id)
                    ).select(book.id, where=(checkout.return_date != Null) | (checkout.id == Null)))
        
        for book_id, in cursor.fetchall():
            result[book_id] = True
        
        return result


    @classmethod
    def search_is_available(cls, name, clause):
        _, operator, operand = clause 
        if operator == '!=':
            operand = not operand 
        pool = Pool()
        checkout = pool.Checkout.__table__()
        exemplary = pool.Exemplary.__table__()
        book = cls.__table__()
    
        query = book.join(exemplary, condition=(exemplary.book==book.id)
                    ).join(checkout, 'LEFT_OUTER', 
                    condition=(checkout.exemplary == exemplary.id)
                    ).select(book.id, where=(checkout.return_date != Null) | (checkout.id == Null))
        
        return [('id', 'in' if operand else 'not in', query)]
    
    
    
class Exemplary(metaclass=PoolMeta):
    __name__ = 'library.book.exemplary'
    
    checkouts = fields.One2Many('library.user.checkout', 'exemplary', 'Checkouts')
    is_available = fields.Function(fields.Boolean('Is available', help='If True, the exemplary is currently available for borrowing'), 'getter_is_available')
    
    @classmethod
    def getter_is_available(cls, exemplaries, name):
        result = {x.id: True for x in exemplaries}
        
        Checkout = Pool().get('library.user.checkout')
        checkout = Checkout.__table__()
        
        cursor = Transaction().connection.cursor()
        cursor.execute(*checkout.select(checkout.exemplary, where=(checkout.return_date == Null) & checkout.exemplary._in([x.id for x in exemplaries])))
        
        for exemplary_id in cursor.fetchall():
            result[exemplary_id] = False
        return result
    
    @classmethod
    def order_rec_name(cls, tables):
        exemplary, _ = tables[None]
        book = tables.get('book')
        
        if book is None:
            book = Pool().get('library.book').__table__()
            tables['book'] = {None: (book, book.id == exemplary.book)}
            
        return [Concat(book.title, exemplary.identifier)]
  
    