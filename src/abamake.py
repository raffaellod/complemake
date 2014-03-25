#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013, 2014
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

"""Builds outputs and runs unit tests as specified in a .abcmk file."""

import os
import sys

import make



####################################################################################################
# __main__

def main(iterArgs):
   """Implementation of __main__.

   iterable(str*) iterArgs
      Command-line arguments.
   int return
      Command return status.
   """

   mk = make.Make()
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
            elif sArgChar == 'v':
               mk.log.verbosity += 1
            ich += 1
      else:
         break
      iArg += 1

   # Check for a makefile name.
   sMakefilePath = None
   if iArg < iArgEnd:
      sArg = iterArgs[iArg]
      if sArg.endswith('.abcmk'):
         # Save the argument as the makefile path and consume it.
         sMakefilePath = sArg
         iArg += 1
   # No makefile specified?
   if not sMakefilePath:
      # Check if the current directory contains a single ABC makefile.
      for sFilePath in os.listdir():
         if sFilePath.endswith('.abcmk') and len(sFilePath) > len('.abcmk'):
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
         iterTargets.append(mk.get_target_by_name(sArg, None) or mk.get_target_by_file_path(sArg))
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

