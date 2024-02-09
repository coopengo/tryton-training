from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, Button

__all__ = [
    'MoveExemplaries',
    'MoveExemplariesSelectShelf'
]


class MoveExemplaries(Wizard):
    'Move Exemplaries'
    __name__ = 'library.book.exemplary.move'

    start_state = 'check_availability'

    check_availability = StateTransition()
    select_shelf = StateView('library.book.examplary.move.select_shelf',
                             'library_area.move_select_shelf_view_form', [
                                 Button('Cancel', 'end', 'tryton-cancel'),
                                 Button('Put on reserve', 'move_to_reserve', 'tryton-go-next'),
                                 Button('Move', 'move_to_shelf', 'tryton-go-next', default=True)
                             ])
    move_to_reserve = StateTransition()
    move_to_shelf = StateTransition()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
            'unavailable_moved_exemplary': 'You cannot move an unavailable exemplary',
            'no_shelf_specified': 'You must specify a shelf to move exemplaries'
        })

    def transition_check_availability(self):
        if Transaction().context.get('active_model', '') != 'library.book.exemplary':
            self.raise_user_error('invalid_model')
        Exemplary = Pool().get('library.book.exemplary')
        exemplaries = Exemplary.browse(Transaction().context.get('active_ids'))
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
            # TODO: ajouter la selection par défaut des floor/room si shelf commun à tous (complètement facultatif)
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


class MoveExemplariesPreview(ModelView):
    'Move Exemplaries Preview'
    __name__ = 'library.book.examplary.move.preview'
