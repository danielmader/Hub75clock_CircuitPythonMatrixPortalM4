# Hub75clock_CircuitPythonMatrixPortalM4

https://github.com/danielmader/Hub75clock_CircuitPythonMatrixPortalM4

A simple clock for a 64x32 HUB75 LED matrix display powered by Adafruit's MatrixPortal M4 with NTP sync and a Sensirion SHT40 ambient sensor.

Upper left and right corners show a status indicator.

Left:
  * no indicator: OK (i.e. last sync within due interval)
  * blinking: never synced with NTP OR currently syncing
  * permanent amber: NTP is overdue

Right:
  * no network connection

# Hardware

## Adafruit MatrixPortal M4
I'm still using the original MatrixPortal (25,90€):
- https://www.berrybase.de/adafruit-matrix-portal-circuitpython-powered-internet-display

## RGB LED matrix 64x32
The display (23,95€) is from WaveShare (and was much cheaper than the similar product from Adafruit):
- https://www.waveshare.com/wiki/RGB-Matrix-P4-64x32
- https://eckstein-shop.de/WaveShare-RGB-Full-Color-LED-Matrix-Panel-64x32-Pixels-4mm-Pitch-Adjustable-Brightness

Here I've found very valuable information about how to use this kind of display:
- https://www.bigmessowires.com/2018/05/24/64-x-32-led-matrix-programming/
- https://www.sparkfun.com/news/2650

## I²C temperature and pressure sensor
The sensor (7.95€) came on a convenient break-out board from Adafruit:
- https://learn.adafruit.com/adafruit-sht40-temperature-humidity-sensor
- https://eckstein-shop.de/AdafruitSensirionSHT40Temperature26HumiditySensor-STEMMAQT2FQwiic

# Dependencies

- [CircuitPython](https://circuitpython.org/board/matrixportal_m4/) for the MatrixPortal M4
- [Circup](https://pypi.org/project/circup/) to install the dependencies
