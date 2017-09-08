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


class Editor(ModelSQL, ModelView):
    'Editor'
    __name__ = 'library.editor'

    genres = fields.Many2Many('library.editor-library.genre', 'editor',
        'genre', 'Genres')


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


class Book(ModelSQL, ModelView):
    'Book'
    __name__ = 'library.book'

    exemplaries = fields.One2Many('library.book.exemplary', 'book',
        'Exemplaries')
    genre = fields.Many2One('library.genre', 'Genre', ondelete='RESTRICT',
        required=False)


class Exemplary(ModelSQL, ModelView):
    'Exemplary'
    __name__ = 'library.book.exemplary'

    book = fields.Many2One('library.book', 'Book', ondelete='CASCADE',
        required=True)
