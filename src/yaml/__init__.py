#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2015-2016 Raffaello D. Di Napoli
#
# This file is part of Abamake.
#
# Abamake is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Abamake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
# the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Abamake. If not, see
# <http://www.gnu.org/licenses/>.
#---------------------------------------------------------------------------------------------------

"""YAML support."""

import datetime


####################################################################################################

class DuplicateTagError(Exception):
   """Raised when attempting to register a tag with a name that’s already taken."""

   pass

####################################################################################################

class Kind(object):
   """YAML raw object type."""

   MAPPING  = None
   SCALAR   = None
   SEQUENCE = None

   _m_sName = None

   def __init__(self, sName):
      """Constructor.

      str sName
         Name of the kind.
      """

      self._m_sName = sName

   def __str__(self):
      return self._m_sName

Kind.MAPPING  = Kind('mapping')
Kind.SCALAR   = Kind('scalar')
Kind.SEQUENCE = Kind('sequence')

####################################################################################################

class TimestampTZInfo(datetime.tzinfo):
   """Provides a tzinfo for datatime.datetime instances constructed from YAML timestamps that
   included a time zone.
   """

   _m_td = None
   _m_sTZ = None

   def __init__(self, sTZ, iHour, iMinute):
      """Constructor.

      str sTZ
         The timezone, as a string; can be “Z” to indicate UTC.
      int iHour
         Timezone hour part.
      int iMinute
         Timezone minute part.
      """

      self._m_td = datetime.timedelta(hours = iHour, minutes = iMinute)
      self._m_sTZ = sTZ

   def __eq__(self, ttziOther):
      return self._m_td == ttziOther._m_td

   def dst(self, dt):
      """See datetime.tzinfo.dst()."""

      return None

   def tzname(self, dt):
      """See datetime.tzinfo.tzname()."""

      return self._m_sTZ

   def utcoffset(self, dt):
      """See datetime.tzinfo.utcoffset()."""

      return self._m_td
