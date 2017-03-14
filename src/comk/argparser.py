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

##############################################################################################################

class Parser(object):
   """Parses Complemake’s command line."""

   _parser = None

   def __init__(self):
      """Constructor."""

      self._parser = argparse.ArgumentParser(add_help=False)

      # Flags that apply to all commands.
      self._parser.add_argument(
         '-g', '--target-system-type', metavar='SYSTEM-TYPE',
         help='Use SYSTEM-TYPE (e.g. dash-separated triplet) as the build target system type.'
      )
      self._parser.add_argument(
         '--help', action='help',
         help='Show this informative message and exit.'
      )
      self._parser.add_argument(
         '-n', '--dry-run', action='store_true', default=False,
         help='Don’t actually run any external commands. Useful to test if anything needs to be built.'
      )
      self._parser.add_argument(
         '-o', '--output-dir', metavar='/path/to/output/dir', default='',
         help='Location where all Complemake output for the project should be stored. Defaults to the ' +
              'project’s directory.'
      )
      self._parser.add_argument(
         '-p', '--project', metavar='PROJECT.comk',
         help='Complemake file (.comk) containing instructions on how to build targets. If omitted and ' +
              'the current directory contains a single file matching *.comk, that file will be used as the ' +
              'project.'
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
         '--force', dest='force_build', action='store_true', default=False,
         help='Unconditionally rebuild all targets.'
      )
      build_subparser.add_argument(
         '--force-test', action='store_true', default=False,
         help='Unconditionally run all test targets.'
      )
      build_subparser.add_argument(
         '-j', '--jobs', default=None, metavar='N', type=int,
         help='Build using N processes at at time; if N is omitted, build all independent targets at the ' +
              'same time. If not specified, the default is --jobs <number of processors>.'
      )
      build_subparser.add_argument(
         '-k', '--keep-going', action='store_true', default=False,
         help='Continue building targets even if other independent targets fail.'
      )
      build_subparser.add_argument(
         'target', nargs='*',
         help='List of target files to be conditionally built. If none are specified, all targets declared ' +
              'in the Complemake file (.comk) will be conditionally built.'
      )

      clean_subparser = subparsers.add_parser(Command.CLEAN)

   def parse_args(self, *args, **kwargs):
      """See argparse.ArgumentParser.parse_args()."""

      return self._parser.parse_args(*args, **kwargs)
