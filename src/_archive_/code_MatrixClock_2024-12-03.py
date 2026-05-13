# SPDX-FileCopyrightText: 2020 John Park for Adafruit Industries
# SPDX-License-Identifier: MIT
## https://learn.adafruit.com/network-connected-metro-rgb-matrix-clock/code-the-matrix-clock
# Metro Matrix Clock
# Updated to run on MatrixPortal M4 with 64x32 RGB Matrix display

from os import getenv
import time
import board
import busio
import displayio
import terminalio
# from rtc import RTC

from digitalio import DigitalInOut, Pull
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_requests
import adafruit_connection_manager

from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_debouncer import Debouncer
from adafruit_display_text.label import Label
# import adafruit_imageload
from adafruit_bitmap_font import bitmap_font
from adafruit_matrixportal.matrix import Matrix
# from adafruit_matrixportal.network import Network
# from adafruit_ntp import NTP

from datetime_util import cettime


print("*****************************")
print("**** Metro Minimal Clock ****")
print("*****************************")

##==============================================================================
## Settings & Secrets
##==============================================================================

## Read credentials and more from a settings.toml file
settings = {
    "CIRCUITPY_WIFI_SSID": getenv("CIRCUITPY_WIFI_SSID"),
    "CIRCUITPY_WIFI_PASSWORD": getenv("CIRCUITPY_WIFI_PASSWORD"),
    "BLINK" : getenv("BLINK"),
    "TIMEZONE": getenv("TIMEZONE"),
    "NTP_INTERVAL": getenv("NTP_INTERVAL"),
    }
DEBUG = False
BLINK = True if settings["BLINK"] == "True" else False
NTP_INTERVAL = int(settings["NTP_INTERVAL"])
CIRCUITPY_WIFI_SSID = settings["CIRCUITPY_WIFI_SSID"]
CIRCUITPY_WIFI_PASSWORD = settings["CIRCUITPY_WIFI_PASSWORD"]

LEVEL = 1  # 0, 1, 2

##==============================================================================
## Network Setup
##==============================================================================

if LEVEL == 0:
    ## 1) https://learn.adafruit.com/adafruit-matrixportal-m4/internet-connect
    ## Board with pre-defined ESP32 Pins
    esp32_cs = DigitalInOut(board.ESP_CS)
    esp32_ready = DigitalInOut(board.ESP_BUSY)
    esp32_reset = DigitalInOut(board.ESP_RESET)

    ## Secondary (SCK1) SPI used to connect to WiFi board on Arduino Nano Connect RP2040
    if "SCK1" in dir(board):
        spi = busio.SPI(board.SCK1, board.MOSI1, board.MISO1)
    else:
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

    pool = adafruit_connection_manager.get_radio_socketpool(esp)
    ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
    requests = adafruit_requests.Session(pool, ssl_context)

    if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
        print("## ESP32 found and in idle mode")
    print("## Firmware vers.", esp.firmware_version)
    print("## MAC addr:", ":".join("%02X" % byte for byte in esp.MAC_address))

    ## Scan networks (=> slow !!!)
    # for ap in esp.scan_networks():
    #     print("\t%-23s RSSI: %d" % (ap.ssid, ap.rssi))

    print(">> Connecting...")
    while not esp.is_connected:
        try:
            esp.connect_AP(settings["CIRCUITPY_WIFI_SSID"], settings["CIRCUITPY_WIFI_PASSWORD"])
        except OSError as e:
            print("!! Could not connect, retrying: ", e)
            continue
    print("## Connected to", esp.ap_info.ssid, "\tRSSI:", esp.ap_info.rssi)

elif LEVEL == 1:
    ## 2) https://learn.adafruit.com/network-connected-metro-rgb-matrix-clock/code-the-matrix-clock
    ##
    # matrix = Matrix()
    # time.sleep(3)  # show the logo for a bit
    # network = Network(status_neopixel=board.NEOPIXEL, debug=True)

    # matrixportal = MatrixPortal(status_neopixel=board.NEOPIXEL, debug=True)
    # network = Network(debug=True)
    # network = Network(status_neopixel=board.NEOPIXEL, debug=True)
    # network = matrixportal.network
    pass


##==============================================================================
## NTP & RTC Setup
##==============================================================================

# if LEVEL == 0:
#     ntp = NTP(pool, tz_offset=0, cache_seconds=3600)
#     rtc = RTC()
# elif LEVEL == 1:
#     ntp = NTP(network, tz_offset=0, cache_seconds=3600)

##==============================================================================
## Display Setup
##==============================================================================

if LEVEL == 0:
    ## 1) https://learn.adafruit.com/rgb-led-matrices-matrix-panels-with-circuitpython/matrixportal
    rgb_pins = [
        board.MTX_R1,
        board.MTX_G1,
        board.MTX_B1,
        board.MTX_R2,
        board.MTX_G2,
        board.MTX_B2,
        ]
    addr_pins = [
        board.MTX_ADDRA,
        board.MTX_ADDRB,
        board.MTX_ADDRC,
        board.MTX_ADDRD,
        ]
    matrix = Matrix(
        width=64, height=32,
        alt_addr_pins=addr_pins,
        color_order='RGB',
        #rotation=180
        )
    display = matrix.display

    ## TODO: display a logo at startup
    ## https://learn.adafruit.com/moon-phase-clock-for-adafruit-matrixportal
    # image, palette = adafruit_imageload.load(
    #     "Python-logo_32x32.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette
    # )
    # tile_grid = displayio.TileGrid(image, pixel_shader=palette)
    # group = displayio.Group()
    # group.append(tile_grid)
    # display.show(group)

elif LEVEL == 1:
    ## 2) https://docs.circuitpython.org/projects/matrixportal/en/stable/

    # matrixportal = MatrixPortal(esp=network._wifi, debug=True)
    matrixportal = MatrixPortal(debug=True)
    ## Create a new label with the color and text selected
    matrixportal.add_text(
        text_font=terminalio.FONT,
        text_position=(0, (matrixportal.graphics.display.height // 2) - 1),
        scrolling=True,
    )
    SCROLL_DELAY = 0.03
    SCROLL_DELAY = 0.005

    contents = [
        { 'text': 'THIS IS RED',  'color': '#cf2727'},
        # { 'text': 'THIS IS BLUE', 'color': '#0846e4'},
    ]
    while True:
        for content in contents:
            matrixportal.set_text(content['text'])

            ## Set the text color
            matrixportal.set_text_color(content['color'])

            ## Scroll it
            matrixportal.scroll_text(SCROLL_DELAY)
        break

    display = matrixportal.graphics.display
    network = matrixportal.network
    # matrixportal.network.connect()
    print(1111111)

    # network.get_local_time(location=settings["TIMEZONE"])

##==============================================================================
## Button Setup
##==============================================================================

pin_down = DigitalInOut(board.BUTTON_DOWN)
pin_down.switch_to_input(pull=Pull.UP)
button_down = Debouncer(pin_down)
pin_up = DigitalInOut(board.BUTTON_UP)
pin_up.switch_to_input(pull=Pull.UP)
button_up = Debouncer(pin_up)

##==============================================================================
## Drawing Setup
##==============================================================================

group = displayio.Group()  # Create a Group
bitmap = displayio.Bitmap(64, 32, 2)  # Create a bitmap object,width, height, bit depth
color = displayio.Palette(4)  # Create a color palette
color[0] = 0x000000  # black background
color[1] = 0x400000  # red
color[2] = 0xCC4000  # amber
color[3] = 0x404000  # greenish

## Create a TileGrid using the Bitmap and Palette
tile_grid = displayio.TileGrid(bitmap, pixel_shader=color)
## Add the TileGrid to the Group
group.append(tile_grid)  #
display.root_group = group

## https://learn.adafruit.com/network-connected-metro-rgb-matrix-clock/custom-font
font_large = bitmap_font.load_font("IBMPlexMono-Medium-24_jep.bdf")
# font_small = terminalio.FONT
# font_small = bitmap_font.load_font("6x10.bdf")
font_small = bitmap_font.load_font("helvR10.bdf")

## Create labels for the display text
clock_label = Label(font_large)
sensor_label = Label(font_small)

## Place the labels
clock_label.y = display.height // 3
sensor_label.y = 26

## Add the labels to the group
group.append(clock_label)
group.append(sensor_label)

##==============================================================================
## SHT40 Temperature & Pressure Sensor
##==============================================================================

# i2c_bus = I2C(0, scl=Pin(22), sda=Pin(21))
## To use default I2C bus (most boards)
i2c_bus = board.I2C()  # uses board.SCL and board.SDA
# i2c_bus = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

while not i2c_bus.try_lock():
    pass
try:
    i2c_devices = i2c_bus.scan()
    print("\n## I2C device addresses found:")
    print([(device_address, hex(device_address)) for device_address in i2c_devices])
finally:
    i2c_bus.unlock()

sht40_sensor = i2c_devices[1]

sht40_modes = (
    ("SERIAL_NUMBER", 0x89, "Serial number", 0.01),
    ("NOHEAT_HIGHPRECISION", 0xFD, "No heater, high precision", 0.01),
    ("NOHEAT_MEDPRECISION", 0xF6, "No heater, med precision", 0.005),
    ("NOHEAT_LOWPRECISION", 0xE0, "No heater, low precision", 0.002),
    ("HIGHHEAT_1S", 0x39, "High heat, 1 second", 1.1),
    ("HIGHHEAT_100MS", 0x32, "High heat, 0.1 second", 0.11),
    ("MEDHEAT_1S", 0x2F, "Med heat, 1 second", 1.1),
    ("MEDHEAT_100MS", 0x24, "Med heat, 0.1 second", 0.11),
    ("LOWHEAT_1S", 0x1E, "Low heat, 1 second", 1.1),
    ("LOWHEAT_100MS", 0x15, "Low heat, 0.1 second", 0.11),
    )


##==============================================================================
def read_sensor():
    '''
    Read measurement data from Sensirion SHT40.

    Returns
    -------
    * t_degC : float
    * rh_pRH : float
    '''
    mode = sht40_modes[1]  # NOHEAT_HIGHPRECISION
    while not i2c_bus.try_lock():
        pass
    try:
        # print ("\n## Reading sensor data...")
        i2c_bus.writeto(sht40_sensor, bytearray([mode[1]]))
        time.sleep(mode[-1])
        rx_bytes = bytearray(6)
        i2c_bus.readfrom_into(sht40_sensor, rx_bytes)
        # print('>', rx_bytes, len(rx_bytes))
        t_ticks = rx_bytes[0] * 256 + rx_bytes[1]
        rh_ticks = rx_bytes[3] * 256 + rx_bytes[4]
        t_degC = -45 + 175 * t_ticks / 65535  # 2^16 - 1 = 65535
        rh_pRH = -6 + 125 * rh_ticks / 65535
        if (rh_pRH > 100):
            rh_pRH = 100
        if (rh_pRH < 0):
            rh_pRH = 0
        # print('> temperature:', t_degC)
        # print('> humidity:', rh_pRH)

        return t_degC, rh_pRH

    finally:
        i2c_bus.unlock()


##==============================================================================
def update_time(*, hours=None, minutes=None, show_colon=False):
    """
    Update the clock label with the current time."""
    # now = time.localtime()
    now = cettime(time.time())
    if hours is None:
        hours = now[3]
    if hours >= 20 or hours < 7:
        ## Evening hours to morning
        clock_label.color = color[1]
        sensor_label.color = color[1]
    else:
        ## Daylight hours
        clock_label.color = color[3]
        sensor_label.color = color[3]

    if minutes is None:
        minutes = now[4]

    seconds = now[5]

    if BLINK:
        colon = ":" if show_colon or seconds % 2 else " "
    else:
        colon = ":"

    time_str_display = "{:d}{}{:02d}".format(hours, colon, minutes)
    time_str_stdout = "{}:{:02d}".format(time_str_display, seconds)
    clock_label.text = time_str_display
    bbx, bby, bbwidth, bbh = clock_label.bounding_box

    ## Place the label
    clock_label.x = round(display.width / 2 - bbwidth / 2)  # centered
    clock_label.y = display.height // 3
    if DEBUG:
        print("## clock_label bounding box: {},{},{},{}".format(bbx, bby, bbwidth, bbh))
        print("## clock_label x: {} y: {}".format(clock_label.x, clock_label.y))

    ## Read temperature and humidity
    t_degC, rh_pRH = read_sensor()
    sensor_str = "{:.1f}°  {:.1f}%".format(t_degC, rh_pRH)
    sensor_label.text = sensor_str
    bbx, bby, bbwidth, bbh = sensor_label.bounding_box
    sensor_label.x = round(display.width / 2 - bbwidth / 2)  # centered
    sensor_label.y = 26
    if DEBUG:
        print("## sensor_label bounding box: {},{},{},{}".format(bbx, bby, bbwidth, bbh))
        print("## sensor_label x: {} y: {}".format(sensor_label.x, sensor_label.y))

    print("Tick: {} - {}".format(time_str_stdout, sensor_str))


##******************************************************************************
##******************************************************************************
last_check = None
update_time(show_colon=True)  # display whatever time is on the board
while True:
    if last_check is None or time.monotonic() > last_check + NTP_INTERVAL:
        print(">> Updating time via NTP...")
        try:
            update_time(show_colon=True)  # make sure a colon is displayed while updating
            ## 1)
            # # rtc.datetime = ntp.datetime
            ## 2)
            # network.get_local_time(location=settings["TIMEZONE"])
            last_check = time.monotonic()
        except RuntimeError as e:
            print("!! Some error occured, retrying! -", e)
    update_time()
    time.sleep(1)
