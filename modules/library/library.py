import datetime

from sql import Window
from sql.conditionals import Coalesce
from sql.aggregate import Count, Max

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelSQL, ModelView, fields


__all__ = [
    'Genre',
    'Editor',
    'EditorGenreRelation',
    'Author',
    'Book',
    'Exemplary',
    ]


class Genre(ModelSQL, ModelView):
    'Genre'
    __name__ = 'library.genre'

    name = fields.Char('Name', required=True)


class Editor(ModelSQL, ModelView):
    'Editor'
    __name__ = 'library.editor'

    name = fields.Char('Name', required=True)
    creation_date = fields.Date('Creation date',
        help='The date at which the editor was created')
    genres = fields.Many2Many('library.editor-library.genre', 'editor',
        'genre', 'Genres')
    number_of_books = fields.Function(
        fields.Integer('Number of books'),
        'getter_number_of_books')

    @classmethod
    def getter_number_of_books(cls, editors, name):
        result = {x.id: 0 for x in editors}
        Book = Pool().get('library.book')
        book = Book.__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(*book.select(book.editor, Count(book.id),
                where=book.editor.in_([x.id for x in editors]),
                group_by=[book.editor]))
        for editor_id, count in cursor.fetchall():
            result[editor_id] = count
        return result


class EditorGenreRelation(ModelSQL):
    'Editor - Genre relation'
    __name__ = 'library.editor-library.genre'

    editor = fields.Many2One('library.editor', 'Editor', required=True,
        ondelete='CASCADE')
    genre = fields.Many2One('library.genre', 'Genre', required=True,
        ondelete='RESTRICT')


class Author(ModelSQL, ModelView):
    'Author'
    __name__ = 'library.author'

    books = fields.One2Many('library.book', 'author', 'Books')
    name = fields.Char('Name', required=True)
    birth_date = fields.Date('Birth date')
    death_date = fields.Date('Death date')
    gender = fields.Selection([('man', 'Man'), ('woman', 'Woman')], 'Gender')
    age = fields.Function(
        fields.Integer('Age'),
        'getter_age')
    number_of_books = fields.Function(
        fields.Integer('Number of books'),
        'getter_number_of_books')
    genres = fields.Function(
        fields.Many2Many('library.genre', None, None, 'Genres'),
        'getter_genres', searcher='searcher_genres')
    latest_book = fields.Function(
        fields.Many2One('library.book', 'Latest Book'),
        'getter_latest_book')

    def getter_age(self, name):
        if not self.birth_date:
            return None
        end_date = self.death_date or datetime.date.today()
        age = end_date.year - self.birth_date.year
        if (end_date.month, end_date.day) < (
                self.birth_date.month, self.birth_date.day):
            age -= 1
        return age

    def getter_genres(self, name):
        genres = set()
        for book in self.books:
            if book.genre:
                genres.add(book.genre.id)
        return list(genres)

    @classmethod
    def getter_latest_book(cls, authors, name):
        result = {x.id: None for x in authors}
        Book = Pool().get('library.book')
        book = Book.__table__()
        sub_book = Book.__table__()
        cursor = Transaction().connection.cursor()

        sub_query = sub_book.select(sub_book.author,
            Max(Coalesce(sub_book.publishing_date, datetime.date.min),
                window=Window([sub_book.author])).as_('max_date'),
            where=sub_book.author.in_([x.id for x in authors]))

        cursor.execute(*book.join(sub_query,
                condition=(book.author == sub_query.author)
                & (Coalesce(book.publishing_date, datetime.date.min)
                    == sub_query.max_date)
                ).select(book.author, book.id))
        for author_id, book in cursor.fetchall():
            result[author_id] = book
        return result

    @classmethod
    def getter_number_of_books(cls, authors, name):
        result = {x.id: 0 for x in authors}
        Book = Pool().get('library.book')
        book = Book.__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(*book.select(book.author, Count(book.id),
                where=book.author.in_([x.id for x in authors]),
                group_by=[book.author]))
        for author_id, count in cursor.fetchall():
            result[author_id] = count
        return result

    @classmethod
    def searcher_genres(self, name, clause):
        return []


class Book(ModelSQL, ModelView):
    'Book'
    __name__ = 'library.book'
    _rec_name = 'title'

    author = fields.Many2One('library.author', 'Author', required=True,
        ondelete='CASCADE')
    exemplaries = fields.One2Many('library.book.exemplary', 'book',
        'Exemplaries')
    title = fields.Char('Title', required=True)
    genre = fields.Many2One('library.genre', 'Genre', ondelete='RESTRICT',
        required=False)
    editor = fields.Many2One('library.editor', 'Editor', ondelete='RESTRICT',
        required=True)
    isbn = fields.Char('ISBN', size=13,
        help='The International Standard Book Number')
    publishing_date = fields.Date('Publishing date')
    description = fields.Char('Description')
    summary = fields.Text('Summary')
    cover = fields.Binary('Cover')
    page_count = fields.Integer('Page Count',
        help='The number of page in the book')
    edition_stopped = fields.Boolean('Edition stopped',
        help='If True, this book will not be printed again in this version')
    number_of_exemplaries = fields.Function(
        fields.Integer('Number of exemplaries'),
        'getter_number_of_exemplaries')
    latest_exemplary = fields.Function(
        fields.Many2One('library.book.exemplary', 'Latest exemplary'),
        'getter_latest_exemplary')

    def getter_latest_exemplary(self, name):
        latest = None
        for exemplary in self.exemplaries:
            if not exemplary.acquisition_date:
                continue
            if not latest or(
                    latest.acquisition_date < exemplary.acquisition_date):
                latest = exemplary
        return latest.id if latest else None

    @classmethod
    def getter_number_of_exemplaries(cls, books, name):
        result = {x.id: 0 for x in books}
        Exemplary = Pool().get('library.book.exemplary')
        exemplary = Exemplary.__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(*exemplary.select(exemplary.book, Count(exemplary.id),
                where=exemplary.book.in_([x.id for x in books]),
                group_by=[exemplary.book]))
        for book_id, count in cursor.fetchall():
            result[book_id] = count
        return result


class Exemplary(ModelSQL, ModelView):
    'Exemplary'
    __name__ = 'library.book.exemplary'
    _rec_name = 'identifier'

    book = fields.Many2One('library.book', 'Book', ondelete='CASCADE',
        required=True)
    identifier = fields.Char('Identifier', required=True)
    acquisition_date = fields.Date('Acquisition Date')
    acquisition_price = fields.Numeric('Acquisition Price', digits=(16, 2))

    def get_rec_name(self, name):
        return '%s: %s' % (self.book.rec_name, self.identifier)
