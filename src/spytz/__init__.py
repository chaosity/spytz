'''
datetime.tzinfo timezone definitions generated from the
Olson timezone database:

    ftp://elsie.nci.nih.gov/pub/tz*.tar.gz

See the datetime section of the Python Library Reference for information
on how to use these modules.
'''

# The Olson database is updated several times a year.
OLSON_VERSION = '2014d'
VERSION = '2014.4'  # Switching to pip compatible version numbering.
__version__ = VERSION

__all__ = [
    'timezone', 'timezones', 'utc', 
    'country_timezones', 'country_names',
    'AmbiguousTimeError', 'InvalidTimeError',
    'NonExistentTimeError', 'UnknownTimeZoneError',
    'all_timezones',
    ]

import datetime

from cStringIO import StringIO
from spytz import gaetz

from spytz.exceptions import AmbiguousTimeError
from spytz.exceptions import InvalidTimeError
from spytz.exceptions import NonExistentTimeError
from spytz.exceptions import UnknownTimeZoneError
from spytz.tzinfo import unpickler
from spytz.tzfile import build_tzinfo

"""
Methods to add:
- drop_all_memcache
- update_memcache_multi
- ;pad
- get_all_timezones
- get_country_codes 
"""

from struct import unpack, calcsize # required for is_tzdata()


all_timezones = []
_tzinfo_cache = {}


def set_all_timezones_cache():
    global all_timezones
    all_timezones = gaetz.get_all_timezones()


# Build all_timezones first time the module is imported.
if not all_timezones:
    set_all_timezones_cache()


def timezone(tz):
    if tz.upper() == 'UTC':
        return utc

    try:
        return _tzinfo_cache[tz.encode('US-ASCII')]
    except UnicodeEncodeError:
        # All valid timezones are ASCII.
        raise UnknownTimeZoneError(tz)
    except KeyError:
        # Not in _tzinfo_cache, so fetch and build the timezone.
        if tz in all_timezones:
            # Get from memcache.
            _tzinfo_cache[tz] = build_tzinfo(tz, gaetz.get_tzdata(tz))
        else:
            raise UnknownTimeZoneError(tz)

        return _tzinfo_cache[tz]

def timezones(*tzs):
    return [timezone(tz) for tz in tzs]

def flush_app_cache():
    """ Flushes the appengine cache stores, primarily memcache. Required after
    any timezone data updates to ensure the new timezone is picked up.
    """
    gaetz.flush_cache()
    
    
def flush_local_cache():
    """ Flushes the local module cache stores. Required after any timezone 
    data updates to ensure the new timezone is picked up. Also used for 
    """
    _tzinfo_cache.clear()
    all_timezones = None


def flush_cache():
    """ flushes all cache including module & memcache items. App cache must be
    cleared first so when the local cache is refreshed it picks up the new,
    correct data.
    """
    flush_app_cache()
    flush_local_cache()

def is_tzdata(tzdata):
    head_fmt = '>4sc'
    head_size = calcsize(head_fmt)
    
    try:
        (magic, format) =  unpack(head_fmt, tzdata.read(head_size))
    except:
        return False

    # Make sure it is a tzfile(5) file by casting the string or byte string
    # to an ASCII byte string.
    if magic == 'TZif'.encode('US-ASCII'):
        return True
    else:
        return False

ZERO = datetime.timedelta(0)
HOUR = datetime.timedelta(hours=1)


class UTC(datetime.tzinfo):
    """UTC

    Optimized UTC implementation. It unpickles using the single module global
    instance defined beneath this class declaration.
    """
    zone = "UTC"

    _utcoffset = ZERO
    _dst = ZERO
    _tzname = zone

    def fromutc(self, dt):
        if dt.tzinfo is None:
            return self.localize(dt)
        return super(utc.__class__, self).fromutc(dt)

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO

    def __reduce__(self):
        return _UTC, ()

    def localize(self, dt, is_dst=False):
        '''Convert naive time to local time'''
        if dt.tzinfo is not None:
            raise ValueError('Not naive datetime (tzinfo is already set)')
        return dt.replace(tzinfo=self)

    def normalize(self, dt, is_dst=False):
        '''Correct the timezone information on the given datetime'''
        if dt.tzinfo is self:
            return dt
        if dt.tzinfo is None:
            raise ValueError('Naive time - no tzinfo set')
        return dt.astimezone(self)

    def __repr__(self):
        return "<UTC>"

    def __str__(self):
        return "UTC"


UTC = utc = UTC() # UTC is a singleton


def _UTC():
    """Factory function for utc unpickling.

    Makes sure that unpickling a utc instance always returns the same 
    module global.

    These examples belong in the UTC class above, but it is obscured; or in
    the README.txt, but we are not depending on Python 2.4 so integrating
    the README.txt examples with the unit tests is not trivial.

    >>> import datetime, pickle
    >>> dt = datetime.datetime(2005, 3, 1, 14, 13, 21, tzinfo=utc)
    >>> naive = dt.replace(tzinfo=None)
    >>> p = pickle.dumps(dt, 1)
    >>> naive_p = pickle.dumps(naive, 1)
    >>> len(p) - len(naive_p)
    17
    >>> new = pickle.loads(p)
    >>> new == dt
    True
    >>> new is dt
    False
    >>> new.tzinfo is dt.tzinfo
    True
    >>> utc is UTC is timezone('UTC')
    True
    >>> utc is timezone('GMT')
    False
    """
    return utc
_UTC.__safe_for_unpickling__ = True


def _p(*args):
    """Factory function for unpickling pytz tzinfo instances.

    Just a wrapper around tzinfo.unpickler to save a few bytes in each pickle
    by shortening the path.
    """
    return unpickler(*args)
_p.__safe_for_unpickling__ = True


# Time-zone info based solely on fixed offsets

class _FixedOffset(datetime.tzinfo):

    zone = None # to match the standard pytz API

    def __init__(self, minutes):
        if abs(minutes) >= 1440:
            raise ValueError("absolute offset is too large", minutes)
        self._minutes = minutes
        self._offset = datetime.timedelta(minutes=minutes)

    def utcoffset(self, dt):
        return self._offset

    def __reduce__(self):
        return FixedOffset, (self._minutes, )

    def dst(self, dt):
        return ZERO

    def tzname(self, dt):
        return None

    def __repr__(self):
        return 'pytz.FixedOffset(%d)' % self._minutes

    def localize(self, dt, is_dst=False):
        '''Convert naive time to local time'''
        if dt.tzinfo is not None:
            raise ValueError('Not naive datetime (tzinfo is already set)')
        return dt.replace(tzinfo=self)

    def normalize(self, dt, is_dst=False):
        '''Correct the timezone information on the given datetime'''
        if dt.tzinfo is None:
            raise ValueError('Naive time - no tzinfo set')
        return dt.replace(tzinfo=self)


def FixedOffset(offset, _tzinfos = {}):
    """return a fixed-offset timezone based off a number of minutes.

        >>> one = FixedOffset(-330)
        >>> one
        pytz.FixedOffset(-330)
        >>> one.utcoffset(datetime.datetime.now())
        datetime.timedelta(-1, 66600)
        >>> one.dst(datetime.datetime.now())
        datetime.timedelta(0)

        >>> two = FixedOffset(1380)
        >>> two
        pytz.FixedOffset(1380)
        >>> two.utcoffset(datetime.datetime.now())
        datetime.timedelta(0, 82800)
        >>> two.dst(datetime.datetime.now())
        datetime.timedelta(0)

    The datetime.timedelta must be between the range of -1 and 1 day,
    non-inclusive.

        >>> FixedOffset(1440)
        Traceback (most recent call last):
        ...
        ValueError: ('absolute offset is too large', 1440)

        >>> FixedOffset(-1440)
        Traceback (most recent call last):
        ...
        ValueError: ('absolute offset is too large', -1440)

    An offset of 0 is special-cased to return UTC.

        >>> FixedOffset(0) is UTC
        True

    There should always be only one instance of a FixedOffset per timedelta.
    This should be true for multiple creation calls.

        >>> FixedOffset(-330) is one
        True
        >>> FixedOffset(1380) is two
        True

    It should also be true for pickling.

        >>> import pickle
        >>> pickle.loads(pickle.dumps(one)) is one
        True
        >>> pickle.loads(pickle.dumps(two)) is two
        True
    """
    if offset == 0:
        return UTC

    info = _tzinfos.get(offset)
    if info is None:
        # We haven't seen this one before. we need to save it.

        # Use setdefault to avoid a race condition and make sure we have
        # only one
        info = _tzinfos.setdefault(offset, _FixedOffset(offset))

    return info

FixedOffset.__safe_for_unpickling__ = True
