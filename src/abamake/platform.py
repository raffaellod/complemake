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

import make.tool



####################################################################################################
# SystemType

class SystemType(object):
   """System type tuple.

   See <http://wiki.osdev.org/Target_Triplet> for a clear and concise explanation.
   """

   def __init__(self, sMachine = None, sVendor = None, sKernel = None, sOS = None):
      """Constructor.

      str sMachine
         See SystemType.machine.
      str sKernel
         See SystemType.kernel.
      str sVendor
         See SystemType.vendor.
      str sOS
         See SystemType.os.
      """

      self.machine = sMachine
      self.vendor = sVendor
      self.kernel = sKernel
      self.os = sOS


   def __str__(self):
      sVendor = self.vendor or 'unknown'
      if self.kernel:
         return '{}-{}-{}-{}'.format(self.machine, sVendor, self.kernel, self.os)
      if self.self.os:
         return '{}-{}-{}'.format(self.machine, sVendor, self.os)
      if self.vendor:
         return '{}-{}'.format(self.machine, self.vendor)
      if self.machine:
         return '{}'.format(self.machine)
      return 'unknown'


   # Machine type; often this is the processor’s architecture. Examples: 'i386', 'sparc'.
   machine = None


   @staticmethod
   def detect_host():
      """Returns a SystemType instance describing the host on which ABC Make is being run.

      make.platform.SystemType return
         Host system type.
      """

      import platform

      sSystem, sNode, sRelease, sVersion, sMachine, sProcessor = platform.uname()

      if sSystem == 'Windows':
         if sMachine == 'x86':
            return SystemType('i386', None, None, 'win32')
         elif sMachine == 'AMD64':
            return SystemType('x86_64', None, None, 'win64')
      elif sSystem in ('FreeBSD', 'Linux'):
         if sSystem == 'Linux':
            # TODO: don’t assume OS == GNU.
            sOS = 'gnu'
         else:
            sOS = None
            if sMachine == 'amd64':
               sMachine = 'x86_64'
         if sMachine in ('i386', 'i486', 'i586', 'i686', 'x86_64'):
            return SystemType(sMachine, None, sSystem.lower(), sOS)

      raise make.MakeException('unsupported system type')


   # Kernel on which the OS runs. Mostly used for the GNU operating system.
   kernel = None


   @staticmethod
   def parse_tuple(sTuple):
      """Parses a system type tuple into a SystemType instance. The format of the tuple must be one
      of:
      •  machine (1 item)
      •  machine-os (2 items)
      •  machine-vendor-os (3 items)
      •  machine-vendor-kernel-os (4 items)

      str sTuple
         String that will be parsed to extract the necessary information.
      make.platform.SystemType return
         Parsed system type.
      """

      # Break the tuple down.
      listTuple = sTuple.split('-')
      cTupleParts = len(listTuple)
      if cTupleParts == 1:
         # The tuple contains “machine” only.
         return SystemType(listTuple[0])
      if cTupleParts == 2:
         # The tuple contains “machine” and “os”.
         return SystemType(listTuple[0], None, None, listTuple[1])
      else:
         # The tuple contains “machine”, “vendor”, possibly “kernel”, and “os”.
         # Suppress placeholders in the “vendor” field.
         if listTuple[1] in ('none', 'unknown'):
            listTuple[1] = None
         if cTupleParts == 3:
            # The tuple contains “machine”, “vendor” and “os”.
            return SystemType(listTuple[0], listTuple[1], None, listTuple[2])
         if cTupleParts == 4:
            # The tuple contains “machine”, “vendor”, “kernel” and “os”.
            return SystemType(*listTuple)
      raise make.MakeException('invalid system type tuple')


   # Vendor. Examples: 'unknown'. 'pc', 'sun'.
   vendor = None

   # Operating system running on the system, or type of object file format for embedded systems.
   # Examples: 'solaris2.5', 'irix6.3', 'elf', 'coff'.
   os = None



####################################################################################################
# Platform

class Platform(object):
   """Generic software platform (OS/runtime environment)."""

   # Tools to be used for this platform (make.tool.Tool => make.tool.Tool). Associates a Tool
   # subclass to a more derived Tool subclass, representing the implementation to use of the tool.
   _m_dictTools = None
   # Mapping between Platform subclasses and Python sys.platform name prefixes. To add to this
   # mapping, decorate a derived class with @Platform.match_name('platform').
   _sm_dictSubclassPlatformNames = {}


   def __init__(self):
      """Constructor."""

      self._m_dictTools = {}


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


   def configure_tool(self, tool):
      """Configures the specified tool for this platform.

      make.tool.Tool tool
         Tool to configure.
      """

      pass


   @classmethod
   def detect_host(cls):
      """Attempts to detect the underlying (host) platform, returning the Platform subclass that
      models it best.

      type return
         Model for the underlying (host) platform.
      """

      sPlatform = sys.platform
      for sName, clsDerived in cls._sm_dictSubclassPlatformNames.items():
         if sPlatform.startswith(sName):
            return clsDerived
      return None


   @classmethod
   def from_system_type(cls, systype):
      """Returns a Platform subclass that most closely matches the specified system type. For
      example, it will return make.platform.GnuPlatform for SystemType('i686-pc-linux-gnu').

      make.platform.SystemType systype
         System type.
      make.platform.Platform return
         Corresponding platform.
      """

      for clsDeriv in cls.__subclasses__():
         if clsDeriv._match_system_type(systype):
            return clsDeriv
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


   def get_tool(self, clsTool):
      """Returns a subclass of the specified Tool subclass modeling the implementation of the
      specified tool for the platform.

      For example, my_platform.get_tool(make.tool.CxxCompiler) will return make.tool.GxxCompiler if
      G++ is the C++ compiler for my_platorm.

      type clsTool
         Subclass of make.tool.Tool.
      type return
         Subclass of clsTool.
      """

      clsToolImpl = self._m_dictTools.get(clsTool)
      if not clsToolImpl:
         clsToolImpl = clsTool.get_default_impl()
         self._m_dictTools[clsTool] = clsToolImpl
      return clsToolImpl


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


   @classmethod
   def _match_system_type(cls, systype):
      """Returns True if the platform models the specified system type.

      The default implementation always returns False.

      make.platform.SystemType systype
         System type.
      bool return
         True if the platform models the specified system type, or False otherwise.
      """

      return False



####################################################################################################
# GnuPlatform

@Platform.match_name('linux')
class GnuPlatform(Platform):
   """GNU Operating System platform."""

   def add_dir_to_dynlib_env_path(self, dictEnv, sDir):
      """See Platform.add_dir_to_dynlib_env_path()."""

      sLibPath = dictEnv.get('LD_LIBRARY_PATH', '')
      if sLibPath:
         sLibPath = ':' + sLibPath
      sLibPath += os.path.abspath(sDir)
      dictEnv['LD_LIBRARY_PATH'] = sLibPath
      return dictEnv


   def configure_tool(self, tool):
      """See Platform.configure_tool()."""

      if isinstance(tool, make.tool.Linker):
         tool.add_input_lib('dl')
         tool.add_input_lib('pthread')


   def dynlib_file_name(self, sName):
      """See Platform.dynlib_file_name()."""

      return 'lib{}.so'.format(sName)


   def exe_file_name(self, sName):
      """See Platform.exe_file_name()."""

      return '{}'.format(sName)


   @classmethod
   def _match_system_type(cls, systype):
      """See Platform._match_system_type()."""

      return systype.os == 'gnu'



####################################################################################################
# WinPlatform

@Platform.match_name('win32')
class WinPlatform(Platform):
   """Generic Windows platform."""

   def add_dir_to_dynlib_env_path(self, dictEnv, sDir):
      """See Platform.add_dir_to_dynlib_env_path()."""

      sLibPath = dictEnv.get('PATH', '')
      if sLibPath:
         sLibPath = ';' + sLibPath
      sLibPath += os.path.abspath(sDir)
      dictEnv['PATH'] = sLibPath
      return dictEnv


   def configure_tool(self, tool):
      """See Platform.configure_tool()."""

      if isinstance(tool, make.tool.Linker):
         tool.add_input_lib('kernel32')


   def dynlib_file_name(self, sName):
      """See Platform.dynlib_file_name()."""

      return '{}.dll'.format(sName)


   # See Platform.dynlibs_need_implibs.
   dynlibs_need_implibs = True


   def exe_file_name(self, sName):
      """See Platform.exe_file_name()."""

      return '{}.exe'.format(sName)



####################################################################################################
# Win32Platform

class Win32Platform(WinPlatform):
   """Win32 platform."""

   @classmethod
   def _match_system_type(cls, systype):
      """See WinPlatform._match_system_type()."""

      return systype.machine in ('i386', 'i486', 'i586', 'i686') and \
             systype.os in ('win32', 'mingw', 'mingw32')



####################################################################################################
# Win64Platform

class Win64Platform(WinPlatform):
   """Win64 platform."""

   @classmethod
   def _match_system_type(cls, systype):
      """See WinPlatform._match_system_type()."""

      return systype.machine == 'x86_64' and systype.os in ('win64', 'mingw64')

