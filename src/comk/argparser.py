# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013-2017 Raffaello D. Di Napoli
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

"""Complemake command line argument parsing."""

import argparse
import os

import comk


##############################################################################################################

class Command(object):
   _instances = {}

   def __init__(self, name):
      self._name = name
      self._instances[name] = self

   def __repr__(self):
      return self._name

   @classmethod
   def from_str(cls, name):
      return cls._instances.get(name, name)

Command.BUILD = Command('build')
Command.CLEAN = Command('clean')
Command.QUERY = Command('query')

##############################################################################################################

class Parser(object):
   """Parses Complemake’s command line."""

   _parser = None

   def __init__(self):
      """Constructor."""

      self._parser = argparse.ArgumentParser(add_help=False)

      # Flags that apply to all commands.
      self._parser.add_argument(
         '--help', action='help',
         help='Show this informative message and exit.'
      )
      self._parser.add_argument(
         '-n', '--dry-run', action='store_true',
         help='Don’t actually run any external commands. Useful to test if anything needs to be built.'
      )
      self._parser.add_argument(
         '-o', '--output-dir', metavar='/path/to/output/dir', default='',
         help='Location where all Complemake output for the project should be stored. Defaults to the ' +
              'project’s directory.'
      )
      self._parser.add_argument(
         '-p', '--project', metavar='PROJECT.comk',
         help='Complemake project (.comk) containing instructions on how to build targets. If omitted and ' +
              'the current directory contains a single file matching *.comk, that file will be used as the ' +
              'project.'
      )
      if comk.os_is_windows():
         default_shared_dir = 'Complemake'
         user_apps_home_description = 'common repository for application-specific data (typically ' + \
                                      '“Application Data”)'
      else:
         default_shared_dir = '.comk'
         user_apps_home_description = 'user’s $HOME directory'
      self._parser.add_argument(
         '--shared-dir', metavar='path/to/shared/dir', type=self.get_abs_shared_dir,
         default=default_shared_dir,
         help=('Directory where Complemake will store data shared across all projects, such as projects’ ' +
               'dependencies. Defaults to “{}” in the {}.').format(
                  default_shared_dir, user_apps_home_description
               )
      )
      self._parser.add_argument(
         '-s', '--system-type', metavar='SYSTEM-TYPE',
         help='Use SYSTEM-TYPE as the system type for which to build; examples: x86_64-pc-linux-gnu, ' +
              'i686-pc-win32. If omitted, detect a default for the machine on which Complemake is being run.'
      )
      self._parser.add_argument(
         '--tool-c++', metavar='/path/to/c++', dest='tool_cxx',
         help='Use /path/to/c++ as the C++ compiler (and linker driver, unless --tool-ld is also specified).'
      )
      self._parser.add_argument(
         '--tool-ld', metavar='/path/to/ld',
         help='Use /path/to/ld as the linker/linker driver.'
      )
      self._parser.add_argument(
         '-v', '--verbose', action='count', default=0,
         help='Increase verbosity level; can be specified multiple times.'
      )

      subparsers = self._parser.add_subparsers(dest='command')
      subparsers.type = Command.from_str
      subparsers.required = True

      build_subparser = subparsers.add_parser(Command.BUILD)
      build_subparser.add_argument(
         '--force', action='store_true', dest='force_build',
         help='Unconditionally rebuild all targets.'
      )
      build_subparser.add_argument(
         '--force-test', action='store_true',
         help='Unconditionally run all test targets.'
      )
      build_subparser.add_argument(
         '-j', '--jobs', default=None, metavar='N', type=int,
         help='Build using N processes at at time; if N is omitted, build all independent targets at the ' +
              'same time. If not specified, the default is --jobs <number of processors>.'
      )
      build_subparser.add_argument(
         '-k', '--keep-going', action='store_true',
         help='Continue building targets even if other independent targets fail.'
      )
      build_subparser.add_argument(
         '-f', '--target-file', metavar='/generated/file', action='append', dest='target_files', default=[],
         help='Specify once or more to indicate which target files should be built. ' +
              'If no -f or -t arguments are provided, all targets declared in the Complemake project ' +
              '(.comk) will be built.'
      )
      build_subparser.add_argument(
         '-t', '--target-name', action='append', dest='target_names', default=[],
         help='Specify once or more to indicate which named targets should be built. ' +
              'If no -f or -t arguments are provided, all targets declared in the Complemake project ' +
              '(.comk) will be built.'
      )

      clean_subparser = subparsers.add_parser(Command.CLEAN)

      query_subparser = subparsers.add_parser(Command.QUERY)
      query_group = query_subparser.add_mutually_exclusive_group(required=True)
      query_group.add_argument(
         '--exec-env', action='store_true',
         help='Print any environment variable assignments needed to execute binaries build by the project.'
      )

   @staticmethod
   def get_abs_shared_dir(shared_dir):
      if os.path.isabs(shared_dir):
         return shared_dir
      else:
         return os.path.normpath(os.path.join(comk.get_user_apps_home(), shared_dir))

   def parse_args(self, *args, **kwargs):
      """See argparse.ArgumentParser.parse_args()."""

      return self._parser.parse_args(*args, **kwargs)
