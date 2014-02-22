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
import make.target



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


   def schedule_jobs(self, mk, iterBlockingJobs, iterMetadataToUpdate):
      """Schedules one or more jobs that, when run, result in the execution of the tool.

      An implementation will create one or more chained ScheduledJob instances, blocking the first
      with iterBlockingJobs and returning the last one.

      The default implementation schedules a single job, the command line of which is composed by
      calling Tool._run_add_cmd_flags() and Tool._run_add_cmd_inputs().

      Make mk
         Make instance.
      iterable(make.ScheduledJob*) iterBlockingJobs
         Jobs that should block the first one scheduled for this execution of the tool (Tool
         instance).
      iterable(str*) iterMetadataToUpdate
         Paths to the files for which metadata should be updated when this job completes.
      make.ScheduledJob return
         Last job scheduled.
      """

      # Make sure that the output directory exists.
      if self._m_sOutputFilePath:
         os.makedirs(os.path.dirname(self._m_sOutputFilePath), 0o755, True)

      # Build the arguments list.
      listArgs = [self._sm_dictToolFilePaths[type(self)]]
      self._run_add_cmd_flags(listArgs)
      self._run_add_cmd_inputs(listArgs)
      return make.ScheduledJob(
         mk, iterBlockingJobs, listArgs, self._get_quiet_cmd(), iterMetadataToUpdate
      )


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
   # Abstract compiler flags (*FLAG_*).
   _m_setFlags = None
   # Additional include directories.
   _m_listIncludeDirs = None
   # See Tool._smc_sQuietName.
   _smc_sQuietName = 'C++'

   # Forces the compiler to only run the source file through the preprocessor.
   CFLAG_PREPROCESS_ONLY = 1


   def add_flags(self, *args):
      """Adds abstract flags (*FLAG_*) to the tool’s command line. The most derived specialization
      will take care of translating each flag into a command-line argument understood by a specific
      tool implementation (e.g. GCC).

      iterable(int*) *args
         Flags to turn on.
      """

      if self._m_setFlags is None:
         self._m_setFlags = set()
      for iFlag in args:
         self._m_setFlags.add(iFlag)


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

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      CxxCompiler.CFLAG_PREPROCESS_ONLY: '-E',
   }


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
      if self._m_clsFinalOutputTarget is make.target.DynLibTarget:
         listArgs.append('-fPIC')

      # Add any additional abstract flags, translating them to arguments understood by GCC.
      for iFlag in self._m_setFlags or []:
         sFlag = self._translate_abstract_flag(iFlag)
         if sFlag is None:
            raise NotImplementedError('{} does not implement abstract flag {}'.format(
               type(self), iFlag
            ))
         listArgs.append(sFlag)

      # TODO: add support for os.environ['CFLAGS'] and other vars ?
      # Add the include directories.
      for sDirPath in self._m_listIncludeDirs or []:
         listArgs.append('-I' + sDirPath)
      # Add the output file path.
      listArgs.append('-o')
      listArgs.append(self._m_sOutputFilePath)


   def _translate_abstract_flag(self, iFlag):
      """Translates an abstract flag (*FLAG_*) into a command-line argument specific to the tool
      implementation.

      int iFlag
         Abstract flag.
      str return
         Corresponding command-line argument.
      """

      return self._smc_dictAbstactToImplFlags.get(iFlag)



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
      if self._m_clsOutputTarget is make.target.DynLibTarget:
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

