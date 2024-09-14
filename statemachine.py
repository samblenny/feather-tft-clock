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
# | setMDay | day+1  | day-1  | setYr   | setHour | setHour | hhmm | hhmm    |
# | setHour | hour+1 | hour-1 | setMDay | setHMin | setHMin | hhmm | hhmm    |
# | setHMin | min+1  | min-1  | setHour | setSec  | setSec  | hhmm | hhmm    |
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
_SetHour = const(4)
_SetHMin = const(5)
_SetSec  = const(6)

# Action Constants (private)
_NOP    = const(7)
_YrInc  = const(8)
_YrDec  = const(9)
_DayInc = const(10)
_DayDec = const(11)
_HrInc  = const(12)
_HrDec  = const(13)
_MinInc = const(14)
_MinDec = const(15)
_Sec00  = const(16)


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
        (_NOP,    _NOP,    _MMSS,    _MMSS,    _NOP,     _HHMM, _SetHMin),  # hhmm
        (_NOP,    _NOP,    _HHMM,    _HHMM,    _NOP,     _HHMM, _SetHMin),  # mmss
        (_YrInc,  _YrDec,  _SetSec,  _SetMDay, _SetMDay, _HHMM, _HHMM   ),  # setYr
        (_DayInc, _DayDec, _SetYr,   _SetHour, _SetHour, _HHMM, _HHMM   ),  # setMDay
        (_HrInc,  _HrDec,  _SetMDay, _SetHMin, _SetHMin, _HHMM, _HHMM   ),  # setHour
        (_MinInc, _MinDec, _SetHour, _SetSec,  _SetSec,  _HHMM, _HHMM   ),  # setHMin
        (_Sec00,  _Sec00,  _SetHMin, _SetYr,   _SetYr,   _HHMM, _HHMM   ),  # setSec
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
        elif (s == _SetHour) or (s == _SetHMin) or (s == _SetSec):
            # for setting hours, minutes, or seconds like, "12:00:01"
            _setD('%02d:%02d:%02d' % (st.tm_hour, st.tm_min, st.tm_sec))
        elif (s == _SetYr):
            # for setting the year
            _setD('   %04d' % (st.tm_year))
        elif (s == _SetMDay):
            # for setting the month and day
            _setD('  %02d-%02d' % (st.tm_mon, st.tm_mday))

    def handleGamepad(self, button, repeat):
        # Handle a button press event
        # args:
        # - button: one of the button constants
        # - repeat: True if this is a hold-time triggered repeating event

        # Check lookup table for the response code for this button event
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
        elif r == _SetHour:
            self.state = r
            _setM(b'   SET       HOUR')
            _setM(SET_HELP, top=False)
        elif r == _SetHMin:
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
        else:
            # To avoid surprising things like unintentionally changing the day
            # when you're trying to set the minutes (e.g. crossing midnight),
            # we need a struct_time object. But, to do math with time deltas in
            # a way that accounts for leap years, days per month, etc., we need
            # a datetime object. So, make both:
            st = _rtc.datetime                  # struct_time
            now = _fromtimestamp(mktime(st))    # datetime
            # Unpack the struct_time with shorter names
            (year, month, day) = (st.tm_year, st.tm_mon, st.tm_mday)
            (hour, min_, sec) = (st.tm_hour, st.tm_min, st.tm_sec)

            if r == _YrInc:
                # Increment Year
                n = 5 if repeat else 1
                if year + n > 2037:
                    # Don't go above 2037 because attempting to do so causes
                    # a CircuitPython long int overflow error. Note that
                    # 19 January 2038 is the Unix time 32-bit overflow date.
                    # see https://en.wikipedia.org/wiki/Year_2038_problem
                    n = 2037 - year
                _rtc.datetime = (now + timedelta(days=(n*365))).timetuple()
            elif r == _YrDec:
                # Decrement Year
                n = -5 if repeat else -1
                if year + n < 2001:
                    # Don't go below 2001 because adafruit_pcf8523 doesn't like
                    # years below 2000
                    n = 2001 - year
                _rtc.datetime = (now + timedelta(days=(n*365))).timetuple()
            elif r == _DayInc:
                # Increment Day
                n = 10 if repeat else 1
                if (month == 12) and (day + n > 31):
                    # Do not go past December 31 (avoid changing year)
                    n = 31 - day
                _rtc.datetime = (now + timedelta(days=n)).timetuple()
            elif r == _DayDec:
                # Decrement Day
                n = -10 if repeat else -1
                if (month == 1) and (day + n < 1):
                    # Do not go past January 1 (avoid changing year)
                    n = 1 - day
                _rtc.datetime = (now + timedelta(days=n)).timetuple()
            elif r == _HrInc:
                # Increment Hour
                n = 4 if repeat else 1
                if hour + n > 23:
                    # Do not go past 23:xx (avoid changing day)
                    n = 23 - hour
                _rtc.datetime = (now + timedelta(hours=n)).timetuple()
            elif r == _HrDec:
                # Decrement Hour
                n = -4 if repeat else -1
                if hour + n < 0:
                    # Do not go past 00:xx (avoid changing day)
                    n = 0 - hour
                _rtc.datetime = (now + timedelta(hours=n)).timetuple()
            elif r == _MinInc:
                # Increment Minute
                n = 10 if repeat else 1
                if (hour == 23) and (min_ + n > 59):
                    # Do not go past 23:59 (avoid changing day)
                    n = 59 - min_
                _rtc.datetime = (now + timedelta(minutes=n)).timetuple()
            elif r == _MinDec:
                # Decrement Minute
                n = -10 if repeat else -1
                if (hour == 0) and (min_ + n < 0):
                    # Do not go past 00:00 (avoid changing day)
                    n = 00 - min_
                _rtc.datetime = (now + timedelta(minutes=n)).timetuple()
            elif r == _Sec00:
                # Round seconds to nearest minute
                delta = -(sec) if (sec <= 30) else (60-sec)
                _rtc.datetime = (now + timedelta(seconds=delta)).timetuple()
