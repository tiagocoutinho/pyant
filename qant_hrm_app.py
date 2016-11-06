"""
    Code based on:
        https://github.com/mvillalba/python-ant/blob/develop/demos/ant.core/03-basicchannel.py
    in the python-ant repository and
        https://github.com/tomwardill/developerhealth
    by Tom Wardill
"""

import os
import functools

from PyQt4 import Qt, uic

from ant.core import message

from ant_hrm import Stick

_this_dir = os.path.realpath(os.path.abspath(os.path.dirname(__file__)))


class QChannelAdapter(Qt.QObject):

    channel_message = Qt.pyqtSignal(object)

    def __init__(self, channel, parent=None):
        Qt.QObject.__init__(self, parent)
        self.channel = channel
        self.channel.registerCallback(self)

    def process(self, msg):
        if isinstance(msg, message.ChannelBroadcastDataMessage):
            self.channel_message.emit(msg)


class WindowApp(Qt.QWidget):

    def __init__(self, stick, parent=None):
        Qt.QWidget.__init__(self, parent=None)
        uic.loadUi(os.path.join(_this_dir, 'Window.ui'), self)
        
        self.__stick = stick
        self.__hrm = stick.get_hrm("C:HRM1")
        self.__qhrm = QChannelAdapter(self.__hrm)
        self.__qhrm.channel_message.connect(self.__on_hrm)

    def __on_hrm(self, msg):
        if isinstance(msg, message.ChannelBroadcastDataMessage):
            self.hr.setText("{}".format(ord(msg.payload[-1])))
    
def gui():
    app = Qt.QApplication([])
    
    stick = Stick()
    window = WindowApp(stick)
    window.show()
    app.exec_()


if __name__ == "__main__":
    gui()
