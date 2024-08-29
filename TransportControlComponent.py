from _Framework.ControlSurfaceComponent import ControlSurfaceComponent
from _Framework.SubjectSlot import subject_slot
import Live

QUANTIZATION_MAP = [
    Live.Song.Quantization.q_no_q,
    Live.Song.Quantization.q_8_bars,
    Live.Song.Quantization.q_4_bars,
    Live.Song.Quantization.q_2_bars,
    Live.Song.Quantization.q_bar,
    Live.Song.Quantization.q_half,
    Live.Song.Quantization.q_quarter,
    Live.Song.Quantization.q_eight,
    Live.Song.Quantization.q_sixtenth,
    Live.Song.Quantization.q_thirtytwoth
]

class TransportControlComponent(ControlSurfaceComponent):

    def __init__(self, control_surface):
        super(TransportControlComponent, self).__init__()
        self._control_surface = control_surface
        self._song = self._control_surface.song()
        self._update_listeners()

    def set_play_button(self, button):
        self._play_button = button
        self._on_play_value.subject = button

    def set_stop_button(self, button):
        self._stop_button = button
        self._on_stop_value.subject = button

    def set_record_button(self, button):
        self._record_button = button
        self._on_record_value.subject = button

    def set_loop_button(self, button):
        self._loop_button = button
        self._on_loop_value.subject = button

    def set_metronome_button(self, button):
        self._metronome_button = button
        self._on_metronome_value.subject = button

    def set_tap_tempo_button(self, button):
        self._tap_tempo_button = button
        self._on_tap_tempo_value.subject = button

    def set_quant_toggle_button(self, button):
        self._quant_toggle_button = button
        self._on_quant_toggle_value.subject = button

    def set_undo_button(self, button):
        self._undo_button = button
        self._on_undo_value.subject = button

    def set_nudge_buttons(self, button_up, button_down):
        self._nudge_up_button = button_up
        self._nudge_down_button = button_down
        self._on_nudge_up_value.subject = button_up
        self._on_nudge_down_value.subject = button_down

    @subject_slot('value')
    def _on_play_value(self, value):
        if value:
            self._song.is_playing = not self._song.is_playing

    @subject_slot('value')
    def _on_stop_value(self, value):
        if value:
            self._song.stop_playing()

    @subject_slot('value')
    def _on_record_value(self, value):
        if value:
            self._song.record_mode = not self._song.record_mode

    @subject_slot('value')
    def _on_loop_value(self, value):
        if value:
            self._song.loop = not self._song.loop

    @subject_slot('value')
    def _on_metronome_value(self, value):
        if value:
            self._song.metronome = not self._song.metronome

    @subject_slot('value')
    def _on_tap_tempo_value(self, value):
        if value:
            self._song.tap_tempo()

    @subject_slot('value')
    def _on_quant_toggle_value(self, value):
        if value:
            current_quant = self._song.clip_trigger_quantization
            index = QUANTIZATION_MAP.index(current_quant)
            new_index = (index + 1) % len(QUANTIZATION_MAP)
            self._song.clip_trigger_quantization = QUANTIZATION_MAP[new_index]

    @subject_slot('value')
    def _on_undo_value(self, value):
        if value:
            if self._song.can_undo:
                self._song.undo()

    @subject_slot('value')
    def _on_nudge_up_value(self, value):
        if value:
            self._song.nudge_up = True
        else:
            self._song.nudge_up = False

    @subject_slot('value')
    def _on_nudge_down_value(self, value):
        if value:
            self._song.nudge_down = True
        else:
            self._song.nudge_down = False

    def update(self):
        if self.is_enabled():
            if self._play_button:
                self._play_button.set_light("Transport.PlayOn" if self._song.is_playing else "Transport.PlayOff")
            if self._stop_button:
                self._stop_button.set_light("Transport.StopOn" if not self._song.is_playing else "Transport.StopOff")
            if self._record_button:
                self._record_button.set_light("Transport.RecordOn" if self._song.record_mode else "Transport.RecordOff")
            if self._loop_button:
                self._loop_button.set_light("Transport.LoopOn" if self._song.loop else "Transport.LoopOff")
            if self._metronome_button:
                self._metronome_button.set_light("Transport.MetronomeOn" if self._song.metronome else "Transport.MetronomeOff")

    def _update_listeners(self):
        self._song.add_is_playing_listener(self.update)
        self._song.add_record_mode_listener(self.update)
        self._song.add_loop_listener(self.update)
        self._song.add_metronome_listener(self.update)