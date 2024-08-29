import os
from .Settings import Settings
import sys

USER_HOME = os.path.expanduser('~')
LOG_DIRECTORY = USER_HOME + "/Documents/Ableton/User Library/Remote Scripts"
LOG_FILE = LOG_DIRECTORY + "/log.txt"

if Settings.LOGGING:
    try:
        os.makedirs(LOG_DIRECTORY, exist_ok=True)
    except TypeError:
        try:
            os.makedirs(LOG_DIRECTORY)
        except OSError:
            pass
            
    with open(LOG_FILE, 'a') as f:
        f.write('====================\n')

log_num = 0

def log(message):
    global log_num
    if Settings.LOGGING:
        formatted_message = f"{log_num} {message}"
        
        # Write to log file
        with open(LOG_FILE, 'a') as f:
            if isinstance(message, list):
                f.write('\n'.join([formatted_message] + message) + '\n')
            else:
                f.write(formatted_message + '\n')
        
        # Print to Python shell
        print(formatted_message)
        
        # If message is a list, print each item
        if isinstance(message, list):
            for item in message:
                print(item)
        
        log_num += 1