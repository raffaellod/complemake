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

"""Job scheduling and execution classes."""

import multiprocessing
import subprocess
import time
import weakref

import make.target



####################################################################################################
# Job

class Job(object):
   """Job to be executed by a JobController instance."""

   def get_quiet_command(self):
      """Returns a command summary for Make to print out in quiet mode.

      iterable(str, str+) return
         Job’s command summary.
      """

      raise NotImplementedError(
         'Job.get_quiet_command() must be overridden in ' + type(self).__name__
      )


   def get_verbose_command(self):
      """Returns a command-line for Make to print out in verbose mode.

      str return
         Job’s command line.
      """

      raise NotImplementedError(
         'Job.get_verbose_command() must be overridden in ' + type(self).__name__
      )


   def poll(self):
      """Returns the execution status of the job. If the job is never started (e.g. due to “dry run”
      mode), the return value will be 0.

      int return
         Exit code of the job, or None if the job is still running, or 0 if the job was not started.
      """

      raise NotImplementedError('Job.poll() must be overridden in ' + type(self).__name__)


   def start(self):
      """Starts the job."""

      raise NotImplementedError('Job.start() must be overridden in ' + type(self).__name__)



####################################################################################################
# NoopJob

class NoopJob(Job):
   """No-op job. Used to avoid special-case logic to handle targets that don’t need to be (re)built.
   """

   __slots__ = (
      # Value that poll() will return.
      '_m_iRet',
   )


   def __init__(self, iRet):
      """Constructor.

      int iRet
         Value that poll() will return.
      """

      super().__init__()
      self._m_iRet = iRet


   def poll(self):
      """See Job.poll()."""

      return self._m_iRet



####################################################################################################
# ExternalCommandJob

class ExternalCommandJob(Job):
   """Models a job consisting in the invocation of an external program."""

   # Command summary to print out in quiet mode.
   _m_iterQuietCmd = None
   # Controlled Popen instance.
   _m_popen = None
   # Arguments to be passed to Popen’s constructor.
   _m_dictPopenArgs = None


   def __init__(self, iterQuietCmd, dictPopenArgs):
      """Constructor. See Job.__init__().

      iterable(str, str*) iterQuietCmd
         “Quiet mode” command; see return value of tool.Tool._get_quiet_cmd().
      dict(str: object) dictPopenArgs
         Arguments to be passed to Popen’s constructor to execute this job.
      """

      super().__init__()
      self._m_iterQuietCmd = iterQuietCmd
      self._m_dictPopenArgs = dictPopenArgs


   def get_quiet_command(self):
      """See Job.get_quiet_command()."""

      return self._m_iterQuietCmd


   def get_verbose_command(self):
      """See Job.get_verbose_command()."""

      return ' '.join(self._m_dictPopenArgs['args'])


   def poll(self):
      """See Job.poll()."""

      if self._m_popen is None:
         return 0
      else:
         return self._m_popen.poll()


   def start(self):
      """See Job.start()."""

      self._m_popen = subprocess.Popen(**self._m_dictPopenArgs)



####################################################################################################
# JobController

class JobController(object):
   """Schedules any jobs necessary to build targets in an ABC makefile (.abcmk), running them with
   the selected degree of parallelism.
   """

   # See JobController.dry_run.
   _m_bDryRun = False
   # See JobController.force_build.
   _m_bForceBuild = False
   # See JobController.ignore_errors.
   _m_bIgnoreErrors = False
   # See JobController.keep_going.
   _m_bKeepGoing = False
   # Weak reference to the owning make.Make instance.
   _m_mk = None
   # Running jobs for each target build (Job -> Target).
   _m_dictRunningJobs = None
   # Scheduled target builds.
   _m_setScheduledBuilds = None


   def __init__(self, mk):
      """Constructor.

      make.Make mk
         Make instance.
      """

      self._m_mk = weakref.ref(mk)
      self._m_dictRunningJobs = {}
      self.running_jobs_max = multiprocessing.cpu_count()
      self._m_setScheduledBuilds = set()


   def build_scheduled_targets(self):
      """Conditionally builds any targets scheduled for build.

      int return
         Count of jobs that completed in failure.
      """

      log = self._m_mk().log
      cFailedJobsTotal = 0
      while self._m_setScheduledBuilds:
         # Make sure any completed jobs are collected.
         cFailedJobs = self._collect_completed_jobs(0)
         # Make sure we have at least one free job slot.
         while len(self._m_dictRunningJobs) == self.running_jobs_max:
            # Wait for one or more jobs slots to free up.
            cFailedJobs += self._collect_completed_jobs(1)

         cFailedJobsTotal += cFailedJobs
         # Stop starting jobs in case of failed errors – unless overridden by the user.
         if cFailedJobs > 0 and not self._m_bKeepGoing:
            break

         # Find a target that is ready to be built.
         for tgt in self._m_setScheduledBuilds:
            if not tgt.is_build_blocked():
               # Execute this job.
               bBuild = tgt.is_build_needed()
               if bBuild:
                  log(log.MEDIUM, 'controller: {}: rebuilding due to detected changes\n', tgt)
               elif self._m_bForceBuild:
                  log(log.MEDIUM, 'controller: {}: up-to-date, but rebuild forced\n', tgt)
                  bBuild = True
               else:
                  log(log.MEDIUM, 'controller: {}: up-to-date\n', tgt)

               if bBuild:
                  job = tgt.build()
                  if log.verbosity >= log.LOW:
                     log(log.LOW, '{}\n', job.get_verbose_command())
                  else:
                     iterCmd = job.get_quiet_command()
                     log(log.QUIET, '{:^8} {}\n'.format(iterCmd[0], ' '.join(iterCmd[1:])))
                  if not self._m_bDryRun:
                     job.start()
               else:
                  job = NoopJob(0)

               # Move the target from scheduled builds to running jobs.
               self._m_dictRunningJobs[job] = tgt
               self._m_setScheduledBuilds.remove(tgt)
               # Since we modified self._m_setScheduledBuilds, we have to stop iterating over it;
               # the outer while loop will get back here, eventually.
               break

      # There are no more scheduled jobs, just wait for the running ones to complete.
      cFailedJobsTotal += self._collect_completed_jobs(len(self._m_dictRunningJobs))

      return cFailedJobsTotal


   def _collect_completed_jobs(self, cJobsToComplete):
      """Returns only after the specified number of jobs completes and the respective cleanup
      operations (such as releasing blocked jobs) have been performed. If cJobsToComplete == 0, it
      only performs cleanup for jobs that have already completed, without waiting.

      Returns the count of failed jobs, unless ignore_errors is True, in which case it will always
      return 0.

      int cJobsToComplete
         Count of jobs to wait for.
      int return
         Count of jobs that completed in failure.
      """

      mds = self._m_mk()._m_mds
      # This loop alternates poll loop and sleeping.
      cCompletedJobs = 0
      cFailedJobs = 0
      # The termination condition is in the middle.
      while True:
         # This loop restarts the for loop, since we modify self._m_dictRunningJobs. The termination
         # condition is a break statement.
         while True:
            # Poll each running job.
            for job in self._m_dictRunningJobs.keys():
               iRet = job.poll()
               if iRet is not None:
                  # Remove the target build from the running jobs.
                  tgt = self._m_dictRunningJobs.pop(job)
                  cCompletedJobs += 1
                  if iRet == 0 or self._m_bIgnoreErrors:
                     # The job completed successfully or we’re ignoring its failure: any dependent
                     # jobs can now be released.
                     tgt.release_blocked_builds()
                     # If the job was successfully executed, update any files’ metadata.
                     if iRet == 0 and not self._m_bDryRun:
                        mds.update_target_snapshot(tgt)
                  else:
                     if self._m_bKeepGoing:
                        # Unschedule any dependent jobs, so we can continue ignoring this failure as
                        # long as we have scheduled jobs that don’t depend on it.
                        self._unschedule_builds_blocked_by(tgt)
                     cFailedJobs += 1
                  # Since we modified self._m_dictRunningJobs, we have to stop iterating over it.
                  # Iteration will be restarted by the inner while loop.
                  break
            else:
               # The for loop completed without interruptions, which means that no job slots were
               # freed, so break out of the inner while loop into the outer one to wait.
               break
         # If we freed up the requested count of slots, there’s nothing left to do.
         if cCompletedJobs >= cJobsToComplete:
            return cFailedJobs
         if not self._m_bDryRun:
            # Wait a small amount of time.
            # TODO: proper event-based waiting.
            time.sleep(0.1)


   def _get_dry_run(self):
      return self._m_bDryRun

   def _set_dry_run(self, bDryRun):
      self._m_bDryRun = bDryRun

   dry_run = property(_get_dry_run, _set_dry_run, doc = """
      If True, commands will only be printed, not executed; if False, they will be printed and
      executed.
   """)


   def _get_force_build(self):
      return self._m_bForceBuild

   def _set_force_build(self, bForceBuild):
      self._m_bForceBuild = bForceBuild

   force_build = property(_get_force_build, _set_force_build, doc = """
      If True, targets are rebuilt unconditionally; if False, targets are rebuilt as needed.
   """)


   def _get_ignore_errors(self):
      return self._m_bIgnoreErrors

   def _set_ignore_errors(self, bIgnoreErrors):
      self._m_bIgnoreErrors = bIgnoreErrors

   ignore_errors = property(_get_ignore_errors, _set_ignore_errors, doc = """
      If True, scheduled jobs will continue to be run even after a job they depend on fails. If
      False, a failed job causes execution to stop according to the value of keep_going.
   """)


   def _get_keep_going(self):
      return self._m_bKeepGoing

   def _set_keep_going(self, bKeepGoing):
      self._m_bKeepGoing = bKeepGoing

   keep_going = property(_get_keep_going, _set_keep_going, doc = """
      If True, scheduled jobs will continue to be run even after a failed job, as long as they don’t
      depend on a failed job. If False, a failed job causes execution to stop as soon as any other
      running jobs complete.
   """)


   # Maximum count of running jobs, i.e. degree of parallelism. Defaults to the number of processors
   # in the system.
   running_jobs_max = None


   def schedule_build(self, tgt):
      """Schedules the build of the specified target and all its dependencies.

      The implementation recursively visits the dependency tree for the target in a leaves-first
      order, using a set for the builds scheduled to avoid duplicates (targets that are a dependency
      for more than one target).

      make.target.Target tgt
         Target the build of which should be scheduled.
      """

      # Check if we already scheduled this target.
      if tgt not in self._m_setScheduledBuilds:
         # Schedule the target’s dependencies (visit leaves).
         for dep in tgt.get_dependencies():
            if isinstance(dep, make.target.Target):
               # Recursively schedule this dependency target.
               self.schedule_build(dep)

         # Schedule a job for the target (visit node).
         self._m_setScheduledBuilds.add(tgt)


   def _unschedule_builds_blocked_by(self, tgt):
      """Recursively removes the target builds blocked by the specified target from the set of
      scheduled builds.

      make.target.Target tgt
         Target build to be unscheduled.
      """

      for tgtBlocked in tgt.get_dependents():
         # Use set.discard() instead of set.remove() since it may have already been removed due to a
         # previous unrelated call to this method, e.g. another job failed before the one that
         # caused this call.
         self._m_setScheduledBuilds.discard(tgtBlocked)
         self._unschedule_builds_blocked_by(tgtBlocked)

