from dialog import Dialog
import locale

from core import ConfigurationManager
from core import OrderListener
from neurons import Say


class ShellGui:
    def __init__(self):
        # get settings
        self.conf = ConfigurationManager().get_settings()
        locale.setlocale(locale.LC_ALL, '')

        self.d = Dialog(dialog="dialog")

        self.d.set_background_title("Jarvis shell UI")

        self.show_main_menu()

    def show_main_menu(self):
        """
        Main menu of the shell UI.
        Provide a list of action the user can select to test his settings
        :return:
        """

        code, tag = self.d.menu("Test your JARVIS settings from this menu",
                                choices=[("TTS", "Text to Speech"),
                                         ("STT", "Speech to text")])

        if code == self.d.OK:
            if tag == "STT":
                self.show_stt_test_menu()
            if tag == "TTS":
                self.show_tts_test_menu()

    def show_stt_test_menu(self):
        # we get STT from settings
        stt_list = ConfigurationManager.get_stt_list()
        print stt_list
        choices = self._get_choices_tuple_from_list(stt_list)

        code, tag = self.d.menu("Select the STT to test:",
                                choices=choices)

        if code == self.d.CANCEL:
            self.show_main_menu()

        if code == self.d.OK:
            print tag
            self.d.infobox("Please talk now")
            order_listener = OrderListener(callback=self.callback_stt, stt=str(tag))
            order_listener.load_stt_plugin()

    def show_tts_test_menu(self, sentence_to_test=None):
        """
         A menu for testing text to speech
        :return:
        """
        continue_bool = True
        # if we don't have yet a sentence to test, we ask the user to type one
        if sentence_to_test is None:
            # First, we ask the user to type a sentence that will be passed in the TTS
            code, sentence_to_test = self.d.inputbox("Please type the sentence you want to test", height=20, width=50)

            if code == self.d.CANCEL:
                self.show_main_menu()
                continue_bool = False
            if code == self.d.OK:
                continue_bool = True

        if continue_bool:
            # we get TTS from settings
            tts_list = ConfigurationManager.get_tts_list()

            # create a list of tuple that can be used by the dialog menu
            choices = self._get_choices_tuple_from_list(tts_list)

            code, tag = self.d.menu("Sentence to test: %s" % sentence_to_test,
                                    choices=choices)

            if code == self.d.CANCEL:
                self.show_tts_test_menu()
            if code == self.d.OK:
                self._run_tts_test(tag, sentence_to_test)
                # then go back to this menu with the same sentence
                self.show_tts_test_menu(sentence_to_test=sentence_to_test)

    def _run_tts_test(self, tag, sentence_to_test):
        """
        Call the TTS
        :param tag:
        :param sentence_to_test:
        :return:
        """
        Say(message=sentence_to_test, tts=tag)

    @staticmethod
    def _get_choices_tuple_from_list(list_to_convert):
        """
        Return a list of tup that can be used in Dialog menu
        :param stt_list:
        :return:
        """
        # create a list of tuple that can be used by the dialog menu
        choices = list()
        for el in list_to_convert:
            try:
                for name, settings in el.iteritems():
                    print name
                    print settings
                    tup = (str(name), str(settings))
                    choices.append(tup)
            except AttributeError:
                # sometime there is no settings for the STT key
                tup = (str(el), str("No settings"))
                choices.append(tup)
        return choices

    def callback_stt(self, audio):
        """
        Callback function called after the STT has finish his job
        :param audio: Text from the translated audio
        """
        code = self.d.msgbox("The STT engine think you said:\n %s" % audio, width=50)

        if code == self.d.OK:
            self.show_stt_test_menu()