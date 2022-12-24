import atexit
import argparse
import os
import struct
import sys

from subprocess import call # use to call cmd line executables
from threading import Thread
from picovoice import Picovoice
from gpiozero import LED
from picovoice import Picovoice
from pvrecorder import PvRecorder
# this library controls the onboard LEDs
from apa102 import APA102

import pvporcupine
print(pvporcupine.KEYWORDS)

# Picovoice API Access Key
access_key = "cT62spZepr1dAYbJB3QyJhANDZ93/woxETeMA5xQ8y//DW2elHQXgg=="

# keyword_path is the absolute path to the Porcupine wake word engine keyword file (with .ppn extension)
keyword_path = "/home/admin/workspace/mandroid/picovoice_raspberry-pi.ppn"

# context_path is the absolute path to the Rhino Speech-to-Intent engine context file (with .rhn extension)
# context_path = "/home/admin/workspace/mandroid/respeaker_raspberry-pi.rhn"
context_path = "/home/admin/workspace/mandroid/mandroid1_en_raspberry-pi_v2_1_0.rhn"

device_index = 2

espeak_cmd_prefix= 'espeak -v english-north -p 0 -m '
espeak_cmd_postfix= ' 2>/dev/null' # To dump the std errors to /dev/null


COLORS_RGB = dict(
    blue=(0, 0, 255),
    green=(0, 255, 0),
    orange=(255, 128, 0),
    pink=(255, 51, 153),
    purple=(128, 0, 128),
    red=(255, 0, 0),
    white=(255, 255, 255),
    yellow=(255, 255, 51),
)

driver = APA102(num_led=12)
power = LED(5)
power.on()

# class to implement picovoice functionality
class Mandroid(Thread):
    def __init__(
            self,
            porcupine_sensitivity=0.75,
            rhino_sensitivity=0.25):
        super(Mandroid, self).__init__()

        def inference_callback(inference):
            return self._inference_callback(inference)

        self._picovoice = Picovoice(
            access_key=access_key,
            keyword_path=keyword_path,
            wake_word_callback=self._wake_word_callback,
            context_path=context_path,
            inference_callback=inference_callback,
            porcupine_sensitivity=porcupine_sensitivity,
            rhino_sensitivity=rhino_sensitivity)
        
        #handle = Picovoice(
        #access_key=access_key,
        #keyword_path=keyword_path,
        #wake_word_callback=wake_word_callback,
        #context_path=context_path,
        #inference_callback=inference_callback)

        self._context = self._picovoice.context_info

        self._color = 'blue'
        self._device_index = device_index

    @staticmethod
    def _set_color(color):
        for i in range(12):
            driver.set_pixel(i, color[0], color[1], color[2])
        driver.show()

    @staticmethod
    def _wake_word_callback():
        print('[wake word]\n')
        
    def _speak(self, utterance):
        self.pause()
        call([espeak_cmd_prefix + '\'' + utterance + '\'' + espeak_cmd_postfix], shell=True)
        self.play()

    def _inference_callback(self, inference):
        print('{')
        print("  is_understood : '%s'," % ('true' if inference.is_understood else 'false'))
        if inference.is_understood:
            print("  intent : '%s'," % inference.intent)
            if len(inference.slots) > 0:
                print('  slots : {')
                for slot, value in inference.slots.items():
                    print("    '%s' : '%s'," % (slot, value))
                print('  }')
        print('}\n')

        if inference.is_understood:
            if inference.intent == 'changeLightState':
                if inference.slots['state'] == 'off':
                    self._set_color((0, 0, 0))
                else:
                    self._set_color(COLORS_RGB[self._color])
            elif inference.intent == 'changeLightStateOff':
                self._set_color((0, 0, 0))
            elif inference.intent == 'changeColor':
                self._color = inference.slots['color']
                self._set_color(COLORS_RGB[self._color])
            elif inference.intent == 'greeting':
                utterance = 'Hello Master'
                self._speak(utterance)
            elif inference.intent == 'speech':
                utterance = 'speech place holder'
                self._speak(utterance)    
            elif inference.intent == 'complain':    
                utterance = 'complain place holder'
                self._speak(utterance)    
            else:
                raise NotImplementedError()
    
    def pause(self):
        self.recording = False

    def play(self):
        self.recording = True
        recorder = None

        try:
            recorder = PvRecorder(device_index=self._device_index, frame_length=self._picovoice.frame_length)
            recorder.start()

            print(self._context)

            print('[Listening ...]')

            while self.recording:
                pcm = recorder.read()
                self._picovoice.process(pcm)
        except KeyboardInterrupt:
            sys.stdout.write('\b' * 2)
            print('Stopping ...')
        finally:
            if recorder is not None:
                recorder.delete()

            self._picovoice.delete()



# main
def main():
    parser = argparse.ArgumentParser()

    #parser.add_argument(
    #    '--access_key',
    #    help='AccessKey obtained from Picovoice Console (https://console.picovoice.ai/)',
    #    required=True)

    #parser.add_argument('--audio_device_index', help='Index of input audio device.', type=int, default=-1)

    args = parser.parse_args()

    o = Mandroid()
        #os.path.join(os.path.dirname(__file__), 'picovoice_raspberry-pi.ppn'),
        #os.path.join(os.path.dirname(__file__), 'respeaker_raspberry-pi.rhn'),
        #args.access_key,
        #args.audio_device_index
    #)
    o.play()




#def cleanup():
#    print("atexit: releasing resources...")
#    handle.delete()

#atexit.register(cleanup)

if __name__ == '__main__':
    main()

