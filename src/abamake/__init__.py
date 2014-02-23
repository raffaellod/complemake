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

"""This module contains the Make class, which parses and executes ABC makefiles (.abcmk), as well as
Target and its derived classes (make.target.*) and Tool and its derived classes (make.tool.*).

This file contains Make and other core classes.
"""

import os
import re
import subprocess
import sys
import time
import xml.dom
import xml.dom.minidom

import make.target as target
import make.tool as tool



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
   # See Job.quiet_command.
   _m_iterQuietCmd = None
   # Paths to the input and output files for which we’ll need to update metadata after this job
   # completes.
   _m_iterMetadataToUpdate = None


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
      mk._schedule_job(self)


   def _get_blocked(self):
      return self._m_cBlocks > 0

   blocked = property(_get_blocked, doc = """
      True if the job is blocked (i.e. requires other jobs to be run first), or False otherwise.
   """)


   def get_verbose_command(self):
      """Returns a command-line for Make to print out in verbose mode.

      str return
         Job’s command line.
      """

      raise NotImplementedError('Job.get_verbose_command() must be overridden')


   def _get_quiet_command(self):
      return self._m_iterQuietCmd

   quiet_command = property(_get_quiet_command, doc = """
      Command summary for Make to print out in quiet mode.
   """)


   def release_blocked(self):
      """Release any jobs this one was blocking."""

      if self._m_setBlockedJobs:
         for job in self._m_setBlockedJobs:
            job._m_cBlocks -= 1


   def start(self):
      """Starts the job, returning TODO.

      TODO return
         Handle to check the job status and eventual exit code.
      """

      raise NotImplementedError('Job.start() must be overridden')



####################################################################################################
# ExternalCommandJob

class ExternalCommandJob(Job):
   """Models a job consisting in the invocation of an external program."""

   # Command to be invoked, as a list of arguments.
   _m_iterArgs = None


   def __init__(self, mk, iterBlockingJobs, iterQuietCmd, iterMetadataToUpdate, iterArgs):
      """Constructor. See Job.__init__().

      Make mk
         Make instance.
      iterable(Job*) iterBlockingJobs
         Jobs that block this one.
      iterable(str, str*) iterQuietCmd
         “Quiet mode” command; see return value of tool.Tool._get_quiet_cmd().
      iterable(str*) iterMetadataToUpdate
         Paths to the files for which metadata should be updated when this job completes.
      iterable(str+) iterArgs
         Command-line arguments to execute this job.
      """

      super().__init__(mk, iterBlockingJobs, iterQuietCmd, iterMetadataToUpdate)
      self._m_iterArgs = iterArgs


   def get_verbose_command(self):
      """See Job.get_verbose_command()."""

      return ' '.join(self._m_iterArgs)


   def start(self):
      """See Job.start()."""

      return subprocess.Popen(self._m_iterArgs)



####################################################################################################
# FileMetadata

class FileMetadata(object):
   """Metadata for a single file."""

   __slots__ = (
      # Time of the file’s last modification.
      '_m_iMTime',
   )


   def __init__(self, sFilePath):
      """Constructor.

      str sFilePath
         Path to the file of which to collect metadata.
      """

      self._m_iMTime = os.path.getmtime(sFilePath)


   def __getstate__(self):
      return {
         'mtime': self._m_iMTime,
      }


   def __setstate__(self, dictState):
      for sName, sValue in dictState:
         if sName == 'mtime':
            self._m_iMTime = float(sValue)


   def __eq__(self, other):
      return self._m_iMTime - other._m_iMTime < 0.5


   def __ne__(self, other):
      return not self.__eq__(other)



####################################################################################################
# FileMetadataPair

class FileMetadataPair(object):
   """Stores Handles storage and retrieval of file metadata."""

   __slots__ = (
      # Stored file metadata, or None if the file’s metadata was never collected.
      'stored',
      # Current file metadata, or None if the file’s metadata has not yet been refreshed.
      'current',
   )


   def __init__(self):
      self.stored = None
      self.current = None



####################################################################################################
# MetadataStore

class MetadataStore(object):
   """Handles storage and retrieval of file metadata."""

   # Metadata for each file (str -> FileMetadata).
   _m_bDirty = False
   # Persistent storage file path.
   _m_sFilePath = None
   # Metadata for each file (str -> FileMetadata).
   _m_dictMetadataPairs = None


   def __init__(self, sFilePath):
      """Constructor. Loads metadata from the specified file.

      str sFilePath
         Metadata storage file.
      """

      self._m_sFilePath = sFilePath
      self._m_dictMetadataPairs = {}
      try:
         with xml.dom.minidom.parse(sFilePath) as doc:
            doc.documentElement.normalize()
            for eltFile in doc.documentElement.childNodes:
               # Skip unimportant nodes.
               if eltFile.nodeType != xml.dom.Node.ELEMENT_NODE or eltFile.nodeName != 'file':
                  continue
               # Parse this <file> element into the “stored” FileMetadata member of a new
               # FileMetadataPair instance.
               fmdp = FileMetadataPair()
               fmdp.stored = FileMetadata.__new__(FileMetadata)
               fmdp.stored.__setstate__(eltFile.attributes.items())
               self._m_dictMetadataPairs[eltFile.getAttribute('path')] = fmdp
      except FileNotFoundError:
         # If we can’t load the persistent metadata store, start it over.
         pass


   def __bool__(self):
      return bool(self._m_dictMetadataPairs)


   def file_changed(self, sFilePath):
      """Compares the metadata stored for the specified file against the file’s current metadata.

      str sFilePath
         Path to the file of which to compare metadata.
      bool return
         True if the file is determined to have changed, or False otherwise.
      """

      fmdp = self._m_dictMetadataPairs.get(sFilePath)
      # If we have no metadata to compare, report the file as changed.
      if fmdp is None or fmdp.stored is None:
         return True
      # If we still haven’t read the file’s current metadata, retrieve it now.
      if fmdp.current is None:
         try:
            fmdp.current = FileMetadata(sFilePath)
         except FileNotFoundError:
            # If the file doesn’t exist (anymore), consider it changed.
            return True

      # Compare stored vs. current metadata.
      return fmdp.current != fmdp.stored


   def update(self, sFilePath):
      """Creates or updates metadata for the specified file.

      str sFilePath
         Path to the file of which to update metadata.
      """

      fmdp = self._m_dictMetadataPairs.get(sFilePath)
      # Make sure the metadata pair is in the dictionary.
      if fmdp is None:
         fmdp = FileMetadataPair()
         self._m_dictMetadataPairs[sFilePath] = fmdp
      # Always re-read the file metadata because if we obtained it during scheduling, the file might
      # have been regenerated now that jobs have been run.
      fmdp.current = FileMetadata(sFilePath)
      # Replace the stored metadata.
      fmdp.stored = fmdp.current
      self._m_bDirty = True


   def write(self):
      """Stores metadata to the file from which it was loaded."""

      if not self._m_bDirty:
         return

      # Create an empty XML document.
      doc = xml.dom.getDOMImplementation().createDocument(
         doctype       = None,
         namespaceURI  = None,
         qualifiedName = None,
      )
      eltRoot = doc.appendChild(doc.createElement('metadata'))
      # Add metadata for each file.
      for sFilePath, fmdp in self._m_dictMetadataPairs.items():
         eltFile = eltRoot.appendChild(doc.createElement('file'))
         eltFile.setAttribute('path', sFilePath)
         # Add the metadata as attributes for this <file> element.
         for sName, oValue in fmdp.stored.__getstate__().items():
            eltFile.setAttribute(sName, str(oValue))
      # Write the document to file.
      os.makedirs(os.path.dirname(self._m_sFilePath), 0o755, True)
      with open(self._m_sFilePath, 'w') as fileMetadata:
         doc.writexml(fileMetadata, addindent = '   ', newl = '\n')



####################################################################################################
# Make

class Make(object):
   """Processes an ABC makefile (.abcmk) by parsing it, scheduling the necessary jobs to build any
   targets to be built, and then running the jobs with the selected degree of parallelism.

   Example usage:

      make = Make()
      make.parse('project.abcmk')
      make.schedule_target_jobs(make.get_target_by_name('projectbin'))
      make.run_scheduled_jobs()
   """

   # No verbosity, i.e. quiet operation (default). Will display a short summary of each job being
   # executed, instead of its command-line.
   VERBOSITY_NONE = 1
   # Print each job’s command-line as-is instead of a short summary.
   VERBOSITY_LOW = 2
   # Like VERBOSITY_LOW, and also describe what triggers the (re)building of each target.
   VERBOSITY_MEDIUM = 3
   # Like VERBOSITY_MED, and also show all the files that are being checked for changes.
   VERBOSITY_HIGH = 4

   # See Make.cxxcompiler.
   _m_clsCxxCompiler = None
   # See Make.dry_run.
   _m_bDryRun = False
   # See Make.force_build.
   _m_bForceBuild = False
   # See Make.ignore_errors.
   _m_bIgnoreErrors = False
   # See Make.keep_going.
   _m_bKeepGoing = False
   # See Make.linker.
   _m_clsLinker = None
   # Metadata store.
   _m_mds = None
   # Targets explicitly declared in the parsed makefile (name -> Target).
   _m_dictNamedTargets = None
   # See Make.output_dir.
   _m_sOutputDir = ''
   # Running jobs (Popen -> Job).
   _m_dictRunningJobs = {}
   # Maximum count of running jobs, i.e. degree of parallelism.
   _m_cRunningJobsMax = 8
   # Scheduled jobs.
   _m_setScheduledJobs = None
   # “Last” scheduled jobs (Target -> Job that completes it), i.e. jobs that are the last in a chain
   # of jobs scheduled to build a single target. The values are a subset of, or the same as,
   # Make._m_setScheduledJobs.
   _m_dictTargetLastScheduledJobs = None
   # All targets specified by the parsed makefile (file path -> Target), including implicit and
   # intermediate targets not explicitly declared with a <target> element.
   _m_dictTargets = None

   # Special value used with get_target_by_*() to indicate that a target not found should result in
   # an exception.
   _RAISE_IF_NOT_FOUND = object()


   def __init__(self):
      """Constructor."""

      self._m_dictNamedTargets = {}
      self._m_setScheduledJobs = set()
      self._m_dictTargetLastScheduledJobs = {}
      self._m_dictTargets = {}
      self.verbosity = Make.VERBOSITY_NONE


   def _add_target(self, tgt):
      """Adds a target to the relevant dictionaries.

      Target tgt
         Target to add.
      """

      sFilePath = tgt.file_path
      if sFilePath:
         self._m_dictTargets[sFilePath] = tgt
      sName = tgt.name
      if sName:
         self._m_dictNamedTargets[sName] = tgt


   def _collect_completed_jobs(self, cJobsToComplete):
      """Returns only after the specified number of jobs completes and the respective cleanup
      operations (such as releasing blocked jobs) have been performed. If cJobsToComplete == 0, it
      only performs cleanup for jobs that have already completed, without waiting.

      Returns the count of failed jobs, unless Make.ignore_errors is True, in which case it will
      always return 0.

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
            for proc in self._m_dictRunningJobs.keys():
               if self.dry_run:
                  # A no-op is always successful.
                  iRet = 0
               else:
                  iRet = proc.poll()
               if iRet is not None:
                  # Remove the job from the running jobs.
                  job = self._m_dictRunningJobs.pop(proc)
                  cCompletedJobs += 1
                  if iRet == 0 or self.ignore_errors:
                     # The job completed successfully or we’re ignoring its failure: any dependent
                     # jobs can now be released.
                     job.release_blocked()
                     # If the job was successfully executed, update any files’ metadata.
                     if iRet == 0 and not self.dry_run and job._m_iterMetadataToUpdate:
                        self.update_file_metadata(job._m_iterMetadataToUpdate)
                  else:
                     if self.keep_going:
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
         if not self.dry_run:
            # Wait a small amount of time.
            # TODO: proper event-based waiting.
            time.sleep(0.1)


   def _get_cxxcompiler(self):
      if self._m_clsCxxCompiler is None:
         # TODO: what’s MSC’s output?
         self._m_clsCxxCompiler = tool.Tool.detect((
            (tool.GxxCompiler, ('g++', '--version'), r'^g\+\+ '),
            (object,           ('cl',  '/?'       ), r' CL '   ),
         ))
      return self._m_clsCxxCompiler

   cxxcompiler = property(_get_cxxcompiler, doc = """
      C++ compiler class to be used to build CxxObjectTarget instances.
   """)


   def _get_dry_run(self):
      return self._m_bDryRun

   def _set_dry_run(self, bDryRun):
      self._m_bDryRun = bDryRun

   dry_run = property(_get_dry_run, _set_dry_run, doc = """
      If True, commands will only be printed, not executed; if False, they will be printed and
      executed.
   """)


   def file_metadata_changed(self, iterFilePaths):
      """Checks the specified files for changes, returning a list containing any files that appear
      to have changed. After the target dependent on these files has been built, the metadata should
      be refreshed by passing the return value to Make.update_file_metadata().

      iterable(str*) iterFilePaths
         Paths to the files to check for changes.
      iterable(str*) return
         List of changed files, or None if no file changes are detected.
      """

      listChanged = []
      for sFilePath in iterFilePaths:
         if self._m_mds.file_changed(sFilePath):
            if self.verbosity >= Make.VERBOSITY_HIGH:
               sys.stdout.write('Metadata changed for {}\n'.format(sFilePath))
            listChanged.append(sFilePath)
         else:
            if self.verbosity >= Make.VERBOSITY_HIGH:
               sys.stdout.write('Metadata unchanged for {}\n'.format(sFilePath))
      return listChanged or None


   def _get_force_build(self):
      return self._m_bForceBuild

   def _set_force_build(self, bForceBuild):
      self._m_bForceBuild = bForceBuild

   force_build = property(_get_force_build, _set_force_build, doc = """
      If True, targets are rebuilt unconditionally; if False, targets are rebuilt as needed.
   """)


   def get_target_by_file_path(self, sFilePath, oFallback = _RAISE_IF_NOT_FOUND):
      """Returns a target given its path, raising an exception if no such target exists and no
      fallback value was provided.

      str sFilePath
         Path to the file to find a target for.
      object oFallback
         Object to return in case the specified target does not exist. If omitted, an exception will
         be raised if the target does not exist.
      Target return
         Target that builds sFilePath, or oFallback if no such target was defined in the makefile.
      """

      tgt = self._m_dictTargets.get(sFilePath, oFallback)
      if tgt is self._RAISE_IF_NOT_FOUND:
         raise FileNotFoundError('unknown target: {}'.format(sFilePath))
      return tgt


   def get_target_by_name(self, sName, oFallback = _RAISE_IF_NOT_FOUND):
      """Returns a named (in the makefile) target given its name, raising an exception if no such
      target exists and no fallback value was provided.

      str sName
         Name of the target to look for.
      object oFallback
         Object to return in case the specified target does not exist. If omitted, an exception will
         be raised if the target does not exist.
      Target return
         Target named sName, or oFallback if no such target was defined in the makefile.
      """

      tgt = self._m_dictNamedTargets.get(sName, oFallback)
      if tgt is self._RAISE_IF_NOT_FOUND:
         raise NameError('undefined target: {}'.format(sName))
      return tgt


   def _get_ignore_errors(self):
      return self._m_bIgnoreErrors

   def _set_ignore_errors(self, bIgnoreErrors):
      self._m_bIgnoreErrors = bIgnoreErrors

   ignore_errors = property(_get_ignore_errors, _set_ignore_errors, doc = """
      If True, scheduled jobs will continue to be run even after a job they depend on fails. If
      False, a failed job causes execution to stop according to the value of Make.keep_going.
   """)


   @staticmethod
   def _is_node_whitespace(nd):
      """Returns True if a node is whitespace or a comment.

      xml.dom.Node nd
         Node to check.
      bool return
         True if nd is a whitespace or comment node, or False otherwise.
      """

      if nd.nodeType == xml.dom.Node.COMMENT_NODE:
         return True
      if nd.nodeType == xml.dom.Node.TEXT_NODE and re.match(r'^\s*$', nd.nodeValue):
         return True
      return False


   def _get_keep_going(self):
      return self._m_bKeepGoing

   def _set_keep_going(self, bKeepGoing):
      self._m_bKeepGoing = bKeepGoing

   keep_going = property(_get_keep_going, _set_keep_going, doc = """
      If True, scheduled jobs will continue to be run even after a failed job, as long as they don’t
      depend on a failed job. If False, a failed job causes execution to stop as soon as any other
      running jobs complete.
   """)


   def _get_linker(self):
      if self._m_clsLinker is None:
         # TODO: what’s MS Link’s output?
         self._m_clsLinker = tool.Tool.detect((
            (tool.GnuLinker, ('g++',  '-Wl,--version'), r'^GNU ld '),
            (tool.GnuLinker, ('ld',   '--version'    ), r'^GNU ld '),
            (object,         ('link', '/?'           ), r' Link '  ),
         ))
      return self._m_clsLinker

   linker = property(_get_linker, doc = """
      Linker class to be used to build ExecutableTarget instances.
   """)


   def _get_named_targets(self):
      return self._m_dictNamedTargets.values()

   named_targets = property(_get_named_targets, doc = """
      Targets explicitly declared in the parsed makefile.
   """)


   def _get_output_dir(self):
      return self._m_sOutputDir

   def _set_output_dir(self, sOutputDir):
      self._m_sOutputDir = sOutputDir

   output_dir = property(_get_output_dir, _set_output_dir, doc = """
      Output base directory that will be used for both intermediate and final build results.
   """)


   def parse(self, sFilePath):
      """Parses an ABC makefile.

      str sFilePath
         Path to the makefile to parse.
      """

      with xml.dom.minidom.parse(sFilePath) as doc:
         self._parse_doc(doc)
      sMetadataFilePath = os.path.join(os.path.dirname(sFilePath), '.abcmk', 'metadata.xml')
      self._m_mds = MetadataStore(sMetadataFilePath)
      if self.verbosity >= Make.VERBOSITY_HIGH:
         if self._m_mds:
            sys.stdout.write('MetadataStore loaded from {}\n'.format(sMetadataFilePath))
         else:
            sys.stdout.write('MetadataStore empty or missing: {}\n'.format(sMetadataFilePath))


   def _parse_doc(self, doc):
      """Parses a DOM representation of an ABC makefile.

      xml.dom.Document doc
         XML document to parse.
      """

      doc.documentElement.normalize()

      # Do a first scan of the top level elements, to find invalid nodes and unrecognized target
      # types. In the process, we instantiate all the target elements, so
      # Target.parse_makefile_child() can assign the dependencies even if they don’t appear in the
      # correct order in the makefile. This also allows to determine on-the-fly whether a referenced
      # <dynlib> is a target we should build or if we should expect to find it somewhere else.
      listNodesAndTargets = []
      for eltTarget in doc.documentElement.childNodes:
         if self._is_node_whitespace(eltTarget):
            # Skip whitespace/comment nodes.
            continue
         if eltTarget.nodeType != xml.dom.Node.ELEMENT_NODE:
            raise SyntaxError('expected <target>, found: {}'.format(eltTarget.nodeName))

         if eltTarget.nodeName == 'target':
            sType = eltTarget.getAttribute('type')
            # Pick a Target-derived class for this target type.
            if sType == 'unittest':
               # In order to know which UnitTestTarget-derived class to instantiate, we have to
               # look-ahead into the <target> element.
               clsTarget = None
               for ndInTarget in eltTarget.childNodes:
                  if ndInTarget.nodeType != xml.dom.Node.ELEMENT_NODE:
                     continue
                  clsNewTarget = None
                  if ndInTarget.nodeName == 'source':
                     if ndInTarget.hasAttribute('tool'):
                        # A <target> with a <source> with tool="…" override is not going to generate
                        # an executable.
                        clsNewTarget = target.ComparisonUnitTestTarget
                     else:
                        # A <target> with <source> (default tool) will generate an executable.
                        clsNewTarget = target.ExecutableUnitTestTarget
                  elif ndInTarget.nodeName == 'dynlib' or ndInTarget.nodeName == 'script':
                     # Linking to dynamic libraries or using execution scripts is a prerogative of
                     # executable unit tests only.
                     clsNewTarget = target.ExecutableUnitTestTarget
                  if clsNewTarget:
                     # If we already picked clsTarget, make sure it was the same as clsNewTarget.
                     if clsTarget and clsTarget is not clsNewTarget:
                        raise SyntaxError(
                           'unit test target “{}” specifies conflicting execution modes'.format(
                              eltTarget.getAttribute('name')
                           )
                        )
                     clsTarget = clsNewTarget
               if clsTarget is None:
                  raise SyntaxError('invalid empty unit test target “{}” element'.format(
                     eltTarget.getAttribute('name')
                  ))
            elif sType == 'exe':
               clsTarget = target.ExecutableTarget
            elif sType == 'dynlib':
               clsTarget = target.DynLibTarget
            else:
               raise Exception('unsupported target type: {}'.format(sType))
            # Instantiate the Target-derived class, assigning it its name.
            tgt = clsTarget(self, eltTarget.getAttribute('name'))
            listNodesAndTargets.append((tgt, eltTarget))
         else:
            raise SyntaxError('expected <target>; found: <{}>'.format(eltTarget.nodeName))

      # Now that all the targets have been instantiated, we can have them parse their definitions.
      for tgt, eltTarget in listNodesAndTargets:
         for nd in eltTarget.childNodes:
            if self._is_node_whitespace(nd):
               # Skip whitespace/comment nodes.
               continue
            if nd.nodeType != xml.dom.Node.ELEMENT_NODE:
               raise SyntaxError('expected element node, found: '.format(nd.nodeName))
            if not tgt.parse_makefile_child(self, nd):
               # Target.parse_makefile_child() returns False when it doesn’t know how to handle the
               # specified element.
               raise SyntaxError('unexpected element: <{}>'.format(nd.nodeName))


   def print_targets_graph(self):
      """Prints to stdout a graph of target dependencies."""

      # Targets explicitly declared in the parsed makefile (name -> target).
      for sName, tgt in self._m_dictNamedTargets.items():
         print('Target “{}” {}'.format(sName, tgt.file_path))
      # All targets specified by the parsed makefile (file path -> Target), including implicit and
      # intermediate targets not explicitly declared with a <target> element.
      for sFilePath, tgt in self._m_dictTargets.items():
         print('Target {}'.format(tgt.file_path))


   def run_scheduled_jobs(self):
      """Executes any scheduled jobs."""

      # This is the earliest point we know we can reset this.
      self._m_dictTargetLastScheduledJobs.clear()

      cFailedJobsTotal = 0
      while self._m_setScheduledJobs:
         # Make sure any completed jobs are collected.
         cFailedJobs = self._collect_completed_jobs(0)
         # Make sure we have at least one free job slot.
         while len(self._m_dictRunningJobs) == self._m_cRunningJobsMax:
            # Wait for one or more jobs slots to free up.
            cFailedJobs += self._collect_completed_jobs(1)

         cFailedJobsTotal += cFailedJobs
         # Stop starting jobs in case of failed errors – unless overridden by the user.
         if cFailedJobs > 0 and not self.keep_going:
            break

         # Find a job that is ready to be executed.
         for job in self._m_setScheduledJobs:
            if not job.blocked:
               if self.verbosity >= Make.VERBOSITY_LOW:
                  sys.stdout.write(job.get_verbose_command() + '\n')
               else:
                  iterQuietCmd = job.quiet_command
                  sys.stdout.write('{:^8} {}\n'.format(iterQuietCmd[0], ' '.join(iterQuietCmd[1:])))
               if self.dry_run:
                  # Create a placeholder instead of a real Popen instance.
                  proc = object()
               else:
                  proc = job.start()
               # Move the job from scheduled to running jobs.
               self._m_dictRunningJobs[proc] = job
               self._m_setScheduledJobs.remove(job)
               # Since we modified self._m_setScheduledJobs, we have to stop iterating over it; the
               # outer while loop will get back here, eventually.
               break
      # There are no more scheduled jobs, just wait for the running ones to complete.
      cFailedJobsTotal += self._collect_completed_jobs(len(self._m_dictRunningJobs))

      # Write any new metadata.
      if self._m_mds and not self.dry_run:
         if self.verbosity >= Make.VERBOSITY_HIGH:
            sys.stdout.write('Writing MetadataStore\n')
         self._m_mds.write()
      self._m_mds = None

      return cFailedJobsTotal


   def _schedule_job(self, job):
      """Used by Job.__init__() to add itself to the set of scheduled jobs.

      Job job
         Job to schedule.
      """

      self._m_setScheduledJobs.add(job)


   def schedule_target_jobs(self, tgt):
      """Schedules jobs for the specified target and all its dependencies, avoiding duplicate jobs.

      Recursively visits the dependency tree for the target in a leaves-first order, collecting
      (possibly chains of) Job instances returned by Target.build() for all the dependencies, and
      making these block the Job instance(s) for the specified target.

      Target tgt
         Target instance for which jobs should be scheduled by calling its build() method.
      Job return
         Last job scheduled by tgt.build().
      """

      # Check if we already have a (last) Job for this target.
      job = self._m_dictTargetLastScheduledJobs.get(tgt)
      if job is None:
         # Visit leaves.
         listBlockingJobs = None
         for tgtDep in tgt.dependencies or []:
            # Recursively schedule jobs for this dependency, returning and storing the last one.
            jobDep = self.schedule_target_jobs(tgtDep)
            if jobDep is not None:
               # Keep track of the dependencies’ jobs.
               if listBlockingJobs is None:
                  listBlockingJobs = []
               listBlockingJobs.append(jobDep)

         # Visit the node: give the target a chance to schedule jobs, letting it know which of its
         # dependencies scheduled jobs to be rebuilt, if any.
         job = tgt.build(self, listBlockingJobs)
         # Store the job even if None.
         self._m_dictTargetLastScheduledJobs[tgt] = job

      if job is None:
         # If Target.build() did not return a job, there’s nothing to do for this target. This must
         # also mean that no dependencies scheduled any jobs.
         # TODO: how about phonies or “virtual targets”?
         assert(not listBlockingJobs)
      return job


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


   def update_file_metadata(self, iterFilePaths):
      """Updates the metadata stored by ABC Make for the specified files.

      This should be called after each build job completes, to update the metadata for its input and
      output files.

      iterable(str*) iterFilePaths
         Paths to the files whose metadata needs to be updated.
      """

      for sFilePath in iterFilePaths:
         if self.verbosity >= Make.VERBOSITY_HIGH:
            sys.stdout.write('Updating metadata for {}\n'.format(sFilePath))
         self._m_mds.update(sFilePath)


   # True if the exact commands invoked should be printed to stdout, of False if only a short
   # description should.
   verbosity = None

