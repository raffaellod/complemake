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
# Dependency

class Dependency(object):
   """Represents an abstract dependency of which only the file path is known."""

   # See Dependency.file_path.
   _m_sFilePath = None


   def __init__(self, sFilePath):
      """Constructor.

      str sFilePath
         See Dependency.file_path.
      """

      self._m_sFilePath = sFilePath


   def __str__(self):
      return '{} ({})'.format(self._m_sFilePath, type(self).__name__)


   def _get_file_path(self):
      return self._m_sFilePath

   file_path = property(_get_file_path, doc = """Dependency file path.""")



####################################################################################################
# ForeignDependency

class ForeignDependency(Dependency):
   """Abstract foreign dependency. Used by Target and its subclasses to represent files not built by
   ABC Make.
   """

   pass



####################################################################################################
# ForeignSourceDependency

class ForeignSourceDependency(ForeignDependency):
   """Foreign source file dependency."""

   pass



####################################################################################################
# ForeignLibDependency

class ForeignLibDependency(ForeignDependency):
   """Foreign library dependency."""

   pass



####################################################################################################
# Target

class Target(Dependency):
   """Abstract build target."""

   # Dependencies (make.target.Dependency instances) for this target.
   _m_setDeps = None
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

      self._m_setDeps = set()
      self._m_sName = sName
      self._m_mk = weakref.ref(mk)
      super().__init__(self._generate_file_path())
      # Add self to any applicable targets lists.
      mk._add_target(self)


   def __str__(self):
      return '{} ({})'.format(self._m_sName or self._m_sFilePath, type(self).__name__)


   def add_dependency(self, dep):
      """Adds a target dependency.

      make.target.Dependency dep
         Dependency.
      """

      self._m_setDeps.add(dep)


   def build(self, iterBlockingJobs):
      """Builds the output, using the facilities provided by the specified Make instance and
      returning the job scheduled.

      iterable(Job*) iterBlockingJobs
         Jobs that should block the one scheduled to build this target.
      Job return
         Scheduled job.
      """

      raise NotImplementedError('Target.build() must be overridden in ' + type(self).__name__)


   def get_dependencies(self):
      """Iterates over the dependencies (make.target.Dependency instances) for this target.

      make.target.Dependency yield
         Dependency of this target.
      """

      for dep in self._m_setDeps:
         yield dep


   def _get_file_path(self):
      return self._m_sFilePath

   file_path = property(_get_file_path, doc = """Target file path.""")


   def _generate_file_path(self):
      """Generates and returns a file path for the target, based on other member varialbes set
      beforehand and the configuration of the provided Make instance. Called by Target.__init__().

      The default implementation doesn’t generate a file path because no output file is assumed.

      str return
         Target file path; same as Dependency.file_path.
      """

      # No output file.
      return None


   def _get_tool(self):
      """Instantiates and configures the tool to build the target. Not used by Target, but offers a
      model for derived classes to follow.

      Tool return
         Ready-to-use tool.
      """

      raise NotImplementedError('Target._get_tool() must be overridden in ' + type(self).__name__)


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
      self.add_dependency(ForeignSourceDependency(self._m_sSourceFilePath))
      # TODO: add other external dependencies.


   def build(self, iterBlockingJobs):
      """See Target.build()."""

      # Instantiate the appropriate tool, and have it schedule any applicable jobs.
      return self._get_tool().schedule_job(self._m_mk(), self, iterBlockingJobs)


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


   def add_dependency(self, dep):
      """See Target.add_dependency(). If the dependency is something we should link to, also add it
      as a linker input.
      """

      super().add_dependency(dep)
      if isinstance(dep, (ObjectTarget, DynLibTarget, ForeignLibDependency)):
         if self._m_listLinkerInputs is None:
            self._m_listLinkerInputs = []
         self._m_listLinkerInputs.append(dep)


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
         if isinstance(oDep, ForeignLibDependency):
            # Strings go directly to the linker’s command line, assuming that they are external
            # libraries to link to.
            lnk.add_input_lib(oDep)
         elif isinstance(oDep, ObjectTarget):
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

      return lnk.schedule_job(mk, self, iterBlockingJobs)


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
         return True
      if elt.nodeName == 'dynlib':
         # Check if this makefile can build this dynamic library.
         sName = elt.getAttribute('name')
         # If the library is a known target (i.e. it’s built by this makefile), assign it as a
         # dependency of self; else just add the library name.
         dep = mk.get_target_by_name(sName, None)
         if dep is None:
            dep = ForeignLibDependency(sName)
         self.add_dependency(dep)
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



####################################################################################################
# UnitTestTarget

class UnitTestTarget(Target):
   """Generic unit test target."""

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
               clsCurr = ExecutableUnitTestExecTarget
         elif ndChild.nodeName == 'dynlib' or ndChild.nodeName == 'script':
            # Linking to dynamic libraries or using execution scripts is a prerogative of executable
            # unit tests only.
            clsCurr = ExecutableUnitTestExecTarget
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
      for tgt in self._m_setDeps:
         if isinstance(tgt, ProcessedSourceTarget):
            tgtToCompare = tgt
            break

      listArgs = ['cmp', '-s', tgtToCompare.file_path, self._m_sExpectedOutputFilePath]
      return make.job.ExternalCommandJob(
         self._m_mk(), self, iterBlockingJobs, ('CMP', self._m_sName), {'args': listArgs,}
      )


   def is_build_needed(self):
      """See Target.is_build_needed()."""

      # TODO: make unit test execution incremental like everything else by storing something in the
      # metadata store.
      return True


   def parse_makefile_child(self, elt):
      """See UnitTestTarget.parse_makefile_child()."""

      mk = self._m_mk()
      if elt.nodeName == 'source':
         # Check if we already found a <source> child element (dependency).
         for tgt in self._m_setDeps:
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
         self.add_dependency(ForeignDependency(self._m_sExpectedOutputFilePath))
         return True
      return super().parse_makefile_child(elt)



####################################################################################################
# ExecutableUnitTestBuildTarget

class ExecutableUnitTestBuildTarget(ExecutableTarget):
   """Builds an executable unit test. The output file will be placed in a bin/unittest/ directory
   relative to the output base directory.

   One instance of this class is created for every instance of ExecutableUnitTestExecTarget.
   """

   def __init__(self, mk, sName = None):
      """See ExecutableTarget.__init__()."""

      super().__init__(mk, sName)
      # Remove self from mk’s named targets, to let the execution target use sName instead.
      # TODO: don’t poke Make’s privates.
      del mk._m_dictNamedTargets[sName]
      # Give up the name to the execution target.
      self._m_sName = None


   def get_exec_environ(self):
      """Generates an os.environ-like dictionary containing any variables necessary to execute the
      unit test.

      dict(str: str) return
         Modified environment, or None if no environment changes are needed to run the unit test.
      """

      # If the build target is linked to a library built by this same makefile, make sure we add
      # output_dir/lib to the library path.
      assert self._m_listLinkerInputs is not None, \
         'a ExecutableUnitTestBuildTarget must have at least one dependency (the Target it tests)'
      dictEnv = None
      for oDep in self._m_listLinkerInputs:
         if isinstance(oDep, DynLibTarget):
            # TODO: move this env tweaking to a Platform class.
            dictEnv = os.environ.copy()
            sLibPath = dictEnv.get('LD_LIBRARY_PATH', '')
            if sLibPath:
               sLibPath = ':' + sLibPath
            sLibPath += os.path.join(self._m_mk().output_dir, 'lib')
            dictEnv['LD_LIBRARY_PATH'] = sLibPath
            break
      return dictEnv


   def _generate_file_path(self):
      """See ExecutableTarget._generate_file_path()."""

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      return os.path.join(self._m_mk().output_dir, 'bin', 'unittest', '' + self._m_sName + '')



####################################################################################################
# ExecutableUnitTestExecTarget

class ExecutableUnitTestExecTarget(UnitTestTarget):
   """Executes an executable unit test.

   Instantiating this class generates two targets: the first one is a ExecutableUnitTestBuildTarget,
   and takes care of building the unit test’s executable; the second one is of this type, and is
   only needed to run the unit test. The target name is taken by the latter; the former is only
   assigned the path to the file it generates.
   """

   # ExecutableUnitTestBuildTarget instance that builds the unit test executable invoked by building
   # this object.
   _m_eutbt = None
   # Path to the script file that will be invoked to execute the unit test.
   _m_sScriptFilePath = None


   def __init__(self, mk, sName = None):
      """See UnitTestTarget.__init__(). Also instantiates the related ExecutableUnitTestBuildTarget.
      """

      self._m_eutbt = ExecutableUnitTestBuildTarget(mk, sName)
      super().__init__(mk, sName)
      # Add the build target as a dependency. Note that we don’t invoke our overridden method.
      super().add_dependency(self._m_eutbt)


   def add_dependency(self, dep):
      """See UnitTestTarget.add_dependency(). Overridden to add the dependency to the build target
      instead of this one; this target should only depend on the unit test build target.
      """

      self._m_eutbt.add_dependency(dep)


   def build(self, iterBlockingJobs):
      """See Target.build()."""

      # Build the command line to invoke.
      if self._m_sScriptFilePath:
         listArgs = [self._m_sScriptFilePath]
      else:
         listArgs = []
      listArgs.append(self._m_eutbt.file_path)

      return make.job.ExternalCommandJob(
         self._m_mk(), self, iterBlockingJobs, ('TEST', self._m_sName), {
            'args': listArgs,
            'env' : self._m_eutbt.get_exec_environ(),
         }
      )


   def is_build_needed(self):
      """See Target.is_build_needed()."""

      # TODO: make unit test execution incremental like everything else by storing something in the
      # metadata store.
      return True


   def parse_makefile_child(self, elt):
      """See ExecutableTarget.parse_makefile_child() and UnitTestTarget.parse_makefile_child()."""

      if elt.nodeName == 'script':
         self._m_sScriptFilePath = elt.getAttribute('path')
         # Note that we don’t invoke our overridden method.
         super().add_dependency(ForeignDependency(self._m_sScriptFilePath))
         # TODO: support <script name="…"> to refer to a program built by the same makefile.
         # TODO: support more attributes, such as command-line args for the script.
         return True
      if super().parse_makefile_child(elt):
         return True
      # Non-unit test-specific elements are probably for the build target to process.
      return self._m_eutbt.parse_makefile_child(elt)

