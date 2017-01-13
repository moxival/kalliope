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


class MainController:
    """
    This Class is the global controller of the application.
    """
    states = ['init',
              'starting_trigger',
              'unpausing_trigger',
              'playing_ready_sound',
              'waiting_for_trigger_callback',
              'start_order_listener',
              'playing_wake_up_answer',
              'waiting_for_order_listener_callback',
              'analysing_order']

    def __init__(self, brain=None):
        self.brain = brain
        # get global configuration
        sl = SettingLoader()
        self.settings = sl.settings

        # Starting the rest API
        self._start_rest_api()

        # save an instance of the trigger
        self.trigger_instance = None

        # save the current order listener
        self.order_listener = None

        # Initialize the state machine
        self.machine = Machine(model=self, states=MainController.states, initial='init')

        # define transitions
        self.machine.add_transition('start_trigger', 'init', 'starting_trigger')
        self.machine.add_transition('unpause_trigger', ['starting_trigger', 'analysing_order'], 'unpausing_trigger')
        self.machine.add_transition('play_ready_sound', 'unpausing_trigger', 'playing_ready_sound')
        self.machine.add_transition('wait_trigger_callback', 'playing_ready_sound', 'waiting_for_trigger_callback')
        self.machine.add_transition('play_wake_up_answer', 'waiting_for_trigger_callback', 'playing_wake_up_answer')
        self.machine.add_transition('wait_for_order', 'playing_wake_up_answer', 'waiting_for_order_listener_callback')
        self.machine.add_transition('analyse_order', 'waiting_for_order_listener_callback', 'analysing_order')

        self.machine.add_ordered_transitions()

        # add callbacks
        self.machine.on_enter_starting_trigger('start_trigger_process')
        self.machine.on_enter_playing_ready_sound('play_ready_sound_process')
        self.machine.on_enter_waiting_for_trigger_callback('waiting_for_trigger_callback_thread')
        self.machine.on_enter_playing_wake_up_answer('play_wake_up_answer_thread')
        self.machine.on_enter_start_order_listener('start_order_listener_thread')
        self.machine.on_enter_waiting_for_order_listener_callback('waiting_for_order_listener_callback_thread')
        self.machine.on_enter_analysing_order('analysing_order_thread')
        self.machine.on_enter_unpausing_trigger('unpausing_trigger_process')

        self.start_trigger()

    def start_trigger_process(self):
        print "Entering state: %s" % self.state
        self.trigger_instance = self._get_default_trigger()
        # self.trigger_instance.daemon = True
        # Wait that the kalliope trigger is pronounced by the user
        self.trigger_instance.start()
        Utils.print_info("Waiting for trigger detection")
        self.next_state()

    def unpausing_trigger_process(self):
        print "Entering state: %s" % self.state
        self.trigger_instance.unpause()
        self.next_state()

    def play_ready_sound_process(self):
        """
        Play a sound when Kalliope is ready to be awaken
        """
        print "Entering state: %s" % self.state
        # here we tell the user that we are listening
        if self.settings.random_on_ready_answers is not None:
            Say(message=self.settings.random_on_ready_answers)
        elif self.settings.random_on_ready_sounds is not None:
            random_sound_to_play = self._get_random_sound(self.settings.random_on_ready_sounds)
            Mplayer.play(random_sound_to_play)
        self.next_state()

    def waiting_for_trigger_callback_thread(self):
        print "Entering state: %s" % self.state

    def waiting_for_order_listener_callback_thread(self):
        print "Entering state: %s" % self.state

    def trigger_callback(self):
        """
        we have detected the hotword, we can now pause the Trigger for a while
        The user can speak out loud his order during this time.
        """
        print "Trigger callback called"
        self.next_state()

    def start_order_listener_thread(self):
        print "Entering state: %s" % self.state
        # pause the trigger process
        self.trigger_instance.pause()
        # start listening for an order
        self.order_listener = OrderListener(callback=self.order_listener_callback)
        self.order_listener.start()

        self.next_state()

    def play_wake_up_answer_thread(self):
        print "Entering state: %s" % self.state
        # if random wake answer sentence are present, we play this
        if self.settings.random_wake_up_answers is not None:
            Say(message=self.settings.random_wake_up_answers)
        else:
            random_sound_to_play = self._get_random_sound(self.settings.random_wake_up_sounds)
            Mplayer.play(random_sound_to_play)

        self.next_state()

    def order_listener_callback(self, order):
        """
        Receive an order, try to retrieve it in the brain.yml to launch to attached plugins
        :param order: the sentence received
        :type order: str
        """
        print "order to process: %s" % order
        self.next_state(order)

    def analysing_order_thread(self, order):
        print "order in analysing_order_thread %s" % order
        if order is not None:   # maybe we have received a null audio from STT engine
            order_analyser = OrderAnalyser(order, brain=self.brain)
            order_analyser.start()

        self.unpause_trigger()
        # # restart the trigger when the order analyser has finish his job
        # Utils.print_info("Waiting for trigger detection")
        # self.trigger_instance.unpause()
        # create a new order listener that will wait for start
        # self.order_listener = OrderListener(self.analyse_order)

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