"""
    Code based on:
        https://github.com/mvillalba/python-ant/blob/develop/demos/ant.core/03-basicchannel.py
    in the python-ant repository and
        https://github.com/tomwardill/developerhealth
    by Tom Wardill
"""

import functools

from ant.core import driver, node, event, message, log
from ant.core.constants import CHANNEL_TYPE_TWOWAY_RECEIVE, TIMEOUT_NEVER

# USB stick vendor and product codes (valid for Suunto Movestick, ANSELF, ...)
idVendor = 0x0FCF
idProduct = 0x1008
DEFAULT_ADDR = '/dev/ttyUSB0'
ANT_PLUS_NET_KEY = 'B9A521FBBD72C345'.decode('hex')
ANT_FS_NET_KEY = 'A8A423B9F55E63C1'.decode('hex')
PUBLIC_NET_KEY = 'E8E4213B557A67C1'.decode('hex')

def sec_to_search_time(seconds):
    return int(round(seconds / 2.5))

HRM, BRPM, BSPD = 0x78, 0x7A, 0x7B

CHANNELS = {
    # Heart Rate Monitor (slave)
    HRM: dict(channel_type=CHANNEL_TYPE_TWOWAY_RECEIVE,
              network_key=ANT_PLUS_NET_KEY,
              rf_channel=57,
              transmission_type=0,       # 0 = pairing search
              device_type=0x78,          # = 120,
              device_number=0,           # 0 = search
              period=8070,               # counts (8070/32756s (~4.06 Hz))
              search_timeout=sec_to_search_time(30),
              periods=(8070, 2*8070, 4*8070),), # possible periods
    # Bike cadence meter (slave) 
    BRPM: dict(channel_type=CHANNEL_TYPE_TWOWAY_RECEIVE,
              network_key=ANT_PLUS_NET_KEY,
              rf_channel=57,
              transmission_type=0,       # 0 = pairing search
              device_type=0x7A,          # = 123,
              device_number=0,           # 0 = search
              period=8102,               # counts (8102/32768s  (~4.04Hz))
              search_timeout=sec_to_search_time(30),
              periods=(8102, 2*8102, 4*8102),), # possible periods
    # Bike SPeeD meter (slave) 
    BSPD: dict(channel_type=CHANNEL_TYPE_TWOWAY_RECEIVE,
              network_key=ANT_PLUS_NET_KEY,
              rf_channel=57,
              transmission_type=0,       # 0 = pairing search
              device_type=0x7B,          # = 123,
              device_number=0,           # 0 = search
              period=8118,               # counts (8118/32768s  (~4.04Hz))
              search_timeout=sec_to_search_time(30),
              periods=(8118, 2*8118, 4*8118),), # possible periods
}


def try_connect(f):
    functools.wraps(f)
    def wrapped(self, *args, **kwargs):
        self._initialize()
        return f(self, *args, **kwargs)
    return wrapped        


class Stick(object):

    DEFAULT_NET_NAME = 'N:ANT+'

    def __init__(self, driver=None):
        self.addr = DEFAULT_ADDR 
        self.netkey = ANT_PLUS_NET_KEY
        self.driver = driver
        self.node = None
        self.key = None
        self.channels = {}

    def _initialize(self):
        if self.driver is None:
            # actually doesn't matter what parameter we put since USB2
            # doesn't use /dev
            self.driver = driver.USB2Driver(DEFAULT_ADDR)
        if self.node is None:
            self.node = node.Node(self.driver)
            self.node.start()                
            self.key = node.NetworkKey(self.DEFAULT_NET_NAME, self.netkey)
            self.node.setNetworkKey(0, self.key)

    @try_connect
    def get_channel(self, name, device_type, device_number=0, 
                    transmission_type=0, channel_type=CHANNEL_TYPE_TWOWAY_RECEIVE,
                    period=8070, frequency=57, search_timeout=TIMEOUT_NEVER, **kwargs):
        if name in self.channels:
            return self.channels[name]   
        channel = self.node.getFreeChannel()
        channel.name = name
        channel.assign(self.DEFAULT_NET_NAME, channel_type)
        channel.setID(device_type, device_number, transmission_type)
        channel.setSearchTimeout(search_timeout)
        channel.setPeriod(period)
        channel.setFrequency(frequency)
        channel.open()
        self.channels[name] = channel
        return channel

    def get_device(self, name, device_type, **kwargs):
        config = dict(CHANNELS[device_type])
        config.update(kwargs)
        return self.get_channel(name, **config)

    def get_hrm(self, name, **kwargs):
        return self.get_device(name, HRM, **kwargs)

    def close_channel(self, ch):
        if isinstance(ch, (str, unicode)):
            ch = self.channels[ch]
        ch.close()
        ch.unassign()

    def stop(self):
        for channel in self.channels.values():
            self.close_channel(channel)
        self.channels = {}
        if self.node and self.node.running:
            self.node.stop()
            self.node = None

    def close(self):
        self.stop()
        if self.driver and self.driver.is_open:
            self.driver.close()
            self.driver = None

    def __del__(self):
        self.close()


class Hrm(event.EventCallback):

    def __init__(self, serial, netkey):
        self.serial = serial
        self.netkey = netkey
        self.antnode = None
        self.channel = None

    def start(self, cb=None):
        print("starting node")
        if cb is None:
            cb = self
        self._start_antnode()
        self._setup_channel()
        self.channel.registerCallback(cb)
        print("start listening for hr events")

    def stop(self):
        print("stopping...")
        if self.channel:
            self.channel.close()
            self.channel.unassign()
        if self.antnode:
            self.antnode.stop()
        print("stopped!")

    def __enter__(self):
        return self

    def __exit__(self, type_, value, traceback):
        self.stop()

    def _start_antnode(self):
        stick = driver.USB2Driver(self.serial)
        self.antnode = node.Node(stick)
        self.antnode.start()

    def _setup_channel(self):
        key = node.NetworkKey('N:ANT+', self.netkey)
        self.antnode.setNetworkKey(0, key)
        self.channel = self.antnode.getFreeChannel()
        self.channel.name = 'C:HRM'
        self.channel.assign('N:ANT+', CHANNEL_TYPE_TWOWAY_RECEIVE)
        self.channel.setID(120, 0, 0)
        self.channel.setSearchTimeout(TIMEOUT_NEVER)
        self.channel.setPeriod(8070)
        self.channel.setFrequency(57)
        self.channel.open()

    def process(self, msg):
        if isinstance(msg, message.ChannelBroadcastDataMessage):
            print("heart rate is {}".format(ord(msg.payload[-1])))

SERIAL = '/dev/ttyUSB0'
NETKEY = 'B9A521FBBD72C345'.decode('hex')

def console():
    import sys, time
    with Hrm(serial=SERIAL, netkey=NETKEY) as hrm:
        hrm.start()
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                sys.exit(0)

if __name__ == "__main__":
    console()
