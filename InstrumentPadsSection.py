from _Framework.ButtonMatrixElement import ButtonMatrixElement


class InstrumentPadsSection(object):

    def __init__(self, instrument_controller, matrix, full_matrix=None,
                 physical_row_offset=0, physical_grid_height=None):
        assert instrument_controller is not None
        assert isinstance(matrix, ButtonMatrixElement)
        assert isinstance(full_matrix, (ButtonMatrixElement, type(None)))

        self._instrument_controller = instrument_controller
        self._matrix = matrix
        self._full_matrix = full_matrix if full_matrix is not None else matrix
        self._physical_row_offset = max(0, physical_row_offset)
        self._physical_grid_height = max(
            1,
            physical_grid_height if physical_grid_height is not None else self._full_matrix.height())
        self._enabled = False

    @property
    def track_controller(self):
        return getattr(self._instrument_controller, '_track_controller', None)

    @property
    def scales(self):
        return getattr(self._instrument_controller, '_scales', None)

    @property
    def scales_toggle_button(self):
        return getattr(self._instrument_controller, '_scales_toggle_button', None)

    def disconnect(self):
        self.set_enabled(False)
        self._instrument_controller = None
        self._matrix = None
        self._full_matrix = None

    def set_osd(self, osd):
        if self._instrument_controller is not None:
            self._instrument_controller.set_osd(osd)

    def is_enabled(self):
        return self._enabled

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if self._instrument_controller is None:
            return

        if self._enabled:
            self._prepare_controller()
            self._instrument_controller.set_enabled(True)
        else:
            self._instrument_controller.set_enabled(False)

    def set_matrix(self, matrix, full_matrix=None):
        assert isinstance(matrix, ButtonMatrixElement)
        assert isinstance(full_matrix, (ButtonMatrixElement, type(None)))

        self._matrix = matrix
        if full_matrix is not None:
            self._full_matrix = full_matrix

        if self._enabled:
            self.update()

    def set_physical_note_layout(self, row_offset=0, total_rows=None):
        self._physical_row_offset = max(0, row_offset)
        if total_rows is None:
            total_rows = self._full_matrix.height()
        self._physical_grid_height = max(1, total_rows)

        if self._enabled and self._instrument_controller is not None:
            self._instrument_controller.set_physical_note_layout(
                self._physical_row_offset,
                self._physical_grid_height)

    def close_overlays(self):
        if self._instrument_controller is None:
            return

        scales = self.scales
        if scales is None or not scales.is_enabled():
            return

        if self._instrument_controller.is_enabled():
            self._instrument_controller._scales_toggle(0, self.scales_toggle_button)
        else:
            scales.set_enabled(False)

    def update(self):
        if not self._enabled or self._instrument_controller is None:
            return

        self._prepare_controller()
        self._instrument_controller.update()

    def _prepare_controller(self):
        if getattr(self._instrument_controller, '_matrix', None) != self._matrix:
            self._instrument_controller.set_matrix(self._matrix)
        self._instrument_controller.set_physical_note_layout(
            self._physical_row_offset,
            self._physical_grid_height)