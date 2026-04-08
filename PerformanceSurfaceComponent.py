from _Framework.ButtonMatrixElement import ButtonMatrixElement

from .BlueHandNavigationComponent import BlueHandNavigationComponent
from .InstrumentPadsSection import InstrumentPadsSection
from .PerformanceConfigOverlayComponent import (
    FULL_PADS_LAYOUT,
    STACKED_XY_PADS_LAYOUT,
    VALID_PERFORMANCE_LAYOUTS,
    PerformanceConfigOverlayComponent,
)


class PerformanceSurfaceComponent(object):

    def __init__(self, matrix, side_buttons, top_buttons, control_surface,
                 instrument_controller):
        assert isinstance(matrix, ButtonMatrixElement)
        assert isinstance(side_buttons, tuple)
        assert isinstance(top_buttons, tuple)

        self._matrix = matrix
        self._side_buttons = side_buttons
        self._top_buttons = top_buttons
        self._control_surface = control_surface
        self._instrument_controller = instrument_controller
        self._pads_section = InstrumentPadsSection(
            instrument_controller=instrument_controller,
            matrix=self._matrix,
            full_matrix=self._matrix,
            physical_row_offset=0,
            physical_grid_height=self._matrix.height())
        self._osd = None
        self._enabled = False
        self._config_mode = False
        self._layout_id = FULL_PADS_LAYOUT
        self._active_navigation_layout = None
        self._overlay_interaction = False
        self._top_matrix = ButtonMatrixElement(rows=[
            [self._matrix.get_button(x, y) for x in range(self._matrix.width())]
            for y in range(4)
        ])
        self._bottom_matrix = ButtonMatrixElement(rows=[
            [self._matrix.get_button(x, y) for x in range(self._matrix.width())]
            for y in range(4, self._matrix.height())
        ])
        self._overlay = PerformanceConfigOverlayComponent(
            matrix=self._matrix,
            control_surface=self._control_surface,
            on_layout_selected=self._on_layout_selected)
        self._blue_hand_navigation = BlueHandNavigationComponent(
            control_surface=self._control_surface,
            is_enabled_callback=self._blue_hand_navigation_is_enabled,
            is_locked_callback=lambda: False,
            on_device_selected=self._on_device_selected,
            set_device_view_callback=self._show_device_view_if_allowed)

        try:
            self.song().view.add_selected_track_listener(self._on_selected_track_changed)
        except RuntimeError:
            pass

    def disconnect(self):
        try:
            self.song().view.remove_selected_track_listener(self._on_selected_track_changed)
        except RuntimeError:
            pass

        self._overlay.disconnect()
        self._blue_hand_navigation.disconnect()
        self._pads_section.disconnect()
        self._instrument_controller = None
        self._pads_section = None
        self._control_surface = None
        self._osd = None

    def song(self):
        return self._control_surface.song()

    def set_osd(self, osd):
        self._osd = osd
        if self._pads_section is not None:
            self._pads_section.set_osd(osd)

    @property
    def layout_id(self):
        return self._layout_id

    def is_enabled(self):
        return self._enabled

    def is_config_overlay_active(self):
        return self._config_mode

    def consume_overlay_interaction(self):
        interaction = self._overlay_interaction
        self._overlay_interaction = False
        return interaction

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if self._enabled:
            self.update()
        else:
            self._disable_surface()

    def set_layout(self, layout_id):
        self._set_layout(layout_id, close_overlay=True)

    def _set_layout(self, layout_id, close_overlay):
        if layout_id not in VALID_PERFORMANCE_LAYOUTS:
            return

        if layout_id == STACKED_XY_PADS_LAYOUT:
            self._control_surface.show_message('STACKED XY + PADS NOT IMPLEMENTED YET')
            layout_id = FULL_PADS_LAYOUT

        layout_changed = self._layout_id != layout_id
        self._layout_id = layout_id
        self._overlay.set_selected_layout(layout_id)
        if close_overlay:
            self._config_mode = False

        if layout_changed:
            if layout_id == FULL_PADS_LAYOUT:
                self._control_surface.show_message('PERFORMANCE LAYOUT: FULL PADS')
            else:
                self._control_surface.show_message('PERFORMANCE LAYOUT: STACKED XY + PADS')

        if self._enabled and layout_id == STACKED_XY_PADS_LAYOUT:
            self._blue_hand_navigation.on_selected_track_changed()

        if self._enabled:
            self.update()

    def open_config_overlay(self):
        if not self._enabled:
            return

        self._close_instrument_overlays()
        self._overlay_interaction = False
        self._config_mode = True
        self._control_surface.show_message('PERFORMANCE CONFIG')
        self.update()

    def close_config_overlay(self):
        if not self._config_mode:
            return

        self._config_mode = False
        if self._enabled:
            self.update()

    def update(self):
        if not self._enabled or self._pads_section is None:
            return

        if self._config_mode:
            self._update_config_overlay()
        else:
            self._update_active_layout()

    def _disable_surface(self):
        if self._pads_section is None:
            return

        self._config_mode = False
        self._overlay_interaction = False
        self._overlay.set_enabled(False)
        self._close_instrument_overlays()
        self._clear_navigation_assignments()
        self._pads_section.set_enabled(False)

    def _update_config_overlay(self):
        self._restore_matrix_messages()
        self._pads_section.set_enabled(False)
        self._overlay.set_selected_layout(self._layout_id)
        self._overlay.set_enabled(True)
        self._update_overlay_osd()

    def _update_active_layout(self):
        self._overlay.set_enabled(False)
        self._pads_section.set_matrix(self._matrix, full_matrix=self._matrix)
        self._pads_section.set_physical_note_layout(0, self._matrix.height())
        self._apply_navigation_layout()
        if not self._pads_section.is_enabled():
            self._pads_section.set_enabled(True)
        else:
            self._pads_section.update()

        track_controller = self._pads_section.track_controller
        if track_controller is not None:
            track_controller.update()

        if self._layout_id == STACKED_XY_PADS_LAYOUT:
            self._blue_hand_navigation.update_device_buttons()

        self._update_layout_osd()

    def _apply_navigation_layout(self):
        track_controller = self._pads_section.track_controller
        if track_controller is None:
            return

        if self._layout_id == STACKED_XY_PADS_LAYOUT:
            if self._active_navigation_layout != STACKED_XY_PADS_LAYOUT:
                track_controller.set_prev_scene_button(None)
                track_controller.set_next_scene_button(None)
                track_controller.set_prev_track_button(self._top_buttons[2])
                track_controller.set_next_track_button(self._top_buttons[3])
                self._blue_hand_navigation.set_prev_device_button(self._top_buttons[0])
                self._blue_hand_navigation.set_next_device_button(self._top_buttons[1])
                self._active_navigation_layout = STACKED_XY_PADS_LAYOUT
        else:
            if self._active_navigation_layout != FULL_PADS_LAYOUT:
                track_controller.set_prev_scene_button(self._top_buttons[0])
                track_controller.set_next_scene_button(self._top_buttons[1])
                track_controller.set_prev_track_button(self._top_buttons[2])
                track_controller.set_next_track_button(self._top_buttons[3])
                self._blue_hand_navigation.set_prev_device_button(None)
                self._blue_hand_navigation.set_next_device_button(None)
                self._active_navigation_layout = FULL_PADS_LAYOUT

    def _clear_navigation_assignments(self):
        track_controller = getattr(self._instrument_controller, '_track_controller', None)
        if track_controller is not None:
            track_controller.set_prev_scene_button(None)
            track_controller.set_next_scene_button(None)
            track_controller.set_prev_track_button(None)
            track_controller.set_next_track_button(None)

        self._blue_hand_navigation.set_prev_device_button(None)
        self._blue_hand_navigation.set_next_device_button(None)
        self._active_navigation_layout = None

    def _restore_matrix_messages(self):
        for button, _ in self._matrix.iterbuttons():
            if button is not None:
                button.use_default_message()
                button.force_next_send()

    def _close_instrument_overlays(self):
        self._pads_section.close_overlays()

    def _update_overlay_osd(self):
        if self._osd is None:
            return

        self._osd.clear()
        self._osd.mode = 'Performance Config'
        self._osd.info[0] = 'pad 1 : full pads'
        self._osd.info[1] = 'pad 2 : stacked XY + pads'
        self._osd.update()

    def _update_layout_osd(self):
        if self._osd is None:
            return

        self._osd.mode = 'Performance'
        if self._layout_id == FULL_PADS_LAYOUT:
            self._osd.info[1] = 'layout : full pads'
        else:
            self._osd.info[1] = 'layout : stacked XY + pads'
        self._osd.update()

    def _blue_hand_navigation_is_enabled(self):
        return self._enabled and not self._config_mode and self._layout_id == STACKED_XY_PADS_LAYOUT

    def _show_device_view_if_allowed(self):
        if self._control_surface is None:
            return

        view = self._control_surface.application().view
        if not view.is_view_visible('Detail') or not view.is_view_visible('Detail/DeviceChain'):
            view.show_view('Detail')
            view.show_view('Detail/DeviceChain')

    def _on_layout_selected(self, layout_id):
        self._overlay_interaction = True
        self._set_layout(layout_id, close_overlay=False)

    def _on_selected_track_changed(self):
        if self._blue_hand_navigation_is_enabled():
            self._blue_hand_navigation.on_selected_track_changed()
            self._blue_hand_navigation.update_device_buttons()

    def _on_device_selected(self, device, track):
        if self._blue_hand_navigation_is_enabled():
            self._blue_hand_navigation.update_device_buttons()