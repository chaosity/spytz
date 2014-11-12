#!/usr/bin/env python
#
# Copyright (C) 2012 - 2014 Chaosity Enterprises Pty Ltd. All Rights Reserved

# App Engine Modules
from google.appengine.ext import ndb
from google.appengine.api import memcache

from cStringIO import StringIO

#from pytz.exceptions import AmbiguousTimeError
#from pytz.exceptions import InvalidTimeError
#from pytz.exceptions import NonExistentTimeError
from spytz.exceptions import UnknownTimeZoneError

from datetime import datetime
import logging

# For debugging exceptions
import sys

_all_tz_cache = []

# Memcache paramters
MC_NAMESPACE = '--spytz--'
MC_STORE_TIME = 86400 # 1 day
MC_ALLTZS = '_alltzs_'

class SpytzData(ndb.Model):
    version = ndb.StringProperty() # Olson DB version.
    checked_on = ndb.DateTimeProperty() # Date last checked for an update.
    updated_on = ndb.DateTimeProperty() # Date last updated.
    all_tz = ndb.TextProperty(repeated=True) # comma separated list of all timezones

    datastore_id = 1 # only store one entry, keep the id here.

    @classmethod
    def get_spytz_data(cls):
        # get the existing data from the database.
        data = None
        try:
            obj = ndb.Key(cls, cls.datastore_id)
            data = obj.get(use_memcache=False, use_cache=False)
        except:
            # Something went wrong...
            logging.warning('SPYTZ: Error while trying to fetch Spytz data.')

        if not data:
            logging.warning('SPYTZ: Fresh install, creating Spytz Metadata.')
            data = SpytzData(id = cls.datastore_id,
                             version = None,
                             checked_on = datetime.now(),
                             updated_on = datetime.now(),
                             all_tz = [])
            data.put(use_memcache=False, use_cache=False)
        
        return data 

class TimeZoneData(ndb.Model):
    # TODO: test this the CPU impact of compressed vs uncompressed
    data = ndb.BlobProperty(required=True) #,compressed=True) # Binary TZ data
    country_code = ndb.StringProperty() # Olson DB version
    country = ndb.StringProperty() # country code for the TZ
    coords = ndb.StringProperty()

    @classmethod
    def add_or_update(cls, timezone, tzdata, country, version):
        """Creates or replaxes a timezone entry in the datastore, using
        put_async ndb method.
        Returns a 'future' object if successful, 'None' if not successful.
        """
        tz = cls.fetch(timezone)
        
        if tz:
            tz.data = tzdata
            tz.country = country
            tz.version = version
        else:
            # Create a new Region entity.
            tz = TimeZoneData(id = timezone,
                              data = tzdata,
                              country = country,
                              version = version)

        try:

            future = tz.put_async()
        except:
            logging.error('Error while trying to store timezone "{}"'.format(timezone))
            return None

        return future

    @classmethod
    def fetch_tz(cls, timezone):
        tz_data = memcache.get(timezone,
                               namespace=MC_NAMESPACE)
        
        if tz_data is not None:
            # Return the memcache data
            return tz_data
        else:
            # Memcache key not found, so force a reload.
            tz_obj = cls.fetch(timezone)
            if tz_obj is None:
                logging.error("SPYTZ: timezone '{}' does not exist!".format(timezone))
                raise UnknownTimeZoneError
            tz_data = tz_obj.data
            # Add the keys / data to memcache.
            memcache.set(timezone, tz_data, MC_STORE_TIME, namespace=MC_NAMESPACE)

        # Return the memcache data
        return tz_data

    @classmethod
    def fetch(cls, timezone):
        try:
            # Fetch the object from the datastore
            obj = ndb.Key(cls, timezone)
            result = obj.get(use_memcache=False, use_cache=False)
        except:
            # Key is of an invalid type
            logging.error('Error while trying to fetch timezone "{}"'.format(timezone))
        else:
            # Return the Region object
            return result

    @classmethod
    def update_cache(cls, timezones):
        pass
        
    @classmethod
    def _get_country_codes(cls):
        TimeZone.all().order('country')

    #def __str__(self):
    #    return "{} timezones".format(self._number_timezones())

def get_installed_version(update=False):
    spytz_data = SpytzData.get_spytz_data()
    
    if update:
        spytz_data.checked = datetime.now()
        spytz_data.put(use_memcache=False, use_cache=False)

    return spytz_data.version


def update_metadata(new_version, all_tzs=None):
    """ Applies the new version and current date/time to the 'updated_on'
    timestamp property. If a list passed in for all_tzs, this will be used to
    update the all_tzs property,
    """
    spytz_data = SpytzData.get_spytz_data()
    spytz_data.version = new_version
    spytz_data.updated_on = datetime.now()
    
    if all_tzs:
        spytz_data.all_tz = all_tzs

    spytz_data.put(use_memcache=False, use_cache=False)
    
def flush_cache():
    # Get the current list of timezones (in case some are deleted).
    all_tzs = get_all_timezones()

    # And remove them.
    memcache.delete_multi(all_tzs, namespace=MC_NAMESPACE)

    # And then delete and reload all_tzs again.
    memcache.delete(MC_ALLTZS, namespace=MC_NAMESPACE)
    all_tzs = get_all_timezones()

def get_all_timezones():
    """Returns a list of all the timezones in the datastore. Checks
    Memcache first, datastore second.
    """
    # Get the memcache data first.
    tz_list = memcache.get(MC_ALLTZS, namespace=MC_NAMESPACE)

    if tz_list:
        # Make the string a list before returning it.
        return tz_list.split(',')
    else:
        # Memcache key not found, so reload the data.
        try:
            # Fetch the object from the datastore.
            obj = SpytzData.get_spytz_data()
            tz_list = obj.all_tz
        except:
            # Key is of an invalid type
            logging.error('SPYTZ: Error while trying to fetch SpytzData.all_timezones property')
            return []

        # Update memcache.
        memcache.set(MC_ALLTZS, ','.join(tz_list), namespace=MC_NAMESPACE)
        # Return all timezones.
        return tz_list

def delete_all_data():
    """Deletes all timezones from datastore.
    """
    # Get a list of all the timezones in the datastore.
    tz_all = get_all_timezones()
    
    futures = ndb.delete_multi_async([ndb.Key(TimeZoneData, x) 
                                      for x in tz_all],
                                     use_memcache=False, use_cache=False)

    TimeZoneData.remove_from_cache(tz_all)

    # Delete the SpytzData timezone information.
    spytz_data = SpytzData.get_spytz_data()
    
    if spytz_data:
        spytz_data.all_tz = []
        spytz_data.put(use_memcache=False, use_cache=False)

    # And delete the SpytzData memcache object.
    memcache.delete(MC_ALLTZS, namespace=MC_NAMESPACE)

    ndb.Future.wait_all(futures)

    # Return the list of timezones deleted.
    return tz_all

def get_tz_obj(timezone):
    tz_obj = TimeZoneData.fetch(timezone)
    return tz_obj

def get_tzdata(timezone):
    tz_data = memcache.get(timezone, namespace=MC_NAMESPACE)
    
    if not tz_data:
        # Memcache key not found, so force a reload.
        tz_obj = TimeZoneData.fetch(timezone)
        if tz_obj is None:
            logging.error("SPYTZ: timezone '{}' does not exist!".format(timezone))
            raise UnknownTimeZoneError

        tz_data = tz_obj.data
        # Add the keys / data to memcache.
        memcache.set(timezone, tz_data, MC_STORE_TIME, namespace=MC_NAMESPACE)

    # Return the memcache data
    return StringIO(tz_data)
