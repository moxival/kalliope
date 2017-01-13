from threading import Thread
from time import sleep

import speech_recognition as sr

from kalliope import Utils


class SpeechRecognition(Thread):

    def __init__(self):
        super(SpeechRecognition, self).__init__()
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.callback = None
        self.stop_listening = None
        self.kill_yourself = False
        with self.microphone as source:
            # we only need to calibrate once, before we start listening
            self.recognizer.adjust_for_ambient_noise(source)

    def run(self):
        Utils.print_info("Say something!")
        self.stop_listening = self.recognizer.listen_in_background(self.microphone, self.callback)
        while not self.kill_yourself:
            sleep(0.5)
        print "I kill myself"
        self.stop_listening()

    def set_callback(self, callback):
        self.callback = callback