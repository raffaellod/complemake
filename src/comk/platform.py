# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2014-2017 Raffaello D. Di Napoli
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

"""Classes that abstract different software platforms, concealing their differences for the rest of
Complemake.
"""

from __future__ import absolute_import

import os
import platform as pyplatform
import re
import sys

import comk
import comk.tool


##############################################################################################################

class SystemTypeError(Exception):
   """Indicates an error related to system types."""

   pass

##############################################################################################################

class SystemTypeTupleError(ValueError, SystemTypeError):
   """Raised when an invalid system type tuple is encountered."""

   pass

##############################################################################################################

class SystemType(object):
   """System type tuple.

   See <http://wiki.osdev.org/Target_Triplet> for a clear and concise explanation.
   """

   # See SystemType.kernel.
   _kernel = None
   # See SystemType.machine.
   _machine = None
   # See SystemType.os.
   _os = None
   # See SystemType.parsed_source.
   _parsed_source = None
   # See SystemType.vendor.
   _vendor = None

   def __init__(self, machine, vendor, kernel, os_):
      """Constructor.

      str machine
         See SystemType.machine.
      str kernel
         See SystemType.kernel.
      str vendor
         See SystemType.vendor.
      str os_
         See SystemType.os.
      """

      self._kernel = kernel
      self._machine = machine
      self._os = os_
      self._parsed_source = None
      self._vendor = vendor

   def __eq__(self, other):
      return \
         self._none_or_equal(self._kernel,  other._kernel ) and \
         self._none_or_equal(self._machine, other._machine) and \
         self._none_or_equal(self._os,      other._os     ) and \
         self._none_or_equal(self._vendor,  other._vendor )

   def __hash__(self):
      # Hashes like a tuple.
      return hash((self._machine, self._vendor, self._kernel, self._os))

   def __len__(self):
      return int(bool(self._machine)) + int(bool(self._vendor)) + \
             int(bool(self._os     )) + int(bool(self._kernel))

   def __ne__(self, other):
      return not self.__eq__(other)

   def __str__(self):
      if self._parsed_source:
         return self._parsed_source
      # TODO: don’t to this.
      vendor = self._vendor or 'unknown'
      if self._kernel:
         return '{}-{}-{}-{}'.format(self._machine, vendor, self._kernel, self._os)
      if self._os:
         return '{}-{}-{}'.format(self._machine, vendor, self._os)
      if self._vendor:
         return '{}-{}'.format(self._machine, self._vendor)
      if self._machine:
         return '{}'.format(self._machine)
      return 'unknown'

   @staticmethod
   def detect_host():
      """Returns a SystemType instance describing the host on which Complemake is being run.

      comk.platform.SystemType return
         Host system type.
      """

      os_, node, release, version, machine, processor = pyplatform.uname()

      if os_ == 'Windows':
         if machine == 'ARM':
            return SystemType('arm', None, None, 'win32')
         elif machine == 'x86':
            return SystemType('i386', None, None, 'win32')
         elif machine == 'AMD64':
            return SystemType('x86_64', None, None, 'win64')
      elif os_ in ('Darwin', 'FreeBSD', 'Linux'):
         vendor = None
         kernel = None
         if os_ == 'Linux':
            kernel = 'linux'
            # TODO: don’t assume OS == GNU.
            os_ = 'gnu'
         else:
            os_ = os_.lower()
            if machine == 'amd64':
               machine = 'x86_64'
            if os_ == 'darwin':
               # TODO: don’t assume Vendor == Apple.
               vendor = 'apple'
            # Add the release version number to the OS field.
            match = re.match(r'^\d+(?:\.\d+)*', release)
            if match:
               os_ += match.group()
         if machine in ('i386', 'i486', 'i586', 'i686', 'x86_64'):
            return SystemType(machine, vendor, kernel, os_)

      raise SystemTypeError('unsupported system type')

   def _get_kernel(self):
      return self._kernel

   kernel = property(_get_kernel, doc="""
      Kernel on which the OS runs. Mostly used for the GNU operating system.
   """)

   def _get_machine(self):
      return self._machine

   machine = property(_get_machine, doc="""
      Machine type; often this is the processor’s architecture. Examples: 'i386', 'sparc'.
   """)

   @staticmethod
   def _none_or_equal(o1, o2):
      """Returns True if the two values are equal or if either is None.

      object o1
         First value to compare.
      object o2
         Second value to compare.
      bool return
         True if o1 == o2 or either is None, or False otherwise.
      """

      return not o1 or not o2 or o1 == o2

   def _get_os(self):
      return self._os

   os = property(_get_os, doc="""
      Operating system running on the system, or type of object file format for embedded systems. Examples:
      'solaris2.5', 'irix6.3', 'elf', 'coff'.
   """)

   @staticmethod
   def parse_tuple(tpl_source):
      """Parses a system type tuple into a SystemType instance. The format of the tuple must be one of:
      •  machine (1 item)
      •  machine-os (2 items)
      •  machine-vendor-os (3 items)
      •  machine-vendor-kernel-os (4 items)

      str tpl_source
         String that will be parsed to extract the necessary information.
      comk.platform.SystemType return
         Parsed system type.
      """

      # Break the tuple down.
      tpl = tpl_source.split('-')
      tpl_len = len(tpl)
      ret = None
      if tpl_len == 1:
         # The tuple contains “machine” only.
         ret = SystemType(tpl[0])
      elif tpl_len == 2:
         # The tuple contains “machine” and “os”.
         ret = SystemType(tpl[0], None, None, tpl[1])
      else:
         # The tuple contains “machine”, “vendor” and/or “kernel”, and “os”.
         # Suppress placeholders in the “vendor” field.
         if tpl[1] in ('none', 'unknown'):
            tpl[1] = None
         if tpl_len == 3:
            # Assume that GNU always requires a kernel to be part of the tuple.
            # TODO: find a way to avoid this? It could become a long list of “special cases”.
            if tpl[2] == 'gnu':
               # The tuple contains “machine”, “kernel” and “os”.
               ret = SystemType(tpl[0], None, tpl[1], tpl[2])
            else:
               # The tuple contains “machine”, “vendor” and “os”.
               ret = SystemType(tpl[0], tpl[1], None, tpl[2])
         elif tpl_len == 4:
            # The tuple contains “machine”, “vendor”, “kernel” and “os”.
            ret = SystemType(*tpl)
      if not ret:
         raise SystemTypeTupleError('invalid system type tuple: “{}”'.format(tpl_source))
      # Assign the SystemType the string it was parsed from.
      ret._parsed_source = tpl_source
      return ret

   def _get_parsed_source(self):
      return self._parsed_source

   parsed_source = property(_get_parsed_source, doc="""
      String from which the Platform object was parsed. Example: 'x86_64-pc-linux-gnu'.
   """)

   def _get_vendor(self):
      return self._vendor

   vendor = property(_get_vendor, doc="""Vendor. Examples: 'unknown'. 'pc', 'sun'.""")

##############################################################################################################

class Platform(object):
   """Generic software platform (OS/runtime environment)."""

   # Factories that create Tools for this platform. Associates a Tool non-leaf subclass to a factory able to
   # instantiate a leaf class configured for this platform’s system type (comk.tool.Tool =>
   # comk.tool.ToolFactory).
   _tool_factories = None
   # System type (more specific than the platform type).
   _system_type = None

   def __init__(self, system_type):
      """Constructor.

      comk.platform.SystemType system_type
         System type of this platform.
      """

      self._tool_factories = {}
      self._system_type = system_type

   def add_dir_to_dynlib_env_path(self, env, dir):
      """Modifies an environment dictionary (similar to os.environ) so that it allows to load dynamic
      libraries from the specified directory.

      dict(str: str) env
         Environment dictionary.
      str dir
         Directory to add to the dynlib path.
      dict(str: str) return
         Same as env, returned for convenience.
      """

      raise NotImplementedError(
         'Platform.add_dir_to_dynlib_env_path() must be overridden in ' + type(self).__name__
      )

   def adjust_popen_args_for_script(self, popen_args):
      """Adjusts a dictionary of arguments to be used to run a program with subprocess.Popen in a way that
      allows to execute non-programs (e.g. scripts), by changing the command into a shell invocation if
      necessary.

      The default implementation assumes that scripts can be executed directly (e.g. via shebang) without any
      changes to popen_args.

      dict(str: object) popen_args
         Popen arguments dictionary.
      """

      pass

   def configure_tool(self, tool):
      """Configures the specified tool for this platform.

      comk.tool.Tool tool
         Tool to configure.
      """

      pass

   @classmethod
   def detect_host(cls):
      """Attempts to detect the underlying (host) platform, returning an instance of the Platform subclass
      that models it best.

      comk.platform.Platform return
         Model for the underlying (host) platform.
      """

      return cls.from_system_type(SystemType.detect_host())

   def dynlib_file_name(self, name):
      """Generates a file name for a dynamic library from the specified name.

      str name
         Name of the dynamic library.
      str return
         Name of the dynamic library’s file.
      """

      raise NotImplementedError('Platform.dynlib_file_name() must be overridden in ' + type(self).__name__)

   # If True, dynamic libraries need import libraries (i.e. statically-linked runtime-patchable data) for the
   # linker to be able to generate executables that link to them; if False, dynlibs can be linked to directly.
   dynlibs_need_implibs = False

   def exe_file_name(self, name):
      """Generates an executable file name from the specified name.

      str name
         Name of the executable.
      str return
         Name of the executable’s file.
      """

      raise NotImplementedError('Platform.exe_file_name() must be overridden in ' + type(self).__name__)

   @classmethod
   def from_system_type(cls, system_type):
      """Returns an instance of the Platform subclass that most closely matches the specified system type. For
      example, Platform.from_system_type(SystemType.parse_tuple('i686-pc-linux-gnu')) will return a
      comk.platform.GnuPlatform instance.

      comk.platform.SystemType system_type
         System type.
      comk.platform.Platform return
         Corresponding platform.
      """

      best_match_index = 0
      best_match_cls = None
      for devired_cls in comk.derived_classes(cls):
         match = devired_cls._match_system_type(system_type)
         if match > best_match_index:
            best_match_index = match
            best_match_cls = devired_cls
      if not best_match_cls:
         raise Exception('unable to detect platform for system type {}'.format(system_type))
      return best_match_cls(system_type)

   def get_tool(self, tool_cls):
      """Returns a leaf subclass of the specified Tool non-leaf subclass modeling the implementation of the
      specified tool for the platform.

      For example, my_platform.get_tool(comk.tool.CxxCompiler) will return an instance of
      comk.tool.GxxCompiler if G++ is the C++ compiler for my_platorm.

      type tool_cls
         Subclass of comk.tool.Tool.
      type return
         Instance of a tool_cls subclass.
      """

      tool_factory_cls = self._tool_factories.get(tool_cls)
      if not tool_factory_cls:
         tool_factory_cls = tool_cls.get_factory(None, self._system_type)
         self._tool_factories[tool_cls] = tool_factory_cls
#        print('using {} as {}'.format(tool_factory_cls._file_path, tool_cls.__name__))
      return tool_factory_cls()

   @classmethod
   def _match_system_type(cls, system_type):
      """Returns a confidence index of how much the platform models the specified system type.

      The default implementation always returns 0.

      comk.platform.SystemType system_type
         System type.
      int return
         A value in range 0-4, representing how many elements of system_type match the platform.
      """

      return 0

   def set_tool(self, tool_cls, file_path):
      """Applies the user’s choice of executable to be used as the specified tool type (e.g. CxxCompiler),
      detecting the tool subtype (e.g. ClangxxCompiler).

      type tool_cls
         Subclass of comk.tool.Tool.
      str file_path
         Path to the tool’s executable.
      """

      if tool_cls in self._tool_factories:
         raise Exception('tool {} already set or detected for system type {}'.format(
            tool_cls.__name__, self._system_type
         ))
      tool_factory_cls = tool_cls.get_factory(file_path, self._system_type)
      self._tool_factories[tool_cls] = tool_factory_cls
 #    print('using {} as {}'.format(tool_factory_cls._file_path, tool_cls.__name__))

   def system_type(self):
      """Returns the system type from which the Platform instance was created.

      comk.platform.SystemType return
         System type.
      """

      return self._system_type

##############################################################################################################

class DarwinPlatform(Platform):
   """Darwin (OS X) platform."""

   def add_dir_to_dynlib_env_path(self, env, dir):
      """See Platform.add_dir_to_dynlib_env_path()."""

      lib_path = env.get('DYLD_LIBRARY_PATH', '')
      if lib_path:
         lib_path += ':'
      lib_path += dir
      env['DYLD_LIBRARY_PATH'] = lib_path
      return env

   def configure_tool(self, tool):
      """See Platform.configure_tool()."""

      pass

   def dynlib_file_name(self, name):
      """See Platform.dynlib_file_name()."""

      return 'lib{}.dylib'.format(name)

   def exe_file_name(self, name):
      """See Platform.exe_file_name()."""

      return '{}'.format(name)

   @classmethod
   def _match_system_type(cls, system_type):
      """See Platform._match_system_type()."""

      if system_type.os.startswith('darwin'):
         return 1
      else:
         return 0

##############################################################################################################

class FreeBsdPlatform(Platform):
   """FreeBSD platform."""

   def add_dir_to_dynlib_env_path(self, env, dir):
      """See Platform.add_dir_to_dynlib_env_path()."""

      lib_path = env.get('LD_LIBRARY_PATH', '')
      if lib_path:
         lib_path += ':'
      lib_path += dir
      env['LD_LIBRARY_PATH'] = lib_path
      return env

   def configure_tool(self, tool):
      """See Platform.configure_tool()."""

      if isinstance(tool, comk.tool.Linker):
         tool.add_input_lib('pthread')

   def dynlib_file_name(self, name):
      """See Platform.dynlib_file_name()."""

      return 'lib{}.so'.format(name)

   def exe_file_name(self, name):
      """See Platform.exe_file_name()."""

      return '{}'.format(name)

   @classmethod
   def _match_system_type(cls, system_type):
      """See Platform._match_system_type()."""

      if system_type.os.startswith('freebsd'):
         return 1
      else:
         return 0

##############################################################################################################

class GnuPlatform(Platform):
   """GNU Operating System platform."""

   def add_dir_to_dynlib_env_path(self, env, dir):
      """See Platform.add_dir_to_dynlib_env_path()."""

      lib_path = env.get('LD_LIBRARY_PATH', '')
      if lib_path:
         lib_path += ':'
      lib_path += dir
      env['LD_LIBRARY_PATH'] = lib_path
      return env

   def configure_tool(self, tool):
      """See Platform.configure_tool()."""

      if isinstance(tool, comk.tool.Linker):
         tool.add_input_lib('dl')
         tool.add_input_lib('pthread')

   def dynlib_file_name(self, name):
      """See Platform.dynlib_file_name()."""

      return 'lib{}.so'.format(name)

   def exe_file_name(self, name):
      """See Platform.exe_file_name()."""

      return '{}'.format(name)

   @classmethod
   def _match_system_type(cls, system_type):
      """See Platform._match_system_type()."""

      if system_type.os in ('gnu', 'gnueabi'):
         return 1
      else:
         return 0

##############################################################################################################

class WinPlatform(Platform):
   """Generic Windows platform."""

   def add_dir_to_dynlib_env_path(self, env, dir):
      """See Platform.add_dir_to_dynlib_env_path()."""

      lib_path = env.get('PATH', '')
      if lib_path:
         lib_path += ';'
      lib_path += dir
      env['PATH'] = lib_path
      return env

   def adjust_popen_args_for_script(self, popen_args):
      """See Platform.adjust_popen_args_for_script()."""

      arg0 = popen_args['args'][0]
      if not arg0.endswith('.exe') and not arg0.endswith('.com'):
         # Windows cannot execute non-executables directly; have a shell figure out how to run this script.
         popen_args['shell'] = True

   def configure_tool(self, tool):
      """See Platform.configure_tool()."""

      if isinstance(tool, comk.tool.Linker):
         tool.add_input_lib('advapi32')
         tool.add_input_lib('kernel32')
         tool.add_input_lib('mswsock')
         tool.add_input_lib('user32')
         tool.add_input_lib('ws2_32')

   def dynlib_file_name(self, name):
      """See Platform.dynlib_file_name()."""

      return '{}.dll'.format(name)

   # See Platform.dynlibs_need_implibs.
   dynlibs_need_implibs = True

   def exe_file_name(self, name):
      """See Platform.exe_file_name()."""

      return '{}.exe'.format(name)

##############################################################################################################

class Win32Platform(WinPlatform):
   """Win32 platform."""

   @classmethod
   def _match_system_type(cls, system_type):
      """See WinPlatform._match_system_type()."""

      if system_type.machine in ('arm', 'i386', 'i486', 'i586', 'i686') and \
         system_type.os in ('win32', 'mingw', 'mingw32') \
      :
         return 2
      else:
         return 0

##############################################################################################################

class Win64Platform(WinPlatform):
   """Win64 platform."""

   @classmethod
   def _match_system_type(cls, system_type):
      """See WinPlatform._match_system_type()."""

      if system_type.machine == 'x86_64' and system_type.os in ('win64', 'mingw64'):
         return 2
      else:
         return 0
