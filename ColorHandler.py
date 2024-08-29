from .ColorsMK2 import translate_color_index, Rgb, RGB_COLOR_TABLE, Color

class ColorHandler:
    @staticmethod
    def get_track_color(track):
        if track:
            return translate_color_index(track.color_index)
        return Rgb.WHITE.midi_value  # Default color if no track is selected

    @staticmethod
    def get_rgb_color(color_index):
        translated_index = translate_color_index(color_index)
        
        # Find the corresponding RGB value in the RGB_COLOR_TABLE
        for index, rgb_value in RGB_COLOR_TABLE:
            if index == translated_index:
                return rgb_value
        
        # If no matching index is found, return white as a default
        return 16777215  # RGB value for white (255, 255, 255)

    @staticmethod
    def get_color_object(color_index):
        rgb_value = ColorHandler.get_rgb_color(color_index)
        return Color(rgb_value)

    @staticmethod
    def get_skin_color(color_index):
        # Convert the color index to a Color object
        color_object = ColorHandler.get_color_object(color_index)
        # Return the midi_value of the Color object
        return color_object.midi_value