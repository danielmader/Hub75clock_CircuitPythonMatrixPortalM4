"""
MatrixClock - a HUB75 LED matrix clock driven by Adafruit MaxtrixPortal M4.
* Synchronization with NTP.
* Temperature/humidity ambient sensor (Sensirion SHT40).

@author: mada
@version: 2024-09-20
"""

from os import getenv

import board
from digitalio import DigitalInOut
from busio import SPI

import time
import adafruit_ntp
import rtc

import asyncio

import microcontroller
# from microcontroller import Pin

## Frozen modules
import adafruit_connection_manager
import adafruit_requests
from adafruit_esp32spi import adafruit_esp32spi
# from adafruit_matrixportal.matrix import Matrix
import neopixel

## Custom modules
import datetime_util
# import characters

##******************************************************************************
##******************************************************************************

## DEBUG mode ------------------------------------------------------------------
debug_mode = False
# debug_mode = True

## Global variables ------------------------------------------------------------
## NTP sync interval and last sync timestamp
ntp_interval = 3600 * 12  # 3600s = 60min = 1h
ts_ntpsync = 0
## Clock counter
if debug_mode:
    ## Start at 05:59:00 UTC = 06:59:00 CET ...
    ts_clocktick = 60 * 60 * 5 + 59 * 60
else:
    ## Start at 00:00:00 UTC
    ts_clocktick = time.time()

##******************************************************************************
##******************************************************************************


##==============================================================================
def show_boardpins():
    """
    Show all available board pins.

    https://learn.adafruit.com/adafruit-matrixportal-m4/circuitpython-pins-and-modules
    """
    '''
    dir(board):
    ['__class__', '__name__', 'A0', 'A1', 'A2', 'A3', 'A4', 'ACCELEROMETER_INTERRUPT', 'BUTTON_DOWN', 'BUTTON_UP',
    'ESP_BUSY', 'ESP_CS', 'ESP_GPIO0', 'ESP_RESET', 'ESP_RTS', 'ESP_RX', 'ESP_TX', 'I2C', 'L', 'LED', 'MISO', 'MOSI',
    'MTX_ADDRA', 'MTX_ADDRB', 'MTX_ADDRC', 'MTX_ADDRD', 'MTX_ADDRE', 'MTX_ADDRESS', 'MTX_B1', 'MTX_B2', 'MTX_CLK',
    'MTX_COMMON', 'MTX_G1', 'MTX_G2', 'MTX_LAT', 'MTX_OE', 'MTX_R1', 'MTX_R2', 'NEOPIXEL', 'RX', 'SCK', 'SCL', 'SDA',
    'SPI', 'STEMMA_I2C', 'TX', 'UART', '__dict__', 'board_id']

    dir(microcontroller.pin):
    ['__class__', 'PA00', 'PA01', 'PA02', 'PA03', 'PA04', 'PA05', 'PA06', 'PA07', 'PA08', 'PA09', 'PA10', 'PA11',
    'PA12', 'PA13', 'PA14', 'PA15', 'PA16', 'PA17', 'PA18', 'PA19', 'PA20', 'PA21', 'PA22', 'PA23', 'PA27', 'PA30',
    'PA31', 'PB00', 'PB01', 'PB02', 'PB03', 'PB04', 'PB05', 'PB06', 'PB07', 'PB08', 'PB09', 'PB10', 'PB11', 'PB12',
    'PB13', 'PB14', 'PB15', 'PB16', 'PB17', 'PB22', 'PB23', 'PB30', 'PB31', '__dict__']

    sorted board pins:
    board.A0 (PA02)
    board.A1 (PA05)
    board.A2 (PA04)
    board.A3 (PA06)
    board.A4 (PA07)
    board.ACCELEROMETER_INTERRUPT (PA27)
    board.BUTTON_DOWN (PB23)
    board.BUTTON_UP (PB22)
    board.ESP_BUSY (PA22)
    board.ESP_CS (PB17)
    board.ESP_GPIO0 (PA20)
    board.ESP_RESET (PA21)
    board.ESP_RTS (PA18)
    board.ESP_RX (PA12)
    board.ESP_TX (PA13)
    board.L board.LED (PA14)
    board.MISO (PA17)
    board.MOSI (PA19)
    board.MTX_ADDRA (PB07)
    board.MTX_ADDRB (PB08)
    board.MTX_ADDRC (PB09)
    board.MTX_ADDRD (PB15)
    board.MTX_ADDRE (PB13)
    board.MTX_B1 (PB02)
    board.MTX_B2 (PB05)
    board.MTX_CLK (PB06)
    board.MTX_G1 (PB01)
    board.MTX_G2 (PB04)
    board.MTX_LAT (PB14)
    board.MTX_OE (PB12)
    board.MTX_R1 (PB00)
    board.MTX_R2 (PB03)
    board.NEOPIXEL (PA23)
    board.RX (PA01)
    board.SCK (PA16)
    board.SCL (PB30)
    board.SDA (PB31)
    board.TX (PA00)
    '''
    board_pins = []
    for pin in dir(microcontroller.pin):
        if (isinstance(getattr(microcontroller.pin, pin), microcontroller.Pin)):
            pins = []
            for alias in dir(board):
                if getattr(board, alias) is getattr(microcontroller.pin, pin):
                    pins.append(f"board.{alias}")
            # Add the original GPIO name, in parentheses.
            if pins:
                # Only include pins that are in board.
                pins.append(f"({str(pin)})")
                board_pins.append(" ".join(pins))
    print("\n#### Labeled pins vs. MCU pins:")
    for pins in sorted(board_pins):
        print(pins)


##==============================================================================
def init_neopixels():
    """
    Init onboard Neopixel.

    Returns
    -------
    * pixels : neopixel.NeoPixel
    """
    return neopixel.NeoPixel(board.NEOPIXEL, 1)


##==============================================================================
def init_wifi():
    """
    Initialize wifi.

    Returns
    -------
    * esp : adafruit_esp32spi.ESP_SPIcontrol
    * pool : adafruit_connection_manager.get_radio_socketpool(esp)
    * requests : adafruit_requests.Session
    """
    ## ESP32 SPI webclient
    ## MatrixPortal M4: https://learn.adafruit.com/adafruit-matrixportal-m4/internet-connect
    ## MatrixPortal S3: https://learn.adafruit.com/adafruit-matrixportal-s3/circuitpython-internet-test

    ##--------------------------------------------------------------------------
    ## Initialize the ESP32 over SPI
    ## If you are using a board with pre-defined ESP32 Pins:
    esp32_cs = DigitalInOut(board.ESP_CS)
    esp32_ready = DigitalInOut(board.ESP_BUSY)
    esp32_reset = DigitalInOut(board.ESP_RESET)

    ## If you have an AirLift Shield:
    # esp32_cs = DigitalInOut(board.D10)
    # esp32_ready = DigitalInOut(board.D7)
    # esp32_reset = DigitalInOut(board.D5)

    ## If you have an AirLift Featherwing or ItsyBitsy Airlift:
    # esp32_cs = DigitalInOut(board.D13)
    # esp32_ready = DigitalInOut(board.D11)
    # esp32_reset = DigitalInOut(board.D12)

    ## If you have an externally connected ESP32:
    ## NOTE: You may need to change the pins to reflect your wiring
    # esp32_cs = DigitalInOut(board.D9)
    # esp32_ready = DigitalInOut(board.D10)
    # esp32_reset = DigitalInOut(board.D5)

    ## Secondary (SCK1) SPI used to connect to WiFi board on Arduino Nano Connect RP2040
    if "SCK1" in dir(board):
        spi = SPI(board.SCK1, board.MOSI1, board.MISO1)
    else:
        spi = SPI(board.SCK, board.MOSI, board.MISO)
    esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

    ##--------------------------------------------------------------------------
    ## Get the socket pool and the SSL context
    pool = adafruit_connection_manager.get_radio_socketpool(esp)
    ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
    requests = adafruit_requests.Session(pool, ssl_context)

    ##--------------------------------------------------------------------------
    ## Verify ESP32 HW and FW
    if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
        print("\n#### ESP32 found and in idle mode")
    else:
        print()
    print("Firmware vers.", esp.firmware_version)
    print("MAC addr:", ":".join("%02X" % byte for byte in esp.MAC_address))

    return esp, pool, requests


##==============================================================================
def scan_networks(esp):
    """Scan all available access points (slow)."""
    print("\n#### Scanning networks ...")
    for ap in esp.scan_networks():
        print("\t%-23s RSSI: %d" % (ap.ssid, ap.rssi))


##==============================================================================
def connect(esp):
    """
    Connect to AP defined in secrets.

    Returns
    -------
    * esp.ap_info.ssid
    * esp.ap_info.rssi
    * esp.ipv4_address
    """
    ## Get wifi details and more from a settings.toml file
    ## tokens used by this Demo: CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD
    secrets = {
        "ssid": getenv("CIRCUITPY_WIFI_SSID"),
        "password": getenv("CIRCUITPY_WIFI_PASSWORD"),
    }

    if secrets == {"ssid": None, "password": None}:
        try:
            ## Fallback on secrets.py until deprecation is over and option is removed
            from secrets import secrets
        except ImportError:
            print("#### WiFi secrets are kept in settings.toml, please add them there!")
            raise

    print("\n#### Connecting to AP ...")
    while not esp.is_connected:
        try:
            esp.connect_AP(secrets["ssid"], secrets["password"])
        except OSError as e:
            print(f"!!!! Could not connect to AP: {e}\n#### Retrying ....")
            continue
    print("#### Connected to", esp.ap_info.ssid, "\tRSSI:", esp.ap_info.rssi)
    print("IP address: ", esp.ipv4_address)

    return esp.ap_info.ssid, esp.ap_info.rssi, esp.ipv4_address


##==============================================================================
def test_connection(esp, requests):
    """Test connection and demonstrate JSON parsing."""
    print("\n#### Connection test:")
    LOOKUP_URL = getenv('LOOKUP_URL')
    PING_ADDRESS = getenv('PING_ADDRESS')
    PING_URL = getenv('PING_URL')
    TEXT_URL = getenv('TEXT_URL')
    JSON_URL = getenv('JSON_URL')

    print("1/5: Ping '%s': %d ms" % (PING_ADDRESS, esp.ping(PING_ADDRESS)))
    print("2/5: Ping '%s': %d ms" % (PING_URL, esp.ping(PING_URL)))
    # esp._debug = True
    print("3/5: IP lookup '%s': %s" % (LOOKUP_URL, esp.pretty_ip(esp.get_host_by_name(LOOKUP_URL))))
    print("4/5: Fetching TEXT from", TEXT_URL)
    r = requests.get(TEXT_URL)
    print("-" * 40)
    print(r.text)
    print("-" * 40)
    r.close()
    print()
    print("5/5: Fetching JSON from", JSON_URL)
    r = requests.get(JSON_URL)
    print("-" * 40)
    print(r.json())
    print("-" * 40)
    r.close()


##==============================================================================
def sync_time_NTP(ntp):
    """
    Synchronize via NTP.
    """
    try:
        print("\n>>>> syncing with NTP ...")
        ## Check connection status, and (re-)connect if required
        ## TODO:
        # wlan_util.connect()

        ## Get time
        # print('<< NTP timestamp:', ntptime.time())
        ## set time
        # ntptime.settime()

        ## NOTE: This changes the system time so make sure you aren't assuming that time doesn't jump.
        # print(ntp.datetime)
        rtc.RTC().datetime = ntp.datetime
        print("<<<< NTP timestamp:", time.time())
        return True

    except Exception as e:
        print(f"!!!! NTP synchronization failed: {e}")
        return False


##==============================================================================
def init_sensor():
    """
    Initialize Sensirion SHT40 temperature & pressure sensor .

    Returns
    -------
    * i2c_bus : I2C
    * i2c_devices : [int] device addresses (sht40 = i2c_devices[1])
    """
    # i2c_bus = I2C(0, scl=Pin(22), sda=Pin(21))
    ## To use default I2C bus (most boards)
    i2c_bus = board.I2C()  # uses board.SCL and board.SDA
    # i2c_bus = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

    while not i2c_bus.try_lock():
        pass
    try:
        i2c_devices = i2c_bus.scan()
        print("\n#### I2C addresses found:")
        print([(device_address, hex(device_address)) for device_address in i2c_devices])
    finally:
        ## Unlock the I2C bus
        i2c_bus.unlock()

    return i2c_bus, i2c_devices[1]


##==============================================================================
def read_sensor():
    '''
    Read measurement data from Sensirion SHT40.

    Returns
    -------
    * t_degC : float
    * rh_pRH : float
    '''
    modes = (
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
    # print ("\n>> reading sensor data ...")
    mode = modes[1]  # NOHEAT_HIGHPRECISION
    while not i2c_bus.try_lock():
        pass
    try:
        i2c_bus.writeto(i2c_device, bytearray([mode[1]]))
        time.sleep(mode[-1])
        rx_bytes = bytearray(6)
        i2c_bus.readfrom_into(i2c_device, rx_bytes)
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
        ## Unlock the I2C bus
        i2c_bus.unlock()


##==============================================================================
def set_clock(timestamp=None):
    """
    Update the display readings.
    """
    ##--------------------------------------------------------------------------
    ## Assemble raw time and sensor strings
    if not timestamp:
        # timestamp = ts_clocktick
        timestamp = time.time()

    localtime = datetime_util.cettime(timestamp)
    hour, minute, second = localtime[3:6]
    try:
        temp, hum = read_sensor()
    except Exception:
        temp, hum = None, None

    ## DEBUG
    # if second // 10 == 0:
    #     temp, hum = 9.9, 55.5
    # elif second // 10 == 1:
    #     temp, hum = -9.9, 55.5
    # elif second // 10 == 2:
    #     temp, hum = -11.1, 55.5
    # elif second // 10 == 3:
    #     temp, hum = 3.3, 4.4
    # elif second // 10 == 4:
    #     temp, hum = 22.2, 55.5
    # elif second // 10 == 5:
    #     temp, hum = None, None

    time_str = "{:02d}:{:02d}.{:02d}".format(hour, minute, second)
    try:
        sensor_str = "{:4.1f}C {:4.1f}%".format(temp, hum)
    except ValueError:
        sensor_str = "----  ----"
    print("{} / {}".format(time_str, sensor_str))


##------------------------------------------------------------------------------
async def _sync_time_NTP(lock, ntp):
    """
    Scheduler to synchronize via NTP.
    """
    global ts_clocktick
    global ts_ntpsync

    while True:
        if (ts_ntpsync == 0) or (ts_clocktick - ts_ntpsync > ntp_interval):
            await lock.acquire()
            for _ in range(5):
                if sync_time_NTP(ntp):
                    ts_clocktick = time.time()
                    ts_ntpsync = ts_clocktick
                    # print(datetime_util.cettime(ts_clocktick))

                    ## Update clock immediately after NTP sync
                    set_clock()
                    break
            lock.release()

        await asyncio.sleep(5)


##------------------------------------------------------------------------------
async def _refresh_display(lock):
    """
    Scheduler to show/refresh the display.
    """
    while True:
        await lock.acquire()
        pass
        # hub75spi.display_data()
        lock.release()
        await asyncio.sleep(0)


##------------------------------------------------------------------------------
async def _refresh_neopixel(lock, pixels, idx, rgb=None):
    """
    Scheduler to update Neopixel status.
    """
    while True:
        if not rgb:
            for i in range(3):
                pixels[idx] = (10, 0, 0)
                time.sleep(0.25)
                pixels[idx] = (0, 10, 0)
                time.sleep(0.25)
                pixels[idx] = (0, 0, 10)
                time.sleep(0.25)
                pixels[idx] = (0, 0, 0)
        else:
            pixels[idx] = rgb
            time.sleep(0.5)
            pixels[idx] = (0, 0, 0)
        await asyncio.sleep(3)


##------------------------------------------------------------------------------
async def _set_clock(lock):
    """
    Scheduler to update the display readings.
    """
    # global ts_clocktick
    while True:
        await lock.acquire()

        ts_timetime = time.time()
        ## Time difference
        timediff = ts_timetime - ts_clocktick
        ## UTC
        # print("\tUTC:",time.localtime())
        ## formatted CET/CEST
        time_str = "{:02d}.{:02d}:{:02d}"
        localtime_tick = datetime_util.cettime(ts_clocktick)[3:6]
        localtime_time = datetime_util.cettime(ts_timetime)[3:6]
        print(f"time: {time_str.format(*localtime_time)} / tick: {time_str.format(*localtime_tick)} / delta: {timediff:5.2f}")

        ## TODO: Update every second when flickerfree
        if ts_timetime % 10 == 0:
            print("#### Running set_clock() ...")
            set_clock()

        lock.release()
        await asyncio.sleep(1)


##------------------------------------------------------------------------------
async def _clocktick(lock):
    """
    Scheduler to add one second to the counter.
    """
    global ts_clocktick
    while True:
        # await lock.acquire()
        ts_clocktick += 1
        # lock.release()
        await asyncio.sleep(1)


##==============================================================================
async def main():
    ##--------------------------------------------------------------------------
    ## Show Python Logo
    # matrix.set_pixels(0, 16, logo)
    # for _ in range(100):
    #    hub75spi.display_data()

    ##--------------------------------------------------------------------------
    ## Init networking
    esp, pool, requests = init_wifi()
    ssid, rssi, ipv4 = connect(esp)

    ##--------------------------------------------------------------------------
    ## Test connection
    # test_connection(esp, requests)

    ##--------------------------------------------------------------------------
    ## Init NTP sync
    # ntp = adafruit_ntp.NTP(pool, tz_offset=0, cache_seconds=3600)
    ntp = adafruit_ntp.NTP(esp)

    ##--------------------------------------------------------------------------
    ## Create the Lock instance
    lock = asyncio.Lock()

    ## Init co-routines (cooperative tasks) for basic clock function
    asyncio.create_task(_clocktick(lock))
    asyncio.create_task(_set_clock(lock))
    asyncio.create_task(_sync_time_NTP(lock, ntp))

    ##--------------------------------------------------------------------------
    ## Init NeoPixel
    # pixels = init_neopixels()
    # asyncio.create_task(_refresh_neopixel(lock, pixels, 0))

    ##--------------------------------------------------------------------------
    ## Init clock face update
    # asyncio.create_task(_refresh_display(lock))

    while True:
        await asyncio.sleep(0)


##******************************************************************************
##******************************************************************************

##------------------------------------------------------------------------------
show_boardpins()

##------------------------------------------------------------------------------
## Init sensor
try:
    i2c_bus, i2c_device = init_sensor()
except IndexError:
    i2c_bus, i2c_device = None, None
    pass

##------------------------------------------------------------------------------
## Main clock routine
try:
    asyncio.run(main())
finally:
    ## Clear retained state
    _ = asyncio.new_event_loop()

print("\n#### All done!")
