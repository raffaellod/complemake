#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013, 2014
# Raffaello D. Di Napoli
#
# This file is part of Abaclade.
#
# Abaclade is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Abaclade is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
# the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Abaclade. If not, see
# <http://www.gnu.org/licenses/>.
#---------------------------------------------------------------------------------------------------

"""Classes implementing different build tools, such as C++ compilers, providing an abstract
interface to the very different implementations.
"""

import os
import re
import subprocess

import abamake
import abamake.job
import abamake.logging


####################################################################################################
# Tool

class AbstractFlag(object):
   """Declares a unique abstract tool flag."""

   def __str__(self):
      """Returns the member name, in the containing class, of the abstract flag.

      Implemented by searching for self in every abamake.tool.Tool-derived class, and returning the
      corresponding member name when found.

      str return
         Flag name.
      """

      sAttr = self._get_self_in_class(Tool)
      if sAttr:
         return sAttr
      for cls in abamake.derived_classes(Tool):
         sAttr = self._get_self_in_class(cls)
         if sAttr:
            return sAttr
      return '(UNKNOWN)'

   def _get_self_in_class(self, cls):
      """Searches for self among the members of the specified class, returning the corresponding
      attribute name if found.

      type cls
         Class to search.
      str return
         Fully-qualified attribute name if self is a member of cls, or None otherwise.
      """

      for sAttr in cls.__dict__:
         if getattr(cls, sAttr) is self:
            return '{}.{}'.format(cls.__name__, sAttr)
      return None

####################################################################################################
# Tool

class Tool(object):
   """Abstract tool."""

   # Abstract tool flags (*FLAG_*).
   _m_setAbstractFlags = None
   # Default file name for the tool.
   _smc_sDefaultFileName = None
   # Associates SystemTypes to paths to this a tool’s executable (SystemType => str).
   _sm_dictFilePaths = None
   # Files to be processed by the tool.
   _m_listInputFilePaths = None
   # See Tool.output_file_path.
   _m_sOutputFilePath = None
   # Short name of the tool, to be displayed in quiet mode. If None, the tool file name will be
   # displayed.
   _smc_sQuietName = None
   # Target system type.
   _m_st = None
   # Environment block (dictionary) modified to force programs to display output in US English.
   _sm_dictUSEngEnv = None

   # Specifies an output file path. Must be in str.format() syntax and include a replacement “path”
   # with the intuitive meaning.
   FLAG_OUTPUT_PATH_FORMAT = AbstractFlag()

   def __init__(self, st):
      """Constructor.

      abamake.platform.SystemType st
         Target system type.
      """

      self._m_setAbstractFlags = set()
      self._m_listInputFilePaths = []
      self._m_st = st

   def add_flags(self, *iterArgs):
      """Adds abstract flags (*FLAG_*) to the tool’s command line. The most derived specialization
      will take care of translating each flag into a command-line argument understood by a specific
      tool implementation (e.g. GCC).

      iterable(abamake.tool.AbstractFlag*) *iterArgs
         Flags to turn on.
      """

      for flag in iterArgs:
         self._m_setAbstractFlags.add(flag)

   def add_input(self, sInputFilePath):
      """Adds an input file to the tool input set. Duplicates are not discarded.

      str sInputFilePath
         Path to the input file.
      """

      self._m_listInputFilePaths.append(sInputFilePath)

   @classmethod
   def _add_exe_to_system_type_cache(cls, st, sFilePath):
      """Saves the path to the version of the tool that targets st.

      abamake.platform.SystemType st
         Target system type.
      str sFilePath
         Path to the executable file.
      """

      dictFilePaths = cls._sm_dictFilePaths
      if not dictFilePaths:
         dictFilePaths = {}
         cls._sm_dictFilePaths = dictFilePaths
      dictFilePaths[st] = sFilePath

   def create_job(self, mk, tgt):
      """Returns a job that, when run, results in the execution of the tool.

      The default implementation schedules a job whose command line is composed by calling
      Tool._create_job_add_flags() and Tool._create_job_add_inputs().

      abamake.Make mk
         Make instance.
      abamake.target.Target tgt
         Target that this job will build.
      abamake.job.Job return
         Job scheduled.
      """

      # Build the arguments list.
      listArgs = [type(self)._get_exe_from_system_type_cache(self._m_st)]

      self._create_job_add_flags(listArgs)

      if self._m_sOutputFilePath:
         if not mk.job_controller.dry_run:
            # Make sure that the output directory exists.
            abamake.makedirs(os.path.dirname(self._m_sOutputFilePath))
         # Get the compiler-specific command-line argument to specify an output file path.
         sFormat = self._translate_abstract_flag(self.FLAG_OUTPUT_PATH_FORMAT)
         # Add the output file path.
         listArgs.append(sFormat.format(path = self._m_sOutputFilePath))

      self._create_job_add_inputs(listArgs)

      dictPopenArgs = {
         'args': listArgs,
      }
      return self._create_job_instance(
         self._get_quiet_cmd(), dictPopenArgs, tgt._m_mk().log, tgt.build_log_path
      )

   def _create_job_add_flags(self, listArgs):
      """Builds the flags portion of the tool’s command line.

      The default implementation applies the flags added with Tool.add_flags() after translating
      them using Tool._translate_abstract_flag().

      list(str*) listArgs
         Arguments list.
      """

      # Add any additional abstract flags, translating them to arguments understood by GCC.
      if self._m_setAbstractFlags:
         for flag in self._m_setAbstractFlags:
            listArgs.append(self._translate_abstract_flag(flag))

   def _create_job_add_inputs(self, listArgs):
      """Builds the input files portion of the tool’s command line.

      The default implementation adds the input file paths at the end of listArgs.

      list(str*) listArgs
         Arguments list.
      """

      # Add the source file paths, if any.
      if self._m_listInputFilePaths:
         listArgs.extend(self._m_listInputFilePaths)

   def _create_job_instance(self, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath):
      """Returns an new abamake.job.ExternalCmdJob instance constructed with the provided arguments.
      It allows subclasses to customize the job creation.

      iterable(str, str*) iterQuietCmd
         See iterQuietCmd argument in abamake.job.ExternalCmdJob.__init__().
      dict(str: object) dictPopenArgs
         See dictPopenArgs argument in abamake.job.ExternalCmdJob.__init__().
      abamake.logging.Logger log
         See log argument in abamake.job.ExternalCmdJob.__init__().
      str sStdErrFilePath
         See sStdErrFilePath argument in abamake.job.ExternalCmdJob.__init__().
      abamake.job.ExternalCmdJob return
         Newly instantiated job.
      """

      return abamake.job.ExternalCmdJob(iterQuietCmd, dictPopenArgs, log, sStdErrFilePath)

   class default_file_name(object):
      """Decorator used to specify a default executable name for a Tool subclass. The specified file
      name will be used by Tool.get_impl_for_system_type() if no file path is provided to it.

      str sFileName
         Tool’s executable file name.
      """

      def __init__(self, sFileName):
         self._m_sFileName = sFileName

      def __call__(self, cls):
         cls._smc_sDefaultFileName = self._m_sFileName
         return cls

   @classmethod
   def _exe_matches_tool_and_system_type(cls, st, sFilePath):
      """Returns True if the specified executable file is modeled by the tool, and if that
      executable supports targeting the specified system type.

      The default implementation always returns False.

      abamake.platform.SystemType st
         System type.
      str sFilePath
         Path to the tool’s executable file.
      bool return
         True if a version of the tool supports st, or False otherwise.
      """

      return False

   @classmethod
   def _get_cmd_output(cls, iterArgs):
      """Runs the specified command and returns its combined stdout and stderr.

      iterable(str+) iterArgs
         Command line to invoke.
      str return
         Output of the program.
      """

      # Make sure we have a US English environment dictionary.
      dictUSEngEnv = cls._sm_dictUSEngEnv
      if not dictUSEngEnv:
         # Copy the current environment and add to it a locale override for US English.
         dictUSEngEnv = os.environ.copy()
         dictUSEngEnv['LC_ALL'] = 'en_US.UTF-8'
         cls._sm_dictUSEngEnv = dictUSEngEnv

      try:
         return subprocess.Popen(
            iterArgs, env = dictUSEngEnv,
            stdout = subprocess.PIPE, stderr = subprocess.STDOUT, universal_newlines = True
         ).communicate()[0].rstrip('\r\n')
      except (abamake.FileNotFoundErrorCompat, OSError):
         # Could not execute the program.
         return None

   @classmethod
   def _get_exe_from_system_type_cache(cls, st):
      """Returns the path to the version of the tool that targets st, if any was ever cached.

      abamake.platform.SystemType st
         Target system type.
      str return
         Path to the executable file.
      """

      dictFilePaths = cls._sm_dictFilePaths
      return dictFilePaths and dictFilePaths.get(st)

   @classmethod
   def get_impl_for_system_type(cls, st, sFilePath = None):
      """Detects if a tool of the type of this class (e.g. a C++ compiler for
      abamake.tool.CxxCompiler) exists for the specified system type, returning the corresponding
      implementation class (e.g. abamake.tool.GxxCompiler if G++ for that system type is installed).

      If an executable file path is specified, this method will just find an implementation class
      for it, instead of checking whether each class’s tool is installed.

      abamake.platform.SystemType st
         System type for which the tool is needed.
      str sFilePath
         Path to the tool’s executable file, or None if the tool should be detected automatically.
      type return
         Matching abamake.tool.Tool subclass for the tool found or specified.
      """

      for clsDeriv in abamake.derived_classes(cls):
         if sFilePath:
            # Explicit file path: only a match if it’s the correct tool and it supports st.
            if clsDeriv._exe_matches_tool_and_system_type(st, sFilePath):
               return clsDeriv
         elif cls._get_exe_from_system_type_cache(st):
            # Implicit cached file name: always a match.
            return clsDeriv
         else:
            # No implicit or explicit file name: attempt to detect it.
            sFileName = clsDeriv._smc_sDefaultFileName
            if clsDeriv._exe_matches_tool_and_system_type(st, sFileName):
               # Match: cache the file name/path.
               cls._add_exe_to_system_type_cache(st, sFileName)
               return clsDeriv
      raise Exception('unable to detect {} tool for system type {}'.format(cls.__name__, st))

   def _get_quiet_cmd(self):
      """Returns an iterable containing the short name and relevant (input or output) files for the
      tool, to be displayed in quiet mode.

      iterable(str, str*) return
         Iterable containing the quiet command name and the output file path(s).
      """

      return self._smc_sQuietName, (self._m_sOutputFilePath or '')

   def _set_output_file_path(self, sOutputFilePath):
      self._m_sOutputFilePath = sOutputFilePath

   output_file_path = property(fset = _set_output_file_path, doc = """
      Path to the output file to be generated by this tool.
   """)

   def _translate_abstract_flag(self, flag):
      """Translates an abstract flag (*FLAG_*) into a command-line argument specific to the tool
      implementation using a class-specific _smc_dictAbstactToImplFlags dictionary.

      abamake.tool.AbstractFlag flag
         Abstract flag.
      str return
         Corresponding command-line argument.
      """

      sFlag = type(self)._smc_dictAbstactToImplFlags.get(flag)
      if sFlag is None:
         raise NotImplementedError(
            'class {} must define a mapping for abstract flag {}'.format(type(self).__name__, flag)
         )
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
   CFLAG_PREPROCESS_ONLY = AbstractFlag()
   # Causes the compiler to generate code suitable for a dynamic library.
   CFLAG_DYNLIB = AbstractFlag()
   # Defines a preprocessor macro. Must be in str.format() syntax and include replacements “name”
   # and “expansion”, each with its respective intuitive meaning.
   CFLAG_DEFINE_FORMAT = AbstractFlag()
   # Adds a directory to the include search path. Must be in str.format() syntax and include a
   # replacement “dir” with the intuitive meaning.
   CFLAG_ADD_INCLUDE_DIR_FORMAT = AbstractFlag()

   def __init__(self, st):
      """See Tool.__init__()."""

      Tool.__init__(self, st)

      self._m_listIncludeDirs = []
      self._m_dictMacros = {}

   def add_include_dir(self, sIncludeDirPath):
      """Adds an include directory to the compiler’s command line.

      str sIncludeDirPath
         Path to the include directory to add.
      """

      self._m_listIncludeDirs.append(sIncludeDirPath)

   def add_macro(self, sName, sExpansion = ''):
      """Adds a macro definition to the compiler’s command line.

      str sName
         Name of the macro.
      str sExpansion
         Expansion (value) of the macro.
      """

      self._m_dictMacros[sName] = sExpansion

   def _create_job_add_flags(self, listArgs):
      """See Tool._create_job_add_flags()."""

      # TODO: remove hard-coded dirs.
      self.add_include_dir('include')

      Tool._create_job_add_flags(self, listArgs)

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

   def _get_quiet_cmd(self):
      """See Tool._get_quiet_cmd(). This override substitutes the output file path with the inputs,
      to show the source file path instead of the intermediate one.
      """

      iterQuietCmd = Tool._get_quiet_cmd(self)

      return [iterQuietCmd[0]] + self._m_listInputFilePaths

   # Name suffix for intermediate object files.
   object_suffix = None

####################################################################################################
# ClangxxCompiler

@Tool.default_file_name('clang++')
class ClangxxCompiler(CxxCompiler):
   """Clang C++ compiler."""

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT            : '-o{path}',
      CxxCompiler.CFLAG_ADD_INCLUDE_DIR_FORMAT: '-I{dir}',
      CxxCompiler.CFLAG_DEFINE_FORMAT         : '-D{name}={expansion}',
      CxxCompiler.CFLAG_DYNLIB                : '-fPIC',
      CxxCompiler.CFLAG_PREPROCESS_ONLY       : '-E',
   }

   # See CxxCompiler.object_suffix.
   def _create_job_add_flags(self, listArgs):
      """See CxxCompiler._create_job_add_flags()."""

      listArgs.extend([
         '-c',                     # Compile without linking.
         '-std=c++11',             # Select C++11 language standard.
         '-fvisibility=hidden',    # Set default ELF symbol visibility to “hidden”.
      ])

      CxxCompiler._create_job_add_flags(self, listArgs)

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

   @classmethod
   def _exe_matches_tool_and_system_type(cls, st, sFilePath):
      """See CxxCompiler._exe_matches_tool_and_system_type()."""

      sOut = Tool._get_cmd_output((sFilePath, '-v'))
      if not sOut:
         return False

      # Verify that it’s indeed Clang.
      match = re.search(r'^clang version (?P<ver>[^ ]+)(?: .*)?$', sOut, re.MULTILINE)
      if not match:
         return False

      # Verify that this compiler supports the specified system type.
      match = re.search(r'^Target: (?P<target>.*)$', sOut, re.MULTILINE)
      if not match:
         return False
      try:
         stSupported = abamake.platform.SystemType.parse_tuple(match.group('target'))
      except abamake.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return False
      # This is not a strict equality test.
      return st == stSupported

   object_suffix = '.o'

####################################################################################################
# GxxCompiler

@Tool.default_file_name('g++')
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

   # See CxxCompiler.object_suffix.
   def _create_job_add_flags(self, listArgs):
      """See CxxCompiler._create_job_add_flags()."""

      listArgs.extend([
         '-c',                     # Compile without linking.
         '-std=c++0x',             # Select C++11 language standard.
         '-fnon-call-exceptions',  # Allow trapping instructions to throw exceptions.
         '-fvisibility=hidden',    # Set default ELF symbol visibility to “hidden”.
      ])

      CxxCompiler._create_job_add_flags(self, listArgs)

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

   @classmethod
   def _exe_matches_tool_and_system_type(cls, st, sFilePath):
      """See CxxCompiler._exe_matches_tool_and_system_type()."""

      sOut = Tool._get_cmd_output((sFilePath, '--version'))
      if not sOut:
         return False

      # Verify that it’s indeed G++.
      match = re.search(r'^g\+\+.*?(?P<ver>[.0-9]+)$', sOut, re.MULTILINE)
      if not match:
         return False

      # Verify that this compiler supports the specified system type.
      sOut = Tool._get_cmd_output((sFilePath, '-dumpmachine'))
      if not sOut:
         return False
      try:
         stSupported = abamake.platform.SystemType.parse_tuple(sOut)
      except abamake.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return False
      # This is not a strict equality test.
      return st == stSupported

   object_suffix = '.o'

####################################################################################################
# MscCompiler

@Tool.default_file_name('cl')
class MscCompiler(CxxCompiler):
   """Microsoft C/C++ compiler (MSC).

   For a list of recognized command-line arguments, see <http://msdn.microsoft.com/en-us/library/
   fwkeyyhe%28v=vs.100%29.aspx>.
   """

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT            : '/Fo{path}',
      CxxCompiler.CFLAG_ADD_INCLUDE_DIR_FORMAT: '/I{dir}',
      CxxCompiler.CFLAG_DEFINE_FORMAT         : '/D{name}={expansion}',
      CxxCompiler.CFLAG_DYNLIB                : '/LD',
      CxxCompiler.CFLAG_PREPROCESS_ONLY       : '/P',
   }

   def _create_job_add_flags(self, listArgs):
      """See CxxCompiler._create_job_add_flags()."""

      listArgs.extend([
         '/c',         # Compile without linking.
         '/EHa',       # Allow catching synchronous (C++) and asynchronous (SEH) exceptions.
#        '/MD',        # Use the multithreaded runtime DLL.
         '/MDd',       # Use the multithreaded debug runtime DLL.
         '/nologo',    # Suppress brand banner display.
         '/TP',        # Force all sources to be compiled as C++.
      ])

      CxxCompiler._create_job_add_flags(self, listArgs)

      if CxxCompiler.CFLAG_PREPROCESS_ONLY in self._m_setAbstractFlags:
         listArgs.extend([
            '/Fi' + self._m_sOutputFilePath, # cl.exe requires a separate argument to specify the
                       # preprocessed output file path.
            '/wd4668', # Suppress “'macro' is not defined as a preprocessor macro, replacing with
                       # '0' for '#if/#elif'”. Somehow cl.exe /P will ignore a supposedly equivalent
                       # #pragma in a header file. This occurs in MS-provided header files.
         ])

      listArgs.extend([
         '/DDEBUG=1',  # Enable debug code.
         '/Od',        # Disable code optimization.
         '/Z7',        # Generate debug info for PDB, stored in the .obj file.
      ])
      listArgs.extend([
         '/Wall',      # Enable all warnings.
      ])

   def _create_job_instance(self, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath):
      """See CxxCompiler._create_job_instance()."""

      # cl.exe logs to stdout instead of stderr.
      dictPopenArgs['stderr'] = subprocess.STDOUT

      # cl.exe has the annoying habit of printing the file name we asked it to compile; create a
      # filtered logger to hide it.
      log = abamake.logging.FilteredLogger(log)
      log.add_exclusion(os.path.basename(self._m_listInputFilePaths[0]))

      return CxxCompiler._create_job_instance(
         self, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath
      )

   @classmethod
   def _exe_matches_tool_and_system_type(cls, st, sFilePath):
      """See CxxCompiler._exe_matches_tool_and_system_type()."""

      sOut = Tool._get_cmd_output((sFilePath, '/?'))
      if not sOut:
         return False

      reVersion = re.compile(
         r'^Microsoft \(R\).*? Optimizing Compiler Version (?P<ver>[.0-9]+) for (?P<target>\S+)$',
         re.MULTILINE
      )

      # TODO: verify that match('target') matches st.

      return True

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
   LDFLAG_DYNLIB = AbstractFlag()
   # Adds a directory to the library search path. Must be in str.format() syntax and include a
   # replacement “dir” with the intuitive meaning.
   LDFLAG_ADD_LIB_DIR_FORMAT = AbstractFlag()
   # Adds a library to link to. Must be in str.format() syntax and include a replacement “lib” with
   # the intuitive meaning.
   LDFLAG_ADD_LIB_FORMAT = AbstractFlag()

   def __init__(self, st):
      """See Tool.__init__()."""

      Tool.__init__(self, st)

      self._m_listInputLibs = []
      self._m_listLibPaths = []

   def add_input_lib(self, sInputLibFilePath):
      """Appends a library to the linker’s command line.

      str sInputLibFilePath
         Path to the input library file.
      """

      self._m_listInputLibs.append(sInputLibFilePath)

   def add_lib_path(self, sLibPath):
      """Appends a directory to the library search path.

      str sLibPath
         Path to the library directory to add.
      """

      self._m_listLibPaths.append(sLibPath)

   def _create_job_add_inputs(self, listArgs):
      """See Tool._create_job_add_inputs()."""

      Tool._create_job_add_inputs(self, listArgs)

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
# ClangGnuLdLinker

@Tool.default_file_name('clang++')
class ClangGnuLdLinker(Linker):
   """Clang-driven GNU object code linker (LD)."""

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT    : '-o{path}',
      Linker.LDFLAG_ADD_LIB_DIR_FORMAT: '-L{dir}',
      Linker.LDFLAG_ADD_LIB_FORMAT    : '-l{lib}',
      Linker.LDFLAG_DYNLIB            : '-shared',
   }

   def _create_job_add_flags(self, listArgs):
      """See Linker._create_job_add_flags()."""

      Linker._create_job_add_flags(self, listArgs)

      listArgs.extend([
         '-Wl,--as-needed', # Only link to libraries containing symbols actually used.
      ])
      listArgs.extend([
         '-ggdb',           # Generate debug info compatible with GDB.
      ])

      # TODO: add support for os.environ['LDFLAGS'] ?

   @classmethod
   def _exe_matches_tool_and_system_type(cls, st, sFilePath):
      """See Linker._exe_matches_tool_and_system_type()."""

      sOut = Tool._get_cmd_output((sFilePath, '-Wl,--version'))
      if not sOut:
         return False

      # Verify that Clang is really wrapping GNU ld.
      match = re.search(r'^GNU ld .*?(?P<ver>[.0-9]+)$', sOut, re.MULTILINE)
      if not match:
         return False

      # Verify that this linker driver supports the specified system type.
      sOut = Tool._get_cmd_output((sFilePath, '-v'))
      if not sOut:
         return False

      match = re.search(r'^Target: (?P<target>.*)$', sOut, re.MULTILINE)
      if not match:
         return False
      try:
         stSupported = abamake.platform.SystemType.parse_tuple(match.group('target'))
      except abamake.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return False
      # This is not a strict equality test.
      return st == stSupported

####################################################################################################
# GxxGnuLdLinker

@Tool.default_file_name('g++')
class GxxGnuLdLinker(Linker):
   """G++-driven GNU object code linker (LD)."""

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT    : '-o{path}',
      Linker.LDFLAG_ADD_LIB_DIR_FORMAT: '-L{dir}',
      Linker.LDFLAG_ADD_LIB_FORMAT    : '-l{lib}',
      Linker.LDFLAG_DYNLIB            : '-shared',
   }

   def _create_job_add_flags(self, listArgs):
      """See Linker._create_job_add_flags()."""

      Linker._create_job_add_flags(self, listArgs)

      listArgs.extend([
         '-Wl,--as-needed', # Only link to libraries containing symbols actually used.
      ])
      listArgs.extend([
         '-ggdb',           # Generate debug info compatible with GDB.
      ])

      # TODO: add support for os.environ['LDFLAGS'] ?

   @classmethod
   def _exe_matches_tool_and_system_type(cls, st, sFilePath):
      """See Linker._exe_matches_tool_and_system_type()."""

      sOut = Tool._get_cmd_output((sFilePath, '-Wl,--version'))
      if not sOut:
         return False

      # Verify that G++ is really wrapping GNU ld.
      match = re.search(r'^GNU ld .*?(?P<ver>[.0-9]+)$', sOut, re.MULTILINE)
      if not match:
         return False

      # Verify that this linker driver supports the specified system type.
      sOut = Tool._get_cmd_output((sFilePath, '-dumpmachine'))
      if not sOut:
         return False
      try:
         stSupported = abamake.platform.SystemType.parse_tuple(sOut)
      except abamake.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return False
      # This is not a strict equality test.
      return st == stSupported

####################################################################################################
# MsLinker

@Tool.default_file_name('link')
class MsLinker(Linker):
   """Microsoft linker (Link).

   For a list of recognized command-line arguments, see <http://msdn.microsoft.com/en-us/library/
   y0zzbyt4%28v=vs.100%29.aspx>.
   """

   # Mapping table between abstract (*FLAG_*) flags
   _smc_dictAbstactToImplFlags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT    : '/OUT:{path}',
      Linker.LDFLAG_ADD_LIB_DIR_FORMAT: '/LIBPATH:{dir}',
      Linker.LDFLAG_ADD_LIB_FORMAT    : '{lib}.lib',
      Linker.LDFLAG_DYNLIB            : '/DLL',
   }

   def _create_job_add_flags(self, listArgs):
      """See Linker._create_job_add_flags()."""

      listArgs.extend([
         '/nologo',              # Suppress brand banner display.
      ])

      Linker._create_job_add_flags(self, listArgs)

      sPdbFilePath = os.path.splitext(self._m_sOutputFilePath)[0] + '.pdb'
      listArgs.extend([
         '/DEBUG',               # Keep debug info.
         '/PDB:' + sPdbFilePath, # Create a program database file (PDB).
      ])

   def _create_job_instance(self, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath):
      """See Linker._create_job_instance()."""

      # link.exe logs to stdout instead of stderr.
      dictPopenArgs['stderr'] = subprocess.STDOUT

      # link.exe has the annoying habit of telling us it’s doing what we told it to; create a
      # filtered logger to hide it.
      log = abamake.logging.FilteredLogger(log)
      log.add_exclusion('   Creating library {0}.lib and object {0}.exp'.format(
         os.path.splitext(self._m_sOutputFilePath)[0]
      ))

      return Linker._create_job_instance(self, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath)

   @classmethod
   def _exe_matches_tool_and_system_type(cls, st, sFilePath):
      """See CxxCompiler._exe_matches_tool_and_system_type()."""

      sOut = Tool._get_cmd_output((sFilePath, '/?'))
      if not sOut:
         return False

      reVersion = re.compile(
         r'^Microsoft \(R\) Incremental Linker Version (?P<ver>[.0-9]+)$', re.MULTILINE
      )

      # TODO: see if the linker can be 32- or 64-bit specific, and if so ensure that it matches st.

      return True
