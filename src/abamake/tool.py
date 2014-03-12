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
import make.job



####################################################################################################
# Tool

class Tool(object):
   """Abstract tool."""

   # Abstract tool flags (*FLAG_*).
   _m_setAbstractFlags = None
   # Default derived class to instantiate when a specific one is not required. Detected and set by
   # calling Tool._detect() on a subclass and passing a list of its own subclasses as argument.
   _sm_clsDefaultDerived = None
   # Path to this tool’s executable. Detected and set by Tool._detect().
   _sm_sFilePath = None
   # Files to be processed by the tool.
   _m_listInputFilePaths = None
   # See Tool.output_file_path.
   _m_sOutputFilePath = None
   # Short name of the tool, to be displayed in quiet mode. If None, the tool file name will be
   # displayed.
   _smc_sQuietName = None
   # Environment block (dictionary) modified to force programs to display output in US English.
   _sm_dictUSEngEnv = None

   # Specifies an output file path. Must be in str.format() syntax and include a replacement “path”
   # with the intuitive meaning.
   FLAG_OUTPUT_PATH_FORMAT = 1000


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
   def get_default_impl(cls):
      """Returns the default implementation for this base class. For example, if GCC is detected,
      CxxCompiler.get_default_impl() will return GxxCompiler as CxxCompiler’s default implementation
      class.

      type return
         Default implementation of this class.
      """

      if cls._sm_clsDefaultDerived is None:
         # Attempt to detect the presence of a derived class’s executable.
         # TODO: accept paths provided via command line.
         # TODO: apply a cross-compiler prefix.

         # Make sure we have a US English environment dictionary.
         if Tool._sm_dictUSEngEnv is None:
            # Copy the current environment and add to it a locale override for US English.
            Tool._sm_dictUSEngEnv = os.environ.copy()
            Tool._sm_dictUSEngEnv['LC_ALL'] = 'en_US.UTF-8'

         for clsDeriv in cls.__subclasses__():
            iterArgs  = clsDeriv._smc_iterDetectArgs
            sOutMatch = clsDeriv._smc_sDetectPattern
            try:
               with subprocess.Popen(
                  iterArgs, env = Tool._sm_dictUSEngEnv,
                  stdout = subprocess.PIPE, stderr = subprocess.PIPE, universal_newlines = True
               ) as procTool:
                  sOut, sErr = procTool.communicate()
            except FileNotFoundError:
               # This just means that the program is not installed; move on to the next candidate.
               continue
            if re.search(sOutMatch, sOut, re.MULTILINE):
               # Store the file path in clsDeriv and clsDeriv as cls’s default implementation.
               clsDeriv._sm_sFilePath = iterArgs[0]
               cls._sm_clsDefaultDerived = clsDeriv
               break
         else:
            # No supported executable found: raise an exception with a list of possibilities.
            raise Exception(
               'unable to detect default implementation for {}; expected one of:\n'.format(
                  cls.__name__
               ) +
               '\n'.join(['  {:7}  {}'.format(
                  clsDeriv._smc_iterDetectArgs[0], clsDeriv.__doc__.lstrip('.')
               ) for clsDeriv in cls.__subclasses__()])
            )

      return cls._sm_clsDefaultDerived


   def _get_quiet_cmd(self):
      """Returns an iterable containing the short name and relevant (input or output) files for the
      tool, to be displayed in quiet mode.

      iterable(str, str*) return
         Iterable containing the quiet command name and the output file path(s).
      """

      if self._smc_sQuietName is None:
         sQuietName = os.path.basename(self._sm_sFilePath)
      else:
         sQuietName = self._smc_sQuietName
      return sQuietName, (self._m_sOutputFilePath or '')


   def _set_output_file_path(self, sOutputFilePath):
      self._m_sOutputFilePath = sOutputFilePath

   output_file_path = property(fset = _set_output_file_path, doc = """
      Path to the output file to be generated by this tool.
   """)


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
      iterable(make.job.Job*) iterBlockingJobs
         Jobs that should block the first one scheduled for this execution of the tool (Tool
         instance).
      iterable(str*) iterMetadataToUpdate
         Paths to the files for which metadata should be updated when this job completes.
      make.job.Job return
         Last job scheduled.
      """

      # Build the arguments list.
      listArgs = [self._sm_sFilePath]

      self._run_add_cmd_flags(listArgs)

      if self._m_sOutputFilePath:
         if not mk.dry_run:
            # Make sure that the output directory exists.
            os.makedirs(os.path.dirname(self._m_sOutputFilePath), 0o755, True)
         # Make sure to update the metadata for the output file once the job completes.
         if iterMetadataToUpdate is None:
            iterMetadataToUpdate = []
         iterMetadataToUpdate.append(self._m_sOutputFilePath)
         # Get the compiler-specific command-line argument to specify an output file path.
         sFormat = self._translate_abstract_flag(self.FLAG_OUTPUT_PATH_FORMAT)
         # Add the output file path.
         listArgs.append(sFormat.format(path = self._m_sOutputFilePath))

      self._run_add_cmd_inputs(listArgs)

      return make.job.ExternalCommandJob(
         mk, iterBlockingJobs, self._get_quiet_cmd(), iterMetadataToUpdate, {
            'args': listArgs,
         }
      )


   def _translate_abstract_flag(self, iFlag):
      """Translates an abstract flag (*FLAG_*) into a command-line argument specific to the tool
      implementation using a class-specific _smc_dictAbstactToImplFlags dictionary.

      int iFlag
         Abstract flag.
      str return
         Corresponding command-line argument.
      """

      sFlag = type(self)._smc_dictAbstactToImplFlags.get(iFlag)
      if sFlag is None:
         raise NotImplementedError('{} must implement abstract flag {}'.format(type(self), iFlag))
      return sFlag



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
   # Adds a directory to the include search path. Must be in str.format() syntax and include a
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


   def add_macro(self, sName, sExpansion = ''):
      """Adds a macro definition to the compiler’s command line.

      str sName
         Name of the macro.
      str sExpansion
         Expansion (value) of the macro.
      """

      if self._m_dictMacros is None:
         self._m_dictMacros = {}
      self._m_dictMacros[sName] = sExpansion


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

      # TODO: remove hardcoded dirs.
      self.add_include_dir('include')

      super()._run_add_cmd_flags(listArgs)

      # Add any preprocessor macros.
      if self._m_dictMacros:
         # Get the compiler-specific command-line argument to define a macro.
         sFormat = self._translate_abstract_flag(self.CFLAG_DEFINE_FORMAT)
         for sName, sExpansion in self._m_dictMacros.items():
            listArgs.append(sFormat.format(name = sName, expansion = sExpansion))

      # Add any additional include directories.
      if self._m_listIncludeDirs:
         # Get the compiler-specific command-line argument to add an include directory.
         sFormat = self._translate_abstract_flag(self.CFLAG_ADD_INCLUDE_DIR_FORMAT)
         for sDir in self._m_listIncludeDirs:
            listArgs.append(sFormat.format(dir = sDir))



####################################################################################################
# GxxCompiler

class GxxCompiler(CxxCompiler):
   """GNU C++ compiler (G++)."""

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT            : '-o{path}',
      CxxCompiler.CFLAG_ADD_INCLUDE_DIR_FORMAT: '-I{dir}',
      CxxCompiler.CFLAG_DEFINE_FORMAT         : '-D{name}={expansion}',
      CxxCompiler.CFLAG_DYNLIB                : '-fPIC',
      CxxCompiler.CFLAG_PREPROCESS_ONLY       : '-E',
   }
   # Arguments to invoke this tool with in order to detect its presence.
   _smc_iterDetectArgs = ('g++', '--version')
   # Pattern to compare the output of _smc_iterDetectArgs against.
   _smc_sDetectPattern = r'^g\+\+.*(?P<ver>[.0-9]+)$'


   # See CxxCompiler.object_suffix.
   object_suffix = '.o'


   def _run_add_cmd_flags(self, listArgs):
      """See CxxCompiler._run_add_cmd_flags()."""

      listArgs.extend([
         '-c',                     # Compile without linking.
         '-std=c++0x',             # Select C++11 language standard.
         '-fnon-call-exceptions',  # Allow trapping instructions to throw exceptions.
         '-fvisibility=hidden',    # Set default ELF symbol visibility to “hidden”.
      ])

      super()._run_add_cmd_flags(listArgs)

      listArgs.extend([
         '-ggdb',                  # Generate debug info compatible with GDB.
         '-O0',                    # Disable code optimization.
         '-DDEBUG=1',              # Enable debug code.
      ])
      listArgs.extend([
         '-Wall',                  # Enable more warnings.
         '-Wextra',                # Enable extra warnings not enabled by -Wall.
         '-pedantic',              # Issue all the warnings demanded by strict ISO C++.
         '-Wconversion',           # Warn for implicit conversions that may alter a value.
         '-Winline',               # Warn if a function declared as inline cannot be inlined.
         '-Wlogical-op',           # Warn about suspicious uses of logical operators in expressions.
         '-Wmissing-declarations', # Warn if a global function is defined without a previous
                                   # declaration.
         '-Wpacked',               # Warn if a struct has “packed” attribute but that has no effect
                                   # on its layout or size.
         '-Wshadow',               # Warn when a local symbol shadows another symbol.
         '-Wsign-conversion',      # Warn for implicit conversions that may change the sign of an
                                   # integer value.
         '-Wundef',                # Warn if an undefined identifier is evaluated in “#if”.
      ])

      # TODO: add support for os.environ['CFLAGS'] and other vars ?



####################################################################################################
# MscCompiler

class MscCompiler(CxxCompiler):
   """Microsoft C/C++ compiler (MSC)."""

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT            : '/Fo{path}',
      CxxCompiler.CFLAG_ADD_INCLUDE_DIR_FORMAT: '/I{dir}',
      CxxCompiler.CFLAG_DEFINE_FORMAT         : '/D{name}={expansion}',
      CxxCompiler.CFLAG_DYNLIB                : '/LD',
      CxxCompiler.CFLAG_PREPROCESS_ONLY       : '/P',
   }
   # Arguments to invoke this tool with in order to detect its presence.
   _smc_iterDetectArgs = ('cl', '/?')
   # Pattern to compare the output of _smc_iterDetectArgs against.
   _smc_sDetectPattern = r'^Microsoft \(R\).* Optimizing Compiler Version (?P<ver>[.0-9]+) for ' + \
                         r'(?P<target>\S+)$'

   # See CxxCompiler.object_suffix.
   object_suffix = '.obj'


   def _run_add_cmd_flags(self, listArgs):
      """See CxxCompiler._run_add_cmd_flags()."""

      listArgs.extend([
         '/nologo',   # Suppress brand banner display.
         '/c',        # Compile without linking.
         '/TP',       # Force all sources to be compiled as C++.
         '/EHa',      # Allow catching synchronous (C++) and asynchronous (SEH) exceptions.
      ])

      super()._run_add_cmd_flags(listArgs)

      listArgs.extend([
         '/Zi',       # Generate debug info for PDB.
         '/Od',       # Disable code optimization.
         '/DDEBUG=1', # Enable debug code.
      ])
      listArgs.extend([
         '/Wall',     # Enable all warnings.
      ])



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
   # Adds a directory to the library search path. Must be in str.format() syntax and include a
   # replacement “dir” with the intuitive meaning.
   LDFLAG_ADD_LIB_DIR_FORMAT = 5001
   # Adds a library to link to. Must be in str.format() syntax and include a replacement “lib” with
   # the intuitive meaning.
   LDFLAG_ADD_LIB_FORMAT = 5002


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


   def _run_add_cmd_inputs(self, listArgs):
      """See Tool._run_add_cmd_inputs()."""

      super()._run_add_cmd_inputs(listArgs)

      # Add the library search directories.
      if self._m_listLibPaths:
         # Get the compiler-specific command-line argument to add a library directory.
         sFormat = self._translate_abstract_flag(self.LDFLAG_ADD_LIB_DIR_FORMAT)
         for sDir in self._m_listLibPaths:
            listArgs.append(sFormat.format(dir = sDir))
      # Add the libraries.
      if self._m_listInputLibs:
         # Get the compiler-specific command-line argument to add a library.
         sFormat = self._translate_abstract_flag(self.LDFLAG_ADD_LIB_FORMAT)
         for sLib in self._m_listInputLibs:
            listArgs.append(sFormat.format(lib = sLib))



####################################################################################################
# GnuLinker

class GnuLinker(Linker):
   """GCC-driven GNU object code linker (LD)."""

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT    : '-o{path}',
      Linker.LDFLAG_ADD_LIB_DIR_FORMAT: '-L{dir}',
      Linker.LDFLAG_ADD_LIB_FORMAT    : '-l{lib}',
      Linker.LDFLAG_DYNLIB            : '-shared',
   }
   # Arguments to invoke this tool with in order to detect its presence.
   _smc_iterDetectArgs = ('g++', '-Wl,--version')
   # Pattern to compare the output of _smc_iterDetectArgs against.
   _smc_sDetectPattern = r'^GNU ld .*?(?P<ver>[.0-9]+)$'


   def _run_add_cmd_flags(self, listArgs):
      """See Linker._run_add_cmd_flags()."""

      super()._run_add_cmd_flags(listArgs)

      listArgs.extend([
         '-Wl,--as-needed', # Only link to libraries containing symbols actually used.
      ])
      listArgs.extend([
         '-ggdb',           # Generate debug info compatible with GDB.
      ])

      # TODO: add support for os.environ['LDFLAGS'] ?


   def _run_add_cmd_inputs(self, listArgs):
      """See Linker._run_add_cmd_inputs()."""

      # TODO: should not assume that GNU LD will only be used to build for POSIX; the default
      # libraries list should come from a Platform class.
      self.add_input_lib('dl')
      self.add_input_lib('pthread')

      super()._run_add_cmd_inputs(listArgs)



####################################################################################################
# MsLinker

class MsLinker(Linker):
   """Microsoft linker (Link)."""

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT    : '/OUT:{path}',
      Linker.LDFLAG_ADD_LIB_DIR_FORMAT: '/LIBPATH:{dir}',
      Linker.LDFLAG_ADD_LIB_FORMAT    : '{lib}',
      Linker.LDFLAG_DYNLIB            : '/DLL',
   }
   # Arguments to invoke this tool with in order to detect its presence.
   _smc_iterDetectArgs = ('link', '/?')
   # Pattern to compare the output of _smc_iterDetectArgs against.
   _smc_sDetectPattern = r'^Microsoft \(R\) Incremental Linker Version (?P<ver>[.0-9]+)$'


   def _run_add_cmd_flags(self, listArgs):
      """See Linker._run_add_cmd_flags()."""

      listArgs.extend([
         '/nologo',              # Suppress brand banner display.
      ])

      super()._run_add_cmd_flags(listArgs)

      sPdbFilePath = os.path.splitext(self._m_sOutputFilePath)[0] + '.pdb'
      listArgs.extend([
         '/DEBUG',               # Keep debug info.
         '/PDB:' + sPdbFilePath, # Create a program database file (PDB).
      ])

