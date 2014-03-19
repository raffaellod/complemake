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
import weakref

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
# OutputRerefenceDependency

class OutputRerefenceDependency(ForeignDependency):
   """File used as a reference to validate expected outputs."""

   pass



####################################################################################################
# UnitTestExecScriptDependency

class UnitTestExecScriptDependency(ForeignDependency):
   """Executable that runs a unit test according to a “script”. Used to mimic interation with a
   shell that ABC Make does not implement.
   """

   pass



####################################################################################################
# Target

class Target(Dependency):
   """Abstract build target."""

   # Unfinished dependency builds that block building this target.
   _m_cBuildBlocks = None
   # Dependencies (make.target.Dependency instances) for this target. Cannot be a set, because in
   # some cases (e.g. linker inputs) we need to keep the order.
   # TODO: use an ordered set when one becomes available in “stock” Python?
   _m_listDependencies = None
   # Targets (make.target.Target instances) dependent on this target.
   _m_listDependents = None
   # Weak ref to the owning make instance.
   _m_mk = None
   # Mapping between Target subclasses and XML element names.
   _smc_dictSubclassElementNames = {}
   # See Target.name.
   _m_sName = None


   def __init__(self, mk, sName = None):
      """Constructor. It initializes the file_path to None, because it’s assumed that a derived
      class will know better.

      make.Make mk
         Make instance.
      str sName
         See Target.name.
      """

      super().__init__(None)

      self._m_cBuildBlocks = 0
      self._m_listDependencies = []
      self._m_listDependents = []
      self._m_mk = weakref.ref(mk)
      self._m_sName = sName


   def __str__(self):
      return '{} ({})'.format(self._m_sName or self._m_sFilePath, type(self).__name__)


   class xml_element(object):
      """Decorator to teach Target.select_subclass() the association of the decorated class with an
      XML element name.

      str sNodeName
         Name of the element to associate with the decorated class.
      """

      def __init__(self, sNodeName):
         self._m_sNodeName = sNodeName

      def __call__(self, clsDerived):
         Target._smc_dictSubclassElementNames[self._m_sNodeName] = clsDerived
         return clsDerived


   def add_dependency(self, dep):
      """Adds a target dependency.

      make.target.Dependency dep
         Dependency.
      """

      if dep not in self._m_listDependencies:
         self._m_listDependencies.append(dep)
         # If the dependency is a target built by the same makefile, add a reverse dependency link
         # (dependent) and increment the block count for this target.
         if isinstance(dep, Target):
            # Use weak references to avoid creating reference loops.
            dep._m_listDependents.append(weakref.ref(self))
            self._m_cBuildBlocks += 1


   def build(self):
      """Instantiates a job that will build the output.

      make.job.Job return
         Scheduled job, or None if there’s nothing to be built. Some minor processing may still
         occur synchronously to the main thread in Target.build_complete().
      """

      raise NotImplementedError('Target.build() must be overridden in ' + type(self).__name__)


   def build_complete(self, job, iRet):
      """Invoked by the JobController when the job executed to build this target completes, either
      in success or in failure.

      make.job.Job job
         Job instance, or None if the job was not started (due to e.g. “dry run” mode).
      int iRet
         Return value of the job’s execution. If job is None, this will be 0 (success).
      int return
         New return value. Used to report errors in the output of the build job.
      """

      if iRet == 0:
         # Release all dependent targets.
         for tgt in self._m_listDependents:
            # These are weak references.
            tgt()._m_cBuildBlocks -= 1
         # If a job was really run (not None), update the target snapshot.
         if job:
            self._m_mk().metadata.update_target_snapshot(self)
      return iRet


   def get_dependencies(self):
      """Iterates over the dependencies (make.target.Dependency instances) for this target.

      make.target.Dependency yield
         Dependency of this target.
      """

      for dep in self._m_listDependencies:
         yield dep


   def dump_dependencies(self, sIndent = ''):
      """TODO: comment."""

      for dep in self._m_listDependencies:
         print(sIndent + str(dep))
         if isinstance(dep, Target):
            dep.dump_dependencies(sIndent + '  ')


   def dump_dependents(self, sIndent = ''):
      """TODO: comment."""

      for wdep in self._m_listDependents:
         dep = wdep()
         print(sIndent + str(dep))
         if isinstance(dep, Target):
            dep.dump_dependents(sIndent + '  ')


   def get_dependents(self):
      """Iterates over the targets (make.target.Target instances) dependent on this target.

      make.target.Target yield
         Dependent on this target.
      """

      for tgt in self._m_listDependents:
         # These are weak references.
         yield tgt()


   def _get_tool(self):
      """Instantiates and configures the tool to build the target. Not used by Target, but offers a
      model for derived classes to follow.

      make.tool.Tool return
         Ready-to-use tool.
      """

      raise NotImplementedError('Target._get_tool() must be overridden in ' + type(self).__name__)


   def is_build_blocked(self):
      """Returns True if the build of this target is blocked, i.e. it requires one ore more
      dependencies to be built first.

      bool return
         True if this target can’t be build yet, or False if it can.
      """

      return self._m_cBuildBlocks > 0


   def is_build_needed(self):
      """Checks if the target should be (re)built or if it’s up-to-date.

      bool return
         True if a build is needed, or False otherwise.
      """

      # Now compare the current metadata with what’s in the store.
      return self._m_mk().metadata.has_target_snapshot_changed(self)


   def _get_name(self):
      return self._m_sName

   name = property(_get_name, doc = """Name of the target.""")


   def parse_makefile_child(self, elt):
      """Validates and processes the specified child element of the target’s XML element.

      xml.dom.Element elt
         Element to parse.
      bool return
         True if elt was recognized and parsed, or False if it was not expected.
      """

      # Default implementation: expect no child elements.
      return False


   def remove_dependency(self, dep):
      """Removes a target dependency.

      make.target.Dependency dep
         Dependency.
      """

      self._m_listDependencies.remove(dep)
      # If the dependency is a target built by the same makefile, remove the reverse dependency link
      # (dependent) and decrement the block count for this target.
      if isinstance(dep, Target):
         # Can’t just use dep._m_listDependents.remove(self) because the list contains weak
         # references, so self would not be found.
         for i, depRev in enumerate(dep._m_listDependents):
            if depRev() is self:
               del dep._m_listDependents[i]
         self._m_cBuildBlocks -= 1


   @classmethod
   def select_subclass(cls, eltTarget):
      """Returns the Target-derived class that should be instantiated to model the specified XML
      element.

      xml.dom.Element eltTarget
         Element to parse.
      type return
         Model class for eltTarget.
      """

      return cls._smc_dictSubclassElementNames.get(eltTarget.nodeName)



####################################################################################################
# ProcessedSourceTarget

class ProcessedSourceTarget(Target):
   """Intermediate target generated by processing a source file. The output file will be placed in a
   int/ directory relative to the output base directory.
   """

   # Target that that this target’s output will be linked into.
   _m_tgtFinalOutput = None
   # Source from which the target is built.
   _m_sSourceFilePath = None


   def __init__(self, mk, sName, sSourceFilePath, tgtFinalOutput = None):
      """Constructor. See Target.__init__().

      make.Make mk
         Make instance.
      str sName
         See Target.name.
      str sSourceFilePath
         Source from which the target is built.
      make.target.Target tgtFinalOutput
         Target that this target’s output will be linked into. If omitted, no output-driven
         configuration will be applied to the Tool instance generating this output.
      """

      super().__init__(mk, sName)

      self._m_sSourceFilePath = sSourceFilePath
      self._m_sFilePath = os.path.join(mk.output_dir, 'int', sSourceFilePath)
      if tgtFinalOutput:
         self._m_tgtFinalOutput = weakref.ref(tgtFinalOutput)
      else:
         self._m_tgtFinalOutput = None
      self.add_dependency(ForeignSourceDependency(self._m_sSourceFilePath))
      # TODO: add other external dependencies.


   def build(self):
      """See Target.build()."""

      # Instantiate the appropriate tool, and have it schedule any applicable jobs.
      return self._get_tool().create_job(self._m_mk(), self)



####################################################################################################
# CxxPreprocessedTarget

class CxxPreprocessedTarget(ProcessedSourceTarget):
   """Preprocessed C++ source target."""

   def __init__(self, mk, sName, sSourceFilePath, tgtFinalOutput = None):
      """Constructor. See ProcessedSourceTarget.__init__()."""

      super().__init__(mk, sName, sSourceFilePath, tgtFinalOutput)

      self._m_sFilePath += '.i'


   def _get_tool(self):
      """See ProcessedSourceTarget._get_tool(). Implemented using CxxObjectTarget._get_tool()."""

      cxx = CxxObjectTarget._get_tool(self)
      cxx.add_flags(make.tool.CxxCompiler.CFLAG_PREPROCESS_ONLY)
      return cxx



####################################################################################################
# ObjectTarget

class ObjectTarget(ProcessedSourceTarget):
   """Intermediate object target."""

   pass



####################################################################################################
# CxxObjectTarget

class CxxObjectTarget(ObjectTarget):
   """C++ intermediate object target."""

   def __init__(self, mk, sName, sSourceFilePath, tgtFinalOutput = None):
      """Constructor. See ObjectTarget.__init__()."""

      super().__init__(mk, sName, sSourceFilePath, tgtFinalOutput)

      self._m_sFilePath += make.tool.CxxCompiler.get_default_impl().object_suffix


   def _get_tool(self):
      """See ObjectTarget._get_tool()."""

      cxx = make.tool.CxxCompiler.get_default_impl()()
      cxx.output_file_path = self._m_sFilePath
      cxx.add_input(self._m_sSourceFilePath)

      if self._m_tgtFinalOutput:
         # Let the final output configure the compiler.
         self._m_tgtFinalOutput().configure_compiler(cxx)

      # TODO: add file-specific flags.
      return cxx



####################################################################################################
# ExecutableTarget

@Target.xml_element('exe')
class ExecutableTarget(Target):
   """Executable program target. The output file will be placed in a bin/ directory relative to the
   output base directory.
   """

   def __init__(self, mk, sName):
      """Constructor. See Target.__init__()."""

      super().__init__(mk, sName)

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      self._m_sFilePath = os.path.join(mk.output_dir, 'bin', '' + sName + '')


   def build(self):
      """See Target.build()."""

      mk = self._m_mk()
      lnk = self._get_tool()

      # Scan this target’s dependencies for linker inputs.
      bOutputLibPathAdded = False
      # At this point all the dependencies are available, so add them as inputs.
      for dep in self._m_listDependencies:
         if isinstance(dep, ForeignLibDependency):
            # Strings go directly to the linker’s command line, assuming that they are external
            # libraries to link to.
            lnk.add_input_lib(dep)
         elif isinstance(dep, ObjectTarget):
            lnk.add_input(dep.file_path)
         elif isinstance(dep, DynLibTarget):
            lnk.add_input_lib(dep.name)
            # Since we’re linking to a library built by this makefile, make sure to add the
            # output lib/ directory to the library search path.
            if not bOutputLibPathAdded:
               lnk.add_lib_path(os.path.join(mk.output_dir, 'lib'))
               bOutputLibPathAdded = True
         else:
            raise Exception('{}: unclassified linker input: {}'.format(self, dep))

      # TODO: add other external dependencies.

      return lnk.create_job(mk, self)


   def configure_compiler(self, tool):
      """Configures the specified Tool instance to generate code suitable for linking in this
      Target.

      make.tool.Tool tool
         Tool (compiler) to configure.
      """

      # TODO: e.g. configure Link Time Code Generation to match this Target.
      pass


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
            raise Exception('{}: unsupported source file type: {}'.format(self, sFilePath))
         # Create an object target with the file path as its source.
         tgtObj = clsObjTarget(mk, None, sFilePath, self)
         mk.add_target(tgtObj)
         self.add_dependency(tgtObj)
      elif elt.nodeName == 'dynlib':
         # Check if this makefile can build this dynamic library.
         sName = elt.getAttribute('name')
         # If the library is a known target (i.e. it’s built by this makefile), assign it as a
         # dependency of self; else just add the library name.
         dep = mk.get_target_by_name(sName, None)
         if dep is None:
            dep = ForeignLibDependency(sName)
         self.add_dependency(dep)
      elif elt.nodeName == 'unittest':
         # A unit test must be built after the target it’s supposed to test.
         sName = elt.getAttribute('name')
         tgtUnitTest = mk.get_target_by_name(sName, None)
         if tgtUnitTest is None:
            raise Exception(
               '{}: could not find definition of referenced unit test: {}'.format(self, sName)
            )
         tgtUnitTest.add_dependency(self)
      else:
         return super().parse_makefile_child(elt)
      return True



####################################################################################################
# DynLibTarget

@Target.xml_element('dynlib')
class DynLibTarget(ExecutableTarget):
   """Dynamic library target. The output file will be placed in a lib/ directory relative to the
   output base directory.
   """

   def __init__(self, mk, sName):
      """Constructor. See ExecutableTarget.__init__()."""

      super().__init__(mk, sName)

      # TODO: change 'lib' + '.so' from hardcoded to computed by a Platform class.
      self._m_sFilePath = os.path.join(mk.output_dir, 'lib', 'lib' + sName + '.so')


   def configure_compiler(self, tool):
      """See ExecutableTarget.configure_compiler()."""

      if isinstance(tool, make.tool.CxxCompiler):
         # Make sure we’re generating code suitable for a dynamic library.
         tool.add_flags(make.tool.CxxCompiler.CFLAG_DYNLIB)
         # Allow building both a dynamic library and its clients using the same header file, by
         # changing “import” to “export” when this macro is defined.
         tool.add_macro('ABCMK_BUILD_{}'.format(re.sub(r'[^_0-9A-Z]+', '_', self._m_sName.upper())))


   def _get_tool(self):
      """See ExecutableTarget._get_tool(). Overridden to tell the linker to generate a dynamic
      library.
      """

      lnk = super()._get_tool()
      lnk.add_flags(make.tool.Linker.LDFLAG_DYNLIB)
      return lnk



####################################################################################################
# UnitTestTarget

@Target.xml_element('unittest')
class UnitTestTarget(Target):
   """Target that executes a unit test."""

   # True if comparison operands should be treated as amorphous BLOBS, or False if they should be
   # treated as strings.
   _m_bBinaryCompare = None
   # Filter (regex) to apply to the comparison operands.
   _m_reFilter = None
   # UnitTestBuildTarget instance that builds the unit test executable invoked as part of this
   # target.
   _m_tgtUnitTestBuild = None


   def add_dependency(self, dep):
      """See Target.add_dependency(). Overridden to reroute dependencies to the build target, if
      any.
      """

      if self._m_tgtUnitTestBuild:
         # Forward the dependency to the build target.
         self._m_tgtUnitTestBuild.add_dependency(dep)
      else:
         # Our dependency.
         super().add_dependency(dep)


   def build(self):
      """See Target.build(). It executes the unit test built by the build target, if any."""

      # Collect dependencies according to their type.
      depExecScript = None
      cStaticComparands = 0
      for dep in self._m_listDependencies:
         if isinstance(dep, (ProcessedSourceTarget, OutputRerefenceDependency)):
            cStaticComparands += 1
         elif isinstance(dep, UnitTestBuildTarget):
            # The output of tgtUnitTestBuild will be one of the two comparison operands.
            assert dep is self._m_tgtUnitTestBuild
         elif isinstance(dep, UnitTestExecScriptDependency):
            depExecScript = dep

      if self._m_tgtUnitTestBuild:
         # One of the dependencies is a unit test to execute: prepare its command line.
         if depExecScript:
            # We also have a “script” to drive the unit test.
            listArgs = [depExecScript.file_path]
            # TODO: support more arguments, once they’re recognized by parse_makefile_child().
         else:
            listArgs = []
         listArgs.append(self._m_tgtUnitTestBuild.file_path)

         if cStaticComparands > 1:
            raise Exception(
               '{}: can’t compare the unit test output against more than one file'.format(self)
            )
         if cStaticComparands:
            # We’ll need to compare the output of the unit test, so execute it with an output-
            # capturing job; we’ll then compare its output in build_complete().
            clsJob = make.job.ExternalPipedCommandJob
         else:
            # No need to capture the output, just use an execution job.
            clsJob = make.job.ExternalCommandJob
         return clsJob(('TEST', self._m_sName), {
            'args'              : listArgs,
            'env'               : self._m_tgtUnitTestBuild.get_exec_environ(),
            'universal_newlines': not self._m_bBinaryCompare,
         })
      else:
         if cStaticComparands != 2:
            raise Exception('{}: need exactly two files/outputs to compare'.format(self))
         # No unit test to execute; we’ll compare the two pre-built files in build_complete().
         return None


   def build_complete(self, job, iRet):
      """See Target.build_complete()."""

      iRet = super().build_complete(job, iRet)
      if iRet == 0:
         # Extract and transform the contents of the two dependencies to compare, and generate a
         # display name for them.
         listCmpNames = []
         listCmpOperands = []
         if self._m_bBinaryCompare:
            sFileMode = 'b'
         else:
            sFileMode = ''
         for dep in self._m_listDependencies:
            if isinstance(dep, (ProcessedSourceTarget, OutputRerefenceDependency)):
               # Add as comparison operand the contents of this dependency file.
               listCmpNames.append(dep.file_path)
               with open(dep.file_path, 'r' + sFileMode) as fileComparand:
                  listCmpOperands.append(self._transform_comparison_operand(fileComparand.read()))

         if listCmpOperands:
            if self._m_tgtUnitTestBuild:
               # We have a build target and at least another comparison operand, so the job that
               # just completed must be of type ExternalPipedCommandJob, and we’ll add its output as
               # comparison operand.
               sUnitTestStdOutFilePath = self._m_tgtUnitTestBuild.file_path + '.stdout'
               listCmpNames.append(sUnitTestStdOutFilePath)
               listCmpOperands.append(self._transform_comparison_operand(job.get_stdout()))

            assert len(listCmpOperands) == 2, \
               'UnitTestTarget.build() did not correctly validate the count of comparison operands'

            log = self._m_mk().log
            if self._m_bBinaryCompare:
               sCmpV = 'internal:binary-compare'
               sCmpQ = 'CMPBIN'
            else:
               sCmpV = 'internal:text-compare'
               sCmpQ = 'CMPTXT'
            if log.verbosity >= log.LOW:
               log(log.LOW, '[{}] {} {}\n', sCmpV, *listCmpNames)
            else:
               log(log.QUIET, '{:^8} {} <=> {}\n', sCmpQ, *listCmpNames)

            # Compare the targets.
            if listCmpOperands[0] == listCmpOperands[1]:
               iRet = 0
            else:
               iRet = 1
               # The comparison failed; if we have a build target, save its output to a file to help
               # diagnosing the problem.
               if self._m_tgtUnitTestBuild:
                  with open(sUnitTestStdOutFilePath, 'w' + sFileMode) as fileStdOut:
                     fileStdOut.write(job.get_stdout())
      return iRet


   def is_build_needed(self):
      """See Target.is_build_needed()."""

      # TODO: decide whether to make unit test execution incremental like everything else; support
      # is already there via MetadataStore.
      return True


   def parse_makefile_child(self, elt):
      """See Target.parse_makefile_child()."""

      mk = self._m_mk()
      if elt.nodeName == 'unittest':
         raise SyntaxError('<unittest> not allowed in <unittest>')
      elif elt.nodeName == 'source' and elt.hasAttribute('tool'):
         # Due to specifying a non-default tool, this <source> does not generate an object file or
         # an executable.
         sFilePath = elt.getAttribute('path')
         sTool = elt.getAttribute('tool')
         # Pick the correct target class based on the file name extension and the tool to use.
         if re.search(r'\.c(?:c|pp|xx)$', sFilePath):
            if sTool == 'preproc':
               clsObjTarget = CxxPreprocessedTarget
            else:
               raise Exception(
                  '{}: unknown tool “{}” for source file: {}'.format(self, sTool, sFilePath)
               )
         else:
            raise Exception('{}: unsupported source file type: {}'.format(self, sFilePath))
         # Create an object target with the file path as its source.
         tgtObj = clsObjTarget(mk, None, sFilePath)
         mk.add_target(tgtObj)
         # Note that we don’t invoke our add_dependency() override.
         super().add_dependency(tgtObj)
      elif elt.nodeName == 'expected-output':
         dep = OutputRerefenceDependency(elt.getAttribute('path'))
         # Note that we don’t invoke our add_dependency() override.
         super().add_dependency(dep)
         sMode = elt.getAttribute('mode')
         if sMode:
            if sMode == 'binary':
               bBinaryCompare = True
            elif sMode == 'text':
               bBinaryCompare = False
            else:
               raise SyntaxError('{}: invalid comparison mode for {}: {}'.format(self, dep, sMode))
            if self._m_bBinaryCompare is None:
               self._m_bBinaryCompare = bBinaryCompare
            elif self._m_bBinaryCompare != bBinaryCompare:
               raise Exception(
                  '{}: conflicting comparison modes specified for different operands'.format(self)
               )
      elif elt.nodeName == 'output-transform':
         sFilter = elt.getAttribute('filter')
         if sFilter:
            self._m_reFilter = re.compile('ABCMK_CMP_BEGIN.*?ABCMK_CMP_END', re.DOTALL)
         else:
            raise Exception('{}: unsupported output transformation'.format(self))
      elif elt.nodeName == 'script':
         dep = UnitTestExecScriptDependency(elt.getAttribute('path'))
         # TODO: support <script name="…"> to refer to a program built by the same makefile.
         # TODO: support more attributes, such as command-line args for the script.
         # Note that we don’t invoke our add_dependency() override.
         super().add_dependency(dep)
      elif not super().parse_makefile_child(elt):
         # This child element may indicate that this target requires a separate build target to
         # create the unit test executable.
         #
         # If we still don’t have an associated build target, instantiate one and transfer to it all
         # the dependencies of any type not added by this method override, then allow it to process
         # this child element.
         # If the build target doesn’t know what to do with it, we’ll forward its False return
         # value, which means that ABC Make will terminate and the erroneous creation of a build
         # target won’t have any ill effect.
         # If the build target can handle it, then self will have correctly changed into a build +
         # run pair with its build target.
         tgtUnitTestBuild = self._m_tgtUnitTestBuild
         if not tgtUnitTestBuild:
            # Create the build target.
            tgtUnitTestBuild = UnitTestBuildTarget(mk, self._m_sName)
            mk.add_target(tgtUnitTestBuild)

            # Transfer any dependencies we don’t handle.
            i = 0
            listDeps = self._m_listDependencies
            while i < len(listDeps):
               dep = listDeps[i]
               if isinstance(dep, (
                  CxxPreprocessedTarget, OutputRerefenceDependency, UnitTestExecScriptDependency,
               )):
                  # Keep this dependency and move on to the next one.
                  i += 1
               else:
                  # Transfer this dependency to the build target.
                  tgtUnitTestBuild.add_dependency(dep)
                  self.remove_dependency(dep)

            # Add the build target as a dependency.
            # Note that we don’t invoke our add_dependency() override.
            super().add_dependency(tgtUnitTestBuild)
            self._m_tgtUnitTestBuild = tgtUnitTestBuild

         # Let the build target decide whether this child element is valid or not.
         return tgtUnitTestBuild.parse_makefile_child(elt)
      return True


   def _transform_comparison_operand(self, s):
      """Transforms a string according to any <output-transform> rules specified in the makefile,
      and returns the result.

      str s
         String to tranform.
      str return
         Processed string.
      """

      # Apply the only supported filter.
      # TODO: use an interface/specialization to apply transformations.
      if self._m_reFilter:
         if self._m_bBinaryCompare:
            oJoiner = b'\n'
         else:
            oJoiner = '\n'
         s = oJoiner.join(self._m_reFilter.findall(s))

      return s


####################################################################################################
# UnitTestBuildTarget

class UnitTestBuildTarget(ExecutableTarget):
   """Builds an executable unit test. The output file will be placed in a bin/unittest/ directory
   relative to the output base directory.
   """

   def __init__(self, mk, sName = None):
      """See ExecutableTarget.__init__()."""

      # sName is only used to generate _m_sFilePath; don’t pass it to ExecutableTarget.__init__().
      super().__init__(mk, '')

      # Clear the name.
      self._m_sName = None
      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      self._m_sFilePath = os.path.join(mk.output_dir, 'bin', 'unittest', '' + sName + '')


   def get_exec_environ(self):
      """Generates an os.environ-like dictionary containing any variables necessary to execute the
      unit test.

      dict(str: str) return
         Modified environment, or None if no environment changes are needed to run the unit test.
      """

      # If the build target is linked to a library built by this same makefile, make sure we add
      # output_dir/lib to the library path.
      dictEnv = None
      if any(isinstance(dep, DynLibTarget) for dep in self._m_listDependencies):
         # TODO: move this env tweaking to a Platform class.
         dictEnv = os.environ.copy()
         sLibPath = dictEnv.get('LD_LIBRARY_PATH', '')
         if sLibPath:
            sLibPath = ':' + sLibPath
         sLibPath += os.path.join(self._m_mk().output_dir, 'lib')
         dictEnv['LD_LIBRARY_PATH'] = sLibPath
      return dictEnv

