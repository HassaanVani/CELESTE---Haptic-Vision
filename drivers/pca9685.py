import board
import busio
from adafruit_pca9685 import PCA9685
from config.settings import PCA9685_ADDRESSES, PCA9685_FREQUENCY


class PCA9685Driver:
    """Manages two daisy-chained PCA9685 boards over I2C."""

    def __init__(self):
        self._i2c = None
        self._boards: dict[int, PCA9685] = {}

    def init(self):
        """Initialize I2C bus and both PCA9685 boards."""
        self._i2c = busio.I2C(board.SCL, board.SDA)
        for addr in PCA9685_ADDRESSES:
            pca = PCA9685(self._i2c, address=addr)
            pca.frequency = PCA9685_FREQUENCY
            self._boards[addr] = pca

    def set_duty_cycle(self, addr: int, channel: int, value: int):
        """Set PWM duty cycle on a specific board/channel.

        Args:
            addr: I2C address (0x40 or 0x41)
            channel: PWM channel (0-15)
            value: 12-bit duty cycle (0-4095)
        """
        # adafruit library uses 16-bit duty_cycle (0-65535)
        value_16bit = min(65535, value * 16)
        self._boards[addr].channels[channel].duty_cycle = value_16bit

    def all_off(self):
        """Turn all channels off on all boards."""
        for pca in self._boards.values():
            for i in range(16):
                pca.channels[i].duty_cycle = 0

    def shutdown(self):
        """Gracefully shut down: all motors off, deinit I2C."""
        self.all_off()
        for pca in self._boards.values():
            pca.deinit()
        if self._i2c:
            self._i2c.deinit()
