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

"""Job scheduling and execution classes."""

"""DOC:6821 Abamake ‒ Execution of external commands

External commands run by Abamake are managed by specializations of abamake.Job. The default
subclass, abamake.ExternalCmdJob, executes the job capturing its stderr and stdout and publishing
them to any subclasses; stderr is always logged to a file, with a name (chosen by the code that
instantiates the job) that’s typically output_dir/log/<path-to-the-target-built-by-the-job>.

A subclass of abamake.ExternalCmdJob, abamake.ExternalCmdCapturingJob, also captures to file the
standard output of the program; this is typically used to execute unit tests, since stdout is
considered the non-log output of the test; for example, a unit test for an image manipulation
library could output a generated bitmap to stdout, to have Abamake compare it against a pre-rendered
bitmap and determine whether the test is passed or not, in addition to checking the unit test
executable’s return code.

Special support is provided for unit tests using the abc::testing framework. Such tests are executed
using abamake.AbacladeUnitTestJob, a subclass of abamake.ExternalCmdCapturingJob; the stderr and
stdout are still captured and stored in files, but additionally stderr is parsed to capture progress
of the assertions and test cases executed, and the resulting counts are used to display a test
summary at the end of Abamake’s execution.

TODO: link to documentation for abc::testing support in Abamake.
"""

import io
import multiprocessing
import os
import subprocess
import sys
import threading
import time
import weakref

import abamake
import abamake.target



####################################################################################################
# Job

class Job(object):
   """Job to be executed by a JobController instance. See [DOC:6821 Abamake ‒ Execution of external
   commands] for an overview on external command execution in Abamake.
   """

   __slots__ = ()


   def get_quiet_command(self):
      """Returns a command summary for Make to print out in quiet mode.

      iterable(str, str*) return
         Job command summary: an iterable containing the short name and relevant (input or output)
         files for the tool.
      """

      raise NotImplementedError(
         'Job.get_quiet_command() must be overridden in ' + type(self).__name__
      )


   def get_verbose_command(self):
      """Returns a command-line for Make to print out in verbose mode.

      str return
         Job command line.
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

      pass



####################################################################################################
# NoopJob

class NoopJob(Job):
   """No-op job. Used to avoid special-case logic to handle targets that don’t need to be (re)built.
   """

   __slots__ = (
      # Command summary to print out in quiet mode.
      '_m_iterQuietCmd',
      # Value that poll() will return.
      '_m_iRet',
      # Command to print out in verbose mode.
      '_m_sVerboseCmd',
   )


   def __init__(self, iRet, iterQuietCmd = ('NOOP',), sVerboseCmd = '[internal:noop]'):
      """Constructor.

      int iRet
         Value that poll() will return.
      iterable(str, str*) iterQuietCmd
         “Quiet mode” command; see return value of Job.get_quiet_command().
      str sVerboseCmd
         “Verbose mode” command; see return value of Job.get_verbose_command().
      """

      Job.__init__(self)

      self._m_iterQuietCmd = iterQuietCmd
      self._m_iRet = iRet
      self._m_sVerboseCmd = sVerboseCmd


   def get_quiet_command(self):
      """See Job.get_quiet_command()."""

      return self._m_iterQuietCmd


   def get_verbose_command(self):
      """See Job.get_verbose_command()."""

      return self._m_sVerboseCmd


   def poll(self):
      """See Job.poll()."""

      return self._m_iRet



####################################################################################################
# SkippedBuildJob

class SkippedBuildJob(NoopJob):

   def __init__(self):
      """See NoopJob.__init__()."""

      NoopJob.__init__(self, 0, ('SKIP',), sVerboseCmd = '[internal:skipped-build]')



####################################################################################################
# ExternalCmdJob

class ExternalCmdJob(Job):
   """Invokes an external program, capturing stdout and stderr.

   The standard output is made available to subclasses via the overridable _stdout_chunk_read(). The
   default implementation of _stdout_chunk_read() doesn’t do anything.
   
   The error output is published via the overridable _stderr_line_read() and saved to the file path
   passed to the constructor. The default implementation of _stderr_line_read() logs everything, but
   this can be overridden in a subclass.
   """

   __slots__ = (
      # Logger instance.
      '_m_log',
      # Controlled Popen instance.
      '_m_popen',
      # Arguments to be passed to Popen’s constructor.
      '_m_dictPopenArgs',
      # Command summary to print out in quiet mode.
      '_m_iterQuietCmd',
      # See ExternalCmdJob.stderr_file_path.
      '_m_sStdErrFilePath',
      # Thread that reads from the job process’ stderr.
      '_m_thrStdErrReader',
      # Thread that reads from the job process’ stdout.
      '_m_thrStdOutReader',
   )


   def __init__(self, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath):
      """See Job.__init__().

      iterable(str, str*) iterQuietCmd
         “Quiet mode” command; see return value of tool.Tool._get_quiet_cmd().
      dict(str: object) dictPopenArgs
         Arguments to be passed to Popen’s constructor to execute this job. Both 'stdout' and
         'stderr' default to subprocess.PIPE. If the program to run incorrectly uses stdout instead
         of stderr, specify 'stderr' = subprocess.STDOUT; this will cause no stdout to be read
         (ExternalCmdJob._stdout_chunk_read() will never be called), but logging will work as
         expected. 'universal_newlines' should always be omitted, since this class handles stderr as
         text and stdout as binary.
      abamake.logging.Logger log
         Object to which the stderr of the process will be logged.
      str sStdErrFilePath
         Path to the file where the stderr of the process will be saved.
      """

      Job.__init__(self)

      self._m_log = log
      self._m_popen = None
      self._m_iterQuietCmd = iterQuietCmd
      self._m_dictPopenArgs = dictPopenArgs
      self._m_sStdErrFilePath = sStdErrFilePath
      self._m_thrStdErrReader = None
      self._m_thrStdOutReader = None

      # Make sure the client’s not trying to access stdout/stderr as TextIOBase.
      assert 'universal_newlines' not in dictPopenArgs

      # Make sure that the process’ output is piped in a way supported by this class.
      stderr = dictPopenArgs.setdefault('stderr', subprocess.PIPE)
      stdout = dictPopenArgs.setdefault('stdout', subprocess.PIPE)
      if stderr not in (subprocess.PIPE, subprocess.STDOUT):
         raise ValueError('invalid value for dictPopenArgs[\'stderr\']')
      if stdout != subprocess.PIPE:
         raise ValueError('invalid value for dictPopenArgs[\'stdout\']')


   def get_quiet_command(self):
      """See Job.get_quiet_command()."""

      return self._m_iterQuietCmd


   def get_verbose_command(self):
      """See Job.get_verbose_command()."""

      return ' '.join(self._m_dictPopenArgs['args'])


   def poll(self):
      """See Job.poll()."""

      if self._m_popen:
         iRet = self._m_popen.poll()
         if iRet is not None:
            # The process terminated, so wait for the I/O threads to do the same.
            self._m_thrStdErrReader.join()
            if self._m_thrStdOutReader:
               self._m_thrStdOutReader.join()
      else:
         iRet = 0
      return iRet


   def start(self):
      """See Job.start()."""

      self._m_popen = subprocess.Popen(**self._m_dictPopenArgs)

      # Start the I/O threads.
      self._m_thrStdErrReader = threading.Thread(target = self._stderr_reader_thread)
      self._m_thrStdErrReader.start()
      if self._m_dictPopenArgs['stderr'] != subprocess.STDOUT:
         self._m_thrStdOutReader = threading.Thread(target = self._stdout_reader_thread)
         self._m_thrStdOutReader.start()


   def _get_stderr_file_path(self):
      return self._m_sStdErrFilePath

   stderr_file_path = property(_get_stderr_file_path, doc = """
      Path to the file to which the error output of the process is saved.
   """)


   def _stderr_line_read(self, sLine):
      """Internal method invoked for each stderr line read.

      The default implementation logs each line received.

      str sLine
         Line of text read from stderr, stripped of any trailing new-line characters.
      """

      log = self._m_log
      log(None, '{}', sLine)


   def _stderr_reader_thread(self):
      """Reads from the job process’ stderr."""

      # Pick stdout if stderr is merged with it.
      if self._m_dictPopenArgs['stderr'] == subprocess.STDOUT:
         fileErrOut = self._m_popen.stdout
      else:
         fileErrOut = self._m_popen.stderr
      # Always read the file as text.
      if sys.hexversion >= 0x03000000:
         fileStdErrTextPipe = io.TextIOWrapper(fileErrOut)
      else:
         # Create a 3.x text I/O object for the 2.x file opened by subprocess.Popen.
         fileStdErrTextPipe = io.open(fileErrOut.fileno(), 'r', closefd = False)
      del fileErrOut
      # Make sure that the directory in which we’ll write stdout exists.
      abamake.makedirs(os.path.dirname(self._m_sStdErrFilePath))
      # Use io.open() instead of just open() for Python 2.x.
      with io.open(self._m_sStdErrFilePath, 'w') as fileStdErr:
         for sLine in fileStdErrTextPipe:
            self._stderr_line_read(sLine.rstrip('\r\n'))
            fileStdErr.write(sLine)


   def _stdout_chunk_read(self, byChunk):
      """Internal method invoked for each stdout chunk read.

      The default implementation doesn’t do anything.

      bytes byChunk
         Raw bytes output by the external process to stdout.
      """

      pass


   def _stdout_reader_thread(self):
      """Reads from the job process’ stdout."""

      if sys.hexversion >= 0x03000000:
         # Use the underlying RawIOBase object to avoid redundant buffering and to make any output
         # immediately available (instead of waiting for multiple os.read() calls).
         fileStdOutRaw = self._m_popen.stdout.raw
      else:
         fileStdOutRaw = self._m_popen.stdout
      while True:
         by = fileStdOutRaw.read(io.DEFAULT_BUFFER_SIZE)
         if not by:
            # EOF.
            break
         self._stdout_chunk_read(by)



####################################################################################################
# ExternalCmdCapturingJob

class ExternalCmdCapturingJob(ExternalCmdJob):
   """Same as ExternalCmdJob, but captures stdout and stderr of the process to files and allows to
   analyze them when the job completes.

   Internally, separate threads communicate with the process through the pipes, joining the main
   thread when the process terminates.
   """

   __slots__ = (
      # See ExternalCmdCapturingJob.stdout.
      '_m_byStdOut',
      # Collects the job process’ output on disk.
      '_m_fileStdOut',
      # See ExternalCmdCapturingJob.stdout_file_path.
      '_m_sStdOutFilePath',
   )


   def __init__(self, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath, sStdOutFilePath):
      """See ExternalCmdJob.__init__().

      iterable(str, str*) iterQuietCmd
         “Quiet mode” command; see return value of tool.Tool._get_quiet_cmd().
      dict(str: object) dictPopenArgs
         Arguments to be passed to Popen’s constructor to execute this job.
      abamake.logging.Logger log
         Object to which the stderr of the process will be logged.
      str sStdErrFilePath
         Path to the file where the stderr of the process will be saved.
      str sStdOutFilePath
         Path to the file where the stdout of the process will be saved.
      """

      ExternalCmdJob.__init__(self, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath)

      self._m_byStdOut = None
      self._m_fileStdOut = None
      self._m_sStdOutFilePath = sStdOutFilePath


   def poll(self):
      """See Job.poll(). Overridden to make sure we close _m_fileStdOut as soon as the process
      terminates.
      """

      iRet = ExternalCmdJob.poll(self)

      if self._m_popen and iRet is not None:
         # Note that at this point, _stdout_chunk_read() won’t be called again.
         self._m_fileStdOut.close()
         self._m_fileStdOut = None
      return iRet


   def start(self):
      """See ExternalCmdCapturingJob.start()."""

      # Make sure that the directory in which we’ll write stdout exists.
      abamake.makedirs(os.path.dirname(self._m_sStdOutFilePath))
      # Initialize buffering stdout in memory and on disk.
      self._m_byStdOut = b''
      self._m_fileStdOut = open(self._m_sStdOutFilePath, 'wb')

      ExternalCmdJob.start(self)


   def _get_stdout(self):
      return self._m_byStdOut

   stdout = property(_get_stdout, doc = """Collected output of the process.""")


   def _get_stdout_file_path(self):
      return self._m_sStdOutFilePath

   stdout_file_path = property(_get_stdout_file_path, doc = """
      Path to the file to which the output of the process is saved.
   """)


   def _stdout_chunk_read(self, byChunk):
      """See ExternalCmdJob._stdout_chunk_read(). Overridden to accumulate stdout in a member
      variable, so that it can be accessed from memory instead of having to be re-read from the file
      ExternalCmdJob saves it to.
      """

      self._m_byStdOut += byChunk
      self._m_fileStdOut.write(byChunk)



####################################################################################################
# AbacladeUnitTestJob

class AbacladeUnitTestJob(ExternalCmdCapturingJob):
   """External program performing tests using the abc::testing framework. Such a program will
   communicate via stderr its test results (courtesy of abc::testing::runner), which this class will
   parse and log.
   """

   __slots__ = (
      # Title of the test case being currently executed.
      '_m_sCurrTestCase',
      # Count of failed assertions for the current test case.
      '_m_cFailedTestAssertions',
      # Collects the job process’ output on disk.
      '_m_fileStdOut',
      # See ExternalCmdCapturingJob.stdout_file_path.
      '_m_sStdOutFilePath',
      # Count of test assertions performed for the current test case.
      '_m_cTotalTestAssertions',
   )


   def _stderr_line_read(self, sLine):
      """See ExternalCmdCapturingJob._stderr_line_read(). Overridden to interpret information sent
      by the abc::testing framework and only show errors (the program’s stderr file log will still
      contain the entire stderr output anyway).
      """

      # TODO: document possible abc::testing output info and link to it from [DOC:6931 Abamake],
      # here, and in every involved abc::testing::runner method.

      if sLine.startswith('ABCMK-TEST-'):
         sInfo = sLine[len('ABCMK-TEST-'):]
         if sInfo.startswith('ASSERT-PASS'):
            self._m_cTotalTestAssertions += 1
            sLine = None
         elif sInfo.startswith('ASSERT-FAIL'):
            self._m_cTotalTestAssertions += 1
            self._m_cFailedTestAssertions += 1
            # Make the line more readable before logging it.
            sLine = sInfo[len('ASSERT-FAIL') + 1:]
         elif sInfo.startswith('CASE-START'):
            self._m_sCurrTestCase = sInfo[len('CASE-START') + 1:]
            self._m_cTotalTestAssertions = 0
            self._m_cFailedTestAssertions = 0
            sLine = None
         elif sInfo.startswith('CASE-END'):
            self._m_log.add_testcase_result(
               self._m_sCurrTestCase, self._m_cTotalTestAssertions, self._m_cFailedTestAssertions
            )
            if self._m_cFailedTestAssertions:
               # Show the title of the failed test case.
               sLine = 'test case failed: {}'.format(self._m_sCurrTestCase)
            else:
               sLine = None
         else:
            sLine = 'unknown info from abc::testing program: {}'.format(sLine)
      if sLine is not None:
         # self._m_iterQuietCmd[1] is the unit test name.
         self._m_log(None, '{}: {}', self._m_iterQuietCmd[1], sLine)



####################################################################################################
# JobController

class JobController(object):
   """Schedules any jobs necessary to build targets in an Abamakefile (.abamk), running them with
   the selected degree of parallelism.
   """

   # See JobController.dry_run.
   _m_bDryRun = False
   # See JobController.force_build.
   _m_bForceBuild = False
   # See JobController.keep_going.
   _m_bKeepGoing = False
   # Weak reference to the owning abamake.Make instance.
   _m_mk = None
   # Running jobs for each target build (Job -> Target).
   _m_dictRunningJobs = None
   # Scheduled target builds.
   _m_setScheduledBuilds = None


   def __init__(self, mk):
      """Constructor.

      abamake.Make mk
         Make instance.
      """

      self._m_mk = weakref.ref(mk)
      self._m_dictRunningJobs = {}
      self.running_jobs_max = multiprocessing.cpu_count()
      self._m_setScheduledBuilds = set()


   def build_scheduled_targets(self):
      """Builds any targets scheduled for build by JobController.schedule_build().

      It allows for incremental builds by invoking Target.is_build_needed() before proceeding to
      build a target; it also supports unconditional builds as determined by the
      JobController.force_build setting, as well as no-op builds depending on the setting of
      JobController.dry_run.

      It repeatedly scans the scheduled targets set for targets that are ready to be built, then
      goes ahead to start the jobs to build them. At the same time, it enforces the limit on the
      degree of parallelism (see JobControl.running_jobs_max), by waiting for a job slot to free up
      before attempting to start a new job.

      int return
         Count of builds that completed in failure.
      """

      log = self._m_mk().log
      cFailedBuildsTotal = 0
      try:
         while self._m_setScheduledBuilds:
            # Make sure any completed jobs are collected.
            cFailedBuilds = self._collect_completed_jobs(0)
            # Make sure we have at least one free job slot.
            while len(self._m_dictRunningJobs) == self.running_jobs_max:
               # Wait for one or more jobs slots to free up.
               cFailedBuilds += self._collect_completed_jobs(1)

            cFailedBuildsTotal += cFailedBuilds
            # Quit starting jobs in case of failed errors – unless overridden by the user.
            if cFailedBuilds > 0 and not self._m_bKeepGoing:
               break

            # Find a target that is ready to be built.
            for tgt in self._m_setScheduledBuilds:
               if not tgt.is_build_blocked():
                  # Check if this target needs to be built.
                  bBuild = tgt.is_build_needed()
                  if bBuild:
                     log(log.MEDIUM, 'controller: {}: rebuilding due to detected changes', tgt)
                  elif self._m_bForceBuild:
                     log(log.MEDIUM, 'controller: {}: up-to-date, but rebuild forced', tgt)
                     bBuild = True
                  else:
                     log(log.MEDIUM, 'controller: {}: up-to-date', tgt)

                  if bBuild:
                     # Obtain a job to build this target.
                     job = tgt.build()
                     if not job:
                        # tgt’s Target.build() didn’t create a job; probably it only performs post-
                        # build steps.
                        bBuild = False

                  if bBuild:
                     # We have a job, run it.
                     if log.verbosity >= log.LOW:
                        log(log.LOW, '{}', job.get_verbose_command())
                     else:
                        iterCmd = job.get_quiet_command()
                        log(log.QUIET, '{} {}', log.qm_tool_name(iterCmd[0]), ' '.join(iterCmd[1:]))
                     if not self._m_bDryRun:
                        # Execute the build job.
                        job.start()
                  else:
                     # Even if we’re not building anything, this class’ algorithm still requires a
                     # placeholder job: start a no-op job with an exit code of 0 (success).
                     job = SkippedBuildJob()

                  # Move the target from scheduled builds to running jobs.
                  self._m_dictRunningJobs[job] = tgt
                  self._m_setScheduledBuilds.remove(tgt)
                  # We used up the job slot freed above; get back to the outer while loop, where we
                  # will wait for another slot to free up.
                  break

         # There are no more scheduled builds, just wait for the running ones to complete.
         cFailedBuildsTotal += self._collect_completed_jobs(len(self._m_dictRunningJobs))
      finally:
         if not self._m_bDryRun:
            # Write any new metadata.
            mds = self._m_mk().metadata
            if mds:
               mds.write()

      return cFailedBuildsTotal


   def _collect_completed_jobs(self, cJobsToComplete):
      """Called by JobController.build_scheduled_targets(), returns when (at least) the requested
      number of jobs completes and the respective targets’ Target.build_complete() have been called.
      If cJobsToComplete == 0, it only invokes Target.build_complete() for targets whose jobs have
      completed, but it does not wait for any jobs to complete.

      The call to Target.build_complete(), among other things, releases any dependent targets; any
      dependencies with no other blocks will be built by JobController.build_scheduled_targets().

      When a build terminates in failure and JobController.keep_going is True, the corresponding
      target and all its dependencies are removed from the scheduled targets with a (recursive) call
      to JobController._unschedule_builds_blocked_by(), to prevent
      JobController.build_scheduled_targets() from getting stuck waiting for targets that will never
      be released.

      int cJobsToComplete
         Count of jobs to wait for.
      int return
         Count of builds that completed in failure.
      """

      log = self._m_mk().log
      mds = self._m_mk().metadata
      # This loop alternates poll loop and sleeping.
      cCompletedBuilds = 0
      cFailedBuilds = 0
      # The termination condition is in the middle.
      while True:
         # This loop restarts the for loop, since we modify self._m_dictRunningJobs. The termination
         # condition is a break statement.
         while True:
            # Give the running jobs some lovin’ by polling.
            # TODO: with event-based waiting we should know exactly which event was triggered (i.e.
            # what it is that needs attention), so we won’t need to iterate (_m_dictRunningJobs will
            # need a different key though).
            for job in self._m_dictRunningJobs.keys():
               iRet = job.poll()
               if iRet is not None:
                  # Remove the target build from the running jobs.
                  tgt = self._m_dictRunningJobs.pop(job)
                  # If we decided not to run the job requested by the target (due to e.g. “dry run”
                  # mode), pass None instead, so Target.build_complete() doesn’t need to know how to
                  # tell the difference.
                  if self._m_bDryRun or isinstance(job, SkippedBuildJob):
                     job = None
                  # Target.build_complete() can change a success into a failure.
                  iRet = tgt.build_complete(job, iRet)

                  # Keep track of completed/failed builds.
                  cCompletedBuilds += 1
                  if iRet != 0:
                     if self._m_bKeepGoing:
                        # Unschedule any dependent builds, so we can continue ignoring this failure
                        # as long as we have scheduled builds that don’t depend on it.
                        self._unschedule_builds_blocked_by(tgt)
                     cFailedBuilds += 1
                     if job:
                        log(
                           None, 'make: {}: build failed (code: {}), command was: {}',
                           tgt, iRet, job.get_verbose_command()
                        )
                     else:
                        log(None, 'make: {}: build failed (code: {})', tgt, iRet)

                  # Since we modified self._m_dictRunningJobs, we have to stop iterating over it.
                  # Iteration will be restarted by the inner while loop.
                  break
            else:
               # The for loop completed without interruptions, which means that no job slots were
               # freed, so break out of the inner while loop into the outer one to wait.
               break
         # If we freed up the requested count of slots, there’s nothing left to do.
         if cCompletedBuilds >= cJobsToComplete:
            return cFailedBuilds
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
      """Schedules the build of the specified target and all its dependencies. Any targets that have
      already been scheduled won’t be scheduled a second time.

      abamake.target.Target tgt
         Target the build of which should be scheduled.
      """

      # Check if we already scheduled this target.
      if tgt not in self._m_setScheduledBuilds:
         # Schedule the build of this target.
         self._m_setScheduledBuilds.add(tgt)
         # Recursively schedule the build of the dependencies of this target, if Target themselves.
         for dep in tgt.get_dependencies(bTargetsOnly = True):
            self.schedule_build(dep)


   def _unschedule_builds_blocked_by(self, tgt):
      """Recursively removes the target builds blocked by the specified target from the set of
      scheduled builds.

      abamake.target.Target tgt
         Target build to be unscheduled.
      """

      for tgtBlocked in tgt.get_dependents():
         # Use set.discard() instead of set.remove() since it may have already been removed due to a
         # previous unrelated call to this method, e.g. another job failed before the one that
         # caused this call.
         self._m_setScheduledBuilds.discard(tgtBlocked)
         self._unschedule_builds_blocked_by(tgtBlocked)

