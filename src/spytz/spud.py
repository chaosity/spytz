"""
Auto-update.
"""
# Spytz module imports
import spytz
from spytz import gaetz

# Google API imports
try:
    from google.appengine.api import urlfetch
    from google.appengine.ext import ndb
except:
    pass

# Used by SpytzReleaseFile
import json

# Used by SpytzUpdateFile()
import hashlib
import tarfile
import contextlib
from cStringIO import StringIO

# Monitoring & Logging
import time
import logging

# Auto update host info.
SPYTZ_UPDATE_URL = 'http://spytz-app.appspot.com/releases/'
#SPYTZ_UPDATE_URL = 'http://localhost:9003/releases/'

SPYTZ_RELEASE_FILE = 'releases.json'


class SpytzUpdateError(Exception):
    pass

class InvalidVersionError(SpytzUpdateError):
    pass

class InvalidUrlError(SpytzUpdateError):
    pass

class InvalidFileError(SpytzUpdateError):
    pass



class SpytzReleaseInfo(object):
    def __init__(self, filestr=None, version='latest'):
        if filestr is None:
            raise InvalidFileError

        # Convert the file to a usable dictionary.
        jdata = json.loads(filestr)
        
        if jdata is None:
            raise InvalidFileError

        # Work out which version we're trying to install.
        if version == 'latest':
            self.version = jdata['latest']
        else:
            self.version = version 

        # Get the latest version.
        self.latest = jdata['latest']
        
        # Get a list of all available versions.
        self.all_versions = jdata['releases'].keys()
        
        # Check the version we want is available to install.
        if self.version not in self.all_versions:
            # version passed does not exist.
            raise InvalidVersionError

        rel_info = jdata['releases'][self.version]
        self.filename = rel_info['filename']
        self.hashtype = rel_info['hashtype']
        self.hash = rel_info['hash']


""" We don't want too much functionality in the SpytzUpdateFile class. A 
SpytzUpdateFile instance must:
- store the file object as a string. Will be parsed as StringIO
- calculate a hash of the file
- raise exceptions if it is unable to determine: version, alltzs, meta
- determine if a file is an actual tzfile
- iterate (yield) through all timezone files.

from spytz import spud
f = open('releases\spytz-zoneinfo-2014.4.tar.gz', 'rb')
sf = spud.SpytzUpdateFile(f.read())
b = sf.next_tz()
print b.next()

print sf.hash
print sf.alltzs
print sf.next_tz()
"""

class SpytzUpdateFile():
    def __init__(self, fileobj=None, hashtype='sha1'):
        """ 'fileobj' must be a string representation of a tar archive file
        object - not a file, file object, filename, handle or pointer.
        
        Can be instantiated with:
            open(os.path.join(root, filename), "rb") as fo:
                spytzfile = SpytzUpdateFile(fo.read())
        """
        if fileobj is None:
            raise InvalidFileError

        self.fileobj = fileobj

        self.hashtype = hashtype
        self.hash = self._calc_hash(hashtype)
        
        with tarfile.open(fileobj=StringIO(self.fileobj)) as tar:
            # If file doesn't exist tarfile raises a KeyError
            self.version = tar.extractfile('VERSION').readline()
            
            with contextlib.closing(tar.extractfile('iso3166.tab')) as fo:
                cc = {d[0]: d[1] for d in [l.strip().split(None, 1)
                                           for l in fo
                                           if not l.startswith("#")]
                      }
            
            with contextlib.closing(tar.extractfile('zone.tab')) as fo:
                zones = [l.strip().split(None, 4)[:3]
                         for l in fo if not l.startswith("#")]
            
            self._tzmeta = {z[2]: {'country': z[0],
                                   'country_code': cc[z[0]],
                                   'coords': z[1]} for z in zones}

    def next_tz(self):
        """ Iterator to loop through timezones in the tarfile, returning data
        as a dictionary. Adds associated metadata to the returned dictionary.
        dict = {'tz': <timezone name>,
                'tzinfo': <data>,
                'country': <country>,
                'country_code': <country_code>,
                'coords': <geo coordinates>'
                }
        """

        with tarfile.open(fileobj=StringIO(self.fileobj)) as tar:
            for tzname in tar.getnames():
                if spytz.is_tzdata(tar.extractfile(tzname)):
                    # Link in the metadata.
                    d = self._tzmeta.get(tzname, {})
                    tz = {'name': tzname,
                          'data': tar.extractfile(tzname).read(),
                          'country': d.get('country', None),
                          'country_code': d.get('country_code', None),
                          'coords': d.get('coords', None)
                          }
                    yield tz

    def _get_all_tzs(self, fileobj):
        return [l.rstrip() for l in fileobj]
    
    def _calc_hash(self, hashtype):
        """ Performs a hash calculation, determine by hashtype. Will force a 
        sha1 hash calculation if None or an invalid type is passed.
        """
        if hashtype == 'md5':
            return hashlib.md5(self.fileobj).hexdigest()
        else:
            # Perform a sha1 hash calc by default.
            return hashlib.sha1(self.fileobj).hexdigest()


def download_file(url):
    if url is None:
        raise InvalidUrlError

    logging.debug('SPYTZ: Downloading remote file {}.'.format(url))
    try:
        result = urlfetch.fetch(url)
    except:
        logging.error('SPYTZ: Could not download remote file.')
        return None
    
    if result.status_code == 200:
        if result.content:
            logging.info('SPYTZ: Downloaded remote file. {} bytes received.'.
                         format(len(result.content)))
            return result.content
        else:
            logging.error('SPYTZ: Error downloading or accessing remote file.')
            raise InvalidFileError
    else:
        raise InvalidUrlError


def update(install_version='latest', force_refresh=False):
    """Updates the timezone data in the datastore. Process is:
            1. Check if the remote 'latest' version is different to 
               local 'current'.
            2. Ensure the checksums match for the downloaded file and
               its reference.
            3. Load the downloaded zipfile into memory.
            4. Open and parse the country and country timezones tab 
               files.
            5. Process each of the timezone records in the zip archive.
            6. Add or update the timezone records in the datastore.
            7. Update the Spytz Metadata.
            8. Delete deprecated timezones from the datastore.
    """
    # Start the timer.
    _ts = time.time()
    
    logging.info("SPYTZ: Running automated update process.")
    
    # Download the release information and load it.
    url = SPYTZ_UPDATE_URL + SPYTZ_RELEASE_FILE
    logging.info('SPYTZ: downloading file {}.'.format(url))
    rel_info = SpytzReleaseInfo(download_file(url))

    current_version = gaetz.get_installed_version(update=True)

    # Update checked date.
    logging.info("SPYTZ: Installed version is '{}'".format(current_version))
    logging.info("SPYTZ: Latest available is '{}'.".format(rel_info.latest))
    logging.info("SPYTZ: We want to install '{}'.".format(rel_info.version))
    logging.info("SPYTZ: Force refresh is: {}".format(force_refresh))

    # If versions match and we're not forcing a refresh, skip the update.
    if current_version == install_version and force_refresh is False:
        logging.info("SPYTZ: No need to update timezones. Exiting.")
        logging.info("SPYTZ: Completed update process in {:4.4f}.".
                     format(time.time() - _ts))
        return False

    # Download the update file from the remote server.
    df = SPYTZ_UPDATE_URL + rel_info.filename
    sf = SpytzUpdateFile(download_file(df))
    
    logging.info("SPYTZ: Downloaded file SHA is '{}'.".format(sf.hash))
    logging.info("SPYTZ: Reference SHA is '{}'.".format(rel_info.hash))

    # Make sure the checksums match, if not, raise an error.
    if not sf.hash == rel_info.hash:
        logging.error('SPYTZ: Checksums do not match. Aborting.')
        logging.info("SPYTZ: Completed update process in {:4.4f}.".
                     format(time.time() - _ts))
        raise InvalidFileError

    all_tz_current = gaetz.get_all_timezones()
    all_tz_objs_current = ndb.get_multi([ndb.Key(gaetz.TimeZoneData, tz) 
                                         for tz in all_tz_current])

    all_tz_updated = []
    all_tz_not_updated = []

    tz_upd = []
    tz_del = []

    # next_tz() is a generator, so we can loop through it.
    for tz in sf.next_tz():
        obj = None
        for item in all_tz_objs_current:
            if item.key.id() == tz['name']:
                obj = item
                all_tz_objs_current.remove(item)

        if obj:
            if force_refresh is True or obj.data != tz['data']:
                obj.data = tz['data']
                obj.country = tz['country']
                obj.country_code = tz['country_code']
                obj.coords = tz['coords']
            else:
                # break this loop so we don't add obj to the list below.
                all_tz_not_updated.append(obj.key.id())
                continue
        else:
            # Create a new timezone entity.
            obj = gaetz.TimeZoneData(id = tz['name'],
                                     data = tz['data'],
                                     country = tz['country'],
                                     country_code = tz['country_code'],
                                     coords = tz['coords'])

        all_tz_updated.append(obj.key.id())
        tz_upd.append(obj)

    all_tzs =  all_tz_updated + all_tz_not_updated
    all_tz_deleted = list(set(all_tz_current) - set(all_tzs))
    
    # Determine the difference for timezones that no longer exist (unlikely).
    for tz in all_tz_deleted:
        if tz:
            logging.info("SPYTZ: Deleting tz {}.".format(tz))
            tz_del.append(gaetz.get_tz_obj(tz))

    upd_futures = ndb.put_multi_async(tz_upd,
                                      use_memcache=False,
                                      use_cache=False,
                                      read_policy=ndb.EVENTUAL_CONSISTENCY)
    
    del_futures = ndb.delete_multi_async(tz_del,
                                         use_memcache=False,
                                         use_cache=False,
                                         read_policy=ndb.EVENTUAL_CONSISTENCY)
    
    logging.info("SPYTZ: Skipped {} matching timezones.".format(len(all_tz_not_updated)))
    logging.info("SPYTZ: Updated {} timezones.".format(len(all_tz_updated)))
    logging.info("SPYTZ: Deleted {} timezones.".format(len(all_tz_deleted)))
    
    # Update the SpytzData model version, dates and lists.
    gaetz.update_metadata(install_version, all_tzs)

    # Reset all memcache entries. 
    logging.info("SPYTZ: Flushing cache.".format(len(all_tz_not_updated)))
    spytz.flush_cache()
    
    # Wait until all async operations have finished before exiting.
    ndb.Future.wait_all(upd_futures + del_futures)
    

    logging.info("SPYTZ: Successfully updated to version '{}'.".format(rel_info.version))
    logging.info("SPYTZ: Completed update process in {:4.4f}.".format(time.time() - _ts))

    return True
