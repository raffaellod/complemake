#!/usr/bin/env python
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

"""Builds outputs and runs tests as specified in a .comk file."""

# TODO: maybe support launching gdb/devenv to run one of the programs via debugger?
#
# POSIX:
#    gdb --args {exe}
#
# Win32:
#    devenv.exe /debugexe {exe}  Opens the specified executable to be debugged. The remainder of the command
#                                line is passed to this executable as its arguments.
#    vsjitdebugger.exe -p {pid}  Attaches the debugger from the command line.

from __future__ import absolute_import

import os
import platform as pyplatform
import sys

import comk.argparser
import comk.core
import comk.tool


##############################################################################################################

def main(args):
   """Implementation of __main__.

   iterable(str*) args
      Command-line arguments.
   int return
      Command return status.
   """

   if pyplatform.system() == 'Windows':
      def _win_safe_write(self, s):
         if not isinstance(s, bytes):
            s = bytes(s, encoding=self.encoding, errors='replace')
         self.buffer.write(s)
         self.buffer.flush()
      sys.stderr.write = lambda s: _win_safe_write(sys.stderr, s)
      sys.stdout.write = lambda s: _win_safe_write(sys.stdout, s)

   args = comk.argparser.Parser().parse_args()

   core = comk.core.Core()
   core.dry_run = args.dry_run
   core.output_dir = args.output_dir
   core.project_path = os.getcwd()
   if args.target_system_type:
      core.set_target_platform(args.target_system_type)
   if args.tool_cxx:
      core.target_platform.set_tool(comk.tool.CxxCompiler, args.tool_cxx)
      if not args.tool_ld:
         # Also use the C++ compiler as the linker driver.
         core.target_platform.set_tool(comk.tool.Linker, args.tool_cxx)
   if args.tool_ld:
      core.target_platform.set_tool(comk.tool.Linker, args.tool_ld)
   core.log.verbosity += args.verbose

   # Find a project if one was not specified.
   if not args.project:
      try:
         args.project = core.find_project_file()
      except comk.core.AmbiguousProjectError as x:
         sys.stderr.write(
            'error: could not determine which project to build in the current folder; please specify one ' +
            'explicitly with --project PROJECT.comk\n'
         )
         return 1
   core.parse(args.project)
#   core.print_target_graphs()

   if args.command is comk.argparser.Command.BUILD:
      if args.jobs:
         core.job_runner.running_jobs_max = args.jobs
      core.force_build = args.force_build
      core.force_test = args.force_test
      core.keep_going = args.keep_going

      core.prepare_external_dependencies()
      # If any targets were specified, only a subset of the targets should be built; otherwise all named targets
      # will be built.
      if args.target:
         # core.get_file_target() will raise an exception if no such file target is defined.
         targets = (
            core.get_named_target(target, None) or core.get_file_target(os.path.normpath(target)) \
               for target in args.target
         )
      else:
         targets = core.named_targets

      # Build the selected targets.
      all_succeeded = core.build_targets(targets)

      core.log.test_summary()
      return 0 if all_succeeded else 1
   elif args.command is comk.argparser.Command.CLEAN:
      core.clean()
      return 0

if __name__ == '__main__':
   sys.exit(main(sys.argv))
