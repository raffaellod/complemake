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

"""Utilities to parse and use software version numbers."""

import functools
import re
import sys

if sys.hexversion >= 0x03000000:
   basestring = str


##############################################################################################################

class InvalidVersionError(ValueError):
   """Raised upon failure to parse a software version string."""

   pass

##############################################################################################################

@functools.total_ordering
class Version(object):
   """Software version number."""

   # Major version number, or None if unset.
   _major = None,
   # Minor version number, or None if unset.
   _minor = None,
   # Revision number, or None if unset.
   _revision = None,
   # Build number, or None if unset.
   _build = None,

   def __init__(self, major = None, minor = None, revision = None, build = None):
      """Constructor.

      object major
         Optional major version number.
      object minor
         Optional minor version number.
      object revision
         Optional revision number.
      object build
         Optional build number.
      """

      self._major    = major
      self._minor    = minor
      self._revision = revision
      self._build    = build

   def __eq__(self, other):
      return self._compare_component(self._major,    other._major   ) == 0 \
         and self._compare_component(self._minor,    other._minor   ) == 0 \
         and self._compare_component(self._revision, other._revision) == 0 \
         and self._compare_component(self._build,    other._build   ) == 0

   def __lt__(self, other):
      ret = self._compare_component(self._major, other._major)
      if ret == 0:
         ret = self._compare_component(self._minor, other._minor)
         if ret == 0:
            ret = self._compare_component(self._revision, other._revision)
            if ret == 0:
               ret = self._compare_component(self._build, other._build)
      return ret < 0

   def __str__(self):
      s = str(self._major) if self._major else ''
      if self._minor:
         s += '.{}'.format(self._minor)
         if self._revision:
            s += '.{}'.format(self._revision)
            if self._build:
               s += '.{}'.format(self._build)
      return s

   @staticmethod
   def _canonicalize_component(o):
      """Attempts to convert a version component into an integer.

      object o
         Version component to canonicalize.
      object return
         Resulting value.
      """

      if o is None:
         return 0
      elif isinstance(o, basestring):
         if o.isdigit():
            return int(o)
      return o

   @classmethod
   def _compare_component(cls, l, r):
      """Compares a version component with another of the same level.

      object l
         Left version component to compare.
      object r
         Right version component to compare.
      int return
         +1 if l > r, -1 if l < r, r 0 if l == r.
      """

      l = cls._canonicalize_component(l)
      r = cls._canonicalize_component(r)
      if isinstance(l, int) and isinstance(r, int):
         # Both are integers, compare them as such.
         return l - r
      else:
         # Compare them as strings.
         l = str(l)
         r = str(r)
         if l > r:
            return +1
         elif l < r:
            return -1
         else:
            return 0

   @classmethod
   def parse(cls, s):
      """Parses a version number strings, returning a Version instance.

      str s
         String to parse.
      comk.tool.Version return
         Parsed version number.
      """

      match = re.match(r'''
         ^(?:
            (?P<major>[^.]+)
            (?:
               \.(?P<minor>[^.]+)
               (?:
                  \.(?P<revision>[^.]+)
                  (?:
                     \.(?P<build>[^.]+)
                  )?
               )?
            )?
         )?$
      ''', s, re.VERBOSE)
      if not match:
         raise InvalidVersionError('could not parse version: {}'.format(s))

      return cls(match.group('major'), match.group('minor'), match.group('revision'), match.group('build'))
