from config.settings import PCA9685_ADDRESSES, GRID_COLS, GRID_ROWS


class ChannelMap:
    """Maps grid positions (row, col) to (i2c_address, pwm_channel).

    Board 0x40 Ch 0-7:   Row 0 (wrist),  Cols 0-7
    Board 0x40 Ch 8-15:  Row 1,           Cols 0-7
    Board 0x41 Ch 0-7:   Row 2,           Cols 0-7
    Board 0x41 Ch 8-15:  Row 3 (elbow),  Cols 0-7
    """

    def __init__(self):
        self._map = {}
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                board_idx = row // 2
                channel = (row % 2) * GRID_COLS + col
                addr = PCA9685_ADDRESSES[board_idx]
                self._map[(row, col)] = (addr, channel)

    def get(self, row: int, col: int) -> tuple[int, int]:
        """Returns (i2c_address, pwm_channel) for given grid position."""
        return self._map[(row, col)]

    def all_positions(self) -> list[tuple[int, int]]:
        """Returns all (row, col) positions in raster order."""
        return [(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)]
