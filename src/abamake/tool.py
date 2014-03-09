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

"""Classes implementing different build tools, such as C++ compilers, providing an abstract
interface to the very different implementations.
"""

import os
import re
import subprocess

import make



####################################################################################################
# Tool

class Tool(object):
   """Abstract tool."""

   # Abstract tool flags (*FLAG_*).
   _m_setAbstractFlags = None
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


   def add_flags(self, *args):
      """Adds abstract flags (*FLAG_*) to the tool’s command line. The most derived specialization
      will take care of translating each flag into a command-line argument understood by a specific
      tool implementation (e.g. GCC).

      iterable(int*) *args
         Flags to turn on.
      """

      if self._m_setAbstractFlags is None:
         self._m_setAbstractFlags = set()
      for iFlag in args:
         self._m_setAbstractFlags.add(iFlag)


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

      iterable(type*) iterSupported
         Iterable containing a class wrapper for each supported tool of the type of interest.
      type return
         Class wrapping the first detected tool among these in iterSupported.
      """

      # TODO: accept paths provided via command line.
      # TODO: apply a cross-compiler prefix.

      listTried = []
      for clsTool in iterSupported:
         iterArgs  = clsTool._smc_iterDetectArgs
         sOutMatch = clsTool._smc_sDetectPattern
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

      The default implementation applies the flags added with Tool.add_flags() after translating
      them using Tool._translate_abstract_flag().

      list(str*) listArgs
         Arguments list.
      """

      # Add any additional abstract flags, translating them to arguments understood by GCC.
      if self._m_setAbstractFlags:
         for iFlag in self._m_setAbstractFlags:
            listArgs.append(self._translate_abstract_flag(iFlag))


   def _run_add_cmd_inputs(self, listArgs):
      """Builds the input files portion of the tool’s command line.

      The default implementation adds the input file paths at the end of listArgs.

      list(str*) listArgs
         Arguments list.
      """

      # Add the source file paths, if any.
      if self._m_listInputFilePaths:
         listArgs.extend(self._m_listInputFilePaths)


   def schedule_jobs(self, mk, iterBlockingJobs, iterMetadataToUpdate):
      """Schedules one or more jobs that, when run, result in the execution of the tool.

      An implementation will create one or more chained Job instances, blocking the first with
      iterBlockingJobs and returning the last one.

      The default implementation schedules a single job, the command line of which is composed by
      calling Tool._run_add_cmd_flags() and Tool._run_add_cmd_inputs().

      Make mk
         Make instance.
      iterable(make.Job*) iterBlockingJobs
         Jobs that should block the first one scheduled for this execution of the tool (Tool
         instance).
      iterable(str*) iterMetadataToUpdate
         Paths to the files for which metadata should be updated when this job completes.
      make.Job return
         Last job scheduled.
      """

      # Make sure that the output directory exists.
      if self._m_sOutputFilePath:
         os.makedirs(os.path.dirname(self._m_sOutputFilePath), 0o755, True)

      # Make sure to update the metadata for the output file once the job completes.
      iterMetadataToUpdate = [self._m_sOutputFilePath] + (iterMetadataToUpdate or [])

      # Build the arguments list.
      listArgs = [self._sm_dictToolFilePaths[type(self)]]
      self._run_add_cmd_flags(listArgs)
      self._run_add_cmd_inputs(listArgs)

      return make.ExternalCommandJob(
         mk, iterBlockingJobs, self._get_quiet_cmd(), iterMetadataToUpdate, {
            'args': listArgs,
         }
      )


   def set_output(self, sOutputFilePath):
      """Assigns the name of the tool output.

      str sOutputFilePath
         Path to the output file to be generated by this tool.
      """

      self._m_sOutputFilePath = sOutputFilePath


   def _translate_abstract_flag(self, iFlag):
      """Translates an abstract flag (*FLAG_*) into a command-line argument specific to the tool
      implementation.

      int iFlag
         Abstract flag.
      str return
         Corresponding command-line argument.
      """

      raise NotImplementedError('{} must implement abstract flag {}'.format(type(self), iFlag))



####################################################################################################
# CxxCompiler

class CxxCompiler(Tool):
   """Abstract C++ compiler."""

   # Additional include directories.
   _m_listIncludeDirs = None
   # Macros defined via command-line arguments.
   _m_dictMacros = None
   # See Tool._smc_sQuietName.
   _smc_sQuietName = 'C++'

   # Forces the compiler to only run the source file through the preprocessor.
   CFLAG_PREPROCESS_ONLY = 2000
   # Causes the compiler to generate code suitable for a dynamic library.
   CFLAG_DYNLIB = 2001
   # Defines a preprocessor macro. Must be in str.format() syntax and include replacements “name”
   # and “expansion”, each with its respective intuitive meaning.
   CFLAG_DEFINE_FORMAT = 2002
   # Adds in directory to the include search path. Must be in str.format() syntax and include a
   # replacement “dir” with the intuitive meaning.
   CFLAG_ADD_INCLUDE_DIR_FORMAT = 2003


   def add_include_dir(self, sIncludeDirPath):
      """Adds an include directory to the compiler’s command line.

      str sIncludeDirPath
         Path to the include directory to add.
      """

      if self._m_listIncludeDirs is None:
         self._m_listIncludeDirs = []
      self._m_listIncludeDirs.append(sIncludeDirPath)


   def add_macro(self, sName, sExpansion):
      """Adds a macro definition to the compiler’s command line.

      str sName
         Name of the macro.
      str sExpansion
         Expansion (value) of the macro.
      """

      if self._m_dictMacros is None:
         self._m_dictMacros = {}
      self._m_dictMacros[sName] = sExpansion


   @classmethod
   def detect(cls):
      return Tool.detect((GxxCompiler, MscCompiler))


   def _get_quiet_cmd(self):
      """See Tool._get_quiet_cmd(). This override substitutes the output file path with the inputs,
      to show the source file path instead of the intermediate one.
      """

      iterQuietCmd = super()._get_quiet_cmd()
      return [iterQuietCmd[0]] + self._m_listInputFilePaths


   # Name suffix for intermediate object files.
   object_suffix = None


   def _run_add_cmd_flags(self, listArgs):
      """See Tool._run_add_cmd_flags()."""

      super()._run_add_cmd_flags(listArgs)

      # Add any preprocessor macros.
      if self._m_dictMacros:
         # Get the compiler-specific command-line argument to define a macro.
         sDefineFormat = self._translate_abstract_flag(self.CFLAG_DEFINE_FORMAT)
         for sName, sExpansion in self._m_dictMacros.items():
            listArgs.append(sDefineFormat.format(name = sName, expansion = sExpansion))

      # Add any additional include directories.
      if self._m_listIncludeDirs:
         # Get the compiler-specific command-line argument to define a macro.
         sAddIncludeDirFormat = self._translate_abstract_flag(self.CFLAG_ADD_INCLUDE_DIR_FORMAT)
         for sDir in self._m_listIncludeDirs:
            listArgs.append(sAddIncludeDirFormat.format(dir = sDir))



####################################################################################################
# GxxCompiler

class GxxCompiler(CxxCompiler):
   """GNU C++ compiler (G++)."""

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      CxxCompiler.CFLAG_ADD_INCLUDE_DIR_FORMAT: '-I{dir}',
      CxxCompiler.CFLAG_DEFINE_FORMAT         : '-D{name}={expansion}',
      CxxCompiler.CFLAG_DYNLIB                : '-fPIC',
      CxxCompiler.CFLAG_PREPROCESS_ONLY       : '-E',
   }
   # Arguments to invoke this tool with in order to detect its presence.
   _smc_iterDetectArgs = ('g++', '--version')
   # Pattern to compare the output of _smc_iterDetectArgs against.
   _smc_sDetectPattern = r'^g\+\+.*(?P<ver>[.0-9]+)$'


   def __init__(self):
      """Constructor. See Linker.__init__()."""

      super().__init__()
      # TODO: remove hardcoded dirs.
      self.add_include_dir('include')


   # See CxxCompiler.object_suffix.
   object_suffix = '.o'


   def _run_add_cmd_flags(self, listArgs):
      """See CxxCompiler._run_add_cmd_flags()."""

      # Add flags.
      listArgs.extend([
         '-c', '-std=c++0x', '-fnon-call-exceptions', '-fvisibility=hidden'
      ])
      super()._run_add_cmd_flags(listArgs)
      listArgs.extend([
         '-ggdb', '-O0', '-DDEBUG=1'
      ])
      listArgs.extend([
         '-Wall', '-Wextra', '-pedantic', '-Wundef', '-Wshadow', '-Wconversion',
         '-Wsign-conversion', '-Wlogical-op', '-Wmissing-declarations', '-Wpacked',
         '-Wunreachable-code', '-Winline'
      ])

      # TODO: add support for os.environ['CFLAGS'] and other vars ?

      # Add the output file path.
      listArgs.append('-o')
      listArgs.append(self._m_sOutputFilePath)


   def _translate_abstract_flag(self, iFlag):
      """See CxxCompiler._translate_abstract_flag()."""

      sFlag = self._smc_dictAbstactToImplFlags.get(iFlag)
      if sFlag is None:
         sFlag = super()._translate_abstract_flag(iFlag)
      return sFlag



####################################################################################################
# MscCompiler

class MscCompiler(CxxCompiler):
   """Microsoft C/C++ compiler (MSC)."""

   # Arguments to invoke this tool with in order to detect its presence.
   _smc_iterDetectArgs = ('cl', '/?')
   # Pattern to compare the output of _smc_iterDetectArgs against.
   _smc_sDetectPattern = r'^Microsoft \(R\).* Optimizing Compiler Version (?P<ver>[.0-9]+) for ' + \
                         r'(?P<target>\S+)$'

   # See CxxCompiler.object_suffix.
   object_suffix = '.obj'



####################################################################################################
# Linker

class Linker(Tool):
   """Abstract object code linker."""

   # Additional libraries to link to.
   _m_listInputLibs = None
   # Directories to be included in the library search path.
   _m_listLibPaths = None
   # See Tool._smc_sQuietName.
   _smc_sQuietName = 'LINK'


   # Tells the linker to generate a dynamic library instead of a stand-alone executable.
   LDFLAG_DYNLIB = 5000


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


   @classmethod
   def detect(cls):
      return Tool.detect((GnuLinker, MsLinker))



####################################################################################################
# GnuLinker

class GnuLinker(Linker):
   """GCC-driven GNU object code linker (LD)."""

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      Linker.LDFLAG_DYNLIB: '-shared',
   }
   # Arguments to invoke this tool with in order to detect its presence.
   _smc_iterDetectArgs = ('g++', '-Wl,--version')
   # Pattern to compare the output of _smc_iterDetectArgs against.
   _smc_sDetectPattern = r'^GNU ld .*?(?P<ver>[.0-9]+)$'


   def _run_add_cmd_flags(self, listArgs):
      """See Linker._run_add_cmd_flags()."""

      super()._run_add_cmd_flags(listArgs)

      listArgs.append('-Wl,--as-needed')
      listArgs.append('-ggdb')
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


   def _translate_abstract_flag(self, iFlag):
      """See Linker._translate_abstract_flag()."""

      sFlag = self._smc_dictAbstactToImplFlags.get(iFlag)
      if sFlag is None:
         sFlag = super()._translate_abstract_flag(iFlag)
      return sFlag



####################################################################################################
# MsLinker

class MsLinker(Linker):
   """Microsoft linker (Link)."""

   # Arguments to invoke this tool with in order to detect its presence.
   _smc_iterDetectArgs = ('link', '/?')
   # Pattern to compare the output of _smc_iterDetectArgs against.
   _smc_sDetectPattern = r'^Microsoft \(R\) Incremental Linker Version (?P<ver>[.0-9]+)$'

