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

"""Implementation of the main Complemake class, Core."""

import os
import re
import sys

import comk.job
import comk.logging
import comk.metadata
import comk.platform
import comk.projectparser
import comk.target
import yaml


##############################################################################################################

class AmbiguousProjectError(Exception):
   """Indicates that 0 or more than 1 projects were found in a given folder."""

   pass

##############################################################################################################

class ProjectError(Exception):
   """Indicates a semantical error in a project."""

   pass

##############################################################################################################

class DependencyCycleError(ProjectError):
   """Raised when a project specifies dependencies among targets in a way that creates circular dependencies,
   an unsolvable situation.
   """

   _targets = None

   def __init__(self, message, targets, *args):
      """See ProjectError.__init__().

      str message
         Exception message.
      iterable(comk.target.Target) targets
         Targets that create a cycle in the dependency graph.
      iterable(object*) args
         Other arguments.
      """

      # Don’t pass targets to the superclass’ constructor, so its __str__() won’t display it.
      ProjectError.__init__(self, message, *args)

      self._targets = targets

   def __str__(self):
      # Show the regular exception description line followed by the targets in the cycle, one per line.
      s = ProjectError.__str__(self) + '\n' + '\n'.join('  ' + str(target) for target in self._targets)
      return s

##############################################################################################################

class TargetReferenceError(ProjectError):
   """Raised when a reference to a target can’t be resolved."""

   pass

##############################################################################################################

@comk.projectparser.ProjectParser.local_tag('complemake/project', yaml.Kind.MAPPING)
@comk.projectparser.ProjectParser.local_tag('complemake/makefile', yaml.Kind.MAPPING) # TODO: delete legacy alias.
class Project(object):
   """Stores the attributes of a YAML complemake/project object."""

   def __init__(self, parser, parsed):
      """Constructor.

      comk.projectparser.ProjectParser parser
         Parser instantiating the object.
      object parsed
         Parsed YAML object to be used to construct the new instance.
      """

      targets = parsed.get('targets')
      if not targets or not isinstance(targets, list):
         parser.raise_parsing_error('attribute “targets” must be a non-empty sequence')
      for i, o in enumerate(targets):
         if not isinstance(o, comk.target.Target):
            parser.raise_parsing_error((
               'elements of the “targets” attribute must be of type !complemake/target/*, but element [{}] ' +
               'is not'
            ).format(i))

##############################################################################################################

class Core(object):
   """Parses a Complemake file (.comk) and exposes a comk.job.Runner instance that can be used to schedule
   target builds and run them.

   Example usage:

      core = comk.Core()
      core.parse('project.comk.yml')
      target = core.get_named_target('projectbin')
      core.build((target, ))
   """

   # See Core.cross_build.
   _cross_build = None
   # See Core.dry_run.
   _dry_run = None
   # Targets explicitly or implicitly defined (e.g. intermediate targets) in the project that have a file path
   # assigned (file path -> Target).
   _file_targets = None
   # See Core.force_build.
   _force_build = None
   # See Core.force_test.
   _force_test = None
   # Platform under which targets will be built.
   _host_platform = None
   # See Core.job_runner.
   _job_runner = None
   # See Core.keep_going.
   _keep_going = None
   # See Core.log.
   _log = None
   # See Core.metadata.
   _metadata = None
   # Targets defined in the project that have a name assigned (name -> Target).
   _named_targets = None
   # See Core.output_dir.
   _output_dir = None
   # Platform under which targets will be executed.
   _target_platform = None
   # All targets explicitly or implicitly defined in the project.
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
      self._project_path = ''
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

   def find_project_file(self):
      """Finds and returns a single project file in the self.project_path, or raises an error if 0 or >1
      project files could be found.

      str return
         Selected project.
      """

      project_file_path = None
      # Check if the current directory contains a single Complemake file.
      for file_name in os.listdir(self._project_path):
         if file_name.endswith('.comk'):
            if project_file_path:
               raise AmbiguousProjectError('multiple projects found in “{}”'.format(self._project_path))
            project_file_path = os.path.join(self._project_path, file_name)
      if project_file_path:
         return project_file_path
      else:
         raise AmbiguousProjectError('no projects found in “{}”'.format(self._project_path))

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
         Target that builds file_path, or fallback if no such target was defined in the project.
      """

      target = self._file_targets.get(file_path, fallback)
      if target is self._RAISE_IF_NOT_FOUND:
         raise TargetReferenceError('unknown target: {}'.format(file_path))
      return target

   def get_named_target(self, name, fallback = _RAISE_IF_NOT_FOUND):
      """Returns a target given its name as specified in the project, raising an exception if no such target
      exists and no fallback value was provided.

      str name
         Name of the target to look for.
      object fallback
         Object to return in case the specified target does not exist. If omitted, an exception will be raised
         if the target does not exist.
      comk.target.Target return
         Target named name, or fallback if no such target was defined in the project.
      """

      target = self._named_targets.get(name, fallback)
      if target is self._RAISE_IF_NOT_FOUND:
         raise TargetReferenceError('undefined target: {}'.format(name))
      return target

   def inproject_path(self, path):
      """Prepends the project’s path to a non-absolute path, leaving absolute paths unchanged.

      str path
         Input path.
      str return
         Resulting path.
      """

      if not os.path.isabs(path):
         path = os.path.join(self._project_path, path)
      return os.path.normpath(path)

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

   named_targets = property(_get_named_targets, doc="""Targets explicitly declared in the parsed project.""")

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
         Path to the project to parse.
      """

      parser = comk.projectparser.ProjectParser(self)
      # parser.parse_file() will construct instances of any YAML-constructible Target subclass; Target
      # instances will add themselves to self._targets on construction. By collecting all targets upfront we
      # allow for Target.validate() to always find a referenced target even it it was defined after the target
      # on which validate() is called.
      project = parser.parse_file(file_path)
      # At this point, each target is stored in the YAML object tree as a Target/YAML object pair.
      if not isinstance(project, Project):
         parser.raise_parsing_error(
            'the top level object of a Complemake file must be of type complemake/project'
         )
      # Validate each target.
      for target in self._targets:
         target.validate()
      # Make sure the project doesn’t define circular dependencies.
      self.validate_dependency_graph()

      metadata_file_path = os.path.join(self._output_dir, '.comk-metadata')
      # Try loading an existing metadata store, or default to creating a new one.
      try:
         self._metadata = comk.metadata.MetadataParser(self).parse_file(metadata_file_path)
      except (comk.FileNotFoundErrorCompat, OSError):
         self._metadata = comk.metadata.MetadataStore(self, metadata_file_path)

   def _get_project_path(self):
      return self._project_path

   def _set_project_path(self, project_path):
      self._project_path = project_path

   project_path = property(_get_project_path, _set_project_path, doc='Base path of the project.')

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

      See also the recursion step Core._validate_dependency_subtree().
      """

      # No previous ancerstors considered for the targets enumerated by this function.
      dependents = []
      # No subtrees validated yet.
      validated_subtrees = set()
      for target in self._targets:
         if target not in validated_subtrees:
            self._validate_dependency_subtree(target, dependents, validated_subtrees)

   def _validate_dependency_subtree(self, sub_root_target, dependents, validated_subtrees):
      """Recursion step for Core.validate_dependency_graph(). Validates a dependency graph subtree rooted in
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
