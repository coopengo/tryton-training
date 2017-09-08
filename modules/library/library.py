from trytond.model import ModelSQL, ModelView


__all__ = [
    'Author',
    ]


class Author(ModelSQL, ModelView):
    'Author'
    __name__ = 'library.author'
