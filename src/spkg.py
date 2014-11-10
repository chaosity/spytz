#!/usr/bin/env python
#
# Copyright (C) 2014 Chaosity Enterprises Pty Ltd. All Rights Reserved

"""
Spytz Package building, validation & release management tool. 

Copyright (C) 2014 Chaosity Enterprises. All Rights Reserved.
"""

import os, sys, re, argparse, logging

import json
import tarfile

# Spytz modules
from spytz.spud import SpytzUpdateFile

__author__ = "Simon Dean <simon.dean@chaosity.net>"
__status__  = "test"
__version__ = "0.1.0"
__date__  = "19 Sep 2014"
__license__ = "MIT"

app_version = __version__

# Mandatory files required in the release package.
ALLTZ_FILE = 'alltzs'
VERSION_FILE = 'VERSION'
LICENCE_FILE = 'LICENCE'
ISO3166_FILE = 'iso3166.tab'
ZONE_FILE = 'zone.tab'

REQUIRED_FILES = [VERSION_FILE, LICENCE_FILE, ALLTZ_FILE, ISO3166_FILE, 
                  ZONE_FILE]

PKG_FILENAME_FORMAT = 'spytz-zoneinfo-{}.tar.gz'

# Regex expression for correct version format
REGEX_VERSION = "^[0-9]{4}\.[0-9]{1}$"

# Default location for releases.
RELEASES_DIR = 'releases'

# Default filename of the published release JSON config file.
RELEASES_FILE = 'releases.json'

# Exception Handling
class SpytzBuildError(Exception):
    pass

class SpytzVersionError(Exception):
    pass

class InvalidFileError(Exception):
    pass

class InvalidPathError(Exception):
    pass


def build_json(pkg_path):    
    releases = {}
    for root, dirnames, filenames in os.walk(pkg_path):
        # Restrict to GZip tar archives. 
        re_filename = '^.*\.tgz|.*\.tar\.gz$'
        for filename in filenames:
            if re.match(re_filename, filename):
                # Open binary for multiplatform support. 
                with open(os.path.join(root, filename), "rb") as fo:
                    spfile = SpytzUpdateFile(fo.read())
                    releases[spfile.version] = {'filename': filename,
                                                'hash': spfile.hash,
                                                'hashtype': spfile.hashtype}

    number_pkgs = len(releases.keys()) 
    
    if number_pkgs > 0:
        logging.debug("Found {} release files.".format(number_pkgs))

        # Perhaps not the best way to derive the latest, but it works for now.
        release_json = {'releases': releases,
                        'latest': sorted(releases.keys(), reverse=True)[0]
                        }
        
        logging.debug("Latest version: {}".format(release_json['latest']))
    
        with open(os.path.join(pkg_path, RELEASES_FILE), "wb") as release_file:
            logging.debug("Creating {}".format(os.path.join(pkg_path, RELEASES_FILE)))
            release_file.write(json.dumps(release_json, indent=4))

        return True
        
    else:
        logging.warning("No spytz release packages found. Exiting.")
        return False


def build_package(build_path, dst_path, version):
        
    # Check the version value matches. If None, will fail.
    if not re.match(REGEX_VERSION, version):
        logging.error("Error! Version string invalid. Must be of format 'NNNN.N'")
        sys.exit(1)
    else:
        # Version format ok, write it to build path.
        with open(os.path.join(build_path, VERSION_FILE), "wb") as fo:
            fo.write(version)

    ctr = 0

    # Regex to match the parent directory, this must be removed convert a path
    # into a timezone identier. Takes the form 'timezone' or 'region/timezone'.
    regex_path_sub = "^[\{sep}]*{path}[\{sep}]*".format(sep=os.path.sep, path=build_path)

    # Create the 'alltzs' file 
    fname = os.path.join(build_path, ALLTZ_FILE)
    with open(fname, "wb") as fo:
        for dirname, dirnames, filenames in os.walk(build_path):
            for fn in filenames:
                tzpath = os.path.join(dirname, fn)
                if SpytzUpdateFile.is_tzdata(open(tzpath)):
                    # Remove the base path and remaining backslashses with
                    # forward slashes. Result is timezone name. 
                    tz = re.sub(regex_path_sub, '', tzpath).replace('\\', '/')
    
                    # Write the timezone name to the file.
                    fo.write(tz + "\n")
                    ctr += 1
                
    logging.info("{} timezones found.".format(ctr))

    # Check the build before creating the package.
    if not check_build(args.src):
        return False
    
    fname = os.path.join(dst_path, PKG_FILENAME_FORMAT.format(version))
    with tarfile.open(fname, 'w:gz') as fo:
        for dirname, dirnames, filenames in os.walk(build_path):
            # print path to all filenames.
            for filename in filenames:
                fpath = os.path.join(dirname, filename)
                arc_name = re.sub(regex_path_sub, '', fpath).replace('\\', '/')
                fo.add(fpath, arcname=arc_name)

    if not os.path.exists(fname):
        return False
    else:
        logging.debug("Spytz release package created as '{}'.".format(fname))
        return fname


def check_path(path, create=False):
    """ Checks if 'path' exists on the filesystem. If 'create' is True and
    'path' doesn't exist, the path will be created.
    """
    if os.path.isdir(path):
        return True
    else:
        if os.path.exists(path):
            # 'path' exists, but isn't a directory.
            raise InvalidPathError
        else:
            if create is True:
                # Create 'path'.
                os.makedirs(path)
                return True
        # Path doesn't exist, and we're not creating it.
        return False

def check_package(pkg_file):
    """ Sanity check of the compiled package.
    """
    error = None
    
    if not tarfile.is_tarfile(pkg_file):
        logging.error("'' is not a valid tarfile.".format(pkg_file))
        return False

    with tarfile.open(pkg_file) as tf:
        for rf in REQUIRED_FILES:
            try:
                tf.getmember(rf)
            except KeyError:
                logging.error("File '{}' doesn't exist.".format(rf))
                error = True

    if error:
        return False
    else:
        return True

def check_build(build_path):
    """ Sanity check of the files in the build path
    """
    error = None

    # List all files missing, not just the first one not found.
    for rf in REQUIRED_FILES:
        if not os.path.exists(os.path.join(build_path, rf)):
            logging.error("File '{}' not found.".format(os.path.join(build_path, rf)))
            error = True

    if error:
        return False
    else:
        return True


# Build the command line parser commands, arguments and options.
ap = argparse.ArgumentParser(description="Spytz release management tool.")
subparsers = ap.add_subparsers(dest='cmd_name', help='Spytz Release Management Commands')
ap.add_argument('-v', action='store_const', dest='verbosity', const=20,
                help="Verbose logging (INFO level).")
ap.add_argument('-vv', action='store_const', dest='verbosity', const=10,
                help="Verbose logging (DEBUG level).")

ap.add_argument('--version', action='version', version=app_version)

# Parsers for the 'build' command
ap_build = subparsers.add_parser('build', help='Create a new Spytz release package.')
ap_build.add_argument('version', action="store", metavar="version")
ap_build.add_argument('src', action="store", metavar="src",
                      default='/build', help="Source path of the spytz build.")
ap_build.add_argument('dest', action="store", metavar="dest", default='/releases',
                      help="Release path / Destination of the Spytz package.")

# Parsers for the 'check' command
ap_check = subparsers.add_parser('check', help='Sanity check a spytz release package.')
ap_check.add_argument('source', action="store", metavar="SOURCE",
                      help="Spytz package file path.")

# Parsers for the 'release' command
ap_release = subparsers.add_parser('publish', help='Build the release.json file.')
ap_release.add_argument('dest', action='store', metavar='dest',
                        help='Path to Spytz package releases.')

args = ap.parse_args()

logging.basicConfig(format='%(levelname)s: %(message)s')

# Change the level of verbosity printed to STDOUT
if args.verbosity:
    l = logging.getLogger()
    l.setLevel(args.verbosity)

logging.debug(args)

if __name__ == "__main__":
    
    if args.cmd_name == 'build':
        # check if a release already exists for the version provided.
        fname = build_package(args.src, args.dest, args.version)
        if fname:
            result = check_package(fname)
            if result:
                logging.info("Package successfully verified.")
            else:
                logging.error("Sanity check failed.")
                sys.exit(1)
        else:
            logging.critical("Could not create package.")
            sys.exit(1)

    elif args.cmd_name == 'check':
        result = check_package(args.src)
        
        if result:
            logging.info("Package successfully verified.")
        else:
            logging.error("Sanity check failed.")
            sys.exit(1)
    
    elif args.cmd_name == 'publish':
        if build_json(args.dest):
            logging.info("Release file successfully published.")
        else:
            logging.error("Release file not published.")
            sys.exit(1)
