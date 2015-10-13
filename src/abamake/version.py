#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2015 Raffaello D. Di Napoli
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

"""Utilities to parse and use software version numbers."""

import functools
import re


####################################################################################################
# InvalidVersionError

class InvalidVersionError(ValueError):
   """Raised upon failure to parse a software version string."""

   pass

####################################################################################################
# Version

@functools.total_ordering
class Version(object):
   """Software version number."""

   # Major version number, or None if unset.
   _m_oMajor = None,

   # Minor version number, or None if unset.
   _m_oMinor = None,

   # Revision number, or None if unset.
   _m_oRevision = None,

   # Build number, or None if unset.
   _m_oBuild = None,

   def __init__(self, oMajor = None, oMinor = None, oRevision = None, oBuild = None):
      """Constructor.

      object oMajor
         Optional major version number.
      object oMinor
         Optional minor version number.
      object oRevision
         Optional revision number.
      object oBuild
         Optional build number.
      """

      self._m_oMajor    = oMajor
      self._m_oMinor    = oMinor
      self._m_oRevision = oRevision
      self._m_oBuild    = oBuild

   def __eq__(self, verOther):
      return self._compare_component(self._m_oMajor,    verOther._m_oMajor   ) == 0 \
         and self._compare_component(self._m_oMinor,    verOther._m_oMinor   ) == 0 \
         and self._compare_component(self._m_oRevision, verOther._m_oRevision) == 0 \
         and self._compare_component(self._m_oBuild,    verOther._m_oBuild   ) == 0

   def __lt__(self, verOther):
      iRet = self._compare_component(self._m_oMajor, verOther._m_oMajor)
      if iRet == 0:
         iRet = self._compare_component(self._m_oMinor, verOther._m_oMinor)
         if iRet == 0:
            iRet = self._compare_component(self._m_oRevision, verOther._m_oRevision)
            if iRet == 0:
               iRet = self._compare_component(self._m_oBuild, verOther._m_oBuild)
      return iRet < 0

   def __str__(self):
      s = str(self._m_oMajor) if self._m_oMajor else ''
      if self._m_oMinor:
         s += '.{}'.format(self._m_oMinor)
         if self._m_oRevision:
            s += '.{}'.format(self._m_oRevision)
            if self._m_oBuild:
               s += '.{}'.format(self._m_oBuild)
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
      elif isinstance(o, str):
         if o.isdigit():
            return int(o)
      return o

   @classmethod
   def _compare_component(cls, oL, oR):
      """Compares a version component with another of the same level.

      object oL
         Left version component to compare.
      object oR
         Right version component to compare.
      int return
         +1 if oL > oR, -1 if oL < oR, or 0 if oL == oR.
      """

      oL = cls._canonicalize_component(oL)
      oR = cls._canonicalize_component(oR)
      if isinstance(oL, int) and isinstance(oR, int):
         # Both are integers, compare them as such.
         return oL - oR
      else:
         # Compare them as strings.
         oL = str(oL)
         oR = str(oR)
         if oL > oR:
            return +1
         elif oL < oR:
            return -1
         else:
            return 0

   @classmethod
   def parse(cls, sVersion):
      """Parses a version number strings, returning a Version instance.

      str sVersion
         String to parse.
      abamake.tool.Version return
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
      ''', sVersion, re.VERBOSE)
      if not match:
         raise InvalidVersionError('could not parse version: {}'.format(sVersion))

      return cls(
         match.group('major'), match.group('minor'), match.group('revision'), match.group('build')
      )
