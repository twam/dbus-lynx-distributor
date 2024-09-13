from time import time
import usb


class Ftdi:
    """
        Very basic class to control FTDI Chips in MPSSE mode

        Sources:
            [1] https://krinkinmu.github.io/2020/09/05/ftdi-protocol.html
            [2] https://www.ftdichip.com/Support/Documents/AppNotes/AN_255_USB%20to%20I2C%20Example%20using%20the%20FT232H%20and%20FT201X%20devices.pdf
            [3] https://www.ftdichip.com/Support/Documents/AppNotes/AN_108_Command_Processor_for_MPSSE_and_MCU_Host_Bus_Emulation_Modes.pdf
    """

    @classmethod
    def scan(cls, vid: int = 0x0403, pid: int = 0xD4F8):
        """ Scans for USB devices and returns an Ftdi object for each one """
        return [cls(dev) for dev in usb.core.find(find_all=True, idVendor=vid, idProduct=pid)]

    def __init__(self, dev):
        self._dev = dev

    def _write(self, data):
        self._dev.write(0x02, data)

    def _read(self, length: int, timeout=0.1):
        ret = []

        start = time()

        while (len(ret) < length) and (time() < start + timeout):
            data = self._dev.read(0x81, length-len(ret)+2)
            if len(data) > 2:
                ret += data[2:]

        return ret

    @property
    def serial_number(self):
        return self._dev.serial_number

    def reset(self):
        """ Resets device, see [1] """
        self._dev.ctrl_transfer(bmRequestType=0x40, bRequest = 0x00, wValue = 0x0000, wIndex = 0x0000)
        self._dev.ctrl_transfer(bmRequestType=0x40, bRequest = 0x00, wValue = 0x0001, wIndex = 0x0000) # Purge RX?
        self._dev.ctrl_transfer(bmRequestType=0x40, bRequest = 0x00, wValue = 0x0002, wIndex = 0x0000) # Purge TX?

    def disable_special_characters(self):
        """ Disable special characters, see [1]"""
        self._dev.ctrl_transfer(bmRequestType=0x40, bRequest = 0x06, wValue = 0x0000, wIndex = 0x0000)
        self._dev.ctrl_transfer(bmRequestType=0x40, bRequest = 0x07, wValue = 0x0000, wIndex = 0x0000)

    def set_bit_mode(self, mpsse: bool = True):
        """ Set bit mode, see [1]"""
        self._dev.ctrl_transfer(bmRequestType=0x40, bRequest = 0x0b, wValue = 0x0200 if mpsse else 0x0000, wIndex = 0x0000)

    def init_i2c(self, clockDivisor: int = 0xC8):
        data = bytes([
            0x8A, # Disable clock divide-by-5 for 60Mhz master clock
            0x97, # Ensure adaptive clocking is off
            0x8C, # Enable 3 phase data clocking, data valid on both clock edges for I2C
            0x9E, # Enable drive-zero mode on the lines used for I2C ...
            0x07, # ... on the bits AD0, 1 and 2 of the lower port...
            0x00, # ...not required on the upper port AC 0-7
            0x85,  # Ensure internal loopback is off
            ])
        self._write(data)

        data = bytes([
            0x86, # Command to set clock divisor
            clockDivisor & 0xFF, # Set 0xValueL of clock divisor
            (clockDivisor >> 8) & 0xFF, # Set 0xValueH of clock divisor
            ])
        self._write(data)

    def set_i2c_lines_idle(self):
        data = bytes([
            # Set the idle states for the AD lines
            0x80, # Command to set ADbus direction and data
            0xFF, # Set all 8 lines to high level
            0xFB, # Set all pins as o/p except bit 2 (data_in)
            # IDLE line states are ...
            # AD0 (SCL) is output high (open drain, pulled up externally)
            # AD1 (DATA OUT) is output high (open drain, pulled up externally)
            # AD2 (DATA IN) is input (therefore the output value specified is ignored)
            # AD3 to AD7 are inputs (not used in this application)
            # Set the idle states for the AC lines
            0x82, # Command to set ACbus direction and data
            0xFF, # Set all 8 lines to high level
            0x40, # Only bit 6 is output
            ])
        self._write(data)

    def set_i2c_start(self):
        data = bytes(
            [
            0x80, # Command to set ADbus direction/ data
            0xFD, # Bring data out low (bit 1)
            0xFB, # Set pins o/p except bit 2 (data_in)
            ] * 4 + # Repeat commands to ensure the minimum period of the start hold time is achieved
            [
            0x80, # Command to set ADbus direction/ data
            0xFC, # Bring clock line low too
            0xFB, # Set pins o/p except bit 2 (data_in)
            ] * 4) # Repeat commands to ensure the minimum period
        self._write(data)

    def set_i2c_stop(self):
        data = bytes(
            # Initial condition for the I2C Stop - Pull data low (Clock will already be low and is kept low)
            [
            0x80, # Command to set ADbus direction/data
            0xFC, # put data and clock low
            0xFB, # Set pins o/p except bit 2 (data_in)
            ] * 4 + # Repeat commands to ensure the minimum period of the stop setup time is achieved
            # Clock now goes high (open drain)
            [
            0x80, #Command to set ADbus direction/data
            0xFD, #put data low, clock remains high
            0xFB, #Set pins o/p except bit 2 (data_in)
            ] * 4 + # Repeat commands to ensure the minimum period of the stop setup time is achieved
            # Data now goes high too (both clock and data now high / open drain)
            [
            0x80, # Command to set ADbus direction/data
            0xFF, # both clock and data now high
            0xFB, # Set pins o/p except bit 2 (data_in)
            ] * 4) # Repeat commands to ensure the minimum period of the stop hold time is achieved
        self._write(data)

    def read_byte_and_send_nak(self):
        data = bytes([
            0x20, # Command: clock data byte in on clk rising edge
            0x00, # Length
            0x00, # Length 0x0000 means clock ONE byte in
            # Now clock out one bit (ACK/NAK). This bit has value '1' to send a NAK to the I2C Slave
            0x13, # Command: clock data bits out on clk falling edge
            0x00, # Length of 0x00 means clock out ONE bit
            0xFF, # Command will send bit 7 of this byte (= ‘1’)
            # Put I2C line back to idle (during transfer) state... Clock line low, Data line high
            0x80, #Command to set ADbus direction/ data
            0xFE, #Set the value of the pins
            0xFB, #Set pins o/p except bit 2 (data_in)
            # AD0 (SCL) is output driven low
            # AD1 (DATA OUT) is output high (open drain)
            # AD2 (DATA IN) is input (therefore the output value specified is ignored)
            # AD3 to AD7 are inputs driven high (not used in this application)
            # This command then tells the MPSSE to send any results gathered back immediately
            0x87, # Send answer back immediate command
            ])
        self._write(data)

        data_read = self._read(1)

        if len(data_read) == 0:
            return None

        return data_read[0]

    def send_addr_and_check_ack(self, address: int, read: bool = True):
        data = bytes([
            0x11, # command: clock bytes out MSB first on clock falling edge
            0x00, #
            0x00, # Data length of 0x0000 means clock out 1 byte
            address << 1 | (0x01 if read else 0x00), # Actual byte to clock out
            # Put I2C line back to idle (during transfer) state... Clock line low, Data line high
            0x80, # Command to set ADbus direction/ data
            0xFE, # Set the value of the pins
            0xFB, # Set pins o/p except bit 2 (data_in)
            # AD0 (SCL) is output driven low
            # AD1 (DATA OUT) is output high (open drain)
            # AD2 (DATA IN) is input (therefore the output value specified is ignored)
            # AD3 to AD7 are inputs driven high (not used in this application)
            0x22, # Command to clock in bits MSB first on rising edge
            0x00, # Length of 0x00 means to scan in 1 bit
            # This command then tells the MPSSE to send any results gathered back immediately
            0x87, # Send answer back immediate command
            ])
        self._write(data)

        data_read = self._read(1)

        if len(data_read) == 0:
            return False

        ack = (data_read[0] & 0x01) == 0x00
        return ack