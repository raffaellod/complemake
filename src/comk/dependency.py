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

from __future__ import absolute_import

import hashlib
import os
import platform as pyplatform
import shutil
import sys
import weakref

import comk
import comk.core
import comk.projectparser
import comk.tool

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

   class Repo(object):
      """Abstraction for source code repository."""

      # Path to the local work area (build & output) for the dependency.
      _work_area_path = None

      def __init__(self, path):
         """Constructor.

         str repo
            Location of the repository.
         """

         hash = hashlib.sha1()
         if isinstance(path, bytes):
            hash.update(path)
         else:
            hash.update(path.encode('utf-8'))
         self._work_area_path = os.path.join(comk.get_per_user_comk_dir(), 'depwa', hash.hexdigest())

      def get_output_dir(self):
         """Returns the path to the directory where build output files will be generated.

         str return
            Output path.
         """

         return os.path.join(self._work_area_path, 'out')

      def get_project_path(self):
         """Returns a path from which Complemake can be run to build the dependency project.

         str return
            Path to the project.
         """

         raise NotImplementedError('Repo.get_project_path() must be overridden in ' + type(self).__name__)

      def update(self, log):
         """Updates the repo snapshot.

         comk.logging.Logger log
            Logger to use for any output.
         """

         raise NotImplementedError('Repo.pull() must be overridden in ' + type(self).__name__)


   class GitRepo(Repo):
      """Git repository."""

      # Latest “treeish” (hash, tag or branch) that may be used. If None, the tip of the repo’s default branch
      # will be used.
      _max_treeish = None
      # Earliest “treeish” (hash, tag or branch) that may be used. If None, the first commit in the repo’s
      # default branch will be used.
      _min_treeish = None
      # Git remote URI.
      _uri = None

      def __init__(self, uri, min_treeish = None, max_treeish = None):
         """Constructor.

         str uri
            Git remote URI.
         str min_treeish
            Earliest “treeish” (hash, tag or branch) that may be used. If None, the first commit in the repo’s
            default branch will be used.
         str max_treeish
            Latest “treeish” (hash, tag or branch) that may be used. If None, the tip of the repo’s default
            branch will be used.
         """

         ExternalProjectDependency.Repo.__init__(self, uri)

         self._max_treeish = max_treeish
         self._min_treeish = min_treeish
         self._uri = uri

      def get_project_path(self):
         """See Repo.get_project_path()."""

         return os.path.join(self._work_area_path, 'repo')

      def update(self, log):
         """See Repo.update()."""

         log(log.MEDIUM, 'dep: updating git repo from {}', self._uri)
         repo_clone_path = self.get_project_path()
         if os.path.isdir(os.path.join(repo_clone_path, '.git')):
            # TODO: invoke git from repo_clone_path.
            # Drop all foreign files and changes.
            self.run_git('git', 'clean', '--force', cwd=repo_clone_path)
            # Use --ff-only to “encourage” the user to not fork within a Complemake-managed repo clone.
            self.run_git('git', 'pull', '--ff-only', cwd=repo_clone_path)
         else:
            # First time.
            comk.makedirs(repo_clone_path)
            self.run_git('git', 'clone', self._uri, repo_clone_path)


   class LocalDirRepo(Repo):
      """Directory on the same host posing as a repository."""

      # Path where the “repository” is located.
      _path = None

      def __init__(self, path):
         """Constructor.

         str path
            Path where the “repository” is located.
         """

         ExternalProjectDependency.Repo.__init__(self, path)

         self._path = os.path.abspath(path)

      def get_project_path(self):
         """See Repo.get_project_path()."""

         return self._path

      def update(self, log):
         """See Repo.update()."""

         comk.makedirs(self._work_area_path)
         # Leave a track of where the project actually is, for user’s convenience.
         source_link_path = os.path.join(self._work_area_path, 'source')
         if pyplatform.system() == 'Windows':
            # The user most likely doesn’t have privilege to create a symlink, so just make a plain text file.
            link_exists = os.path.exists(source_link_path)
            if link_exists and not os.path.isfile(source_link_path):
               shutil.rmtree(source_link_path, ignore_errors=True)
               link_exists = False
            if link_exists:
               with io.open(source_link_path, 'r', encoding='utf-8') as source_link:
                  stored_link = source_link.read()
               if stored_link != self._path:
                  os.unlink(source_link_path)
            if link_exists:
               link_updated = False
            else:
               log(log.MEDIUM, 'dep: updating source link for {}', self._path)
               with io.open(source_link_path, 'w', encoding='utf-8') as source_link:
                  source_link.write(self._path)
               link_updated = True
         else:
            link_exists = os.path.lexists(source_link_path)
            if link_exists and not os.path.islink(source_link_path):
               shutil.rmtree(source_link_path, ignore_errors=True)
               link_exists = False
            if link_exists and os.readlink(source_link_path) != self._path:
               os.unlink(source_link_path)
               link_exists = False
            if link_exists:
               link_updated = False
            else:
               log(log.MEDIUM, 'dep: updating source link for {}', self._path)
               os.symlink(self._path, source_link_path)
               link_updated = True
         if not link_updated:
            log(log.MEDIUM, 'dep: nothing to update for {}', self._path)


   # Parent Core instance.
   _core = None
   # Core instance to build the dependency.
   _dep_core = None
   # Repo instance to provide repository interaction.
   _repo = None

   def __init__(self, parser, parsed):
      """Constructor.

      comk.projectparser.ProjectParser parser
         Parser instantiating the object.
      object parsed
         Parsed YAML object to be used to construct the new instance.
      """

      core = parser.core
      self._core = weakref.ref(core)
      repo = parsed.get('repo')
      if not isinstance(repo, basestring):
         parser.raise_parsing_error('missing or non-string attribute “repo”')
      if repo.endswith('.git') or repo.endswith('.git/'):
         min_version = parser.get('min version')
         if min_version and not isinstance(min_version, basestring):
            parser.raise_parsing_error('attribute “min version” must be a string')
         max_version = parser.get('max version')
         if max_version and not isinstance(max_version, basestring):
            parser.raise_parsing_error('attribute “max version” must be a string')
         self._repo = self.GitRepo(repo, min_version, max_version)
      elif repo.startswith('file:///') or repo.startswith('/') or repo.startswith('.'):
         if repo.startswith('file:///'):
            repo = repo[len('file:///'):]
         self._repo = self.LocalDirRepo(core.inproject_path(repo))
      else:
         raise comk.core.ProjectError('unsupported repo path/URI: “{}”'.format(repo))

   def build(self):
      """Builds the dependency. Unlike in-project targets, external dependencies build synchronously.

      TODO: build external dependencies asynchronously, like targets.
      """

      return self._dep_core.build_targets(self._dep_core.named_targets)

   def create_core(self):
      """Creates a Core instance for the dependency.

      comk.core.Core return
         Core instance for the dependency project.
      """

      self._dep_core = self._core().spawn_child()
      self._dep_core.output_dir   = self._repo.get_output_dir()
      self._dep_core.project_path = self._repo.get_project_path()

      self._dep_core.parse(self._dep_core.find_project_file())
      self._dep_core.prepare_external_dependencies()

      return self._dep_core

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

   def update(self):
      """Updates the repo snapshot."""

      self._repo.update(self._core().log)

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
         raise comk.core.ProjectError('missing target name')
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
         raise comk.core.ProjectError('missing target file path')
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
