from trytond.pool import Pool

from . import library
from . import wizard


def register():
    Pool.register(
        library.Room,
        library.Shelf,
        library.Exemplary,
        wizard.CreateShelvesParameters,
        wizard.CreateExemplariesParameters,
        wizard.ExemplaryDisplayer,
        wizard.SetLocation,
        wizard.ReturnToShelfSelectedExemplaries,
        module='library_organize', type_='model')

    Pool.register(
        wizard.CreateShelves,
        wizard.CreateExemplaries,
        wizard.ReturnToShelf,
        wizard.Borrow,
        module='library_organize', type_='wizard')
