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

Install the device libraries listed in `requirements.txt` onto the board:

    .venv/bin/circup install -r requirements.txt

# Development: linting & type checking

## venv setup

The configuration files (`pyrightconfig.json`, `pyproject.toml`) expect the
venv at `.venv` with **Python 3.11**. Set it up with either pip or uv:

    ## Option A: pip/venv
    python3.11 -m venv .venv
    .venv/bin/pip install -r requirements-dev.txt

    ## Option B: uv
    uv venv --python 3.11 .venv
    uv pip install -r requirements-dev.txt

    ## Both cases: select the board-specific pins for the `board` module
    .venv/bin/circuitpython_setboard matrixportal_m4

`requirements-dev.txt` contains everything needed for the host venv:

* `circuitpython-stubs` — type stubs for the CircuitPython core modules
  (`board`, `displayio`, `rgbmatrix`, `rtc`, ...), packaged as regular
  PEP-561 stub packages — unlike MicroPython, **no custom typeshed is needed**
* the typed Adafruit libraries (`adafruit-circuitpython-*`) plus Blinka —
  these give the checkers the real APIs of `adafruit_display_text` & Co.
* `basedpyright` (same engine as Pylance), `ty`, `ruff`, `circup`, `mpremote`

**Important:** `circuitpython_setboard matrixportal_m4` copies the
MatrixPortal-M4 pin definitions into the `board` stubs inside the venv.
Re-run it after every `circuitpython-stubs` update and on every fresh venv,
otherwise `board.MTX_R1` etc. are unknown to the checkers.

## Running the checkers

    .venv/bin/basedpyright src    ## config: pyrightconfig.json
    .venv/bin/ty check            ## config: pyproject.toml [tool.ty]
    .venv/bin/ruff check src      ## config: pyproject.toml [tool.ruff]

All three must pass without errors. Notes:

* `src/_archive_/` (dated snapshots) is excluded from checking.
* A few upstream stub quirks are deliberately suppressed with comments in the
  code or overrides in `pyproject.toml`:
  * `adafruit_bitmap_font` names the `get_glyph` parameter `code_point`, the
    `FontProtocol` of circuitpython-stubs expects `codepoint` → ty override.
  * `adafruit_display_text` annotates `bounding_box` as `Tuple[int, int]`,
    but it returns 4 values → per-line `# pyright: ignore`.
  * The `rgbmatrix` stubs declare the pin parameters as `DigitalInOut`,
    but the real API (and every official example) takes `microcontroller.Pin`
    → file-level suppression in `code_scrolling text.py`.
* The on-device `secrets.py` (gitignored) shadows the CPython stdlib module
  `secrets` — the example carries per-line ignores for this.

## VSCode

Recommended extensions: **Pylance** (or basedpyright) and **ty**. To make the
extensions use the venv-installed checkers, add to the workspace settings
(`*.code-workspace` is gitignored, recreate if needed):

    "settings": {
        "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
        "ty.importStrategy": "fromEnvironment",
        "basedpyright.importStrategy": "fromEnvironment"
    }
