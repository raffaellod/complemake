#!/usr/bin/python
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

"""Job scheduling and execution classes."""

"""DOC:6821 Complemake ‒ Execution of external commands

External commands run by Complemake are managed by specializations of comk.Job. The default subclass,
comk.ExternalCmdJob, executes the job capturing its stderr and stdout and publishing them to any subclasses;
stderr is always logged to a file, with a name (chosen by the code that instantiates the job) that’s typically
output_dir/log/<path-to-the-target-built-by-the-job>.

A subclass of comk.ExternalCmdJob, comk.ExternalCmdCapturingJob, also captures to file the standard output of
the program; this is typically used to execute tests, since stdout is considered the non-log output of the
test; for example, a test for an image manipulation library could output a generated bitmap to stdout, to have
Complemake compare it against a pre-rendered bitmap and determine whether the test is passed or not, in
addition to checking the test executable’s exit code.

Special support is provided for tests using the abc::testing framework. Such tests are executed using
comk.AbacladeTestJob, a subclass of comk.ExternalCmdCapturingJob; the stderr and stdout are still captured and
stored in files, but additionally stderr is parsed to capture progress of the assertions and test cases
executed, and the resulting counts are used to display a test summary at the end of Complemake’s execution.

TODO: link to documentation for abc::testing support in Complemake.
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

import comk


##############################################################################################################

class Job(object):
   """Job to be executed by a comk.job.Runner instance. See [DOC:6821 Complemake ‒ Execution of external
   commands] for an overview on external command execution in Complemake.
   """

   # Function to call when the job completes.
   _on_complete_fn = None

   def __init__(self, on_complete_fn):
      """Constructor.

      callable on_complete_fn
         Function to be called when the job completes.
      """

      self._on_complete_fn = on_complete_fn

   def get_quiet_command(self):
      """Returns a command summary for Core to print out in quiet mode.

      iterable(str, str*) return
         Job command summary: an iterable containing the short name and relevant (input or output) files for
         the tool.
      """

      raise NotImplementedError('Job.get_quiet_command() must be overridden in ' + type(self).__name__)

   def get_verbose_command(self):
      """Returns a command-line for Core to print out in verbose mode.

      str return
         Job command line.
      """

      raise NotImplementedError('Job.get_verbose_command() must be overridden in ' + type(self).__name__)

   def on_complete(self):
      """Invokes the on_complete handler."""

      self._on_complete_fn()

##############################################################################################################

class SynchronousJob(Job):
   """Job that is executed synchronously. Typically this is implemented directly in Python, which means it
   might be faster than spawning a child process/thread to execute the task asynchronously.
   """

   def run(self):
      """Executes the job, synchronously.

      int return
         Exit code of the job.
      """

      # The default implementation is a no-op and always returns success.
      return 0

##############################################################################################################

class AsynchronousJob(Job):
   """Job that is executed asynchronously, typically in a separate process."""

   # Weak reference to the comk.job.Runner that called start().
   _runner = None

   def __init__(self, on_complete_fn):
      """See Job.__init__()."""

      Job.__init__(self, on_complete_fn)

      self._runner = None

   def join(self):
      """Waits for any outstanding processes or threads related to the job, returning the job’s exit code.

      int return
         Exit code of the job.
      """

      # The default implementation has nothing to wait for and always returns success.
      return 0

   def start(self, runner):
      """Starts processes and threads required to run the job."""

      self._runner = weakref.ref(runner)
      # The default implementation doesn’t start anything.

##############################################################################################################

class ExternalCmdJob(AsynchronousJob):
   """Invokes an external program, capturing stdout and stderr.

   The standard output is made available to subclasses via the overridable _stdout_chunk_read(). The default
   implementation of _stdout_chunk_read() doesn’t do anything.

   The error output is published via the overridable _stderr_line_read() and saved to the file path passed to
   the constructor. The default implementation of _stderr_line_read() logs everything, but this can be
   overridden in a subclass.
   """

   # Logger instance.
   _log = None
   # Controlled Popen instance.
   _popen = None
   # Arguments to be passed to Popen’s constructor.
   _popen_args = None
   # Command summary to print out in quiet mode.
   _quiet_cmd = None
   # See ExternalCmdJob.stderr_file_path.
   _stderr_file_path = None
   # Thread that reads from the job process’ stderr.
   _stderr_reader_thread = None
   # Thread that reads from the job process’ stdout.
   _stdout_reader_thread = None

   def __init__(self, on_complete_fn, quiet_cmd, popen_args, log, stderr_file_path):
      """See AsynchronousJob.__init__().

      callable on_complete_fn
         Function to be called when the job completes.
      iterable(str, str*) quiet_cmd
         “Quiet mode” command; see return value of tool.Tool._get_quiet_cmd().
      dict(str: object) popen_args
         Arguments to be passed to Popen’s constructor to execute this job. Both 'stdout' and 'stderr' default
         to subprocess.PIPE. If the program to run incorrectly uses stdout instead of stderr, specify
         'stderr'=subprocess.STDOUT; this will cause no stdout to be read (ExternalCmdJob._stdout_chunk_read()
         will never be called), but logging will work as expected. 'universal_newlines' should always be
         omitted, since this class handles stderr as text and stdout as binary.
      comk.logging.Logger log
         Object to which the stderr of the process will be logged.
      str stderr_file_path
         Path to the file where the stderr of the process will be saved.
      """

      AsynchronousJob.__init__(self, on_complete_fn)

      self._log = log
      self._popen = None
      self._quiet_cmd = quiet_cmd
      self._popen_args = popen_args
      self._stderr_file_path = stderr_file_path
      self._stderr_reader_thread = None
      self._stdout_reader_thread = None

      # Make sure the client’s not trying to access stdout/stderr as TextIOBase.
      assert 'universal_newlines' not in popen_args

      # Make sure that the process’ output is piped in a way supported by this class.
      stderr = popen_args.setdefault('stderr', subprocess.PIPE)
      stdout = popen_args.setdefault('stdout', subprocess.PIPE)
      if stderr not in (subprocess.PIPE, subprocess.STDOUT):
         raise ValueError('invalid value for popen_args[\'stderr\']')
      if stdout is not subprocess.PIPE:
         raise ValueError('invalid value for popen_args[\'stdout\']')

   def get_quiet_command(self):
      """See AsynchronousJob.get_quiet_command()."""

      return self._quiet_cmd

   def get_verbose_command(self):
      """See AsynchronousJob.get_verbose_command()."""

      return ' '.join(self._popen_args['args'])

   def join(self):
      """See AsynchronousJob.join()."""

      if self._popen:
         ret = self._popen.wait()
         self._stderr_reader_thread.join()
         return ret
      else:
         return None

   def _read_stderr(self):
      """Reads from the job process’ stderr."""

      # Pick stdout if stderr is merged with it.
      if self._popen_args['stderr'] is subprocess.STDOUT:
         err_out = self._popen.stdout
      else:
         err_out = self._popen.stderr
      # Always read the file as text.
      if sys.hexversion >= 0x03000000:
         stderr_text_pipe = io.TextIOWrapper(err_out)
      else:
         # Create a 3.x text I/O object for the 2.x file opened by subprocess.Popen.
         stderr_text_pipe = io.open(err_out.fileno(), 'r', closefd=False)
      del err_out
      # Make sure that the directory in which we’ll write stdout exists.
      comk.makedirs(os.path.dirname(self._stderr_file_path))
      with io.open(self._stderr_file_path, 'w') as stderr:
         for line in stderr_text_pipe:
            self._stderr_line_read(line.rstrip('\r\n'))
            stderr.write(line)
      # If we started the stdout thread, join it before ending this thread or releasing the job.
      if self._stdout_reader_thread:
         self._stdout_reader_thread.join()
         self._stdout_reader_thread = None
      # EOF: tell the runner that this job is finished.
      self._runner().job_complete(self)

   def _read_stdout(self):
      """Reads from the job process’ stdout."""

      if sys.hexversion >= 0x03000000:
         # Use the underlying RawIOBase object to avoid redundant buffering and to make any output immediately
         # available (instead of waiting for multiple os.read() calls).
         stdout_raw = self._popen.stdout.raw
      else:
         stdout_raw = self._popen.stdout
      while True:
         by = stdout_raw.read(io.DEFAULT_BUFFER_SIZE)
         if not by:
            # EOF. Rely on _read_stderr() to call _runner.job_complete().
            break
         self._stdout_chunk_read(by)

   def start(self, runner):
      """See AsynchronousJob.start()."""

      AsynchronousJob.start(self, runner)

      self._popen = subprocess.Popen(**self._popen_args)
      # Start the I/O threads.
      self._stderr_reader_thread = threading.Thread(target=self._read_stderr)
      self._stderr_reader_thread.start()
      if self._popen_args['stderr'] is not subprocess.STDOUT:
         self._stdout_reader_thread = threading.Thread(target=self._read_stdout)
         self._stdout_reader_thread.start()

   def _get_stderr_file_path(self):
      return self._stderr_file_path

   stderr_file_path = property(_get_stderr_file_path, doc="""
      Path to the file to which the error output of the process is saved.
   """)

   def _stderr_line_read(self, line):
      """Internal method invoked for each stderr line read.

      The default implementation logs each line received.

      str line
         Line of text read from stderr, stripped of any trailing new-line characters.
      """

      log = self._log
      log(None, '{}', line)

   def _stdout_chunk_read(self, chunk_bytes):
      """Internal method invoked for each stdout chunk read.

      The default implementation doesn’t do anything.

      bytes chunk_bytes
         Raw bytes output by the external process to stdout.
      """

      pass

##############################################################################################################

class ExternalCmdCapturingJob(ExternalCmdJob):
   """Same as ExternalCmdJob, but captures stdout and stderr of the process to files and allows to analyze
   them when the job completes.

   Internally, separate threads communicate with the process through the pipes, joining the main thread when
   the process terminates.
   """

   # Collects the job process’ output on disk.
   _stdout = None
   # See ExternalCmdCapturingJob.stdout.
   _stdout_bytes = None
   # See ExternalCmdCapturingJob.stdout_file_path.
   _stdout_file_path = None

   def __init__(self, on_complete_fn, quiet_cmd, popen_args, log, stderr_file_path, stdout_file_path):
      """See ExternalCmdJob.__init__().

      callable on_complete_fn
         Function to be called when the job completes.
      iterable(str, str*) quiet_cmd
         “Quiet mode” command; see return value of tool.Tool._get_quiet_cmd().
      dict(str: object) popen_args
         Arguments to be passed to Popen’s constructor to execute this job.
      comk.logging.Logger log
         Object to which the stderr of the process will be logged.
      str stderr_file_path
         Path to the file where the stderr of the process will be saved.
      str stdout_file_path
         Path to the file where the stdout of the process will be saved.
      """

      ExternalCmdJob.__init__(self, on_complete_fn, quiet_cmd, popen_args, log, stderr_file_path)

      self._stdout_bytes = None
      self._stdout = None
      self._stdout_file_path = stdout_file_path

   def join(self):
      """See ExternalCmdJob.join(). Overridden to make sure we close _stdout."""

      ret = ExternalCmdJob.join(self)

      if self._popen:
         # Note that at this point, _stdout_chunk_read() won’t be called again.
         self._stdout.close()
         self._stdout = None
      return ret

   def start(self, runner):
      """See ExternalCmdCapturingJob.start()."""

      # Make sure that the directory in which we’ll write stdout exists.
      comk.makedirs(os.path.dirname(self._stdout_file_path))
      # Initialize buffering stdout in memory and on disk.
      self._stdout_bytes = b''
      self._stdout = io.open(self._stdout_file_path, 'wb')

      return ExternalCmdJob.start(self, runner)

   def _get_stdout(self):
      return self._stdout_bytes

   stdout = property(_get_stdout, doc="""Collected output of the process.""")

   def _stdout_chunk_read(self, chunk_bytes):
      """See ExternalCmdJob._stdout_chunk_read(). Overridden to accumulate stdout in a member variable, so
      that it can be accessed from memory instead of having to be re-read from the file ExternalCmdJob saves
      it to.
      """

      self._stdout_bytes += chunk_bytes
      self._stdout.write(chunk_bytes)

   def _get_stdout_file_path(self):
      return self._stdout_file_path

   stdout_file_path = property(_get_stdout_file_path, doc="""
      Path to the file to which the output of the process is saved.
   """)

##############################################################################################################

class AbacladeTestJob(ExternalCmdCapturingJob):
   """External program performing tests using the abc::testing framework. Such a program will communicate via
   stderr its test results (courtesy of abc::testing::runner), which this class will parse and log.
   """

   # Title of the test case being currently executed.
   _curr_test_case = None
   # Count of failed assertions for the current test case.
   _failed_test_assertions = None
   # Collects the job process’ output on disk.
   _stdout = None
   # See ExternalCmdCapturingJob.stdout_file_path.
   _stdout_file_path = None
   # Count of test assertions performed for the current test case.
   _total_test_assertions = None

   def _stderr_line_read(self, line):
      """See ExternalCmdCapturingJob._stderr_line_read(). Overridden to interpret information sent by the
      abc::testing framework and only show errors (the program’s stderr file log will still contain the entire
      stderr output anyway).
      """

      # TODO: document possible abc::testing output info and link to it from [DOC:6931 Complemake], here, and
      # in every involved abc::testing::runner method.

      if line.startswith('COMK-TEST-'):
         info = line[len('COMK-TEST-'):]
         if info.startswith('ASSERT-PASS'):
            self._total_test_assertions += 1
            line = None
         elif info.startswith('ASSERT-FAIL'):
            self._total_test_assertions += 1
            self._failed_test_assertions += 1
            # Make the line more readable before logging it.
            line = info[len('ASSERT-FAIL') + 1:]
         elif info.startswith('CASE-START'):
            self._curr_test_case = info[len('CASE-START') + 1:]
            self._total_test_assertions = 0
            self._failed_test_assertions = 0
            line = None
         elif info.startswith('CASE-END'):
            self._log.add_testcase_result(
               self._curr_test_case, self._total_test_assertions, self._failed_test_assertions
            )
            if self._failed_test_assertions:
               # Show the title of the failed test case.
               line = u'test case failed: {}'.format(self._curr_test_case)
            else:
               line = None
         else:
            line = u'unknown info from abc::testing program: {}'.format(line)
      if line is not None:
         # self._quiet_cmd[1] is the test name.
         self._log(None, u'{}: {}', self._quiet_cmd[1], line)

##############################################################################################################

class Runner(object):
   """Manages the execution of jobs for Complemake. It contains a queue to which jobs are pushed, and offers a
   method to process the queue, run().
   """

   # Count of failed jobs.
   _failed_jobs = None
   # Type of a message written to/read from the jobs status queue.
   _jobs_status_queue_message_struct = struct.Struct('P')
   # Pipe end used by the main thread to get status updates from process-controlling threads.
   _jobs_status_queue_read = None
   # Pipe end used by process-controlling threads to communicate with the main thread.
   _jobs_status_queue_write = None
   # Lock that must be acquired prior to writing to _jobs_status_queue_write.
   _jobs_status_queue_write_lock = None
   # Weak reference to the owning comk.Core instance.
   _core = None
   # Changed from True to False when a job fails and keep_going mode is not enabled.
   _process_queue = True
   # Jobs queued to be run.
   _queued_jobs = None
   # Maps the ID of running jobs with the corresponding Job instances.
   _running_jobs = None
   # See Runner.running_jobs_max
   _running_jobs_max = None

   def __init__(self, core):
      """Constructor.

      comk.Core core
         Core instance.
      """

      self._failed_jobs = 0
      self._jobs_status_queue_read, self._jobs_status_queue_write = os.pipe()
      self._jobs_status_queue_write_lock = threading.Lock()
      self._core = weakref.ref(core)
      self._process_queue = True
      self._queued_jobs = set()
      self._running_jobs = {}
      self._running_jobs_max = multiprocessing.cpu_count()

   def __del__(self):
      """Destructor."""

      os.close(self._jobs_status_queue_read)
      os.close(self._jobs_status_queue_write)

   def _after_job_end(self, job, ret):
      """Invoked after a job completes, it executes its on_complete handler or reports a build error,
      depending on the job’s exit code.

      comk.job.Job job
         Job that just completed.
      int ret
         Exit code of the job.
      """

      if ret == 0:
         job.on_complete()
      else:
         core = self._core()
         log = core.log
         log(log.QUIET, 'scheduler: job failed ({}); command was: {}', ret, job.get_verbose_command())
         # Track this failure.
         self._failed_jobs += 1
         # If not configured to keep going after a failure, stop processing the queue.
         if not core.keep_going:
            self._process_queue = False

   def _before_job_start(self, job):
      """Invoked before a job is started, it logs information about it.

      comk.job.Job job
         Job that’s about to start.
      """

      log = self._core().log
      if log.verbosity >= log.LOW:
         log(log.LOW, '{}', job.get_verbose_command())
      else:
         quiet_command = job.get_quiet_command()
         log(log.QUIET, '{} {}', log.qm_tool_name(quiet_command[0]), ' '.join(quiet_command[1:]))

   def enqueue(self, job):
      """Adds a job to the job execution queue, or executes it immediately if it’s a synchronous one.

      comk.job.Job
         Job to execute.
      """

      log = self._core().log
      if self._core().dry_run:
         log(log.HIGH, 'scheduler: dry-running job synchronously')
         # Report running the job with an exit code of 0.
         self._before_job_start(job)
         self._after_job_end(job, 0)
      elif isinstance(job, SynchronousJob):
         log(log.HIGH, 'scheduler: running synchronous job')
         # Run the job immediately.
         self._before_job_start(job)
         ret = job.run()
         self._after_job_end(job, ret)
      else:
         # If there’s a free job slot, start the job now, otherwise queue it for later.
         if len(self._running_jobs) < self._running_jobs_max:
            log(log.HIGH, 'scheduler: starting asynchronous job id={}', id(job))
            self._start_asynchronous_job(job)
         else:
            log(log.HIGH, 'scheduler: enqueueing asynchronous job')
            self._queued_jobs.add(job)

   def _get_failed_jobs(self):
      return self._failed_jobs

   failed_jobs = property(_get_failed_jobs, doc="""
      Count of failed jobs. If 0, all jobs completed successfully.
   """)

   def job_complete(self, job):
      """Report that an asynchronous job has completed. This is typically called from a different thread owned
      by the job itself.

      comk.job.Job job
         Job that has completed.
      """

      log = self._core().log
      log(log.HIGH, 'scheduler: releasing main thread after completion of job id={}', id(job))
      bytes_to_write = self._jobs_status_queue_message_struct.pack(id(job))
      with self._jobs_status_queue_write_lock as lock:
         written_len = os.write(self._jobs_status_queue_write, bytes_to_write)
         assert written_len == len(bytes_to_write)

   def run(self):
      """Processes the job queue, starting jobs and waiting for them to complete. This method blocks until the
      job queue has been processed, which includes jobs added by on_complete handlers of other jobs.
      """

      log = self._core().log
      self._process_queue = True
      while self._running_jobs:
         log(log.MEDIUM, 'scheduler: waiting for a job to complete')
         # This is blocking.
         job = self._wait_for_job_complete()

         # job reported that it just terminated: wait on its threads/processes, and let it run its on_complete
         # handler.
         ret = job.join()
         self._after_job_end(job, ret)
         # Release the Job instance.
         del job

         # If there’s another job in the queue (which may have been just added by the on_complete handler),
         # start it now.
         if self._process_queue:
            if self._queued_jobs:
               log(log.MEDIUM, 'scheduler: starting queued job')
               self._start_asynchronous_job(self._queued_jobs.pop())
         else:
            # TODO: the build failed, stop all running jobs.
            pass

   def _get_running_jobs_max(self):
      return self._running_jobs_max

   def _set_running_jobs_max(self, max_running_jobs):
      self._running_jobs_max = max_running_jobs

   running_jobs_max = property(_get_running_jobs_max, _set_running_jobs_max, doc="""
      Maximum count of running jobs, i.e. degree of parallelism. Defaults to the number of processors in the
      system.
   """)

   def _start_asynchronous_job(self, job):
      """Starts an asynchrnous job, calling _before_job_start() and adding the job to _running_jobs.

      comk.job.AsynchronousJob job
         Job to start.
      """

      self._before_job_start(job)
      job.start(self)
      self._running_jobs[id(job)] = job

   def _wait_for_job_complete(self):
      """Blocks to read from the jobs status queue, returning the first job that reported having completed.

      comk.job.Job return
         Job instance that has completed.
      """

      # Wait for, read and unpack a message on the jobs status queue.
      len_to_read = self._jobs_status_queue_message_struct.size
      read_bytes = os.read(self._jobs_status_queue_read, len_to_read)
      assert len(read_bytes) == len_to_read
      job_id, = self._jobs_status_queue_message_struct.unpack(read_bytes)
      # job_id is the ID of the job that just reported to have terminated; remove it from _running_jobs and
      # return it.
      return self._running_jobs.pop(job_id)
