#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013-2016 Raffaello D. Di Napoli
#
# This file is part of Complemake.
#
# Complemake is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Complemake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Complemake. If not,
# see <http://www.gnu.org/licenses/>.
#---------------------------------------------------------------------------------------------------

"""Classes implementing different types of dependencies."""

import os

import comk.make


####################################################################################################

class Dependency(object):
   """Represents an abstract dependency with no additional information."""

   def __str__(self):
      return '({})'.format(type(self).__name__)

####################################################################################################

class NamedDependencyMixIn(object):
   """Mixin that provides a name for a Dependency subclass."""

   # Dependency name.
   _m_sName = None

   def __init__(self, sName):
      """Constructor.

      str sName
         Dependency name.
      """

      if not sName:
         raise comk.make.MakefileError('missing target name')
      self._m_sName = sName

   def __str__(self):
      return '{} ({})'.format(self._m_sName, type(self).__name__)

   def _get_name(self):
      return self._m_sName

   name = property(_get_name, doc = """Name of the dependency.""")

####################################################################################################

class FileDependencyMixIn(object):
   """Mixin that provides a file path for a Dependency subclass."""

   # Dependency file path.
   _m_sFilePath = None

   def __init__(self, sFilePath):
      """Constructor.

      str sFilePath
         Dependency file path.
      """

      if not sFilePath:
         raise comk.make.MakefileError('missing target file path')
      self._m_sFilePath = os.path.normpath(sFilePath)

   def __str__(self):
      return '{} ({})'.format(self._m_sFilePath, type(self).__name__)

   def _get_file_path(self):
      return self._m_sFilePath

   file_path = property(_get_file_path, doc = """Path to the dependency file.""")

   def get_generated_files(self):
      """Returns a list containing the path of every file generated by this dependency.

      list(str+) return
         File path of each generated file.
      """

      # Only one generated file in this default implementation.
      return [self._m_sFilePath]

####################################################################################################

class ForeignDependency(Dependency):
   """Abstract foreign dependency. Used by comk.target.Target and its subclasses to represent files
   not built by Complemake.
   """

   pass

####################################################################################################

class ForeignSourceDependency(FileDependencyMixIn, ForeignDependency):
   """Foreign source file dependency."""

   pass

####################################################################################################

class ForeignLibDependency(NamedDependencyMixIn, ForeignDependency):
   """Foreign library dependency. Supports libraries referenced only by name, as in their typical
   usage.
   """

   pass

####################################################################################################

class OutputRerefenceDependency(FileDependencyMixIn, ForeignDependency):
   """File used as a reference to validate expected outputs."""

   pass

####################################################################################################

class TestExecScriptDependency(FileDependencyMixIn, ForeignDependency):
   """Executable that runs a test according to a “script”. Used to mimic interaction with a shell
   that Complemake does not implement.
   """

   pass

####################################################################################################

class UndeterminedLibDependency(NamedDependencyMixIn, Dependency):
   """Foreign or local library dependency; gets replaced by a comk.target.Target subclass or
   ForeignLibDependency during Target.validate().
   """

   pass
