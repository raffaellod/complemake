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

"""Builds outputs and runs unit tests as specified in a .abcmk file."""

import os
import re
import subprocess
import sys
import time
import xml.dom
import xml.dom.minidom



####################################################################################################
# Tool

class Tool(object):
   """Abstract tool."""

   # Files to be processed by the tool.
   _m_listInputFilePaths = None
   # Output file path.
   _m_sOutputFilePath = None
   # Short name of the tool, to be displayed in quiet mode. If None, the tool file name will be
   # displayed.
   _smc_sQuietName = None
   # Associates a Tool-derived class to its executable file name.
   _sm_dictToolFilePaths = {}
   # Environment block (dictionary) modified to force programs to display output in US English.
   _sm_dictUSEngEnv = None


   def add_input(self, sInputFilePath):
      """Adds an input file to the tool input set. Duplicates are not discarded.

      str sInputFilePath
         Path to the input file.
      """

      if self._m_listInputFilePaths is None:
         self._m_listInputFilePaths = []
      self._m_listInputFilePaths.append(sInputFilePath)


   @classmethod
   def detect(cls, iterSupported):
      """Attempts to detect the presence of a tool’s executable from a list of supported ones,
      returning the corresponding class.

      iterable(tuple(class, iterable(str*), str)*) iterSupported
         Iterable containing a class wrapper for each supported tool of the type of interest, the
         (arguments of the) command that shall be executed to determine whether a tool is avaiable,
         and the last item is a string that will be used as a regular expression to determine
         whether the tool output the expected identification string when invoked.
      type return
         Class wrapping the first detected tool among these in iterSupported.
      """

      # TODO: accept paths provided via command line.
      # TODO: apply a cross-compiler prefix.

      listTried = []
      for clsTool, iterArgs, sOutMatch in iterSupported:
         # Make sure we have a US English environment dictionary.
         if cls._sm_dictUSEngEnv is None:
            # Copy the current environment and add to it a locale override for US English.
            cls._sm_dictUSEngEnv = os.environ.copy()
            cls._sm_dictUSEngEnv['LC_ALL'] = 'en_US.UTF-8'

         try:
            with subprocess.Popen(
               iterArgs, env = cls._sm_dictUSEngEnv,
               stdout = subprocess.PIPE, stderr = subprocess.PIPE, universal_newlines = True
            ) as procTool:
               sOut, sErr = procTool.communicate()
         except FileNotFoundError:
            # This just means that the program is not installed; move on to the next candidate.
            pass
         else:
            if re.search(sOutMatch, sOut, re.MULTILINE):
               # Permanently associate the tool to the file path.
               cls._sm_dictToolFilePaths[clsTool] = iterArgs[0]
               # Return the selection.
               return clsTool

         # Remember we tried this executable name.
         listTried.append(iterArgs[0])

      # No executable matched any of the supported ones.
      raise Exception('unable to detect tool; expected one of: ' + ', '.join(listTried))


   def _get_quiet_cmd(self):
      """Returns an iterable containing the short name and relevant (input or output) files for the
      tool, to be displayed in quiet mode.

      iterable(str, str*) return
         Iterable containing the quiet command name and the output file path(s).
      """

      if self._smc_sQuietName is None:
         sQuietName = os.path.basename(self._sm_dictToolFilePaths[type(self)])
      else:
         sQuietName = self._smc_sQuietName
      return sQuietName, self._m_sOutputFilePath


   def _run_add_cmd_flags(self, listArgs):
      """Builds the flags portion of the tool’s command line.

      The default implementation does nothing – no flags can be applied to every tool.

      list(str*) listArgs
         Arguments list.
      """

      pass


   def _run_add_cmd_inputs(self, listArgs):
      """Builds the input files portion of the tool’s command line.

      The default implementation adds the input file paths at the end of listArgs.

      list(str*) listArgs
         Arguments list.
      """

      # Add the source file paths, if any.
      if self._m_listInputFilePaths:
         listArgs.extend(self._m_listInputFilePaths)


   def schedule_jobs(self, make, iterBlockingJobs, iterMetadataToUpdate):
      """Schedules one or more jobs that, when run, result in the execution of the tool.

      An implementation will create one or more chained ScheduledJob instances, blocking the first
      with iterBlockingJobs and returning the last one.

      The default implementation schedules a single job, the command line of which is composed by
      calling Tool._run_add_cmd_flags() and Tool._run_add_cmd_inputs().

      Make make
         Make instance.
      iterable(ScheduledJob*) iterBlockingJobs
         Jobs that should block the first one scheduled for this execution of the tool (Tool
         instance).
      iterable(str*) iterMetadataToUpdate
         Paths to the files for which metadata should be updated when this job completes.
      ScheduledJob return
         Last job scheduled.
      """

      # Make sure that the output directory exists.
      if self._m_sOutputFilePath:
         os.makedirs(os.path.dirname(self._m_sOutputFilePath), 0o755, True)

      # Build the arguments list.
      listArgs = [self._sm_dictToolFilePaths[type(self)]]
      self._run_add_cmd_flags(listArgs)
      self._run_add_cmd_inputs(listArgs)
      if make.verbosity >= Make.VERBOSITY_LOW:
         iterQuietCmd = None
      else:
         iterQuietCmd = self._get_quiet_cmd()
      return ScheduledJob(make, iterBlockingJobs, listArgs, iterQuietCmd, iterMetadataToUpdate)


   def set_output(self, sOutputFilePath):
      """Assigns the name of the tool output.

      str sOutputFilePath
         Path to the output file to be generated by this tool.
      """

      self._m_sOutputFilePath = sOutputFilePath



####################################################################################################
# CxxCompiler

class CxxCompiler(Tool):
   """Abstract C++ compiler."""

   # See ObjectTarget.final_output_target.
   _m_clsFinalOutputTarget = None
   # Additional include directories.
   _m_listIncludeDirs = None
   # See Tool._smc_sQuietName.
   _smc_sQuietName = 'C++'


   def add_include_dir(self, sIncludeDirPath):
      """Adds an include directory to the compiler’s command line.

      str sIncludeDirPath
         Path to the include directory to add.
      """

      if self._m_listIncludeDirs is None:
         self._m_listIncludeDirs = []
      self._m_listIncludeDirs.append(sIncludeDirPath)


   def _get_quiet_cmd(self):
      """See Tool._get_quiet_cmd(). This override substitutes the output file path with the inputs,
      to show the source file path instead of the intermediate one.
      """

      iterQuietCmd = super()._get_quiet_cmd()
      return [iterQuietCmd[0]] + self._m_listInputFilePaths


   # Name suffix for intermediate object files.
   object_suffix = None


   def set_output(self, sOutputFilePath, clsFinalOutputTarget):
      """See Tool.set_output(); also assigns the type of the final linker output.

      str sOutputFilePath
         Path to the output file to be generated by this tool.
      type clsFinalOutputTarget
         Target-derived class of which the final output for this target is an instance.
      """

      super().set_output(sOutputFilePath)
      self._m_clsFinalOutputTarget = clsFinalOutputTarget



####################################################################################################
# GCC-driven GNU LD

class GxxCompiler(CxxCompiler):
   """GNU C++ compiler (G++)."""

   def __init__(self):
      """Constructor. See Linker.__init__()."""

      super().__init__()
      # TODO: remove hardcoded dirs.
      self.add_include_dir('include')


   # See CxxCompiler.object_suffix.
   object_suffix = '.o'


   def _run_add_cmd_flags(self, listArgs):
      """See CxxCompiler._run_add_cmd_flags()."""

      super()._run_add_cmd_flags(listArgs)

      # Add flags.
      listArgs.extend([
         '-c', '-std=c++0x', '-fnon-call-exceptions', '-fvisibility=hidden'
      ])
      listArgs.extend([
         '-ggdb', '-O0', '-DDEBUG=1'
      ])
      listArgs.extend([
         '-Wall', '-Wextra', '-pedantic', '-Wundef', '-Wshadow', '-Wconversion',
         '-Wsign-conversion', '-Wlogical-op', '-Wmissing-declarations', '-Wpacked',
         '-Wunreachable-code', '-Winline'
      ])
      if self._m_clsFinalOutputTarget is DynLibTarget:
         listArgs.append('-fPIC')
      # TODO: add support for os.environ['CFLAGS'] and other vars ?
      # Add the include directories.
      for sDirPath in self._m_listIncludeDirs or []:
         listArgs.append('-I' + sDirPath)
      # Add the output file path.
      listArgs.append('-o')
      listArgs.append(self._m_sOutputFilePath)



####################################################################################################
# Linker

class Linker(Tool):
   """Abstract object code linker."""


   # Additional libraries to link to.
   _m_listInputLibs = None
   # Directories to be included in the library search path.
   _m_listLibPaths = None
   # Type of output to generate.
   _m_clsOutputTarget = None
   # See Tool._smc_sQuietName.
   _smc_sQuietName = 'LINK'


   def add_input_lib(self, sInputLibFilePath):
      """Appends a library to the linker’s command line.

      str sInputLibFilePath
         Path to the input library file.
      """

      if self._m_listInputLibs is None:
         self._m_listInputLibs = []
      self._m_listInputLibs.append(sInputLibFilePath)


   def add_lib_path(self, sLibPath):
      """Appends a directory to the library search path.

      str sLibPath
         Path to the library directory to add.
      """

      if self._m_listLibPaths is None:
         self._m_listLibPaths = []
      self._m_listLibPaths.append(sLibPath)


   def set_output(self, sOutputFilePath, clsOutputTarget):
      """See Tool.set_output(); also assigns the type of the linker output.

      str sOutputFilePath
         Path to the output file to be generated by this tool.
      type clsOutputTarget
         Target-derived class of which the output is an instance.
      """

      super().set_output(sOutputFilePath)
      self._m_clsOutputTarget = clsOutputTarget



####################################################################################################
# GCC-driven GNU LD

class GnuLinker(Linker):
   """GCC-driven GNU object code linker (LD)."""


   def _run_add_cmd_flags(self, listArgs):
      """See Linker._run_add_cmd_flags()."""

      super()._run_add_cmd_flags(listArgs)

      listArgs.append('-Wl,--as-needed')
      listArgs.append('-ggdb')
      if self._m_clsOutputTarget is DynLibTarget:
         listArgs.append('-shared')
      # TODO: add support for os.environ['LDFLAGS'] ?
      # Add the output file path.
      listArgs.append('-o')
      listArgs.append(self._m_sOutputFilePath)


   def _run_add_cmd_inputs(self, listArgs):
      """See Linker._run_add_cmd_inputs()."""

      # TODO: should not assume that GNU LD will only be used to build for POSIX.
      self.add_input_lib('dl')
      self.add_input_lib('pthread')

      super()._run_add_cmd_inputs(listArgs)

      # Add the library search directories.
      for sDir in self._m_listLibPaths or []:
         listArgs.append('-L' + sDir)
      # Add the libraries.
      for sLib in self._m_listInputLibs or []:
         listArgs.append('-l' + sLib)



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


   def __init__(self, make, sName = None):
      """Constructor. Generates the target’s file path by calling Target._generate_file_path(), then
      adds itself to the Make instance’s target lists.

      Make make
         Make instance.
      str sName
         See Target.name.
      """

      self._m_sName = sName
      self._m_sFilePath = self._generate_file_path(make)
      if self._m_sFilePath is not None:
         # Add self to the target lists.
         make._add_target(self)


   def add_dependency(self, tgtDep):
      """Adds a target dependency.

      Target tgtDep
         Dependency.
      """

      if self._m_setDeps is None:
         self._m_setDeps = set()
      self._m_setDeps.add(tgtDep)


   def build(self, make, iterBlockingJobs):
      """Builds the output, using the facilities provided by the specified Make instance and
      returning the last job scheduled.

      Make make
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


   def _generate_file_path(self, make):
      """Generates and returns a file path for the target, based on other member varialbes set
      beforehand and the configuration of the provided Make instance. Called by Target.__init__().

      The default implementation doesn’t generate a file path because no output file is assumed.

      Make make
         Make instance.
      str return
         Target file path; same as Target.file_path.
      """

      # No output file.
      return None


   def _get_name(self):
      return self._m_sName

   name = property(_get_name, doc = """Name of the target.""")


   def parse_makefile_child(self, elt, make):
      """Validates and processes the specified child element of the target’s <target> element.

      xml.dom.Element elt
         <target> element to parse.
      Make make
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


   def __init__(self, make, sName, sSourceFilePath):
      """Constructor. See Target.__init__().

      Make make
         Make instance.
      str sName
         See Target.name.
      str sSourceFilePath
         See ObjectTarget.source_file_path.
      """

      self._m_sSourceFilePath = sSourceFilePath
      super().__init__(make, sName)


   def _get_final_output_target(self):
      return self._m_clsFinalOutputTarget

   def _set_final_output_target(self, clsFinalOutputTarget):
      self._m_clsFinalOutputTarget = clsFinalOutputTarget

   final_output_target = property(_get_final_output_target, _set_final_output_target, doc = """
      Kind of output that ObjectTarget.build() will aim for when generating the object file, e.g. by
      passing -fPIC for a C++ source file when compiling it for a shared object.
   """)


   def _generate_file_path(self, make):
      """See Target._generate_file_path()."""

      return os.path.join(
         make.output_dir, 'obj', self._m_sSourceFilePath + make.cxxcompiler.object_suffix
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

   def build(self, make, iterBlockingJobs):
      """See Target.build()."""

      tplDeps = None
      if iterBlockingJobs:
         if make.verbosity >= Make.VERBOSITY_MEDIUM:
            sys.stdout.write(
               '{}: rebuilding due to dependencies being rebuilt\n'.format(self.file_path)
            )
      else:
         # TODO: check for additional changed external dependencies.
         tplDeps = (self._m_sSourceFilePath, )
         if make.file_metadata_changed(tplDeps):
            if make.verbosity >= Make.VERBOSITY_MEDIUM:
               sys.stdout.write('{}: rebuilding due to changed sources\n'.format(self.file_path))
         else:
            # No dependencies being rebuilt, source up-to-date: no need to rebuild.
            if make.verbosity >= Make.VERBOSITY_MEDIUM:
               sys.stdout.write('{}: up-to-date\n'.format(self.file_path))
            return None

      cxx = make.cxxcompiler()
      cxx.set_output(self.file_path, self.final_output_target)
      cxx.add_input(self.source_file_path)
      # TODO: add file-specific flags.
      return cxx.schedule_jobs(make, iterBlockingJobs, tplDeps)



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


   def build(self, make, iterBlockingJobs):
      """See Target.build()."""

      # Due to the different types of objects in _m_listLinkerInputs and the fact we want to iterate
      # over that list only once, combine building the list of dependencies for which metadata need
      # to be checked with collecting linker inputs.
      listDeps = []
      lnk = make.linker()
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
               lnk.add_lib_path(os.path.join(make.output_dir, 'lib'))
            else:
               raise Exception('unclassified linker input: {}'.format(oDep.file_path))

      if iterBlockingJobs:
         if make.verbosity >= Make.VERBOSITY_MEDIUM:
            sys.stdout.write(
               '{}: rebuilding due to dependencies being rebuilt\n'.format(self.file_path)
            )
      elif listDeps:
         if make.file_metadata_changed(listDeps):
            if make.verbosity >= Make.VERBOSITY_MEDIUM:
               sys.stdout.write('{}: rebuilding due to changed dependencies\n'.format(
                  self.file_path
               ))
         else:
            # No dependencies being rebuilt, inputs up-to-date: no need to rebuild.
            if make.verbosity >= Make.VERBOSITY_MEDIUM:
               sys.stdout.write('{}: up-to-date\n'.format(self.file_path))
            return None
      else:
         # No dependencies being rebuilt, no inputs: no change.
         if make.verbosity >= Make.VERBOSITY_MEDIUM:
            sys.stdout.write('{}: up-to-date\n'.format(self.file_path))
         return None

      return lnk.schedule_jobs(make, iterBlockingJobs, listDeps)


   def _generate_file_path(self, make):
      """See Target._generate_file_path()."""

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      return os.path.join(make.output_dir, 'bin', '' + self.name + '')


   def parse_makefile_child(self, elt, make):
      """See Target.parse_makefile_child()."""

      if elt.nodeName == 'source':
         # Pick the correct target class based on the file name extension.
         sFilePath = elt.getAttribute('path')
         if re.search(r'\.c(?:c|pp|xx)$', sFilePath):
            clsObjTarget = CxxObjectTarget
         else:
            raise Exception('unsupported source file type')
         # Create an object target with the file path as its source.
         tgtObj = clsObjTarget(make, None, sFilePath)
         # Add the target as a dependency to this target.
         tgtObj.final_output_target = type(self)
         self.add_dependency(tgtObj)
         self.add_linker_input(tgtObj)
      elif elt.nodeName == 'dynlib':
         # Check if this makefile can build this dynamic library.
         sName = elt.getAttribute('name')
         # If the library was in the dictionary (i.e. it’s built by this makefile), assign it as a
         # dependency of self; else just add the library name (hence passing sName as 2nd argument
         # to make.get_target_by_name()).
         oDynLib = make.get_target_by_name(sName, sName)
         if oDynLib is not sName:
            self.add_dependency(oDynLib)
         self.add_linker_input(oDynLib)
      elif elt.nodeName == 'unittest':
         # A unit test must be built after the target it’s supposed to test.
         sName = elt.getAttribute('name')
         tgtUnitTest = make.get_target_by_name(sName, None)
         if tgtUnitTest is None:
            raise Exception(
               'could not find definition of referenced unit test: {}'.format(sName)
            )
         tgtUnitTest.add_dependency(self)
      else:
         super().parse_makefile_child(elt, make)



####################################################################################################
# DynLibTarget

class DynLibTarget(ExecutableTarget):
   """Dynamic library target. The output file will be placed in a lib/ directory relative to the
   output base directory.
   """

   def _generate_file_path(self, make):
      """See ExecutableTarget._generate_file_path()."""

      # TODO: change 'lib' + '.so' from hardcoded to computed by a Platform class.
      return os.path.join(make.output_dir, 'lib', 'lib' + self.name + '.so')


   def parse_makefile_child(self, elt, make):
      """See ExecutableTarget.parse_makefile_child()."""

      super().parse_makefile_child(elt, make)
      if elt.nodeName == 'unittest':
         sName = elt.getAttribute('name')
         tgtUnitTest = make.get_target_by_name(sName)
         # Make the unit test link to this library.
         tgtUnitTest.add_linker_input(self)



####################################################################################################
# UnitTestTarget

class UnitTestTarget(ExecutableTarget):
   """Executable unit test target. The output file will be placed in a bin/unittest/ directory
   relative to the output base directory.
   """

   def _generate_file_path(self, make):
      """See ExecutableTarget._generate_file_path()."""

      # TODO: change '' + '' from hardcoded to computed by a Platform class.
      return os.path.join(make.output_dir, 'bin', 'unittest', '' + self.name + '')


   def parse_makefile_child(self, elt, make):
      """See ExecutableTarget.parse_makefile_child()."""

      if elt.nodeName == 'unittest':
         raise SyntaxError('<unittest> not allowed in <target type="unittest">')
      elif elt.nodeName == 'runner':
         # TODO: assign the runner type.
         pass
      else:
         super().parse_makefile_child(elt, make)



####################################################################################################
# ScheduledJob

class ScheduledJob(object):
   """Schedules a job in the Make instance’s queue, keeping track of the jobs it must wait to
   complete.
   """

   # See ScheduledJob.command.
   _m_iterArgs = None
   # Jobs that this one is blocking.
   _m_setBlockedJobs = None
   # Count of jobs that block this one.
   _m_cBlocks = 0
   # See ScheduledJob.quiet_command.
   _m_iterQuietCmd = None
   # Files for which we’ll need to update metadata after this job completes. This includes the
   # output file and any input files that are not built by the same makefile.
   _m_iterMetadataToUpdate = None


   def __init__(self, make, iterBlockingJobs, iterArgs, iterQuietCmd, iterMetadataToUpdate):
      """Constructor.

      Make make
         Make instance.
      iterable(ScheduledJob*) iterBlockingJobs
         Jobs that block this one.
      iterable(str+) iterArgs
         Command-line arguments to execute this job.
      iterable(str, str*) iterQuietCmd
         “Quiet mode” command; see return value of Tool._get_quiet_cmd().
      iterable(str*) iterMetadataToUpdate
         Paths to the files for which metadata should be updated when this job completes.
      """

      self._m_iterArgs = iterArgs
      self._m_iterQuietCmd = iterQuietCmd
      self._m_iterMetadataToUpdate = iterMetadataToUpdate
      if iterBlockingJobs is not None:
         # Assign this job as “blocked” by the jobs it depends on, and store their count.
         for sjDep in iterBlockingJobs:
            if sjDep._m_setBlockedJobs is None:
               sjDep._m_setBlockedJobs = set()
            sjDep._m_setBlockedJobs.add(self)
         self._m_cBlocks = len(iterBlockingJobs)
      # Schedule this job.
      make._schedule_job(self)


   def _get_blocked(self):
      return self._m_cBlocks > 0

   blocked = property(_get_blocked, doc = """
      True if the job is blocked (i.e. requires other jobs to be run first), or False otherwise.
   """)


   def _get_command(self):
      return self._m_iterArgs

   command = property(_get_command, doc = """Command to be invoked, as a list of arguments.""")


   def _get_quiet_command(self):
      return self._m_iterQuietCmd

   quiet_command = property(_get_quiet_command, doc = """
      Command summary to print out in quiet mode.
   """)


   def release_blocked(self):
      """Release any jobs this one was blocking."""

      if self._m_setBlockedJobs:
         for sj in self._m_setBlockedJobs:
            sj._m_cBlocks -= 1



####################################################################################################
# FileMetadata

class FileMetadata(object):
   """Metadata for a single file."""

   # Time of the file’s last modification.
   _m_iMTime = None


   def __init__(self, sFilePath):
      """Constructor.

      str sFilePath
         Path to the file of which to collect metadata.
      """

      self._m_iMTime = os.path.getmtime(sFilePath)


   def __eq__(self, other):
      return self._m_iMTime == other._m_iMTime


   def __ne__(self, other):
      return not self.__eq__(other)


####################################################################################################
# FileMetadataPair

class FileMetadataPair(object):
   """Stores Handles storage and retrieval of file metadata."""


   # Stored file metadata, or None if the file’s metadata was never collected.
   stored = None
   # Current file metadata, or None if the file’s metadata has not yet been refreshed.
   current = None



####################################################################################################
# MetadataStore

class MetadataStore(object):
   """Handles storage and retrieval of file metadata."""

   # Persistent storage file path.
   _m_sFilePath = None
   # Metadata for each file (str -> FileMetadata).
   _m_dictMetadata = None


   def __init__(self, sFilePath):
      """Constructor. Loads metadata from the specified file.

      str sFilePath
         Metadata storage file.
      """

      self._m_sFilePath = sFilePath
      self._m_dictMetadata = {}


   def __bool__(self):
      return bool(self._m_dictMetadata)


   def file_changed(self, sFilePath):
      """Compares the metadata stored for the specified file against the file’s current metadata.

      str sFilePath
         Path to the file of which to compare metadata.
      bool return
         True if the file is determined to have changed, or False otherwise.
      """

      fmp = self._m_dictMetadata.get(sFilePath)
      # If we have no metadata to compare, report the file as changed.
      if fmp is None or fmp.stored is None:
         return True
      # If we still haven’t read the file’s current metadata, retrieve it now.
      if fmp.current is None:
         fmp.current = FileMetadata(sFilePath)
      # Compare stored vs. current metadata.
      return fmp.current == fmp.stored


   def update(self, sFilePath):
      """Creates or updates metadata for the specified file.

      str sFilePath
         Path to the file of which to update metadata.
      """

      fmp = self._m_dictMetadata.get(sFilePath)
      # Make sure the metadata pair is in the dictionary.
      if fmp is None:
         fmp = FileMetadataPair()
         self._m_dictMetadata[sFilePath] = fmp
      # It’s still possible that MetadataStore.file_changed() was never called for this file (e.g.
      # prior changed metadata was sufficient to decide that a dependency needed to be rebuilt), so
      # make sure we have up-to-date metadata for this file.
      if fmp.current is None:
         fmp.current = FileMetadata(sFilePath)
      # Replace the stored metadata.
      fmp.stored = fmp.current


   def write(self):
      """Stores metadata to the file from which it was loaded."""

      pass



####################################################################################################
# Make

class Make(object):
   """Processes an ABC makefile (.abcmk) by parsing it, scheduling the necessary jobs to build any
   targets to be built, and then running the jobs with the selected degree of parallelism.

   Example usage:

      make = Make()
      make.parse('project.abcmk')
      make.schedule_target_jobs(make.get_target_by_name('projectbin'))
      make.run_scheduled_jobs()
   """

   # No verbosity, i.e. quiet operation (default). Will display a short summary of each job being
   # executed, instead of its command-line.
   VERBOSITY_NONE = 1
   # Print each job’s command-line as-is instead of a short summary.
   VERBOSITY_LOW = 2
   # Like VERBOSITY_LOW, and also describe what triggers the (re)building of each target.
   VERBOSITY_MEDIUM = 3
   # Like VERBOSITY_MED, and also show all the files that are being checked for changes.
   VERBOSITY_HIGH = 4

   # See Make.cxxcompiler.
   _m_clsCxxCompiler = None
   # See Make.dry_run.
   _m_bDryRun = False
   # See Make.force_build.
   _m_bForceBuild = False
   # See Make.ignore_errors.
   _m_bIgnoreErrors = False
   # See Make.keep_going.
   _m_bKeepGoing = False
   # See Make.linker.
   _m_clsLinker = None
   # Metadata store.
   _m_mds = None
   # Targets explicitly declared in the parsed makefile (name -> Target).
   _m_dictNamedTargets = None
   # See Make.output_dir.
   _m_sOutputDir = ''
   # Running jobs (Popen -> ScheduledJob).
   _m_dictRunningJobs = {}
   # Maximum count of running jobs, i.e. degree of parallelism.
   _m_cRunningJobsMax = 8
   # Scheduled jobs.
   _m_setScheduledJobs = None
   # “Last” scheduled jobs (Target -> ScheduledJob that completes it), i.e. jobs that are the last
   # in a chain of jobs scheduled to build a single target. The values are a subset of, or the same
   # as, Make._m_setScheduledJobs.
   _m_dictTargetLastScheduledJobs = None
   # All targets specified by the parsed makefile (file path -> Target), including implicit and
   # intermediate targets not explicitly declared with a <target> element.
   _m_dictTargets = None

   # Special value used with get_target_by_*() to indicate that a target not found should result in
   # an exception.
   _RAISE_IF_NOT_FOUND = object()


   def __init__(self):
      """Constructor."""

      self._m_dictNamedTargets = {}
      self._m_setScheduledJobs = set()
      self._m_dictTargetLastScheduledJobs = {}
      self._m_dictTargets = {}
      self.verbosity = Make.VERBOSITY_NONE


   def _add_target(self, tgt):
      """Adds a target to the relevant dictionaries.

      Target tgt
         Target to add.
      """

      self._m_dictTargets[tgt.file_path] = tgt
      sName = tgt.name
      if sName:
         self._m_dictNamedTargets[sName] = tgt


   def _collect_completed_jobs(self, cJobsToComplete):
      """Returns only after the specified number of jobs completes and the respective cleanup
      operations (such as releasing blocked jobs) have been performed. If cJobsToComplete == 0, it
      only performs cleanup for jobs that have already completed, without waiting.

      Returns the count of failed jobs, unless Make._m_bIgnoreErrors is True, in which case it will
      always return 0.

      int cJobsToComplete
         Count of jobs to wait for.
      int return
         Count of jobs that completed in failure.
      """

      # This loop alternates poll loop and sleeping.
      cCompletedJobs = 0
      cFailedJobs = 0
      # The termination condition is in the middle.
      while True:
         # This loop restarts the for loop, since we modify _m_dictRunningJobs. The termination
         # condition is a break statement.
         while True:
            # Poll each running job.
            for proc in self._m_dictRunningJobs.keys():
               if self._m_bDryRun:
                  # A no-ops is always successful.
                  iRet = 0
               else:
                  iRet = proc.poll()
               if iRet is not None:
                  # Remove the job from the running jobs.
                  sj = self._m_dictRunningJobs.pop(proc)
                  cCompletedJobs += 1
                  if iRet == 0 or self._m_bIgnoreErrors:
                     # The job completed successfully or we’re ignoring its failure: any dependent
                     # jobs can now be released.
                     sj.release_blocked()
                     # If the job was successfully executed, update any input files’ metadata.
                     if iRet == 0 and not self._m_bDryRun and sj._m_iterMetadataToUpdate:
                        self.update_file_metadata(sj._m_iterMetadataToUpdate)
                  else:
                     if self._m_bKeepGoing:
                        # Unschedule any dependent jobs, so we can continue ignoring this failure as
                        # long as we have scheduled jobs that don’t depend on it.
                        if sj._m_setBlockedJobs:
                           self._unschedule_jobs_blocked_by(sj)
                     cFailedJobs += 1
                  # Since we modified self._m_setScheduledJobs, we have to stop iterating over it.
                  # Iteration will be restarted by the inner while loop.
                  break
            else:
               # The for loop completed without interruptions, which means that no job slots were
               # freed, so break out of the inner while loop into the outer one to wait.
               break
         # If we freed up the requested count of slots, there’s nothing left to do.
         if cCompletedJobs >= cJobsToComplete:
            return cFailedJobs
         if not self._m_bDryRun:
            # Wait a small amount of time.
            # TODO: proper event-based waiting.
            time.sleep(0.1)


   def _get_cxxcompiler(self):
      if self._m_clsCxxCompiler is None:
         # TODO: what’s MSC’s output?
         self._m_clsCxxCompiler = Tool.detect((
            (GxxCompiler, ('g++', '--version'), r'^g\+\+ '),
            (object,      ('cl',  '/?'       ), r' CL '   ),
         ))
      return self._m_clsCxxCompiler

   cxxcompiler = property(_get_cxxcompiler, doc = """
      C++ compiler class to be used to build CxxObjectTarget instances.
   """)


   def _get_dry_run(self):
      return self._m_bDryRun

   def _set_dry_run(self, bDryRun):
      self._m_bDryRun = bDryRun

   dry_run = property(_get_dry_run, _set_dry_run, doc = """
      If True, commands will only be printed, not executed; if False, they will be printed and
      executed.
   """)


   def file_metadata_changed(self, iterFilePaths):
      """Checks the specified input files for changes, returning True if any file appears to have
      changed. After the target dependent on these files has been built, the metadata should be
      refreshed by calling Make.update_file_metadata() with the same arguments.

      iterable(str*) iterFilePaths
         Paths to the files to check for changes.
      bool return
         True if any file has changed, or False otherwise.
      """

      for sFilePath in iterFilePaths:
         if self._m_mds.file_changed(sFilePath):
            if self.verbosity >= Make.VERBOSITY_HIGH:
               sys.stdout.write('Metadata changed for {}\n'.format(sFilePath))
            return True
         if self.verbosity >= Make.VERBOSITY_HIGH:
            sys.stdout.write('Metadata unchanged for {}\n'.format(sFilePath))
      return False


   def _get_force_build(self):
      return self._m_bForceBuild

   def _set_force_build(self, bForceBuild):
      self._m_bForceBuild = bForceBuild

   force_build = property(_get_force_build, _set_force_build, doc = """
      If True, targets are rebuilt unconditionally; if False, targets are rebuilt as needed.
   """)


   def get_target_by_file_path(self, sFilePath, oFallback = _RAISE_IF_NOT_FOUND):
      """Returns a target given its path, raising an exception if no such target exists and no
      fallback value was provided.

      str sFilePath
         Path to the file to find a target for.
      object oFallback
         Object to return in case the specified target does not exist. If omitted, an exception will
         be raised if the target does not exist.
      Target return
         Target that builds sFilePath, or oFallback if no such target was defined in the makefile.
      """

      tgt = self._m_dictTargets.get(sFilePath, oFallback)
      if tgt is self._RAISE_IF_NOT_FOUND:
         raise FileNotFoundError('unknown target: {}'.format(sFilePath))
      return tgt


   def get_target_by_name(self, sName, oFallback = _RAISE_IF_NOT_FOUND):
      """Returns a named (in the makefile) target given its name, raising an exception if no such
      target exists and no fallback value was provided.

      str sName
         Name of the target to look for.
      object oFallback
         Object to return in case the specified target does not exist. If omitted, an exception will
         be raised if the target does not exist.
      Target return
         Target named sName, or oFallback if no such target was defined in the makefile.
      """

      tgt = self._m_dictNamedTargets.get(sName, oFallback)
      if tgt is self._RAISE_IF_NOT_FOUND:
         raise NameError('undefined target: {}'.format(sName))
      return tgt


   def _get_ignore_errors(self):
      return self._m_bIgnoreErrors

   def _set_ignore_errors(self, bIgnoreErrors):
      self._m_bIgnoreErrors = bIgnoreErrors

   ignore_errors = property(_get_ignore_errors, _set_ignore_errors, doc = """
      If True, scheduled jobs will continue to be run even after a job they depend on fails. If
      False, a failed job causes execution to stop according to the value of Make.keep_going.
   """)


   @staticmethod
   def _is_node_whitespace(nd):
      """Returns True if a node is whitespace or a comment.

      xml.dom.Node nd
         Node to check.
      bool return
         True if nd is a whitespace or comment node, or False otherwise.
      """

      if nd.nodeType == xml.dom.Node.COMMENT_NODE:
         return True
      if nd.nodeType == xml.dom.Node.TEXT_NODE and re.match(r'^\s*$', nd.nodeValue):
         return True
      return False


   def _get_keep_going(self):
      return self._m_bKeepGoing

   def _set_keep_going(self, bKeepGoing):
      self._m_bKeepGoing = bKeepGoing

   keep_going = property(_get_keep_going, _set_keep_going, doc = """
      If True, scheduled jobs will continue to be run even after a failed job, as long as they don’t
      depend on a failed job. If False, a failed job causes execution to stop as soon as any other
      running jobs complete.
   """)


   def _get_linker(self):
      if self._m_clsLinker is None:
         # TODO: what’s MS Link’s output?
         self._m_clsLinker = Tool.detect((
            (GnuLinker, ('g++',  '-Wl,--version'), r'^GNU ld '),
            (GnuLinker, ('ld',   '--version'    ), r'^GNU ld '),
            (object,    ('link', '/?'           ), r' Link '  ),
         ))
      return self._m_clsLinker

   linker = property(_get_linker, doc = """
      Linker class to be used to build ExecutableTarget instances.
   """)


   def _get_named_targets(self):
      return self._m_dictNamedTargets.values()

   named_targets = property(_get_named_targets, doc = """
      Targets explicitly declared in the parsed makefile.
   """)


   def _get_output_dir(self):
      return self._m_sOutputDir

   def _set_output_dir(self, sOutputDir):
      self._m_sOutputDir = sOutputDir

   output_dir = property(_get_output_dir, _set_output_dir, doc = """
      Output base directory that will be used for both intermediate and final build results.
   """)


   def parse(self, sFilePath):
      """Parses an ABC makefile.

      str sFilePath
         Path to the makefile to parse.
      """

      self.parse_doc(xml.dom.minidom.parse(sFilePath))
      sMetadataFilePath = os.path.join(os.path.dirname(sFilePath), '.abcmk', 'metadata')
      self._m_mds = MetadataStore(sMetadataFilePath)
      if self.verbosity >= Make.VERBOSITY_HIGH:
         if self._m_mds:
            sys.stdout.write('MetadataStore loaded from {}\n'.format(sMetadataFilePath))
         else:
            sys.stdout.write('MetadataStore empty or missing: {}\n'.format(sMetadataFilePath))


   def parse_doc(self, doc):
      """Parses a DOM representation of an ABC makefile.

      xml.dom.Document doc
         XML document to parse.
      """

      doc.documentElement.normalize()

      # TODO: check whether and where this method should use contexts for the DOM nodes and/or
      # directly call unlink() on them.

      # Do a first scan of the top level elements, to find invalid nodes and unrecognized target
      # types. In the process, we instantiate all the target elements, so
      # Target.parse_makefile_child() can assign the dependencies even if they don’t appear in the
      # correct order in the makefile. This also allows to determine on-the-fly whether a referenced
      # <dynlib> is a target we should build or if we should expect to find it somewhere else.
      listNodesAndTargets = []
      for eltTarget in doc.documentElement.childNodes:
         if self._is_node_whitespace(eltTarget):
            # Skip whitespace/comment nodes.
            continue
         if eltTarget.nodeType != xml.dom.Node.ELEMENT_NODE:
            raise SyntaxError('expected <target>, found: {}'.format(eltTarget.nodeName))

         if eltTarget.nodeName == 'target':
            sType = eltTarget.getAttribute('type')
            # Pick a Target-derived class for this target type.
            if sType == 'unittest':
               clsTarget = UnitTestTarget
            elif sType == 'exe':
               clsTarget = ExecutableTarget
            elif sType == 'dynlib':
               clsTarget = DynLibTarget
            else:
               raise Exception('unsupported target type: {}'.format(sType))
            # Instantiate the Target-derived class, assigning it its name.
            tgt = clsTarget(self, eltTarget.getAttribute('name'))
            listNodesAndTargets.append((tgt, eltTarget))
         else:
            raise SyntaxError('expected <target>; found: <{}>'.format(eltTarget.nodeName))

      # Now that all the targets have been instantiated, we can have them parse their definitions.
      for tgt, eltTarget in listNodesAndTargets:
         for nd in eltTarget.childNodes:
            if self._is_node_whitespace(nd):
               # Skip whitespace/comment nodes.
               continue
            if nd.nodeType != xml.dom.Node.ELEMENT_NODE:
               raise Exception('expected element node, found: '.format(nd.nodeName))
            tgt.parse_makefile_child(nd, self)


   def print_targets_graph(self):
      """Prints to stdout a graph of target dependencies."""

      # Targets explicitly declared in the parsed makefile (name -> target).
      for sName, tgt in self._m_dictNamedTargets.items():
         print('Target “{}” {}'.format(sName, tgt.file_path))
      # All targets specified by the parsed makefile (file path -> Target), including implicit and
      # intermediate targets not explicitly declared with a <target> element.
      for sFilePath, tgt in self._m_dictTargets.items():
         print('Target {}'.format(tgt.file_path))


   def run_scheduled_jobs(self):
      """Executes any scheduled jobs."""

      # This is the earliest point we know we can reset this.
      self._m_dictTargetLastScheduledJobs.clear()

      cFailedJobsTotal = 0
      while self._m_setScheduledJobs:
         # Make sure any completed jobs are collected.
         cFailedJobs = self._collect_completed_jobs(0)
         # Make sure we have at least one free job slot.
         while len(self._m_dictRunningJobs) == self._m_cRunningJobsMax:
            # Wait for one or more jobs slots to free up.
            cFailedJobs += self._collect_completed_jobs(1)

         cFailedJobsTotal += cFailedJobs
         # Stop starting jobs in case of failed errors – unless overridden by the user.
         if cFailedJobs > 0 and not self._m_bKeepGoing:
            break

         # Find a job that is ready to be executed.
         for sj in self._m_setScheduledJobs:
            if not sj.blocked:
               iterArgs = sj.command
               if self.verbosity >= Make.VERBOSITY_LOW:
                  sys.stdout.write(' '.join(iterArgs) + '\n')
               else:
                  iterQuietCmd = sj.quiet_command
                  sys.stdout.write('{:^8} {}\n'.format(iterQuietCmd[0], ' '.join(iterQuietCmd[1:])))
               if self._m_bDryRun:
                  # Create a placeholder instead of a real Popen instance.
                  proc = object()
               else:
                  proc = subprocess.Popen(iterArgs)
               # Move the job from scheduled to running jobs.
               self._m_dictRunningJobs[proc] = sj
               self._m_setScheduledJobs.remove(sj)
               # Since we modified self._m_setScheduledJobs, we have to stop iterating over it; the
               # outer while loop will get back here, eventually.
               break
      # There are no more scheduled jobs, just wait for the running ones to complete.
      cFailedJobsTotal += self._collect_completed_jobs(len(self._m_dictRunningJobs))

      # Write any new metadata.
      if self._m_mds:
         if self.verbosity >= Make.VERBOSITY_HIGH:
            sys.stdout.write('Writing MetadataStore\n')
         self._m_mds.write()
      self._m_mds = None

      return cFailedJobsTotal


   def _schedule_job(self, sj):
      """Used by ScheduledJob.__init__() to add itself to the set of scheduled jobs.

      ScheduledJob sj
         Job to schedule.
      """

      self._m_setScheduledJobs.add(sj)


   def schedule_target_jobs(self, tgt):
      """Schedules jobs for the specified target and all its dependencies, avoiding duplicate jobs.

      Recursively visits the dependency tree for the target in a leaves-first order, collecting
      (possibly chains of) ScheduledJob instances returned by Target.build() for all the
      dependencies, and making these block the ScheduledJob instance(s) for the specified target.

      Target tgt
         Target instance for which jobs should be scheduled by calling its build() method.
      ScheduledJob return
         Last job scheduled by tgt.build().
      """

      # Check if we already have a (last) ScheduledJob for this target.
      sj = self._m_dictTargetLastScheduledJobs.get(tgt)
      if sj is None:
         # Visit leaves.
         listBlockingJobs = None
         for tgtDep in tgt.dependencies or []:
            # Recursively schedule jobs for this dependency, returning and storing the last one.
            sjDep = self.schedule_target_jobs(tgtDep)
            if sjDep is not None:
               # Keep track of the dependencies’ jobs.
               if listBlockingJobs is None:
                  listBlockingJobs = []
               listBlockingJobs.append(sjDep)

         # Visit the node: give the target a chance to schedule jobs, letting it know which of its
         # dependencies scheduled jobs to be rebuilt, if any.
         sj = tgt.build(self, listBlockingJobs)
         # Store the job even if None.
         self._m_dictTargetLastScheduledJobs[tgt] = sj

      if sj is None:
         # If Target.build() did not return a job, there’s nothing to do for this target. This must
         # also mean that no dependencies scheduled any jobs.
         # TODO: how about phonies or “virtual targets”?
         assert(not listBlockingJobs)
      return sj


   def _unschedule_jobs_blocked_by(self, sj):
      """Recursively removes the jobs blocked by the specified job from the set of scheduled
      jobs.

      ScheduledJob sj
         Job to be unscheduled.
      """

      for sjBlocked in sj._m_setBlockedJobs:
         # Use set.discard() instead of set.remove() since it may have already been removed due to a
         # previous unrelated call to this method, e.g. another job failed before the one that
         # caused this call.
         self._m_setScheduledJobs.discard(sjBlocked)
         if sjBlocked._m_setBlockedJobs:
            self._unschedule_jobs_blocked_by(sjBlocked._m_setBlockedJobs)


   def update_file_metadata(self, iterFilePaths):
      """Updates the metadata stored by ABC Make for the specified files.

      This should be called after each build job completes, to update the metadata for its input
      files.

      iterable(str*) iterFilePaths
         Paths to the files whose metadata needs to be updated.
      """

      for sFilePath in iterFilePaths:
         if self.verbosity >= Make.VERBOSITY_HIGH:
            sys.stdout.write('Updating metadata for {}\n'.format(sFilePath))
         self._m_mds.update(sFilePath)


   # True if the exact commands invoked should be printed to stdout, of False if only a short
   # description should.
   verbosity = None



####################################################################################################
# __main__

def _main(iterArgs):
   """Implementation of __main__.

   iterable(str*) iterArgs
      Command-line arguments.
   int return
      Command return status.
   """

   make = Make()
   iArg = 1
   iArgEnd = len(iterArgs)

   # Parse arguments, looking for option flags.
   while iArg < iArgEnd:
      sArg = iterArgs[iArg]
      if sArg.startswith('--'):
         if sArg == '--force-build':
            make.force_build = True
         elif sArg == '--dry-run':
            make.dry_run = True
         elif sArg == '--ignore-errors':
            make.ignore_errors = True
         elif sArg == '--keep-going':
            make.keep_going = True
         elif sArg == '--verbose':
            make.verbosity += 1
      elif sArg.startswith('-'):
         for sArgChar in sArg:
            if sArgChar == 'f':
               make.force_build = True
            elif sArgChar == 'i':
               make.ignore_errors = True
            elif sArgChar == 'k':
               make.keep_going = True
            elif sArgChar == 'n':
               make.dry_run = True
            elif sArgChar == 'v':
               make.verbosity += 1
      else:
         break
      iArg += 1

   # Check for a makefile name.
   if iArg < iArgEnd:
      sArg = iterArgs[iArg]
      if sArg.endswith('.abcmk'):
         # Save the argument as the makefile path and consume it.
         sMakefilePath = sArg
         iArg += 1
   else:
      # Check if the current directory contains a single ABC makefile.
      sMakefilePath = None
      for sFilePath in os.listdir():
         if sFilePath.endswith('.abcmk'):
            if sMakefilePath is None:
               sMakefilePath = sFilePath
            else:
               sys.stderr.write(
                  'error: multiple makefiles found in the current directory, please specify one ' +
                     'explicitly\n'
               )
               return 1
      if not sMakefilePath:
         sys.stderr.write('error: no makefile specified\n')
         return 1

   # Load the makefile.
   make.parse(sMakefilePath)

   # If there are more argument, they will be treated as target named, indicating that only a subset
   # of the targets should be built; otherwise all named targets will be built.
   if iArg < iArgEnd:
      iterTargets = []
      while iArg < iArgEnd:
         sArg = iterArgs[iArg]
         iterTargets.add(make.get_target_by_name(sArg, None) or make.get_target_by_file_path(sArg))
         iArg += 1
   else:
      iterTargets = make.named_targets

   # Build all selected targets: first schedule the jobs building them, then run them.
   for tgt in iterTargets:
      make.schedule_target_jobs(tgt)
   return make.run_scheduled_jobs()


if __name__ == '__main__':
   sys.exit(_main(sys.argv))

