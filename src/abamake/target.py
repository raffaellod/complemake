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

"""Classes implementing different types of build target, each aware of how to build itself."""

import os
import re
import sys

import make



####################################################################################################
# Target

class Target(object):
   """Abstract build target."""

   # See Target.dependencies.
   _m_setDeps = None
   # See Target.file_path.
   _m_sFilePath = None
   # See Target.name.
   _m_sName = None


   def __init__(self, mk, sName = None):
      """Constructor. Generates the target’s file path by calling Target._generate_file_path(), then
      adds itself to the Make instance’s target lists.

      Make mk
         Make instance.
      str sName
         See Target.name.
      """

      self._m_sName = sName
      self._m_sFilePath = self._generate_file_path(mk)
      # Add self to any applicable targets lists.
      mk._add_target(self)


   def add_dependency(self, tgtDep):
      """Adds a target dependency.

      Target tgtDep
         Dependency.
      """

      if self._m_setDeps is None:
         self._m_setDeps = set()
      self._m_setDeps.add(tgtDep)


   def build(self, mk, iterBlockingJobs):
      """Builds the output, using the facilities provided by the specified Make instance and
      returning the last job scheduled.

      Make mk
         Make instance.
      iterable(ScheduledJob*) iterBlockingJobs
         Jobs that should block the first one scheduled to build this target.
      ScheduledJob return
         Last job scheduled if the target scheduled jobs to be rebuilt, of None if it was already
         current.
      """

      raise NotImplementedError('Target.build() must be overridden')


   def _get_dependencies(self):
      if self._m_setDeps is None:
         return None
      else:
         # Return a copy, so the caller can manipulate it as necessary.
         return list(self._m_setDeps)

   dependencies = property(_get_dependencies, doc = """
      List of targets on which this target depends.
   """)


   def _get_file_path(self):
      return self._m_sFilePath

   file_path = property(_get_file_path, doc = """Target file path.""")


   def _generate_file_path(self, mk):
      """Generates and returns a file path for the target, based on other member varialbes set
      beforehand and the configuration of the provided Make instance. Called by Target.__init__().

      The default implementation doesn’t generate a file path because no output file is assumed.

      Make mk
         Make instance.
      str return
         Target file path; same as Target.file_path.
      """

      # No output file.
      return None


   def _get_name(self):
      return self._m_sName

   name = property(_get_name, doc = """Name of the target.""")


   def parse_makefile_child(self, elt, mk):
      """Validates and processes the specified child element of the target’s <target> element.

      xml.dom.Element elt
         <target> element to parse.
      Make mk
         Make instance.
      """

      # Default implementation: expect no child elements.
      raise SyntaxError('unexpected element: <{}>'.format(elt.nodeName))



####################################################################################################
# ObjectTarget

class ObjectTarget(Target):
   """Intermediate object target. The output file will be placed in a obj/ directory relative to the
   output base directory.
   """

   # See ObjectTarget.final_output_target.
   _m_clsFinalOutputTarget = None
   # See ObjectTarget.source_file_path.
   _m_sSourceFilePath = None


   def __init__(self, mk, sName, sSourceFilePath):
      """Constructor. See Target.__init__().

      Make mk
         Make instance.
      str sName
         See Target.name.
      str sSourceFilePath
         See ObjectTarget.source_file_path.
      """

      self._m_sSourceFilePath = sSourceFilePath
      super().__init__(mk, sName)


   def _get_final_output_target(self):
      return self._m_clsFinalOutputTarget

   def _set_final_output_target(self, clsFinalOutputTarget):
      self._m_clsFinalOutputTarget = clsFinalOutputTarget

   final_output_target = property(_get_final_output_target, _set_final_output_target, doc = """
      Kind of output that ObjectTarget.build() will aim for when generating the object file, e.g. by
      passing -fPIC for a C++ source file when compiling it for a shared object.
   """)


   def _generate_file_path(self, mk):
      """See Target._generate_file_path()."""

      return os.path.join(
         mk.output_dir, 'obj', self._m_sSourceFilePath + mk.cxxcompiler.object_suffix
      )


   def _get_source_file_path(self):
      return self._m_sSourceFilePath

   source_file_path = property(_get_source_file_path, doc = """
      Source from which the target is built.
   """)



####################################################################################################
# CxxObjectTarget

class CxxObjectTarget(ObjectTarget):
   """C++ intermediate object target."""

   def build(self, mk, iterBlockingJobs):
      """See Target.build()."""

      tplDeps = None
      if iterBlockingJobs:
         if mk.verbosity >= mk.VERBOSITY_MEDIUM:
            sys.stdout.write(
               '{}: rebuilding due to dependencies being rebuilt\n'.format(self.file_path)
            )
      else:
         # TODO: check for additional changed external dependencies.
         tplDeps = (self._m_sSourceFilePath, )
         if mk.file_metadata_changed(tplDeps):
            if mk.verbosity >= mk.VERBOSITY_MEDIUM:
               sys.stdout.write('{}: rebuilding due to changed sources\n'.format(self.file_path))
         else:
            # No dependencies being rebuilt, source up-to-date: no need to rebuild, unless --force.
            if mk.force_build:
               if mk.verbosity >= mk.VERBOSITY_MEDIUM:
                  sys.stdout.write('{}: up-to-date, but rebuild forced\n'.format(self.file_path))
            else:
               if mk.verbosity >= mk.VERBOSITY_MEDIUM:
                  sys.stdout.write('{}: up-to-date\n'.format(self.file_path))
               return None

      cxx = mk.cxxcompiler()
      cxx.set_output(self.file_path, self.final_output_target)
      cxx.add_input(self.source_file_path)
      # TODO: add file-specific flags.
      return cxx.schedule_jobs(mk, iterBlockingJobs, tplDeps)



####################################################################################################
# ExecutableTarget

class ExecutableTarget(Target):
   """Executable program target. The output file will be placed in a bin/ directory relative to the
   output base directory.
   """

   # List of dynamic libraries against which the target will be linked. Each item is either a Target
   # instance (for libraries/object files that can be built by the same makefile) or a string (for
   # external files).
   _m_listLinkerInputs = None


   def add_linker_input(self, oLib):
      """Adds a library dependency. Similar to Target.add_dependency(), but does not implicitly add
      oLib as a dependency.

      object oLib
         Library dependency. Can be a Target(-derived class) instance or a string.
      """

      if self._m_listLinkerInputs is None:
         self._m_listLinkerInputs = []
      self._m_listLinkerInputs.append(oLib)


   def build(self, mk, iterBlockingJobs):
      """See Target.build()."""

      # Due to the different types of objects in _m_listLinkerInputs and the fact we want to iterate
      # over that list only once, combine building the list of dependencies for which metadata need
      # to be checked with collecting linker inputs.
      listDeps = []
      lnk = mk.linker()
      lnk.set_output(self.file_path, type(self))
      # At this point all the dependencies are available, so add them as inputs.
      for oDep in self._m_listLinkerInputs or []:
         if isinstance(oDep, str):
            listDeps.append(oDep)
            # Strings go directly to the linker’s command line, assuming that they are external
            # libraries to link to.
            lnk.add_input_lib(oDep)
         else:
            listDeps.append(oDep.file_path)
            if isinstance(oDep, ObjectTarget):
               lnk.add_input(oDep.file_path)
            elif isinstance(oDep, DynLibTarget):
               lnk.add_input_lib(oDep.name)
               # Since we’re linking to a library built by this makefile, make sure to add the
               # output lib/ directory to the library search path.
               lnk.add_lib_path(os.path.join(mk.output_dir, 'lib'))
            else:
               raise Exception('unclassified linker input: {}'.format(oDep.file_path))

      if iterBlockingJobs:
         if mk.verbosity >= mk.VERBOSITY_MEDIUM:
            sys.stdout.write(
               '{}: rebuilding due to dependencies being rebuilt\n'.format(self.file_path)
            )
      elif listDeps and mk.file_metadata_changed(listDeps):
         if mk.verbosity >= mk.VERBOSITY_MEDIUM:
            sys.stdout.write('{}: rebuilding due to changed dependencies\n'.format(
               self.file_path
            ))
      else:
         # No dependencies being rebuilt, no inputs or inputs up-to-date: no need to rebuild, unless
         # --force.
         if mk.force_build:
            if mk.verbosity >= mk.VERBOSITY_MEDIUM:
               sys.stdout.write('{}: up-to-date, but rebuild forced\n'.format(self.file_path))
         else:
            if mk.verbosity >= mk.VERBOSITY_MEDIUM:
               sys.stdout.write('{}: up-to-date\n'.format(self.file_path))
            return None

      return lnk.schedule_jobs(mk, iterBlockingJobs, listDeps)


   def _generate_file_path(self, mk):
      """See Target._generate_file_path()."""

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      return os.path.join(mk.output_dir, 'bin', '' + self.name + '')


   def parse_makefile_child(self, elt, mk):
      """See Target.parse_makefile_child()."""

      if elt.nodeName == 'source':
         # Pick the correct target class based on the file name extension.
         sFilePath = elt.getAttribute('path')
         if re.search(r'\.c(?:c|pp|xx)$', sFilePath):
            clsObjTarget = CxxObjectTarget
         else:
            raise Exception('unsupported source file type')
         # Create an object target with the file path as its source.
         tgtObj = clsObjTarget(mk, None, sFilePath)
         # Add the target as a dependency to this target.
         tgtObj.final_output_target = type(self)
         self.add_dependency(tgtObj)
         self.add_linker_input(tgtObj)
      elif elt.nodeName == 'dynlib':
         # Check if this makefile can build this dynamic library.
         sName = elt.getAttribute('name')
         # If the library was in the dictionary (i.e. it’s built by this makefile), assign it as a
         # dependency of self; else just add the library name (hence passing sName as 2nd argument
         # to mk.get_target_by_name()).
         oDynLib = mk.get_target_by_name(sName, sName)
         if oDynLib is not sName:
            self.add_dependency(oDynLib)
         self.add_linker_input(oDynLib)
      elif elt.nodeName == 'unittest':
         # A unit test must be built after the target it’s supposed to test.
         sName = elt.getAttribute('name')
         tgtUnitTest = mk.get_target_by_name(sName, None)
         if tgtUnitTest is None:
            raise Exception(
               'could not find definition of referenced unit test: {}'.format(sName)
            )
         tgtUnitTest.add_dependency(self)
      else:
         super().parse_makefile_child(elt, mk)



####################################################################################################
# DynLibTarget

class DynLibTarget(ExecutableTarget):
   """Dynamic library target. The output file will be placed in a lib/ directory relative to the
   output base directory.
   """

   def _generate_file_path(self, mk):
      """See ExecutableTarget._generate_file_path()."""

      # TODO: change 'lib' + '.so' from hardcoded to computed by a Platform class.
      return os.path.join(mk.output_dir, 'lib', 'lib' + self.name + '.so')


   def parse_makefile_child(self, elt, mk):
      """See ExecutableTarget.parse_makefile_child()."""

      super().parse_makefile_child(elt, mk)
      if elt.nodeName == 'unittest':
         sName = elt.getAttribute('name')
         tgtUnitTest = mk.get_target_by_name(sName)
         # If tgtUnitTest generates an executable, have it link to this library.
         if isinstance(tgtUnitTest, ExecutableTarget):
            tgtUnitTest.add_linker_input(self)



####################################################################################################
# UnitTestTarget

class UnitTestTarget(Target):
   """Generic unit test target."""


   def parse_makefile_child(self, elt, mk):
      """See Target.parse_makefile_child()."""

      if elt.nodeName == 'unittest':
         raise SyntaxError('<unittest> not allowed in <target type="unittest">')
      else:
         super().parse_makefile_child(elt, mk)



####################################################################################################
# ComparisonUnitTestTarget

class ComparisonUnitTestTarget(UnitTestTarget):
   """Unit test target that compares the output of a tool (e.g. C preprocessor) against a file with
   the expected output.
   """

   _m_sExpectedOutputFilePath = None


   def build(self, mk, iterBlockingJobs):
      """See Target.build(). In addition to building the unit test, it also schedules its execution.
      """

      tplDeps = None
      if iterBlockingJobs:
         if mk.verbosity >= mk.VERBOSITY_MEDIUM:
            sys.stdout.write('{}: re-running due to dependencies being rebuilt\n'.format(self.name))
      else:
         tplDeps = (self._m_sExpectedOutputFilePath, )
         if mk.file_metadata_changed(tplDeps):
            if mk.verbosity >= mk.VERBOSITY_MEDIUM:
               sys.stdout.write('{}: rebuilding due to changed inputs\n'.format(self.name))
         else:
            # No dependencies being rebuilt, source up-to-date: no need to rebuild, unless --force.
            if mk.force_build:
               if mk.verbosity >= mk.VERBOSITY_MEDIUM:
                  sys.stdout.write('{}: inputs unchanged, but rebuild forced\n'.format(self.name))
            else:
               if mk.verbosity >= mk.VERBOSITY_MEDIUM:
                  sys.stdout.write('{}: inputs unchanged\n'.format(self.name))
               return None

      # TODO: supply the path of the tool’s output.
      listArgs = ['cmp', '-s', '/tmp/test', self._m_sExpectedOutputFilePath]
      # TODO: move verbosity-related logic in a common place, leaving here only iterQuietCmd = …
      if mk.verbosity >= mk.VERBOSITY_LOW:
         iterQuietCmd = None
      else:
         iterQuietCmd = ('CMP', self.name)
      return make.ScheduledJob(mk, iterBlockingJobs, listArgs, iterQuietCmd, tplDeps)


   def parse_makefile_child(self, elt, mk):
      """See ExecutableTarget.parse_makefile_child()."""

      if elt.nodeName == 'source':
         # TODO: implement CxxPreprocessedTarget, then enable the following lines.
         pass
         # Pick the correct target class based on the file name extension.
#        sFilePath = elt.getAttribute('path')
#        if re.search(r'\.c(?:c|pp|xx)$', sFilePath):
#           clsObjTarget = CxxPreprocessedTarget
#        else:
#           raise Exception('unsupported source file type')
         # Create an object target with the file path as its source.
#        tgtObj = clsObjTarget(mk, None, sFilePath)
         # Add the target as a dependency to this target.
#        self.add_dependency(tgtObj)
      elif elt.nodeName == 'expected-output':
         self._m_sExpectedOutputFilePath = elt.getAttribute('path')
      else:
         super().parse_makefile_child(elt, mk)



####################################################################################################
# ExecutableUnitTestTarget

class ExecutableUnitTestTarget(ExecutableTarget, UnitTestTarget):
   """Executable unit test target. The output file will be placed in a bin/unittest/ directory
   relative to the output base directory.
   """

   # Path to the script file that will be invoked to execute the unit test.
   _m_sScriptFilePath = None


   def build(self, mk, iterBlockingJobs):
      """See ExecutableTarget.build(). In addition to building the unit test, it also schedules its
      execution.
      """

      sjBuild = super().build(mk, iterBlockingJobs)
      # If to build the unit test executable we scheduled any jobs, make sure that the metadata for
      # the jobs’ output is updated and that the unit test execution depends on the build job(s).
      if sjBuild:
         tplBlockingJobs = (sjBuild, )
         tplDeps = (self.file_path, )
      else:
         # No need to block the unit test job with iterBlockingJobs: if sjBuild is None,
         # iterBlockingJobs must be None as well, or else we would’ve scheduled jobs in
         # Target.build().
         assert(not iterBlockingJobs)
         tplBlockingJobs = None
         tplDeps = None

      if self._m_sScriptFilePath:
         tplArgs = (self._m_sScriptFilePath, self.file_path)
      else:
         tplArgs = (self.file_path, )
      # TODO: move verbosity-related logic in a common place, leaving here only iterQuietCmd = …
      if mk.verbosity >= mk.VERBOSITY_LOW:
         iterQuietCmd = None
      else:
         iterQuietCmd = ('TEST', self.name)
      return make.ScheduledJob(mk, tplBlockingJobs, tplArgs, iterQuietCmd, tplDeps)


   def _generate_file_path(self, mk):
      """See ExecutableTarget._generate_file_path()."""

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      return os.path.join(mk.output_dir, 'bin', 'unittest', '' + self.name + '')


   def parse_makefile_child(self, elt, mk):
      """See ExecutableTarget.parse_makefile_child() and UnitTestTarget.parse_makefile_child()."""

      if elt.nodeName == 'script':
         self._m_sScriptFilePath = elt.getAttribute('path')
         # TODO: support <script name="…"> to refer to a program built by the same makefile.
         # TODO: support more attributes, such as command-line args for the script.
      else:
         # TODO: call both ExecutableTarget and UnitTestTarget’s implementation.
         super().parse_makefile_child(elt, mk)

