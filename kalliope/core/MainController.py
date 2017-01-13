import logging
import random

from flask import Flask
from transitions import Machine

from kalliope.core import Utils
from kalliope.core.ConfigurationManager import SettingLoader
from kalliope.core.OrderAnalyser import OrderAnalyser
from kalliope.core.OrderListener import OrderListener
from kalliope.core.Players import Mplayer
from kalliope.core.RestAPI.FlaskAPI import FlaskAPI
from kalliope.core.TriggerLauncher import TriggerLauncher
from kalliope.neurons.say.say import Say

logging.basicConfig()
logger = logging.getLogger("kalliope")


class StateMachine(object):

    states = ['init', 'trigger_started', 'ready_sound_played', 'wake_up_answer',
              'order_listener_started', 'order_analyser']

    def __init__(self, brain=None):
        self.brain = brain

        self.main_controller = MainController(brain=brain)
        # Initialize the state machine
        self.machine = Machine(model=self.main_controller, states=StateMachine.states, initial='init')

        # define transitions
        self.machine.add_transition('start_trigger', 'init', 'trigger_started')
        self.machine.add_transition('play_ready_sound', 'trigger_init', 'ready_sound_played')
        self.machine.add_transition('start_order_listener', 'ready_sound_played', 'order_listener_started')
        self.machine.add_transition('play_wake_up_answer', 'order_listener_started', 'wake_up_answer')

        # add callbacks
        self.machine.on_enter_trigger_started('start_trigger_thread')

        self.main_controller.start_trigger()


class MainController:
    """
    This Class is the global controller of the application.
    """

    def __init__(self, brain=None):
        self.brain = brain
        # get global configuration
        sl = SettingLoader()
        self.settings = sl.settings

        # save an instance of the trigger
        self.trigger_instance = None

        # save the current order listener
        self.order_listener = None

        # Starting the rest API
        self._start_rest_api()

    def start_trigger_thread(self):
        print "here"
        self.trigger_instance = self._get_default_trigger()
        # Wait that the kalliope trigger is pronounced by the user
        self.trigger_instance.start()
        print "here"
        Utils.print_info("Waiting for trigger detection")
        # self.machine.play_ready_sound()

    def play_ready_sound(self):
        """
        Play a sound when Kalliope is ready to be awaken
        """
        # here we tell the user that we are listening
        if self.settings.random_on_ready_answers is not None:
            Say(message=self.settings.random_on_ready_answers)
        elif self.settings.random_on_ready_sounds is not None:
            random_sound_to_play = self._get_random_sound(self.settings.random_on_ready_sounds)
            Mplayer.play(random_sound_to_play)

    def trigger_callback(self):
        """
        we have detected the hotword, we can now pause the Trigger for a while
        The user can speak out loud his order during this time.
        """
        self.machine.start_order_listener()

    def start_order_listener(self):
        # pause the trigger process
        self.trigger_instance.pause()
        # start listening for an order
        self.order_listener = OrderListener(callback=self.order_listener_callback)
        self.order_listener.start()
        self.machine.play_wake_up_answer()

    def play_wake_up_answer(self):
        # if random wake answer sentence are present, we play this
        if self.settings.random_wake_up_answers is not None:
            Say(message=self.settings.random_wake_up_answers)
        else:
            random_sound_to_play = self._get_random_sound(self.settings.random_wake_up_sounds)
            Mplayer.play(random_sound_to_play)

    def order_listener_callback(self, order):
        """
        Receive an order, try to retrieve it in the brain.yml to launch to attached plugins
        :param order: the sentence received
        :type order: str
        """
        print "order to process: %s" % order
        # self.order_listener.stt_instance.stop_listening()
        # if order is not None:   # maybe we have received a null audio from STT engine
        #     order_analyser = OrderAnalyser(order, brain=self.brain)
        #     order_analyser.start()
        #
        # # restart the trigger when the order analyser has finish his job
        # Utils.print_info("Waiting for trigger detection")
        # self.trigger_instance.unpause()
        # # create a new order listener that will wait for start
        # # self.order_listener = OrderListener(self.analyse_order)

    def _get_default_trigger(self):
        """
        Return an instance of the default trigger
        :return: Trigger
        """
        for trigger in self.settings.triggers:
            if trigger.name == self.settings.default_trigger_name:
                return TriggerLauncher.get_trigger(trigger, callback=self.trigger_callback)

    @staticmethod
    def _get_random_sound(random_wake_up_sounds):
        """
        Return a path of a sound to play
        If the path is absolute, test if file exist
        If the path is relative, we check if the file exist in the sound folder
        :param random_wake_up_sounds: List of wake_up sounds
        :return: path of a sound to play
        """
        # take first randomly a path
        random_path = random.choice(random_wake_up_sounds)
        logger.debug("Selected sound: %s" % random_path)
        return Utils.get_real_file_path(random_path)

    def _start_rest_api(self):
        # run the api if the user want it
        if self.settings.rest_api.active:
            Utils.print_info("Starting REST API Listening port: %s" % self.settings.rest_api.port)
            app = Flask(__name__)
            flask_api = FlaskAPI(app=app,
                                 port=self.settings.rest_api.port,
                                 brain=self.brain,
                                 allowed_cors_origin=self.settings.rest_api.allowed_cors_origin)
            flask_api.daemon = True
            flask_api.start()