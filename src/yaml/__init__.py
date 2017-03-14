# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2015-2017 Raffaello D. Di Napoli
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

"""YAML parser and generator.

To run the test suite:
  (cd src && python -m unittest discover yaml '*_test.py')

To temporarily disable unit tests:
  @unittest.skip
"""

import datetime


##############################################################################################################

class DuplicateTagError(Exception):
   """Raised when attempting to register a tag with a name that’s already taken."""

   pass

##############################################################################################################

class Kind(object):
   """YAML raw object type."""

   MAPPING  = None
   SCALAR   = None
   SEQUENCE = None

   _name = None

   def __init__(self, name):
      """Constructor.

      str name
         Name of the kind.
      """

      self._name = name

   def __str__(self):
      return self._name

Kind.MAPPING  = Kind('mapping')
Kind.SCALAR   = Kind('scalar')
Kind.SEQUENCE = Kind('sequence')

##############################################################################################################

class TimestampTZInfo(datetime.tzinfo):
   """Provides a tzinfo for datatime.datetime instances constructed from YAML timestamps that included a time
   zone.
   """

   _td = None
   _tz = None

   def __init__(self, tz, hour, minute):
      """Constructor.

      str tz
         The timezone, as a string; can be “Z” to indicate UTC.
      int hour
         Timezone hour part.
      int minute
         Timezone minute part.
      """

      self._td = datetime.timedelta(hours=hour, minutes=minute)
      self._tz = tz

   def __eq__(self, other):
      return self._td == other._td

   def dst(self, dt):
      """See datetime.tzinfo.dst()."""

      return None

   def tzname(self, dt):
      """See datetime.tzinfo.tzname()."""

      return self._tz

   def utcoffset(self, dt):
      """See datetime.tzinfo.utcoffset()."""

      return self._td
