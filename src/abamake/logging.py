#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2014
# Raffaello D. Di Napoli
#
# This file is part of Application-Building Components (henceforth referred to as ABC).
#
# ABC is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ABC is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with ABC. If not, see
# <http://www.gnu.org/licenses/>.
#---------------------------------------------------------------------------------------------------

"""Logging-related classes."""

import threading
import sys



####################################################################################################
# Logger

class Logger(object):
   """Logger with multiple verbosity levels."""

   # Lock that must be acquired prior to writing to stderr.
   _m_lockStdErr = None

   # No verbosity, i.e. quiet operation (default). Will display a short summary of each job being
   # executed, instead of its command-line.
   QUIET = 1
   # Print each job’s command-line as-is instead of a short summary.
   LOW = 2
   # Like LOW, and also describe what triggers the (re)building of each target.
   MEDIUM = 3
   # Like MED, and also show all the files that are being checked for changes.
   HIGH = 4


   def __init__(self):
      """Constructor."""

      self.verbosity = self.QUIET
      self._m_lockStdErr = threading.Lock()


   def __call__(self, iLevel, sFormat, *iterArgs, **dictKwArgs):
      """Logs a formatted string. A new-line character will be automatically appended because due
      to concurrency, a thread should not expect to log a complete line with multiple log calls.

      int iLevel
         Minimum logging level. If the log verbosity setting is below this value, the log entry will
         not be printed. If this value is None, the message will be output unconditionally (useful
         to report errors, for example).
      str sFormat
         Format string.
      iter(object*) *iterArgs
         Forwarded to sFormat.format().
      dict(str: object) **dictKwArgs
         Forwarded to sFormat.format().
      """

      if iLevel is None or self.verbosity >= iLevel:
         s = sFormat.format(*iterArgs, **dictKwArgs) + '\n'
         # Lock stderr and write to it.
         with self._m_lockStdErr as lock:
            sys.stderr.write(s)


   # Selects a verbosity level (make.Make.*), affecting what is displayed about the operations
   # executed.
   verbosity = None

