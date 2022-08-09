import datetime
import json
from trytond.pool import Pool, PoolMeta
from trytond.pyson import PYSONEncoder
from trytond.transaction import Transaction
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, StateAction
from trytond.wizard import Button

__all__ = [
    'CreateShelves',
    'CreateShelvesParameters',
    'CreateExemplaries',
    'CreateExemplariesParameters',
    'SetLocation',
    'ReturnToShelf',
    'ReturnToShelfSelectedExemplaries',
    'Borrow',
]


class CreateShelves(Wizard):
    'Create Shelves'
    __name__ = 'library.room.create_shelves'

    start_state = 'parameters'
    parameters = StateView('library.room.create_shelves.parameters',
                           'library_organize.create_shelves_parameters_view_form', [
                               Button('Cancel', 'end', 'tryton-cancel'),
                               Button('Create', 'create_shelves', 'tryton-go-next',
                                      default=True)])
    create_shelves = StateTransition()
    open_shelves = StateAction('library_organize.act_open_room_shelf')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
            'invalid_model': 'This action should be started from a room',
        })

    def default_parameters(self, name):
        if Transaction().context.get('active_model', '') != 'library.room':
            self.raise_user_error('invalid_model')
        return {
            'room': Transaction().context.get('active_id'),
        }

    def transition_create_shelves(self):
        Shelf = Pool().get('library.room.shelf')
        to_create = []
        while len(to_create) < self.parameters.number_of_shelves:
            shelf = Shelf()
            shelf.room = self.parameters.room
            shelf.identifier = self.parameters.identifier_start + \
                str(len(to_create) + 1)
            to_create.append(shelf)
        Shelf.save(to_create)
        self.parameters.shelves = to_create
        return 'open_shelves'

    def do_open_shelves(self, action):
        action['pyson_domain'] = PYSONEncoder().encode([
            ('id', 'in', [x.id for x in self.parameters.shelves])])
        return action, {}


class CreateShelvesParameters(ModelView):
    'Create Shelves Parameters'
    __name__ = 'library.room.create_shelves.parameters'

    room = fields.Many2One('library.room', 'Room', readonly=True)
    number_of_shelves = fields.Integer('Number of shelves', domain=[('number_of_shelves', '>=', 0)],
                                       help='The number of shelves that will be created for this room')
    identifier_start = fields.Char('Identifier start',
                                   help='The starting point for shelves identifiers')
    shelves = fields.Many2Many('library.room.shelf', None, None,
                               'Shelves')


class CreateExemplaries(metaclass=PoolMeta):
    'Organize New Exemplaries'
    __name__ = 'library.book.create_exemplaries'

    set_location = StateView('library.book.create_exemplaries.set_location',
                             'library_organize.set_location_view_form', [
                                 Button('Cancel', 'end', 'tryton-cancel'),
                                 Button('Previous', 'parameters',
                                        'tryton-go-previous'),
                                 Button('Confirm', 'set_exemplaries_location', 'tryton-go-next',
                                        default=True)])
    set_exemplaries_location = StateTransition()
    delete_exemplaries_creation = StateTransition()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
            'invalid_storage_quantity': 'Number of exemplaries selected for storage is different than previously indicated',
            'invalid_room': 'The chosen shelf does not belong to the right room',
        })

    def default_parameters(self, name):
        if self.parameters._default_values:
            return self.parameters._default_values
        book = None
        if Transaction().context.get('active_model', '') == 'library.book':
            book = Transaction().context.get('active_id')

        return {
            'acquisition_date': datetime.date.today(),
            'book': book,
            'acquisition_price': 0,
            'exemplaries_to_select': [],
        }

    def transition_create_exemplaries(self):
        if (self.parameters.acquisition_date and
                self.parameters.acquisition_date > datetime.date.today()):
            self.raise_user_error('invalid_date')
        ExemplaryDisplayer = Pool().get('library.book.exemplary.displayer')
        to_display = []
        while len(to_display) < self.parameters.number_of_exemplaries:
            exemplary_displayer = ExemplaryDisplayer()
            exemplary_displayer.book = self.parameters.book
            exemplary_displayer.acquisition_date = self.parameters.acquisition_date
            exemplary_displayer.acquisition_price = self.parameters.acquisition_price
            exemplary_displayer.identifier = self.parameters.identifier_start + str(
                len(to_display) + 1)
            exemplary_displayer.in_storage = True
            exemplary_displayer.room = None
            exemplary_displayer.shelf = None
            self.parameters.exemplaries_to_select = list(
                self.parameters.exemplaries_to_select) + [exemplary_displayer]
            to_display.append(exemplary_displayer)
        return 'set_location'

    def default_set_location(self, name):
        exemplaries_to_display = []
        for exemplary in self.parameters.exemplaries_to_select:
            exemplary_to_display = {}
            exemplary_to_display['book'] = exemplary.book.id
            exemplary_to_display['acquisition_date'] = exemplary.acquisition_date
            exemplary_to_display['acquisition_price'] = exemplary.acquisition_price
            exemplary_to_display['identifier'] = exemplary.identifier
            exemplary_to_display['in_storage'] = exemplary.in_storage
            exemplary_to_display['room'] = exemplary.room
            exemplary_to_display['shelf'] = exemplary.shelf
            exemplaries_to_display.append(exemplary_to_display)
        return {
            'exemplaries': [x for x in exemplaries_to_display],
        }

    def transition_set_exemplaries_location(self):

        Exemplary = Pool().get('library.book.exemplary')
        to_store = []
        to_create = []

        for exemplary_parameters in self.set_location.exemplaries:
            exemplary = Exemplary()
            exemplary.book = exemplary_parameters.book
            exemplary.acquisition_date = exemplary_parameters.acquisition_date
            exemplary.acquisition_price = exemplary_parameters.acquisition_price
            exemplary.identifier = exemplary_parameters.identifier
            exemplary.in_storage = exemplary_parameters.in_storage
            exemplary.room = exemplary_parameters.room
            exemplary.shelf = exemplary_parameters.shelf
            exemplary.retun_to_shelf_date = exemplary_parameters.acquisition_date
            if exemplary.in_storage:
                to_store.append(exemplary)
            else:
                exemplary.return_to_shelf_date = datetime.date.today()
            to_create.append(exemplary)
        if len(to_store) != self.parameters.number_exemplaries_to_store:
            self.raise_user_error('invalid_storage_quantity')
        Exemplary.save(to_create)
        self.parameters.exemplaries = to_create
        return 'open_exemplaries'

    def end(self):
        return 'reload'


class CreateExemplariesParameters(metaclass=PoolMeta):
    'New Exemplaries Information'
    __name__ = 'library.book.create_exemplaries.parameters'

    number_exemplaries_to_store = fields.Integer(
        'Number of exemplaries to store')
    exemplaries_to_select = fields.One2Many(
        'library.book.exemplary.displayer', None, 'Exemplaries')
    in_storage = fields.Boolean('Is stored', help='If True, the exemplary is '
                                'currently in storage and not available for borrow')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.book.readonly = False

    @fields.depends('number_of_exemplaries')
    def on_change_with_number_exemplaries_to_store(self):
        return self.number_of_exemplaries


class SetLocation(ModelView):
    'New Exemplaries Location'
    __name__ = 'library.book.create_exemplaries.set_location'
    exemplaries = fields.One2Many(
        'library.book.exemplary.displayer', 'exemplary', 'Exemplaries')


class ReturnToShelf(Wizard):
    'Return to Shelf'
    __name__ = 'library.book.exemplary.return_to_shelf'

    start_state = 'check_availibility'

    check_availibility = StateTransition()
    select_exemplaries = StateView('library.book.exemplary.return_to_shelf.select_exemplaries',
                                   'library_organize.return_to_shelf_select_exemplaries_view_form', [
                                       Button('Cancel', 'end',
                                              'tryton-cancel'),
                                       Button('Return to shelf', 'return_to_shelf', 'tryton-go-next',
                                              default=True)])
    return_to_shelf = StateTransition()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
            'invalid_model': 'This action should be started from an exemplary',
            'already_available': 'One or more of selected exemplaries is/are already available to borrow',
            'still_in_quarantine': 'One or more of selected exemplaries is/are still in quarantine period',
        })

    def transition_check_availibility(self):
        if Transaction().context.get('active_model', '') != 'library.book.exemplary':
            self.raise_user_error('invalid_model')
        Exemplary = Pool().get('library.book.exemplary')
        exemplaries = Exemplary.browse(Transaction().context.get('active_ids'))
        for exemplary in exemplaries:
            if exemplary.is_available:
                self.raise_user_error('already_available')
            if exemplary.quarantine_on:
                self.raise_user_error('still_in_quarantine')
        return 'select_exemplaries'

    def default_select_exemplaries(self, name):
        Exemplary = Pool().get('library.book.exemplary')
        exemplaries = Exemplary.browse(Transaction().context.get('active_ids'))
        return {
            'selected_exemplaries': [x.id for x in exemplaries],
            'return_to_shelf_date': datetime.datetime.today(),
        }

    def transition_return_to_shelf(self):
        Exemplary = Pool().get('library.book.exemplary')
        Exemplary.write(list(self.select_exemplaries.selected_exemplaries), {
            'return_to_shelf_date': self.select_exemplaries.return_to_shelf_date})

        return 'end'

    def end(self):
        return 'reload'


class ReturnToShelfSelectedExemplaries(ModelView):
    'Select Exemplaries To Return'
    __name__ = 'library.book.exemplary.return_to_shelf.select_exemplaries'

    selected_exemplaries = fields.Many2Many('library.book.exemplary', None, None,
                                            'Selected exemplaries')
    return_to_shelf_date = fields.Date('Return to shelf date')


class Borrow(metaclass=PoolMeta):
    'Borrow books'
    __name__ = 'library.user.borrow'

    def transition_borrow(self):
        Checkout = Pool().get('library.user.checkout')
        Exemplary = Pool().get('library.book.exemplary')
        exemplaries = self.select_books.exemplaries
        user = self.select_books.user
        checkouts = []
        for exemplary in exemplaries:
            if not exemplary.is_available:
                self.raise_user_error('unavailable', {
                    'exemplary': exemplary.rec_name})
            checkouts.append(Checkout(
                user=user, date=self.select_books.date,
                exemplary=exemplary, return_date=None))
        Checkout.save(checkouts)
        Exemplary.write(list(exemplaries), {
            'return_to_shelf_date': None})

        self.select_books.checkouts = checkouts
        return 'checkouts'
