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

"""Classes implementing different types of build target, each aware of how to build itself."""

import locale
import os
import re
import sys
import weakref

import comk
import comk.dependency
import comk.job
import comk.make
import comk.makefileparser
import comk.tool
import yaml

if sys.hexversion >= 0x03000000:
   basestring = str


####################################################################################################

class Target(comk.dependency.Dependency):
   """Abstract build target."""

   # Count of targets whose build is blocking this target’s build.
   _m_cBlockingDependencies = 0
   # Weak references to targets whose build is blocked by this target’s build.
   _m_setBlockedDependents = None
   # If True, the target is being built.
   _m_bBuilding = False
   # Dependencies (comk.dependency.Dependency instances) for this target. Cannot be a set, because
   # in some cases (e.g. linker inputs) we need to keep it in order.
   # TODO: use an ordered set when one becomes available in “stock” Python?
   _m_listDependencies = None
   # Weak ref to the owning make instance.
   _m_mk = None
   # If True, the target has been built or at least verified to be up-to-date.
   _m_bUpToDate = False

   def __init__(self, *iterArgs):
      """Constructor. Automatically registers the target with the specified Make instance.

      comk.makefileparser.MakefileParser mp
         Parser instantiating the object.
      dict(object: object) dictYaml
         Parsed YAML object to be used to construct the new instance.

      - OR -

      comk.make.Make mk
         Make instance.
      """

      comk.dependency.Dependency.__init__(self)

      if isinstance(iterArgs[0], comk.makefileparser.MakefileParser):
         mp, dictYaml = iterArgs
         mk = mp.mk
      else:
         dictYaml = None
         mk, = iterArgs
      self._m_setBlockedDependents = set()
      self._m_cBlockingDependencies = 0
      self._m_bBuilding = False
      self._m_listDependencies = []
      self._m_mk = weakref.ref(mk)
      self._m_bUpToDate = False
      mk.add_target(self)

      if dictYaml:
         oSources = dictYaml.get('sources')
         if oSources:
            if not isinstance(oSources, list):
               mp.raise_parsing_error('attribute “sources” must be a sequence')
            for i, o in enumerate(oSources):
               if isinstance(o, basestring):
                  sFilePath = o
                  sTool = None
               elif isinstance(o, dict):
                  sFilePath = o.get('path')
                  if sFilePath is None:
                     mp.raise_parsing_error((
                        'a mapping in “sources” must specify a “path” attribute, but element ' +
                        '[{}] does not'
                     ).format(i))
                  sTool = o.get('tool')
               else:
                  mp.raise_parsing_error((
                     'elements of the “sources” attribute must be strings or mappings with a ' +
                     '“path” attribute, but element [{}] does not'
                  ).format(i))
               # Pick the correct target class based on the file name extension and the tool to use.
               if re.search(r'\.c(?:c|pp|xx)$', sFilePath):
                  if sTool is None:
                     cls = CxxObjectTarget
                  elif sTool == 'preproc':
                     cls = CxxPreprocessedTarget
                  else:
                     mp.raise_parsing_error(
                        'unknown tool “{}” for source file “{}”'.format(sTool, sFilePath)
                     )
               else:
                  mp.raise_parsing_error('unsupported source file type “{}”'.format(sFilePath))

               # Create the target, passing it the file path as its source.
               tgt = cls(mk, sFilePath, self)
               # TODO: validate the type of tgt?
               self.add_dependency(tgt)

   def add_dependency(self, dep):
      """Adds a target dependency.

      comk.dependency.Dependency dep
         Dependency.
      """

      if dep not in self._m_listDependencies:
         self._m_listDependencies.append(dep)

   def _build_tool_run(self):
      """Enqueues any jobs necessary to unconditionally build the target."""

      mk = self._m_mk()
      log = mk.log
      log(log.HIGH, 'build[{}]: queuing build tool job(s)', self)
      # Instantiate the appropriate tool, and have it schedule any applicable jobs.
      job = self._get_tool().create_jobs(mk, self, self._on_build_tool_run_complete)
      mk.job_runner.enqueue(job)

   def _build_tool_should_run(self):
      """Checks if the target build tool needs to be run to freshen the target.

      bool return
         True if the build tool needs to be run, or False if the target is up-to-date.
      """

      mk = self._m_mk()
      return mk.force_build or mk.metadata.has_target_snapshot_changed(self)

   def _on_build_started(self):
      """Invoked after the target’s build is started."""

      log = self._m_mk().log
      # Regenerate any out-of-date dependency targets.
      listDependencyTargets = tuple(filter(
         lambda dep: isinstance(dep, Target), self._m_listDependencies
      ))
      log(log.HIGH, 'build[{}]: updating {} dependency targets', self, len(listDependencyTargets))
      if listDependencyTargets:
         self._m_cBlockingDependencies = len(listDependencyTargets)
         for tgtDependency in listDependencyTargets:
            tgtDependency.start_build(self)
      else:
         # No dependencies are blocking, continue with the build.
         self._on_dependencies_updated()

   def _on_build_tool_complete(self):
      """Invoked after the tool stage of the build has completed, regardless of whether a tool was
      really run.
      """

      log = self._m_mk().log
      log(log.HIGH, 'build[{}]: skipping metadata update', self)
      self._on_metadata_updated()

   def _on_build_tool_run_complete(self):
      """Invoked after the job that builds the target has completed its execution."""

      mk = self._m_mk()
      log = mk.log
      log(log.HIGH, 'build[{}]: updating metadata', self)
      mk.metadata.update_target_snapshot(self, mk.dry_run)
      self._on_build_tool_complete()

   def _on_dependencies_updated(self):
      """Invoked after all the target’s dependencies have been updated."""

      mk = self._m_mk()
      log = mk.log
      log(log.HIGH, 'build[{}]: all dependencies up-to-date', self)
      # Now that the dependencies are up-to-date, check if any were rebuilt, causing this Target to
      # need to be rebuilt as well.
      if self._build_tool_should_run():
         self._build_tool_run()
      else:
         # There’s nothing to do, so just continue to the next stage.
         self._on_build_tool_complete()

   def _on_dependency_updated(self):
      """Invoked when the build of a dependency completes successfully."""

      log = self._m_mk().log
      self._m_cBlockingDependencies -= 1
      log(
         log.HIGH, 'build[{}]: 1 dependency updated, {} remaining',
         self, self._m_cBlockingDependencies
      )
      if self._m_cBlockingDependencies == 0:
         # All dependencies up-to-date, continue with the build.
         self._on_dependencies_updated()

   def _on_metadata_updated(self):
      """Invoked after the metadata for the target has been updated."""

      log = self._m_mk().log
      log(log.HIGH, 'build[{}]: unblocking dependents', self)
      # The target is built at this point, so its dependents can be unblocked.
      self._m_bUpToDate = True
      self._m_bBuilding = False
      for tgtDependent in self._m_setBlockedDependents:
         tgtDependent()._on_dependency_updated()
      self._m_setBlockedDependents = None
      log(log.HIGH, 'build[{}]: end', self)

   def dump_dependencies(self, sIndent = ''):
      """TODO: comment."""

      for dep in self._m_listDependencies:
         print(sIndent + str(dep))
         if isinstance(dep, Target):
            dep.dump_dependencies(sIndent + '  ')

   def get_dependencies(self, bTargetsOnly = False):
      """Iterates over the dependencies (comk.dependency.Dependency instances) for this target.

      bool bTargetsOnly
         If True, only comk.target.Target instances will be returned; if False, no filtering will
         occur.
      comk.dependency.Dependency yield
         Dependency of this target.
      """

      for dep in self._m_listDependencies:
         if not bTargetsOnly or isinstance(dep, Target):
            yield dep

   def _get_tool(self):
      """Instantiates and configures the tool to build the target. Not used by Target, but offers a
      model for derived classes to follow.

      comk.tool.Tool return
         Ready-to-use tool.
      """

      raise NotImplementedError('Target._get_tool() must be overridden in ' + type(self).__name__)

   def start_build(self, tgtDependent = None):
      """Begins building the target. Builds are asynchronous; use comk.job.Runner.run() to allow
      them to complete.

      comk.target.Target tgtDependent
         Target that will need to be unblocked when the build of this target completes. If self is
         already up-to-date, tgtDependent will be unblocked immediately.
      """

      log = self._m_mk().log
      if self._m_bUpToDate:
         log(log.HIGH, 'build[{}]: skipping', self)
         # Nothing to do, but make sure we unblock the dependent target that called this method.
         if tgtDependent:
            tgtDependent._on_dependency_updated()
      else:
         log(log.HIGH, 'build[{}]: begin', self)
         if tgtDependent:
            # Add the dependent target to those we’ll unblock when this build completes.
            self._m_setBlockedDependents.add(weakref.ref(tgtDependent))
         if not self._m_bBuilding:
            self._m_bBuilding = True
            self._on_build_started()

   def validate(self):
      """Checks that the target doesn’t have invalid settings that were undetectable by the
      constructor.
      """

      pass

####################################################################################################

class NamedTargetMixIn(comk.dependency.NamedDependencyMixIn):
   """Mixin that provides a name for a Target subclass."""

   def __init__(self, mk, sName):
      """Constructor. Automatically registers the name => target association with the specified Make
      instance.

      comk.make.Make mk
         Make instance.
      str sName
         Dependency name.
      """

      if not sName:
         mp.raise_parsing_error('missing or empty “name” non-optional attribute')

      comk.dependency.NamedDependencyMixIn.__init__(self, sName)

      mk.add_named_target(self, sName)

####################################################################################################

class FileTarget(comk.dependency.FileDependencyMixIn, Target):
   """Target that generates a file."""

   def __init__(self, *iterArgs):
      """Constructor. Automatically registers the path => target association with the specified Make
      instance.

      comk.makefileparser.MakefileParser mp
         Parser instantiating the object.
      object dictYaml
         Parsed YAML object to be used to construct the new instance.

      - OR -

      comk.make.Make mk
         Make instance.
      str sFilePath
         Target file path.
      """

      if isinstance(iterArgs[0], comk.makefileparser.MakefileParser):
         mp, dictYaml = iterArgs

         Target.__init__(self, mp, dictYaml)

         mk = mp.mk
         sFilePath = dictYaml.get('path')
         if not isinstance(sFilePath, basestring):
            mp.raise_parsing_error('missing or invalid “path” attribute')
      else:
         mk, sFilePath = iterArgs

         Target.__init__(self, mk)

      comk.dependency.FileDependencyMixIn.__init__(self, sFilePath)

      mk.add_file_target(self, self._m_sFilePath)

   def _get_build_log_path(self):
      return os.path.join(self._m_mk().output_dir, 'log', self._m_sFilePath + '.log')

   build_log_path = property(_get_build_log_path, doc = """
      Path to the file where the build log for this target (i.e. the captured stderr of the process
      that builds it) is saved.
   """)

####################################################################################################

class ProcessedSourceTarget(FileTarget):
   """Intermediate target generated by processing a source file. The output file will be placed in
   the “int” directory relative to the output base directory.
   """

   # Target that that this target’s output will be linked into.
   _m_tgtFinalOutput = None
   # Source from which the target is built.
   _m_sSourceFilePath = None

   def __init__(self, mk, sSourceFilePath, sSuffix, tgtFinalOutput):
      """Constructor.

      comk.make.Make mk
         Make instance.
      str sSourceFilePath
         Source from which the target is built.
      str sSuffix
         Suffix that is added to sSourceFilePath to generate the target’s file path.
      comk.target.Target tgtFinalOutput
         Target that this target’s output will be linked into.
      """

      FileTarget.__init__(self, mk, os.path.join(mk.output_dir, 'int', sSourceFilePath + sSuffix))

      self._m_sSourceFilePath = sSourceFilePath
      self._m_tgtFinalOutput = weakref.ref(tgtFinalOutput)
      self.add_dependency(comk.dependency.ForeignSourceDependency(self._m_sSourceFilePath))
      # TODO: add other external dependencies.

####################################################################################################

class CxxPreprocessedTarget(ProcessedSourceTarget):
   """Preprocessed C++ source target."""

   def __init__(self, mk, sSourceFilePath, tgtFinalOutput):
      """Constructor.

      comk.make.Make mk
         Make instance.
      str sSourceFilePath
         Source from which the target is built.
      comk.target.Target tgtFinalOutput
         Target that this target’s output will be linked into.
      """

      ProcessedSourceTarget.__init__(self, mk, sSourceFilePath, '.i', tgtFinalOutput)

   def _get_tool(self):
      """See ProcessedSourceTarget._get_tool()."""

      # TODO: refactor code shared with CxxObjectTarget._get_tool().

      mk = self._m_mk()

      cxx = mk.target_platform.get_tool(comk.tool.CxxCompiler)
      cxx.output_file_path = self._m_sFilePath
      cxx.add_input(self._m_sSourceFilePath)

      if self._m_tgtFinalOutput:
         tgtFinalOutput = self._m_tgtFinalOutput()
         if isinstance(tgtFinalOutput, BinaryTarget):
            # Let the final output configure the compiler.
            tgtFinalOutput.configure_compiler(cxx)

      # Let the platform configure the compiler.
      mk.target_platform.configure_tool(cxx)

      # TODO: add file-specific flags.
      cxx.add_flags(comk.tool.CxxCompiler.CFLAG_PREPROCESS_ONLY)
      return cxx

   def _on_build_started(self):
      """See ProcessedSourceTarget._on_build_started(). Overridden to start a job to collect
      implicit dependencies (those expressed in the source file via #include statements).
      """

      # TODO: refactor code shared with CxxObjectTarget._on_build_started().

      log = self._m_mk().log
      log(log.HIGH, 'build[{}]: gathering dependencies', self)
      # TODO: gather implicit dependencies by preprocessing the source, passing
      # self._on_implicit_dependencies_gathered as the on_complete handler, instead of doing this:
      self._on_implicit_dependencies_gathered()

   def _on_implicit_dependencies_gathered(self):
      """Invoked after the target’s implicit dependencies have been gathered."""

      # TODO: refactor code shared with CxxObjectTarget._on_implicit_dependencies_gathered().

      log = self._m_mk().log
      log(log.HIGH, 'build[{}]: dependencies gathered', self)
      # Resume with the ProcessedSourceTarget build step we hijacked.
      ProcessedSourceTarget._on_build_started(self)

####################################################################################################

class ObjectTarget(ProcessedSourceTarget):
   """Intermediate object target."""

   pass

####################################################################################################

class CxxObjectTarget(ObjectTarget):
   """C++ intermediate object target."""

   def __init__(self, mk, sSourceFilePath, tgtFinalOutput):
      """Constructor.

      comk.make.Make mk
         Make instance.
      str sSourceFilePath
         Source from which the target is built.
      comk.target.Target tgtFinalOutput
         Target that this target’s output will be linked into.
      """

      ObjectTarget.__init__(
         self, mk, sSourceFilePath,
         mk.target_platform.get_tool(comk.tool.CxxCompiler).object_suffix, tgtFinalOutput
      )

   def _get_tool(self):
      """See ObjectTarget._get_tool()."""

      # TODO: refactor code shared with CxxPreprocessedTarget._get_tool().

      mk = self._m_mk()

      cxx = mk.target_platform.get_tool(comk.tool.CxxCompiler)
      cxx.output_file_path = self._m_sFilePath
      cxx.add_input(self._m_sSourceFilePath)

      if False:
         cxx.add_macro('COMPLEMAKE_USING_VALGRIND')

      if self._m_tgtFinalOutput:
         tgtFinalOutput = self._m_tgtFinalOutput()
         if isinstance(tgtFinalOutput, BinaryTarget):
            # Let the final output configure the compiler.
            tgtFinalOutput.configure_compiler(cxx)

      # Let the platform configure the compiler.
      mk.target_platform.configure_tool(cxx)

      # TODO: add file-specific flags.
      return cxx

   def _on_build_started(self):
      """See ObjectTarget._on_build_started(). Overridden to start a job to collect implicit
      dependencies (those expressed in the source file via #include statements).
      """

      # TODO: refactor code shared with CxxPreprocessedTarget._on_build_started().

      log = self._m_mk().log
      log(log.HIGH, 'build[{}]: gathering dependencies', self)
      # TODO: gather implicit dependencies by preprocessing the source, passing
      # self._on_implicit_dependencies_gathered as the on_complete handler, instead of doing this:
      self._on_implicit_dependencies_gathered()

   def _on_implicit_dependencies_gathered(self):
      """Invoked after the target’s implicit dependencies have been gathered."""

      # TODO: refactor code shared with CxxPreprocessedTarget._on_implicit_dependencies_gathered().

      log = self._m_mk().log
      log(log.HIGH, 'build[{}]: dependencies gathered', self)
      # Resume with the ObjectTarget build step we hijacked.
      ObjectTarget._on_build_started(self)

####################################################################################################

class BinaryTarget(FileTarget):
   """Base class for binary (executable) target classes."""

   def __init__(self, mp, dictYaml):
      """Constructor. Automatically registers the path => target association with the specified Make
      instance.

      comk.makefileparser.MakefileParser mp
         Parser instantiating the object.
      object dictYaml
         Parsed YAML object to be used to construct the new instance.
      """

      FileTarget.__init__(self, mp, dictYaml)

      oLibs = dictYaml.get('libraries')
      if oLibs:
         if not isinstance(oLibs, list):
            mp.raise_parsing_error('attribute “libraries” must be a sequence')
         for i, o in enumerate(oLibs):
            # For now, only strings representing a library name are supported.
            if isinstance(o, basestring):
               sName = o
            else:
               mp.raise_parsing_error((
                  'elements of the “libraries” attribute must be strings, but element [{}] is not'
               ).format(i))
            # The makefile probably hasn’t yet been completely parsed, so we can’t check if the
            # library is a known target (i.e. it’s built by this makefile). For now, just record the
            # dependency as one that will need to be resolved later, in validate().
            dep = comk.dependency.UndeterminedLibDependency(sName)
            self.add_dependency(dep)

      oTests = dictYaml.get('tests')
      if oTests:
         if not isinstance(oTests, list):
            mp.raise_parsing_error('attribute “tests” must be a sequence')
         for i, o in enumerate(oTests):
            if not isinstance(o, (ExecutableTestTarget, ToolTestTarget)):
               mp.raise_parsing_error((
                  'elements of the “tests” attribute must be of type !complemake/target/exetest ' +
                  'or !complemake/target/tooltest, but element [{}] is not'
               ).format(i))
            # A test must be built after the target it’s supposed to test.
            o.add_dependency(self)

   def configure_compiler(self, tool):
      """Configures the specified Tool instance to generate code suitable for linking in this
      target.

      comk.tool.Tool tool
         Tool (compiler) to configure.
      """

      # TODO: e.g. configure Link Time Code Generation to match this target.
      pass

   def _get_tool(self):
      """See FileTarget._get_tool()."""

      mk = self._m_mk()

      lnk = mk.target_platform.get_tool(comk.tool.Linker)
      lnk.output_file_path = self._m_sFilePath
      # TODO: add file-specific flags.

      # Let the platform configure the linker.
      mk.target_platform.configure_tool(lnk)

      # Scan this target’s dependencies for linker inputs.
      bOutputLibPathAdded = False
      # At this point all the dependencies are available, so add them as inputs.
      for dep in self._m_listDependencies:
         if isinstance(dep, comk.dependency.ForeignLibDependency):
            # Strings go directly to the linker’s command line, assuming that they are external
            # libraries to link to.
            lnk.add_input_lib(dep.name)
         elif isinstance(dep, ObjectTarget):
            lnk.add_input(dep.file_path)
         elif isinstance(dep, DynLibTarget):
            lnk.add_input_lib(dep.name)
            # Since we’re linking to a library built by this makefile, make sure to add the output
            # “lib” directory to the library search path.
            if not bOutputLibPathAdded:
               lnk.add_lib_path(os.path.join(mk.output_dir, 'lib'))
               bOutputLibPathAdded = True

      # TODO: add other external dependencies.

      return lnk

   def validate(self):
      """See FileTarget.validate()."""

      mk = self._m_mk()
      # Replace any UndeterminedLibDependency instances with either known Target instances or with
      # ForeignLibDependency instances.
      for i, dep in enumerate(self._m_listDependencies):
         if isinstance(dep, comk.dependency.UndeterminedLibDependency):
            tgt = mk.get_named_target(dep.name, None)
            if tgt:
               dep = tgt
            else:
               dep = comk.dependency.ForeignLibDependency(dep.name)
            self._m_listDependencies[i] = dep
         # TODO: validate the type of all other dependencies.

      FileTarget.validate(self)

####################################################################################################

class NamedBinaryTarget(NamedTargetMixIn, BinaryTarget):
   """Base for named binary (executable) target classes."""

   def __init__(self, mp, dictYaml):
      """Constructor.

      comk.makefileparser.MakefileParser mp
         Parser instantiating the object.
      object dictYaml
         Parsed YAML object to be used to construct the new instance.
      """

      NamedTargetMixIn.__init__(self, mp.mk, dictYaml.get('name', ''))
      BinaryTarget.__init__(self, mp, dictYaml)

####################################################################################################

@comk.makefileparser.MakefileParser.local_tag('complemake/target/exe', yaml.Kind.MAPPING)
class ExecutableTarget(NamedBinaryTarget):
   """Executable program target. The output file will be placed in the “bin” directory relative to
   the output base directory.
   """

   def __init__(self, mp, dictYaml):
      """Constructor.

      comk.makefileparser.MakefileParser mp
         Parser instantiating the object.
      object dictYaml
         Parsed YAML object to be used to construct the new instance.
      """

      # Default the “path” attribute before constructing the base class.
      mk = mp.mk
      # dictYaml['name'] may be missing, but NamedTargetMixIn will catch that.
      dictYaml.setdefault('path', os.path.join(
         mk.output_dir, 'bin', mk.target_platform.exe_file_name(dictYaml.get('name', ''))
      ))

      NamedBinaryTarget.__init__(self, mp, dictYaml)

####################################################################################################

@comk.makefileparser.MakefileParser.local_tag('complemake/target/dynlib', yaml.Kind.MAPPING)
class DynLibTarget(NamedBinaryTarget):
   """Dynamic library target. The output file will be placed in the “lib” directory relative to the
   output base directory.
   """

   def __init__(self, mp, dictYaml):
      """Constructor.

      comk.makefileparser.MakefileParser mp
         Parser instantiating the object.
      object dictYaml
         Parsed YAML object to be used to construct the new instance.
      """

      # Default the “path” attribute before constructing the base class.
      mk = mp.mk
      # dictYaml['name'] may be missing, but NamedTargetMixIn will catch that.
      dictYaml.setdefault('path', os.path.join(
         mk.output_dir, 'lib', mk.target_platform.dynlib_file_name(dictYaml.get('name', ''))
      ))

      NamedBinaryTarget.__init__(self, mp, dictYaml)

   def configure_compiler(self, tool):
      """See NamedBinaryTarget.configure_compiler()."""

      NamedBinaryTarget.configure_compiler(self, tool)

      if isinstance(tool, comk.tool.CxxCompiler):
         # Make sure we’re generating code suitable for a dynamic library.
         tool.add_flags(comk.tool.CxxCompiler.CFLAG_DYNLIB)
         # Allow building both a dynamic library and its clients using the same header file, by
         # changing “import” to “export” when this macro is defined.
         tool.add_macro(
            'COMPLEMAKE_BUILD_{}'.format(re.sub(r'[^_0-9A-Z]+', '_', self._m_sName.upper()))
         )

   def _get_tool(self):
      """See NamedBinaryTarget._get_tool(). Overridden to tell the linker to generate a dynamic
      library.
      """

      lnk = NamedBinaryTarget._get_tool(self)

      lnk.add_flags(comk.tool.Linker.LDFLAG_DYNLIB)
      return lnk

####################################################################################################

class TestTargetMixIn(object):
   """Mixin that provides functionality useful for all test Target subclasses."""

   # True if comparison operands should be treated as amorphous BLOBs, or False if they should be
   # treated as strings.
   _m_bBinaryCompare = None
   # Transformations to apply to the output.
   _m_listOutputTransforms = None

   def __init__(self, mp, dictYaml):
      """Constructor.

      comk.makefileparser.MakefileParser mp
         Parser instantiating the object.
      object dictYaml
         Parsed YAML object to be used to construct the new instance.
      """

      sExpectedOutputFilePath = dictYaml.get('expected output')
      if sExpectedOutputFilePath:
         if not isinstance(sExpectedOutputFilePath, basestring):
            mp.raise_parsing_error('attribute “expected output” must be a string'.format(self))
         dep = comk.dependency.OutputRerefenceDependency(sExpectedOutputFilePath)
         self.add_dependency(dep)

      oOutputTransforms = dictYaml.get('output transform')
      if oOutputTransforms is None:
         self._m_listOutputTransforms = []
      elif isinstance(oOutputTransforms, FilterOutputTransform):
         self._m_listOutputTransforms = [o]
      elif isinstance(oOutputTransforms, list):
         for i, o in enumerate(oOutputTransforms):
            if not isinstance(o, OutputTransform):
               mp.raise_parsing_error((
                  'elements of “output transform” attribute must be of type ' +
                  '!complemake/target/*-output-transform, but element [{}] is not'
               ).format(i))
         self._m_listOutputTransforms = oOutputTransforms
      else:
         mp.raise_parsing_error(
            'attribute “output transform” must be a sequence of, or a single !complemake/target/' +
            'output-filter object'.format(self)
         )

      sScriptFilePath = dictYaml.get('script')
      if sScriptFilePath:
         # TODO: support “script” referencing a binary built by the same makefile.
         # TODO: support “script” being a mapping with more attributes, e.g. command-line args.
         if not isinstance(sScriptFilePath, basestring):
            mp.raise_parsing_error('attribute “script” must be a string'.format(self))
         dep = comk.dependency.TestExecScriptDependency(sScriptFilePath)
         self.add_dependency(self, dep)

   def _transform_comparison_operand(self, o):
      """Transforms a comparison operand according to any “output transform” attributes specified in
      the makefile, and returns the result.

      Some transformations require that the operand is a string; this method will convert a bytes
      instance into a str in a way that mimic what an io.TextIOBase object would do. This allows to
      automatically adjust to performing text-based comparisons (as opposed to bytes-based).

      object o
         str or bytes instance to transform.
      object return
         Transformed comparison operand.
      """

      for ot in self._m_listOutputTransforms:
         o = ot(o)
      return o

####################################################################################################

@comk.makefileparser.MakefileParser.local_tag('complemake/target/tooltest', yaml.Kind.MAPPING)
class ToolTestTarget(NamedTargetMixIn, Target, TestTargetMixIn):
   """Target that executes a test."""

   def __init__(self, mp, dictYaml):
      """Constructor.

      comk.makefileparser.MakefileParser mp
         Parser instantiating the object.
      object dictYaml
         Parsed YAML object to be used to construct the new instance.
      """

      # dictYaml['name'] may be missing, but NamedTargetMixIn will catch that.
      NamedTargetMixIn.__init__(self, mp.mk, dictYaml.get('name', ''))
      Target.__init__(self, mp, dictYaml)
      TestTargetMixIn.__init__(self, mp, dictYaml)

   def _build_tool_run(self):
      """See Target._build_tool_run()."""

      log = self._m_mk().log
      log(log.HIGH, 'build[{}]: no job to run for a ToolTestTarget', self)
      self._on_build_tool_run_complete()

   def _on_build_tool_output_validated(self):
      """Invoked after the test’s output has been validated."""

      log = self._m_mk().log
      log(log.HIGH, 'build[{}]: tool output validated', self)
      # Resume with the Target build step we hijacked.
      Target._on_build_tool_run_complete(self)

   def _on_build_tool_run_complete(self):
      """See Target._on_build_tool_run_complete(). Overridden to perform any comparisons defined for
      the test.
      """

      mk = self._m_mk()
      log = mk.log
      log(log.HIGH, 'build[{}]: validating tool output', self)
      # Extract and transform the contents of the two dependencies to compare, and generate a
      # display name for them.
      listCmpNames = []
      listCmpOperands = []
      for dep in self._m_listDependencies:
         if isinstance(dep, (ProcessedSourceTarget, comk.dependency.OutputRerefenceDependency)):
            # Add as comparison operand the contents of this dependency file.
            listCmpNames.append(dep.file_path)
            with open(dep.file_path, 'rb') as fileComparand:
               listCmpOperands.append(self._transform_comparison_operand(fileComparand.read()))

      # At this point we expect 0 <= len(listCmpOperands) <= 2, but we’ll check that a few more
      # lines below.
      if isinstance(listCmpOperands[0], basestring):
         sCmpV = 'internal:text-compare'
         sCmpQ = 'CMPTXT'
      else:
         sCmpV = 'internal:binary-compare'
         sCmpQ = 'CMPBIN'
      if log.verbosity >= log.LOW:
         log(log.LOW, '[{}] {} {}', sCmpV, *listCmpNames)
      else:
         log(log.QUIET, '{} {} <=> {}', log.qm_tool_name(sCmpQ), *listCmpNames)

      # Compare the targets.
      # TODO: make this asynchronously, passing self._on_build_tool_output_validated as the
      # on_complete handler for a new job, instead of doing this and the last line.
      bEqual = (listCmpOperands[0] == listCmpOperands[1])
      if not bEqual:
         log(log.QUIET, '{}: error: {} and {} differ', self._m_sName, *listCmpNames)
      # This comparison counts as an additional test case with a single assertion.
      log.add_testcase_result(self._m_sName, 1, 0 if bEqual else 1)
      if not bEqual:
         return

      self._on_build_tool_output_validated()

   def validate(self):
      """See Target.validate()."""

      Target.validate(self)

      # TODO: validate the types of self.get_dependencies().

      # Count how many non-output (static) comparison operands have been specified for this target.
      cStaticCmpOperands = 0
      for dep in self._m_listDependencies:
         if isinstance(dep, (ProcessedSourceTarget, comk.dependency.OutputRerefenceDependency)):
            cStaticCmpOperands += 1
      if cStaticCmpOperands != 2:
         raise comk.make.MakefileError('{}: need exactly two files/outputs to compare'.format(self))

####################################################################################################

@comk.makefileparser.MakefileParser.local_tag('complemake/target/exetest', yaml.Kind.MAPPING)
class ExecutableTestTarget(NamedBinaryTarget, TestTargetMixIn):
   """Builds an executable test. The output file will be placed in the “bin/test” directory relative
   to the output base directory.
   """

   # True if the test executable uses abc::testing to execute test cases and report their results,
   # making it compatible with being run via AbacladeTestJob, or False if it’s a monolithic single
   # test, executed via ExternalCmdCapturingJob.
   #
   # TODO: make this a three-state, with True/False meaning explicit declaration, for example via a
   # boolean “use abc::testing” attribute, with true or false mapping to True/False and turning off
   # auto-detection, and if missing mapped to None to mean False with auto-detection that can change
   # it to True using the current logic in add_dependency().
   _m_bUsesAbacladeTesting = None

   def __init__(self, mp, dictYaml):
      """Constructor.

      comk.makefileparser.MakefileParser mp
         Parser instantiating the object.
      object dictYaml
         Parsed YAML object to be used to construct the new instance.
      """

      # Default the “path” attribute before constructing the base class.
      mk = mp.mk
      # dictYaml['name'] may be missing, but NamedTargetMixIn will catch that.
      dictYaml.setdefault('path', os.path.join(
         mk.output_dir, 'bin', 'test', mk.target_platform.exe_file_name(dictYaml.get('name', ''))
      ))

      NamedBinaryTarget.__init__(self, mp, dictYaml)
      TestTargetMixIn.__init__(self, mp, dictYaml)

   def add_dependency(self, dep):
      """See NamedBinaryTarget.add_dependency(). Overridden to detect if the test is linked to
      abaclade-testing, making it compatible with being run via AbacladeTestJob.
      """

      # Check if this test uses the abaclade-testing framework.
      if isinstance(dep, (comk.dependency.UndeterminedLibDependency, comk.dependency.ForeignLibDependency, DynLibTarget)):
         if dep.name == 'abaclade-testing':
            self._m_bUsesAbacladeTesting = True

      NamedBinaryTarget.add_dependency(self, dep)

   def get_exec_environ(self):
      """Generates an os.environ-like dictionary containing any variables necessary to execute the
      test.

      dict(str: str) return
         Modified environment, or None if no environment changes are needed to run the test.
      """

      # If the build target is linked to a library built by this same makefile, make sure we add
      # output_dir/lib to the library path.
      dictEnv = None
      if any(isinstance(dep, DynLibTarget) for dep in self._m_listDependencies):
         mk = self._m_mk()
         dictEnv = mk.target_platform.add_dir_to_dynlib_env_path(
            os.environ.copy(), os.path.join(mk.output_dir, 'lib')
         )
      return dictEnv

   def _on_build_tool_run_complete(self):
      """See NamedBinaryTarget._on_build_tool_run_complete(). Overridden to execute the freshly-
      built test.
      """

      mk = self._m_mk()
      log = mk.log
      log(log.HIGH, 'build[{}]: executing test', self)

      # Prepare the command line.
      for dep in self._m_listDependencies:
         if isinstance(dep, comk.dependency.TestExecScriptDependency):
            # We also have a “script” to drive the test.
            listArgs = [dep.file_path]
            # TODO: support more arguments once __init__() can recognize them.
            break
      else:
         listArgs = []
      listArgs.append(self.file_path)

      # Prepare the arguments for Popen.
      dictPopenArgs = {
         'args': listArgs,
         'env' : self.get_exec_environ(),
      }
      # If we’re using a script to run this test, tweak the Popen invocation to run a possibly non-
      # executable file.
      if len(listArgs) > 1:
         mk.target_platform.adjust_popen_args_for_script(dictPopenArgs)

      # If the build target uses abc::testing, run it with the special abc::testing job,
      # AbacladeTestJob.
      if self._m_bUsesAbacladeTesting:
         clsJob = comk.job.AbacladeTestJob
      else:
         clsJob = comk.job.ExternalCmdCapturingJob
      # This will store stdout and stderr of the program to file, and will buffer stdout in
      # memory so we can use it in _on_build_tool_run_complete() if we need to, without disk access.
      job = clsJob(
         self._on_test_run_complete, ('TEST', self._m_sName), dictPopenArgs,
         mk.log, self.build_log_path, self.file_path + '.out'
      )
      # TODO: FIXME? How can this catch an exception if the job is not started synchronously?
      try:
         mk.job_runner.enqueue(job)
         bStarted = True
      except OSError as x:
         # On POSIX, x.errno == ENOEXEC (8, “Exec format error”) indicates that the binary is for a
         # different machine/architecture.
         # On Windows, x.winerror == ERROR_BAD_EXE_FORMAT (193, “%1 is not a valid Win32
         # application”) for the same condition, but Python properly maps it to errno 8.
         if x.errno == 8 and mk.cross_build:
            bStarted = False
         else:
            # Not something we consider acceptable.
            raise
      if not bStarted:
         # Report that the test was not run, and skip self._on_test_run_complete().
         log(log.QUIET, '{} {}', log.qm_tool_name('SKIP-X'), ' '.join(listArgs))
         NamedBinaryTarget._on_build_tool_run_complete(self)

   def _on_test_run_complete(self):
      """Invoked after the test has been run."""

      mk = self._m_mk()
      log = mk.log
      log(log.HIGH, 'build[{}]: updating dependencies', self)

      # Extract and transform the contents of the two dependencies to compare, and generate a
      # display name for them.
      listCmpNames = []
      listCmpOperands = []
      for dep in self._m_listDependencies:
         if isinstance(dep, comk.dependency.OutputRerefenceDependency):
            # Add as comparison operand the contents of this dependency file.
            listCmpNames.append(dep.file_path)
            with open(dep.file_path, 'rb') as fileComparand:
               listCmpOperands.append(self._transform_comparison_operand(fileComparand.read()))

      # At this point we expect 0 <= len(listCmpOperands) <= 2, but we’ll check that a few more
      # lines below.
      if listCmpOperands:
         # We have a build target and at least another comparison operand, so the job that
         # just completed must be of type ExternalPipedCommandJob, and we’ll add its output as
         # comparison operand.
         listCmpNames.append(job.stdout_file_path)
         listCmpOperands.append(self._transform_comparison_operand(job.stdout))

         if isinstance(listCmpOperands[0], basestring):
            sCmpV = 'internal:text-compare'
            sCmpQ = 'CMPTXT'
         else:
            sCmpV = 'internal:binary-compare'
            sCmpQ = 'CMPBIN'
         if log.verbosity >= log.LOW:
            log(log.LOW, '[{}] {} {}', sCmpV, *listCmpNames)
         else:
            log(log.QUIET, '{} {} <=> {}', log.qm_tool_name(sCmpQ), *listCmpNames)

         # Compare the targets.
         bEqual = (listCmpOperands[0] == listCmpOperands[1])
         if not bEqual:
            log(log.QUIET, '{}: error: {} and {} differ', self._m_sName, *listCmpNames)
            iRet = 1
         # This comparison counts as an additional test case with a single assertion.
         log.add_testcase_result(self._m_sName, 1, 0 if bEqual else 1)
         if iRet != 0:
            # TODO: report build failure.
            return

      NamedBinaryTarget._on_build_tool_run_complete(self)

   def validate(self):
      """See NamedBinaryTarget.validate()."""

      NamedBinaryTarget.validate(self)

      # Count how many non-output (static) comparison operands have been specified for this target.
      cStaticCmpOperands = 0
      for dep in self._m_listDependencies:
         if isinstance(dep, comk.dependency.OutputRerefenceDependency):
            cStaticCmpOperands += 1
      if cStaticCmpOperands != 0 and cStaticCmpOperands != 1:
         # Expected a file against which to compare the test’s output.
         raise comk.make.MakefileError(
            '{}: can’t compare the test output against more than one file'.format(self)
         )

####################################################################################################

class OutputTransform(object):
   """Base class for output transformations."""

   pass

####################################################################################################

@comk.makefileparser.MakefileParser.local_tag(
   'complemake/target/filter-output-transform', yaml.Kind.SCALAR
)
class FilterOutputTransform(OutputTransform):
   """Implements a filter output transformation. This works by removing any text not matching a
   specific regular expression.
   """

   # Filter (regex) to apply.
   _m_re = None

   def __init__(self, mp, sYaml):
      """Constructor.

      comk.makefileparser.MakefileParser mp
         Parser instantiating the object.
      object sYaml
         Parsed YAML object to be used to construct the new instance.
      """

      self._m_re = re.compile(sYaml, re.DOTALL)

   def __call__(self, o):
      """Function call.

      object o
         Object to transform.
      object return
         Transformed object.
      """

      if sys.hexversion < 0x03000000:
         unistr = unicode
      else:
         unistr = str
      if isinstance(o, bytes):
         o = unistr(o, encoding = locale.getpreferredencoding())
      elif not isinstance(o, unistr):
         raise TypeError('cannot transform objects of type {}'.format(type(o).__name__))
      return '\n'.join(self._m_re.findall(o))
