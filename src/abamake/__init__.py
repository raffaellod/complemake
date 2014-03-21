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



####################################################################################################
# Logger

class Logger(object):
   """Logger with multiple verbosity levels."""

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
      """Logs a formatted string.

      int iLevel
         Minimum logging level. If the log verbosity setting is below this value, the log entry will
         not be printed. If this value is None, the message will be output unconditionally (useful
         to report errors, for example).
      str sFormat
         Format string.
      iter(object*) *iterArgs
         Forwarded to sFormat.format().
      dict(str: object) **dictKwArgs
         Forwarded to sFormat.format().
      """

      if iLevel is None or self.verbosity >= iLevel:
         s = sFormat.format(*iterArgs, **dictKwArgs)
         sys.stderr.write(s)


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
      mk.job_controller.schedule_build(mk.get_target_by_name('projectbin'))
      mk.job_controller.build_scheduled_targets()
   """

   # See Make.job_controller.
   _m_jc = None
   # See Make.log.
   _m_log = None
   # See Make.metadata.
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

      self._m_jc = job.JobController(self)
      self._m_log = Logger()
      self._m_dictNamedTargets = {}
      self._m_dictTargets = {}


   def add_target(self, tgt):
      """Adds a target to the applicable dictionaries, making sure no duplicates are added.

      make.target.Target tgt
         Target to add.
      """

      sName = tgt.name
      sFilePath = tgt.file_path
      if not sName and not sFilePath:
         raise Exception('a target must have either a name or a file path ({})'.format(tgt))
      if sName:
         if sName in self._m_dictNamedTargets:
            raise KeyError('duplicate target name: {}'.format(sName))
         self._m_dictNamedTargets[sName] = tgt
      if sFilePath:
         if sFilePath in self._m_dictTargets:
            raise KeyError('duplicate target file path: {}'.format(sFilePath))
         self._m_dictTargets[sFilePath] = tgt


   def get_target_by_file_path(self, sFilePath, oFallback = _RAISE_IF_NOT_FOUND):
      """Returns a target given its path, raising an exception if no such target exists and no
      fallback value was provided.

      str sFilePath
         Path to the file to find a target for.
      object oFallback
         Object to return in case the specified target does not exist. If omitted, an exception will
         be raised if the target does not exist.
      make.target.Target return
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
      make.target.Target return
         Target named sName, or oFallback if no such target was defined in the makefile.
      """

      tgt = self._m_dictNamedTargets.get(sName, oFallback)
      if tgt is self._RAISE_IF_NOT_FOUND:
         raise NameError('undefined target: {}'.format(sName))
      return tgt


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
      """Parses an ABC makefile.

      str sFilePath
         Path to the makefile to parse.
      """

      with xml.dom.minidom.parse(sFilePath) as doc:
         self._parse_doc(doc)
      sMetadataFilePath = os.path.join(os.path.dirname(sFilePath), '.abcmk-metadata.xml')
      self._m_mds = metadata.MetadataStore(self, sMetadataFilePath)


   def _parse_collect_targets(self, eltParent, listTargetsAndNodes, bTopLevel = True):
      """Recursively parses and collects all the targets defined in the specified XML element.

      xml.dom.Element eltParent
         Parent XML element to parse.
      list(tuple(make.target.Target, xml.dom.Element)*) listTargetsAndNodes
         List of parsed targets and their associated XML nodes. This method will add to this list
         any additional targets parsed.
      bool bTopLevel
         If True, this method will raise exceptions in case of non-target XML nodes; otherwise it
         assumes that a later invocation of Target.parse_makefile_child() will validate the contents
         of eltParent.
      """

      for elt in eltParent.childNodes:
         # Skip whitespace/comment nodes and nodes without children.
         if not self._is_node_whitespace(elt) and elt.hasChildNodes():
            if elt.nodeType == elt.ELEMENT_NODE:
               # Pick a make.target.Target subclass for this target type.
               clsTarget = target.Target.select_subclass(elt)
               if clsTarget:
                  # Every target must have a name attribute.
                  sName = elt.getAttribute('name')
                  if not sName:
                     raise SyntaxError('<{}>: missing “name” attribute'.format(elt.nodeName))
                  # Instantiate the Target-derived class, assigning it its name.
                  tgt = clsTarget(self, sName)
                  self.add_target(tgt)
                  listTargetsAndNodes.append((tgt, elt))
                  # Scan for nested target definitions.
                  self._parse_collect_targets(elt, listTargetsAndNodes, False)
               elif bTopLevel:
                  raise SyntaxError(
                     '<{}>: not a target definition XML element'.format(elt.nodeName)
                  )
            elif bTopLevel:
               raise SyntaxError(
                  'expected target definition XML element, found: {}'.format(elt.nodeName)
               )


   def _parse_doc(self, doc):
      """Parses a DOM representation of an ABC makefile.

      xml.dom.Document doc
         XML document to parse.
      """

      doc.documentElement.normalize()

      # Do a first scan of the document to instantiate all the defined targets and associated with
      # their respective XML elements. By instantiating all targets upfront we allow for
      # Target.parse_makefile_child() to always find a referenced target even it it was defined
      # after the target on which parse_makefile_child() is called, and to determine on-the-fly
      # whether a referenced <dynlib> is a target we should build or if we should expect to find it
      # somewhere else.
      listTargetsAndNodes = []
      self._parse_collect_targets(doc.documentElement, listTargetsAndNodes)

      # Now that all the targets have been instantiated, we can have them parse their definitions.
      for tgt, eltTarget in listTargetsAndNodes:
         for nd in eltTarget.childNodes:
            # Skip whitespace/comment nodes.
            if not self._is_node_whitespace(nd):
               if nd.nodeType != nd.ELEMENT_NODE:
                  raise SyntaxError('{}: expected XML element, found: {}'.format(tgt, nd.nodeName))
               if not tgt.parse_makefile_child(nd):
                  # Target.parse_makefile_child() returns False when it doesn’t know how to handle
                  # the specified child element.
                  raise SyntaxError('{}: unexpected XML element: <{}>'.format(tgt, nd.nodeName))


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

      print('Reverse dependencies')
      print('--------------------')
      for tgt in self._m_dictNamedTargets.values():
         print(str(tgt))
         tgt.dump_dependents('  ')
      print('')

