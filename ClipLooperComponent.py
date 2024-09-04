from __future__ import absolute_import, print_function, unicode_literals
from _Framework.CompoundComponent import CompoundComponent
from _Framework.ButtonMatrixElement import ButtonMatrixElement
from _Framework.SubjectSlot import subject_slot, SlotManager
from _Framework.SessionComponent import SessionComponent
from ableton.v2.base import liveobj_valid
from .ColorsMK2 import CLIP_COLOR_TABLE, RGB_COLOR_TABLE
import Live
import time

ABLETON_TO_LAUNCHPAD_COLORS = {
    0: 72,  # Fight the Sunrise (Light Pink)
    1: 96,  # Hawaiian Passion (Light Orange)
    2: 100, # Gomashio Yellow (Light Yellow)
    3: 98,  # Golden Staff (Yellow)
    4: 122, # Grass Stain Green (Lighter Green)
    5: 21,  # Bright Light Green (Green)
    6: 37,  # Eva Green (Cyan)
    7: 45,  # Icy Life (Turquoise)
    8: 105, # Platonic Blue (Blue)
    9: 105, # Blue Jay (Blue)
    10: 113, # Widowmaker (Light Blue)
    11: 95,  # Hibiscus Pop (Bright Pink)
    12: 95,  # Bit of Berry (Bright Pink)
    13: 3,   # White (White)
    14: 5,   # Coral Red (Red)
    15: 84,  # Apocalyptic Orange (Orange)
    16: 11,  # Chocolate Milk (Dark Amber)
    17: 13,  # Rape Blossoms (Yellow)
    18: 76,  # Easter Green (Green)
    19: 21,  # Harlequin Green (Green)
    20: 37,  # Tealish (Cyan)
    21: 45,  # Sparky Blue (Turquoise)
    22: 105, # Button Blue (Blue)
    23: 47,  # Tall Ships (Dark Cyan)
    24: 115, # Matt Purple (Purple)
    25: 116, # Wisteria (Dark Purple)
    26: 95,  # Mat Dazzle Rose (Bright Pink)
    27: 118, # Ancestral Water (Light Gray)
    28: 106, # Salami Slice (Light Pink)
    29: 97,  # Butternut (Amber)
    30: 99,  # Glittering Sun (Turquoise)
    31: 121, # Hawthorn Blossom (Lighter Yellow)
    32: 123, # Apple Bob (Lighter Mint)
    33: 123, # Greenish Tan (Lighter Mint)
    34: 123, # Olive Sand (Lighter Mint)
    35: 49,  # Cactus Water (Seafoam Green)
    36: 49,  # Frostproof (Seafoam Green)
    37: 113, # California Lilac (Light Blue)
    38: 116, # Drifting Dream (Dark Purple)
    39: 116, # Dull Lavender (Dark Purple)
    40: 119, # Violet Vapor (White)
    41: 2,   # Ultimate Gray (Gray)
    42: 107, # Pressed Blossoms (Red)
    43: 11,  # Choco Biscuit (Dark Amber)
    44: 11,  # Broccoli Brown (Dark Amber)
    45: 99,  # Golden Cartridge (Turquoise)
    46: 76,  # Pea (Green)
    47: 76,  # Kiwi (Green)
    48: 45,  # Undine (Turquoise)
    49: 49,  # Perfect Landing (Seafoam Green)
    50: 104, # Windy City (Purple)
    51: 104, # Grapemist (Purple)
    52: 116, # Glossy Grape (Dark Purple)
    53: 116, # Lupine (Dark Purple)
    54: 106, # Benifuji (Light Pink)
    55: 1,   # Namara Grey (Gray)
    56: 7,   # Red Ink (Dark Red)
    57: 11,  # Orange Roughy (Dark Amber)
    58: 83,  # Coffee Shop (Dark Orange)
    59: 100, # Indian Pale Ale (Light Yellow)
    60: 28,  # Airline Green (Dark Green)
    61: 28,  # Hubert's Truck Green (Dark Green)
    62: 45,  # Flamboyant (Turquoise)
    63: 47,  # Georgian Bay (Dark Cyan)
    64: 53,  # North Star Blue (Dark Blue)
    65: 53,  # Blue Bonnet (Dark Blue)
    66: 115, # Swiss Plum (Purple)
    67: 115, # Purpureus (Purple)
    68: 71,  # Beetroot Purple (Bright Pink)
    69: 0    # Shisha Coal (Black)
}

QUANTIZATION_STEPS = [1, 0.5, 0.25, 0.125]  # 1 bar, 1/2, 1/4, 1/8

class ClipLooperComponent(CompoundComponent, SlotManager):
    def __init__(self, session_component, *a, **k):

        print("ClipLooper: Initializing ClipLooperComponent")
        super(ClipLooperComponent, self).__init__(*a, **k)
        self._session_component = session_component
        self._clip_slots = []
        self._matrix = None
        self._side_buttons = None
        self._nav_buttons = None
        self._update_timer = Live.Base.Timer(callback=self._on_timer, interval=100)
        self._quantization_index = 0  # Default to 1 bar
        self._selected_clip_index = -1
        self._is_setting_loop = False
        self._loop_start = None
        self._loop_length = 8  # Default loop length in beats
        self._playhead_position = []
        self._loop_start = []
        self._loop_end = []
        self._is_enabled = False

        self._on_selected_track_changed.subject = self.song().view
        self._on_selected_scene_changed.subject = self.song().view

        print("ClipLooper: ClipLooperComponent initialization complete")

    def set_matrix(self, matrix):
        self._matrix = matrix
        self._on_matrix_value.subject = matrix if matrix else None
        self._update_display()

    def set_side_buttons(self, buttons):
        self._side_buttons = buttons or []
        for button in self._side_buttons:
            button.add_value_listener(self._on_side_button_value, identify_sender=True)
        self._update_side_buttons()

    def set_nav_buttons(self, buttons):
        if self._nav_buttons:
            for button in self._nav_buttons:
                self.disconnect_nav_button(button)
        self._nav_buttons = buttons
        if buttons:
            for button in buttons:
                button.add_value_listener(self._on_nav_button_value, identify_sender=True)
        self._update_nav_buttons()

    def connect_button(self, button):
        button.add_value_listener(self._on_side_button_value)

    def disconnect_button(self, button):
        button.remove_value_listener(self._on_side_button_value)

    def connect_nav_button(self, button):
        button.add_value_listener(self._on_nav_button_value)

    def disconnect_nav_button(self, button):
        button.remove_value_listener(self._on_nav_button_value)

    @subject_slot('value')
    def _on_matrix_value(self, value, x, y, is_momentary):
        if self._matrix and value is not None:  # Handle both button press and release
            clip_index = y // 2
            if clip_index < len(self._clip_slots):
                clip_slot = self._clip_slots[clip_index]
                if clip_slot is not None and clip_slot.has_clip:
                    clip = clip_slot.clip
                    if y % 2 == 0:  # Playhead row
                        if value == 127:  # Only set position on button press
                            self._set_clip_position(clip, x)
                    else:  # Control row
                        if x == 0:  # Loop set button
                            self._set_loop_points(clip, value == 127)  # Handle both press and release
                        elif value == 127:  # Only handle press for other control buttons
                            self._handle_control_press(clip, x)
                else:
                    self.log_message(f"No valid clip at index {clip_index}")
            else:
                self.log_message(f"Clip index {clip_index} out of range")

        self._update_display()

    def _on_side_button_value(self, value, sender):
        if not self._is_enabled:
            print("ClipLooper: Component is not enabled, ignoring side button value")
            return
        if value and self._side_buttons:  # Only handle button presses
            try:
                index = list(self._side_buttons).index(sender)
                self._handle_side_button_press(index)
            except ValueError:
                self.log_message(f"Sender {sender} not found in side buttons")

    def _on_nav_button_value(self, value, sender):
        if value and self._nav_buttons:  # Only handle button presses
            index = list(self._nav_buttons).index(sender)
            self._handle_nav_button_press(index)

    def _set_clip_position(self, clip, x):
        if not liveobj_valid(clip):
            return

        song = self.song()
        quantization_value = song.clip_trigger_quantization
        
        def quantize_beat(beat):
            quant_grid = {
                Live.Song.Quantization.q_8_bars: 32.0,
                Live.Song.Quantization.q_4_bars: 16.0,
                Live.Song.Quantization.q_2_bars: 8.0,
                Live.Song.Quantization.q_bar: 4.0,
                Live.Song.Quantization.q_half: 2.0,
                Live.Song.Quantization.q_quarter: 1.0,
                Live.Song.Quantization.q_eight: 0.5,
                Live.Song.Quantization.q_sixtenth: 0.25,
                Live.Song.Quantization.q_thirtytwoth: 0.125
            }
            grid = quant_grid.get(quantization_value, 1.0)
            return round(beat / grid) * grid

        original_start = clip.start_marker
        original_end = clip.end_marker
        original_length = original_end - original_start
        current_loop_length = clip.loop_end - clip.loop_start

        print(f"Before any changes: start_marker={original_start}, end_marker={original_end}, length={original_length}")
        print(f"Current loop: start={clip.loop_start}, end={clip.loop_end}, length={current_loop_length}")
        print(f"Button pressed: x={x}")
        print(f"Current quantization: {quantization_value}")

        # Calculate the new loop start and end
        new_loop_start = (x / 7.0) * original_length
        new_loop_start_quantized = quantize_beat(new_loop_start)
        new_loop_end = min(new_loop_start_quantized + current_loop_length, original_length)

        print(f"Calculated new loop: start={new_loop_start}, quantized_start={new_loop_start_quantized}, end={new_loop_end}")

        try:
            # Set both loop points at once to avoid conflicts
            clip.loop = (new_loop_start_quantized, new_loop_end)
            clip.position = new_loop_start_quantized  # Move playhead to start of new loop position
            print(f"Set new loop: start={clip.loop_start}, end={clip.loop_end}, position={clip.position}")
        except Exception as e:
            print(f"Error setting loop position: {str(e)}")

        # Restore original start and end markers if they've changed
        if clip.start_marker != original_start or clip.end_marker != original_end:
            clip.start_marker = original_start
            clip.end_marker = original_end
            print(f"Restored original markers: start={original_start}, end={original_end}")

        # Print final state
        print(f"Final state: start_marker={clip.start_marker}, end_marker={clip.end_marker}")
        print(f"Final state: loop_start={clip.loop_start}, loop_end={clip.loop_end}")
        print(f"Final state: clip position={clip.position}")
        if clip.is_audio_clip:
            print(f"Audio clip: warping={clip.warping}, warp_mode={clip.warp_mode}")
        print("---")
        self._focus_on_clip(clip)  # Focus on the clip after any manipulation

    def _handle_control_press(self, clip, x):
        if x == 1:  # Move loop left
            self._move_loop(clip, -1)
        elif x == 2:  # Move loop right
            self._move_loop(clip, 1)
        elif x == 4:  # Double loop length
            self._double_loop_length(clip)
        elif x == 3:  # Halve loop length
            self._halve_loop_length(clip)
        self._focus_on_clip(clip)  # Focus on the clip after any manipulation

    def _halve_loop_length(self, clip):
        if not liveobj_valid(clip):
            print("Invalid clip object")
            return

        print("Before halve loop:")
        self._print_clip_info(clip)

        loop_length = clip.loop_end - clip.loop_start
        new_loop_end = clip.loop_start + loop_length / 2

        print(f"Attempting to halve loop: loop_start={clip.loop_start}, loop_end={clip.loop_end}, new_loop_end={new_loop_end}")

        if new_loop_end - clip.loop_start >= 1:  # Ensure the new loop is at least 1 beat long
            old_start, old_end = clip.loop_start, clip.loop_end
            clip.loop_end = new_loop_end
            print(f"Halved loop: old_start={old_start}, old_end={old_end}, new_start={clip.loop_start}, new_end={clip.loop_end}")
        else:
            print(f"Couldn't halve loop: new loop length would be less than 1 beat")

        print("After halve loop attempt:")
        self._print_clip_info(clip)
        print("---")

    def _print_clip_info(self, clip):
        print(f"Clip Info:")
        print(f"  Length: {clip.length}")
        print(f"  Calculated Length: {clip.end_marker - clip.start_marker}")
        print(f"  Loop Start: {clip.loop_start}")
        print(f"  Loop End: {clip.loop_end}")
        print(f"  Is Audio Clip: {clip.is_audio_clip}")
        print(f"  Is MIDI Clip: {clip.is_midi_clip}")
        if clip.is_audio_clip:
            print(f"  Warp Mode: {clip.warp_mode}")
            print(f"  Warping: {clip.warping}")
            print(f"  Sample Length: {clip.sample_length}")
            print(f"  Sample Rate: {clip.sample_rate}")
            print(f"  Unwarped Length: {clip.sample_length / clip.sample_rate}")
            print(f"  Start Marker: {clip.start_marker}")
            print(f"  End Marker: {clip.end_marker}")
            print(f"  File Path: {clip.file_path}")
        print(f"  Looping: {clip.looping}")
        print(f"  Signature Numerator: {clip.signature_numerator}")
        print(f"  Signature Denominator: {clip.signature_denominator}")
        print("---")
        
    def _double_loop_length(self, clip):
        if not liveobj_valid(clip):
            print("Invalid clip object")
            return

        print("Before double loop:")
        self._print_clip_info(clip)

        loop_length = clip.loop_end - clip.loop_start
        new_loop_end = clip.loop_start + 2 * loop_length
        clip_length = clip.end_marker - clip.start_marker

        print(f"Attempting to double loop: loop_start={clip.loop_start}, loop_end={clip.loop_end}, new_loop_end={new_loop_end}, clip_length={clip_length}")

        if new_loop_end <= clip_length:
            old_start, old_end = clip.loop_start, clip.loop_end
            clip.loop_end = new_loop_end
            print(f"Doubled loop: old_start={old_start}, old_end={old_end}, new_start={clip.loop_start}, new_end={clip.loop_end}")
        else:
            print(f"Couldn't double loop: new loop end ({new_loop_end}) would exceed clip length ({clip_length})")

        print("After double loop attempt:")
        self._print_clip_info(clip)
        print("---")

    def _move_loop(self, clip, direction):
        if not liveobj_valid(clip):
            print("Invalid clip object")
            return

        print("Before move:")
        self._print_clip_info(clip)

        song = self.song()
        quantization_value = song.clip_trigger_quantization
        
        def quantize_beat(beat):
            quant_grid = {
                Live.Song.Quantization.q_8_bars: 32.0,
                Live.Song.Quantization.q_4_bars: 16.0,
                Live.Song.Quantization.q_2_bars: 8.0,
                Live.Song.Quantization.q_bar: 4.0,
                Live.Song.Quantization.q_half: 2.0,
                Live.Song.Quantization.q_quarter: 1.0,
                Live.Song.Quantization.q_eight: 0.5,
                Live.Song.Quantization.q_sixtenth: 0.25,
                Live.Song.Quantization.q_thirtytwoth: 0.125
            }
            grid = quant_grid.get(quantization_value, 1.0)
            return max(grid, 0.125)  # Ensure a minimum movement of 1/32 note

        loop_length = clip.loop_end - clip.loop_start
        jump_amount = direction * quantize_beat(1)

        print(f"Attempting to move: direction={direction}, jump_amount={jump_amount}")

        # For warped clips, use end marker instead of clip length
        if clip.is_audio_clip and clip.warping:
            effective_clip_length = clip.end_marker
        else:
            effective_clip_length = clip.length

        print(f"Effective clip length: {effective_clip_length}")

        new_start = clip.loop_start + jump_amount
        new_end = new_start + loop_length

        print(f"Calculated new positions: new_start={new_start}, new_end={new_end}")

        # Ensure the loop stays within the effective clip boundaries
        if new_start >= 0 and new_end <= effective_clip_length:
            old_start, old_end = clip.loop_start, clip.loop_end
            try:
                clip.loop_start = new_start
                clip.loop_end = new_end
                print(f"Moved loop: old_start={old_start}, old_end={old_end}, new_start={clip.loop_start}, new_end={clip.loop_end}")
            except RuntimeError as e:
                print(f"Error moving loop: {str(e)}")
                # If setting both points fails, try to maintain the loop length
                try:
                    if direction > 0:
                        clip.loop_end = min(new_end, effective_clip_length)
                        clip.loop_start = max(clip.loop_end - loop_length, 0)
                    else:
                        clip.loop_start = max(new_start, 0)
                        clip.loop_end = min(clip.loop_start + loop_length, effective_clip_length)
                    print(f"Adjusted loop: start={clip.loop_start}, end={clip.loop_end}")
                except RuntimeError as e2:
                    print(f"Failed to adjust loop: {str(e2)}")
        else:
            if new_start < 0:
                print(f"Couldn't move loop: new start ({new_start}) would be less than 0")
            elif new_end > effective_clip_length:
                print(f"Couldn't move loop: new end ({new_end}) would exceed effective clip length ({effective_clip_length})")
            else:
                print(f"Couldn't move loop: unknown boundary issue. new_start={new_start}, new_end={new_end}, effective_clip_length={effective_clip_length}")

        print("After move attempt:")
        self._print_clip_info(clip)
        print("---")
        
    def _handle_side_button_press(self, index):
        if not self._is_enabled:
            print("ClipLooper: Component is not enabled, ignoring side button press")
            return
        if 0 <= index < len(self._clip_slots):
            clip_slot = self._clip_slots[index]
            if clip_slot and clip_slot.has_clip:
                self._selected_clip_index = index
                self.update()
                self.log_message(f"Selected clip {index}")
                self._focus_on_clip(clip_slot.clip)
            else:
                self.log_message(f"No clip in slot {index}")
        else:
            self.log_message(f"Invalid side button index: {index}")

    def _handle_nav_button_press(self, index):
        if not self._is_enabled:
            print("ClipLooper: Component is not enabled, ignoring nav button press")
            return
        self._update_display()
       
        pass

    def _set_loop_points(self, clip, is_button_down):
        if not liveobj_valid(clip):
            return

        song = self.song()
        quantization_value = song.clip_trigger_quantization
        
        def quantize_beat(beat):
            quant_grid = {
                Live.Song.Quantization.q_8_bars: 32.0,
                Live.Song.Quantization.q_4_bars: 16.0,
                Live.Song.Quantization.q_2_bars: 8.0,
                Live.Song.Quantization.q_bar: 4.0,
                Live.Song.Quantization.q_half: 2.0,
                Live.Song.Quantization.q_quarter: 1.0,
                Live.Song.Quantization.q_eight: 0.5,
                Live.Song.Quantization.q_sixtenth: 0.25,
                Live.Song.Quantization.q_thirtytwoth: 0.125
            }
            grid = quant_grid.get(quantization_value, 1.0)
            return round(beat / grid) * grid

        original_start = clip.start_marker
        original_end = clip.end_marker
        original_length = original_end - original_start
        print(f"Before any changes: start_marker={original_start}, end_marker={original_end}, length={original_length}")
        print(f"Before any changes: loop_start={clip.loop_start}, loop_end={clip.loop_end}")
        print(f"Current playhead position: {clip.playing_position}")
        print(f"Is button down: {is_button_down}")
        print(f"Current quantization: {quantization_value}")
        
        if is_button_down:
            self._temp_loop_start = quantize_beat(clip.playing_position - original_start)
            print(f"Storing temporary loop start: {self._temp_loop_start}")
            clip.looping = False  # Turn off clip looping
            print("Turned off clip looping")
        else:
            temp_loop_end = quantize_beat(clip.playing_position - original_start)
            print(f"Setting quantized loop: temp_loop_start={self._temp_loop_start}, temp_loop_end={temp_loop_end}")
            
            try:
                clip.looping = True  # Turn on clip looping
                print("Turned on clip looping")
                
                start = max(0, min(self._temp_loop_start, original_length))
                end = max(start + 1, min(temp_loop_end, original_length))  # Ensure loop is at least 1 beat long
                clip.loop_start = start
                clip.loop_end = end
                print(f"Set loop_start to {clip.loop_start}, loop_end to {clip.loop_end}")
            except Exception as e:
                print(f"Error setting loop points: {str(e)}")

        print(f"Final state: loop_start={clip.loop_start}, loop_end={clip.loop_end}")
        print(f"Final state: start_marker={clip.start_marker}, end_marker={clip.end_marker}")
        print(f"Final state: clip looping = {clip.looping}")
        print("---")

    def _on_timer(self):
        current_time = time.time()
        self.log_message(f"Timer callback triggered at {current_time}")
        if self._is_enabled:
            for i, clip_slot in enumerate(self._clip_slots):
                if clip_slot and clip_slot.has_clip:
                    clip = clip_slot.clip
                    self.log_message(f"Clip {i} status: is_playing={clip.is_playing}, is_triggered={clip.is_triggered}")
                    if clip.is_playing:
                        old_position = self._playhead_position[i]
                        self._playhead_position[i] = clip.playing_position
                        self.log_message(f"Clip {i} playhead updated: {old_position} -> {self._playhead_position[i]}")
                    else:
                        self.log_message(f"Clip {i} is not playing")
                else:
                    self.log_message(f"Clip slot {i} is empty or invalid")
            self._update_display()
        else:
            self.log_message("Component is not enabled")

    def update(self):
        print("ClipLooper: Entering update method")
        if not self._is_enabled:
            print("ClipLooper: Component is not enabled, skipping update")
            return
        super(ClipLooperComponent, self).update()
        if self._is_enabled:
            print("ClipLooper: Updating enabled component")
            self.log_message("Updating component")
            self.update_clip_slots()
            self._update_display()
            self._update_side_buttons()
            self._update_nav_buttons()
        else:
            print("ClipLooper: Component is not enabled, clearing display")
            self._clear_display()
        print("ClipLooper: Finished update method")

    def update_clip_slots(self):
        print("ClipLooper: Entering update_clip_slots method")
        if not self._is_enabled:
            print("ClipLooper: ClipLooperComponent is not enabled, skipping update_clip_slots")
            return
        
        self._on_clip_playing_status_changed.subject = None
        song = self.song()
        track_offset = self._session_component.track_offset()
        scene_offset = self._session_component.scene_offset()

        self._clip_slots = []

        for track_index in range(3):  # Get 3 tracks
            if track_offset + track_index < len(song.tracks):
                track = song.tracks[track_offset + track_index]
                clip_slot = None
                for scene_index in range(len(track.clip_slots) - scene_offset):
                    current_slot = track.clip_slots[scene_offset + scene_index]
                    if current_slot.has_clip and current_slot.clip.is_playing and not current_slot.clip.muted:
                        clip_slot = current_slot
                        break
                self._clip_slots.append(clip_slot)
            else:
                self._clip_slots.append(None)

        self._playhead_position = [0] * len(self._clip_slots)
        self._loop_start = [0] * len(self._clip_slots)
        self._loop_end = [7] * len(self._clip_slots)

        self._setup_clip_listeners()

        for i, clip_slot in enumerate(self._clip_slots):
            if clip_slot:
                self.log_message(f"Clip slot {i}: has_clip={clip_slot.has_clip}")
                if clip_slot.has_clip:
                    clip = clip_slot.clip
                    self.log_message(f"Clip {i} details: name={clip.name}, is_playing={clip.is_playing}, is_triggered={clip.is_triggered}")

        print(f"Updated clip slots: {[cs.clip.name if cs and cs.has_clip else 'None' for cs in self._clip_slots]}")
        print("ClipLooper: Finished update_clip_slots method")

    @subject_slot('selected_track')
    def _on_selected_track_changed(self):
        self.update_clip_slots()
        self.update()

    @subject_slot('selected_scene')
    def _on_selected_scene_changed(self):
        self.update_clip_slots()
        self.update()

    def _focus_on_clip(self, clip):
        """
        Focus on the given clip in Ableton's detail view.
        """
        if liveobj_valid(clip):
            try:
                self.song().view.detail_clip = clip
                clip_slot = clip.canonical_parent
                if liveobj_valid(clip_slot):
                    track = clip_slot.canonical_parent
                    if liveobj_valid(track):
                        scene_index = list(track.clip_slots).index(clip_slot)
                        if 0 <= scene_index < len(self.song().scenes):
                            self.song().view.selected_scene = self.song().scenes[scene_index]
                        self.song().view.selected_track = track
                self.log_message(f"Focused on clip: {clip.name}")
            except Exception as e:
                self.log_message(f"Error focusing on clip: {str(e)}")

    def _update_display(self):
        if not self._is_enabled:
           return
        if not self._matrix:
            # self.log_message("No matrix available for display update")
            return

        for i, clip_slot in enumerate(self._clip_slots):
            y_offset = i * 2
            if clip_slot is not None and clip_slot.has_clip and clip_slot.clip.is_audio_clip:
                clip = clip_slot.clip
                clip_length = clip.end_marker - clip.start_marker
                loop_start_exact = (clip.loop_start - clip.start_marker) * 8 / clip_length
                loop_end_exact = (clip.loop_end - clip.start_marker) * 8 / clip_length
                playhead_exact = (clip.playing_position - clip.start_marker) * 8 / clip_length
                
                # self.log_message(f"Updating display for Clip {i}: loop_start={loop_start_exact}, loop_end={loop_end_exact}, playhead={playhead_exact}")
                # self.log_message(f"Clip {i} details: length={clip_length}, playing_position={clip.playing_position}")
                
                # Use the new color handling function
                clip_color_value = self.get_clip_color(clip)
                
                # Update top row (loop and playhead)
                for x in range(8):
                    button_start = x
                    button_end = x + 1
                    
                    if button_start <= playhead_exact < button_end:
                        # self.log_message(f"Setting playhead color for Clip {i} at position {x} to {clip_color_value}")
                        self._matrix.get_button(x, y_offset).set_light("ClipLooper.Playhead") #Playhead
                    elif button_start <= loop_start_exact < button_end or (x == 0 and loop_start_exact == 8):
                        self._matrix.get_button(x, y_offset).send_value(clip_color_value, channel=0) #LoopStart
                    elif button_start < loop_end_exact <= button_end:
                        self._matrix.get_button(x, y_offset).send_value(clip_color_value, channel=0) #LoopEnd
                    elif loop_start_exact < button_start and button_end <= loop_end_exact:
                        self._matrix.get_button(x, y_offset).send_value(clip_color_value, channel=0) #LoopOn
                    else:
                        self._matrix.get_button(x, y_offset).set_light("ClipLooper.LoopOff")

                # Update bottom row (controls)
                for x in range(8):
                    if x == 0:
                        self._matrix.get_button(x, y_offset + 1).set_light("ClipLooper.SetLoop")
                    elif x == 1:
                        self._matrix.get_button(x, y_offset + 1).set_light("ClipLooper.MoveLeft")
                    elif x == 2:
                        self._matrix.get_button(x, y_offset + 1).set_light("ClipLooper.MoveRight")
                    elif x == 4:
                        self._matrix.get_button(x, y_offset + 1).set_light("ClipLooper.DoubleLoop")
                    elif x == 3:
                        self._matrix.get_button(x, y_offset + 1).set_light("ClipLooper.HalveLoop")
                    # elif button_start <= loop_start_exact < button_end or button_start < loop_end_exact <= button_end or (loop_start_exact < button_start and button_end <= loop_end_exact):
                    #     self._matrix.get_button(x, y_offset + 1).set_light("ClipLooper.InLoop")
                    # else:
                    #     self._matrix.get_button(x, y_offset + 1).set_light("ClipLooper.OutLoop")
            else:
                # self.log_message(f"No valid audio clip for slot {i}, setting to dim gray")
                # Set both rows to dim gray
                for y in range(2):
                    for x in range(8):
                        self._matrix.get_button(x, y_offset + y).set_light("ClipLooper.Disabled")

        self._update_side_buttons()

    def get_clip_color(self, clip):
        """
        Get the color value for a clip using both color index and RGB value.
        """
        clip_color_index = clip.color_index
        clip_color_rgb = clip.color
        # self.log_message(f"Clip color index: {clip_color_index}")
        # self.log_message(f"Clip color RGB: {clip_color_rgb}")

        # Extract RGB values
        r = (clip_color_rgb >> 16) & 255
        g = (clip_color_rgb >> 8) & 255
        b = clip_color_rgb & 255
        # self.log_message(f"Extracted RGB: ({r}, {g}, {b})")

        # Find the closest matching color in the CLIP_COLOR_TABLE
        clip_color_value = self.find_closest_color((r, g, b))

        # self.log_message(f"Final clip color value: {clip_color_value}")
        return clip_color_value

    def find_closest_color(self, rgb):
        """
        Find the closest matching color in the CLIP_COLOR_TABLE or ABLETON_TO_LAUNCHPAD_COLORS.
        """
        if isinstance(rgb, tuple):
            if rgb in ABLETON_TO_LAUNCHPAD_COLORS:
                return ABLETON_TO_LAUNCHPAD_COLORS[rgb]
        else:
            rgb = (rgb >> 16, (rgb >> 8) & 255, rgb & 255)
        
        return min(CLIP_COLOR_TABLE.items(), key=lambda x: self.color_distance(x[0], rgb))[1]

    def color_distance(self, color1, color2):
        """
        Calculate the distance between two RGB colors.
        """
        r1, g1, b1 = color1 if isinstance(color1, tuple) else (color1 >> 16, (color1 >> 8) & 255, color1 & 255)
        r2, g2, b2 = color2
        return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5

    def _update_side_buttons(self):
        for i, clip_slot in enumerate(self._clip_slots):
            if self._side_buttons and i < len(self._side_buttons):
                button = self._side_buttons[i]
                if clip_slot and clip_slot.has_clip:
                    clip = clip_slot.clip
                    clip_color_value = self.get_clip_color(clip)
                    button.send_value(clip_color_value, channel=0)
                else:
                    button.set_light("DefaultButton.Disabled")

    def _update_nav_buttons(self):

        pass

    def _clear_clip_display(self, index):
        y_offset = index * 2
        for y in range(2):
            for x in range(8):
                self._matrix.get_button(x, y_offset + y).set_light("CLipLooper.Disabled")

    def set_enabled(self, enable):
        print(f"ClipLooper: Setting ClipLooperComponent enabled: {enable}")
        if self._is_enabled != enable:
            self._is_enabled = enable
            if self._is_enabled:
                self._update_timer.start()
                self._setup_clip_listeners()
                self.update_clip_slots()
                self._update_display()
            else:
                self._update_timer.stop()
                self._clear_display()
                self._remove_clip_listeners()
            self.update()
        print(f"ClipLooper: ClipLooperComponent enabled state: {self._is_enabled}")

    def _clear_display(self):
        if self._matrix:
            for x in range(8):
                for y in range(6):
                    self._matrix.get_button(x, y).set_light("ClipLooper.Disabled")
        if self._side_buttons:
            for button in self._side_buttons:
                button.set_light("DefaultButton.Disabled")


        super(ClipLooperComponent, self).disconnect()

    def _setup_clip_listeners(self):
        print("ClipLooper: Setting up clip listeners")
        if not self._is_enabled:
            print("ClipLooper: ClipLooperComponent is not enabled, skipping setup of clip listeners")
            return
        for i, clip_slot in enumerate(self._clip_slots):
            if clip_slot and clip_slot.has_clip:
                clip = clip_slot.clip
                if not clip.playing_position_has_listener(self._on_playing_position_changed):
                    clip.add_playing_position_listener(self._on_playing_position_changed)
                if not clip.color_index_has_listener(self._on_clip_color_changed):
                    clip.add_color_index_listener(self._on_clip_color_changed)
                if not clip.color_has_listener(self._on_clip_color_changed):
                    clip.add_color_listener(self._on_clip_color_changed)
                self.log_message(f"Added color listeners for Clip {i}")
        print("ClipLooper: Finished setting up clip listeners")

    @subject_slot('playing_status')
    def _on_clip_playing_status_changed(self):
        self.log_message("Clip playing status changed")
        for i, clip_slot in enumerate(self._clip_slots):
            if clip_slot and clip_slot.has_clip:
                clip = clip_slot.clip
                self.log_message(f"Clip {i} playing status: is_playing={clip.is_playing}, is_triggered={clip.is_triggered}")
        self.update()

    def _on_playing_position_changed(self):
        for i, clip_slot in enumerate(self._clip_slots):
            if clip_slot and clip_slot.has_clip and clip_slot.clip.is_playing:
                self._playhead_position[i] = clip_slot.clip.playing_position
                # self.log_message(f"Clip {i} playing position changed: {self._playhead_position[i]}")
        self._update_display()

    def _on_clip_color_changed(self):
        self.log_message("Clip color changed")
        for i, clip_slot in enumerate(self._clip_slots):
            if clip_slot and clip_slot.has_clip:
                clip = clip_slot.clip
                color_index = clip.color_index
                color = clip.color
                self.log_message(f"Clip {i} color updated: index={color_index}, RGB={color}")
        self._update_display()

    def log_message(self, message):
        if hasattr(self, '_control_surface') and hasattr(self._control_surface, 'log_message'):
            self._control_surface.log_message(f"ClipLooper: {message}")
        else:
            print(f"ClipLooper: {message}")

    def _remove_clip_listeners(self):
        for clip_slot in self._clip_slots:
            if clip_slot and clip_slot.has_clip:
                clip = clip_slot.clip
                if clip.playing_position_has_listener(self._on_playing_position_changed):
                    clip.remove_playing_position_listener(self._on_playing_position_changed)
                if clip.color_index_has_listener(self._on_clip_color_changed):
                    clip.remove_color_index_listener(self._on_clip_color_changed)
                if clip.color_has_listener(self._on_clip_color_changed):
                    clip.remove_color_listener(self._on_clip_color_changed)
        print("ClipLooper: Removed all clip listeners")

    def disconnect(self):
        print("ClipLooper: Disconnecting")
        self._remove_clip_listeners()
        self._on_clip_playing_status_changed.subject = None
        if self._side_buttons:
            for button in self._side_buttons:
                button.remove_value_listener(self._on_side_button_value)
        if self._nav_buttons:
            for button in self._nav_buttons:
                self.disconnect_nav_button(button)
        self._update_timer.stop()
        self._matrix = None  # Clear matrix reference
        self._side_buttons = None  # Clear side buttons reference
        self._nav_buttons = None  # Clear nav buttons reference
        super(ClipLooperComponent, self).disconnect()
        print("ClipLooper: Disconnection complete")

