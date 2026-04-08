from _Framework.ButtonMatrixElement import ButtonMatrixElement

from .ColorsMK2 import RGB_COLOR_TABLE


_RGB_VALUES_BY_MIDI = dict(RGB_COLOR_TABLE)
_PALETTE_RGB = tuple(
    (midi_value,
     ((rgb_value >> 16) & 255, (rgb_value >> 8) & 255, rgb_value & 255))
    for midi_value, rgb_value in RGB_COLOR_TABLE if midi_value != 0)


class XYPadSectionComponent(object):

    def __init__(self, matrix, navigation_provider=None, track_color_provider=None):
        assert isinstance(matrix, (ButtonMatrixElement, type(None)))

        self._matrix = None
        self._navigation_provider = navigation_provider
        self._track_color_provider = track_color_provider
        self._enabled = False
        self._selected_x = 0
        self._selected_y = 0
        self.set_matrix(matrix)

    def disconnect(self):
        self.set_enabled(False)
        self.set_matrix(None)
        self._navigation_provider = None
        self._track_color_provider = None

    def is_enabled(self):
        return self._enabled

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if self._enabled:
            self.update()

    def set_navigation_provider(self, navigation_provider):
        self._navigation_provider = navigation_provider
        if self._enabled:
            self.update()

    def set_track_color_provider(self, track_color_provider):
        self._track_color_provider = track_color_provider
        if self._enabled:
            self.update()

    def set_matrix(self, matrix):
        assert isinstance(matrix, (ButtonMatrixElement, type(None)))

        old_matrix = self._matrix
        if old_matrix is not None and old_matrix != matrix:
            old_matrix.remove_value_listener(self._matrix_value)

        self._matrix = matrix
        if self._matrix is not None and old_matrix != matrix:
            self._matrix.add_value_listener(self._matrix_value)
            if old_matrix is None:
                self._selected_y = max(0, self._matrix.height() - 1)
            self._selected_x = min(self._selected_x, max(0, self._matrix.width() - 1))
            self._selected_y = min(self._selected_y, max(0, self._matrix.height() - 1))

        if self._enabled:
            self.update()

    def update(self):
        if not self._enabled or self._matrix is None:
            return

        target_parameters = self._target_parameters()
        self._sync_selected_coordinates(target_parameters)
        has_target_parameter = target_parameters[0] is not None or target_parameters[1] is not None
        handle_color_value = self._track_color_value()
        halo_color_value = self._halo_color_value(handle_color_value)

        for button, (x, y) in self._matrix.iterbuttons():
            if button is None:
                continue

            button.use_default_message()
            button.set_enabled(True)

            if not has_target_parameter:
                button.set_light('DefaultButton.Disabled')
            elif x == self._selected_x and y == self._selected_y:
                if handle_color_value is not None:
                    button.send_value(handle_color_value)
                else:
                    button.set_light('PerformanceOverlay.StackedXYPads.On')
            elif self._is_halo_button(x, y):
                if halo_color_value is not None:
                    button.send_value(halo_color_value)
                else:
                    button.set_light('PerformanceOverlay.StackedXYPads.Off')
            else:
                button.set_light('DefaultButton.Disabled')

    def _matrix_value(self, value, x, y, is_momentary):
        if not self._enabled:
            return

        if value == 0 and is_momentary:
            return

        self._selected_x = x
        self._selected_y = y
        self._apply_selected_coordinates()
        self.update()

    def _target_parameters(self):
        if self._navigation_provider is None:
            return (None, None)

        return self._navigation_provider.get_target_parameters(
            count=2,
            skip_device_on_parameter=True,
            require_continuous=False)

    def _sync_selected_coordinates(self, target_parameters):
        if self._matrix is None:
            return

        x_parameter, y_parameter = target_parameters
        max_x = max(0, self._matrix.width() - 1)
        max_y = max(0, self._matrix.height() - 1)

        if x_parameter is not None:
            self._selected_x = self._coordinate_for_parameter(x_parameter, max_x)
        else:
            self._selected_x = min(max(self._selected_x, 0), max_x)

        if y_parameter is not None:
            self._selected_y = self._coordinate_for_parameter(y_parameter, max_y, invert=True)
        else:
            self._selected_y = min(max(self._selected_y, 0), max_y)

    def _coordinate_for_parameter(self, parameter, max_index, invert=False):
        if parameter is None or max_index <= 0:
            return max_index if invert and max_index > 0 else 0

        parameter_range = float(parameter.max - parameter.min)
        normalized = 0.0
        if parameter_range > 0:
            normalized = float(parameter.value - parameter.min) / parameter_range
        normalized = max(0.0, min(1.0, normalized))

        if invert:
            normalized = 1.0 - normalized

        return int(round(normalized * max_index))

    def _apply_selected_coordinates(self):
        if self._matrix is None:
            return

        x_parameter, y_parameter = self._target_parameters()
        self._apply_coordinate_to_parameter(
            x_parameter,
            self._selected_x,
            max(0, self._matrix.width() - 1))
        self._apply_coordinate_to_parameter(
            y_parameter,
            self._selected_y,
            max(0, self._matrix.height() - 1),
            invert=True)

    def _apply_coordinate_to_parameter(self, parameter, coordinate, max_index, invert=False):
        if parameter is None:
            return

        normalized = 0.0
        if max_index > 0:
            normalized = float(coordinate) / max_index
        normalized = max(0.0, min(1.0, normalized))

        if invert:
            normalized = 1.0 - normalized

        target_value = parameter.min + (parameter.max - parameter.min) * normalized
        if getattr(parameter, 'is_quantized', False):
            target_value = int(round(target_value))

        target_value = max(parameter.min, min(parameter.max, target_value))
        try:
            parameter.value = target_value
        except RuntimeError:
            pass

    def _track_color_value(self):
        if self._track_color_provider is None:
            return None

        try:
            return self._track_color_provider()
        except RuntimeError:
            return None

    def _halo_color_value(self, color_value):
        if color_value is None:
            return None

        for factor in (0.45, 0.28):
            candidate = self._scaled_palette_color_value(color_value, factor)
            if candidate is not None and candidate != color_value:
                return candidate
        return None

    def _scaled_palette_color_value(self, color_value, factor):
        rgb_value = _RGB_VALUES_BY_MIDI.get(color_value)
        if rgb_value is None:
            return None

        scaled_rgb = (
            int(((rgb_value >> 16) & 255) * factor),
            int(((rgb_value >> 8) & 255) * factor),
            int((rgb_value & 255) * factor))

        best_match = min(
            _PALETTE_RGB,
            key=lambda palette_entry: self._color_distance(palette_entry[1], scaled_rgb))
        return best_match[0]

    def _color_distance(self, color_a, color_b):
        red_delta = color_a[0] - color_b[0]
        green_delta = color_a[1] - color_b[1]
        blue_delta = color_a[2] - color_b[2]
        return (red_delta * red_delta + green_delta * green_delta + blue_delta * blue_delta) ** 0.5

    def _is_halo_button(self, x, y):
        return abs(x - self._selected_x) + abs(y - self._selected_y) == 1