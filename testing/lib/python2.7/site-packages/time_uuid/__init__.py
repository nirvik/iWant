import sys
import uuid
import datetime
import time, calendar
import threading
import random
if sys.version_info > (3,):
    long = int


def utctime():
    """
    Generate a timestamp from the current time in UTC. Returns exactly
    the same thing as :py:func`time.time` but with a UTC offset instead
    of a local one

    :returns: a timestamp
    :rtype: float
    """
    d = datetime.datetime.utcnow()
    return mkutime(d)

def mkutime(d):
    """
    Generate a UTC timestamp from the datetime object.

    :param d: a :py:class:`datetime` object
    :type d: datetime
    """
    return float(calendar.timegm(d.timetuple())) + float(d.microsecond) / 1e6


class IncreasingMicrosecondClock(object):
    """
    A clock that returns a new timestamp value unique across all threads,
    acheived by locking a mutex each call and checking the previous value.
    """
    def __init__(self, timestamp_factory=utctime, mutex=threading.Lock):
        self.timestamp_factory = timestamp_factory
        self.mutex = mutex()
        self.time = timestamp_factory()

    def __call__(self):
        with self.mutex:
            new_time = self.timestamp_factory()
            if new_time > self.time:
                self.time = new_time
            else:
                self.time += .000001
            return self.time


class TimeUUID(uuid.UUID):
    """
    A class that makes dealing with time and V1 UUIDs much easiser. Offers
    accurate comparison (compares accurately with other TimeUUIDs and UUIDv1),
    a way to get TimeUUIDs with UTC-timestamps (instead of the default
    localtime), an easy way to get the UTC datetime object from it, and
    default encoding and decoding methods.
    """
    timestamp_factory = IncreasingMicrosecondClock()

    def __repr__(self):
        return u"TimeUUID('{}')".format(super(TimeUUID, self).__str__())

    def __cmp__(self, other):
        # if other isn't a UUID, do whatever it would do WWUUIDD?
        if not isinstance(other, uuid.UUID):
            return super(TimeUUID, self).__cmp__(other)
        if self.version == 1 and other.version == 1:
            if self.time == other.time:
                return super(TimeUUID, self).__cmp__(other)
            else:
                return cmp(self.time, other.time)
        else:
            return super(TimeUUID, self).__cmp__(other)

    def get_datetime(self):
        return datetime.datetime.utcfromtimestamp(self.get_timestamp())

    def get_timestamp(self):
        try:
            t = self.get_time()
        except AttributeError:
            t = self.time
        return (t - long(0x01b21dd213814000)) / 1e7

    @classmethod
    def upgrade(cls, other):
        if other is None:
            return other
        elif isinstance(other, cls):
            return other
        elif isinstance(other, uuid.UUID):
            return cls(hex=other.hex)
        raise TypeError("Cannot upgrade %s because it is not a uuid.UUID "
                        "(it is a '%s')" % (other, other.__class__.__name__))

    @classmethod
    def with_utc(cls, d, randomize=True, lowest_val=False):
        """
        Create a TimeUUID with any datetime in UTC. Only use this if you are sure
        you are creating your datetime objects properly and can predict how
        the :py:class:`TimeUUID` will sort (if that is at all necessary).

        See :py:meth:`with_timestamp` for a description of how `randomize` and
        `lowest_val` arguments work.

        :param d: A datetime object
        :type d: datetime

        :returns: A TimeUUID object
        :type d: TimeUUID
        """
        return cls.with_timestamp(mkutime(d), randomize=randomize, 
                                  lowest_val=lowest_val)

    @classmethod
    def with_utcnow(cls, randomize=True):
        """
        Create a TimeUUID with the current datetime in UTC. Every TimeUUID
        generated this way, on this machine, will supersede the TimeUUID generated
        before it, by use of a mutex.

        :param randomize: Whether or not to randomize the other bits in the UUID.
        Defaults to `True`
        :type randomize: bool

        :returns: A TimeUUID object
        :rtype: TimeUUID
        """
        return cls.with_timestamp(cls.timestamp_factory(), randomize=randomize)

    @classmethod
    def convert(cls, value, randomize=True, lowest_val=False):
        """
        Try to convert a number of different types to a TimeUUID. Works for
        datetimes, ints (which it treats as timestamps) and UUIDs.

        See :py:meth:`with_timestamp` for descriptions of the `randomize` and
        `lowest_val` arguments.

        :param value: An instance of UUID, TimeUUID, datetime or timestamp
            int or float

        :returns: A TimeUUID object
        :rtype: TimeUUID
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, uuid.UUID):
            return cls.upgrade(value)
        if isinstance(value, datetime.datetime):
            return cls.with_timestamp(mkutime(value), randomize=randomize,
                lowest_val=lowest_val)
        if isinstance(value, (int, long, float)):
            return cls.with_timestamp(value, randomize=randomize,
                lowest_val=lowest_val)
        raise ValueError("Sorry, I don't know how to convert {} to a "
                         "TimeUUID".format(value))

    @classmethod
    def with_timestamp(cls, timestamp, randomize=True, lowest_val=False):
        """
        Create a TimeUUID with any timestamp. Be sure that the timestamp is 
        created with the correct offset. If you are using :py:func:`time.time`
        be sure to know that in python, it may be offset by your machine's
        time zone!

        :param timestamp: A timestamp, like that returned by :py:func:`utctime`
            or py:func:`time.time`.
        :type timestamp: float
        :param randomize: will create a UUID with randomish bits. This overrides
            it's counterpart: `lowest_val` If randomize is False and `lowest_val`
            is False, it will generate a UUID with the highest possible clock seq
            for the same timestamp, otherwise generating a UUID with the *lowest*
            possible clock seq for the same timestamp. Defaults to `True`
        :type randomize: bool
        :param lowest_val: will create a UUID with the lowest possible clock seq if
            randomize is False if set to True, otherwise generating the highest
            possible. Defaults to `False`
        :type lowest_val: bool

        :returns: A TimeUUID object
        :rtype: TimeUUID
        """
        ns = timestamp * 1e9
        ts = int(ns // 100) + long(0x01b21dd213814000)
        time_low = ts & long(0xffffffff)
        time_mid = (ts >> 32) & long(0xffff)
        time_hi_version = (ts >> long(48)) & long(0x0fff)
        if randomize:
            cs = random.randrange(1<<long(14))
            clock_seq_low = cs & long(0xff)
            clock_seq_hi_variant = (cs >> long(8)) & long(0x3f)
            node = uuid.getnode()
        else:
            if lowest_val: # uuid with lowest possible clock value
                clock_seq_low = 0 & long(0xff)
                clock_seq_hi_variant = 0 & long(0x3f)
                node = 0 & long(0xffffffffffff) # 48 bits
            else: # UUID with highest possible clock value
                clock_seq_low = long(0xff)
                clock_seq_hi_variant = long(0x3f)
                node = long(0xffffffffffff) # 48 bits
        return cls(
            fields=(time_low, time_mid, time_hi_version,
                    clock_seq_hi_variant, clock_seq_low, node),
            version=1
        )
