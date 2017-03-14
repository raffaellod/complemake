# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2014, 2016-2017 Raffaello D. Di Napoli
#
# This file is part of Complemake.
#
# Complemake is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# Complemake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along with Complemake. If not, see
# <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------------------------------------

"""Logging-related classes."""

import threading
import sys

if sys.hexversion < 0x03000000:
   import io


##############################################################################################################

class LogGenerator(object):
   """Generator of logs. Only one instance of this class exists for each comk.Core instance."""

   # Total count of failed test assertions.
   _failed_test_assertions = None
   # Total count of failed test cases.
   _failed_test_cases = None
   # Standard error output.
   _stderr = None
   # Lock that must be acquired prior to writing to stderr.
   _stderr_lock = None
   # Total count of test assertions performed.
   _total_test_assertions = None
   # Total count of test cases executed.
   _total_test_cases = None

   def __init__(self):
      """Constructor."""

      self._failed_test_assertions = 0
      self._failed_test_cases = 0
      if sys.hexversion >= 0x03000000:
         self._stderr = sys.stderr
      else:
         # Create a text I/O wrapper for sys.stderr.
         self._stderr = io.open(sys.stderr.fileno(), 'w', closefd=False)
      self._stderr_lock = threading.Lock()
      self._total_test_assertions = 0
      self._total_test_cases = 0
      self.verbosity = Logger.QUIET

   def add_testcase_result(self, title, total_assertions, failed_assertions):
      """Implementation of Logger.add_testcase_result()."""

      # Update the assertion counts.
      self._total_test_assertions += total_assertions
      self._failed_test_assertions += failed_assertions

      # Update the test cases counts.
      self._total_test_cases += 1
      if failed_assertions:
         self._failed_test_cases += 1

   def _test_summary_counts(self, total, failed):
      """Generates a total/passed/failed summary line.

      int total
         Total count.
      int failed
         Count of failures.
      str return
         String with the summary counts.
      """

      passed = total - failed
      return '{:5} total, {:5} passed ({:3}%), {:5} failed ({:3}%)'.format(
         total, passed, (passed * 100 + 1) // total, failed, failed * 100 // total,
      )

   # Selects a verbosity level (comk.logging.Logger.*), affecting what is displayed about the operations
   # executed.
   verbosity = None

   def write(self, s):
      """Implementation of Logger._write()."""

      s += '\n'
      if sys.hexversion < 0x03000000 and not isinstance(s, unicode):
         s = unicode(s)
      # Lock stderr and write to it.
      with self._stderr_lock as lock:
         self._stderr.write(s)

   def write_test_summary(self):
      """Implementation of Logger.test_summary()."""

      if self._total_test_assertions:
         self.write('make: test summary:')
         self.write('  Test cases: ' + self._test_summary_counts(self._total_test_cases,      self._failed_test_cases))
         self.write('  Assertions: ' + self._test_summary_counts(self._total_test_assertions, self._failed_test_assertions))
      else:
         self.write('Test cases: no tests performed')

##############################################################################################################

class Logger(object):
   """Basic logger functor."""

   # LogGenerator instance to use for logging.
   _log_gen = None

   # No verbosity, i.e. quiet operation (default). Will display a short summary of each job being executed,
   # instead of its command-line.
   QUIET = 1
   # Print each job’s command-line as-is instead of a short summary.
   LOW = 2
   # Like LOW, and also describe what triggers the (re)building of each target.
   MEDIUM = 3
   # Like MED, and also show all the files that are being checked for changes.
   HIGH = 4

   def __init__(self, log_gen):
      """Constructor.

      object log_gen
         comk.logging.LogGenerator instance, or comk.logging.Logger whose LogGenerator is to be shared.
      """

      if isinstance(log_gen, LogGenerator):
         self._log_gen = log_gen
      else:
         self._log_gen = log_gen._log_gen

   def __call__(self, level, format, *args, **kwargs):
      """Logs a formatted string. A new-line character will be automatically appended because due to
      concurrency, a thread should not expect to log a complete line with multiple log calls.

      int level
         Minimum logging level. If the log verbosity setting is below this value, the log entry will not be
         printed. If this value is None, the message will be output unconditionally (useful to report errors,
         for example).
      str format
         Format string.
      iterable(object*) *args
         Forwarded to format.format().
      dict(str: object) **kwargs
         Forwarded to format.format().
      """

      if level is None or self._log_gen.verbosity >= level:
         if sys.hexversion < 0x03000000 and not isinstance(format, unicode):
            format = unicode(format)
         self._write(format.format(*args, **kwargs))

   def add_testcase_result(self, title, total_assertions, failed_assertions):
      """Stores the result of a test case for later display as part of the test summary.

      str title
         Title of the test case.
      int total_assertions
         Count of assertions performed.
      int failed_assertions
         Count of failed assertions.
      """

      self._log_gen.add_testcase_result(title, total_assertions, failed_assertions)

   def qm_tool_name(self, tool_name):
      """Returns a “prettier” string for the specified tool, to be displayed in quiet mode.

      str tool_name
         Tool name.
      str return
         “Prettified” tool name.
      """

      # TODO: support coloring in case stderr is a TTY.
      return '{:<8}'.format(tool_name)

   def test_summary(self):
      """Generates and logs a summary of success/failures for the tests performed."""

      self._log_gen.write_test_summary()

   def _get_verbosity(self):
      return self._log_gen.verbosity

   def _set_verbosity(self, level):
      self._log_gen.verbosity = level

   verbosity = property(_get_verbosity, _set_verbosity, doc="""
      Selects a verbosity level (comk.logging.Logger.*), affecting what is displayed about the operations
      executed.
   """)

   def _write(self, s):
      """Unconditionally logs a string.

      str s
         Text to log.
      """

      self._log_gen.write(s)

##############################################################################################################

class FilteredLogger(Logger):
   """Logger that omits specific lines."""

   # Set of lines to skip.
   _exclusions = None

   def __init__(self, log_gen):
      """See Logger.__init__()."""

      Logger.__init__(self, log_gen)

      self._exclusions = set()

   def add_exclusion(self, s):
      """Adds a line to the list of lines that should be omitted from the log.

      str s
         String to be excluded.
      """

      self._exclusions.add(s)

   def _write(self, s):
      """See Logger._write()."""

      # Skip blacklisted lines.
      if s not in self._exclusions:
         Logger._write(self, s)
