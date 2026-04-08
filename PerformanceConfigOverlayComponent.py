from _Framework.ButtonMatrixElement import ButtonMatrixElement


FULL_PADS_LAYOUT = 'full_pads'
STACKED_XY_PADS_LAYOUT = 'stacked_xy_pads'
VALID_PERFORMANCE_LAYOUTS = (FULL_PADS_LAYOUT, STACKED_XY_PADS_LAYOUT)


class PerformanceConfigOverlayComponent(object):

    _LAYOUT_BUTTONS = {
        FULL_PADS_LAYOUT: (0, 0),
        STACKED_XY_PADS_LAYOUT: (1, 0)
    }

    _LAYOUT_COLORS = {
        FULL_PADS_LAYOUT: ('PerformanceOverlay.FullPads.On', 'PerformanceOverlay.FullPads.Off'),
        STACKED_XY_PADS_LAYOUT: ('PerformanceOverlay.StackedXYPads.On', 'PerformanceOverlay.StackedXYPads.Off')
    }

    def __init__(self, matrix, control_surface=None, on_layout_selected=None):
        assert isinstance(matrix, ButtonMatrixElement)
        self._matrix = None
        self._control_surface = control_surface
        self._on_layout_selected = on_layout_selected
        self._enabled = False
        self._selected_layout_id = FULL_PADS_LAYOUT
        self.set_matrix(matrix)

    def disconnect(self):
        self.set_matrix(None)
        self._on_layout_selected = None
        self._control_surface = None

    def set_matrix(self, matrix):
        assert isinstance(matrix, (ButtonMatrixElement, type(None)))
        old_matrix = self._matrix
        if old_matrix is not None and old_matrix != matrix:
            old_matrix.remove_value_listener(self._matrix_value)

        self._matrix = matrix
        if self._matrix is not None and old_matrix != matrix:
            self._matrix.add_value_listener(self._matrix_value)

        if self._enabled:
            self.update()

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if self._enabled:
            self.update()

    def is_enabled(self):
        return self._enabled

    def set_selected_layout(self, layout_id):
        if layout_id not in VALID_PERFORMANCE_LAYOUTS:
            return

        self._selected_layout_id = layout_id
        if self._enabled:
            self.update()

    def update(self):
        if not self._enabled or self._matrix is None:
            return

        for button, (x, y) in self._matrix.iterbuttons():
            if button is None:
                continue

            button.use_default_message()
            button.set_enabled(True)
            button.set_on_off_values('DefaultButton.Disabled', 'DefaultButton.Disabled')
            button.turn_off()

            for layout_id, coordinates in self._LAYOUT_BUTTONS.items():
                if coordinates == (x, y):
                    on_value, off_value = self._LAYOUT_COLORS[layout_id]
                    button.set_on_off_values(on_value, off_value)
                    if layout_id == self._selected_layout_id:
                        button.turn_on()
                    else:
                        button.turn_off()
                    break

    def _matrix_value(self, value, x, y, is_momentary):
        if not self._enabled:
            return

        if value == 0 and is_momentary:
            return

        for layout_id, coordinates in self._LAYOUT_BUTTONS.items():
            if coordinates == (x, y):
                self._selected_layout_id = layout_id
                if self._on_layout_selected is not None:
                    self._on_layout_selected(layout_id)
                break