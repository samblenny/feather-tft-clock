# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# Table of states and state transitions:
#
# | State   | UP     | DOWN   | LEFT    | RIGHT   | A       | B    | START   |
# | ------- | ------ | ------ | ------- | ------- | ------- | ---- | ------- |
# | hhmm    | nop    | nop    | mmss    | mmss    | nop     | hhmm | setHMin |
# | mmss    | nop    | nop    | hhmm    | hhmm    | nop     | hhmm | setHMin |
# | setYr   | year+1 | year-1 | setSec  | setMDay | setMDay | hhmm | hhmm    |
# | setMDay | day+1  | day-1  | setYr   | setHMin | setHMin | hhmm | hhmm    |
# | setHMin | min+1  | min-1  | setMDay | setSec  | setSec  | hhmm | hhmm    |
# | setSec  | sec=0  | sec=0  | setHMin | setYr   | setYr   | hhmm | hhmm    |
#
# Related documentation:
# - https://docs.circuitpython.org/projects/datetime/en/latest/api.html
# - https://docs.circuitpython.org/en/latest/shared-bindings/time/index.html#time.mktime
#
from micropython import const
from time import mktime

from adafruit_datetime import datetime, timedelta


# State Transition Constants (private)
# CAUTION: These values must match row indexes of StateMachine.TABLE
_HHMM    = const(0)
_MMSS    = const(1)
_SetYr   = const(2)
_SetMDay = const(3)
_setHMin = const(4)
_SetSec  = const(5)

# Action Constants (private)
_NOP    = const(6)
_YrInc  = const(7)
_YrDec  = const(8)
_DayInc = const(9)
_DayDec = const(10)
_MinInc = const(11)
_MinDec = const(12)
_Sec00  = const(13)


class StateMachine:

    # Button Press Constants (public)
    # CAUTION: These values must match column indexes of StateMachine.TABLE
    UP    = const(0)
    DOWN  = const(1)
    LEFT  = const(2)
    RIGHT = const(3)
    A     = const(4)
    B     = const(5)
    START = const(6)

    # LookUp Table (private) of actions (including NOP and state transitions)
    # for possible button press events in each of the possible states. NOP is
    # short for "No OPeration", and it means to do nothing.
    _TABLE = (
        # UP      DOWN     LEFT      RIGHT     A         B      START       State
        (_NOP,    _NOP,    _MMSS,    _MMSS,    _NOP,     _HHMM, _setHMin),  # hhmm
        (_NOP,    _NOP,    _HHMM,    _HHMM,    _NOP,     _HHMM, _setHMin),  # mmss
        (_YrInc,  _YrDec,  _SetSec,  _SetMDay, _SetMDay, _HHMM, _HHMM   ),  # setYr
        (_DayInc, _DayDec, _SetYr,   _setHMin, _setHMin, _HHMM, _HHMM   ),  # setMDay
        (_MinInc, _MinDec, _SetMDay, _SetSec,  _SetSec,  _HHMM, _HHMM   ),  # setHMin
        (_Sec00,  _Sec00,  _setHMin,  _SetYr,  _SetYr,   _HHMM, _HHMM   ),  # setSec
    )

    def __init__(self, digits, charLCD, rtc):
        # Save references to character LCD display, digits display, and RTC
        self.digits = digits
        self.charLCD = charLCD
        self.rtc = rtc
        # Start in the state for Clock Mode with hours and minutes sub-mode
        self.state = _HHMM

    def updateDigits(self, st):
        # Update clock digits from current state and struct_time object, st.
        # struct_time(tm_year, tm_mon, tm_mday, tm_hour, tm_min, tm_sec,
        #     tm_wday, tm_yday, tm_isdst)
        _setD = self.digits.setDigits
        _setM = self.charLCD.setMsg
        s = self.state
        if (s == _HHMM):
            # Simple clock like, "12:00"
            _setD('  %02d:%02d' % (st.tm_hour, st.tm_min))
        elif (s == _MMSS):
            # Full date and time like, "2024-09-12 12:00:01"
            _setM('%04d-%02d-%02d' % (st.tm_year, st.tm_mon, st.tm_mday))
            _setD('%02d:%02d:%02d' % (st.tm_hour, st.tm_min, st.tm_sec))
        elif (s == _setHMin) or (s == _SetSec):
            # for setting hours, minutes, or seconds like, "12:00:01"
            _setD('%02d:%02d:%02d' % (st.tm_hour, st.tm_min, st.tm_sec))
        elif (s == _SetYr):
            # for setting the year
            _setD('   %04d' % (st.tm_year))
        elif (s == _SetMDay):
            # for setting the month and day
            _setD('  %02d-%02d' % (st.tm_mon, st.tm_mday))

    def handleGamepad(self, button):
        # Handle a button press event

        # Check lookup table for the response code for this button press event
        if button < UP or button > START:
            print("Button value out of range:", button)
            return
        r = self._TABLE[self.state][button]

        # Cache frequently used names to reduce time used by dictionary lookups
        _rtc = self.rtc
        _setM = self.charLCD.setMsg
        _fromtimestamp = datetime.fromtimestamp

        # The help message for Set Mode uses a special up/down arrows sprite
        # that is mapped in the sprite sheet to ASCII DEL (0x7f)
        SET_HELP     = b"\x7f:+/-  B:Exit  A:OK"
        SET_HELP_SEC = b"\x7f:=00  B:Exit  A:OK"

        # Handle the response code
        # First, check for state transition codes
        if r == _HHMM:
            self.state = r
            _setM(b'')
            _setM(b'', top=False)
        elif r == _MMSS:
            self.state = r
            _setM(b'')
            _setM(b'', top=False)
        elif r == _SetYr:
            self.state = r
            _setM(b'   SET       YEAR')
            _setM(SET_HELP, top=False)
        elif r == _SetMDay:
            self.state = r
            _setM(b'   SET  MONTH-DAY')
            _setM(SET_HELP, top=False)
        elif r == _setHMin:
            self.state = r
            _setM(b'   SET    MINUTES')
            _setM(SET_HELP, top=False)
        elif r == _SetSec:
            self.state = r
            _setM(b'   SET    SECONDS')
            _setM(SET_HELP_SEC, top=False)

        # Second, check for action codes that don't change the state
        elif r == _NOP:
            return

        # Third, check for action codes that modify the RTC date or time
        elif r == _YrInc:
            # Increment Year
            now = _fromtimestamp(mktime(_rtc.datetime))
            _rtc.datetime = (now + timedelta(days=365)).timetuple()
        elif r == _YrDec:
            # Decrement Year
            now = _fromtimestamp(mktime(_rtc.datetime))
            _rtc.datetime = (now + timedelta(days=-365)).timetuple()
        elif r == _DayInc:
            # Increment Day
            now = _fromtimestamp(mktime(_rtc.datetime))
            _rtc.datetime = (now + timedelta(days=1)).timetuple()
        elif r == _DayDec:
            # Decrement Day
            now = _fromtimestamp(mktime(_rtc.datetime))
            _rtc.datetime = (now + timedelta(days=-1)).timetuple()
        elif r == _MinInc:
            # Increment Minute
            now = _fromtimestamp(mktime(_rtc.datetime))
            _rtc.datetime = (now + timedelta(minutes=1)).timetuple()
        elif r == _MinDec:
            # Decrement Minute
            now = _fromtimestamp(mktime(_rtc.datetime))
            _rtc.datetime = (now + timedelta(minutes=-1)).timetuple()
        elif r == _Sec00:
            # Round seconds to nearest minute
            nowST = _rtc.datetime
            now = _fromtimestamp(mktime(nowST))
            sec = nowST.tm_sec
            delta = -(sec) if (sec <= 30) else (60-sec)
            _rtc.datetime = (now + timedelta(seconds=delta)).timetuple()
