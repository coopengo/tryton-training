from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval
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
                                 # Button('Preview', 'preview', 'tryton-go-next', default=True)
                             ])
    # preview = StateView('library.book.examplary.move.preview',
    #                     'library_area.move_preview_view_form', [
    #                         Button('Previous', 'select_shelf', 'tryton-go-previous'),
    #                         Button('Cancel', 'end', 'tryton-cancel'),
    #                         Button('Move', 'move', 'tryton-go-next', default=True)])
    # move = StateTransition()
    # refresh = StateTransition()  # TODO: Nécessaire ?

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
                'unavailable_moved_exemplary': 'You cannot move an unavailable exemplary'
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


class MoveExemplariesSelectShelf(ModelView):
    'Move Exemplaries Select Shelf'
    __name__ = 'library.book.examplary.move.select_shelf'

    floor = fields.Many2One('library.floor', 'Floor', required=True)
    room = fields.Many2One('library.room', 'Room', required=True,
                           domain=[('floor', '=', Eval('floor'))], depends=['floor'])
    shelf = fields.Many2One('library.shelf', 'Shelf', required=True,
                            domain=[('room', '=', Eval('room'))], depends=['room'])
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
        return self.shelf.number_of_exemplaries + len(self.selected_exemplaries)
