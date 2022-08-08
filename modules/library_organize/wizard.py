import datetime

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, PYSONEncoder, Bool, Equal, Date, And
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
            # shelf.identifier = self.parameters.identifier_start + str(len(to_create) + 1)
            shelf.identifier = str(len(to_create) + 1)
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
    # identifier_start = fields.Char('Identifier start',
        # help='The starting point for shelves identifiers')
    shelves = fields.Many2Many('library.room.shelf', None, None,
        'Shelves')


class CreateExemplaries(metaclass=PoolMeta):
    'Organize New Exemplaries'
    __name__ = 'library.book.create_exemplaries'
    
    set_location = StateView('library.book.create_exemplaries.set_location',
        'library_organize.set_location_view_form', [
            Button('Cancel', 'delete_exemplaries_creation', 'tryton-cancel'),
            Button('Confirm', 'set_exemplaries_location', 'tryton-go-next',
                default=True)])
    set_exemplaries_location = StateTransition()
    delete_exemplaries_creation = StateTransition()
    
    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
                'invalid_storage_quantity': 'Number of exemplaries selected for storage is different than previously indicated',
                'invalid': 'here',
                })
        
    def default_parameters(self, name):
        if Transaction().context.get('active_model', '') == 'library.book':
            return super().default_parameters(name)
        return {
            'acquisition_date': datetime.date.today(),
            'book': None,
            'acquisition_price': 0,
            'exemplaries_to_select': [],
            }

    def transition_create_exemplaries(self):
        if (self.parameters.acquisition_date and
                self.parameters.acquisition_date > datetime.date.today()):
            self.raise_user_error('invalid_date')
        ExemplaryDisplayer = Pool().get('library.book.exemplary.displayer')
        self.to_display = []
        while len(self.to_display) < self.parameters.number_of_exemplaries:
            
            exemplary_displayer = ExemplaryDisplayer()
            exemplary_displayer.book = self.parameters.book
            exemplary_displayer.acquisition_date = self.parameters.acquisition_date
            exemplary_displayer.acquisition_price = self.parameters.acquisition_price
            exemplary_displayer.identifier = self.parameters.identifier_start + str(
                len(self.to_display) + 1)
            exemplary_displayer.in_storage = True
            self.parameters.exemplaries_to_select.append(exemplary_displayer)
            # self.to_display.append(exemplary_displayer)
        # self.set_location.exemplaries = to_display
        
        return 'set_location'
    
    
    def default_set_location(self, name):
        # if self.set_location._default_values:
        #     return self.set_location._default_values      
        return {
            'exemplaries': self.parameters.exemplaries_to_select,
            }
        
    
    def transition_set_exemplaries_location(self):
        Exemplary = Pool().get('library.book.exemplary')
        to_locate = []
        to_store = []
        for exemplary in self.set_location.exemplaries:
            if exemplary.in_storage:
                to_store.append(exemplary)
            to_locate.append(exemplary)
        if len(to_store) != self.parameters.number_exemplaries_to_store:
            self.raise_user_error('invalid_storage_quantity')
        Exemplary.save(to_locate)
        self.parameters.exemplaries = to_locate
        return 'open_exemplaries'
    
    
    def transition_delete_exemplaries_creation(self):
        Exemplary = Pool().get('library.book.exemplary')
        Exemplary.delete(self.parameters.exemplaries)
        return 'end'   
    
    def end(self):
        return 'reload'
    
    
class CreateExemplariesParameters(metaclass=PoolMeta):
    'New Exemplaries Information'
    __name__ = 'library.book.create_exemplaries.parameters'
    
    number_exemplaries_to_store = fields.Integer('Number of exemplaries to store')
    exemplaries_to_select = fields.Many2Many('library.book.exemplary.displayer', None, None, 'Exemplaries')
    # from_book = fields.Function(fields.Boolean('Action Launched From Book'), 'getter_from_book') 
   
    # to modify the readonly option for book in order to allow action initialization from menu
    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.book.readonly = False
        # cls.book.states = {'required': cls.from_book}
       
    
    # def getter_from_book(self, name):
    #     return True if Transaction().context.get('active_model') == 'library.book' else False
        

    @fields.depends('number_of_exemplaries')
    def on_change_with_number_exemplaries_to_store(self):
        return self.number_of_exemplaries


class SetLocation(ModelView):
    'New Exemplaries Location'
    __name__ = 'library.book.create_exemplaries.set_location'
    
    exemplaries = fields.Many2Many('library.book.exemplary.displayer', None, None, 'Exemplaries')
    
 
class ReturnToShelf(Wizard):
    'Return to Shelf'
    __name__ = 'library.book.exemplary.return_to_shelf'

    start_state = 'check_availibility'

    check_availibility = StateTransition()
    select_exemplaries = StateView('library.book.exemplary.return_to_shelf.select_exemplaries',
        'library_organize.return_to_shelf_select_exemplaries_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
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
            }
    
    def transition_return_to_shelf(self):
        Exemplary = Pool().get('library.book.exemplary')
        exemplaries = Exemplary.browse(Transaction().context.get('active_ids'))
        Exemplary.write(list(exemplaries), {
            'quarantine_off': False
        })     
        return 'end'
    
    def end(self):
        return 'reload'


class ReturnToShelfSelectedExemplaries(ModelView):
    'Select Exemplaries To Return'
    __name__ = 'library.book.exemplary.return_to_shelf.select_exemplaries'

    selected_exemplaries = fields.Many2Many('library.book.exemplary', None, None,
        'Selected exemplaries')
    
