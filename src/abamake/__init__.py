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
import sys
import xml.dom.minidom

import make.job as job
import make.metadata as metadata
import make.target as target
import make.tool as tool



####################################################################################################
# Logger

class Logger(object):
   """Logger with multiple verbosity levels."""

   # Error-only verbosity, i.e. only errors will be output. When used with Logger.__call__(), this
   # specifies an error.
   ERROR = 0
   # No verbosity, i.e. quiet operation (default). Will display a short summary of each job being
   # executed, instead of its command-line.
   QUIET = 1
   # Print each job’s command-line as-is instead of a short summary.
   LOW = 2
   # Like LOW, and also describe what triggers the (re)building of each target.
   MEDIUM = 3
   # Like MED, and also show all the files that are being checked for changes.
   HIGH = 4


   def __init__(self):
      """Constructor."""

      self.verbosity = self.QUIET


   def __call__(self, iLevel, sFormat, *iterArgs, **dictKwArgs):
      """Writes a formatted string to the level matching iLevel.

      TODO: comment.
      """

      if self.verbosity >= iLevel:
         s = sFormat.format(*iterArgs, **dictKwArgs)
         if iLevel == self.ERROR:
            sys.stderr.write(s)
         else:
            sys.stdout.write(s)


   # Selects a verbosity level (make.Make.*), affecting what is displayed about the operations
   # executed.
   verbosity = None



####################################################################################################
# Make

class Make(object):
   """Processes an ABC makefile (.abcmk) by parsing it, scheduling the necessary jobs to build any
   targets to be built, and then running the jobs with the selected degree of parallelism.

   Example usage:

      mk = make.Make()
      mk.parse('project.abcmk')
      mk.schedule_target_jobs(mk.get_target_by_name('projectbin'))
      mk.run_scheduled_jobs()
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

   # See Make.dry_run.
   _m_bDryRun = False
   # See Make.force_build.
   _m_bForceBuild = False
   # See Make.ignore_errors.
   _m_bIgnoreErrors = False
   # See Make.job_controller.
   _m_jc = None
   # See Make.keep_going.
   _m_bKeepGoing = False
   # See Make.log.
   _m_log = None
   # Metadata store.
   _m_mds = None
   # Targets explicitly declared in the parsed makefile (name -> Target).
   _m_dictNamedTargets = None
   # See Make.output_dir.
   _m_sOutputDir = ''
   # All targets specified by the parsed makefile (file path -> Target), including implicit and
   # intermediate targets not explicitly declared with a named target element.
   _m_dictTargets = None

   # Special value used with get_target_by_*() to indicate that a target not found should result in
   # an exception.
   _RAISE_IF_NOT_FOUND = object()


   def __init__(self):
      """Constructor."""

      self._m_jc = job.Controller(self)
      self._m_log = Logger()
      self._m_dictNamedTargets = {}
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

      if nd.nodeType == nd.COMMENT_NODE:
         return True
      if nd.nodeType == nd.TEXT_NODE and re.match(r'^\s*$', nd.nodeValue):
         return True
      return False


   def _get_job_controller(self):
      return self._m_jc

   job_controller = property(_get_job_controller, doc = """Job scheduler/controller.""")


   def _get_keep_going(self):
      return self._m_bKeepGoing

   def _set_keep_going(self, bKeepGoing):
      self._m_bKeepGoing = bKeepGoing

   keep_going = property(_get_keep_going, _set_keep_going, doc = """
      If True, scheduled jobs will continue to be run even after a failed job, as long as they don’t
      depend on a failed job. If False, a failed job causes execution to stop as soon as any other
      running jobs complete.
   """)


   def _get_log(self):
      return self._m_log

   log = property(_get_log, doc = """Output log.""")


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
      sMetadataFilePath = os.path.join(os.path.dirname(sFilePath), '.abcmk-metadata.xml')
      self._m_mds = metadata.MetadataStore(self, sMetadataFilePath)


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
         if eltTarget.nodeType != eltTarget.ELEMENT_NODE:
            raise SyntaxError('expected target, found: {}'.format(eltTarget.nodeName))
         # Every target must have a name attribute.
         sName = eltTarget.getAttribute('name')
         if not sName:
            raise Exception('missing target name')
         # Pick a Target-derived class for this target type.
         clsTarget = target.Target.select_subclass(eltTarget)
         # Instantiate the Target-derived class, assigning it its name.
         tgt = clsTarget(self, sName)
         listNodesAndTargets.append((tgt, eltTarget))

      # Now that all the targets have been instantiated, we can have them parse their definitions.
      for tgt, eltTarget in listNodesAndTargets:
         for nd in eltTarget.childNodes:
            if self._is_node_whitespace(nd):
               # Skip whitespace/comment nodes.
               continue
            if nd.nodeType != nd.ELEMENT_NODE:
               raise SyntaxError('expected element node, found: '.format(nd.nodeName))
            if not tgt.parse_makefile_child(nd):
               # Target.parse_makefile_child() returns False when it doesn’t know how to handle the
               # specified element.
               raise SyntaxError('unexpected element: <{}>'.format(nd.nodeName))


   def print_targets_graph(self):
      """Prints to stdout a graph of target dependencies."""

      # Targets explicitly declared in the parsed makefile (name -> target).
      for sName, tgt in self._m_dictNamedTargets.items():
         print('Target “{}” {}'.format(sName, tgt.file_path))
      # All targets specified by the parsed makefile (file path -> Target), including implicit and
      # intermediate targets not explicitly declared with a named target element.
      for sFilePath, tgt in self._m_dictTargets.items():
         print('Target {}'.format(tgt.file_path))


   def run_scheduled_jobs(self):
      """Executes any scheduled jobs.

      int return
         Count of jobs that completed in failure.
      """

      try:
         cFailedJobsTotal = self._m_jc.run_scheduled_jobs()
      finally:
         # Write any new metadata.
         if self._m_mds and not self.dry_run:
            self._m_log(self._m_log.HIGH, 'metadata: updating\n')
            self._m_mds.write()
         self._m_mds = None

      return cFailedJobsTotal


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
      job = self._m_jc.get_target_jobs(tgt)
      if job is None:
         # Visit leaves.
         listBlockingJobs = None
         for tgtDep in filter(lambda oDep: isinstance(oDep, target.Target), tgt.dependencies or []):
            # Recursively schedule jobs for this dependency, returning and storing the last one.
            jobDep = self.schedule_target_jobs(tgtDep)
            if jobDep is not None:
               # Keep track of the dependencies’ jobs.
               if listBlockingJobs is None:
                  listBlockingJobs = []
               listBlockingJobs.append(jobDep)

         # Visit the node: give the target a chance to schedule jobs, letting it know which of its
         # dependencies scheduled jobs to be rebuilt, if any.
         job = tgt.build(listBlockingJobs)
         # Store the job even if None.
         self._m_jc.set_target_jobs(tgt, job)

      if job is None:
         # If Target.build() did not return a job, there’s nothing to do for this target. This must
         # also mean that no dependencies scheduled any jobs.
         # TODO: how about phonies or “virtual targets”?
         assert not listBlockingJobs, \
            'Target.build() returned no jobs, no dependencies should have scheduled jobs'
      return job


   # Selects a verbosity level (Make.VERBOSITY_*), affecting what is displayed about the operations
   # executed.
   verbosity = None

