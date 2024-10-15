from time import sleep
from gi.repository import GLib
from vedbus import VeDbusService
from dbus import SystemBus
from dataclasses import dataclass
from typing import Callable, Optional, Union, Type
from usb.core import USBError


@dataclass
class ServicePath:
    dbus_path: str
    dbus_gettextcallback: Optional[Callable[[str, Union[int, str, float]], bool]] = None
    dbus_initialvalue: Union[int, str, float] = None
    dbus_writeable: bool = False
    dbus_valuetype: Type = None
    config_key: Optional[str] = None
    config_invert_key: Optional[str] = None


class DbusLynxDistributorService:
    def __init__(
        self,
        *,
        service_name ,
        device_instance,
        ftdi,
        config,
        product_name = 'Lynx Distributor',
        custom_name = 'Lynx Distributor',
        connection='USB<->I2C',
    ):

        self._ftdi = ftdi
        self._config = config

        self._dbusservice = VeDbusService(servicename=service_name, bus=SystemBus(private=True), register=False)

        from . import __version__

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __name__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', __version__)
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/ProductName', product_name)
        self._dbusservice.add_path('/CustomName', self._config_get('name', custom_name))
        self._dbusservice.add_path('/DeviceInstance', device_instance)
        self._dbusservice.add_path('/ProductId', 0xFFFF)
        self._dbusservice.add_path('/Serial', self._ftdi.serial_number)
        self._dbusservice.add_path('/FirmwareVersion', '')
        self._dbusservice.add_path('/HardwareVersion', '')

        self._dbusservice.add_path('/Connected', 1)

        self._dbusservice.add_path('/NrOfDistributors', 4)

        for distributor in ['A', 'B', 'C', 'D']:
            self._dbusservice.add_path(f'/Distributor/{distributor}/Status', None) # <= 0=Not available, 1=Connected, 2=No bus power, 3=Communications Lost
            self._dbusservice.add_path(f'/Distributor/{distributor}/Alarms/ConnectionLost', None) # <= 0=Ok, 2=Alarm
            for fuse in range(4):
                self._dbusservice.add_path(f'/Distributor/{distributor}/Fuse/{fuse}/Name', self._config_get(f'distributor{distributor}Fuse{fuse}Name', None)) # <= UTF-8 string, limited to 16 bytes in firmware
                self._dbusservice.add_path(f'/Distributor/{distributor}/Fuse/{fuse}/Status', None) # <= 0=Not available, 1=Not used, 2=Ok, 3=Blown
                self._dbusservice.add_path(f'/Distributor/{distributor}/Fuse/{fuse}/Alarms/Blown', None)  # <= 0=Ok, 2=Alarm

        self._dbusservice.register()
        self._ftdi.init_i2c()

        self._update()
        GLib.timeout_add(1000, self._update)

    def __del__(self):
        print('Good Bye')

    def _config_get(self, option, fallback):
        return self._config.get(f'ftdi:{self._ftdi.serial_number}', option, fallback=fallback)

    def _config_getboolean(self, option, fallback):
        return self._config.getboolean(f'ftdi:{self._ftdi.serial_number}', option, fallback=fallback)

    def _update(self):
        sleep(1)
        try:
            for lynx in range(3, -1, -1):
                distributor = chr(ord('A') + lynx)
                address = 0x08 + lynx

                available = self._ftdi.send_addr_and_check_ack(address)

                if not available:
                    self._dbusservice[f'/Distributor/{distributor}/Status'] = 3 if self._config_getboolean(f'distributor{distributor}Installed', False) else 0
                    self._dbusservice[f'/Distributor/{distributor}/Alarms/ConnectionLost'] = 2 if self._config_getboolean(f'distributor{distributor}Installed', False) else 0
                else:
                    state = self._ftdi.read_byte_and_send_nak(address)

                    no_bus_power = (state & 0b00000010)

                    self._dbusservice[f'/Distributor/{distributor}/Status'] = 2 if no_bus_power else 1
                    self._dbusservice[f'/Distributor/{distributor}/Alarms/ConnectionLost'] = 0

                    for fuse in range(4):
                        fuse_installed = self._config_getboolean(f'distributor{distributor}Fuse{fuse}Installed', True)
                        fuse_blown = (state & (0b00010000 << fuse))

                        if fuse_installed is False:
                            self._dbusservice[f'/Distributor/{distributor}/Fuse/{fuse}/Status'] = 1
                            self._dbusservice[f'/Distributor/{distributor}/Fuse/{fuse}/Alarms/Blown'] = 0
                        else:
                            if no_bus_power:
                                self._dbusservice[f'/Distributor/{distributor}/Fuse/{fuse}/Status'] = 0
                                self._dbusservice[f'/Distributor/{distributor}/Fuse/{fuse}/Alarms/Blown'] = 0
                            else:
                                if fuse_blown:
                                    self._dbusservice[f'/Distributor/{distributor}/Fuse/{fuse}/Status'] = 3
                                    self._dbusservice[f'/Distributor/{distributor}/Fuse/{fuse}/Alarms/Blown'] = 2
                                else:
                                    self._dbusservice[f'/Distributor/{distributor}/Fuse/{fuse}/Status'] = 2
                                    self._dbusservice[f'/Distributor/{distributor}/Fuse/{fuse}/Alarms/Blown'] = 0

        except USBError:
            print("USB communication failed")
            return False

        return True
