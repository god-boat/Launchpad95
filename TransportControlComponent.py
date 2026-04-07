from _Framework.ControlSurfaceComponent import ControlSurfaceComponent
from _Framework.SubjectSlot import subject_slot
import Live
from Live.Base import Timer

TEMPO_REPEAT_DELAY = 500  # ms
TEMPO_REPEAT_INTERVAL = 50 # ms

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
        self._tempo_up_timer = None
        self._tempo_down_timer = None
        self._update_listeners()

    def disconnect(self):
        if self._tempo_up_timer is not None:
            self._tempo_up_timer.stop()
            self._tempo_up_timer = None
        if self._tempo_down_timer is not None:
            self._tempo_down_timer.stop()
            self._tempo_down_timer = None
        super(TransportControlComponent, self).disconnect()

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

    def set_tempo_buttons(self, button_up, button_down):
        self._tempo_up_button = button_up
        self._tempo_down_button = button_down
        self._on_tempo_up_value.subject = button_up
        self._on_tempo_down_value.subject = button_down

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

    @subject_slot('value')
    def _on_tempo_up_value(self, value):
        if value:
            self._on_tempo_up_pressed()
        else:
            self._on_tempo_up_released()

    @subject_slot('value')
    def _on_tempo_down_value(self, value):
        if value:
            self._on_tempo_down_pressed()
        else:
            self._on_tempo_down_released()

    def _on_tempo_up_pressed(self):
        self._change_tempo(1.0)
        if self._tempo_up_timer is not None:
            self._tempo_up_timer.stop()
        self._tempo_up_timer = Timer(callback=self._repeat_tempo_up, interval=TEMPO_REPEAT_DELAY, start=True)

    def _on_tempo_down_pressed(self):
        self._change_tempo(-1.0)
        if self._tempo_down_timer is not None:
            self._tempo_down_timer.stop()
        self._tempo_down_timer = Timer(callback=self._repeat_tempo_down, interval=TEMPO_REPEAT_DELAY, start=True)

    def _on_tempo_up_released(self):
        if self._tempo_up_timer is not None:
            self._tempo_up_timer.stop()
            self._tempo_up_timer = None

    def _on_tempo_down_released(self):
        if self._tempo_down_timer is not None:
            self._tempo_down_timer.stop()
            self._tempo_down_timer = None

    def _repeat_tempo_up(self):
        # Called by the timer after the initial delay and subsequent intervals
        self._control_surface.log_message("_repeat_tempo_up: Called.")
        self._change_tempo(1.0)
        # Re-trigger timer by creating a NEW timer with the shorter interval
        if self._tempo_up_timer:
            self._tempo_up_timer.stop() # Stop the old timer
            # Create and start a new timer with the faster interval
            self._tempo_up_timer = Timer(callback=self._repeat_tempo_up, interval=TEMPO_REPEAT_INTERVAL, start=True)
            self._control_surface.log_message(f"_repeat_tempo_up: Restarted timer with interval {TEMPO_REPEAT_INTERVAL}")
        else:
            self._control_surface.log_message("_repeat_tempo_up: Error - Timer was None!")

    def _repeat_tempo_down(self):
        # Called by the timer after the initial delay and subsequent intervals
        self._control_surface.log_message("_repeat_tempo_down: Called.")
        self._change_tempo(-1.0)
        # Re-trigger timer by creating a NEW timer with the shorter interval
        if self._tempo_down_timer:
            self._tempo_down_timer.stop() # Stop the old timer
            # Create and start a new timer with the faster interval
            self._tempo_down_timer = Timer(callback=self._repeat_tempo_down, interval=TEMPO_REPEAT_INTERVAL, start=True)
            self._control_surface.log_message(f"_repeat_tempo_down: Restarted timer with interval {TEMPO_REPEAT_INTERVAL}")
        else:
            self._control_surface.log_message("_repeat_tempo_down: Error - Timer was None!")

    def _change_tempo(self, delta):
        current_tempo = self._song.tempo
        new_tempo = max(20.0, min(999.0, current_tempo + delta))
        self._song.tempo = new_tempo

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