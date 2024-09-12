# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# Table of states and state transitions:
#
# | State   | UP     | DOWN   | LEFT | RIGHT | A       | B    | SELECT  |
# | ------- | ------ | ------ | ---- | ----- | ------- | ---- | ------- |
# | hhmm    | nop    | nop    | day  | mmss  | nop     | hhmm | setMin  |
# | mmss    | nop    | nop    | hhmm | year  | nop     | hhmm | setSec  |
# | year    | nop    | nop    | mmss | mon   | nop     | hhmm | setYear |
# | mDay    | nop    | nop    | year | hhmm  | nop     | hhmm | setYear |
# | setYear | year+1 | year-1 | nop  | nop   | setMDay | hhmm | hhmm    |
# | setMDay | day+1  | day-1  | nop  | nop   | setMin  | hhmm | hhmm    |
# | setMin  | min+1  | min-1  | nop  | nop   | setSec  | hhmm | hhmm    |
# | setSec  | sec=0  | sec=0  | nop  | nop   | setYear | hhmm | hhmm    |
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
_Yr      = const(2)
_MDay    = const(3)
_SetYr   = const(4)
_SetMDay = const(5)
_SetMin  = const(6)
_SetSec  = const(7)

# Action Constants (private)
_NOP    = const(8)
_YrInc  = const(9)
_YrDec  = const(10)
_DayInc = const(11)
_DayDec = const(12)
_MinInc = const(13)
_MinDec = const(14)
_Sec00  = const(15)


class StateMachine:

    # Button Press Constants (public)
    # CAUTION: These values must match column indexes of StateMachine.TABLE
    UP     = const(0)
    DOWN   = const(1)
    LEFT   = const(2)
    RIGHT  = const(3)
    A      = const(4)
    B      = const(5)
    SELECT = const(6)

    # LookUp Table (private) of actions (including NOP and state transitions)
    # for possible button press events in each of the possible states
    _TABLE = (
        # UP      DOWN     LEFT   RIGHT  A         B      SELECT     State
        (_NOP,    _NOP,    _MDay, _MMSS, _NOP,     _HHMM, _SetMin),  # hhmm
        (_NOP,    _NOP,    _HHMM, _Yr,   _NOP,     _HHMM, _SetSec),  # mmss
        (_NOP,    _NOP,    _MMSS, _MDay, _NOP,     _HHMM, _SetYr ),  # year
        (_NOP,    _NOP,    _Yr,   _HHMM, _NOP,     _HHMM, _SetYr ),  # mDay
        (_YrInc,  _YrDec,  _NOP,  _NOP,  _SetMDay, _HHMM, _HHMM  ),  # setYr
        (_DayInc, _DayDec, _NOP,  _NOP,  _SetMin,  _HHMM, _HHMM  ),  # setMDay
        (_MinInc, _MinDec, _NOP,  _NOP,  _SetSec,  _HHMM, _HHMM  ),  # setMin
        (_Sec00,  _Sec00,  _NOP,  _NOP,  _SetYr,   _HHMM, _HHMM  ),  # setSec
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
        s = self.state
        if (s == _HHMM) or (s == _SetMin):
            _setD('%02d:%02d' % (st.tm_hour, st.tm_min))
        elif (s == _MMSS) or (s == _SetSec):
            _setD('%02d:%02d' % (st.tm_min, st.tm_sec))
        elif (s == _Yr) or (s == _SetYr):
            _setD(' %04d' % (st.tm_year))
        elif (s == _MDay) or (s == _SetMDay):
            _setD('%02d %02d' % (st.tm_mon, st.tm_mday))

    def handleGamepad(self, button):
        # Handle a button press event

        # Check lookup table for the response code for this button press event
        if button < UP or button > SELECT:
            print("Button value out of range:", button)
            return
        r = self._TABLE[self.state][button]

        # Cache frequently used functions
        setD = self.digits.setDigits
        setMsg = self.charLCD.setMsg

        # The help message for Set Mode uses a special up/down arrows sprite
        # that is mapped in the sprite sheet to ASCII DEL (0x7f)
        SET_HELP = b"\x7f:+/-  B:Exit  A:OK"

        # Handle the response code
        # First, check for state transition codes
        if r == _HHMM:
            self.state = r
            setMsg(b'')
            setMsg(b'', top=False)
        elif r == _MMSS:
            self.state = r
            setMsg(b'         SECONDS')
        elif r == _Yr:
            self.state = r
            setMsg(b'            YEAR')
        elif r == _MDay:
            self.state = r
            setMsg(b'       MONTH DAY')
        elif r == _SetYr:
            self.state = r
            setMsg(b'   SET      YEAR')
            setMsg(SET_HELP, top=False)
        elif r == _SetMDay:
            self.state = r
            setMsg(b'   SET MONTH DAY')
            setMsg(SET_HELP, top=False)
        elif r == _SetMin:
            self.state = r
            setMsg(b'   SET   MINUTES')
            setMsg(SET_HELP, top=False)
        elif r == _SetSec:
            self.state = r
            setMsg(b'   SET   SECONDS')
            setMsg(SET_HELP, top=False)

        # Second, check for action codes that don't change the state
        elif r == _NOP:
            return
        elif r == _YrInc:
            now = datetime.fromtimestamp(mktime(self.rtc.datetime))
            self.rtc.datetime = (now + timedelta(days=365)).timetuple()
        elif r == _YrDec:
            now = datetime.fromtimestamp(mktime(self.rtc.datetime))
            self.rtc.datetime = (now + timedelta(days=-365)).timetuple()
        elif r == _DayInc:
            now = datetime.fromtimestamp(mktime(self.rtc.datetime))
            self.rtc.datetime = (now + timedelta(days=1)).timetuple()
        elif r == _DayDec:
            now = datetime.fromtimestamp(mktime(self.rtc.datetime))
            self.rtc.datetime = (now + timedelta(days=-1)).timetuple()
        elif r == _MinInc:
            now = datetime.fromtimestamp(mktime(self.rtc.datetime))
            self.rtc.datetime = (now + timedelta(minutes=1)).timetuple()
        elif r == _MinDec:
            now = datetime.fromtimestamp(mktime(self.rtc.datetime))
            self.rtc.datetime = (now + timedelta(minutes=-1)).timetuple()
        elif r == _Sec00:
            nowST = self.rtc.datetime
            now = datetime.fromtimestamp(mktime(nowST))
            sec = nowST.tm_sec
            delta = -(sec) if (sec <= 30) else (60-sec)
            self.rtc.datetime = (now + timedelta(seconds=delta)).timetuple()
