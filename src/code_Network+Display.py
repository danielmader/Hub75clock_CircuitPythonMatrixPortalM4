
"""
Initialization of the MatrixPortal M4 with 64x32 RGB Matrix display

https://learn.adafruit.com/creating-projects-with-the-circuitpython-matrixportal-library?view=all
https://learn.adafruit.com/circuitpython-display-support-using-displayio?view=all

https://learn.adafruit.com/adafruit-matrixportal-m4?view=all
https://learn.adafruit.com/weather-display-matrix?view=all
https://learn.adafruit.com/network-connected-metro-rgb-matrix-clock?view=all
https://learn.adafruit.com/moon-phase-clock-for-adafruit-matrixportal?view=all
https://learn.adafruit.com/rgb-led-matrices-matrix-panels-with-circuitpython?view=all

https://adafruit-playground.com/u/VPTechOps/pages/rgb-matrix-word-clocks
"""

# import sys
import os
import time

import adafruit_connection_manager

## Network #1 w/ ESP32 ---------------------------------------------------------
import board
import busio
import digitalio

## Display #3 ------------------------------------------------------------------
import displayio
import neopixel
import terminalio

## Clock Testing ---------------------------------------------------------------
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_wifimanager

## Display #2 ------------------------------------------------------------------
from adafruit_matrixportal.matrix import Matrix

## Display #1 ------------------------------------------------------------------
from adafruit_matrixportal.matrixportal import MatrixPortal

## Network #2 & NTP #2 ---------------------------------------------------------
## ==> needs AIO credentials for network.get_local_time() :(
from adafruit_matrixportal.network import Network
from adafruit_ntp import NTP

## NTP & RTC -------------------------------------------------------------------
from rtc import RTC

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
print("\n***********************************")
print(  "**** Network Setup #1 w/ ESP32 ****")
print(  "***********************************")

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
    try:
        esp.connect_AP(CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD)
    except OSError as e:
        print("!! Could not connect, retrying: ", e)
        continue
ap_info = esp.ap_info  # Optional laut Stubs, daher lokale Variable mit Guard
if ap_info is not None:
    print("## Connected to", ap_info.ssid, "\tRSSI:", ap_info.rssi, "\tIP addr:", esp.pretty_ip(esp.ip_address))


##==============================================================================
## Connection Manager
pool = adafruit_connection_manager.get_radio_socketpool(esp)


##==============================================================================
## Wifi Manager
## TODO: How to use socket pool of the ESP32SPI_WiFiManager class
status_light = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
secrets = {
    'ssid': CIRCUITPY_WIFI_SSID,
    'password': CIRCUITPY_WIFI_PASSWORD,
    }
wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)
wifi.connect()
print("## WiFiManager IP addr:", wifi.ip_address())


##==============================================================================
print("\n****************************************")
print(  "**** NTP & RTC w/ ESP32 socket pool ****")
print(  "****************************************")

ntp = NTP(pool, tz_offset=0, cache_seconds=3600, server="pool.ntp.org")
print("## Current NTP time:", ntp.datetime)
rtc = RTC()
rtc.datetime = ntp.datetime
print("## Current RTC time:", rtc.datetime)


##==============================================================================
print("\n***************************************")
print(  "**** Network Setup #2 w/ Network() ****")
print(  "***************************************")

try:
    # neopixel_pin = board.NEOPIXEL
    # network = Network(status_neopixel=neopixel_pin, debug=True)
    network = Network(debug=True)
except ValueError:
    esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_busy, esp32_reset)
    network = Network(esp=esp, debug=True)

network.connect()
print("## Network IP address:", network.ip_address)


##==============================================================================
print("\n*****************************")
print(  "**** NTP #2 w/ Network() ****")
print(  "*****************************")

# print("## Current NTP time:", network.get_local_time())
## ==> needs AIO credentials for network.get_local_time() :(


##==============================================================================
print("\n********************************************")
print(  "**** Display Setup #1 w/ MatrixPortal() ****")
print(  "********************************************")

# matrixportal = MatrixPortal(debug=True)
try:
    neopixel_pin = board.NEOPIXEL
    matrixportal = MatrixPortal(status_neopixel=neopixel_pin, debug=True)
except ValueError:
    esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_busy, esp32_reset)
    matrixportal = MatrixPortal(esp=esp, debug=True)

## Connect to the internet
# matrixportal.network.connect()
# print("## MatrixPortal IP address:", matrixportal.network.ip_address)
# print("## Current NTP time:", matrixportal.network.get_local_time())
## ==> needs AIO credentials for matrixportal.network.get_local_time() :(

## Set an image
matrixportal.set_background('Python-logo_64x32.bmp')
time.sleep(1)

## Create static labels
label1 = matrixportal.add_text(
    text_font=terminalio.FONT,
    text_position=(0, 10),
    )
label2 = matrixportal.add_text(
    text_font=terminalio.FONT,
    text_position=(0, 25),
    )
while True:
    matrixportal.set_text_color(0xCC4000, label1)
    matrixportal.set_text("Hello", label1)
    time.sleep(0.5)
    matrixportal.set_text_color(0x00FF00, label2)
    matrixportal.set_text("CircuitPython!", label2)
    time.sleep(0.5)
    break

## Set a background color
matrixportal.set_background(0x000044)
time.sleep(1)

## Create a new scrolling label
label3 = matrixportal.add_text(
    text_font=terminalio.FONT,
    text_position=(0, (matrixportal.graphics.display.height // 2) - 1),
    scrolling=True,
    )
SCROLL_DELAY = 0.005
contents = [
    { 'text': 'RED scroller',  'color': '#cf2727'},
    { 'text': 'BLUE scroller', 'color': '#0846e4'},
]
while True:
    for content in contents:
        matrixportal.set_text(content['text'], label3)

        ## Set the text color
        matrixportal.set_text_color(content['color'], label3)

        ## Scroll it
        matrixportal.scroll_text(SCROLL_DELAY)
    break

## Clear the display
matrixportal.set_text('', label1)
matrixportal.set_text('', label2)


##==============================================================================
print("\n**************************************")
print(  "**** Display Setup #2 w/ Matrix() ****")
print(  "**************************************")

matrix = Matrix(
    # width=64, height=32,
    # rotation=180,
    )
time.sleep(1)  # show the Adafruit logo for 1 second
display = matrix.display

text = "Hello\nred!"
text_area = label.Label(terminalio.FONT, text=text, color=0x440000)
text_area.x = 1
text_area.y = 8
display.root_group = text_area
time.sleep(1)  # show the text for 1 second

text = "Hello\ngreen!"
text_area = label.Label(terminalio.FONT, text=text, color=0x004400)
text_area.x = 28
text_area.y = 8
display.root_group = text_area
time.sleep(1)  # show the text for 1 second


##==============================================================================
print("\n**************************************************")
print(  "**** Display Setup #3 w/ Matrix() & displayio ****")
print(  "**************************************************")

matrix = Matrix(
    # width=64, height=32,
    # rotation=180,
    )
time.sleep(1)  # show the Adafruit logo for 1 second
display = matrix.display

## Create a color palette
color = displayio.Palette(5)
color[0] = 0x000000  # black background
color[1] = 0x400000  # red
color[2] = 0xCC4000  # amber
color[3] = 0x404000  # greenish
color[4] = 0x0846e4  # blueish

## Create a bitmap object (width, height, bit depth)
bitmap = displayio.Bitmap(64, 32, 5)
## Set all pixels to black
for i in range(64):
    for j in range(32):
        bitmap[i, j] = 0

## Draw a blueish crosshair in the middle
for i in range(64):
    bitmap[i, 15] = 4
for j in range(32):
    bitmap[32, j] = 4

## Create a Group
group = displayio.Group()
## Create a TileGrid using the Bitmap and Palette
tile_grid = displayio.TileGrid(bitmap, pixel_shader=color)
## Add the TileGrid to the Group
group.append(tile_grid)
display.root_group = group
time.sleep(2)  # show the blueish line for 1 second


##==============================================================================
print("\n***********************")
print(  "**** Clock Testing ****")
print(  "***********************")

network = Network(esp=esp, debug=True)
network.connect()

## Define fonts
# font_large = bitmap_font.load_font("IBMPlexMono-Medium-24_jep.bdf")
# font_small = terminalio.FONT
# font_small = bitmap_font.load_font("helvR10.bdf")
font_small = bitmap_font.load_font("6x10.bdf")

while True:
    year, month, mday, hour, minute, second, weekday, yearday, dst = ntp.datetime
    timestr = f"{year}-{month}-{mday}  {hour:02d}:{minute:02d}:{second:02d}"
    timestr = f"{hour:02d}:{minute:02d}:{second:02d}"
    # ipstr = '%s' % esp.pretty_ip(esp.ip_address)
    # ipstr = '%s' % matrixportal.network.ip_address
    # ipstr = f"{network.ip_address}"

    text = f"{timestr}"
    text_area = label.Label(font_small, text=text, color=0x110000)
    text_area.x = 0
    text_area.y = 8
    display.root_group = text_area
    time.sleep(0.5)
