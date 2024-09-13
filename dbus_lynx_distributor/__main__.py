#!/usr/bin/env python3

from gi.repository import GLib
import logging
from configparser import ConfigParser
from argparse import ArgumentParser
import _thread
from pathlib import Path
from dbus import SystemBus

from settingsdevice import SettingsDevice
from .ftdi import Ftdi
from .dbus_lynx_distributor_service import DbusLynxDistributorService

class Application:
    def _parse_args(self):
        from . import __version__

        parser = ArgumentParser()

        parser.add_argument("-c", "--config", help="Specify config file", metavar="FILE", required=True, type=Path)
        parser.add_argument("-v", "--verbose", help="Increases log verbosity for each occurence", dest="verbose_count", action="count", default=0)
        parser.add_argument("--version", action="version", version=__version__)

        self._args = parser.parse_args()

        logging.basicConfig(format="%(asctime)s %(levelname)-7s %(name)-10s %(message)s", level=max(3 - self._args.verbose_count, 0) * 10)

    def _read_config(self):
        self._config = ConfigParser()
        self._config.read(self._args.config)

    @staticmethod
    def _get_class_and_vrm_instance(*, serial_number: str, service: str):
        settings = SettingsDevice(
            bus=SystemBus(),
            supportedSettings={'ClassAndVrmInstance': [f'/Settings/Devices/dbus_lynx_distributor_{serial_number}/ClassAndVrmInstance', f'{service}:1', 0, 0],},
            eventCallback=None,
            timeout=10)

        return settings['ClassAndVrmInstance'].split(':', 2)

    def run(self):
        self._parse_args()
        self._read_config()

        _thread.daemon = True  # allow the program to quit

        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)

        pid = int(self._config.get(section='general', option='vid', fallback='0x0403'), 0)
        vid = int(self._config.get(section='general', option='pid', fallback='0xD4F8'), 0)

        ftdis = Ftdi.scan(pid=pid, vid=vid)

        if len(ftdis) == 0:
            logging.warning("No devices found.")
            return

        for ftdi in ftdis:
            logging.info(f"Device with serial number {ftdi.serial_number} found.")

            service, device_instance = self._get_class_and_vrm_instance(serial_number=ftdi.serial_number, service='battery')
            service_name = f'com.victronenergy.{service}.dbus_lynx_distributor_{ftdi.serial_number}'

            DbusLynxDistributorService(
                service_name=service_name,
                device_instance=device_instance,
                ftdi=ftdi,
                config=self._config
                )

        mainloop = GLib.MainLoop()
        mainloop.run()

if __name__ == "__main__":
    Application().run()
