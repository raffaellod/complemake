#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013, 2014
# Raffaello D. Di Napoli
#
# This file is part of Abaclade.
#
# Abaclade is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Abaclade is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
# the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Abaclade. If not, see
# <http://www.gnu.org/licenses/>.
#---------------------------------------------------------------------------------------------------

"""Builds outputs and runs unit tests as specified in a .abamk file."""

# TODO: maybe support launching gdb/devenv to run one of the programs via debugger?
#
# POSIX:
#    gdb --args {exe}
#
# Win32:
#    devenv.exe /debugexe {exe}  Opens the specified executable to be debugged. The remainder of the
#                                command line is passed to this executable as its arguments.
#    vsjitdebugger.exe -p {pid}  Attaches the debugger from the command line.


import os
import sys

import abamake



####################################################################################################
# Globals

def helptext(sInvalidArg):
   """Displays a message with instructions on how to invoke Abamake. This function does not return.

   str sInvalidArg
      Invalid argument that prompted to show this message, or None if --help was specified on the
      command line.
   """

   import textwrap
   if sInvalidArg:
      fnWrite = sys.stderr.write
      fnWrite('error: unknown option argument: {}\n'.format(sInvalidArg))
   else:
      fnWrite = sys.stdout.write
   fnWrite(textwrap.dedent("""\
      Usage: abamake.py [options] [makefile] [targets...]
      Options:
      -f, --force-build   Unconditionally rebuild targets.
      -j [N], --jobs[=N]  Build using N processes at at time; if N is omitted,
                          build all independent targets at the same time. If not
                          specified, the default is --jobs=<number of processors>.
      -k, --keep-going    Continue building targets even if other independent
                          targets fail.
      -n, --dry-run       Don’t actually run any external commands. Useful to test
                          if anything needs to be built.
      -t, --force-test    Unconditionally run all test targets.
      -v, --verbose       Increase verbosity level; can be specified multiple
                          times.
   """))
   sys.exit(1 if sInvalidArg else 0)


def main(iterArgs):
   """Implementation of __main__.

   iterable(str*) iterArgs
      Command-line arguments.
   int return
      Command return status.
   """

   mk = abamake.Make()
   iArg = 1
   iArgEnd = len(iterArgs)

   # Parse arguments, looking for option flags.
   while iArg < iArgEnd:
      sArg = iterArgs[iArg]
      if sArg.startswith('--'):
         if sArg == '--dry-run':
            mk.job_controller.dry_run = True
         elif sArg == '--force-build':
            mk.job_controller.force_build = True
         elif sArg == '--force-test':
            mk.job_controller.force_test = True
         elif sArg == '--help':
            helptext(None)
         elif sArg.startswith('--jobs'):
            if sArg[len('--jobs')] == '=':
               cJobs = int(sArg[len('--jobs') + 1:])
            else:
               cJobs = 999999
            mk.job_controller.running_jobs_max = cJobs
         elif sArg == '--keep-going':
            mk.job_controller.keep_going = True
         elif sArg == '--verbose':
            mk.log.verbosity += 1
         else:
            helptext(sArg)
      elif sArg.startswith('-'):
         ich = 1
         ichEnd = len(sArg)
         while ich < ichEnd:
            sArgChar = sArg[ich]
            if sArgChar == 'f':
               mk.job_controller.force_build = True
            elif sArgChar == 'j':
               # TODO: make this parsing more generic and more flexible.
               ichNumberLast = ich + 1
               while ichNumberLast < ichEnd and sArg[ichNumberLast] in '0123456789':
                  ichNumberLast += 1
               if ichNumberLast > ich + 1:
                  cJobs = int(sArg[ich + 1:ichNumberLast])
               else:
                  cJobs = 999999
               mk.job_controller.running_jobs_max = cJobs
            elif sArgChar == 'k':
               mk.job_controller.keep_going = True
            elif sArgChar == 'n':
               mk.job_controller.dry_run = True
            elif sArgChar == 't':
               mk.job_controller.force_test = True
            elif sArgChar == 'v':
               mk.log.verbosity += 1
            else:
               helptext(sArg)
            ich += 1
      else:
         break
      iArg += 1

   # Check for a makefile name.
   sMakefilePath = None
   if iArg < iArgEnd:
      sArg = iterArgs[iArg]
      if sArg.endswith('.abamk'):
         # Save the argument as the makefile path and consume it.
         sMakefilePath = sArg
         iArg += 1
   # No makefile specified?
   if not sMakefilePath:
      # Check if the current directory contains a single Abamakefile.
      for sFilePath in os.listdir(os.getcwd()):
         if sFilePath.endswith('.abamk') and len(sFilePath) > len('.abamk'):
            if sMakefilePath:
               sys.stderr.write(
                  'error: multiple makefiles found in the current directory, please specify one ' +
                     'explicitly\n'
               )
               return 1
            sMakefilePath = sFilePath
      # Still no makefile?
      if not sMakefilePath:
         sys.stderr.write('error: no makefile specified\n')
         return 1

   # Load the makefile.
   mk.parse(sMakefilePath)

#   mk.print_target_graphs()

   # If there are more argument, they will be treated as target named, indicating that only a subset
   # of the targets should be built; otherwise all named targets will be built.
   if iArg < iArgEnd:
      iterTargets = []
      while iArg < iArgEnd:
         sArg = iterArgs[iArg]
         # mk.get_file_target() will raise an exception if no such file target is defined.
         iterTargets.append(
            mk.get_named_target(sArg, None) or mk.get_file_target(os.path.normpath(sArg))
         )
         iArg += 1
   else:
      iterTargets = mk.named_targets

   # Build all selected targets: first schedule the jobs building them, then run them.
   for tgt in iterTargets:
      mk.job_controller.schedule_build(tgt)
   cFailedBuilds = mk.job_controller.build_scheduled_targets()
   mk.log.test_summary()
   return 0 if cFailedBuilds == 0 else 1


if __name__ == '__main__':
   sys.exit(main(sys.argv))

