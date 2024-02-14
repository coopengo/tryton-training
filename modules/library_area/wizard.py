from datetime import date

from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, Button

__all__ = [
    'MoveExemplaries',
    'MoveExemplariesSelectShelf',
    'ExitQuarantine',
    'CreateExemplaries',
    'CreateExemplariesParameters',
    'Borrow',
    'Return'
]


class MoveExemplaries(Wizard):
    'Move Exemplaries'
    __name__ = 'library.book.exemplary.move'

    start_state = 'check_availability'

    check_availability = StateTransition()
    select_shelf = StateView('library.book.examplary.move.select_shelf',
                             'library_area.move_select_shelf_view_form', [
                                 Button('Cancel', 'end', 'tryton-cancel'),
                                 Button('Move to reserve', 'move_to_reserve', 'tryton-go-next'),
                                 Button('Move', 'move_to_shelf', 'tryton-go-next', default=True)
                             ])
    move_to_reserve = StateTransition()
    move_to_shelf = StateTransition()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
            'no_exemplary': 'You have to select at least one exemplary to move to a shelf',
            'unavailable_moved_exemplary': 'You cannot move an unavailable exemplary',
            'no_shelf_specified': 'You must specify a shelf to move exemplaries',
            'quarantined_exemplary': 'Exemplary %(exemplary)s is currently in quarantine so it cannot be moved'
        })

    def transition_check_availability(self):
        if Transaction().context.get('active_model', '') != 'library.book.exemplary':
            self.raise_user_error('invalid_model')
        Exemplary = Pool().get('library.book.exemplary')
        exemplaries = Exemplary.browse(Transaction().context.get('active_ids'))
        if len(exemplaries) == 0:
            self.raise_user_error('no_exemplary')
        for e in exemplaries:
            if e.is_in_quarantine:
                self.raise_user_error('quarantined_exemplary', {'exemplary': e.rec_name})
        if not all([x.is_available for x in exemplaries]):
            self.raise_user_error('unavailable_moved_exemplary')
        return 'select_shelf'

    def default_select_shelf(self, name):
        if self.select_shelf._default_values:
            return self.select_shelf._default_values
        Exemplary = Pool().get('library.book.exemplary')
        exemplaries = Exemplary.browse(Transaction().context.get('active_ids'))
        return {
            'selected_exemplaries': [x.id for x in exemplaries]
        }

    def transition_move_to_shelf(self):
        if None in [self.select_shelf.floor, self.select_shelf.room, self.select_shelf.shelf]:
            self.raise_user_error('no_shelf_specified')
        shelf = self.select_shelf.shelf
        exemplaries = self.select_shelf.selected_exemplaries
        Exemplary = Pool().get('library.book.exemplary')
        Exemplary.write(list(exemplaries), {'shelf': shelf})
        return 'end'

    def transition_move_to_reserve(self):
        exemplaries = self.select_shelf.selected_exemplaries
        Exemplary = Pool().get('library.book.exemplary')
        Exemplary.write(list(exemplaries), {'shelf': None})
        return 'end'

    def end(self):
        return 'reload'


class MoveExemplariesSelectShelf(ModelView):
    'Move Exemplaries Select Shelf'
    __name__ = 'library.book.examplary.move.select_shelf'

    floor = fields.Many2One('library.floor', 'Floor')
    room = fields.Many2One('library.room', 'Room',
                           domain=[
                            If(
                               Bool(Eval('floor')),
                               ('floor', '=', Eval('floor')),
                               ('id', '=', None)
                           )], depends=['floor'])
    shelf = fields.Many2One('library.shelf', 'Shelf',
                            domain=[
                                If(
                                    Bool(Eval('room')),
                                    ('room', '=', Eval('room')),
                                    ('id', '=', None)
                                )], depends=['room'])
    selected_exemplaries = fields.Many2Many('library.book.exemplary', None, None,
                                            'Selected exemplaries', readonly=True)
    before_number_of_exemplaries = fields.Integer('In shelf before', readonly=True)
    after_number_of_exemplaries = fields.Integer('In shelf after', readonly=True)

    @fields.depends('floor')
    def on_change_with_room(self):
        if self.floor is None:
            return None

    @fields.depends('floor', 'room')
    def on_change_with_shelf(self):
        if self.room is None:
            return None

    @fields.depends('floor', 'room', 'shelf')
    def on_change_with_before_number_of_exemplaries(self):
        if None in [self.floor, self.room, self.shelf]:
            return None
        return self.shelf.number_of_exemplaries

    @fields.depends('floor', 'room', 'shelf', 'selected_exemplaries')
    def on_change_with_after_number_of_exemplaries(self):
        if None in [self.floor, self.room, self.shelf]:
            return None

        count_new_exemplaries = len([
            x.id for x in self.selected_exemplaries
            if x.shelf is None or x.shelf.id != self.shelf.id
        ])
        return self.shelf.number_of_exemplaries + count_new_exemplaries


class ExitQuarantine(Wizard):
    'Exit Quarantine'
    __name__ = 'library.book.exemplary.exit_quarantine'

    start_state = 'exit_quarantine'
    exit_quarantine = StateTransition()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
                'invalid_model': 'This action should be started from an exemplary',
                'not_in_quarantine': 'Exemplary %(exemplary)s is not currently in quarantine',
                'must_stay_in_quarantine': 'Exemplary %(exemplary)s must stay in quarantine until %(out_quarantine_date)s',
                })

    def transition_exit_quarantine(self):
        today = date.today()
        if Transaction().context.get('active_model', '') != 'library.book.exemplary':
            self.raise_user_error('invalid_model')
        Exemplary = Pool().get('library.book.exemplary')
        exemplaries = Exemplary.browse(Transaction().context.get('active_ids'))
        for exemplary in exemplaries:
            if exemplary.is_in_quarantine is False:
                self.raise_user_error('not_in_quarantine', {'exemplary': exemplary.rec_name})
            if exemplary.out_quarantine_date > date.today():
                self.raise_user_error('must_stay_in_quarantine',
                                      {'exemplary': exemplary.rec_name,
                                       'out_quarantine_date': exemplary.out_quarantine_date})
        Exemplary.write(list(exemplaries), {'in_quarantine_date': None})
        return 'end'

    def end(self):
        return 'reload'


class CreateExemplaries(metaclass=PoolMeta):
    __name__ = 'library.book.create_exemplaries'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
            'no_shelf_specified': 'You must specify a shelf for exemplaries that will not be moved to the reserve'
        })

    def transition_create_exemplaries(self):
        next_state = super().transition_create_exemplaries()

        shelf = self.parameters.shelf

        exemplaries = self.parameters.exemplaries
        number_to_reserve = self.parameters.number_to_reserve

        if number_to_reserve is not None and number_to_reserve < len(exemplaries):
            if self.parameters.shelf is None:
                self.raise_user_error('no_shelf_specified')
            exemplaries = exemplaries[:-number_to_reserve]

        Exemplary = Pool().get('library.book.exemplary')
        Exemplary.write(list(exemplaries), {'shelf': shelf})

        return next_state


class CreateExemplariesParameters(metaclass=PoolMeta):
    __name__ = 'library.book.create_exemplaries.parameters'

    floor = fields.Many2One('library.floor', 'Floor')
    room = fields.Many2One('library.room', 'Room',
                           domain=[If(
                               Bool(Eval('floor')),
                               ('floor', '=', Eval('floor')),
                               ('id', '=', None)
                           )], depends=['floor'])
    shelf = fields.Many2One('library.shelf', 'Shelf',
                            domain=[If(
                                Bool(Eval('room')),
                                ('room', '=', Eval('room')),
                                ('id', '=', None)
                            )], depends=['room'])
    number_to_reserve = fields.Integer(
        'Number to move to reserve',
        domain=[
            ('number_to_reserve', '>=', 0),
            ('number_to_reserve', '<=', Eval('number_of_exemplaries'))
        ], depends=['number_of_exemplaries'], help='Number of new exemplaries to move to the reserve'
    )

    @fields.depends('floor')
    def on_change_with_room(self):
        if self.floor is None:
            return None

    @fields.depends('floor', 'room')
    def on_change_with_shelf(self):
        if self.room is None:
            return None


class Borrow(metaclass=PoolMeta):
    __name__ = 'library.user.borrow'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
                'in_reserve': 'Exemplary %(exemplary)s is currently in reserve and unavailable for checkout',
                'in_quarantine': 'Exemplary %(exemplary)s is currently in quarantine and unavailable for checkout',
                })

    def transition_borrow(self):
        exemplaries = self.select_books.exemplaries
        for exemplary in exemplaries:
            if exemplary.is_in_reserve:
                self.raise_user_error('in_reserve', {'exemplary': exemplary.rec_name})
            elif exemplary.is_in_quarantine:
                self.raise_user_error('in_quarantine', {'exemplary': exemplary.rec_name})

        next_state = super().transition_borrow()
        return next_state


class Return(metaclass=PoolMeta):
    __name__ = 'library.user.return'

    def transition_return_(self):
        next_state = super().transition_return_()
        checkouts = self.select_checkouts.checkouts
        exemplaries = [c.exemplary for c in checkouts]
        Exemplary = Pool().get('library.book.exemplary')
        Exemplary.write(list(exemplaries), {'in_quarantine_date': self.select_checkouts.date})
        return next_state
