from pyftdi import FtdiLogger                                                             
from pyftdi.ftdi import Ftdi                                                              
from pyftdi.i2c import I2cController, I2cNackError                                        
from pyftdi.misc import add_custom_devices   
from pyftdi.ftdi import Ftdi as PyFtdi                                             
import logging
from time import time
import usb

class Ftdi:
    logging.getLogger('pyftdi').setLevel(logging.ERROR)
    
    @classmethod
    def scan(cls, vid: int = 0x0403, pid: int = 0xD4F8):
        """ Scans for USB devices and returns an Ftdi object for each one """
        return [cls(dev) for dev in usb.core.find(find_all=True, idVendor=vid, idProduct=pid)]

    def __init__(self, dev):
        self._dev = dev
        add_custom_devices(PyFtdi,[f'{dev.idVendor:04x}:{dev.idProduct:04x}'], force_hex=True)

    @property
    def serial_number(self):
        return self._dev.serial_number
    
    @property
    def pid(self):
        return f'0x{self._dev.idProduct:04x}'
        
    def init_i2c(self):
        i2c = I2cController()
        i2c.set_retry_count(1)
        #Address format: ('ftdi://ftdi:pid:serial/1')
        i2c.configure(f'ftdi://ftdi:{self.pid}:{self.serial_number}/1')
        self.i2c = i2c
       
    def read_byte_and_send_nak(self, address: int):
        try:
            port = self.i2c.get_port(address)
            data_read = port.read(1)
        except I2cNackError:
            return None
        if len(data_read) == 0:
            return None
        return data_read[0]

    def send_addr_and_check_ack(self, address: int, read: bool = True):
        port = self.i2c.get_port(address)
        try:
            port.write([])
            return True
        except I2cNackError:
            return False
        