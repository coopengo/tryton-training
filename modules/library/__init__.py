from trytond.pool import Pool

import library


def register():
    Pool.register(
        library.Author,
        module='library', type_='model')
