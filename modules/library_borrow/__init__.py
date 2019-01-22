from trytond.pool import Pool

from . import library
from . import wizard


def register():
    Pool.register(
        library.User,
        library.Checkout,
        library.Book,
        library.Exemplary,
        wizard.BorrowSelectBooks,
        wizard.ReturnSelectCheckouts,
        module='library_borrow', type_='model')

    Pool.register(
        wizard.Borrow,
        wizard.Return,
        module='library_borrow', type_='wizard')
