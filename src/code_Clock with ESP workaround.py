import asyncio
import os
import time

import adafruit_connection_manager
import adafruit_ntp

## Network ---------------------------------------------------------------------
import board
import busio
import digitalio

## NTP & RTC -------------------------------------------------------------------
import rtc
from adafruit_esp32spi import adafruit_esp32spi

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
NTP_INTERVAL = 60  # 60s = 1min  # stress test
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
    try:
        esp.connect_AP(CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD)
    except OSError as e:
        print("!! Could not connect, retrying: ", e)
        continue
ap_info = esp.ap_info  # Optional laut Stubs, daher lokale Variable mit Guard
if ap_info is not None:
    print("## Connected to", ap_info.ssid, "\tRSSI:", ap_info.rssi, "\tIP addr:", esp.pretty_ip(esp.ip_address))


##==============================================================================
print("\n*******************")
print(  "**** NTP & RTC ****")
print(  "*******************")

pool = adafruit_connection_manager.get_radio_socketpool(esp)
ntp = adafruit_ntp.NTP(pool, tz_offset=0, cache_seconds=NTP_INTERVAL, server="pool.ntp.org")
print("## Current NTP time:", ntp.datetime)
rtc_inst = rtc.RTC()  ## eigener Name, um das rtc-Modul nicht zu verschatten
rtc_inst.datetime = ntp.datetime
print("## Current RTC time:", rtc_inst.datetime)


##------------------------------------------------------------------------------
def sync_time_via_ntp():
    """Synchronize RTC and ts_clocktick with NTP."""
    global ts_clocktick
    global ts_lastntpsync
    global consecutive_failures

    print("\n>> Syncing time via NTP...")
    try:
        ## The line below may raise an OSError if SPI times out or if Wi-Fi is locked up
        rtc_inst.datetime = ntp.datetime
        ts_clocktick = time.mktime(ntp.datetime)
        ts_lastntpsync = time.monotonic()
        print("<< Time synchronized successfully.")
        consecutive_failures = 0  # reset on success
    except OSError as e:
        consecutive_failures += 1
        print(f"!! OSError while syncing time: {e} (fail #{consecutive_failures})")

        ## If we’ve failed too many times in a row, reset the ESP
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            print("!! Too many consecutive failures, resetting the ESP module...")
            esp.reset()                # Hard-reset the ESP32
            ## After a reset, the ESP32 is in an initial state, so we need to re-init Wi-Fi
            reconnect_wifi()
            consecutive_failures = 0
        else:
            ## Optional: wait a bit before trying again
            time.sleep(10)


##------------------------------------------------------------------------------
def reconnect_wifi():
    """Reconnect to Wi-Fi after an esp.reset()."""
    while not esp.is_connected:
        try:
            esp.connect_AP(CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD)
        except OSError as e:
            print("!! Could not reconnect to Wi-Fi, retrying:", e)
            time.sleep(5)
    print("!! Reconnected to Wi-Fi after ESP reset.")


##------------------------------------------------------------------------------
def update_display(show_colon=False):
    """Update the clock strings with the current time. NOTE: `show_colon` not used w/o display."""
    # now_monotonic = time.monotonic()
    now_time = time.time()
    now_tick = ts_clocktick
    now_rtc = rtc_inst.datetime
    ## Protect the direct ntp.datetime call
    try:
        now_ntp = ntp.datetime
    except OSError as e:
        print("!! OSError while fetching ntp.datetime:", e)
        now_ntp = now_rtc
    # print(f"## Monotonic: {now_monotonic}")
    # print(f"## Time:      {now_time}")
    # print(f"## Tick:      {now_tick}")
    # print(f"## UTC @ Time: {time.localtime(now_time)}")
    # print(f"## UTC @ Tick: {time.localtime(now_tick)}")
    # print(f"## UTC @ RTC:  {now_rtc}")
    # print(f"## UTC @ NTP:  {now_ntp}")
    print()
    print(f"## CET @ Time: {datetime_util.localtime_toString(time.localtime(now_time))}")
    print(f"## CET @ Tick: {datetime_util.localtime_toString(time.localtime(now_tick))}")
    print(f"## CET @ RTC:  {datetime_util.localtime_toString(now_rtc)}")
    print(f"## CET @ NTP:  {datetime_util.localtime_toString(now_ntp)}")


##------------------------------------------------------------------------------
async def _clocktick(lock):
    """Scheduler to add one second to the counter."""
    global ts_clocktick
    while True:
        # await lock.acquire()
        ts_clocktick += 1
        # lock.release()
        await asyncio.sleep(1)


##------------------------------------------------------------------------------
def clocktick():
    """Check if NTP sync is due and update the clock display."""
    global ts_lastntpsync
    global ts_clocktick

    ## Check if NTP is due
    if ts_lastntpsync is None or time.monotonic() > ts_lastntpsync + NTP_INTERVAL:
        update_display(show_colon=True)  # make sure a colon is displayed while updating
        sync_time_via_ntp()
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
    ## Create the lock instance
    lock = asyncio.Lock()

    ## Init co-routines (cooperative tasks) for basic clock function
    asyncio.create_task(_clocktick(lock))
    # asyncio.create_task(_update_clock(lock))
    # asyncio.create_task(_sync_time_NTP(lock, ntp))

    while True:
        clocktick()
        await asyncio.sleep(1)

# try:
#     asyncio.run(main())
# finally:
#     ## Clear retained state
#     _ = asyncio.new_event_loop()
asyncio.run(main())
