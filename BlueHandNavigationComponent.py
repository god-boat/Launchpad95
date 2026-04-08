import Live
from _Framework.ButtonElement import ButtonElement


class BlueHandNavigationComponent(object):

    def __init__(self, control_surface=None, is_enabled_callback=None,
                 is_locked_callback=None, on_device_selected=None,
                 set_device_view_callback=None):
        self._control_surface = control_surface
        self._is_enabled_callback = is_enabled_callback or (lambda: True)
        self._is_locked_callback = is_locked_callback or (lambda: False)
        self._on_device_selected = on_device_selected
        self._set_device_view_callback = set_device_view_callback
        self._prev_device_button = None
        self._next_device_button = None
        self._selected_track = None
        self._selected_device = None
        self._last_selected_device_per_track = {}
        self.song().add_appointed_device_listener(self._on_appointed_device_changed)

    def disconnect(self):
        self.set_prev_device_button(None)
        self.set_next_device_button(None)
        try:
            self.song().remove_appointed_device_listener(self._on_appointed_device_changed)
        except RuntimeError:
            pass
        self._on_device_selected = None
        self._selected_device = None
        self._control_surface = None

    def song(self):
        return self._control_surface.song()

    @property
    def selected_track(self):
        return self._selected_track

    @property
    def current_device(self):
        return self._selected_device

    def is_device_on_track(self, device_to_check, track):
        if not isinstance(device_to_check, Live.Device.Device) or not isinstance(track, Live.Track.Track):
            return False
        parent = device_to_check.canonical_parent
        while parent is not None:
            if parent == track:
                return True
            if isinstance(parent, (Live.Device.Device, Live.Chain.Chain)):
                parent = parent.canonical_parent
            else:
                break
        return False

    def get_device_track(self, device):
        if not isinstance(device, Live.Device.Device):
            return None
        for track in tuple(self.song().tracks) + tuple(self.song().return_tracks):
            if self.is_device_on_track(device, track):
                return track
        return None

    def focus_device(self, device):
        if not isinstance(device, Live.Device.Device):
            return
        device_track = self.get_device_track(device)
        if device_track is not None and self.song().view.selected_track != device_track:
            self.song().view.selected_track = device_track
        if self.song().appointed_device != device:
            self.song().view.select_device(device)
        if self._set_device_view_callback is not None:
            self._set_device_view_callback()

    def _notify_device_selected(self, device, track=None):
        if track is None:
            track = self.song().view.selected_track
        self._selected_track = track
        self._selected_device = device
        if device is not None and track is not None:
            self._last_selected_device_per_track[track] = device
        elif track in self._last_selected_device_per_track:
            del self._last_selected_device_per_track[track]
        if self._on_device_selected is not None:
            self._on_device_selected(device, track)

    def _select_device(self, device, track=None):
        if track is None:
            track = self.song().view.selected_track
        if device is not None and self.song().appointed_device != device:
            self.song().view.select_device(device)
        else:
            self._notify_device_selected(device, track)
        return device

    def _on_appointed_device_changed(self):
        if self._is_locked_callback():
            return
        current_track = self.song().view.selected_track
        device = self.song().appointed_device
        if device is not None and current_track is not None and self.is_device_on_track(device, current_track):
            self._notify_device_selected(device, current_track)
        else:
            self._selected_track = current_track
            self._selected_device = None
            if self._on_device_selected is not None:
                self._on_device_selected(None, current_track)

    def on_selected_track_changed(self):
        if self._is_locked_callback():
            return

        new_selected_track = self.song().view.selected_track
        self._selected_track = new_selected_track
        if new_selected_track is None:
            self._notify_device_selected(None, None)
            return

        restored_device = False
        stored_device = self._last_selected_device_per_track.get(new_selected_track)

        if stored_device is not None and self.is_device_on_track(stored_device, new_selected_track):
            stored_device = self.normalize_device_for_navigation(stored_device)
            if stored_device is not None:
                self._select_device(stored_device, new_selected_track)
                restored_device = True
        elif new_selected_track in self._last_selected_device_per_track:
            del self._last_selected_device_per_track[new_selected_track]

        if restored_device:
            return

        current_track_device = new_selected_track.view.selected_device
        if current_track_device is not None and self.is_device_on_track(current_track_device, new_selected_track):
            current_track_device = self.normalize_device_for_navigation(current_track_device)
            if current_track_device is not None:
                self._select_device(current_track_device, new_selected_track)
                return

        self.select_first_device(new_selected_track)

    def select_first_device(self, track=None):
        track = track if track is not None else self.song().view.selected_track
        device_to_select = None
        if track is not None and getattr(track, 'devices', None) is not None and len(track.devices) > 0:
            device_to_select = track.devices[0]
        return self._select_device(device_to_select, track)

    def is_rack_open_for_navigation(self, device):
        if not isinstance(device, Live.Device.Device):
            return False
        if not getattr(device, 'can_have_chains', False) or len(device.chains) == 0:
            return False
        if not hasattr(device, 'view'):
            return False
        if getattr(device.view, 'is_collapsed', False):
            return False
        if not getattr(device.view, 'is_showing_chain_devices', False):
            return False
        return device.view.selected_chain is not None

    def visible_device_parent(self, device):
        if self.is_rack_open_for_navigation(device):
            return device.view.selected_chain
        return None

    def collect_visible_devices(self, track_or_chain, visible_devices=None):
        if visible_devices is None:
            visible_devices = []
        devices = list(track_or_chain.devices) if track_or_chain is not None and hasattr(track_or_chain, 'devices') else []
        for child_device in devices:
            visible_devices.append(child_device)
            nested_parent = self.visible_device_parent(child_device)
            if nested_parent is not None:
                self.collect_visible_devices(nested_parent, visible_devices)
        return visible_devices

    def visible_devices(self):
        track = self.song().view.selected_track
        if track is None:
            return []
        return self.collect_visible_devices(track, [])

    def normalize_device_for_navigation(self, device, visible_devices=None):
        if not isinstance(device, Live.Device.Device):
            return None
        if visible_devices is None:
            visible_devices = self.visible_devices()
        if device in visible_devices:
            return device
        current_device = device
        while isinstance(current_device, Live.Device.Device):
            parent = current_device.canonical_parent
            if not isinstance(parent, Live.Chain.Chain):
                break
            current_device = parent.canonical_parent
            if current_device in visible_devices:
                return current_device
        return None

    def get_device_by_offset(self, device, offset):
        visible_devices = self.visible_devices()
        if len(visible_devices) == 0:
            return None
        if device is None:
            return visible_devices[0] if offset > 0 else visible_devices[-1]
        normalized_device = self.normalize_device_for_navigation(device, visible_devices)
        if normalized_device is None:
            return visible_devices[0] if offset > 0 else visible_devices[-1]
        index = visible_devices.index(normalized_device) + offset
        if index >= 0 and index < len(visible_devices):
            return visible_devices[index]
        return None

    def get_next_device(self, device):
        return self.get_device_by_offset(device, 1)

    def get_previous_device(self, device):
        return self.get_device_by_offset(device, -1)

    def update_device_buttons(self):
        if not self._is_enabled_callback():
            return

        current_device = self.current_device
        if self._prev_device_button is not None:
            self._prev_device_button.set_on_off_values("Mode.Device.On", "Mode.Device.Off")
            if current_device and self.get_previous_device(current_device):
                self._prev_device_button.turn_on()
            else:
                self._prev_device_button.turn_off()

        if self._next_device_button is not None:
            self._next_device_button.set_on_off_values("Mode.Device.On", "Mode.Device.Off")
            if current_device and self.get_next_device(current_device):
                self._next_device_button.turn_on()
            else:
                self._next_device_button.turn_off()

    def set_next_device_button(self, button):
        assert isinstance(button, (ButtonElement, type(None)))
        if self._next_device_button != button:
            if self._next_device_button is not None:
                self._next_device_button.remove_value_listener(self.handle_next_device_value)
            self._next_device_button = button
            if self._next_device_button is not None:
                self._next_device_button.add_value_listener(self.handle_next_device_value, identify_sender=True)

    def handle_next_device_value(self, value, sender):
        assert self._next_device_button is not None
        assert value in range(128)
        if self._is_enabled_callback() and ((not sender.is_momentary()) or (value != 0)):
            device = self.get_next_device(self.current_device)
            if device:
                self._select_device(device)

    def set_prev_device_button(self, button):
        assert isinstance(button, (ButtonElement, type(None)))
        if self._prev_device_button != button:
            if self._prev_device_button is not None:
                self._prev_device_button.remove_value_listener(self.handle_prev_device_value)
            self._prev_device_button = button
            if self._prev_device_button is not None:
                self._prev_device_button.add_value_listener(self.handle_prev_device_value, identify_sender=True)

    def handle_prev_device_value(self, value, sender):
        assert self._prev_device_button is not None
        assert value in range(128)
        if self._is_enabled_callback() and ((not sender.is_momentary()) or (value != 0)):
            device = self.get_previous_device(self.current_device)
            if device:
                self._select_device(device)

    def _is_usable_parameter(self, parameter, require_continuous=False):
        if parameter is None or not getattr(parameter, 'is_enabled', True):
            return False
        if require_continuous and getattr(parameter, 'is_quantized', False):
            return False
        return True

    def _is_device_on_parameter(self, parameter):
        parameter_name = str(getattr(parameter, 'name', '')).lower()
        original_name = str(getattr(parameter, 'original_name', '')).lower()
        return parameter_name in ('device on', 'on') or original_name == 'device on'

    def get_target_parameters(self, count=2, skip_device_on_parameter=True, require_continuous=False):
        device = self.current_device
        result = []
        if isinstance(device, Live.Device.Device):
            parameters = list(getattr(device, 'parameters', []))
            if skip_device_on_parameter and parameters and self._is_device_on_parameter(parameters[0]):
                parameters = parameters[1:]
            for parameter in parameters:
                if self._is_usable_parameter(parameter, require_continuous):
                    result.append(parameter)
                if len(result) >= count:
                    break
        while len(result) < count:
            result.append(None)
        return tuple(result)