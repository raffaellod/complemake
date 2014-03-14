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
import weakref

import make
import make.job
import make.tool



####################################################################################################
# Target

class Target(object):
   """Abstract build target."""

   # See Target.dependencies.
   _m_setDeps = None
   # See Target.file_path.
   _m_sFilePath = None
   # Weak ref to the owning make instance.
   _m_mk = None
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
      self._m_mk = weakref.ref(mk)
      self._m_sFilePath = self._generate_file_path()
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


   def build(self, iterBlockingJobs):
      """Builds the output, using the facilities provided by the specified Make instance and
      returning the last job scheduled.

      iterable(Job*) iterBlockingJobs
         Jobs that should block the first one scheduled to build this target.
      Job return
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


   def _generate_file_path(self):
      """Generates and returns a file path for the target, based on other member varialbes set
      beforehand and the configuration of the provided Make instance. Called by Target.__init__().

      The default implementation doesn’t generate a file path because no output file is assumed.

      str return
         Target file path; same as Target.file_path.
      """

      # No output file.
      return None


   def _get_tool(self):
      """Instantiates and configures the tool to build the target. Not used by Target, but offers a
      model for derived classes to follow.

      Tool return
         Ready-to-use tool.
      """

      raise NotImplementedError('Target._get_tool() must be overridden')


   def is_build_needed(self):
      """Checks if the target should be (re)built or if it’s up-to-date.

      bool return
         True if a build is needed, or False otherwise.
      """

      # Now compare the metadata with what’s in the store.
      return self._m_mk()._m_mds.compare_target_snapshot(self)


   def _get_name(self):
      return self._m_sName

   name = property(_get_name, doc = """Name of the target.""")


   def parse_makefile_child(self, elt):
      """Validates and processes the specified child element of the target’s <target> element.

      xml.dom.Element elt
         Element to parse.
      bool return
         True if elt was recognized and parsed, or False if it was not expected.
      """

      # Default implementation: expect no child elements.
      return False


   @classmethod
   def select_subclass(cls, eltTarget):
      """Returns the Target-derived class that should be instantiated to model the specified
      <target> element.

      xml.dom.Element eltTarget
         Element to parse.
      type return
         Model class for eltTarget.
      """

      sType = eltTarget.nodeName
      if sType == 'unittest':
         # In order to know which UnitTestTarget-derived class to instantiate, we have to look-ahead
         # into the <target> element.
         cls = UnitTestTarget.select_subclass(eltTarget)
      elif sType == 'exe':
         cls = ExecutableTarget
      elif sType == 'dynlib':
         cls = DynLibTarget
      else:
         raise Exception('unsupported target type <{}>'.format(sType))
      return cls



####################################################################################################
# ProcessedSourceTarget

class ProcessedSourceTarget(Target):
   """Intermediate target generated by processing a source file. The output file will be placed in a
   int/ directory relative to the output base directory.
   """

   # Path to the file that this target’s output will be linked into.
   _m_sFinalOutputFilePath = None
   # Source from which the target is built.
   _m_sSourceFilePath = None


   def __init__(self, mk, sName, sSourceFilePath, sFinalOutputFilePath = None):
      """Constructor. See Target.__init__().

      Make mk
         Make instance.
      str sName
         See Target.name.
      str sSourceFilePath
         Source from which the target is built.
      str sFinalOutputFilePath
         Path to the file that this target’s output will be linked into. If omitted, no output-
         driven configuration will be applied to the Tool instance generating this output.
      """

      self._m_sSourceFilePath = sSourceFilePath
      self._m_sFinalOutputFilePath = sFinalOutputFilePath
      super().__init__(mk, sName)
      self.add_dependency(self._m_sSourceFilePath)
      # TODO: add other external dependencies.


   def build(self, iterBlockingJobs):
      """See Target.build()."""

      # Instantiate the appropriate tool, and have it schedule any applicable jobs.
      return self._get_tool().schedule_jobs(self._m_mk(), self, iterBlockingJobs)


   def _generate_file_path(self):
      """See Target._generate_file_path()."""

      return os.path.join(self._m_mk().output_dir, 'int', self._m_sSourceFilePath)



####################################################################################################
# CxxPreprocessedTarget

class CxxPreprocessedTarget(ProcessedSourceTarget):
   """Preprocessed C++ source target."""

   def _generate_file_path(self):
      """See ProcessedSourceTarget._generate_file_path()."""

      return super()._generate_file_path() + '.i'


   def _get_tool(self):
      """See ProcessedSourceTarget._get_tool(). Implemented using CxxObjectTarget._get_tool()."""

      cxx = CxxObjectTarget._get_tool(self)
      cxx.add_flags(make.tool.CxxCompiler.CFLAG_PREPROCESS_ONLY)
      return cxx



####################################################################################################
# ObjectTarget

class ObjectTarget(ProcessedSourceTarget):
   """Intermediate object target."""

   def _generate_file_path(self):
      """See ProcessedSourceTarget._generate_file_path()."""

      return super()._generate_file_path() + \
         make.tool.CxxCompiler.get_default_impl().object_suffix



####################################################################################################
# CxxObjectTarget

class CxxObjectTarget(ObjectTarget):
   """C++ intermediate object target."""

   def _get_tool(self):
      """See ObjectTarget._get_tool()."""

      cxx = make.tool.CxxCompiler.get_default_impl()()
      cxx.output_file_path = self._m_sFilePath
      cxx.add_input(self._m_sSourceFilePath)

      if self._m_sFinalOutputFilePath:
         # Let the final output configure the compiler.
         tgtFinalOutput = self._m_mk().get_target_by_file_path(self._m_sFinalOutputFilePath)
         tgtFinalOutput.configure_compiler(cxx)

      # TODO: add file-specific flags.
      return cxx



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


   def build(self, iterBlockingJobs):
      """See Target.build()."""

      mk = self._m_mk()
      lnk = self._get_tool()

      # Due to the different types of objects in _m_listLinkerInputs and the fact we want to iterate
      # over that list only once, combine building the list of files to be checked for changes with
      # collecting linker inputs.
      bOutputLibPathAdded = False
      # At this point all the dependencies are available, so add them as inputs.
      for oDep in self._m_listLinkerInputs or []:
         if isinstance(oDep, str):
            # Strings go directly to the linker’s command line, assuming that they are external
            # libraries to link to.
            lnk.add_input_lib(oDep)
         else:
            if isinstance(oDep, ObjectTarget):
               lnk.add_input(oDep.file_path)
            elif isinstance(oDep, DynLibTarget):
               lnk.add_input_lib(oDep.name)
               # Since we’re linking to a library built by this makefile, make sure to add the
               # output lib/ directory to the library search path.
               if not bOutputLibPathAdded:
                  lnk.add_lib_path(os.path.join(mk.output_dir, 'lib'))
                  bOutputLibPathAdded = True
            else:
               raise Exception('unclassified linker input: {}'.format(oDep.file_path))

      # TODO: add other external dependencies.

      return lnk.schedule_jobs(mk, self, iterBlockingJobs)


   def configure_compiler(self, tool):
      """Configures the specified Tool instance to generate code suitable for linking in this
      Target.

      Tool tool
         Tool (compiler) to configure.
      """

      # TODO: e.g. configure Link Time Code Generation to match this Target.
      pass


   def _generate_file_path(self):
      """See Target._generate_file_path()."""

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      return os.path.join(self._m_mk().output_dir, 'bin', '' + self._m_sName + '')


   def _get_tool(self):
      """See Target._get_tool()."""

      lnk = make.tool.Linker.get_default_impl()()
      lnk.output_file_path = self._m_sFilePath
      # TODO: add file-specific flags.
      return lnk


   def parse_makefile_child(self, elt):
      """See Target.parse_makefile_child()."""

      mk = self._m_mk()
      if elt.nodeName == 'source':
         # Pick the correct target class based on the file name extension.
         sFilePath = elt.getAttribute('path')
         if re.search(r'\.c(?:c|pp|xx)$', sFilePath):
            clsObjTarget = CxxObjectTarget
         else:
            raise Exception('unsupported source file type')
         # Create an object target with the file path as its source.
         tgtObj = clsObjTarget(mk, None, sFilePath, self._m_sFilePath)
         self.add_dependency(tgtObj)
         self.add_linker_input(tgtObj)
         return True
      if elt.nodeName == 'dynlib':
         # Check if this makefile can build this dynamic library.
         sName = elt.getAttribute('name')
         # If the library was in the dictionary (i.e. it’s built by this makefile), assign it as a
         # dependency of self; else just add the library name (hence passing sName as 2nd argument
         # to mk.get_target_by_name()).
         oDynLib = mk.get_target_by_name(sName, sName)
         if oDynLib is not sName:
            self.add_dependency(oDynLib)
         self.add_linker_input(oDynLib)
         return True
      if elt.nodeName == 'unittest':
         # A unit test must be built after the target it’s supposed to test.
         sName = elt.getAttribute('name')
         tgtUnitTest = mk.get_target_by_name(sName, None)
         if tgtUnitTest is None:
            raise Exception(
               'could not find definition of referenced unit test: {}'.format(sName)
            )
         tgtUnitTest.add_dependency(self)
         return True
      return super().parse_makefile_child(elt)



####################################################################################################
# DynLibTarget

class DynLibTarget(ExecutableTarget):
   """Dynamic library target. The output file will be placed in a lib/ directory relative to the
   output base directory.
   """

   def configure_compiler(self, tool):
      """See ExecutableTarget.configure_compiler()."""

      if isinstance(tool, make.tool.CxxCompiler):
         # Make sure we’re generating code suitable for a dynamic library.
         tool.add_flags(make.tool.CxxCompiler.CFLAG_DYNLIB)
         # Allow building both a dynamic library and its clients using the same header file, by
         # changing “import” to “export” when this macro is defined.
         tool.add_macro('ABCMK_BUILD_{}'.format(re.sub(r'[^_0-9A-Z]+', '_', self._m_sName.upper())))


   def _generate_file_path(self):
      """See ExecutableTarget._generate_file_path()."""

      # TODO: change 'lib' + '.so' from hardcoded to computed by a Platform class.
      return os.path.join(self._m_mk().output_dir, 'lib', 'lib' + self._m_sName + '.so')


   def _get_tool(self):
      """See ExecutableTarget._get_tool(). Overridden to tell the linker to generate a dynamic
      library.
      """

      lnk = super()._get_tool()
      lnk.add_flags(make.tool.Linker.LDFLAG_DYNLIB)
      return lnk


   def parse_makefile_child(self, elt):
      """See ExecutableTarget.parse_makefile_child()."""

      mk = self._m_mk()
      # This implementation does not allow more element types than the base class’ version.
      if not super().parse_makefile_child(elt):
         return False
      # Apply additional logic on the recognized element.
      if elt.nodeName == 'unittest':
         sName = elt.getAttribute('name')
         tgtUnitTest = mk.get_target_by_name(sName)
         # If tgtUnitTest generates an executable, have it link to this library.
         if isinstance(tgtUnitTest, ExecutableTarget):
            tgtUnitTest.add_linker_input(self)
      return True



####################################################################################################
# UnitTestTarget

class UnitTestTarget(Target):
   """Generic unit test target."""

   def _is_build_needed(self):
      """See Target.is_build_needed()."""

      return True


   def parse_makefile_child(self, elt):
      """See Target.parse_makefile_child()."""

      if elt.nodeName == 'unittest':
         raise SyntaxError('<unittest> not allowed in <target type="unittest">')
      return super().parse_makefile_child(elt)


   @classmethod
   def select_subclass(cls, eltTarget):
      """Returns the UnitTestTarget-derived class that should be instantiated to model the specified
      <target> element. Logically similar to Target.select_subclass(), but not an override.

      xml.dom.Element eltTarget
         Element to parse.
      type return
         Model class for eltTarget.
      """

      cls = None
      sName = eltTarget.getAttribute('name')
      for ndChild in eltTarget.childNodes:
         if ndChild.nodeType != ndChild.ELEMENT_NODE:
            continue
         # Determine what class should be instantiated according to the current node (ndChild).
         clsCurr = None
         if ndChild.nodeName == 'source':
            if ndChild.hasAttribute('tool'):
               # A <target> with a <source> with tool="…" override is not going to generate an
               # executable.
               clsCurr = ComparisonUnitTestTarget
            else:
               # A <target> with <source> (default tool) will generate an executable.
               clsCurr = ExecutableUnitTestTarget
         elif ndChild.nodeName == 'dynlib' or ndChild.nodeName == 'script':
            # Linking to dynamic libraries or using execution scripts is a prerogative of executable
            # unit tests only.
            clsCurr = ExecutableUnitTestTarget
         if clsCurr:
            # If we already picked cls, make sure it was the same as clsCurr.
            if cls and cls is not clsCurr:
               raise SyntaxError(
                  'unit test target “{}” specifies conflicting execution modes'.format(sName)
               )
            cls = clsCurr
      if cls is None:
         raise SyntaxError('invalid empty unit test target “{}” element'.format(sName))
      return cls


####################################################################################################
# ComparisonUnitTestTarget

class ComparisonUnitTestTarget(UnitTestTarget):
   """Unit test target that compares the output of a tool (e.g. C preprocessor) against a file with
   the expected output.
   """

   # Path to the file containing the expected command output.
   _m_sExpectedOutputFilePath = None


   def build(self, iterBlockingJobs):
      """See Target.build(). In addition to building the unit test, it also schedules its execution.
      """

      # Find the dependency target that generates the output we want to compare.
      for tgt in self._m_setDeps or []:
         if isinstance(tgt, ProcessedSourceTarget):
            tgtToCompare = tgt
            break

      listArgs = ['cmp', '-s', tgtToCompare.file_path, self._m_sExpectedOutputFilePath]
      return make.job.ExternalCommandJob(
         self._m_mk(), self, iterBlockingJobs, ('CMP', self._m_sName), {'args': listArgs,}
      )


   def parse_makefile_child(self, elt):
      """See UnitTestTarget.parse_makefile_child()."""

      mk = self._m_mk()
      if elt.nodeName == 'source':
         # Check if we already found a <source> child element (dependency).
         for tgt in self._m_setDeps or []:
            if isinstance(tgt, ProcessedSourceTarget):
               raise Exception(
                  ('a tool output comparison like “{}” unit test can only have a single <source> ' +
                     'element').format(self._m_sName)
               )
         # Pick the correct target class based on the file name extension and the tool to use.
         sFilePath = elt.getAttribute('path')
         sTool = elt.getAttribute('tool')
         if re.search(r'\.c(?:c|pp|xx)$', sFilePath):
            if sTool == 'preproc':
               clsObjTarget = CxxPreprocessedTarget
            else:
               raise Exception('unknown tool “{}” for source file “{}”'.format(sTool, sFilePath))
         else:
            raise Exception('unsupported source file type')
         # Create an object target with the file path as its source.
         tgtObj = clsObjTarget(mk, None, sFilePath)
         # Add the target as a dependency to this target.
         self.add_dependency(tgtObj)
         return True
      if elt.nodeName == 'expected-output':
         self._m_sExpectedOutputFilePath = elt.getAttribute('path')
         self.add_dependency(self._m_sExpectedOutputFilePath)
         return True
      return super().parse_makefile_child(elt)



####################################################################################################
# ExecutableUnitTestTarget

class ExecutableUnitTestTarget(ExecutableTarget, UnitTestTarget):
   """Executable unit test target. The output file will be placed in a bin/unittest/ directory
   relative to the output base directory.
   """

   # Path to the script file that will be invoked to execute the unit test.
   _m_sScriptFilePath = None


   def build(self, iterBlockingJobs):
      """See ExecutableTarget.build(). In addition to building the unit test, it also schedules its
      execution.
      """

      mk = self._m_mk()
      jobBuild = super().build(iterBlockingJobs)
      # If to build the unit test executable we scheduled any jobs, make sure that the metadata for
      # the jobs’ output is updated and that the unit test execution depends on the build job(s).
      if jobBuild:
         tplBlockingJobs = (jobBuild, )
         tplDeps = (self._m_sFilePath, )
      else:
         # No need to block the unit test job with iterBlockingJobs: if jobBuild is None,
         # iterBlockingJobs must be None as well, or else we would’ve scheduled jobs in
         # Target.build().
         assert not iterBlockingJobs, \
            'ExecutableTarget.build() returned no jobs, no dependencies should have scheduled jobs'
         tplBlockingJobs = None
         tplDeps = None

      # Build the command line to invoke.
      if self._m_sScriptFilePath:
         tplArgs = (self._m_sScriptFilePath, self._m_sFilePath)
      else:
         tplArgs = (self._m_sFilePath, )

      # If this target is linked to a library built by this same makefile, make sure we add
      # output_dir/lib to the library path.
      assert self._m_listLinkerInputs is not None, \
         'a UnitTestTarget must have at least one dependency (the Target it tests)'
      dictEnv = None
      for oDep in self._m_listLinkerInputs:
         if isinstance(oDep, DynLibTarget):
            # TODO: move this env tweaking to a Platform class.
            dictEnv = os.environ.copy()
            sLibPath = dictEnv.get('LD_LIBRARY_PATH', '')
            if sLibPath:
               sLibPath = ':' + sLibPath
            sLibPath += os.path.join(mk.output_dir, 'lib')
            dictEnv['LD_LIBRARY_PATH'] = sLibPath
            break

      return make.job.ExternalCommandJob(mk, self, tplBlockingJobs, ('TEST', self._m_sName), {
         'args': tplArgs,
         'env' : dictEnv,
      })


   def _generate_file_path(self):
      """See ExecutableTarget._generate_file_path()."""

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      return os.path.join(self._m_mk().output_dir, 'bin', 'unittest', '' + self._m_sName + '')


   def parse_makefile_child(self, elt):
      """See ExecutableTarget.parse_makefile_child() and UnitTestTarget.parse_makefile_child()."""

      if elt.nodeName == 'script':
         self._m_sScriptFilePath = elt.getAttribute('path')
         self.add_dependency(self._m_sScriptFilePath)
         # TODO: support <script name="…"> to refer to a program built by the same makefile.
         # TODO: support more attributes, such as command-line args for the script.
         return True
      if ExecutableTarget.parse_makefile_child(self, elt):
         return True
      return UnitTestTarget.parse_makefile_child(self, elt)

