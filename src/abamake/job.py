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
import sys
import time



####################################################################################################
# RunningJob

class RunningJob(object):
   """Runtime version of Job. Allows to synchronize with it and to check its return status."""

   __slots__ = ()


   def poll(self):
      """Returns the execution status of the job.

      int return
         Exit code of the job, or None if the job is still running.
      """

      raise NotImplementedError('RunningJob.poll() must be overridden')



####################################################################################################
# RunningNoopJob

class RunningNoopJob(RunningJob):
   """No-op running job. Used to implement Make’s “dry run” mode as well as jobs that are carried
   out synchronously.
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

      self._m_iRet = iRet


   def poll(self):
      """See RunningJob.poll()."""

      return self._m_iRet



####################################################################################################
# RunningPopenJob

class RunningPopenJob(RunningJob):
   """Running job consisting in an external process (Popen)."""

   __slots__ = (
      # Controlled Popen instance.
      '_m_popen',
   )


   def __init__(self, popen):
      """Constructor.

      Popen popen
         External process to take control of.
      """

      self._m_popen = popen


   def poll(self):
      """See RunningJob.poll()."""

      return self._m_popen.poll()



####################################################################################################
# Job

class Job(object):
   """Asynchronous job that is first scheduled and then executed by a Make instance. It keeps track
   of the jobs it depends on.
   """

   # Jobs that this one is blocking.
   _m_setBlockedJobs = None
   # Count of jobs that block this one.
   _m_cBlocks = 0
   # Paths to the input and output files for which we’ll need to update metadata after this job
   # completes.
   _m_iterMetadataToUpdate = None
   # Command summary for Make to print out in quiet mode..
   _m_iterQuietCmd = None


   def __init__(self, mk, iterBlockingJobs, iterQuietCmd, iterMetadataToUpdate):
      """Constructor.

      Make mk
         Make instance.
      iterable(Job*) iterBlockingJobs
         Jobs that block this one.
      iterable(str, str*) iterQuietCmd
         “Quiet mode” command; see return value of tool.Tool._get_quiet_cmd().
      iterable(str*) iterMetadataToUpdate
         Paths to the files for which metadata should be updated when this job completes.
      """

      self._m_iterQuietCmd = iterQuietCmd
      self._m_iterMetadataToUpdate = iterMetadataToUpdate
      if iterBlockingJobs is not None:
         # Assign this job as “blocked” by the jobs it depends on, and store their count.
         for jobDep in iterBlockingJobs:
            if jobDep._m_setBlockedJobs is None:
               jobDep._m_setBlockedJobs = set()
            jobDep._m_setBlockedJobs.add(self)
         self._m_cBlocks = len(iterBlockingJobs)
      # Schedule this job.
      mk.job_controller.schedule_job(self)


   def _get_blocked(self):
      return self._m_cBlocks > 0

   blocked = property(_get_blocked, doc = """
      True if the job is blocked (i.e. requires other jobs to be run first), or False otherwise.
   """)


   def get_quiet_command(self):
      """Returns a command summary for Make to print out in quiet mode.

      iterable(str, str+) return
         Job’s command summary.
      """

      return self._m_iterQuietCmd


   def get_verbose_command(self):
      """Returns a command-line for Make to print out in verbose mode.

      str return
         Job’s command line.
      """

      raise NotImplementedError('Job.get_verbose_command() must be overridden')


   def release_blocked(self):
      """Release any jobs this one was blocking."""

      if self._m_setBlockedJobs:
         for job in self._m_setBlockedJobs:
            job._m_cBlocks -= 1


   def start(self):
      """Starts the job, returning a RunningJob instance that can be used to check on the job’s
      execution status.

      RunningJob return
         Object to check the job status and eventual exit code.
      """

      raise NotImplementedError('Job.start() must be overridden')



####################################################################################################
# ExternalCommandJob

class ExternalCommandJob(Job):
   """Models a job consisting in the invocation of an external program."""

   # Arguments to be passed to Popen’s constructor.
   _m_dictPopenArgs = None


   def __init__(self, mk, iterBlockingJobs, iterQuietCmd, iterMetadataToUpdate, dictPopenArgs):
      """Constructor. See Job.__init__().

      Make mk
         Make instance.
      iterable(Job*) iterBlockingJobs
         Jobs that block this one.
      iterable(str, str*) iterQuietCmd
         “Quiet mode” command; see return value of tool.Tool._get_quiet_cmd().
      iterable(str*) iterMetadataToUpdate
         Paths to the files for which metadata should be updated when this job completes.
      dict(object+) dictPopenArgs
         Arguments to be passed to Popen’s constructor to execute this job.
      """

      super().__init__(mk, iterBlockingJobs, iterQuietCmd, iterMetadataToUpdate)
      self._m_dictPopenArgs = dictPopenArgs


   def get_verbose_command(self):
      """See Job.get_verbose_command()."""

      return ' '.join(self._m_dictPopenArgs['args'])


   def start(self):
      """See Job.start()."""

      return RunningPopenJob(subprocess.Popen(**self._m_dictPopenArgs))



####################################################################################################
# Controller

class Controller(object):
   """Schedules any jobs necessary to build targets in an ABC makefile (.abcmk), running them with
   the selected degree of parallelism.
   """

   # Running jobs (Popen -> Job).
   _m_dictRunningJobs = None
   # Scheduled jobs.
   _m_setScheduledJobs = None
   # “Last” scheduled jobs (Target -> Job that completes it), i.e. jobs that are the last in a chain
   # of jobs scheduled to build a single target. The values are a subset of, or the same as,
   # Make._m_setScheduledJobs.
   _m_dictTargetLastScheduledJobs = None


   def __init__(self):
      """Constructor."""

      self._m_dictRunningJobs = {}
      self.running_jobs_max = multiprocessing.cpu_count()
      self._m_setScheduledJobs = set()
      self._m_dictTargetLastScheduledJobs = {}


   def _collect_completed_jobs(self, mk, cJobsToComplete):
      """Returns only after the specified number of jobs completes and the respective cleanup
      operations (such as releasing blocked jobs) have been performed. If cJobsToComplete == 0, it
      only performs cleanup for jobs that have already completed, without waiting.

      Returns the count of failed jobs, unless Make.ignore_errors is True, in which case it will
      always return 0.

      Make mk
         Make instance.
      int cJobsToComplete
         Count of jobs to wait for.
      int return
         Count of jobs that completed in failure.
      """

      # This loop alternates poll loop and sleeping.
      cCompletedJobs = 0
      cFailedJobs = 0
      # The termination condition is in the middle.
      while True:
         # This loop restarts the for loop, since we modify _m_dictRunningJobs. The termination
         # condition is a break statement.
         while True:
            # Poll each running job.
            for rj in self._m_dictRunningJobs.keys():
               iRet = rj.poll()
               if iRet is not None:
                  # Remove the job from the running jobs.
                  job = self._m_dictRunningJobs.pop(rj)
                  cCompletedJobs += 1
                  if iRet == 0 or mk.ignore_errors:
                     # The job completed successfully or we’re ignoring its failure: any dependent
                     # jobs can now be released.
                     job.release_blocked()
                     # If the job was successfully executed, update any files’ metadata.
                     if iRet == 0 and not mk.dry_run and job._m_iterMetadataToUpdate:
                        mk.update_file_metadata(job._m_iterMetadataToUpdate)
                  else:
                     if mk.keep_going:
                        # Unschedule any dependent jobs, so we can continue ignoring this failure as
                        # long as we have scheduled jobs that don’t depend on it.
                        if job._m_setBlockedJobs:
                           self._unschedule_jobs_blocked_by(job)
                     cFailedJobs += 1
                  # Since we modified self._m_setScheduledJobs, we have to stop iterating over it.
                  # Iteration will be restarted by the inner while loop.
                  break
            else:
               # The for loop completed without interruptions, which means that no job slots were
               # freed, so break out of the inner while loop into the outer one to wait.
               break
         # If we freed up the requested count of slots, there’s nothing left to do.
         if cCompletedJobs >= cJobsToComplete:
            return cFailedJobs
         if not mk.dry_run:
            # Wait a small amount of time.
            # TODO: proper event-based waiting.
            time.sleep(0.1)


   def get_target_jobs(self, tgt):
      """Retrieves the job (chain) associated to a target.

      Target tgt
         Target for which to retrieve jobs.
      Job return
         Last job scheduled by tgt.build(), or None if tgt.build() has not been called yet.
      """

      return self._m_dictTargetLastScheduledJobs.get(tgt)


   def run_scheduled_jobs(self, mk):
      """Executes any scheduled jobs.

      Make mk
         Make instance.
      int return
         Count of jobs that completed in failure.
      """

      # This is the earliest point we know we can reset this.
      self._m_dictTargetLastScheduledJobs.clear()

      cFailedJobsTotal = 0
      while self._m_setScheduledJobs:
         # Make sure any completed jobs are collected.
         cFailedJobs = self._collect_completed_jobs(mk, 0)
         # Make sure we have at least one free job slot.
         while len(self._m_dictRunningJobs) == self.running_jobs_max:
            # Wait for one or more jobs slots to free up.
            cFailedJobs += self._collect_completed_jobs(mk, 1)

         cFailedJobsTotal += cFailedJobs
         # Stop starting jobs in case of failed errors – unless overridden by the user.
         if cFailedJobs > 0 and not mk.keep_going:
            break

         # Find a job that is ready to be executed.
         for job in self._m_setScheduledJobs:
            if not job.blocked:
               if mk.verbosity >= mk.VERBOSITY_LOW:
                  sys.stdout.write(job.get_verbose_command() + '\n')
               else:
                  iterQuietCmd = job.get_quiet_command()
                  sys.stdout.write('{:^8} {}\n'.format(iterQuietCmd[0], ' '.join(iterQuietCmd[1:])))
               if mk.dry_run:
                  # Create an always-successful job instead of starting the real job.
                  rj = RunningNoopJob(0)
               else:
                  rj = job.start()
               # Move the job from scheduled to running jobs.
               self._m_dictRunningJobs[rj] = job
               self._m_setScheduledJobs.remove(job)
               # Since we modified self._m_setScheduledJobs, we have to stop iterating over it; the
               # outer while loop will get back here, eventually.
               break
      # There are no more scheduled jobs, just wait for the running ones to complete.
      cFailedJobsTotal += self._collect_completed_jobs(mk, len(self._m_dictRunningJobs))

      return cFailedJobsTotal


   # Maximum count of running jobs, i.e. degree of parallelism. Defaults to the number of processors
   # in the system.
   running_jobs_max = None


   def schedule_job(self, job):
      """Used by Job.__init__() to add itself to the set of scheduled jobs.

      Job job
         Job to schedule.
      """

      self._m_setScheduledJobs.add(job)


   def set_target_jobs(self, tgt, job):
      """Associates a job (chain) with a target.

      Target tgt
         Target to with job should be associated.
      Job job
         Last job scheduled by tgt.build(). None is an allowed value.
      """

      self._m_dictTargetLastScheduledJobs[tgt] = job


   def _unschedule_jobs_blocked_by(self, job):
      """Recursively removes the jobs blocked by the specified job from the set of scheduled
      jobs.

      Job job
         Job to be unscheduled.
      """

      for jobBlocked in job._m_setBlockedJobs:
         # Use set.discard() instead of set.remove() since it may have already been removed due to a
         # previous unrelated call to this method, e.g. another job failed before the one that
         # caused this call.
         self._m_setScheduledJobs.discard(jobBlocked)
         if jobBlocked._m_setBlockedJobs:
            self._unschedule_jobs_blocked_by(jobBlocked)

