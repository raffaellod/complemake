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

"""Classes that abstract different software platforms, concealing their differences for the rest of
ABC Make.
"""

import os
import sys



####################################################################################################
# Platform

class Platform(object):
   """Generic software platform (OS/runtime environment)."""

   # Mapping between Platform subclasses and Python sys.platform name prefixes. To add to this
   # mapping, decorate a derived class with @Platform.match_name('platform').
   _sm_dictSubclassPlatformNames = {}


   def add_dir_to_dynlib_env_path(self, dictEnv, sDir):
      """Modifies an environment dictionary (similar to os.environ) so that it allows to load
      dynamic libraries from the specified directory.

      dict(str: str) dictEnv
         Environment dictionary.
      str sDir
         Directory to add to the dynlib path.
      dict(str: str) return
         Same as dictEnv, returned for convenience.
      """

      raise NotImplementedError(
         'Platform.add_dir_to_dynlib_env_path() must be overridden in ' + type(self).__name__
      )


   @classmethod
   def get_host_subclass(cls):
      """Attempts to detect the underlying (host) platform, returning the Platform subclass best
      modeling it.

      type return
         Model for the underlying (host) platform.
      """

      sPlatform = sys.platform
      for sName, clsDerived in cls._sm_dictSubclassPlatformNames.items():
         if sPlatform.startswith(sName):
            return clsDerived
      return None


   def dynlib_file_name(self, sName):
      """Generates a file name for a dynamic library from the specified name.

      str sName
         Name of the dynamic library.
      str return
         Name of the dynamic library’s file.
      """

      raise NotImplementedError(
         'Platform.dynlib_file_name() must be overridden in ' + type(self).__name__
      )


   # If True, dynamic libraries need import libraries (i.e. statically-linked runtime-patchable
   # data) for the linker to be able to generate executables that link to them; if False, dynlibs
   # can be linked to directly.
   dynlibs_need_implibs = False


   def exe_file_name(self, sName):
      """Generates an executable file name from the specified name.

      str sName
         Name of the executable.
      str return
         Name of the executable’s file.
      """

      raise NotImplementedError(
         'Platform.exe_file_name() must be overridden in ' + type(self).__name__
      )


   class match_name(object):
      """Decorator to teach Platform.detect() the association of the decorated class with a Python
      sys.platform name prefix.

      str sPlatformName
         Python platform name prefix to associate with the decorated class.
      """

      def __init__(self, sPlatformName):
         self._m_sPlatformName = sPlatformName

      def __call__(self, clsDerived):
         Platform._sm_dictSubclassPlatformNames[self._m_sPlatformName] = clsDerived
         return clsDerived



####################################################################################################
# PosixPlatform

class PosixPlatform(Platform):
   """POSIX-(mostly-)compliant platform."""

   def dynlib_file_name(self, sName):
      """See Platform.dynlib_file_name()."""

      return 'lib{}.so'.format(sName)


   def exe_file_name(self, sName):
      """See Platform.exe_file_name()."""

      return '{}'.format(sName)



####################################################################################################
# GnuPlatform

@Platform.match_name('linux')
class GnuPlatform(PosixPlatform):
   """GNU Operating System platform."""

   def add_dir_to_dynlib_env_path(self, dictEnv, sDir):
      """See PosixPlatform.add_dir_to_dynlib_env_path()."""

      sLibPath = dictEnv.get('LD_LIBRARY_PATH', '')
      if sLibPath:
         sLibPath = ':' + sLibPath
      sLibPath += os.path.abspath(sDir)
      dictEnv['LD_LIBRARY_PATH'] = sLibPath
      return dictEnv



####################################################################################################
# WinPlatform

@Platform.match_name('win32')
class WinPlatform(Platform):
   """Generic Microsoft Windows platform."""

   def add_dir_to_dynlib_env_path(self, dictEnv, sDir):
      """See Platform.add_dir_to_dynlib_env_path()."""

      sLibPath = dictEnv.get('PATH', '')
      if sLibPath:
         sLibPath = ';' + sLibPath
      sLibPath += os.path.abspath(sDir)
      dictEnv['PATH'] = sLibPath
      return dictEnv


   def dynlib_file_name(self, sName):
      """See Platform.dynlib_file_name()."""

      return '{}.dll'.format(sName)


   # See Platform.dynlibs_need_implibs.
   dynlibs_need_implibs = True


   def exe_file_name(self, sName):
      """See Platform.exe_file_name()."""

      return '{}.exe'.format(sName)

