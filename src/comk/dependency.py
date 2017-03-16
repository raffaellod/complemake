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

"""Classes implementing different types of dependencies."""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import weakref

import comk
import comk.core
import comk.project
import yaml

if sys.hexversion >= 0x03000000:
   basestring = str


##############################################################################################################

class Dependency(object):
   """Represents an abstract dependency with no additional information."""

   def __str__(self):
      return '({})'.format(type(self).__name__)

##############################################################################################################

class ExternalProjectDependency(Dependency):
   """Dependency on an external project, that needs to be retrieved from a different repo and built prior to
   building the current makefile.
   """

   # Parent Core instance.
   _core = None
   # See dep_core.
   _dep_core = None
   # Repository. Typically a URI or an absolute folder path.
   _repo = None
   # Path to the local work area (build & output) for the dependency.
   _work_area_path = None

   def __init__(self, core, repo):
      """Constructor.

      comk.core.Core core
         Core instance.
      str repo
         Repository.
      """

      self._core = weakref.ref(core)
      self._dep_core = None
      hash = hashlib.sha1()
      if isinstance(repo, bytes):
         hash.update(repo)
      else:
         hash.update(repo.encode('utf-8'))
      self._repo = repo
      self._work_area_path = os.path.join(core.shared_dir, 'depwa', hash.hexdigest())

      core.add_external_dependency(self, repo)

   def create_core(self):
      """Creates a Core instance for the dependency.

      comk.core.Core return
         Core instance for the dependency project.
      """

      self._dep_core = self._core().spawn_child()
      self._dep_core.output_dir   = self.get_output_dir()
      self._dep_core.project_path = self.get_project_path()

      self._dep_core.parse(self._dep_core.find_project_file())

      return self._dep_core

   def _get_dep_core(self):
      return self._dep_core

   dep_core = property(_get_dep_core, doc="""Core instance for the dependency.""")

   def get_output_dir(self):
      """Returns the path to the directory where build output files will be generated.

      str return
         Output path.
      """

      return os.path.join(self._work_area_path, 'out')

   def get_path(self, dir):
      """Returns a well-known directory for the project.

      str dir
         Well-known directory to get for the project.
      str return
         Output path.
      """

      if dir != comk.core.Core.INCLUDE_DIR:
         dir = os.path.join(self._dep_core.output_dir, dir)
      return self._dep_core.inproject_path(dir)

   def get_project_path(self):
      """Returns a path from which Complemake can be run to build the dependency project.

      str return
         Path to the project.
      """

      raise NotImplementedError(
         'ExternalProjectDependency.get_project_path() must be overridden in ' + type(self).__name__
      )

   def initialize(self):
      """Initializes the repo snapshot."""

      raise NotImplementedError(
         'ExternalProjectDependency.initialize() must be overridden in ' + type(self).__name__
      )

   def update(self):
      """Updates the repo snapshot."""

      raise NotImplementedError(
         'ExternalProjectDependency.update() must be overridden in ' + type(self).__name__
      )

##############################################################################################################

@comk.project.Parser.local_tag('complemake/dep/git', yaml.Kind.MAPPING)
class ExternalGitDependency(ExternalProjectDependency):
   """Dependency on an external git repo."""

   # Latest “treeish” (hash, tag or branch) that may be used. If None, the tip of the repo’s default branch
   # will be used.
   _max_treeish = None
   # Earliest “treeish” (hash, tag or branch) that may be used. If None, the first commit in the repo’s
   # default branch will be used.
   _min_treeish = None

   def __init__(self, parser, parsed):
      """Constructor.

      comk.project.Parser parser
         Parser instantiating the object.
      object parsed
         Parsed YAML object to be used to construct the new instance.
      """

      repo = parsed.get('repo')
      if not repo or not isinstance(repo, basestring):
         parser.raise_parsing_error('missing or non-string attribute “repo”')
      # Convert non-URIs into absolute paths.
      if not re.match('^([^@]*@)?[a-z]+://', repo):
         repo = parser.core.inproject_path(repo)

      ExternalProjectDependency.__init__(self, parser.core, repo)

      min_version = parsed.get('min version')
      if min_version and not isinstance(min_version, basestring):
         parser.raise_parsing_error('attribute “min version” must be a string')
      max_version = parsed.get('max version')
      if max_version and not isinstance(max_version, basestring):
         parser.raise_parsing_error('attribute “max version” must be a string')
      self._max_treeish = max_version
      self._min_treeish = min_version

   def get_project_path(self):
      """See ExternalProjectDependency.get_project_path()."""

      return os.path.join(self._work_area_path, 'repo')

   def initialize(self):
      """See ExternalProjectDependency.initialize()."""

      log = self._core().log

      repo_clone_path = self.get_project_path()
      if not os.path.isdir(os.path.join(repo_clone_path, '.git')):
         # First time.
         log(log.MEDIUM, 'dep: updating git repo from {}', self._repo)
         comk.makedirs(repo_clone_path)
         self.run_git('git', 'clone', self._repo, '.')

   def run_git(self, *args):
      subprocess.check_call(args, cwd=self.get_project_path())

   def update(self):
      """See ExternalProjectDependency.update()."""

      log = self._core().log

      if os.path.isdir(os.path.join(self.get_project_path(), '.git')):
         log(log.MEDIUM, 'dep: updating git repo from {}', self._repo)
         # Drop all foreign files and changes.
         self.run_git('git', 'clean', '--force')
         # Use --ff-only to “encourage” the user to not fork within a Complemake-managed repo clone.
         self.run_git('git', 'pull', '--ff-only')
      else:
         # First time.
         self.initialize()

##############################################################################################################

@comk.project.Parser.local_tag('complemake/dep/dir', yaml.Kind.MAPPING)
class ExternalDirDependency(ExternalProjectDependency):
   """Dependency on an external project elsewhere in the file system."""

   def __init__(self, parser, parsed):
      """Constructor.

      comk.project.Parser parser
         Parser instantiating the object.
      object parsed
         Parsed YAML object to be used to construct the new instance.
      """

      repo = parsed.get('repo')
      if not repo or not isinstance(repo, basestring):
         parser.raise_parsing_error('missing or non-string attribute “repo”')

      ExternalProjectDependency.__init__(self, parser.core, parser.core.inproject_path(repo))

   def get_project_path(self):
      """See ExternalProjectDependency.get_project_path()."""

      return self._repo

   def initialize(self):
      """See ExternalProjectDependency.initialize()."""

      log = self._core().log

      comk.makedirs(self._work_area_path)
      # Leave a track of where the project actually is, for user’s convenience.
      # Note: under Windows we assume that the user most likely doesn’t have privilege to create
      # symlinks, so “link” here means a plain text file.
      source_link_path = os.path.join(self._work_area_path, 'source')
      link_exists = os.path.lexists(source_link_path)
      if link_exists:
         if comk.os_is_windows():
            link_is_link = os.path.isfile(source_link_path)
         else:
            link_is_link = os.path.islink(source_link_path)
         if not link_is_link:
            log(log.HIGH, 'dep: removing unexpected non-file: {}', source_link_path)
            shutil.rmtree(source_link_path, ignore_errors=True)
            link_exists = False
      if link_exists:
         if comk.os_is_windows():
            with io.open(source_link_path, 'r', encoding='utf-8') as source_link:
               stored_link = source_link.read()
         else:
            stored_link = os.readlink(source_link_path)
         if stored_link != self._repo:
            log(log.HIGH, 'dep: deleting source link with incorrect contents: {}', stored_link)
            os.unlink(source_link_path)
            link_exists = False
      if not link_exists:
         log(log.MEDIUM, 'dep: creating source link for {}', self._repo)
         if comk.os_is_windows():
            with io.open(source_link_path, 'w', encoding='utf-8') as source_link:
               source_link.write(self._repo)
         else:
            os.symlink(self._repo, source_link_path)

   def update(self):
      """See ExternalProjectDependency.update()."""

      log = self._core().log

      # Leave a track of where the project actually is, for user’s convenience.
      source_link_path = os.path.join(self._work_area_path, 'source')
      if comk.os_is_windows():
         # The user most likely doesn’t have privilege to create a symlink, so just make a plain text file.
         link_exists = os.path.exists(source_link_path)
      else:
         link_exists = os.path.lexists(source_link_path)
      if link_exists:
         log(log.MEDIUM, 'dep: nothing to update for {}', self._repo)
      else:
         self.initialize()

##############################################################################################################

class NamedDependencyMixIn(object):
   """Mixin that provides a name for a Dependency subclass."""

   # Dependency name.
   _name = None

   def __init__(self, name):
      """Constructor.

      str name
         Dependency name.
      """

      if not name:
         raise comk.project.Error('missing target name')
      self._name = name

   def __str__(self):
      return '{} ({})'.format(self._name, type(self).__name__)

   def _get_name(self):
      return self._name

   name = property(_get_name, doc="""Name of the dependency.""")

##############################################################################################################

class ExternalLibDependency(NamedDependencyMixIn, Dependency):
   """External library dependency. Supports not built by the same project and referenced only by name, as in
   their typical usage.
   """

   pass

##############################################################################################################

class FileDependencyMixIn(object):
   """Mixin that provides a file path for a Dependency subclass."""

   # Dependency file path.
   _file_path = None

   def __init__(self, file_path):
      """Constructor.

      str file_path
         Dependency file path.
      """

      if not file_path:
         raise comk.project.Error('missing target file path')
      self._file_path = os.path.normpath(file_path)

   def __str__(self):
      return '{} ({})'.format(self._file_path, type(self).__name__)

   def _get_file_path(self):
      return self._file_path

   file_path = property(_get_file_path, doc="""Path to the dependency file.""")

   def get_generated_files(self):
      """Returns a list containing the path of every file generated by this dependency.

      list(str+) return
         File path of each generated file.
      """

      # Only one generated file in this default implementation.
      return [self._file_path]

##############################################################################################################

class OutputRerefenceDependency(FileDependencyMixIn, Dependency):
   """File used as a reference to validate expected outputs."""

   pass

##############################################################################################################

class SourceFileDependency(FileDependencyMixIn, Dependency):
   """Source file dependency."""

   pass

##############################################################################################################

class TestExecScriptDependency(FileDependencyMixIn, Dependency):
   """Executable that runs a test according to a “script”. Used to mimic interaction with a shell that
   Complemake does not implement.
   """

   pass

##############################################################################################################

class UndeterminedLibDependency(NamedDependencyMixIn, Dependency):
   """External or internal library dependency; gets replaced by a comk.target.Target subclass or
   ExternalLibDependency during Target.validate().
   """

   pass
