#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013, 2014, 2015
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

"""This module contains the implementation of Abamake (short for “Abaclade Make”).

This file contains Abamake and other core classes.

See [DOC:6931 Abamake] for more information.
"""

"""DOC:6931 Abamake

Abamake (short for “Abaclade Make”) was created to satisfy these requirements:

•  Cross-platform enough to no longer need to separately maintain a GNU makefile and a Visual Studio
   solution and projects to build Abaclade; this is especially important when thinking of Abaclade
   as a framework that should simplify building projects with/on top of it;

•  Allow a single makefile per project (this was just impossible with MSBuild);

•  Simplified syntax for a very shallow learning curve, just like Abaclade itself aims to be easier
   to use than other C++ frameworks;

•  Minimal-to-no build instructions required in each makefile, and no toolchain-specific commands/
   flags (this was getting difficult with GNU make);

•  Implicit definition of intermediate targets, so that each makefile needs only mention sources and
   outputs (this had already been achieved via Makefile.inc for GNU make, and was not required for
   MSBuild);

•  Trivial unit test declaration and execution (this had been implemented in both GNU make and
   MSBuild, but at the cost of a lot of made-up conventions);

•  Integration with abc::testing unit testing framework (this had already been accomplished for GNU
   make, but was still only planned for MSBuild);

•  Default parallel building of independent targets;

•  Command-line options generally compatible with GNU make, to be immediately usable by GNU make
   users.


Abamake loads an Abamakefile (short for “Abamake makefile”, a fairly simple XML file; see [DOC:5581
Abamakefiles]), creating a list of named and unnamed (file path-only) targets; these are then
scheduled for build, and the resulting build is started, proceeding in the necessary order.

Most targets are built using external commands (e.g. a C++ compiler); see [DOC:6821 Abamake ‒
Execution of external commands] for more information. Multiple non-dependent external commands are
executed in parallel, depending on the multiprocessing capability of the host system and command-
line options used.

TODO: link to documentation for abc::testing support in Abamake.
"""

import os
import re
import xml.dom.minidom

import abamake.job as job
import abamake.logging as logging
import abamake.metadata as metadata
import abamake.platform as platform
import abamake.target as target

FileNotFoundErrorCompat = getattr(__builtins__, 'FileNotFoundError', IOError)


####################################################################################################
# Non-member functions

def derived_classes(clsBase):
   """Iterates over all the classes that derive directly or indirectly from the specified one.

   This is probably rather slow, so it should not be abused.

   type clsBase
      Base class.
   type yield
      Class derived from clsBase.
   """

   setYielded = set()
   listClassesToScan = [clsBase]
   while listClassesToScan:
      # Iterate over the direct subclasses of the first class to scan.
      for clsDeriv in listClassesToScan.pop().__subclasses__():
         if clsDeriv not in setYielded:
            # We haven’t met or yielded this class before.
            yield clsDeriv
            setYielded.add(clsDeriv)
            listClassesToScan.append(clsDeriv)

def is_node_whitespace(nd):
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

def makedirs(sPath):
   """Implementation of os.makedirs(exists_ok = True) for both Python 2.7 and 3.x.

   str sPath
      Full path to the directory that should exist.
   """

   try:
      os.makedirs(sPath)
   except OSError:
      if not os.path.isdir(sPath):
         raise

####################################################################################################
# MakefileError

class MakefileError(Exception):
   """Indicates a syntactical or semantical error in a makefile."""

   pass

####################################################################################################
# DependencyCycleError

class DependencyCycleError(MakefileError):
   """Raised when a makefile specifies dependencies among targets in a way that creates circular
   dependencies, an unsolvable situation.
   """

   _m_iterTargets = None

   def __init__(self, sMessage, iterTargets, *iterArgs):
      """See MakefileError.__init__().

      str sMessage
         Exception message.
      iter(abamake.target.Target) iterTargets
         Targets that create a cycle in the dependency graph.
      iterable(object*) iterArgs
         Other arguments.
      """

      # Don’t pass iterTargets to the superclass’ constructor, so its __str__() won’t display it.
      MakefileError.__init__(self, sMessage, *iterArgs)

      self._m_iterTargets = iterTargets

   def __str__(self):
      # Show the regular exception description line followed by the targets in the cycle, one per
      # line.
      s = MakefileError.__str__(self) + '\n' + \
          '\n'.join('  ' + str(tgt) for tgt in self._m_iterTargets)
      return s

####################################################################################################
# MakefileSyntaxError

class MakefileSyntaxError(MakefileError):
   """Indicates a syntactical error in a makefile."""

   pass

####################################################################################################
# TargetReferenceError

class TargetReferenceError(MakefileError):
   """Raised when a reference to a target can’t be resolved."""

   pass

####################################################################################################
# Make

class Make(object):
   """Parses an Abamakefile (.abamk) and exposes a abamake.job.Runner instance that can be used to
   schedule target builds and run them.

   Example usage:

      mk = abamake.Make()
      mk.parse('project.abamk')
      tgt = mk.get_named_target('projectbin')
      mk.build((tgt, ))
   """

   # See Make.cross_build.
   _m_bCrossBuild = None
   # See Make.dry_run.
   _m_bDryRun = None
   # Targets explicitly or implicitly defined (e.g. intermediate targets) in the makefile that have
   # a file path assigned (file path -> Target).
   _m_dictFileTargets = None
   # See Make.force_build.
   _m_bForceBuild = None
   # See Make.force_test.
   _m_bForceTest = None
   # Platform under which targets will be built.
   _m_platformHost = None
   # See Make.job_runner.
   _m_jr = None
   # See Make.keep_going.
   _m_bKeepGoing = None
   # See Make.log.
   _m_log = None
   # See Make.metadata.
   _m_mds = None
   # Targets defined in the makefile that have a name assigned (name -> Target).
   _m_dictNamedTargets = None
   # See Make.output_dir.
   _m_sOutputDir = None
   # Platform under which targets will be executed.
   _m_platformTarget = None
   # All targets explicitly or implicitly defined in the makefile.
   _m_setTargets = None

   # Special value used with get_target_by_*() to indicate that a target not found should result in
   # an exception.
   _RAISE_IF_NOT_FOUND = object()

   def __init__(self):
      """Constructor."""

      self._m_bCrossBuild = False
      self._m_bDryRun = False
      self._m_dictFileTargets = {}
      self._m_bForceBuild = False
      self._m_bForceTest = False
      self._m_platformHost = platform.Platform.detect_host()
      self._m_jr = job.Runner(self)
      self._m_bKeepGoing = False
      self._m_log = logging.Logger(logging.LogGenerator())
      self._m_mds = None
      self._m_dictNamedTargets = {}
      self._m_sOutputDir = ''
      self._m_platformTarget = None
      self._m_setTargets = set()

   def add_file_target(self, tgt, sFilePath):
      """Records a file target, making sure no duplicates are added.

      abamake.target.FileTarget tgt
         Target to add.
      str sFilePath
         Target file path.
      """

      if sFilePath in self._m_dictFileTargets:
         raise KeyError('duplicate target file path: {}'.format(sFilePath))
      self._m_dictFileTargets[sFilePath] = tgt

   def add_named_target(self, tgt, sName):
      """Records a named target, making sure no duplicates are added.

      abamake.target.NamedTargetMixIn tgt
         Target to add.
      str sName
         Target name.
      """

      if sName in self._m_dictNamedTargets:
         raise KeyError('duplicate target name: {}'.format(sName))
      self._m_dictNamedTargets[sName] = tgt

   def add_target(self, tgt):
      """Records a target.

      abamake.target.Target tgt
         Target to add.
      """

      self._m_setTargets.add(tgt)

   def _get_cross_build(self):
      return self._m_bCrossBuild

   cross_build = property(_get_cross_build, doc = """
      If True, the host platform is not the same as the target platform, and Abamake may be unable
      to execute the binaries it builds.
   """)

   def build_targets(self, iterTargets):
      """Builds the specified targets, as well as their dependencies, as needed.

      iterable(abamake.target.Target*) iterTargets
         Targets to be built.
      bool return
         True if all the targets were built successfuly, or False otherwise.
      """

      # Begin building the selected targets.
      for tgt in iterTargets:
         tgt.start_build()
      # Keep running until all queued jobs have completed.
      cFailedBuilds = self._m_jr.run()
      if not self._m_bDryRun:
         # Write any new metadata.
         self._m_mds.write()
      return self.job_runner.failed_jobs == 0

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

   def _get_force_test(self):
      return self._m_bForceTest

   def _set_force_test(self, bForceTest):
      self._m_bForceTest = bForceTest

   force_test = property(_get_force_test, _set_force_test, doc = """
      If True, all test targets are executed unconditionally; if False, test targets are only
      executed if triggered by their dependencies.
   """)

   def get_file_target(self, sFilePath, oFallback = _RAISE_IF_NOT_FOUND):
      """Returns a file target given its file path, raising an exception if no such target exists
      and no fallback value was provided.

      str sFilePath
         Path to the target’s file.
      object oFallback
         Object to return in case the specified target does not exist. If omitted, an exception will
         be raised if the target does not exist.
      abamake.target.Target return
         Target that builds sFilePath, or oFallback if no such target was defined in the makefile.
      """

      tgt = self._m_dictFileTargets.get(sFilePath, oFallback)
      if tgt is self._RAISE_IF_NOT_FOUND:
         raise TargetReferenceError('unknown target: {}'.format(sFilePath))
      return tgt

   def get_named_target(self, sName, oFallback = _RAISE_IF_NOT_FOUND):
      """Returns a target given its name as specified in the makefile, raising an exception if no
      such target exists and no fallback value was provided.

      str sName
         Name of the target to look for.
      object oFallback
         Object to return in case the specified target does not exist. If omitted, an exception will
         be raised if the target does not exist.
      abamake.target.Target return
         Target named sName, or oFallback if no such target was defined in the makefile.
      """

      tgt = self._m_dictNamedTargets.get(sName, oFallback)
      if tgt is self._RAISE_IF_NOT_FOUND:
         raise TargetReferenceError('undefined target: {}'.format(sName))
      return tgt

   def _get_job_runner(self):
      return self._m_jr

   job_runner = property(_get_job_runner, doc = """Job runner.""")

   def _get_keep_going(self):
      return self._m_bKeepGoing

   def _set_keep_going(self, bKeepGoing):
      self._m_bKeepGoing = bKeepGoing

   keep_going = property(_get_keep_going, _set_keep_going, doc = """
      If True, build jobs will continue to be run even after a failed job, as long as they don’t
      depend on a failed job. If False, a failed job causes execution to stop as soon as any other
      running jobs complete.
   """)

   def _get_log(self):
      return self._m_log

   log = property(_get_log, doc = """Output log.""")

   def _get_metadata(self):
      return self._m_mds

   metadata = property(_get_metadata, doc = """Metadata store.""")

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
      """Parses an Abamakefile.

      str sFilePath
         Path to the makefile to parse.
      """

      self._parse_doc(xml.dom.minidom.parse(sFilePath))

      # Make sure the makefile doesn’t define circular dependencies.
      self.validate_dependency_graph()
      # Validate each target.
      for tgt in self._m_setTargets:
         tgt.validate()

      sMetadataFilePath = os.path.join(os.path.dirname(sFilePath), '.abamk-metadata.xml')
      self._m_mds = metadata.MetadataStore(self, sMetadataFilePath)

   def _parse_collect_targets(self, eltParent, listTargetsAndNodes, bTopLevel = True):
      """Recursively parses and collects all the targets defined in the specified XML element.

      xml.dom.Element eltParent
         Parent XML element to parse.
      list(tuple(abamake.target.Target, xml.dom.Element)*) listTargetsAndNodes
         List of parsed targets and their associated XML nodes. This method will add to this list
         any additional targets parsed.
      bool bTopLevel
         If True, this method will raise exceptions in case of non-target XML nodes; otherwise it
         assumes that a later invocation of Target.parse_makefile_element_child() will validate the
         contents of eltParent.
      """

      for elt in eltParent.childNodes:
         # Skip whitespace/comment nodes (unimportant) and non-top-level-nodes without children
         # (they’re references, not definitions).
         if not is_node_whitespace(elt) and (bTopLevel or elt.hasChildNodes()):
            if elt.nodeType == elt.ELEMENT_NODE:
               # Pick an abamake.target.Target subclass for this target type.
               clsTarget = target.Target.select_subclass(elt)
               if clsTarget:
                  # Instantiate the Target-derived class, assigning it its name.
                  tgt = clsTarget.parse_makefile_element(self, elt)
                  self.add_target(tgt)
                  listTargetsAndNodes.append((tgt, elt))
                  # Scan for nested target definitions.
                  self._parse_collect_targets(elt, listTargetsAndNodes, False)
               elif bTopLevel:
                  raise MakefileSyntaxError(
                     '<{}>: not a target definition XML element'.format(elt.nodeName)
                  )
            elif bTopLevel:
               raise MakefileSyntaxError(
                  'expected target definition XML element, found: {}'.format(elt.nodeName)
               )

   def _parse_doc(self, doc):
      """Parses a DOM representation of an Abamakefile.

      xml.dom.Document doc
         XML document to parse.
      """

      doc.documentElement.normalize()

      # Do a first scan of the document to instantiate all the defined targets and associated with
      # their respective XML elements. By instantiating all targets upfront we allow for
      # Target.parse_makefile_element_child() to always find a referenced target even it it was
      # defined after the target on which parse_makefile_element_child() is called, and to determine
      # on-the-fly whether a referenced <dynlib> is a target we should build or if we should expect
      # to find it somewhere else.
      listTargetsAndNodes = []
      self._parse_collect_targets(doc.documentElement, listTargetsAndNodes)

      # Now that all the targets have been instantiated, we can have them parse their definitions.
      for tgt, eltTarget in listTargetsAndNodes:
         for nd in eltTarget.childNodes:
            # Skip whitespace/comment nodes.
            if not is_node_whitespace(nd):
               if nd.nodeType != nd.ELEMENT_NODE:
                  raise MakefileSyntaxError(
                     '{}: expected XML element, found: {}'.format(tgt, nd.nodeName)
                  )
               if not tgt.parse_makefile_element_child(nd):
                  # Target.parse_makefile_element_child() returns False when it doesn’t know how to
                  # handle the specified child element.
                  raise MakefileSyntaxError(
                     '{}: unexpected XML element: <{}>'.format(tgt, nd.nodeName)
                  )

   def _get_target_platform(self):
      if not self._m_platformTarget:
         self._m_platformTarget = platform.Platform.detect_host()
         self._m_bCrossBuild = False
      return self._m_platformTarget

   target_platform = property(_get_target_platform, doc = """
      Platform under which the generated outputs will execute.
   """)

   def print_target_graphs(self):
      """Prints to stdout a graph with all the targets’ dependencies and one with their reverse
      dependencies.
      """

      print('Dependencies')
      print('------------')
      for tgt in self._m_dictNamedTargets.values():
         print(str(tgt))
         tgt.dump_dependencies('  ')
      print('')

   def validate_dependency_graph(self):
      """Ensures that no cycles exist in the targets dependency graph.

      Implemented by performing a depth-first search for back edges in the graph; this is very
      speed-efficient because it only visits each subtree once.

      See also the recursion step Make._validate_dependency_subtree().
      """

      # No previous ancerstors considered for the targets enumerated by this function.
      listDependents = []
      # No subtrees validated yet.
      setValidatedSubtrees = set()
      for tgt in self._m_setTargets:
         if tgt not in setValidatedSubtrees:
            self._validate_dependency_subtree(tgt, listDependents, setValidatedSubtrees)

   def _validate_dependency_subtree(self, tgtSubRoot, listDependents, setValidatedSubtrees):
      """Recursion step for Make.validate_dependency_graph(). Validates a dependency graph subtree
      rooted in tgtSubRoot, adding tgtSubRoot to setValidatedSubtrees in case of success, or raising
      an exception in case of problems with the subtree.

      abamake.target.Target tgtSubRoot
         Target at the root of the subtree to validate.
      list listDependents
         Ancestors of tgtSubRoot. An ordered set with fast push/pop would be faster, since we
         performs a lot of lookups in it.
      set setValidatedSubtrees
         Subtrees already validated. Used to avoid visiting a subtree more than once.
      """

      # Add this target to the dependents. This allows to find back edges and will even reveal if a
      # target depends on itself.
      listDependents.append(tgtSubRoot)
      for tgtDependency in tgtSubRoot.get_dependencies(bTargetsOnly = True):
         for i, tgtDependent in enumerate(listDependents):
            if tgtDependent is tgtDependency:
               # Back edge found: this dependency creates a cycle. Since listDependents[i] is the
               # previous occurrence of tgtDependency as ancestor of tgtSubRoot, listDependents[i:]
               # will yield all the nodes (targets) in the cycle. Note that listDependents does
               # include tgtSubRoot.
               raise DependencyCycleError(
                  'dependency graph validation failed, cycle detected:', listDependents[i:]
               )
         if tgtDependency not in setValidatedSubtrees:
            # Recurse to verify that this dependency’s subtree doesn’t contain cycles.
            self._validate_dependency_subtree(tgtDependency, listDependents, setValidatedSubtrees)
      # Restore the dependents and mark this subtree as validated.
      del listDependents[len(listDependents) - 1]
      setValidatedSubtrees.add(tgtSubRoot)
