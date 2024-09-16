<!-- SPDX-License-Identifier: MIT -->
<!-- SPDX-FileCopyrightText: Copyright 2024 Sam Blenny -->
# Feather TFT Clock

This clock project uses USB gamepad input to control its time setting menu. The
display uses TileGrid sprites that I made in Krita. The code demonstrates how
to use timers and a state machine to build an event loop with gamepad input,
I2C real time clock IO, and display updates.

![photo of clock code running on a Feather TFT board with Adalogger and USB Host boards](feather-tft-clock.jpeg)


## Overview and Context

This clock is a step along the way on my quest towards learning how to build
little games and apps in CircuitPython. The look for the display theme is about
digital watches and alarm clocks from the 80's and 90's.

Some of the technical bits and pieces from this project that you might be able
to reuse in your own projects include:

- Menu system for manually setting time and date

- USB gamepad input system with edge-triggered button press events and
  repeating timer-triggered button hold events

- Data-watch style display theme with three display areas: 20 ASCII characters
  at the top, an eight digit 7-segment clock display in the middle, and another
  20 ASCII character display at the bottom

- Main event loop with gamepad button polling, real time clock polling, state
  machine updates and display updates


## Sprites and Krita

To make the sprites in Krita for 7-segment digits and data-watch style ASCII
characters, I used the "Pixel Art" brush preset with a custom palette swatch.


### Clock Digit Sprites

This is a Krita screenshot showing a zoomed in view of the spritesheet I made
for 7-segment digits. When the spritesheet is loaded as CircuitPython bitmap
for `displayio.TileGrid`, the sprite numbers start at `0` for the "0" sprite.
The "9" sprite is number `9`, the ":" sprite is `10`, the "-" sprite is `11`,
and the empty sprite is `12`.

![Krita screenshot showing seven-segment digit sprites](digit-font-screenshot.png)

Each sprite is 30 pixels wide by 50 pixels high. The top pixel of each sprite
is blank to work around a bug that currently affects bitmaps loaded from PNG
files with adafruit_imageloader. By the time you read this, the bug may have
been fixed (see https://github.com/adafruit/circuitpython/issues/9587).

The solid grid lines between sprites are Krita guides. The dotted lines are
grid divisions (for details, refer to the Grid options tab in the screenshot).


## ASCII Character Sprites

This Krita screenshot shows a zoomed in view of the spritesheet for my ASCII
character font:

![annotated Krita screenshot showing a spritesheet](ASCII-font-screenshot.png)

The sprites are each 6 pixels wide by 8 pixels high. The look is based on dot
matrix character LCD fonts used in digital watches and serial character
displays.

Numbering for the character sprites starts with 0 for the ASCII space
character. The last sprite number is 95, which corresponds to ASCII DEL
character (127), which I used for a custom up/down arrows glyph. To translate
from a Python string or byte to the sprite number, you subtract 32 from the
character's ordinal number (`ord()`) or the byte's integer value.

To get from a Krita document to a BMP spritesheet, I did:

1. In Krita: File menu > Export... > (export PNG file: ASCII-font.png)

2. In Debian terminal shell:
   `gm convert ASCII-font.png BMP3:ASCII-font.bmp`

The `gm convert` shell command requires that you have the Debian GraphicsMagick
package installed (`sudo apt install graphicsmagick`). ImageMagick would also
work.


## State Machine

The clock's state machine is moderately complicated. So, I made a table to help
me organize all the states along with actions and state transitions:

| State   | UP     | DOWN   | LEFT    | RIGHT   | A       | B    | START   |
| ------- | ------ | ------ | ------- | ------- | ------- | ---- | ------- |
| hhmm    | nop    | nop    | mmss    | mmss    | nop     | hhmm | setHMin |
| mmss    | nop    | nop    | hhmm    | hhmm    | nop     | hhmm | setHMin |
| setYr   | year+1 | year-1 | setSec  | setMDay | setMDay | hhmm | hhmm    |
| setMDay | day+1  | day-1  | setYr   | setHour | setHour | hhmm | hhmm    |
| setHour | hour+1 | hour-1 | setMDay | setHMin | setHMin | hhmm | hhmm    |
| setHMin | min+1  | min-1  | setHour | setSec  | setSec  | hhmm | hhmm    |
| setSec  | sec=0  | sec=0  | setHMin | setCal  | setYr   | hhmm | hhmm    |
| setCal  | cal+1  | cal-1  | setSec  | setYr   | setYr   | hhmm | hhmm    |


### Major Modes and Sub-modes

The state machine has 2 major modes:

1) **Clock Mode** shows the current time or date. There are sub-modes for a
   minimal hour and minute display (hhmm) and a fancier display with full date
   and time including seconds (mmss).

2) **Set Mode** lets you set the clock's year, month, day, hour, minutes,
   seconds, and calibration. Set Mode has sub-modes for setting the year
   (setYr), the month and day (setMDay), hours (setHour), hours and minutes
   (setHMin), seconds (setSec), and PCF8523 RTC calibration register (setCal).


### Button Actions

Clock Mode (all sub-modes):
- **LEFT** or **RIGHT**: switch between sub-modes
- **B**: Switch back to the hours and minutes sub-mode (hhmm)
- **START**: Switch to Set Mode

Set Mode (sub-modes: year, month-day, hours-minutes):
- **UP**: Add 1 to the value being set, or press and hold to increment the
  value faster
- **DOWN**: Subtract 1 from the value being set, or press and hold to decrement
  the value faster
- **A** or **RIGHT**: Advance to the next sub-mode
- **LEFT**: Switch to the previous sub-mode
- **B** or **START**: Switch back to Clock Mode

Set Mode (sub-mode: seconds):
- **UP** or **DOWN**: Set seconds to 00, rounding minutes to closest minute
- **A** or **RIGHT**: Advance to the next sub-mode
- **LEFT**: Switch to the previous sub-mode
- **B** or **START**: Switch back to Clock Mode

Set Mode (sub-mode: calibration):
- **UP**: Add 1 to the clock drift compensation calibration register
- **UP**: Subtract 1 from the clock drift compensation calibration register
- **A** or **RIGHT**: Advance to the next sub-mode
- **LEFT**: Switch to the previous sub-mode
- **B** or **START**: Switch back to Clock Mode


## Hardware


### Parts

- 8BitDo SN30 Pro USB gamepad
  ([product page](https://www.8bitdo.com/sn30-pro-usb-gamepad/))

- Adafruit ESP32-S3 TFT Feather - 4MB Flash, 2MB PSRAM
  ([product page](https://www.adafruit.com/product/5483),
  [learn guide](https://learn.adafruit.com/adafruit-esp32-s3-tft-feather))

- Adafruit USB Host FeatherWing with MAX3421E
  ([product page](https://www.adafruit.com/product/5858),
  [learn guide](https://learn.adafruit.com/adafruit-usb-host-featherwing-with-max3421e))

- Adalogger FeatherWing - RTC + SD
  ([product page](https://www.adafruit.com/product/2922),
  [learn guide](https://learn.adafruit.com/adafruit-adalogger-featherwing))

- FeatherWing Tripler Mini Kit
  ([product page](https://www.adafruit.com/product/3417))

- CR1220 12mm Diameter - 3V Lithium Coin Cell Battery
  ([product page](https://www.adafruit.com/product/380))

- Tamiya Universal Plate Set #70157
  (3mm thick, 160x60mm ABS plates with 3mm holes on 5mm grid)

- M2.5 Nylon Standoff Set
  (misc. M2.5 machine screws, standoffs, and nuts)


### Tools and Consumables

- Soldering iron

- Solder

- Fine point hobby knife with safety handle (X-ACTO or similar)

- Solid-Core insulated 22AWG hookup wire (Adafruit
  [#289](https://www.adafruit.com/product/289) or similar)

- Wire strippers (Adafruit [#527](https://www.adafruit.com/product/527) or
  similar)

- Breadboard (Adafruit [#65](https://www.adafruit.com/product/65),
  [#239](https://www.adafruit.com/product/239),
  or similar)

- Soldering Vise (Adafruit [#3197](https://www.adafruit.com/product/3197) or
  similar)

- Flush diagonal cutters
  (Adafruit [#152](https://www.adafruit.com/product/152) or similar)

- Adhesive tape with clean-removable adhesive (Kapton tape, 3M Scotch 35
  electrical tape, blue painter's tape, or whatever)


### Pinouts

| TFT feather | USB Host | ST7789 TFT | Adalogger          |
| ----------- | -------- | ---------- | ------------------ |
|  SCK        |  SCK     |            | SCK (SD)           |
|  MOSI       |  MOSI    |            | MOSI (SD)          |
|  MISO       |  MISO    |            | MISO (SD)          |
|  SDA        |          |            | SDA (RTC)          |
|  SCL        |          |            | SCL (RTC)          |
|  D9         |  IRQ     |            |                    |
|  D10        |  CS      |            | (Not SDCS!)        |
|  D11        |          |            | SDCS (wire jumper) |
|  TFT_CS     |          |  CS        |                    |
|  TFT_DC     |          |  DC        |                    |



## Assemble the Hardware

If you are unfamiliar with soldering headers, you might want to read:

- [Adafruit Guide To Excellent Soldering](https://learn.adafruit.com/adafruit-guide-excellent-soldering/tools)

- [How To Solder Headers](https://learn.adafruit.com/how-to-solder-headers)


### Order of Soldering

1. The TFT Feather, USB Host Featherwing, and Adalogger FeatherWing each come
   with two strips of 16-position male header. Since feather boards have 16
   holes on one side and 12 holes on the other, use your flush cutters to trim
   4 pins off the header strips for the 12-hole sides.

2. Assemble the USB Host FeatherWing with pin headers on a breadboard, then
   solder the headers in place. (The breadboard will align your header pins at
   the right angle relative to the FeatherWing PCB. Once the FeatherWing pins
   are done, you can use the FeatherWing as a jig to help hold the Tripler's
   female headers while you solder them.)

3. Locate a set of female headers from your FeatherWing Tripler kit. Remove the
   USB host FeatherWing from the breadboard, then put female headers onto the
   pins of the USB host FeatherWing.

4. Using the USB host FeatherWing to hold the female headers in place, put the
   female header pins into one of the silkscreened Feather footprints of the
   Tripler. Tape the ends of the USB host FeatherWing to the Tripler, being
   careful not to cover any of the pins.

5. Clamp the Tripler in a vise and solder the female headers in place.

6. Locate another set of female headers from your Tripler kit. Remove the USB
   host FeatherWing from the Tripler, then put the female headers onto the pins
   of the USB host board.

7. Put the female header pins into one of the open silkscreen footprint of your
   Tripler board, then prepare the assembly as before with tape and a vise.

8. Solder the female header pins in place.

9. Repeat the previous 6 steps to solder the third set of female headers in
   place on the third silkscreen footprint of your Tripler.

10. Carefully assemble your ESP32-S3 TFT Feather with header pins on a
    breadboard. Leave the protective film in place to protect the display from
    flux splatter. Solder the header pins in place. You can use the solder wire
    to bend the pull tab of the protective film out of the way so it does not
    touch your soldering iron.

11. Remove the Feather TFT from the breadboard and set it aside.

12. Assemble the Adalogger FeatherWing with pin headers on a breadboard, then
    solder the headers in place.

13. **IMPORTANT:** The Adalogger FeatherWing's default SD card CS pin is D10,
    which conflicts with the CS pin for the USB Host FeatherWing, so the
    Adalogger's SDCS signal needs to be moved with a wire jumper. For more
    details, check out the
    [SD & SPI Pins](https://learn.adafruit.com/adafruit-adalogger-featherwing?view=all#sd-and-spi-pins-2933321)
    section of the Adalogger Learn Guide.

    Locate the Adalogger's SDCS silkscreen label next to the corner of its
    micro SD card slot. Right next to the "CS" of the SDCS label, you should
    see a jumper (two rectangular pads joined by a thin trace) along with a
    round drilled pad. Use a fine point hobby knife to cut the trace between
    the jumper pads with a light scraping motion.

14. Cut and strip a piece of 22AWG insulated hookup wire long enough to reach
    from the SDCS drilled pad over to the inner pad for the Adalogger's D11 pin
    (one pad closer to the battery holder).

15. Clamp the Adalogger board in a vise, solder the jumper wire from the
    bottom of the board, then trim the excess wire ends with flush cutters. The
    end result should look like this:

    ![Adafruit Adalogger FeatherWing with CS jumper wire](adalogger-cs-jumper.jpeg)


### Smoke Test and Final Assembly

1. (optional) Use nylon M2.5 standoffs to mount your Tripler board on a
   backplate, such as a Tamiya Universal Plate, so the board is easier to
   handle without shorts or static discharges.

2. Assemble the Tripler with your Feather TFT, USB Host FeatherWing, and
   Adalogger FeatherWing.

3. Try plugging your board into a USB charger to make sure the LEDs light up.

4. If the LEDs light up, unplug the USB power cable, install the CR1220 coin
   cell in your Adalogger's battery holder, then plug the USB gamepad into the
   Host FeatherWing's USB A port.


## Updating CircuitPython

**NOTE: To update CircuitPython on the ESP32-S3 TFT Feather with 2MB PSRAM and
4MB Flash, you need to use the .BIN file (combination bootloader and
CircuitPython core)**

1. Download the CircuitPython 9.1.3 **.BIN** file from the
   [Feather ESP32-S3 TFT PSRAM](https://circuitpython.org/board/adafruit_feather_esp32s3_tft/)
   page on circuitpython.org

2. Follow the instructions in the
   [Web Serial ESPTool](https://learn.adafruit.com/circuitpython-with-esp32-quick-start/web-serial-esptool)
   section of the "CircuitPython on ESP32 Quick Start" learn guide to update
   your board with CircuitPython 9.1.3. First erasing the board's contents,
   then programming it with the .BIN file.

   If you encounter errors with the Adafruit ESPTool web application, you can
   also try Espressif's [ESP32 Tool](https://espressif.github.io/esptool-js/)
   web application. But, if you do that, be sure to se the "Flash Address"
   field to "0" before using the "Program" button.


## Installing CircuitPython Code

To copy the project bundle files to your CIRCUITPY drive:

1. Download the project bundle .zip file using the button on the Playground
   guide or the attachment download link on the GitHub repo Releases page.

2. Expand the zip file by opening it, or use `unzip` in a Terminal. The zip
   archive should expand to a folder. When you open the folder, it should
   contain a `README.txt` file and a `CircuitPython 9.x` folder.

3. Open the CircuitPython 9.x folder and copy all of its contents to your
   CIRCUITPY drive.

To learn more about copying libraries to your CIRCUITPY drive, check out the
[CircuitPython Libraries](https://learn.adafruit.com/welcome-to-circuitpython/circuitpython-libraries)
section of the
[Welcome to CircuitPython!](https://learn.adafruit.com/welcome-to-circuitpython)
learn guide.


## Running the Code

1. Connect the USB gamepad to the MAX3421E USB Host Featherwing.

2. Plug a computer or charger into the Feather TFT ESP32-S3 USB C port.

CAUTION: This code was tested with an 8BitDo SN30 Pro USB wired gamepad, which
uses the XInput protocol and identifies itself with the vendor and product IDs
of an Xbox 360 gamepad (045e:028e). This code may not work properly with other
gamepads.


## Understanding the Code

1. The `main()` function in `code.py` initializes objects for the data-watch
   display theme, USB gamepad input, the real time clock, and the state
   machine. It also has the main event loop that coordinates gamepad polling
   and clock display updates. The timers for gamepad repeating timer-triggered
   button hold events are part of the main event loop.

2. The `XInputGamepad` class from `gamepad.py` handles low-level USB gamepad
   details.

3. The `SevenSeg` and `CharLCD` classes from `sevenseg.py` and `charldcd.py`
   implement the 7-segment and ASCII character display with
   `displayio.TileGrid` sprites.

4. The `StateMachine` class from `statemachine.py` implements the logic to
   model the behavior of the clocks time display and time setting modes. The
   code for setting the Adalogger's PCF8523 Real Time Clock is in
   `StateMachine.handleDigits`.
