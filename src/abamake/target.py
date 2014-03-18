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
      """Builds the output.

      make.job.Job return
         Scheduled job.
      """

      raise NotImplementedError('Target.build() must be overridden in ' + type(self).__name__)


   def build_complete(self, job, iRet, bIgnoreErrors):
      """Invoked by the JobController when the job executed to build this target completes, either
      in success or in failure.

      make.job.Job job
         Job instance, or None if the job was not started (due to e.g. “dry run” mode).
      int iRet
         Return value of the job’s execution. If job is None, this will be 0 (success).
      bool bIgnoreErrors
         If True, the job should be considered successfully completed even if iRet != 0.
      int return
         New return value. Used to report errors in the output of the build job.
      """

      if iRet == 0 or bIgnoreErrors:
         # Release all dependent targets.
         for tgt in self._m_listDependents:
            # These are weak references.
            tgt()._m_cBuildBlocks -= 1
         # If the job really completed successfully, update the target snapshot.
         if iRet == 0 and job is not None:
            self._m_mk().metadata.update_target_snapshot(self)
      return iRet


   def get_dependencies(self):
      """Iterates over the dependencies (make.target.Dependency instances) for this target.

      make.target.Dependency yield
         Dependency of this target.
      """

      for dep in self._m_listDependencies:
         yield dep


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

   def __init__(self, mk, sName, sSourceFilePath, tgtFinalOutput = None):
      """Constructor. See ProcessedSourceTarget.__init__()."""

      super().__init__(mk, sName, sSourceFilePath, tgtFinalOutput)

      self._m_sFilePath += make.tool.CxxCompiler.get_default_impl().object_suffix



####################################################################################################
# CxxObjectTarget

class CxxObjectTarget(ObjectTarget):
   """C++ intermediate object target."""

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
            raise Exception('unclassified linker input: {}'.format(dep.file_path))

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
            raise Exception('unsupported source file type')
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
               'could not find definition of referenced unit test: {}'.format(sName)
            )
         tgtUnitTest.add_dependency(self)
      else:
         return super().parse_makefile_child(elt)
      return True



####################################################################################################
# DynLibTarget

class DynLibTarget(ExecutableTarget):
   """Dynamic library target. The output file will be placed in a lib/ directory relative to the
   output base directory.
   """

   def __init__(self, mk, sName):
      """Constructor. See ExecutableTarget.__init__()."""

      super().__init__(mk, sName)

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      self._m_sFilePath = os.path.join(mk.output_dir, 'bin', '' + sName + '')


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

   # Filter (regex) to apply to the comparands.
   _m_reFilter = None


   def build(self):
      """See Target.build(). In addition to building the unit test, it also schedules its execution.
      """

      # Get a name to display for the two dependencies to compare.
      tgtGenerator = None
      listComparands = []
      for dep in self._m_listDependencies:
         if isinstance(dep, (ProcessedSourceTarget, ForeignDependency)):
            listComparands.append(dep.file_path)
         elif isinstance(dep, ExecutableUnitTestBuildTarget):
            # The output of this target will be one of the two comparands.
            tgtGenerator = dep
            listComparands.append('stdout({})'.format(dep.file_path))
      if len(listComparands) != 2:
         raise Exception('target {} can only compare two files/outputs'.format(self._m_sName))

      if tgtGenerator:
         listArgs = []
         listArgs.append(self._m_eutbt.file_path)
         # One of the comparands is a generator: schedule a job to execute it and capture its
         # output, which we’ll compare in build_complete().
         return make.job.ExternalPipedCommandJob(['TEST'] + listComparands, {
            'args': listArgs,
            'env' : tgtGenerator.get_exec_environ(),
         })
      else:
         # No generator to execute; we’ll compare the two files in build_complete().
         return make.job.NoopJob(
            0, ['CMP'] + listComparands,
            '[internal:compare] {} {}'.format(*listComparands)
         )


   def build_complete(self, job, iRet, bIgnoreErrors):
      """See UnitTestTarget.build_complete()."""

      if iRet != 0 and not bIgnoreErrors:
         return iRet

      # Extract and transform the contents of the two dependencies to compare.
      listComparands = []
      for dep in self._m_listDependencies:
         if isinstance(dep, (ProcessedSourceTarget, ForeignDependency)):
            with open(dep.file_path, 'r') as fileComparand:
               listComparands.append(self._transform_comparand(fileComparand.read()))
         elif isinstance(dep, ExecutableUnitTestBuildTarget):
            listComparands.append(self._transform_comparand(dep))

      # Compare the targets.
      if listComparands[0] == listComparands[1]:
         return 0
      else:
         return 1


   def is_build_needed(self):
      """See Target.is_build_needed()."""

      # TODO: make unit test execution incremental like everything else by storing something in the
      # metadata store.
      return True


   def parse_makefile_child(self, elt):
      """See UnitTestTarget.parse_makefile_child()."""

      mk = self._m_mk()
      if elt.nodeName == 'source':
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
         mk.add_target(tgtObj)
         self.add_dependency(tgtObj)
      elif elt.nodeName == 'expected-output':
         self.add_dependency(ForeignDependency(elt.getAttribute('path')))
      elif elt.nodeName == 'output-transform':
         sFilter = elt.getAttribute('filter')
         if sFilter:
            self._m_reFilter = re.compile('ABCMK_CMP_BEGIN.*?ABCMK_CMP_END', re.DOTALL)
         else:
            raise Exception('unsupported output transformation')
      else:
         return super().parse_makefile_child(elt)
      return True


   def _transform_comparand(self, s):
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
         s = '\n'.join(self._m_reFilter.findall(s))

      return s


####################################################################################################
# ExecutableUnitTestBuildTarget

class ExecutableUnitTestBuildTarget(ExecutableTarget):
   """Builds an executable unit test. The output file will be placed in a bin/unittest/ directory
   relative to the output base directory.

   One instance of this class is created for every instance of ExecutableUnitTestExecTarget.
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

      super().__init__(mk, sName)

      # Add the build target as a dependency.
      eutbt = ExecutableUnitTestBuildTarget(mk, sName)
      self._m_eutbt = eutbt
      mk.add_target(eutbt)
      # Note that we don’t invoke our overridden method.
      super().add_dependency(eutbt)


   def add_dependency(self, dep):
      """See UnitTestTarget.add_dependency(). Overridden to add the dependency to the build target
      instead of this one; this target should only depend on the unit test build target.
      """

      self._m_eutbt.add_dependency(dep)


   def build(self):
      """See UnitTestTarget.build()."""

      # Build the command line to invoke.
      if self._m_sScriptFilePath:
         listArgs = [self._m_sScriptFilePath]
      else:
         listArgs = []
      listArgs.append(self._m_eutbt.file_path)

      return make.job.ExternalCommandJob(('TEST', self._m_sName), {
         'args': listArgs,
         'env' : self._m_eutbt.get_exec_environ(),
      })


   def is_build_needed(self):
      """See Target.is_build_needed()."""

      # TODO: make unit test execution incremental like everything else by storing something in the
      # metadata store.
      return True


   def parse_makefile_child(self, elt):
      """See UnitTestTarget.parse_makefile_child()."""

      if elt.nodeName == 'script':
         self._m_sScriptFilePath = elt.getAttribute('path')
         # Note that we don’t invoke our overridden method.
         super().add_dependency(ForeignDependency(self._m_sScriptFilePath))
         # TODO: support <script name="…"> to refer to a program built by the same makefile.
         # TODO: support more attributes, such as command-line args for the script.
      elif not super().parse_makefile_child(elt):
         # Non-unit test-specific elements are probably for the build target to process.
         return self._m_eutbt.parse_makefile_child(elt)
      return True

