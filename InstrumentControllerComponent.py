import Live
from _Framework.CompoundComponent import CompoundComponent
from _Framework.SubjectSlot import subject_slot
from _Framework.ButtonElement import ButtonElement
from _Framework.Util import find_if, clamp
from ableton.v2.base import liveobj_valid
try:
	from itertools import imap
except ImportError:
	# Python 3...
	imap=map
	
from .TrackControllerComponent import TrackControllerComponent
from .ScaleComponent import ScaleComponent,CIRCLE_OF_FIFTHS,MUSICAL_MODES,KEY_NAMES
try:
	from .Settings import Settings
except ImportError:
	from .Settings import *
	
#fix for python3
try:
	xrange
except NameError:
	xrange = range

from _Framework.ButtonMatrixElement import ButtonMatrixElement
KEY_MODE = 0
SCALE_TYPE_MODE = 1

# Add necessary imports for color handling
from .ColorsMK2 import CLIP_COLOR_TABLE, RGB_COLOR_TABLE, Rgb # Assuming RGB_COLOR_TABLE exists or adapt as needed

# Add ABLETON_TO_LAUNCHPAD_COLORS if needed, or rely on find_closest_color logic
# Example based on ClipLooperComponent - adjust if your color definitions differ
ABLETON_TO_LAUNCHPAD_COLORS = {
    0: 72, 1: 96, 2: 100, 3: 98, 4: 122, 5: 21, 6: 37, 7: 45, 8: 105, 9: 105,
    10: 113, 11: 95, 12: 95, 13: 3, 14: 5, 15: 84, 16: 11, 17: 13, 18: 76, 19: 21,
    20: 37, 21: 45, 22: 105, 23: 47, 24: 115, 25: 116, 26: 95, 27: 118, 28: 106, 29: 97,
    30: 99, 31: 121, 32: 123, 33: 123, 34: 123, 35: 49, 36: 49, 37: 113, 38: 116, 39: 116,
    40: 119, 41: 2, 42: 107, 43: 11, 44: 11, 45: 99, 46: 76, 47: 76, 48: 45, 49: 49,
    50: 104, 51: 104, 52: 116, 53: 116, 54: 106, 55: 1, 56: 7, 57: 11, 58: 83, 59: 100,
    60: 28, 61: 28, 62: 45, 63: 47, 64: 53, 65: 53, 66: 115, 67: 115, 68: 71, 69: 0
}

class InstrumentControllerComponent(CompoundComponent):

	def __init__(self, matrix, side_buttons, top_buttons, control_surface, note_repeat):
		super(InstrumentControllerComponent, self).__init__()
		self._control_surface = control_surface
		self._note_repeat = note_repeat
		self._osd = None
		self._matrix = None
		self._side_buttons = side_buttons
		self._remaining_buttons = []
		self._track_controller = None
		self.base_channel = 11
		self._quick_scales = [0, 1, 2, 3, 4, 5, 6, 7, 10, 13, 14, 15, 17, 18, 24]
		self._quick_scale_root = 0
		self._normal_feedback_velocity = int(self._control_surface._skin['Note.Feedback'])
		self._recordind_feedback_velocity = int(self._control_surface._skin['Note.FeedbackRecord'])
		self._drum_group_device = None
		self._octave_up_button = None
		self._octave_down_button = None
		self._scales_toggle_button = None
		self._track_pad_color_int = None  # Initialize track color cache
		self._using_track_color_for_feedback = False  # Flag to track if we're using track color

		# Initialize color table using the CLIP_COLOR_TABLE directly
		self._clip_color_table = CLIP_COLOR_TABLE

		self.set_scales_toggle_button(side_buttons[0])#Enable scale selecting mode
		self.set_octave_up_button(side_buttons[2])#Shift octave up
		self.set_octave_down_button(side_buttons[3])#Shift octave down
		
		self._osd_mode_backup = "Instrument"
		
		self._track_controller = self.register_component(TrackControllerComponent(control_surface = control_surface, implicit_arm = True))
		self._track_controller.set_enabled(False)
		
		#Clip navigation buttons
		self._track_controller.set_prev_scene_button(top_buttons[0])
		self._track_controller.set_next_scene_button(top_buttons[1])
		self._track_controller.set_prev_track_button(top_buttons[2])
		self._track_controller.set_next_track_button(top_buttons[3])
		
		#Clip edition buttons
		self._track_controller.set_undo_button(side_buttons[1])
		self._track_controller.set_start_stop_button(side_buttons[4])
		self._track_controller.set_lock_button(side_buttons[5])
		self._track_controller.set_solo_button(side_buttons[6])
		self._track_controller.set_session_record_button(side_buttons[7])

		self._scales = self.register_component(ScaleComponent(self._control_surface))
		#self._scales.set_enabled(False)
		self._scales.set_osd(self._osd)
		
		self.set_matrix(matrix)

		self._on_session_record_changed.subject = self.song()
		self._on_swing_amount_changed_in_live.subject = self.song()
		self._note_repeat_selector = False
		self._note_repeat.set_enabled(False)
	
	# --- Helper functions for color conversion (adapted from ClipLooperComponent) ---
	def color_distance(self, color1, color2):
		"""
		Calculate the distance between two RGB colors.
		"""
		# Handle both tuple and integer color representations
		r1, g1, b1 = color1 if isinstance(color1, tuple) else (color1 >> 16, (color1 >> 8) & 255, color1 & 255)
		r2, g2, b2 = color2 if isinstance(color2, tuple) else (color2 >> 16, (color2 >> 8) & 255, color2 & 255)
		return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5

	def find_closest_color(self, track_color_rgb_int):
		"""
		Find the closest matching Launchpad color value using the ABLETON_TO_LAUNCHPAD_COLORS mapping.
		Input is the Ableton track color integer.
		Returns a Launchpad color value (integer 0-127).
		"""
		if track_color_rgb_int is None:
			return None

		# Try direct mapping first - this should work for standard Ableton colors
		if track_color_rgb_int in ABLETON_TO_LAUNCHPAD_COLORS:
			return ABLETON_TO_LAUNCHPAD_COLORS[track_color_rgb_int]

		# Extract RGB values if input is an integer
		if isinstance(track_color_rgb_int, int):
			r = (track_color_rgb_int >> 16) & 255
			g = (track_color_rgb_int >> 8) & 255
			b = track_color_rgb_int & 255
			track_rgb_tuple = (r, g, b)
		else:
			track_rgb_tuple = track_color_rgb_int

		# Check if we already have a mapping for this RGB tuple
		if isinstance(track_rgb_tuple, tuple) and track_rgb_tuple in ABLETON_TO_LAUNCHPAD_COLORS:
			return ABLETON_TO_LAUNCHPAD_COLORS[track_rgb_tuple]

		# Find the closest matching color in the CLIP_COLOR_TABLE
		closest_color_value = None
		min_dist = float('inf')
		
		for color_tuple, lp_value in self._clip_color_table.items():
			dist = self.color_distance(color_tuple, track_rgb_tuple)
			if dist < min_dist:
				min_dist = dist
				closest_color_value = lp_value
		
		return closest_color_value

	# --- End of helper functions ---

	def _remove_scale_listeners(self):
		try:
			self.song().remove_root_note_listener(self.handle_root_note_changed)
		except RuntimeError:
			pass
		try:
			self.song().remove_scale_name_listener(self.handle_scale_name_changed)
		except RuntimeError:
			pass
	
	def _register_scale_listeners(self):
		try:
			self.song().add_root_note_listener(self.handle_root_note_changed)
		except RuntimeError:
			pass
		try:
			self.song().add_scale_name_listener(self.handle_scale_name_changed)
		except RuntimeError:
			pass

	def handle_root_note_changed(self):
		self._scales.set_key(self.song().root_note, False, True)
		self.update()


	def handle_scale_name_changed(self):
		self._scales.set_modus(self._scales._modus_names.index(self.song().scale_name), False, True)
		self.update()
		
		

	def set_enabled(self, enabled):
		CompoundComponent.set_enabled(self, enabled)
		if self._track_controller != None:
			self._track_controller.set_enabled(enabled)
		feedback_channels = [self.base_channel, self.base_channel + 1, self.base_channel + 2, self.base_channel + 3]
		# non_feedback_channel = self.base_channel + 4
		
		# Update track color and then set feedback velocity
		if enabled:
			self._update_track_color()
		self._set_feedback_velocity()
		
		self._control_surface.set_feedback_channels(feedback_channels)
		if not enabled:
			self._control_surface.release_controlled_track()
			self._note_repeat.set_enabled(False)
			self._remove_scale_listeners()
		else:
			self._control_surface.set_controlled_track(self._track_controller.selected_track)

		if self._track_controller != None:
			self._register_scale_listeners()
			self._track_controller._do_implicit_arm(enabled)
			self._track_controller.set_enabled(enabled)
			
		if enabled:
			self._update_OSD()
			self.on_selected_track_changed()
					
	def _set_feedback_velocity(self):
		if self.song().session_record:
			# For recording, always use the red feedback color
			self._control_surface._c_instance.set_feedback_velocity(self._recordind_feedback_velocity)
			self._using_track_color_for_feedback = False
		elif self._scales.is_drumrack and self._drum_group_device != None:
			# For drum mode, use the standard feedback color
			self._control_surface._c_instance.set_feedback_velocity(self._normal_feedback_velocity)
			self._using_track_color_for_feedback = False
		else:
			# For note mode, use track color if available
			if self._track_pad_color_int is not None:
				self._control_surface._c_instance.set_feedback_velocity(self._track_pad_color_int)
				self._using_track_color_for_feedback = True
			else:
				# Fallback to standard feedback color if no track color
				self._control_surface._c_instance.set_feedback_velocity(self._normal_feedback_velocity)
				self._using_track_color_for_feedback = False

	@subject_slot('session_record')
	def _on_session_record_changed(self):
		self._set_feedback_velocity()

	@subject_slot('swing_amount')
	def _on_swing_amount_changed_in_live(self):
		self.update()

	def _change_swing_amount_value(self, value):
		self._set_swing_amount_value(clamp(self.song().swing_amount + value*0.025, 0.0, 0.99))

		
	def _set_swing_amount_value(self, value):
		self.song().swing_amount = value
		self._control_surface.show_message("REPEATER Swing amount: " + str(int(self._swing_amount()*100)) + "%")
				
	def _swing_amount(self):
		return self.song().swing_amount
	
	def _toggle_note_repeat_selector(self):
		self._note_repeat_selector = not self._note_repeat_selector
	
	def _toggle_note_repeater(self):
		self._note_repeat.set_enabled(not self._note_repeat.is_enabled())
		

	# Refresh button and its listener
	def set_scales_toggle_button(self, button):
		assert isinstance(button, (ButtonElement, type(None)))
		if (self._scales_toggle_button != None):
			self._scales_toggle_button.remove_value_listener(self._scales_toggle)
		self._scales_toggle_button = button
		if (self._scales_toggle_button != None):
			self._scales_toggle_button.add_value_listener(self._scales_toggle, identify_sender=True)
			self._scales_toggle_button.turn_off()

	# Refresh button and its listener
	def set_octave_up_button(self, button=None):
		assert isinstance(button, (ButtonElement, type(None)))
		if (self._octave_up_button != None):
			self._octave_up_button.remove_value_listener(self._scroll_octave_up)
		self._octave_up_button = button
		if (self._octave_up_button != None):
			self._octave_up_button.add_value_listener(self._scroll_octave_up, identify_sender=True)
			self._octave_up_button.turn_off()

	# Refresh button and its listener
	def set_octave_down_button(self, button=None):
		assert isinstance(button, (ButtonElement, type(None)))
		if (self._octave_down_button != None):
			self._octave_down_button.remove_value_listener(self._scroll_octave_down)
		self._octave_down_button = button
		if (self._octave_down_button != None):
			self._octave_down_button.add_value_listener(self._scroll_octave_down, identify_sender=True)
			self._octave_down_button.turn_off()

	#Enables scale selection mode
	def _scales_toggle(self, value, sender):
		if self.is_enabled():
			if (value != 0):
				self._get_drumrack_device()
				if(self._scales.is_drumrack and self._drum_group_device != None):
					self._toggle_note_repeat_selector()
					self._scales_toggle_button.turn_on()
					self._scales.update()
				else:
					self._scales.set_enabled(True)
					self._osd_mode_backup = self._osd.mode
					self._osd.mode = self._osd_mode_backup + ' - Scale'
					self._scales_toggle_button.turn_on()
					self._scales.update()
			else:
				self._scales_toggle_button.turn_off()
				self._scales.set_enabled(False)
				self._osd.mode = self._osd_mode_backup
				if(not self._scales.is_quick_scale):
					self._note_repeat.set_enabled(False)
				self.update()


	# Transposes key one octave up 
	def _scroll_octave_up(self, value, sender):
		if self.is_enabled():
			if ((not sender.is_momentary()) or (value != 0)):
				if self._can_scroll_octave_up():
					self._scales._octave += 1
					self.update()

	def _can_scroll_octave_up(self):
		if(self._scales.is_drumrack):
			if self._note_repeat_selector:
				return self._scales._octave < 6
			else:	
				return self._scales._octave < 5
		else:
			return self._scales._octave < 10

	# Transposes key one octave down 
	def _scroll_octave_down(self, value, sender):
		if self.is_enabled():
			if ((not sender.is_momentary()) or (value != 0)):
				if self._can_scroll_octave_down():
					self._scales._octave -= 1
					self.update()

	def _can_scroll_octave_down(self):
		if(self._scales.is_drumrack):
			return self._scales._octave  > 0
		else:
			return self._scales._octave  > -2

	#Handles scale setting and configuration
	def _matrix_value_quickscale(self, value, x, y, is_momentary):  # matrix buttons listener for advanced mode
		if self.is_enabled():
			if self._scales.is_drumrack:
				if ((value != 0) or (not is_momentary)):
	
					if(y == 0):
						if x == 4:
							self._change_swing_amount_value(-1) 
						elif x == 5:
							self._change_swing_amount_value(1)
						elif x == 6:
							pass   
						elif x == 7:
							self._toggle_note_repeater()
							self._control_surface.show_message("REPEATER is: " + str("ON" if self._note_repeat.is_enabled() else "OFF"))																							
					elif(y == 1):
						if x == 4:
							self._set_swing_amount_value(0.0)   
						elif x == 5:
							self._set_swing_amount_value(0.25)   
						if x == 6:
							self._set_swing_amount_value(0.5)	
						elif x == 7:
							self._set_swing_amount_value(0.75)	
					elif(y == 2):
						self._note_repeat.set_freq_index((x-4)*2+y-2)
						self._control_surface.show_message("REPEATER Step: " + str(self._note_repeat.freq_name()))
					elif(y == 3):  
						self._note_repeat.set_freq_index((x-4)*2+y-2)
						self._control_surface.show_message("REPEATER Step: " + str(self._note_repeat.freq_name()))
					self.update()

			elif not self._scales.is_enabled() and self._scales.is_quick_scale:
				keys = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
				if ((value != 0) or (not is_momentary)):
					if self._quick_scale_root==0:
						root = -1
						selected_key = self._scales._key
						selected_modus = self._scales._modus
						#Root selection keys
						if y == 1 and x < 7 or y == 0 and x in[0, 1, 3, 4, 5]:
							if y == 1:
								root = [0, 2, 4, 5, 7, 9, 11, 12][x]
								self._control_surface.show_message(keys[root]+" "+str(self._scales._modus_names[selected_modus]))
							if y == 0 and x < 6:
								root = [0, 2, 4, 5, 7, 9, 11, 12][x] + 1
								self._control_surface.show_message(keys[root]+" "+str(self._scales._modus_names[selected_modus]))
							if root == selected_key:  # alternate minor/major
								if selected_modus == 0:
									selected_modus = self._scales._current_minor_mode
								elif selected_modus in [1, 13, 14]:
									self._scales._current_minor_mode = selected_modus
									selected_modus = 0
								elif selected_modus == 11:
									selected_modus = 12
								elif selected_modus == 12:
									selected_modus = 11
								self._control_surface.show_message(keys[root]+" "+str(self._scales._modus_names[selected_modus]))
						else:
							
							if y == 0 and x == 7:  # change scale mode
								self.setup_quick_scale_mode()
								self.update()
							if y == 1 and x == 7:  # nav circle of 5th right
								root = CIRCLE_OF_FIFTHS[(self.tuple_idx(CIRCLE_OF_FIFTHS, selected_key) + 1 + 12) % 12]
								self._control_surface.show_message("circle of 5ths -> "+keys[selected_key]+" "+str(self._scales._modus_names[selected_modus])+" => "+keys[root]+" "+str(self._scales._modus_names[selected_modus]))
							if y == 0 and x == 6:  # nav circle of 5th left
								root = CIRCLE_OF_FIFTHS[(self.tuple_idx(CIRCLE_OF_FIFTHS, selected_key) - 1 + 12) % 12]
								self._control_surface.show_message("circle of 5ths <- "+keys[selected_key]+" "+str(self._scales._modus_names[selected_modus])+" => "+keys[root]+" "+str(self._scales._modus_names[selected_modus]))
							if y == 0 and x == 2:  # relative scale
								if selected_modus == 0:
									selected_modus = self._scales._current_minor_mode
									root = CIRCLE_OF_FIFTHS[(self.tuple_idx(CIRCLE_OF_FIFTHS, selected_key) + 3) % 12]
								elif selected_modus in [1, 13, 14]:
									self._scales._current_minor_mode = selected_modus
									selected_modus = 0
									root = CIRCLE_OF_FIFTHS[(self.tuple_idx(CIRCLE_OF_FIFTHS, selected_key) - 3 + 12) % 12]
								elif selected_modus == 11:
									selected_modus = 12
									root = CIRCLE_OF_FIFTHS[(self.tuple_idx(CIRCLE_OF_FIFTHS, selected_key) + 3) % 12]
								elif selected_modus == 12:
									selected_modus = 11
									root = CIRCLE_OF_FIFTHS[(self.tuple_idx(CIRCLE_OF_FIFTHS, selected_key) - 3 + 12) % 12]
								self._control_surface.show_message("Relative scale : "+keys[root]+" "+str(self._scales._modus_names[selected_modus]))
	
						if root != -1:
							self._scales.set_modus(selected_modus, False)
							self._scales.set_key(root, False)
							self.update()
	
					elif self._quick_scale_root==1:
						if(y == 0):
							if x < 7 and self._quick_scales[x] != -1:
								self._scales.set_modus(self._quick_scales[x])
								self._control_surface.show_message("mode : "+str(self._scales._modus_names[self._scales._modus]))
								self.update()
							if x == 7:
								self.setup_quick_scale_mode()
								self.update()
						if(y == 1):
							if x < 8 and self._quick_scales[x + 7] != -1:
								self._scales.set_modus(self._quick_scales[x + 7])
								self._control_surface.show_message("mode : "+str(self._scales._modus_names[self._scales._modus]))
								self.update()
					else:
						if(y == 0):
							if x == 0:
								self._change_swing_amount_value(-1)
							elif x == 1:
								self._change_swing_amount_value(1)
							elif x == 2:
								self._set_swing_amount_value(0.0)
							elif x == 3:
								self._set_swing_amount_value(0.25)
							elif x == 4:
								self._set_swing_amount_value(0.5)	
							elif x == 5:
								self._set_swing_amount_value(0.75)	
							elif x == 6:
								self._toggle_note_repeater()
								self._control_surface.show_message("REPEATER is: " + str("ON" if self._note_repeat.is_enabled() else "OFF"))																							
							elif x == 7:
								self.setup_quick_scale_mode()
								
						if(y == 1):
							if x in range(8):
								
								self._note_repeat.set_freq_index(x)
								self._control_surface.show_message("REPEATER Step: " + str(self._note_repeat.freq_name()))
						self.update()							

	def setup_quick_scale_mode(self):
		
		self._quick_scale_root = ((self._quick_scale_root + 1) % 3)
		
		if self._quick_scale_root==0:
			self._control_surface.show_message("quick scale : root")
		elif self._quick_scale_root==1:
			self._control_surface.show_message("quick scale : modes")
		else:
			self._control_surface.show_message("quick scale : REPEATER")

	def _update_track_color(self):
		"""Update the track color cache for the currently selected track"""
		self._track_pad_color_int = None
		selected_track = self._track_controller.selected_track
		if liveobj_valid(selected_track):
			# Get the track color via the find_closest_color method
			track_color_rgb = selected_track.color
			self._track_pad_color_int = self.find_closest_color(track_color_rgb)
		
		return self._track_pad_color_int

	def update(self):
		if self.is_enabled():
			if self._track_controller != None:
				self._track_controller.set_enabled(True)

			# Update track color cache
			self._update_track_color()
			
			self._update_matrix()

			for button in self._remaining_buttons:
				button.set_light("DefaultButton.Disabled")

			if self._scales_toggle_button != None:
				self._scales_toggle_button.set_on_off_values("Note.Scale")
				self._scales_toggle_button.turn_off()

			if self._octave_up_button != None:
				self._octave_up_button.set_on_off_values("Note.Octave")
				if(self._can_scroll_octave_up()):
					self._octave_up_button.turn_on()
				else:
					self._octave_up_button.turn_off()

			if self._octave_down_button != None:
				self._octave_down_button.set_on_off_values("Note.Octave")
				if(self._can_scroll_octave_down()):
					self._octave_down_button.turn_on()
				else:
					self._octave_down_button.turn_off()

			self._update_OSD()
			#self._control_surface.log_message("Swing Amount: " + str(self._swing_amount()))

	def set_osd(self, osd):
		self._osd = osd

	def _update_OSD(self):
		if self._osd != None:
			if self._scales.is_quick_scale:
				self._osd.mode = "Instrument (quick scale)"
			else:
				self._osd.mode = "Instrument"
			self._osd.attributes[0] = MUSICAL_MODES[self._scales._modus * 2]
			self._osd.attribute_names[0] = "Scale"
			self._osd.attributes[1] = KEY_NAMES[self._scales._key % 12]
			self._osd.attribute_names[1] = "Root Note"
			self._osd.attributes[2] = self._scales._octave
			self._osd.attribute_names[2] = "Octave"
			self._osd.attributes[3] = " "
			self._osd.attribute_names[3] = " "
			self._osd.attributes[4] = " "
			self._osd.attribute_names[4] = " "
			self._osd.attributes[5] = " "
			self._osd.attribute_names[5] = " "
			self._osd.attributes[6] = " "
			self._osd.attribute_names[6] = " "
			self._osd.attributes[7] = " "
			self._osd.attribute_names[7] = " "

			if self._track_controller.selected_track != None:
				self._osd.info[0] = "track : " + self._track_controller.selected_track.name
			else:
				self._osd.info[0] = " "

			self._osd.info[1] = " "
			self._osd.update()

	# Refresh matrix and its listener
	def set_matrix(self, matrix):
		old_matrix = self._matrix
		if old_matrix != matrix and old_matrix != None:
			old_matrix.remove_value_listener(self._matrix_value_quickscale)
		self._matrix = matrix
		if self._matrix != None:
			self._matrix.reset()
			if old_matrix != matrix:
				self._matrix.add_value_listener(self._matrix_value_quickscale)
		if self._scales != None:
			self._scales.set_matrix(matrix)
		self._update_matrix()

	#Listener, setup drumrack scale mode and load the selected scale for Track/Cip (Disabled)
	def on_selected_track_changed(self):
		if self._track_controller._implicit_arm:
			# Update track color first thing when track changes
			self._track_pad_color_int = None  # Clear the cache
			self._update_track_color()  # Update with new track's color
			
			self._get_drumrack_device()
			if self._drum_group_device != None:
				self._scales.set_drumrack(True)
			else:
				self._scales.set_drumrack(False)
				
			self._note_repeat.set_enabled(False)
			# Update feedback velocity to match the new track color
			self._set_feedback_velocity()
			self.update()
	
	def on_selected_scene_changed(self):
		if self._track_controller._implicit_arm:		
			self.update()

	#Set the drum rack instrument to _drum_group_device variable, if it exists
	def _get_drumrack_device(self):
		if self._track_controller.selected_track != None:
			track = self._track_controller.selected_track
			if(track.devices != None and len(track.devices) > 0):
				#device = track.devices[0]
				device = self.find_drum_group_device(track)
				if(device != None and device.can_have_drum_pads and device.has_drum_pads):
					self._drum_group_device = device
				else:
					self._drum_group_device = None
			else:
				self._drum_group_device = None
		else:
			self._drum_group_device = None
	
	#Return the drum device inside the track devices or inside the track chain or None if device is not a Drum
	def find_drum_group_device(self, track):
		device = find_if(lambda d: d.type == Live.Device.DeviceType.instrument, track.devices)
		if device:
			if device.can_have_drum_pads:
				return device
			elif device.can_have_chains:
				return find_if(bool, imap(self.find_drum_group_device, device.chains))
		else:
			return None
			
	def _update_matrix(self):
		if not self.is_enabled() or not self._matrix or self._scales.is_enabled():
			self._control_surface.release_controlled_track()
			# self._control_surface.set_feedback_channels([])
		else:
			# feedback_channels = [self.base_channel, self.base_channel + 1, self.base_channel + 2, self.base_channel + 3]
			non_feedback_channel = self.base_channel + 4

			# create array to keep last channel used for note.
			note_channel = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0 ]
			#range(128)
			for i in range(128):
				note_channel[i] = self.base_channel

			# Validate if device is drumrack (assign _drum_group_device)
			self._get_drumrack_device()

			if self._scales.is_drumrack and not self._scales.is_diatonic and not self._scales.is_chromatic:
				self._scales.set_drumrack(True) 
			else:
				self._scales.set_drumrack(False)

			for button, (x, y) in self._matrix.iterbuttons():
				button.use_default_message()
				button.set_channel(non_feedback_channel)
				#button.force_next_send()

			if self._scales.is_drumrack:
				#Live.Base.log("InstrumentControllerComponent - OCTAVE: " + str(self._scales._octave))
				
				for button, (x, y) in self._matrix.iterbuttons():
					if button:
						note = 0

						if(x < 4):
							note = 16 * (self._scales._octave -1)+ x + 4 * (8 - y)
						else:
							note = 16 * (self._scales._octave -1) + 32 + x + 4 * (7 - y)	 

						if self._note_repeat_selector:
							if(x >= 4 and y<4):
								note = -99 #Avoid light errors

						if note < 128 and note >= 0:
							if self._drum_group_device == None or (self._drum_group_device != None and self._drum_group_device.can_have_drum_pads and self._drum_group_device.has_drum_pads and self._drum_group_device.drum_pads[note].chains):
								light = self._getLightForNote(note)
								button.set_enabled(False)
								button.set_channel(self.base_channel)
								button.set_identifier(note)
								
								# Check if light is an integer (track color) or string (skin value)
								if isinstance(light, int):
									button.send_value(light)
								else:
									button.set_light(light)
							else:
								button.set_light("DrumGroup.PadEmpty")
								button.set_enabled(False)
								button.set_channel(self.base_channel)
								button.set_identifier(note)
						elif (note == -99):
							
							button.set_enabled(True)
							button.set_channel(non_feedback_channel)
							
							if (y==0):
								
								if(x==4):
									button.set_on_off_values("QuickScale.Quant.On", "QuickScale.Quant.Off")
									if(not self._swing_amount() ==0.0):
										button.turn_on()
									else:
										button.turn_off()
								elif(x ==5):
									button.set_on_off_values("QuickScale.Quant.On", "QuickScale.Quant.Off")
									if(self._swing_amount() < 0.98):
										button.turn_on()
									else:
										button.turn_off()   
								elif(x ==6):
									button.set_light("DrumGroup.PadEmpty")										
								elif(x ==7):
									button.set_on_off_values("QuickScale.NoteRepeater.On", "QuickScale.NoteRepeater.Off")
									if(self._note_repeat.is_enabled()):
										button.turn_on()
									else:								
										button.turn_off() 
							elif(y==1):
								if(x ==4):
									button.set_on_off_values("QuickScale.Quant.Straight", "DefaultButton.Disabled")
									button.turn_on()
								elif(x ==5):
									button.set_on_off_values("QuickScale.Quant.Swing", "DefaultButton.Disabled")
									button.turn_on()
								elif(x ==6):
									button.set_on_off_values("QuickScale.Quant.Dotted", "DefaultButton.Disabled")
									button.turn_on()
								elif(x ==7):
									button.set_on_off_values("QuickScale.Quant.Flam", "DefaultButton.Disabled")
									button.turn_on()  
							elif(y==2 or y==3):
								if(x%2==0):						
									button.set_on_off_values("QuickScale.Quant.Selected", "QuickScale.Quant.Note")
								else:
									button.set_on_off_values("QuickScale.Quant.Selected", "QuickScale.Quant.Tripplet")
								if ((x-4)*2+y-2) == self._note_repeat.freq_index():
									button.turn_on()
								else:
									button.turn_off()	
						else:
							button.set_light("DrumGroup.PadEmpty")
							button.set_enabled(True)
							button.set_channel(non_feedback_channel)
						#button.force_next_send()
						#button.turn_off()
						
						
			else:
				# --- Get Track Color ---
				track_pad_color_int = self._track_pad_color_int  # Use cached value
				if track_pad_color_int is None:
					track_pad_color_int = self._update_track_color()  # Update if not cached


				# Define skin fallbacks
				root_skin_key = 'Note.Pads.Root'
				drum_filled_skin_key = 'DrumGroup.PadFilled'
				in_scale_color = "Note.Pads.InScale" # Keep using skin color for non-root notes for contrast
				highlight_color = "Note.Pads.Highlight"
				out_of_scale_color = "Note.Pads.OutOfScale"
				invalid_color = "Note.Pads.Invalid"
				empty_pad_color = "DrumGroup.PadEmpty" # Added for drum rack consistency
				# --- End Track Color ---


				if self._scales.is_quick_scale:

					selected_modus = self._scales._modus
					selected_key = self._scales._key


					if self._quick_scale_root==KEY_MODE:
						if selected_modus == 0 or selected_modus == 12:
							key_color = "QuickScale.Major.Key"
							fifth_button_color = "QuickScale.Major.CircleOfFifths"
							mode_button_color = "QuickScale.Major.Mode"
							relative_scale_button_color = "QuickScale.Major.RelativeScale"
						elif selected_modus == 1 or selected_modus == 11:
							key_color = "QuickScale.Minor.Key"
							fifth_button_color = "QuickScale.Minor.CircleOfFifths"
							mode_button_color = "QuickScale.Minor.Mode"
							relative_scale_button_color = "QuickScale.Minor.RelativeScale"
						else:
							key_color = "QuickScale.Other.Key"
							fifth_button_color = "QuickScale.Other.CircleOfFifths"
							mode_button_color = "QuickScale.Other.Mode"
							relative_scale_button_color = "QuickScale.Other.RelativeScale"

						# circle of 5th nav right
						button = self._matrix.get_button(7, 1)
						button.set_light(fifth_button_color)
						# circle of 5th nav left
						button = self._matrix.get_button(6, 0)
						button.set_light(fifth_button_color)
						# mode button
						button = self._matrix.get_button(7, 0)
						button.set_light(mode_button_color)
						# relative scale button
						button = self._matrix.get_button(2, 0)
						button.set_light(relative_scale_button_color)

						for x in [0, 1, 3, 4, 5]:
							button = self._matrix.get_button(x, 0)
							button.set_enabled(True)
							button.set_on_off_values(key_color)
							#button.force_next_send()
							if [0, 2, 4, 5, 7, 9, 11, 12][x] + 1 == selected_key:
								button.turn_on()
							else:
								button.turn_off()

						for x in [0, 1, 2, 3, 4, 5, 6]:
							button = self._matrix.get_button(x, 1)
							button.set_enabled(True)
							button.set_on_off_values(key_color)
							#button.force_next_send()
							if [0, 2, 4, 5, 7, 9, 11, 12][x] == selected_key:
								button.turn_on()
							else:
								button.turn_off()
					elif self._quick_scale_root==SCALE_TYPE_MODE:
						button = self._matrix.get_button(7, 0)
						button.set_light("QuickScale.Major.Mode")
						for x in range(7):
							button = self._matrix.get_button(x, 0)
							button.set_enabled(True)
							if self._quick_scales[x] != -1:
								button.set_on_off_values("QuickScale.Modus")
								if self._quick_scales[x] == selected_modus:
									button.turn_on()
								else:
									button.turn_off()
								
							else:
								button.set_light("DefaultButton.Disabled")
							
						for x in range(8):
							button = self._matrix.get_button(x, 1)
							button.set_enabled(True)
							if self._quick_scales[x + 7] != -1:
								button.set_on_off_values("QuickScale.Modus")
							else:
								button.set_on_off_values("DefaultButton.Disabled", "DefaultButton.Disabled")
							#button.force_next_send()
							if self._quick_scales[x + 7] == selected_modus:
								button.turn_on()
							else:
								button.turn_off()
					else: #NOTE REPEATER
						button = self._matrix.get_button(7, 0)
						button.set_light("QuickScale.Quant.Mode")
						
						
						for x in range(7):
							button = self._matrix.get_button(x, 0)
							button.set_enabled(True)
							
							if(x ==0):
								button.set_on_off_values("QuickScale.Quant.On", "QuickScale.Quant.Off")
								if(not self._swing_amount() ==0.0):
									button.turn_on()
								else:
									button.turn_off()
							elif(x ==1):
								button.set_on_off_values("QuickScale.Quant.On", "QuickScale.Quant.Off")
								if(self._swing_amount() < 0.98):
									button.turn_on()
								else:
									button.turn_off()	
								
							elif(x ==2):
								button.set_on_off_values("QuickScale.Quant.Straight", "DefaultButton.Disabled")
								button.turn_on()
							elif(x ==3):
								button.set_on_off_values("QuickScale.Quant.Swing", "DefaultButton.Disabled")
								button.turn_on()
							elif(x ==4):
								button.set_on_off_values("QuickScale.Quant.Dotted", "DefaultButton.Disabled")
								button.turn_on()
							elif(x ==5):
								button.set_on_off_values("QuickScale.Quant.Flam", "DefaultButton.Disabled")
								button.turn_on()								
							
							elif(x ==6):
								button.set_on_off_values("QuickScale.NoteRepeater.On", "QuickScale.NoteRepeater.Off")
								if(self._note_repeat.is_enabled()):
									button.turn_on()
								else:								
									button.turn_off()
							
						for x in range(8):
							button = self._matrix.get_button(x, 1)
							button.set_enabled(True)
							if(x%2==0):						
								button.set_on_off_values("QuickScale.Quant.Selected", "QuickScale.Quant.Note")
							else:
								button.set_on_off_values("QuickScale.Quant.Selected", "QuickScale.Quant.Tripplet")

							if (x) == self._note_repeat.freq_index():
								button.turn_on()
							else:
								button.turn_off()
					
				pattern = self._scales.get_pattern()
				max_j = self._matrix.width() - 1
				a = 0
				if self._scales.is_chromatic:
					a= 63
				for button, (i, j) in self._matrix.iterbuttons():
					if button and (not self._scales.is_quick_scale or j > 1):
						a = a +1
						note_info = pattern.note(i, max_j - j)
						button.set_enabled(False) # Assume it's a note button unless proven otherwise
						button.set_channel(non_feedback_channel) # Default channel

						if note_info.index != None:
							button.set_channel(note_channel[note_info.index])
							button.set_identifier(note_info.index)
							if(note_channel[note_info.index]<15):
								note_channel[note_info.index] = note_channel[note_info.index] + 1

							if note_info.root:
								# Use track color for root notes if available
								if track_pad_color_int is not None:
									button.send_value(track_pad_color_int)
								else:
									button.set_light(root_skin_key)
							elif note_info.highlight:
								button.set_light(highlight_color)
							elif note_info.in_scale:
								# Use a lighter version of track color for in-scale notes if available
								if track_pad_color_int is not None:
									# Get a brighter variant of the track color
									# This is a simplified approach - you might want to define specific 
									# highlight colors for each track color in your color tables
									button.set_light(in_scale_color) # Use skin for now
								else:
									button.set_light(in_scale_color)
							elif note_info.valid: # valid but out_of_scale
								button.set_light(out_of_scale_color)
							else: # Not valid (should be covered by else below, but safety)
								button.set_light(invalid_color)
								button.set_enabled(True) # Non-note button
								button.set_channel(non_feedback_channel)
								button.set_identifier(a)
						else:
							# This button does not correspond to a valid note index
							button.set_channel(non_feedback_channel)
							button.set_identifier(a)
							button.set_light(invalid_color)
							button.set_enabled(True) # Treat as disabled/non-note button

						#button.force_next_send() # force_next_send might interfere with send_value color

			for button in self._side_buttons:
				button.use_default_message()
				button.set_channel(non_feedback_channel)
				button.set_enabled(True)
				button.force_next_send()

	def _getLightForNote(self, note):
		# Get track color if available
		track_pad_color_int = self._track_pad_color_int
		
		# If we have a valid track color, use it directly
		if track_pad_color_int is not None:
			return track_pad_color_int
		
		# Fall back to skin colors if no track color is available
		if (note<4):
			return "DrumGroup.PadFilled1"
		elif (note<20):
			return "DrumGroup.PadFilled2"
		elif (note<36):
			return "DrumGroup.PadFilled3"
		elif (note<52):
			return "DrumGroup.PadFilled4"
		elif (note<68):
			return "DrumGroup.PadFilled5"
		elif (note<84):
			return "DrumGroup.PadFilled1"
		elif (note<100):
			return "DrumGroup.PadFilled2"        
		elif (note<116):
			return "DrumGroup.PadFilled3"            
		else: 
			return "DrumGroup.PadFilled4"

	def tuple_idx(self, target_tuple, obj):
		for i in xrange(0, len(target_tuple)):
			if (target_tuple[i] == obj):
				return i
		return(False)
