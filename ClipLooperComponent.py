from __future__ import absolute_import, print_function, unicode_literals
from _Framework.CompoundComponent import CompoundComponent
from _Framework.ButtonMatrixElement import ButtonMatrixElement
from _Framework.SubjectSlot import subject_slot, SlotManager
from _Framework.SessionComponent import SessionComponent
from ableton.v2.base import liveobj_valid
from .ColorsMK2 import CLIP_COLOR_TABLE, RGB_COLOR_TABLE
import Live
import time

TRANSPOSE_REPEAT_DELAY = 500  # ms
TRANSPOSE_REPEAT_INTERVAL = 50 # ms, faster repeat for transpose

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
MIN_LOOP_LENGTH_BEATS = 0.125 # Minimum allowed loop length

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
        self._temp_loop_start = None # Added for _set_loop_points logic
        self._transpose_up_timers = [None] * 3 # Added for transposition repeat
        self._transpose_down_timers = [None] * 3 # Added for transposition repeat
        self._is_enabled = False
        self._monitored_tracks = []
        self._ignore_top_row = False # Flag to ignore row 0 when in transport overlay mode
        self._control_surface = None # Added for logging

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

    def set_ignore_top_row(self, ignore):
        self.log_message(f"Setting ignore_top_row to: {ignore}")
        self._ignore_top_row = ignore
        self.update() # Trigger an update to redraw correctly

    @subject_slot('value')
    def _on_matrix_value(self, value, x, y, is_momentary):
        if self._ignore_top_row:
            # --- Transport Mode ---
            if y == 0: # Row 0 is transport, ignore here
                return

            if y == 1: # Physical Row 1 is transpose
                clip_index = -1
                action = None # 'down' or 'up'

                if x == 0: clip_index, action = 0, 'down'
                elif x == 1: clip_index, action = 0, 'up'
                elif x == 2: clip_index, action = 1, 'down'
                elif x == 3: clip_index, action = 1, 'up'
                elif x == 4: clip_index, action = 2, 'down'
                elif x == 5: clip_index, action = 2, 'up'

                if clip_index != -1 and action:
                    if action == 'down':
                        if value: self._on_transpose_down_pressed(clip_index)
                        else: self._on_transpose_down_released(clip_index)
                    elif action == 'up':
                        if value: self._on_transpose_up_pressed(clip_index)
                        else: self._on_transpose_up_released(clip_index)
                return # Handled transpose, exit

            # --- Clip Rows (Physical Rows 2-7) ---
            effective_y = y - 2 # Offset by transport (0) and transpose (1) rows
            if effective_y < 0: # Should only happen for y=0, 1 handled above
                 self.log_message(f"Ignoring press on unexpected row {y} in transport mode.")
                 return

        else:
            # --- Normal Mode (Physical Rows 0-5) ---
            if y < 0 or y >= 6: # Clip controls are on rows 0-5
                self.log_message(f"Ignoring press on row {y} outside active clip area in normal mode.")
                return
            effective_y = y # No offset

        # --- Common Logic for Clip Interaction ---
        if effective_y >= 0: # Ensure we are in a valid clip row range
            clip_index = effective_y // 2
            row_type = effective_y % 2 # 0 for Playhead/Loop, 1 for Controls

            if 0 <= clip_index < len(self._clip_slots):
                clip_slot = self._clip_slots[clip_index]
                if clip_slot is not None and clip_slot.has_clip:
                    clip = clip_slot.clip
                    if row_type == 0:  # Playhead/Loop row
                        if value == 127:  # Only set position on button press
                            self._set_clip_position(clip, x)
                    else:  # Control row
                        if x == 0:  # Loop set button
                            self._set_loop_points(clip, value == 127)  # Handle both press and release
                        elif value == 127:  # Only handle press for other control buttons
                            self._handle_control_press(clip, x)
                else:
                    self.log_message(f"No valid clip at index {clip_index} for row_type {row_type} (effective_y={effective_y}, y={y})")
            else:
                self.log_message(f"Clip index {clip_index} out of range (effective_y={effective_y}, y={y})")

        self._update_display() # Update display after handling regular clip interactions

    def _on_side_button_value(self, value, sender):
        if not self._is_enabled:
            print("ClipLooper: Component is not enabled, ignoring side button value")
            return

        if value and self._side_buttons:  # Only handle button presses
            try:
                index = list(self._side_buttons).index(sender)
                # Map side button index (2, 4, 6) to clip index (0, 1, 2) for FOCUS
                # Map side button index (3, 5, 7) to clip index (0, 1, 2) for PLAY/STOP TOGGLE
                focus_clip_index = -1
                toggle_clip_index = -1

                if index == 2: focus_clip_index = 0
                elif index == 4: focus_clip_index = 1
                elif index == 6: focus_clip_index = 2
                elif index == 3: toggle_clip_index = 0
                elif index == 5: toggle_clip_index = 1
                elif index == 7: toggle_clip_index = 2
                
                # Handle FOCUS action
                if 0 <= focus_clip_index < len(self._clip_slots):
                    clip_slot = self._clip_slots[focus_clip_index]
                    if clip_slot and clip_slot.has_clip:
                        self._selected_clip_index = focus_clip_index 
                        self.log_message(f"Side button {index} selected clip {focus_clip_index}")
                        self._focus_on_clip(clip_slot.clip)
                        # Only update display after focusing
                        self._update_display()
                    else:
                        self.log_message(f"No clip in slot {focus_clip_index} for side button {index}")
                # Handle MUTE TOGGLE action
                elif 0 <= toggle_clip_index < len(self._clip_slots):
                    clip_slot = self._clip_slots[toggle_clip_index]
                    # Get the track object
                    track = None
                    if clip_slot and liveobj_valid(clip_slot):
                        track = clip_slot.canonical_parent # Track is the parent of clip_slot

                    if track and liveobj_valid(track):
                        # Toggle mute state
                        new_mute_state = not track.mute
                        self.log_message(f"Side button {index} toggling track mute for clip {toggle_clip_index}. Current: {track.mute}, Setting to: {new_mute_state}")
                        track.mute = new_mute_state
                        self._update_display()  # Update display after mute toggle
                    else:
                         self.log_message(f"No valid track found for clip_slot at index {toggle_clip_index} for side button {index}")
                else:
                    # Ignore presses on side buttons 0, 1
                    self.log_message(f"Ignoring press on unused side button index: {index}")
                    
            except ValueError:
                self.log_message(f"Sender {sender} not found in side buttons")

    def _on_nav_button_value(self, value, sender):
        if value and self._nav_buttons:  # Only handle button presses
            index = list(self._nav_buttons).index(sender)
            self._handle_nav_button_press(index)

    def _clip_uses_absolute_loop_points(self, clip):
        return liveobj_valid(clip) and clip.is_audio_clip and clip.warping

    def _get_loop_position_bounds(self, clip):
        if self._clip_uses_absolute_loop_points(clip):
            return clip.start_marker, clip.end_marker
        return 0.0, max(0.0, clip.end_marker - clip.start_marker)

    def _get_quantized_playback_position(self, clip, quantize_beat):
        if self._clip_uses_absolute_loop_points(clip):
            return quantize_beat(clip.playing_position)
        return quantize_beat(clip.playing_position - clip.start_marker)

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
        loop_min, loop_max = self._get_loop_position_bounds(clip)
        loop_range = loop_max - loop_min
        current_loop_length = clip.loop_end - clip.loop_start

        print(f"Before any changes: start_marker={original_start}, end_marker={original_end}, length={original_length}")
        print(f"Current loop: start={clip.loop_start}, end={clip.loop_end}, length={current_loop_length}")
        print(f"Button pressed: x={x}")
        print(f"Current quantization: {quantization_value}")

        # Calculate the new loop start and end - use 8 divisions for intuitive positioning
        # This makes button 0 = start, button 4 = middle, button 7 = 7/8 through the clip
        new_loop_start = loop_min + (x / 8.0) * loop_range
        new_loop_start_quantized = quantize_beat(new_loop_start)
        max_loop_start = max(loop_min, loop_max - current_loop_length)
        new_loop_start_quantized = max(loop_min, min(new_loop_start_quantized, max_loop_start))
        new_loop_end = min(new_loop_start_quantized + current_loop_length, loop_max)

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
        elif x == 5: # Decrease loop length by quantization
            self._adjust_loop_length_by_quantization(clip, -1)
        elif x == 6: # Increase loop length by quantization
            self._adjust_loop_length_by_quantization(clip, 1)
        elif x == 7: # Toggle loop on/off
            self._toggle_loop(clip)

        # Only focus if we didn't already focus in the adjustment method
        if x not in [5, 6]:
            self._focus_on_clip(clip) # Focus on the clip after manipulation

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
        _, loop_max = self._get_loop_position_bounds(clip)

        print(f"Attempting to double loop: loop_start={clip.loop_start}, loop_end={clip.loop_end}, new_loop_end={new_loop_end}, loop_max={loop_max}")

        if new_loop_end <= loop_max:
            old_start, old_end = clip.loop_start, clip.loop_end
            clip.loop_end = new_loop_end
            print(f"Doubled loop: old_start={old_start}, old_end={old_end}, new_start={clip.loop_start}, new_end={clip.loop_end}")
        else:
            print(f"Couldn't double loop: new loop end ({new_loop_end}) would exceed clip boundary ({loop_max})")

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
        loop_min, loop_max = self._get_loop_position_bounds(clip)

        print(f"Attempting to move: direction={direction}, jump_amount={jump_amount}")
        print(f"Loop bounds: start={loop_min}, end={loop_max}")

        new_start = clip.loop_start + jump_amount
        new_end = new_start + loop_length

        print(f"Calculated new positions: new_start={new_start}, new_end={new_end}")

        # Ensure the loop stays within the clip boundaries.
        if new_start >= loop_min and new_end <= loop_max:
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
                        clip.loop_end = min(new_end, loop_max)
                        clip.loop_start = max(clip.loop_end - loop_length, loop_min)
                    else:
                        clip.loop_start = max(new_start, loop_min)
                        clip.loop_end = min(clip.loop_start + loop_length, loop_max)
                    print(f"Adjusted loop: start={clip.loop_start}, end={clip.loop_end}")
                except RuntimeError as e2:
                    print(f"Failed to adjust loop: {str(e2)}")
        else:
            if new_start < loop_min:
                print(f"Couldn't move loop: new start ({new_start}) would be less than loop boundary ({loop_min})")
            elif new_end > loop_max:
                print(f"Couldn't move loop: new end ({new_end}) would exceed loop boundary ({loop_max})")
            else:
                print(f"Couldn't move loop: unknown boundary issue. new_start={new_start}, new_end={new_end}, loop_min={loop_min}, loop_max={loop_max}")

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
        original_loop_start = clip.loop_start
        original_loop_end = clip.loop_end
        original_length = original_end - original_start
        loop_min, loop_max = self._get_loop_position_bounds(clip)
        minimum_loop_length = 1.0
        print(f"Before any changes: start_marker={original_start}, end_marker={original_end}, length={original_length}")
        print(f"Before any changes: loop_start={clip.loop_start}, loop_end={clip.loop_end}")
        print(f"Current playhead position: {clip.playing_position}")
        print(f"Is button down: {is_button_down}")
        print(f"Current quantization: {quantization_value}")
        
        if is_button_down:
            self._temp_loop_start = self._get_quantized_playback_position(clip, quantize_beat)
            print(f"Storing temporary loop start: {self._temp_loop_start}")
            clip.looping = False  # Turn off clip looping
            print("Turned off clip looping")
        else:
            if self._temp_loop_start is None:
                print("No stored loop start, ignoring loop end release")
                return

            temp_loop_end = self._get_quantized_playback_position(clip, quantize_beat)
            print(f"Setting quantized loop: temp_loop_start={self._temp_loop_start}, temp_loop_end={temp_loop_end}")
            
            try:
                clip.looping = True  # Turn on clip looping
                print("Turned on clip looping")
                
                max_loop_start = max(loop_min, loop_max - minimum_loop_length)
                start = max(loop_min, min(self._temp_loop_start, max_loop_start))
                end = max(start + minimum_loop_length, min(temp_loop_end, loop_max))  # Ensure loop is at least 1 beat long
                
                # Try setting end first, then start
                try:
                    clip.loop_end = end
                    clip.loop_start = start
                except Exception:
                    # If that fails, try setting start first, then end
                    try:
                        clip.loop_start = start
                        clip.loop_end = end
                    except Exception as e:
                        print(f"Error setting loop points: {str(e)}")
                        # If both attempts fail, revert to original loop points
                        clip.loop_start = original_loop_start
                        clip.loop_end = original_loop_end
                
                print(f"Set loop_start to {clip.loop_start}, loop_end to {clip.loop_end}")
            except Exception as e:
                print(f"Error setting loop points: {str(e)}")
            finally:
                self._temp_loop_start = None

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
                # Set the view first
                self.application().view.show_view('Detail/Clip')
                
                # Then set the detail clip
                self.song().view.detail_clip = clip
                
                # Finally set the track and scene
                clip_slot = clip.canonical_parent
                if liveobj_valid(clip_slot):
                    track = clip_slot.canonical_parent
                    if liveobj_valid(track):
                        scene_index = list(track.clip_slots).index(clip_slot)
                        if 0 <= scene_index < len(self.song().scenes):
                            self.song().view.selected_scene = self.song().scenes[scene_index]
                        self.song().view.selected_track = track
                self.log_message(f"Focused on clip: {clip.name}")
                # Update side buttons immediately after focusing
                self._update_side_buttons()
            except Exception as e:
                self.log_message(f"Error focusing on clip: {str(e)}")

    def _update_display(self):
        if not self._is_enabled:
           return
        if not self._matrix:
            # self.log_message("No matrix available for display update")
            return

        num_clip_rows = 3 # Max clips this component handles

        if self._ignore_top_row:
            # --- Transport Mode ---
            # Row 0 is handled by TransportControlComponent

            # --- Draw Transpose Row (Physical Row 1) ---
            transpose_row_y = 1
            for clip_index in range(3):
                clip_valid_for_transpose = (clip_index < len(self._clip_slots) and
                                            self._clip_slots[clip_index] is not None and
                                            self._clip_slots[clip_index].has_clip and
                                            liveobj_valid(self._clip_slots[clip_index].clip) and
                                            self._clip_slots[clip_index].clip.is_audio_clip)

                down_button_x = clip_index * 2
                up_button_x = down_button_x + 1
                clip_color_value = 0 # Default off if invalid
                if clip_valid_for_transpose:
                   clip_color_value = self.get_clip_color(self._clip_slots[clip_index].clip)

                # Draw Down Button
                button_down = self._matrix.get_button(down_button_x, transpose_row_y) # Physical Row 1
                if button_down:
                    if clip_valid_for_transpose:
                        button_down.send_value(clip_color_value, channel=0)
                    else:
                        button_down.set_light("DefaultButton.Disabled")

                # Draw Up Button
                button_up = self._matrix.get_button(up_button_x, transpose_row_y) # Physical Row 1
                if button_up:
                    if clip_valid_for_transpose:
                        button_up.send_value(clip_color_value, channel=0)
                    else:
                        button_up.set_light("DefaultButton.Disabled")

            # Turn off remaining buttons in the transpose row (x=6, 7 on Physical Row 1)
            for x in range(6, self._matrix.width()):
                 button = self._matrix.get_button(x, transpose_row_y)
                 if button:
                     button.set_light("DefaultButton.Disabled")

            # --- Draw Clip Rows (Starting Physical Row 2) ---
            clip_display_start_row = 2
            for i in range(num_clip_rows):
                playhead_row_y = clip_display_start_row + (i * 2) # Physical rows 2, 4, 6
                control_row_y = playhead_row_y + 1            # Physical rows 3, 5, 7

                # Check if rows are within matrix bounds (safety)
                if playhead_row_y >= self._matrix.height() or control_row_y >= self._matrix.height():
                    continue

                clip_slot = self._clip_slots[i] if i < len(self._clip_slots) else None

                if clip_slot is not None and clip_slot.has_clip and liveobj_valid(clip_slot.clip) and clip_slot.clip.is_audio_clip:
                    clip = clip_slot.clip
                    if not liveobj_valid(clip):
                        self.log_message(f"Clip in slot {i} became invalid during update, clearing display.")
                        self._clear_clip_display_rows_from_matrix(playhead_row_y, control_row_y)
                        continue

                    clip_length = clip.end_marker - clip.start_marker
                    loop_start_exact = (clip.loop_start - clip.start_marker) * 8 / clip_length if clip_length > 0 else 0
                    loop_end_exact = (clip.loop_end - clip.start_marker) * 8 / clip_length if clip_length > 0 else 0
                    playhead_exact = (clip.playing_position - clip.start_marker) * 8 / clip_length if clip_length > 0 else 0
                    clip_color_value = self.get_clip_color(clip)

                    # Update top row (loop and playhead) - use playhead_row_y
                    for x in range(8):
                        button = self._matrix.get_button(x, playhead_row_y)
                        if not button: continue
                        button_start, button_end = x, x + 1
                        if button_start <= playhead_exact < button_end: button.set_light("ClipLooper.Playhead")
                        elif button_start <= loop_start_exact < button_end or (x == 0 and loop_start_exact >= 8): button.send_value(clip_color_value, channel=0)
                        elif button_start < loop_end_exact <= button_end: button.send_value(clip_color_value, channel=0)
                        elif loop_start_exact < button_start and button_end <= loop_end_exact: button.send_value(clip_color_value, channel=0)
                        else: button.set_light("ClipLooper.LoopOff")

                    # Update bottom row (controls) - use control_row_y
                    for x in range(8):
                        button = self._matrix.get_button(x, control_row_y)
                        if not button: continue
                        if x == 0: button.set_light("ClipLooper.SetLoop")
                        elif x == 1: button.set_light("ClipLooper.MoveLeft")
                        elif x == 2: button.set_light("ClipLooper.MoveRight")
                        elif x == 4: button.set_light("ClipLooper.DoubleLoop")
                        elif x == 3: button.set_light("ClipLooper.HalveLoop")
                        elif x == 5: button.set_light("ClipLooper.ShrinkLoop")
                        elif x == 6: button.set_light("ClipLooper.GrowLoop")
                        elif x == 7:
                            # Toggle Loop button - use clip color when loop is on, off when loop is off
                            if clip.looping:
                                button.send_value(clip_color_value, channel=0)
                            else:
                                button.set_light("ClipLooper.Disabled")
                        else: button.set_light("ClipLooper.Disabled")
                else:
                    # Clear the display for this clip slot if no valid clip
                    self._clear_clip_display_rows_from_matrix(playhead_row_y, control_row_y)

            # --- Clear Remaining Rows (None needed in transport mode as 0-7 are used) ---

        else: # Normal mode (not ignoring top row)
            # --- Draw Clip Rows (Starting Physical Row 0) ---
            clip_display_start_row = 0
            for i in range(num_clip_rows):
                playhead_row_y = clip_display_start_row + (i * 2) # Physical rows 0, 2, 4
                control_row_y = playhead_row_y + 1            # Physical rows 1, 3, 5

                 # Check if rows are within matrix bounds (safety)
                if playhead_row_y >= self._matrix.height() or control_row_y >= self._matrix.height():
                    continue

                clip_slot = self._clip_slots[i] if i < len(self._clip_slots) else None

                if clip_slot is not None and clip_slot.has_clip and liveobj_valid(clip_slot.clip) and clip_slot.clip.is_audio_clip:
                    clip = clip_slot.clip
                    if not liveobj_valid(clip):
                        self.log_message(f"Clip in slot {i} became invalid during update, clearing display.")
                        self._clear_clip_display_rows_from_matrix(playhead_row_y, control_row_y)
                        continue

                    clip_length = clip.end_marker - clip.start_marker
                    loop_start_exact = (clip.loop_start - clip.start_marker) * 8 / clip_length if clip_length > 0 else 0
                    loop_end_exact = (clip.loop_end - clip.start_marker) * 8 / clip_length if clip_length > 0 else 0
                    playhead_exact = (clip.playing_position - clip.start_marker) * 8 / clip_length if clip_length > 0 else 0
                    clip_color_value = self.get_clip_color(clip)

                    # Update top row (loop and playhead) - use playhead_row_y
                    for x in range(8):
                        button = self._matrix.get_button(x, playhead_row_y)
                        if not button: continue
                        button_start, button_end = x, x + 1
                        if button_start <= playhead_exact < button_end: button.set_light("ClipLooper.Playhead")
                        elif button_start <= loop_start_exact < button_end or (x == 0 and loop_start_exact >= 8): button.send_value(clip_color_value, channel=0)
                        elif button_start < loop_end_exact <= button_end: button.send_value(clip_color_value, channel=0)
                        elif loop_start_exact < button_start and button_end <= loop_end_exact: button.send_value(clip_color_value, channel=0)
                        else: button.set_light("ClipLooper.LoopOff")

                    # Update bottom row (controls) - use control_row_y
                    for x in range(8):
                        button = self._matrix.get_button(x, control_row_y)
                        if not button: continue
                        if x == 0: button.set_light("ClipLooper.SetLoop")
                        elif x == 1: button.set_light("ClipLooper.MoveLeft")
                        elif x == 2: button.set_light("ClipLooper.MoveRight")
                        elif x == 4: button.set_light("ClipLooper.DoubleLoop")
                        elif x == 3: button.set_light("ClipLooper.HalveLoop")
                        elif x == 5: button.set_light("ClipLooper.ShrinkLoop")
                        elif x == 6: button.set_light("ClipLooper.GrowLoop")
                        elif x == 7:
                            # Toggle Loop button - use clip color when loop is on, off when loop is off
                            if clip.looping:
                                button.send_value(clip_color_value, channel=0)
                            else:
                                button.set_light("ClipLooper.Disabled")
                        else: button.set_light("ClipLooper.Disabled")
                else:
                    # Clear the display for this clip slot if no valid clip
                    self._clear_clip_display_rows_from_matrix(playhead_row_y, control_row_y)

            # --- Clear Remaining Rows ---
            start_clear_row = clip_display_start_row + (num_clip_rows * 2) # Should be 6
            for y in range(start_clear_row, self._matrix.height()): # Clear physical rows 6, 7
                for x in range(self._matrix.width()):
                    button = self._matrix.get_button(x, y)
                    if button:
                        button.set_light("ClipLooper.Disabled")

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
        if not self._side_buttons:
            return

        # Reset all side buttons first
        for button in self._side_buttons:
            if button:
                 button.set_light("DefaultButton.Disabled")

        # Update focus buttons (2, 4, 6) and play/toggle buttons (3, 5, 7)
        for clip_index, clip_slot in enumerate(self._clip_slots):
            focus_button_index = (clip_index * 2) + 2
            toggle_button_index = (clip_index * 2) + 3

            focus_button = self._side_buttons[focus_button_index] if focus_button_index < len(self._side_buttons) else None
            toggle_button = self._side_buttons[toggle_button_index] if toggle_button_index < len(self._side_buttons) else None
            
            if clip_slot and clip_slot.has_clip:
                clip = clip_slot.clip
                clip_color_value = self.get_clip_color(clip)
                is_selected = (clip_index == self._selected_clip_index)
                is_playing = clip.is_playing
                is_triggered = clip.is_triggered
                
                # Update Focus Button (2, 4, 6)
                if focus_button:
                    if is_selected:
                        focus_button.send_value(clip_color_value, channel=0) # Normal color for selected
                    else:
                        dim_color_value = 2 # Ultimate Gray for non-selected focus button
                        focus_button.send_value(dim_color_value, channel=0)
                        
                # Update Mute/Toggle Button (3, 5, 7)
                if toggle_button:
                    track = None
                    if clip_slot and liveobj_valid(clip_slot):
                       track = clip_slot.canonical_parent
                    
                    if track and liveobj_valid(track):
                        if track.mute:
                            muted_color_value = 13 # Yellow (Rape Blossoms)
                            toggle_button.send_value(muted_color_value, channel=0)
                        else: # Unmuted
                            # Turn the button off when unmuted
                            unmuted_color_value = 0 # 0 usually means off
                            toggle_button.send_value(unmuted_color_value, channel=0)
                    elif clip_slot and clip_slot.has_clip: # Track might be invalid but clip exists? Treat as unmuted (off).
                         unmuted_color_value = 0
                         toggle_button.send_value(unmuted_color_value, channel=0)
                    else: # No clip or track
                         toggle_button.set_light("DefaultButton.Disabled") # Keep it off / disabled

            else: # No clip in slot
                 # Ensure focus/toggle buttons for this index are off
                 if focus_button:
                     focus_button.set_light("DefaultButton.Disabled")
                 if toggle_button:
                     toggle_button.set_light("DefaultButton.Disabled")

    def _update_nav_buttons(self):
        pass # Nav buttons not currently used for specific feedback in this component

    def _clear_clip_display_rows_from_matrix(self, row1_y, row2_y):
        """ Clears two specific rows on the matrix. """
        if not self._matrix:
            return
        for y in [row1_y, row2_y]:
             if 0 <= y < self._matrix.height():
                 for x in range(self._matrix.width()):
                     button = self._matrix.get_button(x, y)
                     if button:
                         button.set_light("ClipLooper.Disabled")

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
                self.application().view.show_view('Detail/Clip') # Ensure clip detail view
                self._update_timer.start()
                self._setup_clip_listeners()
                self._setup_track_listeners()
                self.update_clip_slots()
                self._update_display()
            else:
                self._update_timer.stop()
                self._clear_display()
                self._remove_clip_listeners()
                self._remove_track_listeners()
                self._reset_state()
            self.update()
        print(f"ClipLooper: ClipLooperComponent enabled state: {self._is_enabled}")

    def _clear_display(self):
        if self._matrix:
            if self._ignore_top_row:
                start_row = 1 # Don't clear transport row 0
            else:
                start_row = 0 # Clear from row 0
            end_row = self._matrix.height()
            for y in range(start_row, end_row):
                for x in range(self._matrix.width()):
                    button = self._matrix.get_button(x, y)
                    if button:
                         # Use a generic 'off' state
                         button.set_light("DefaultButton.Disabled")
        if self._side_buttons:
            for button in self._side_buttons:
                 if button: # Check if button exists
                     button.set_light("DefaultButton.Disabled")
        # Do not call super disconnect here, it should be handled by the owner component (MainSelectorComponent)
        # super(ClipLooperComponent, self).disconnect()

    def _setup_clip_listeners(self):
        self.log_message("Setting up clip listeners")
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
        # Check for control_surface attribute before logging
        if hasattr(self, '_control_surface') and self._control_surface and hasattr(self._control_surface, 'log_message'):
            try:
                self._control_surface.log_message(f"ClipLooper: {message}")
            except Exception as e:
                print(f"ClipLooper Log Error: {e}")
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

    def _reset_state(self):
        print("ClipLooper: Resetting state")
        self._clip_slots = []
        self._playhead_position = []
        self._loop_start = []
        self._loop_end = []
        self._temp_loop_start = None
        self._selected_clip_index = -1
        self._is_setting_loop = False

    def _setup_track_listeners(self):
        self.log_message("Setting up track listeners")
        if not self._is_enabled:
            self.log_message("ClipLooperComponent is not enabled, skipping setup of track listeners")
            return
            
        self._remove_track_listeners()  # Remove existing listeners first
        
        song = self.song()
        track_offset = self._session_component.track_offset()
        self._monitored_tracks = []
        
        for track_index in range(3):  # Monitor 3 tracks
            absolute_track_index = track_offset + track_index
            if absolute_track_index < len(song.tracks):
                track = song.tracks[absolute_track_index]
                if liveobj_valid(track):
                    self._monitored_tracks.append(track) # Store valid tracks
                    # Add fired_slot_index listener
                    if not track.fired_slot_index_has_listener(self._on_track_fired_slot_index_changed):
                        track.add_fired_slot_index_listener(self._on_track_fired_slot_index_changed)
                        self.log_message(f"Added fired_slot_index listener to track {absolute_track_index}")
                    # Add mute listener
                    if not track.mute_has_listener(self._on_track_mute_changed):
                         track.add_mute_listener(self._on_track_mute_changed)
                         self.log_message(f"Added mute listener to track {absolute_track_index}")
        
    def _on_track_fired_slot_index_changed(self):
        self.log_message("Track fired slot index changed")
        # This will refresh which clips we're monitoring
        self.update_clip_slots()
        self._update_display()

    def _on_track_mute_changed(self):
        self.log_message("Track mute changed")
        self.update() # Trigger a display update
        
    def _remove_track_listeners(self):
        self.log_message("Removing track listeners")
        for track in self._monitored_tracks:
            if liveobj_valid(track):
                # Remove fired_slot_index listener
                if track.fired_slot_index_has_listener(self._on_track_fired_slot_index_changed):
                    track.remove_fired_slot_index_listener(self._on_track_fired_slot_index_changed)
                # Remove mute listener
                if track.mute_has_listener(self._on_track_mute_changed):
                    track.remove_mute_listener(self._on_track_mute_changed)
        self._monitored_tracks = []

    def disconnect(self):
        print("ClipLooper: Disconnecting")
        self._remove_clip_listeners()
        self._remove_track_listeners()
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
        # Stop and clear transposition timers
        for i in range(len(self._transpose_up_timers)):
             self._on_transpose_up_released(i) # Use release helper to stop/clear
        for i in range(len(self._transpose_down_timers)):
             self._on_transpose_down_released(i) # Use release helper to stop/clear
        super(ClipLooperComponent, self).disconnect()
        print("ClipLooper: Disconnection complete")

    def _get_quantization_beat_value(self):
        """ Returns the current global quantization value in beats. """
        song = self.song()
        quantization_value = song.clip_trigger_quantization
        quant_grid = {
            Live.Song.Quantization.q_no_q: 0.0, # Should handle no quantization case
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
        # Default to clip's minimum if quantization is off or unknown
        return quant_grid.get(quantization_value, MIN_LOOP_LENGTH_BEATS)

    def _adjust_loop_length_by_quantization(self, clip, direction):
        """ Increases or decreases the loop end by the current quantization value. """
        if not liveobj_valid(clip):
            self.log_message("Invalid clip object for loop adjustment")
            return

        quant_beats = self._get_quantization_beat_value()
        if quant_beats <= 0:
            self.log_message(f"Cannot adjust loop length: quantization value is zero or negative ({quant_beats})")
            return

        change_amount = direction * quant_beats
        current_loop_start = clip.loop_start
        current_loop_end = clip.loop_end
        new_loop_end = current_loop_end + change_amount

        # Loop points are absolute for warped audio clips and relative-to-zero otherwise.
        if clip.is_audio_clip and clip.warping:
            max_loop_end = clip.end_marker
        else:
            max_loop_end = clip.length

        self.log_message(f"Adjusting loop: current_start={current_loop_start}, current_end={current_loop_end}, change={change_amount}, max_end={max_loop_end}")

        # --- Validation ---
        # 1. Ensure new end is after start.
        if new_loop_end <= current_loop_start:
            self.log_message(f"Cannot adjust loop: new end ({new_loop_end}) would be before or at start ({current_loop_start})")
            return

        # 2. Ensure new end stays inside the clip boundary.
        if new_loop_end > max_loop_end:
            self.log_message(f"Cannot adjust loop: new end ({new_loop_end}) would exceed clip boundary ({max_loop_end})")
            return

        # 3. Ensure minimum loop length.
        if (new_loop_end - current_loop_start) < MIN_LOOP_LENGTH_BEATS:
            self.log_message(f"Cannot adjust loop: new length ({new_loop_end - current_loop_start}) would be less than minimum ({MIN_LOOP_LENGTH_BEATS})")
            return

        # --- Apply Change ---
        try:
            clip.loop_end = new_loop_end
            self.log_message(f"Adjusted loop end: old={current_loop_end}, new={clip.loop_end}")
        except Exception as e:
            self.log_message(f"Error adjusting loop end: {str(e)}")
            # Attempt to restore original value if setting failed
            try:
                clip.loop_end = current_loop_end
            except:
                pass # Avoid nested exceptions

        self._print_clip_info(clip)
        self._focus_on_clip(clip) # Keep focus after adjustment

    # --- Transposition Control (Triggered by Matrix) --- #

    def _on_transpose_up_pressed(self, index):
        if self._change_transpose(index, 1):
            # Focus the clip if transposition was successful
            self._selected_clip_index = index # Set the selected index
            clip_slot = self._clip_slots[index]
            if clip_slot and clip_slot.has_clip:
                self._focus_on_clip(clip_slot.clip)
                
            if self._transpose_up_timers[index] is not None:
                self._transpose_up_timers[index].stop()
            self._transpose_up_timers[index] = Live.Base.Timer(callback=lambda: self._repeat_transpose_up(index), interval=TRANSPOSE_REPEAT_DELAY, start=True)
            self.log_message(f"Transpose Up Pressed (Clip {index}), starting timer.")

    def _on_transpose_down_pressed(self, index):
        if self._change_transpose(index, -1):
            # Focus the clip if transposition was successful
            self._selected_clip_index = index # Set the selected index
            clip_slot = self._clip_slots[index]
            if clip_slot and clip_slot.has_clip:
                self._focus_on_clip(clip_slot.clip)

            if self._transpose_down_timers[index] is not None:
                self._transpose_down_timers[index].stop()
            self._transpose_down_timers[index] = Live.Base.Timer(callback=lambda: self._repeat_transpose_down(index), interval=TRANSPOSE_REPEAT_DELAY, start=True)
            self.log_message(f"Transpose Down Pressed (Clip {index}), starting timer.")

    def _on_transpose_up_released(self, index):
        if index < len(self._transpose_up_timers) and self._transpose_up_timers[index] is not None:
            self._transpose_up_timers[index].stop()
            self._transpose_up_timers[index] = None
            self.log_message(f"Transpose Up Released (Clip {index}), stopping timer.")

    def _on_transpose_down_released(self, index):
        if index < len(self._transpose_down_timers) and self._transpose_down_timers[index] is not None:
            self._transpose_down_timers[index].stop()
            self._transpose_down_timers[index] = None
            self.log_message(f"Transpose Down Released (Clip {index}), stopping timer.")

    def _repeat_transpose_up(self, index):
        if self._change_transpose(index, 1):
            if index < len(self._transpose_up_timers) and self._transpose_up_timers[index] is not None:
                self._transpose_up_timers[index].stop() # Stop the old timer
                # Create and start a new timer with the faster interval
                self._transpose_up_timers[index] = Live.Base.Timer(callback=lambda: self._repeat_transpose_up(index), interval=TRANSPOSE_REPEAT_INTERVAL, start=True)
                self.log_message(f"Repeat Transpose Up (Clip {index}), interval {TRANSPOSE_REPEAT_INTERVAL}.")
            else:
                self.log_message(f"Repeat Transpose Up (Clip {index}) - Timer Error or Index Out of Bounds!")
        else:
             self._on_transpose_up_released(index) # Stop repeating if change failed

    def _repeat_transpose_down(self, index):
        if self._change_transpose(index, -1):
            if index < len(self._transpose_down_timers) and self._transpose_down_timers[index] is not None:
                self._transpose_down_timers[index].stop() # Stop the old timer
                # Create and start a new timer with the faster interval
                self._transpose_down_timers[index] = Live.Base.Timer(callback=lambda: self._repeat_transpose_down(index), interval=TRANSPOSE_REPEAT_INTERVAL, start=True)
                self.log_message(f"Repeat Transpose Down (Clip {index}), interval {TRANSPOSE_REPEAT_INTERVAL}.")
            else:
                self.log_message(f"Repeat Transpose Down (Clip {index}) - Timer Error or Index Out of Bounds!")
        else:
            self._on_transpose_down_released(index) # Stop repeating if change failed

    def _change_transpose(self, index, delta):
        if 0 <= index < len(self._clip_slots):
            clip_slot = self._clip_slots[index]
            if clip_slot and clip_slot.has_clip:
                clip = clip_slot.clip
                if liveobj_valid(clip) and clip.is_audio_clip: # Only transpose audio clips for now
                    current_pitch = clip.pitch_coarse
                    new_pitch = max(-48, min(48, current_pitch + delta)) # Limit to +/- 48 semitones
                    if new_pitch != current_pitch:
                        clip.pitch_coarse = new_pitch
                        self.log_message(f"Changed Clip {index} pitch_coarse from {current_pitch} to {new_pitch}")
                        return True
                    else:
                        self.log_message(f"Clip {index} pitch already at limit ({current_pitch}).")
                        return False
                else:
                    self.log_message(f"Clip {index} is not a valid audio clip for transposition.")
                    return False
            else:
                self.log_message(f"No valid clip at index {index} for transposition.")
                return False
        self.log_message(f"Invalid index {index} for transposition.")
        return False

    def _toggle_loop(self, clip):
        """Toggle the clip's looping state on/off."""
        if not liveobj_valid(clip):
            self.log_message("Invalid clip object for loop toggle")
            return
            
        try:
            # Toggle the looping state
            new_looping_state = not clip.looping
            clip.looping = new_looping_state
            self.log_message(f"Toggled clip looping: {clip.looping}")
        except Exception as e:
            self.log_message(f"Error toggling loop state: {str(e)}")

        self._print_clip_info(clip)

