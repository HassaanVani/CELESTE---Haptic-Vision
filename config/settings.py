# Hardware
I2C_BUS = 1
PCA9685_ADDRESSES = [0x40, 0x41]
PCA9685_FREQUENCY = 1000  # 1kHz PWM — above audible coil whine for ERM motors

# Grid
GRID_COLS = 8  # around arm circumference
GRID_ROWS = 4  # along forearm length

# Camera
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
GAUSSIAN_KERNEL = (5, 5)
GAUSSIAN_SIGMA = 0  # auto-compute from kernel

# Processing
FRAME_QUEUE_SIZE = 2   # small queue = low latency, drop-oldest discipline
PWM_QUEUE_SIZE = 2
MIN_DUTY_CYCLE = 0
MAX_DUTY_CYCLE = 4095  # 12-bit max
BRIGHTNESS_FLOOR = 20  # ignore sensor noise below this
BRIGHTNESS_CEIL = 240  # clamp saturation above this
GAMMA = 1.5            # >1 emphasizes dim-to-mid range for better obstacle perception

# Timing
TARGET_LOOP_HZ = 20     # haptic update rate target
SHUTDOWN_TIMEOUT = 3.0   # seconds to wait for threads on exit
