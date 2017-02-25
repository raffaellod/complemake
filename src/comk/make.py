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

"""Implementation of the main Complemake class, Make."""

import os
import re
import sys

import comk.job
import comk.logging
import comk.makefileparser
import comk.metadata
import comk.platform
import comk.target
import yaml


##############################################################################################################

class MakefileError(Exception):
   """Indicates a semantical error in a makefile."""

   pass

##############################################################################################################

class DependencyCycleError(MakefileError):
   """Raised when a makefile specifies dependencies among targets in a way that creates circular dependencies,
   an unsolvable situation.
   """

   _targets = None

   def __init__(self, message, targets, *args):
      """See MakefileError.__init__().

      str message
         Exception message.
      iterable(comk.target.Target) targets
         Targets that create a cycle in the dependency graph.
      iterable(object*) args
         Other arguments.
      """

      # Don’t pass targets to the superclass’ constructor, so its __str__() won’t display it.
      MakefileError.__init__(self, message, *args)

      self._targets = targets

   def __str__(self):
      # Show the regular exception description line followed by the targets in the cycle, one per line.
      s = MakefileError.__str__(self) + '\n' + '\n'.join('  ' + str(target) for target in self._targets)
      return s

##############################################################################################################

class TargetReferenceError(MakefileError):
   """Raised when a reference to a target can’t be resolved."""

   pass

##############################################################################################################

@comk.makefileparser.MakefileParser.local_tag('complemake/makefile', yaml.Kind.MAPPING)
class Makefile(object):
   """Stores the attributes of a YAML complemake/makefile object."""

   # List of comk.target.Target instances parsed from the top-level “targets” attribute.
   _targets = None

   def __init__(self, mp, parsed):
      """Constructor.

      comk.makefileparser.MakefileParser mp
         Parser instantiating the object.
      object parsed
         Parsed YAML object to be used to construct the new instance.
      """

      targets = parsed.get('targets')
      if not isinstance(targets, list):
         mp.raise_parsing_error('attribute “targets” must be a sequence')
      for i, o in enumerate(targets):
         if not isinstance(o, comk.target.Target):
            mp.raise_parsing_error((
               'elements of the “targets” attribute must be of type !complemake/target/*, but element [{}] ' +
               'is not'
            ).format(i))
      self._targets = targets

   def _get_targets(self):
      return self._targets

   targets = property(_get_targets, doc="""Returns the top-level targets declared in the makefile.""")

##############################################################################################################

class Make(object):
   """Parses a Complemake file (.comk) and exposes a comk.job.Runner instance that can be used to schedule
   target builds and run them.

   Example usage:

      mk = comk.Make()
      mk.parse('project.comk.yml')
      target = mk.get_named_target('projectbin')
      mk.build((target, ))
   """

   # See Make.cross_build.
   _cross_build = None
   # See Make.dry_run.
   _dry_run = None
   # Targets explicitly or implicitly defined (e.g. intermediate targets) in the makefile that have a file
   # path assigned (file path -> Target).
   _file_targets = None
   # See Make.force_build.
   _force_build = None
   # See Make.force_test.
   _force_test = None
   # Platform under which targets will be built.
   _host_platform = None
   # See Make.job_runner.
   _job_runner = None
   # See Make.keep_going.
   _keep_going = None
   # See Make.log.
   _log = None
   # See Make.metadata.
   _metadata = None
   # Targets defined in the makefile that have a name assigned (name -> Target).
   _named_targets = None
   # See Make.output_dir.
   _output_dir = None
   # Platform under which targets will be executed.
   _target_platform = None
   # All targets explicitly or implicitly defined in the makefile.
   _targets = None

   # Special value used with get_target_by_*() to indicate that a target not found should result in an
   # exception.
   _RAISE_IF_NOT_FOUND = object()

   def __init__(self):
      """Constructor."""

      self._cross_build = None
      self._dry_run = False
      self._file_targets = {}
      self._force_build = False
      self._force_test = False
      self._host_platform = comk.platform.Platform.detect_host()
      self._job_runner = comk.job.Runner(self)
      self._keep_going = False
      self._log = comk.logging.Logger(comk.logging.LogGenerator())
      self._metadata = None
      self._named_targets = {}
      self._output_dir = ''
      self._target_platform = None
      self._targets = set()

   def add_file_target(self, target, file_path):
      """Records a file target, making sure no duplicates are added.

      comk.target.FileTarget target
         Target to add.
      str file_path
         Target file path.
      """

      if file_path in self._file_targets:
         raise KeyError('duplicate target file path: {}'.format(file_path))
      self._file_targets[file_path] = target

   def add_named_target(self, target, name):
      """Records a named target, making sure no duplicates are added.

      comk.target.NamedTargetMixIn target
         Target to add.
      str name
         Target name.
      """

      if name in self._named_targets:
         raise KeyError('duplicate target name: {}'.format(name))
      self._named_targets[name] = target

   def add_target(self, target):
      """Records a target.

      comk.target.Target target
         Target to add.
      """

      self._targets.add(target)

   def _get_cross_build(self):
      return self._cross_build

   cross_build = property(_get_cross_build, doc="""
      If True, the host platform is not the same as the target platform, and Complemake may be unable to
      execute the binaries it builds.
   """)

   def build_targets(self, targets):
      """Builds the specified targets, as well as their dependencies, as needed.

      iterable(comk.target.Target*) targets
         Targets to be built.
      bool return
         True if all the targets were built successfully, or False otherwise.
      """

      try:
         # Begin building the selected targets.
         for target in targets:
            target.start_build()
         # Keep running until all queued jobs have completed.
         self._job_runner.run()
      finally:
         if not self._dry_run:
            # Write any new metadata.
            self._metadata.write()
      return self.job_runner.failed_jobs == 0

   def _get_dry_run(self):
      return self._dry_run

   def _set_dry_run(self, dry_run):
      self._dry_run = dry_run

   dry_run = property(_get_dry_run, _set_dry_run, doc="""
      If True, commands will only be printed, not executed; if False, they will be printed and executed.
   """)

   def _get_force_build(self):
      return self._force_build

   def _set_force_build(self, force_build):
      self._force_build = force_build

   force_build = property(_get_force_build, _set_force_build, doc="""
      If True, targets are rebuilt unconditionally; if False, targets are rebuilt as needed.
   """)

   def _get_force_test(self):
      return self._force_test

   def _set_force_test(self, force_test):
      self._force_test = force_test

   force_test = property(_get_force_test, _set_force_test, doc="""
      If True, all test targets are executed unconditionally; if False, test targets are only executed if
      triggered by their dependencies.
   """)

   def get_file_target(self, file_path, fallback = _RAISE_IF_NOT_FOUND):
      """Returns a file target given its file path, raising an exception if no such target exists and no
      fallback value was provided.

      str file_path
         Path to the target’s file.
      object fallback
         Object to return in case the specified target does not exist. If omitted, an exception will be raised
         if the target does not exist.
      comk.target.Target return
         Target that builds file_path, or fallback if no such target was defined in the makefile.
      """

      target = self._file_targets.get(file_path, fallback)
      if target is self._RAISE_IF_NOT_FOUND:
         raise TargetReferenceError('unknown target: {}'.format(file_path))
      return target

   def get_named_target(self, name, fallback = _RAISE_IF_NOT_FOUND):
      """Returns a target given its name as specified in the makefile, raising an exception if no such target
      exists and no fallback value was provided.

      str name
         Name of the target to look for.
      object fallback
         Object to return in case the specified target does not exist. If omitted, an exception will be raised
         if the target does not exist.
      comk.target.Target return
         Target named name, or fallback if no such target was defined in the makefile.
      """

      target = self._named_targets.get(name, fallback)
      if target is self._RAISE_IF_NOT_FOUND:
         raise TargetReferenceError('undefined target: {}'.format(name))
      return target

   def _get_job_runner(self):
      return self._job_runner

   job_runner = property(_get_job_runner, doc="""Job runner.""")

   def _get_keep_going(self):
      return self._keep_going

   def _set_keep_going(self, keep_going):
      self._keep_going = keep_going

   keep_going = property(_get_keep_going, _set_keep_going, doc="""
      If True, build jobs will continue to be run even after a failed job, as long as they don’t depend on a
      failed job. If False, a failed job causes execution to stop as soon as any other running jobs complete.
   """)

   def _get_log(self):
      return self._log

   log = property(_get_log, doc="""Output log.""")

   def _get_metadata(self):
      return self._metadata

   metadata = property(_get_metadata, doc="""Metadata store.""")

   def _get_named_targets(self):
      return self._named_targets.values()

   named_targets = property(_get_named_targets, doc="""Targets explicitly declared in the parsed makefile.""")

   def _get_output_dir(self):
      return self._output_dir

   def _set_output_dir(self, output_dir):
      self._output_dir = output_dir

   output_dir = property(_get_output_dir, _set_output_dir, doc="""
      Output base directory that will be used for both intermediate and final build results.
   """)

   def parse(self, file_path):
      """Parses a Complemake file.

      str file_path
         Path to the makefile to parse.
      """

      mp = comk.makefileparser.MakefileParser(self)
      # mp.parse_file() will construct instances of any YAML-constructible Target subclass; Target instances
      # will add themselves to self._targets on construction. By collecting all targets upfront we allow for
      # Target.validate() to always find a referenced target even it it was defined after the target on which
      # validate() is called.
      mkf = mp.parse_file(file_path)
      # At this point, each target is stored in the YAML object tree as a Target/YAML object pair.
      if not isinstance(mkf, Makefile):
         mp.raise_parsing_error(
            'the top level object of a Complemake file must be of type complemake/makefile'
         )
      # Validate each target.
      for target in self._targets:
         target.validate()
      # Make sure the makefile doesn’t define circular dependencies.
      self.validate_dependency_graph()

      metadata_file_path = os.path.join(os.path.dirname(file_path), '.comk-metadata')
      # Try loading an existing metadata store, or default to creating a new one.
      try:
         self._metadata = comk.metadata.MetadataParser(self).parse_file(metadata_file_path)
      except (comk.FileNotFoundErrorCompat, OSError):
         self._metadata = comk.metadata.MetadataStore(self, metadata_file_path)

   def _get_target_platform(self):
      if not self._target_platform:
         self._target_platform = comk.platform.Platform.detect_host()
         self._cross_build = False
      return self._target_platform

   def _set_target_platform(self, o):
      if self._target_platform:
         raise Exception('cannot set target platform after it’s already been assigned or detected')
      if isinstance(o, basestring):
         o = comk.platform.SystemType.parse_tuple(o)
      if isinstance(o, comk.platform.SystemType):
         o = comk.platform.Platform.from_system_type(o)
      if not isinstance(o, comk.platform.Platform):
         raise TypeError((
            'cannot set target platform from object of type {}; expected one of str, ' +
            'comk.platform.SystemType, comk.platform.Platform'
         ).format(type(o)))
      self._target_platform = o
      self._cross_build = (o.system_type() != self._host_platform.system_type())

   target_platform = property(_get_target_platform, _set_target_platform, doc="""
      Platform under which the generated outputs will execute.
   """)

   def print_target_graphs(self):
      """Prints to stdout a graph with all the targets’ dependencies and one with their reverse dependencies.
      """

      print('Dependencies')
      print('------------')
      for target in self._named_targets.values():
         print(str(target))
         target.dump_dependencies('  ')
      print('')

   def validate_dependency_graph(self):
      """Ensures that no cycles exist in the targets dependency graph.

      Implemented by performing a depth-first search for back edges in the graph; this is very speed-efficient
      because it only visits each subtree once.

      See also the recursion step Make._validate_dependency_subtree().
      """

      # No previous ancerstors considered for the targets enumerated by this function.
      dependents = []
      # No subtrees validated yet.
      validated_subtrees = set()
      for target in self._targets:
         if target not in validated_subtrees:
            self._validate_dependency_subtree(target, dependents, validated_subtrees)

   def _validate_dependency_subtree(self, sub_root_target, dependents, validated_subtrees):
      """Recursion step for Make.validate_dependency_graph(). Validates a dependency graph subtree rooted in
      sub_root_target, adding sub_root_target to validated_subtrees in case of success, or raising an
      exception in case of problems with the subtree.

      comk.target.Target sub_root_target
         Target at the root of the subtree to validate.
      list dependents
         Ancestors of sub_root_target. An ordered set with fast push/pop would be faster, since we performs a
         lot of lookups in it.
      set validated_subtrees
         Subtrees already validated. Used to avoid visiting a subtree more than once.
      """

      # Add this target to the dependents. This allows to find back edges and will even reveal if a target
      # depends on itself.
      dependents.append(sub_root_target)
      for dependency_target in sub_root_target.get_dependencies(targets_only=True):
         for i, dependent_target in enumerate(dependents):
            if dependent_target is dependency_target:
               # Back edge found: this dependency creates a cycle. Since dependents[i] is the previous
               # occurrence of dependency_target as ancestor of sub_root_target, dependents[i:] will yield all
               # the nodes (targets) in the cycle. Note that dependents does include sub_root_target.
               raise DependencyCycleError(
                  'dependency graph validation failed, cycle detected:', dependents[i:]
               )
         if dependency_target not in validated_subtrees:
            # Recurse to verify that this dependency’s subtree doesn’t contain cycles.
            self._validate_dependency_subtree(dependency_target, dependents, validated_subtrees)
      # Restore the dependents and mark this subtree as validated.
      del dependents[len(dependents) - 1]
      validated_subtrees.add(sub_root_target)
