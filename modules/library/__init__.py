from trytond.pool import Pool

import library
import wizard


def register():
    Pool.register(
        library.Genre,
        library.Editor,
        library.EditorGenreRelation,
        library.Author,
        library.Book,
        library.Exemplary,
        wizard.CreateExemplariesParameters,
        module='library', type_='model')

    Pool.register(
        wizard.CreateExemplaries,
        module='library', type_='wizard')
