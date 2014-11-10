# spytz
`spytz` provides timezone support intended for online applications, 
specifically [Webapp2](https://webapp-improved.appspot.com/) and [Google App Engine](https://developers.google.com/appengine/docs/python/gettingstartedpython27/introduction).
It implements the same functionality as `pytz`, and continues on from where 
`gae-pytz` left off implementing optimisations for online use.

This is based on the Python `pytz` module, found at http://pypi.python.org/pypi/pytz/

Timezone database files come from http://www.iana.org/time-zones/

# Goal
The goal of `spytz` is to:
* Be friendly for web applications
* Millisecond response times for module imports.
* Low memory footprint
* Low CPU usage
** Zipped alternatives require CPU to decompress
 
and timezone references in GAE, with minimal memory footprint.

## Problem with `pytz` on GAE
`pytz` is **_fast_** on GAE, right out of the box, but it does have some
drawbacks that affect its usability:
* Caching is done per instance, instead of globally for all instances.
* No cleanup for caches means memory can be unnecessarily hogged or inflated.
* Lots of files to upload & manage, affecting app quotas (currently 10,000 files)
* TZ file updates require the GAE app to be re-deployed. 

Some people don't care about any of this, some do.

## Costs of `spytz` on GAE
`spytz` is intended to carry a lower memory and CPU overhead, and reduce the
burden of administration. Having said that, it does come with some costs:
* Uses datastore allowances, including:
** Storage (~1MB)
** Read & write transactions when updating datastore or memcache
* Uses network bandwidth to download any updates

# Meaning
Until we think of something better, `spytz` stands for **S** pecialised **pytz**.

# Performance
See current performance results: http://spytz-app.appspot.com

## Compression
The Olson Timezone files currently number 584, which took a significant chunk
out of Googles' original app limit of 1,000, then 3,000, app files. The original `gae-pytz`
used a zip archive to reduce this amount and make it more workable for GAE.

Google now permits up to 10,000 files making this less of an issue, but a zip
compressed archive requires more CPU and memory to read, and slower to respond
overall.

## Pytz Lazy Loading
`pytz` uses lazy loading to really improve access times when the module is
imported. This is further backed up with caching to make it a fast option
straight out of the box.

# Usage
Add `spytz` to your app or sources directory. Import it regularly:

```python
import spytz
```

To maintain compatability with `pytz`:

From the appengine interactive console:
```python
>>> import pprint
>>> import timeit
>>> dt = datetime(2009, 4, 15)
>>> tz = spytz.timezone('US/Eastern')
>>> pprint.pprint(tz.localize(dt))
datetime.datetime(2009, 4, 15, 0, 0, tzinfo=<DstTzInfo 'US/Eastern' EDT-1 day, 20:00:00 DST>)
>>> t1 = timeit.Timer('tz.localize(dt)', setup="import spytz; from datetime import datetime; dt = datetime(2009, 4, 15); tz = spytz.timezone('US/Eastern')")
>>> t2 = timeit.Timer('tz.localize(dt)', setup="import pytz; from datetime import datetime; dt = datetime(2009, 4, 15); tz = pytz.timezone('US/Eastern')")
>>> pprint.pprint(t1.timeit(number=100000))
>>> pprint.pprint(t2.timeit(number=100000))
2.905263900756836
2.81188702583313
>>> t3 = timeit.Timer("tz.normalize(tz.localize(dt)).astimezone(spytz.timezone('Australia/Melbourne'))", setup="import spytz; from datetime import datetime; dt = datetime(2009, 4, 15); tz = spytz.timezone('US/Eastern')")
>>> t4 = timeit.Timer("tz.normalize(tz.localize(dt)).astimezone(pytz.timezone('Australia/Melbourne'))", setup="import pytz; from datetime import datetime; dt = datetime(2009, 4, 15); tz = pytz.timezone('US/Eastern')")
>>> pprint.pprint(t3.timeit(number=100000))
>>> pprint.pprint(t4.timeit(number=100000))
4.437927961349487
4.734771013259888
```

# References
- http://takashi-matsuo.blogspot.com.au/2008/07/using-newest-zipped-pytz-on-gae.html
- http://takashi-matsuo.blogspot.com.au/2008/07/using-zipped-pytz-on-gae.html
- http://appengine-cookbook.appspot.com/recipe/caching-pytz-helper/

# Resources
- http://timezones.appspot.com/?translate_to=pst&translate_with=astimezone
