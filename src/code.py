"""
MatrixClock - a HUB75 LED matrix clock driven by Adafruit's MaxtrixPortal M4.

* Synchronization with NTP.
* Temperature/humidity ambient sensor (Sensirion SHT40).

@author: mada
@version: 2026-05-06
"""

import os
import time
import asyncio
import microcontroller

## Network ---------------------------------------------------------------------
import board
import digitalio
import busio
from adafruit_esp32spi import adafruit_esp32spi

# import neopixel
# from adafruit_esp32spi import adafruit_esp32spi_wifimanager

import adafruit_connection_manager

## NTP & RTC -------------------------------------------------------------------
from rtc import RTC
from adafruit_ntp import NTP

## Display ---------------------------------------------------------------------
from adafruit_matrixportal.matrix import Matrix
from adafruit_display_text.label import Label
from adafruit_bitmap_font import bitmap_font
import adafruit_imageload
import displayio
import terminalio

## Clock -----------------------------------------------------------------------
import datetime_util

##******************************************************************************
##******************************************************************************

## DEBUG mode
DEBUG = False
# DEBUG = True
## Blinking colon
BLINK = True
## NTP sync interval
NTP_INTERVAL = 3600 * 12  # 3600s * 12 = 60min * 12 = 12h
NTP_INTERVAL = 3600  # 3600s = 60min = 1h
## NTP retry interval after failure
NTP_RETRY_INTERVAL = 300  # 5 minutes
## Last NTP sync
ts_lastntpsync = None
## Clock counter
if DEBUG:
    ## Start at 05:59:00 UTC = 06:59:00 CET ...
    ts_clocktick = 60 * 60 * 5 + 59 * 60
else:
    ## Start at 00:00:00 UTC
    ts_clocktick = time.time()

MAX_CONSECUTIVE_FAILURES = 3
consecutive_failures = 0

WIFI_CONNECT_TIMEOUT = 20
WIFI_RETRY_DELAY = 2
I2C_LOCK_TIMEOUT = 1.0
I2C_LOCK_RETRY_DELAY = 0.01
SENSOR_READ_INTERVAL = 10

last_sensor_read_monotonic = 0.0
last_sensor_reading = (None, None)

##******************************************************************************
##******************************************************************************


##==============================================================================
print("\n****************************")
print(  "**** Settings & Secrets ****")
print(  "****************************")

## Read credentials and more from a settings.toml file
settings = {
    "CIRCUITPY_WIFI_SSID": os.getenv("CIRCUITPY_WIFI_SSID"),
    "CIRCUITPY_WIFI_PASSWORD": os.getenv("CIRCUITPY_WIFI_PASSWORD"),
    # "TIMEZONE": getenv("TIMEZONE"),
    # "NTP_INTERVAL": getenv("NTP_INTERVAL"),
    }
CIRCUITPY_WIFI_SSID = settings["CIRCUITPY_WIFI_SSID"]
CIRCUITPY_WIFI_PASSWORD = settings["CIRCUITPY_WIFI_PASSWORD"]


##==============================================================================
print("\n***********************")
print(  "**** Network Setup ****")
print(  "***********************")

esp32_cs = digitalio.DigitalInOut(board.ESP_CS)
esp32_busy = digitalio.DigitalInOut(board.ESP_BUSY)
esp32_reset = digitalio.DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)

esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_busy, esp32_reset)

if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
    print("## ESP32 found and in idle mode")
print("## Firmware vers.", esp.firmware_version)
print("## MAC addr:", ":".join("%02X" % byte for byte in esp.MAC_address))
print("## IP addr:", esp.pretty_ip(esp.ip_address))

## Scan networks (=> slow !!!)
# for ap in esp.scan_networks():
#     print("\t%-23s RSSI: %d" % (ap.ssid, ap.rssi))

print(">> Connecting...")
while not esp.is_connected:
    connect_started = time.monotonic()
    while (not esp.is_connected) and (time.monotonic() - connect_started < WIFI_CONNECT_TIMEOUT):
        try:
            esp.connect_AP(CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD)
        except OSError as e:
            print("!! Could not connect, retrying:", e)
            time.sleep(WIFI_RETRY_DELAY)
    if not esp.is_connected:
        print("!! Wi-Fi connect timeout, resetting ESP and retrying...")
        esp.reset()
        time.sleep(1)
print("## Connected to", esp.ap_info.ssid, "\tRSSI:", esp.ap_info.rssi, "\tIP addr:", esp.pretty_ip(esp.ip_address))


##==============================================================================
print("\n*******************")
print(  "**** NTP & RTC ****")
print(  "*******************")

pool = adafruit_connection_manager.get_radio_socketpool(esp)
ntp = NTP(pool, tz_offset=0, cache_seconds=NTP_INTERVAL, server="pool.ntp.org")
print("## Current NTP time:", ntp.datetime)
rtc = RTC()
rtc.datetime = ntp.datetime
print("## Current RTC time:", rtc.datetime)


##------------------------------------------------------------------------------
async def sync_time_via_ntp():
    """Synchronize RTC and ts_clocktick with NTP."""
    global ts_clocktick
    global ts_lastntpsync
    global consecutive_failures

    print("\n>> Syncing time via NTP...")
    try:
        if not esp.is_connected:
            print("!! Wi-Fi disconnected before NTP sync, reconnecting...")
            if not await reconnect_wifi():
                raise OSError("Wi-Fi reconnect timeout before NTP sync")

        ## Cache ntp.datetime once to avoid two blocking network calls
        ntp_now = ntp.datetime
        rtc.datetime = ntp_now
        ts_clocktick = time.mktime(ntp_now)
        ts_lastntpsync = time.monotonic()
        print("<< Time synchronized successfully.")
        consecutive_failures = 0  # reset on success
    except OSError as e:
        consecutive_failures += 1
        print(f"!! OSError while syncing time: {e} (fail #{consecutive_failures})")
        ## Schedule next retry after NTP_RETRY_INTERVAL, not on every tick
        ts_lastntpsync = time.monotonic() - NTP_INTERVAL + NTP_RETRY_INTERVAL
        ## If we’ve failed too many times in a row, reset the ESP
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            print("!! Too many consecutive failures, resetting the ESP module...")
            esp.reset()                # Hard-reset the ESP32
            ## After a reset, the ESP32 is in an initial state, so we need to re-init Wi-Fi
            if not await reconnect_wifi(max_wait_s=30):
                print("!! ESP reconnect failed repeatedly; performing board reset.")
                microcontroller.reset()
            consecutive_failures = 0


##------------------------------------------------------------------------------
async def reconnect_wifi(max_wait_s=20):
    """Reconnect to Wi-Fi after an esp.reset()."""
    deadline = time.monotonic() + max_wait_s
    while (not esp.is_connected) and (time.monotonic() < deadline):
        try:
            esp.connect_AP(CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD)
        except OSError as e:
            print("!! Could not reconnect to Wi-Fi, retrying:", e)
            ## Yield control to the event loop instead of blocking
        await asyncio.sleep(WIFI_RETRY_DELAY)

    if esp.is_connected:
        print("!! Reconnected to Wi-Fi after ESP reset.")
        return True

    print("!! Reconnect timeout.")
    return False


##==============================================================================
print("\n***********************")
print(  "**** Display Setup ****")
print(  "***********************")

matrix = Matrix(
    # width=64, height=32,
    # rotation=180,
    )
time.sleep(1)  # show the Adafruit logo for 1 second
display = matrix.display

## Load Python logo from a BMP file
image, palette = adafruit_imageload.load("Python-logo_64x32.bmp")
tile_grid = displayio.TileGrid(image, pixel_shader=palette)
group = displayio.Group()
group.append(tile_grid)
display.root_group = group
time.sleep(2)  # show the Python logo for 2 seconds

# text = "Hello\nred!"
# text_area = Label(terminalio.FONT, text=text, color=0x440000)
# text_area.x = 1
# text_area.y = 8
# display.root_group = text_area
# time.sleep(1)  # show the text for 1 second

# text = "Hello\ngreen!"
# text_area = Label(terminalio.FONT, text=text, color=0x004400)
# text_area.x = 28
# text_area.y = 8
# display.root_group = text_area
# time.sleep(1)  # show the text for 1 second

## Create a color palette
color = displayio.Palette(5)
color[0] = 0x000000  # black background
color[1] = 0x400000  # red
# color[1] = 0xAA0000  # red (night mode – dim but visible)
color[2] = 0xCC4000  # amber
color[3] = 0x404000  # greenish
color[4] = 0x0846e4  # blueish

# ## Create a bitmap object (width, height, bit depth)
# bitmap = displayio.Bitmap(64, 32, 5)
# ## Set all pixels to black
# for i in range(64):
#     for j in range(32):
#         bitmap[i, j] = 0

# ## Draw a blueish crosshair in the middle
# for i in range(64):
#     bitmap[i, 15] = 4
# for j in range(32):
#     bitmap[32, j] = 4

# ## Create a Group
# group = displayio.Group()
# ## Create a TileGrid using the Bitmap and Palette
# tile_grid = displayio.TileGrid(bitmap, pixel_shader=color)
# ## Add the TileGrid to the Group
# group.append(tile_grid)
# display.root_group = group
# time.sleep(2)  # show the blueish line for 1 second


##==============================================================================
print("\n*********************************************")
print(  "**** SHT40 Temperature & Pressure Sensor ****")
print(  "*********************************************")

## To use default I2C bus (most boards)
i2c_bus = board.I2C()  # uses board.SCL and board.SDA
# i2c_bus = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

def lock_i2c_with_timeout(timeout_s=I2C_LOCK_TIMEOUT):
    """Try to acquire I2C lock and return True on success, False on timeout."""
    started = time.monotonic()
    while not i2c_bus.try_lock():
        if time.monotonic() - started >= timeout_s:
            return False
        time.sleep(I2C_LOCK_RETRY_DELAY)
    return True


if lock_i2c_with_timeout():
    try:
        i2c_devices = i2c_bus.scan()
        print("\n## I2C device addresses found:")
        print(">", [(device_address, hex(device_address)) for device_address in i2c_devices])
    finally:
        i2c_bus.unlock()
else:
    print("!! I2C lock timeout during startup scan; continuing without scan.")

sht40_sensor = 0x44  # i2c_devices[1]

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


##------------------------------------------------------------------------------
def read_sensor():
    """
    Read measurement data from Sensirion SHT40.

    Returns
    -------
    * t_degC : float
    * rh_pRH : float
    """
    mode = sht40_modes[1]  # NOHEAT_HIGHPRECISION

    if not lock_i2c_with_timeout():
        raise RuntimeError("I2C lock timeout while reading SHT40")

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


print("\n## Reading sensor data...")
try:
    t_degC, rh_pRH = read_sensor()
    last_sensor_reading = (t_degC, rh_pRH)
    last_sensor_read_monotonic = time.monotonic()
    print('> temperature:', t_degC)
    print('> humidity:', rh_pRH)
except Exception as e:
    print("!! Initial sensor read failed:", e)


##==============================================================================
print("\n**********************")
print(  "**** Matrix Clock ****")
print(  "**********************")

## Define fonts
font_clock_day = bitmap_font.load_font("IBMPlexMono-Medium-24_jep.bdf")
# font_sensor_day = bitmap_font.load_font("6x10.bdf")  # ugly
font_sensor_day = bitmap_font.load_font("helvR10.bdf")
font_sensor_night = terminalio.FONT
font_clock_night = terminalio.FONT
font_sensor_night = font_sensor_day
font_clock_night = font_sensor_day

## Create labels for the display text
clock_label = Label(font_clock_day)
sensor_label = Label(font_sensor_day)
clock_label.color = color[4]
sensor_label.color = color[4]
## Place the labels
clock_label.y = display.height // 3
sensor_label.y = 26

## Create a display group for the labels
group = displayio.Group()
display.root_group = group
## Add the labels to the group
group.append(clock_label)
group.append(sensor_label)


##------------------------------------------------------------------------------
def update_display(*, hours=None, minutes=None, show_colon=False):
    """Update the clock display with the current time and sensor readings."""
    global last_sensor_read_monotonic
    global last_sensor_reading

    # now_monotonic = time.monotonic()
    now_time = time.time()
    now_monotonic = time.monotonic()
    now_tick = ts_clocktick
    now_rtc = rtc.datetime
    # print(f"## Monotonic: {now_monotonic}")
    # print(f"## Time:      {now_time}")
    # print(f"## Tick:      {now_tick}")
    # print(f"## UTC @ Time: {time.localtime(now_time)}")
    # print(f"## UTC @ Tick: {time.localtime(now_tick)}")
    # print(f"## UTC @ RTC:  {now_rtc}")
    print()
    print(f"## CET @ Time: {datetime_util.localtime_toString(time.localtime(now_time))}")
    print(f"## CET @ Tick: {datetime_util.localtime_toString(time.localtime(now_tick))}")
    print(f"## CET @ RTC:  {datetime_util.localtime_toString(now_rtc)}")

    ## Use the RTC (already NTP-synced) for display – avoids blocking network calls
    offset = datetime_util.daylightSavingOffset(now_time)  # TZ offset in seconds (CET/CEST)
    now = time.localtime(time.mktime(now_rtc) + offset)  # CET/CEST

    if hours is None:
        hours = now[3]
    if minutes is None:
        minutes = now[4]
    seconds = now[5]
    if now[6] in [5, 6]:  # Saturday or Sunday
        wakeup = 8
    else:
        wakeup = 7

    if hours >= 20 or hours < wakeup:
        ## Evening hours to morning
        clock_label.font = font_clock_night
        clock_label.color = color[1]
        sensor_label.font = font_sensor_night
        sensor_label.color = color[1]
    else:
        ## Daylight hours
        clock_label.font = font_clock_day
        clock_label.color = color[3]
        sensor_label.font = font_sensor_day
        sensor_label.color = color[3]

    if BLINK:
        colon = ":" if show_colon or seconds % 2 else " "
    else:
        colon = ":"

    ## Format the time string --------------------------------------------------
    time_str_display = "{:d}{}{:02d}".format(hours, colon, minutes)
    # time_str_stdout = "{}:{:02d}".format(time_str_display, seconds)
    clock_label.text = time_str_display
    bbx, bby, bbwidth, bbh = clock_label.bounding_box

    clock_label.x = round(display.width / 2 - bbwidth / 2)  # centered
    clock_label.y = display.height // 3
    if DEBUG:
        print("## clock_label bounding box: {},{},{},{}".format(bbx, bby, bbwidth, bbh))
        print("## clock_label x: {} y: {}".format(clock_label.x, clock_label.y))

    ## Format the sensor string ------------------------------------------------
    if now_monotonic - last_sensor_read_monotonic >= SENSOR_READ_INTERVAL:
        try:
            last_sensor_reading = read_sensor()
            last_sensor_read_monotonic = now_monotonic
        except Exception as e:
            print("!! Sensor read failed:", e)

    t_degC, rh_pRH = last_sensor_reading
    if t_degC is None or rh_pRH is None:
        sensor_str = "--.-°  --.-%"
    else:
        sensor_str = "{:.1f}°  {:.1f}%".format(t_degC, rh_pRH)

    sensor_label.text = sensor_str
    bbx, bby, bbwidth, bbh = sensor_label.bounding_box
    sensor_label.x = round(display.width / 2 - bbwidth / 2)  # centered
    sensor_label.y = 26
    if DEBUG:
        print("## sensor_label bounding box: {},{},{},{}".format(bbx, bby, bbwidth, bbh))
        print("## sensor_label x: {} y: {}".format(sensor_label.x, sensor_label.y))


##------------------------------------------------------------------------------
async def _clocktick():
    """Scheduler to add one second to the counter."""
    global ts_clocktick
    while True:
        ts_clocktick += 1
        await asyncio.sleep(1)


##------------------------------------------------------------------------------
async def clocktick():
    """Check if NTP sync is due and update the clock display."""
    ## Check if NTP is due
    if ts_lastntpsync is None or time.monotonic() > ts_lastntpsync + NTP_INTERVAL:
        update_display(show_colon=True)  # make sure a colon is displayed while updating
        await sync_time_via_ntp()
    ## Update the time display
    update_display()


##******************************************************************************
##******************************************************************************

update_display(show_colon=True)  # display whatever time is on the board

## 1) Run clock in a loop
# while True:
#     clocktick()
#     time.sleep(1)


## 2) Run clock in a routine
async def main():
    ## Init co-routines (cooperative tasks) for basic clock function
    asyncio.create_task(_clocktick())
    # asyncio.create_task(_update_clock(lock))
    # asyncio.create_task(_sync_time_NTP(lock, ntp))

    while True:
        try:
            await clocktick()
        except Exception as e:
            print("!! Unhandled error in main loop:", e)
        await asyncio.sleep(1)


# try:
#     asyncio.run(main())
# finally:
#     ## Clear retained state
#     _ = asyncio.new_event_loop()
asyncio.run(main())
