from trytond.pool import Pool

from . import library
from . import wizard


def register():
    Pool.register(
        library.Genre,
        library.Editor,
        library.EditorGenreRelation,
        library.Author,
        library.Book,
        library.Exemplary,
        wizard.CreateExemplariesParameters,
        wizard.FuseBooksSelectMain,
        wizard.FuseBooksPreview,
        module='library', type_='model')

    Pool.register(
        wizard.CreateExemplaries,
        wizard.FuseBooks,
        module='library', type_='wizard')
