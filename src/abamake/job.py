#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013, 2014
# Raffaello D. Di Napoli
#
# This file is part of Abamake.
#
# Abamake is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Abamake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
# the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Abamake. If not, see
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
import struct
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
   """Job to be executed by a abamake.job.Runner instance. See [DOC:6821 Abamake ‒ Execution of
   external commands] for an overview on external command execution in Abamake.
   """

   # Function to call when the job completes.
   _m_fnOnComplete = None

   def __init__(self, fnOnComplete):
      """Constructor.

      callable fnOnComplete
         Function to be called when the job completes.
      """

      self._m_fnOnComplete = fnOnComplete

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

   def on_complete(self):
      """Invokes the on_complete handler."""

      self._m_fnOnComplete()

####################################################################################################
# SynchronousJob

class SynchronousJob(Job):
   """Job that is executed synchronously. Typically this is implemented directly in Python, which
   means it might be faster than spawning a child process/thread to execute the task asynchronously.
   """

   def run(self):
      """Executes the job, synchronously.

      int return
         Exit code of the job.
      """

      # The default implementation is a no-op and always returns success.
      return 0

####################################################################################################
# AsynchronousJob

class AsynchronousJob(Job):
   """Job that is executed asynchronously, typically in a separate process."""

   # Weak reference to the abamake.job.Runner that called start().
   _m_runner = None

   def __init__(self, fnOnComplete):
      """See Job.__init__()."""

      Job.__init__(self, fnOnComplete)

      self._m_runner = None

   def join(self):
      """Waits for any outstanding processes or threads related to the job, returning the job’s
      exit code.

      int return
         Exit code of the job.
      """

      # The default implementation has nothing to wait for and always returns success.
      return 0

   def start(self, runner):
      """Starts processes and threads required to run the job."""

      self._m_runner = weakref.ref(runner)
      # The default implementation doesn’t start anything.

####################################################################################################
# ExternalCmdJob

class ExternalCmdJob(AsynchronousJob):
   """Invokes an external program, capturing stdout and stderr.

   The standard output is made available to subclasses via the overridable _stdout_chunk_read(). The
   default implementation of _stdout_chunk_read() doesn’t do anything.
   
   The error output is published via the overridable _stderr_line_read() and saved to the file path
   passed to the constructor. The default implementation of _stderr_line_read() logs everything, but
   this can be overridden in a subclass.
   """

   # Logger instance.
   _m_log = None
   # Controlled Popen instance.
   _m_popen = None
   # Arguments to be passed to Popen’s constructor.
   _m_dictPopenArgs = None
   # Command summary to print out in quiet mode.
   _m_iterQuietCmd = None
   # See ExternalCmdJob.stderr_file_path.
   _m_sStdErrFilePath = None
   # Thread that reads from the job process’ stderr.
   _m_thrStdErrReader = None
   # Thread that reads from the job process’ stdout.
   _m_thrStdOutReader = None

   def __init__(self, fnOnComplete, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath):
      """See AsynchronousJob.__init__().

      callable fnOnComplete
         Function to be called when the job completes.
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

      AsynchronousJob.__init__(self, fnOnComplete)

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
      """See AsynchronousJob.get_quiet_command()."""

      return self._m_iterQuietCmd

   def get_verbose_command(self):
      """See AsynchronousJob.get_verbose_command()."""

      return ' '.join(self._m_dictPopenArgs['args'])

   def join(self):
      """See AsynchronousJob.join()."""

      if self._m_popen:
         iRet = self._m_popen.wait()
         self._m_thrStdErrReader.join()
         if self._m_thrStdOutReader:
            self._m_thrStdOutReader.join()
         return iRet
      else:
         return None

   def start(self, runner):
      """See AsynchronousJob.start()."""

      AsynchronousJob.start(self, runner)

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
         # EOF: tell the runner that this job is finished.
         self._m_runner().job_complete(self)

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
            # EOF. Rely on _stderr_reader_thread() to call _m_runner.job_complete().
            break
         self._stdout_chunk_read(by)

   def _stdout_chunk_read(self, byChunk):
      """Internal method invoked for each stdout chunk read.

      The default implementation doesn’t do anything.

      bytes byChunk
         Raw bytes output by the external process to stdout.
      """

      pass

####################################################################################################
# ExternalCmdCapturingJob

class ExternalCmdCapturingJob(ExternalCmdJob):
   """Same as ExternalCmdJob, but captures stdout and stderr of the process to files and allows to
   analyze them when the job completes.

   Internally, separate threads communicate with the process through the pipes, joining the main
   thread when the process terminates.
   """

   # See ExternalCmdCapturingJob.stdout.
   _m_byStdOut = None
   # Collects the job process’ output on disk.
   _m_fileStdOut = None
   # See ExternalCmdCapturingJob.stdout_file_path.
   _m_sStdOutFilePath = None

   def __init__(
      self, fnOnComplete, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath, sStdOutFilePath
   ):
      """See ExternalCmdJob.__init__().

      callable fnOnComplete
         Function to be called when the job completes.
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

      ExternalCmdJob.__init__(self, fnOnComplete, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath)

      self._m_byStdOut = None
      self._m_fileStdOut = None
      self._m_sStdOutFilePath = sStdOutFilePath

   def join(self):
      """See ExternalCmdJob.join(). Overridden to make sure we close _m_fileStdOut."""

      iRet = ExternalCmdJob.join(self)

      if self._m_popen:
         # Note that at this point, _stdout_chunk_read() won’t be called again.
         self._m_fileStdOut.close()
         self._m_fileStdOut = None
      return iRet

   def start(self, runner):
      """See ExternalCmdCapturingJob.start()."""

      # Make sure that the directory in which we’ll write stdout exists.
      abamake.makedirs(os.path.dirname(self._m_sStdOutFilePath))
      # Initialize buffering stdout in memory and on disk.
      self._m_byStdOut = b''
      self._m_fileStdOut = open(self._m_sStdOutFilePath, 'wb')

      return ExternalCmdJob.start(self, runner)

   def _get_stdout(self):
      return self._m_byStdOut

   stdout = property(_get_stdout, doc = """Collected output of the process.""")

   def _stdout_chunk_read(self, byChunk):
      """See ExternalCmdJob._stdout_chunk_read(). Overridden to accumulate stdout in a member
      variable, so that it can be accessed from memory instead of having to be re-read from the file
      ExternalCmdJob saves it to.
      """

      self._m_byStdOut += byChunk
      self._m_fileStdOut.write(byChunk)

   def _get_stdout_file_path(self):
      return self._m_sStdOutFilePath

   stdout_file_path = property(_get_stdout_file_path, doc = """
      Path to the file to which the output of the process is saved.
   """)

####################################################################################################
# AbacladeUnitTestJob

class AbacladeUnitTestJob(ExternalCmdCapturingJob):
   """External program performing tests using the abc::testing framework. Such a program will
   communicate via stderr its test results (courtesy of abc::testing::runner), which this class will
   parse and log.
   """

   # Title of the test case being currently executed.
   _m_sCurrTestCase = None
   # Count of failed assertions for the current test case.
   _m_cFailedTestAssertions = None
   # Collects the job process’ output on disk.
   _m_fileStdOut = None
   # See ExternalCmdCapturingJob.stdout_file_path.
   _m_sStdOutFilePath = None
   # Count of test assertions performed for the current test case.
   _m_cTotalTestAssertions = None

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
               sLine = u'test case failed: {}'.format(self._m_sCurrTestCase)
            else:
               sLine = None
         else:
            sLine = u'unknown info from abc::testing program: {}'.format(sLine)
      if sLine is not None:
         # self._m_iterQuietCmd[1] is the unit test name.
         self._m_log(None, u'{}: {}', self._m_iterQuietCmd[1], sLine)

####################################################################################################
# Runner

class Runner(object):
   """Manages the execution of jobs for Abamake. It contains a queue to which jobs are pushed, and
   offers a method to process the queue, run().
   """

   # Count of failed jobs.
   _m_cFailedJobs = None
   # Type of a message written to/read from the jobs status queue.
   _smc_structJobsStatusQueueMessage = struct.Struct('P')
   # Pipe end used by the main thread to get status updates from process-controlling threads.
   _m_fdJobsStatusQueueRead = None
   # Pipe end used by process-controlling threads to communicate with the main thread.
   _m_fdJobsStatusQueueWrite = None
   # Lock that must be acquired prior to writing to _m_fdJobsStatusQueueWrite.
   _m_lockJobsStatusQueueWrite = None
   # Weak reference to the owning abamake.Make instance.
   _m_mk = None
   # Changed from True to False when a job fails and keep_going mode is not enabled.
   _m_bProcessQueue = True
   # Jobs queued to be run.
   _m_setQueuedJobs = None
   # Maps the ID of running jobs with the corresponding Job instances.
   _m_dictRunningJobs = None
   # See Runner.running_jobs_max
   _m_cRunningJobsMax = None

   def __init__(self, mk):
      """Constructor.

      abamake.Make mk
         Make instance.
      """

      self._m_cFailedJobs = 0
      self._m_fdJobsStatusQueueRead = None
      self._m_fdJobsStatusQueueWrite = None
      self._m_lockJobsStatusQueueWrite = threading.Lock()
      self._m_mk = weakref.ref(mk)
      self._m_bProcessQueue = True
      self._m_setQueuedJobs = set()
      self._m_dictRunningJobs = {}
      self._m_cRunningJobsMax = multiprocessing.cpu_count()

   def _after_job_end(self, job, iRet):
      """Invoked after a job completes, it executes its on_complete handler or reports a build
      error, depending on the job’s exit code.

      abamake.job.Job job
         Job that just completed.
      int iRet
         Exit code of the job.
      """

      if iRet == 0:
         job.on_complete()
      else:
         mk = self._m_mk()
         log = mk.log
         log(
            log.QUIET, 'make: job failed ({}); command was: {}',
            iRet, job.get_verbose_command()
         )
         # Track this failure.
         self._m_cFailedJobs += 1
         # If not configured to keep going after a failure, stop processing the queue.
         if not mk.keep_going:
            self._m_bProcessQueue = False

   def _before_job_start(self, job):
      """Invoked before a job is started, it logs information about it.

      abamake.job.Job job
         Job that’s about to start.
      """

      log = self._m_mk().log
      if log.verbosity >= log.LOW:
         log(log.LOW, '{}', job.get_verbose_command())
      else:
         iterCmd = job.get_quiet_command()
         log(log.QUIET, '{} {}', log.qm_tool_name(iterCmd[0]), ' '.join(iterCmd[1:]))

   def enqueue(self, job):
      """Adds a job to the job execution queue, or executes it immediately if it’s a synchronous
      one.

      abamake.job.Job
         Job to execute.
      """

      if isinstance(job, SynchronousJob):
         # Run the job immediately.
         self._run_synchronous_job(job)
      else:
         # If there’s a free job slot, start the job now, otherwise queue it for later.
         if len(self._m_dictRunningJobs) < self._m_cRunningJobsMax:
            self._start_asynchronous_job(job)
         else:
            self._m_setQueuedJobs.add(job)

   def _get_failed_jobs(self):
      return self._m_cFailedJobs

   failed_jobs = property(_get_failed_jobs, doc = """
      Count of failed jobs. If 0, all jobs completed successfully.
   """)

   def job_complete(self, job):
      """Report that an asynchronous job has completed. This is typically called from a different
      thread owned by the job itself.

      abamake.job.Job job
         Job that has completed.
      """

      by = self._smc_structJobsStatusQueueMessage.pack(id(job))
      with self._m_lockJobsStatusQueueWrite as lock:
         # _m_fdJobsStatusQueueWrite may be None if the main thread has already left Runner.run().
         # In that case, there’s nothing left to do, so just skip what follows.
         if self._m_fdJobsStatusQueueWrite:
            cbWritten = os.write(self._m_fdJobsStatusQueueWrite, by)
            while cbWritten < len(by):
               by = by[cbWritten:]
               cbWritten = os.write(self._m_fdJobsStatusQueueRead, by)

   def run(self):
      """Processes the job queue, starting jobs and waiting for them to complete. This method blocks
      until the job queue has been processed, which includes jobs added by on_complete handlers of
      other jobs.
      """

      mk = self._m_mk()
      log = mk.log
      with self._m_lockJobsStatusQueueWrite as lock:
         self._m_fdJobsStatusQueueRead, self._m_fdJobsStatusQueueWrite = os.pipe()
      self._m_bProcessQueue = True
      try:
         while self._m_dictRunningJobs:
            log(log.MEDIUM, 'make: waiting for a job to complete')
            # This is blocking.
            job = self._wait_for_job_complete()

            # job reported that it just terminated: wait on its threads/processes, and let it run
            # its on_complete handler.
            iRet = job.join()
            self._after_job_end(job, iRet)
            # Release the Job instance.
            del job

            # If there’s another job in the queue (which may have been just added by the on_complete
            # handler), start it now.
            if self._m_bProcessQueue:
               if self._m_setQueuedJobs:
                  log(log.MEDIUM, 'make: starting queued job')
                  self._start_asynchronous_job(self._m_setQueuedJobs.pop())
            else:
               # TODO: the build failed, stop all running jobs.
               pass
      finally:
         with self._m_lockJobsStatusQueueWrite as lock:
            os.close(self._m_fdJobsStatusQueueRead)
            os.close(self._m_fdJobsStatusQueueWrite)
            self._m_fdJobsStatusQueueRead = None
            self._m_fdJobsStatusQueueWrite = None

   def _get_running_jobs_max(self):
      return self._m_cRunningJobsMax

   def _set_running_jobs_max(self, cRunningJobsMax):
      self._m_cRunningJobsMax = cRunningJobsMax

   running_jobs_max = property(_get_running_jobs_max, _set_running_jobs_max, doc = """
      Maximum count of running jobs, i.e. degree of parallelism. Defaults to the number of
      processors in the system.
   """)

   def _run_synchronous_job(self, job):
      """Runs a synchrnous job, calling _before_job_start() and _after_job_end().

      abamake.job.SynchronousJob job
         Job to run.
      """

      self._before_job_start(job)
      iRet = job.run()
      self._after_job_end(job, iRet)

   def _start_asynchronous_job(self, job):
      """Starts an asynchrnous job, calling _before_job_start() and adding the job to
      _m_dictRunningJobs.

      abamake.job.AsynchronousJob job
         Job to start.
      """

      self._before_job_start(job)
      job.start(self)
      self._m_dictRunningJobs[id(job)] = job

   def _wait_for_job_complete(self):
      """Blocks to read from the jobs status queue, returning the first job that reported having
      completed.

      abamake.job.Job return
         Job instance that has completed.
      """

      # Wait for, read and unpack a message on the jobs status queue.
      cbNeeded = self._smc_structJobsStatusQueueMessage.size
      by = os.read(self._m_fdJobsStatusQueueRead, cbNeeded)
      while len(by) < cbNeeded:
         by += os.read(self._m_fdJobsStatusQueueRead, cbNeeded - len(by))
      idJob, = self._smc_structJobsStatusQueueMessage.unpack(by)
      # idJob is the ID of the job that just reported to have terminated; remove it from the running
      # jobs and return it.
      return self._m_dictRunningJobs.pop(idJob)
