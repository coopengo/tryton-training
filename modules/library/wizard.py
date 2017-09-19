import datetime

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, StateAction
from trytond.wizard import Button

__all__ = [
    'CreateExemplaries',
    'CreateExemplariesParameters',
    ]


class CreateExemplaries(Wizard):
    'Create Exemplaries'
    __name__ = 'library.book.create_exemplaries'

    start_state = 'parameters'
    parameters = StateView('library.book.create_exemplaries.parameters',
        'library.create_exemplaries_parameters_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_exemplaries', 'tryton-go-next',
                default=True)])
    create_exemplaries = StateTransition()
    open_exemplaries = StateAction('library.act_exemplary')

    @classmethod
    def __setup__(cls):
        super(CreateExemplaries, cls).__setup__()
        cls._error_messages.update({
                'invalid_model': 'This action should be started from a book',
                'invalid_date': 'You cannot purchase books in the future',
                })

    def default_parameters(self, name):
        if Transaction().context.get('active_model', '') != 'library.book':
            self.raise_user_error('invalid_model')
        return {
            'acquisition_date': datetime.date.today(),
            'book': Transaction().context.get('active_id'),
            'acquisition_price': 0,
            }

    def transition_create_exemplaries(self):
        if (self.parameters.acquisition_date and
                self.parameters.acquisition_date > datetime.date.today()):
            self.raise_user_error('invalid_date')
        Exemplary = Pool().get('library.book.exemplary')
        to_create = []
        while len(to_create) < self.parameters.number_of_exemplaries:
            exemplary = Exemplary()
            exemplary.book = self.parameters.book
            exemplary.acquisition_date = self.parameters.acquisition_date
            exemplary.acquisition_price = self.parameters.acquisition_price
            exemplary.identifier = self.parameters.identifier_start + str(
                len(to_create) + 1)
            to_create.append(exemplary)
        Exemplary.save(to_create)
        self.parameters.exemplaries = to_create
        return 'open_exemplaries'

    def do_open_exemplaries(self, action):
        action['pyson_domain'] = [
            ('id', 'in', [x.id for x in self.parameters.exemplaries])]
        return action, {}


class CreateExemplariesParameters(ModelView):
    'Create Exemplaries Parameters'
    __name__ = 'library.book.create_exemplaries.parameters'

    book = fields.Many2One('library.book', 'Book', readonly=True)
    number_of_exemplaries = fields.Integer('Number of exemplaries',
        required=True, domain=[('number_of_exemplaries', '>', 0)],
        help='The number of exemplaries that will be created')
    identifier_start = fields.Char('Identifier start', required=True,
        help='The starting point for exemplaries identifiers')
    acquisition_date = fields.Date('Acquisition Date')
    acquisition_price = fields.Numeric('Acquisition Price', digits=(16, 2),
        domain=[('acquisition_price', '>=', 0)],
        help='The price that was paid per exemplary bought')
    exemplaries = fields.Many2Many('library.book.exemplary', None, None,
        'Exemplaries')
