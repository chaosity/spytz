import webapp2
from google.appengine.ext.webapp.template import render
from google.appengine.api import runtime

import os
import gc

import time
import timeit

from datetime import datetime

class MainPage(webapp2.RequestHandler):
    def get(self):
        data = {}
        template = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(render(template, data))

class TimeitPage(webapp2.RequestHandler):
    def get(self):
        repeat = self.request.get("repeat", 5)
        iter = self.request.get("iter", 100)

        self.response.headers['Content-Type'] = 'text/plain'
        
        stmt1 = """\
        import pytz
        from datetime import datetime
        tz_strings = ('Australia/Perth', 'Australia/Melbourne', 'Europe/London',
                      'America/Indiana/Indianapolis')
        for tz in tz_strings:
            dt = datetime(2009, 4, 15)
            pytz.timezone(tz)
        """
        
        stmt2 = """\
        import spytz3
        from datetime import datetime
        tz_strings = ('Australia/Perth', 'Australia/Melbourne', 'Europe/London',
                      'America/Indiana/Indianapolis')
        for tz in tz_strings:
            dt = datetime(2009, 4, 15)
            spytz3.timezone(tz)
        """

        stmt3 = """\
        import pytz
        from datetime import datetime
        tz_strings = ('Australia/Perth', 'Australia/Melbourne', 'Europe/London',
                      'America/Indiana/Indianapolis')
        for tz in tz_strings:
            dt = datetime(2009, 4, 15)
            pytz.timezone(tz)
        pytz.clear_cache()
        """
        
        stmt4 = """\
        import spytz3
        from datetime import datetime
        tz_strings = ('Australia/Perth', 'Australia/Melbourne', 'Europe/London',
                      'America/Indiana/Indianapolis')
        for tz in tz_strings:
            dt = datetime(2009, 4, 15)
            spytz3.timezone(tz)
        spytz3.clear_cache()
        """
        
        gc.collect()
        self.response.write("-- cache --\n")

        mem_st = runtime.memory_usage().current()
        cpu_st = runtime.cpu_usage().total()
        t1 = timeit.repeat(stmt=stmt1, number=100, repeat=4)
        mem = runtime.memory_usage().current() - mem_st
        cpu = runtime.cpu_usage().total() - cpu_st
        self.response.write("PYTZ    cpu:{}, memory: {}\n".format(cpu, mem))
        self.response.write("timeit: {}\n".format(t1))

        mem_st = runtime.memory_usage().current()
        cpu_st = runtime.cpu_usage().total()
        gc.collect()
        time.sleep(1)
        mem = runtime.memory_usage().current() - mem_st
        cpu = runtime.cpu_usage().total() - cpu_st
        self.response.write("SLEEP   cpu:{}, memory: {}\n".format(cpu, mem))

        mem_st = runtime.memory_usage().current()
        cpu_st = runtime.cpu_usage().total()
        t2 = timeit.repeat(stmt=stmt2, number=100, repeat=4)
        mem = runtime.memory_usage().current() - mem_st
        cpu = runtime.cpu_usage().total() - cpu_st
        self.response.write("SPYTZ   cpu:{}, memory: {}\n".format(cpu, mem))
        self.response.write("timeit: {}\n".format(t2))

        self.response.write("\n")
        self.response.write("-- clear cache --\n")

        mem_st = runtime.memory_usage().current()
        cpu_st = runtime.cpu_usage().total()
        gc.collect()
        time.sleep(1)
        mem = runtime.memory_usage().current() - mem_st
        cpu = runtime.cpu_usage().total() - cpu_st
        self.response.write("SLEEP   cpu:{}, memory: {}\n".format(cpu, mem))

        mem_st = runtime.memory_usage().current()
        cpu_st = runtime.cpu_usage().total()
        t3 = timeit.repeat(stmt=stmt3, number=100, repeat=4)
        mem = runtime.memory_usage().current() - mem_st
        cpu = runtime.cpu_usage().total() - cpu_st
        self.response.write("PYTZ    cpu:{}, memory: {}\n".format(cpu, mem))
        self.response.write("timeit: {}\n".format(t3))

        mem_st = runtime.memory_usage().current()
        cpu_st = runtime.cpu_usage().total()
        gc.collect()
        time.sleep(1)
        mem = runtime.memory_usage().current() - mem_st
        cpu = runtime.cpu_usage().total() - cpu_st
        self.response.write("SLEEP   cpu:{}, memory: {}\n".format(cpu, mem))

        mem_st = runtime.memory_usage().current()
        cpu_st = runtime.cpu_usage().total()
        t4 = timeit.repeat(stmt=stmt4, number=100, repeat=4)
        mem = runtime.memory_usage().current() - mem_st
        cpu = runtime.cpu_usage().total() - cpu_st
        self.response.write("SPYTZ   cpu:{}, memory: {}\n".format(cpu, mem))
        self.response.write("timeit: {}\n".format(t4))

        mem_st = runtime.memory_usage().current()
        cpu_st = runtime.cpu_usage().total()
        gc.collect()
        time.sleep(1)
        mem = runtime.memory_usage().current() - mem_st
        cpu = runtime.cpu_usage().total() - cpu_st
        self.response.write("SLEEP   cpu:{}, memory: {}\n".format(cpu, mem))

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/timeit', TimeitPage),
], debug=True)
