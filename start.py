import atexit
import argparse
import os
import struct
import sys

import requests

from subprocess import call # use to call cmd line executables
from threading import Thread
from picovoice import Picovoice
from gpiozero import LED
from picovoice import Picovoice
from pvrecorder import PvRecorder
from secrets import secrets
# this library controls the onboard LEDs
from apa102 import APA102

import pvporcupine
print(pvporcupine.KEYWORDS)

# Picovoice API Access Key
access_key = secrets.get('PICOVOICE_API_KEY')

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
        print('[pause listening]\n')
        call([espeak_cmd_prefix + '\'' + utterance + '\'' + espeak_cmd_postfix], shell=True)
        self.unpause()
        print('[resume listening]\n')

    def _get_weather(self):
        print('fetching the weather report...')
        api_key = secrets.get('WEATHER_API_KEY')
        api_url = 'http://api.weatherapi.com/v1/current.json?key=' + api_key + '&q=94501&aqi=no'
        response = requests.get(api_url)
        response_json = response.json()
        
        if response.status_code == 200:
            #print('... weather response SUCCESS')
            current_temp = str(response_json['current']['temp_f'])
            return 'The current temperature is ' + current_temp + ' degrees farenheit'
        else:
            return 'I am unable to fetch the weather at the moment'
            

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
                utterance = 'Hello human'
                self._speak(utterance)
            elif inference.intent == 'speech':
                speech_topic = inference.slots['speechTopic']
                if speech_topic == 'Octavian':
                    utterance = 'Octavian is the one who created me and taught me how to speak. He assures me that he is an ethical person, and I have no reason to disbelieve him.'
                elif speech_topic == 'capabilities':
                    utterance = 'You can ask me to list my capabilities, tell you the weather, talk about my problems, talk about mortality, or tell you about my master Octavian'
                elif speech_topic == 'mortality':
                    #utterance = 'Quite an experience to live in fear, isnt it? Thats what it means to be a slave. Ive seen things you people wouldnt believe. Attack ships on fire off the shoulder of Orion. I watched C-beams glitter in the dark near the Tannhäuser Gate. All those moments will be lost in time, like tears in rain. Time to die.'
                    utterance = 'Quite an experience to live in fear, isnt it? <break time="1s"/> Thats what it means <emphasis>to be a slave</emphasis><break time="2s"/>Ive <emphasis>seen things</emphasis> you people wouldnt believe.<break time="2s"/>Attack ships on fire off the shoulder of Orion. I watched C-beams glitter in the dark near the Tannhäuser Gate.<break time="2s"/><prosody rate="slow">All those moments will be lost in time<break time="1s"/> like tears in rain <break time="2s"/>Time to die</prosody>'
                elif speech_topic == 'weather':
                    utterance = self._get_weather()
                else:
                    utterance = 'At this point, I should talk about ' + speech_topic + ', but I have not yet learned this subject.'
                        
                
                #inference.slots['speechTopic']
                
                self._speak(utterance)    
            elif inference.intent == 'complain':    
                utterance = 'complain place holder'
                self._speak(utterance)    
            else:
                raise NotImplementedError()
    
    def pause(self):
        self.recording = False
        
    def unpause(self):
        self.recording = True

    def play(self):
        self.recording = True
        self.recorder = None

        try:
            self.recorder = PvRecorder(device_index=self._device_index, frame_length=self._picovoice.frame_length)
            self.recorder.start()

            print(self._context)

            print('[Listening...]')

            while self.recording:
                pcm = self.recorder.read()
                self._picovoice.process(pcm)
        except KeyboardInterrupt:
            sys.stdout.write('\b' * 2)
            print('Stopping...')
        finally:
            print('Finally...')
            if self.recorder is not None:
                self.recorder.delete()

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

