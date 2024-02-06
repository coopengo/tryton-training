from trytond.pool import Pool

from . import library
from . import wizard


def register():
    Pool.register(
        module='library_borrow', type_='model')

    Pool.register(
        module='library_borrow', type_='wizard')
