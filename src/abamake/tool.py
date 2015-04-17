#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013, 2014, 2015
# Raffaello D. Di Napoli
#
# This file is part of Abamake.
#
# Abamake is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Abamake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
# the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Abamake. If not, see
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
# ToolFactory

class ToolFactory(object):
   """Creates and configures Tool instances."""

   # List of additional arguments, typically stemming from the target system type.
   _m_iterArgs = None
   # Name by which the tool shall be invoked.
   _m_sFilePath = None
   # Tool subclass that the factory will instantiate.
   _m_clsProduct = None
   # Target system type.
   _m_stTarget = None

   def __init__(self, clsProduct, sFilePath, stTarget, iterArgs = None):
      """Constructor.

      type clsProduct
         Class to instantiate.
      str sFilePath
         Path to the tool’s executable.
      abamake.platform.SystemType stTarget
         Target system type.
      iterable(str*) iterArgs
         Optional list of additional arguments to be provided to the tool.
      """

      self._m_iterArgs = iterArgs
      self._m_sFilePath = sFilePath
      self._m_clsProduct = clsProduct
      self._m_stTarget = stTarget

   def __call__(self):
      """Instantiates the target Tool subclass.

      abamake.tool.Tool return
         New tool instance.
      """

      return self._m_clsProduct(self._m_sFilePath, self._m_iterArgs)

####################################################################################################
# Tool

class Tool(object):
   """Abstract tool."""

   # Abstract tool flags (*FLAG_*).
   _m_setAbstractFlags = None
   # Additional arguments provided by a ToolFactory.
   _m_iterFactoryArgs = None
   # Name by which the tool’s executable can be invoked.
   _m_sFilePath = None
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
   FLAG_OUTPUT_PATH_FORMAT = AbstractFlag()

   def __init__(self, sFilePath, iterFactoryArgs):
      """Constructor.

      str sFilePath
         Path to the tool’s executable.
      iterable(str*) iterFactoryArgs
         Additional command-line arguments, as stored in the ToolFactory that instantiated the Tool.
      """

      self._m_setAbstractFlags = set()
      self._m_iterFactoryArgs = iterFactoryArgs
      self._m_sFilePath = sFilePath
      self._m_listInputFilePaths = []
      self._m_sOutputFilePath = None

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

   def _create_job_add_flags(self, listArgs):
      """Builds the flags portion of the tool’s command line.

      The default implementation applies the flags added with Tool.add_flags() after translating
      them using Tool._translate_abstract_flag().

      list(str*) listArgs
         Arguments list.
      """

      # Add the arguments provided via ToolFactory.
      if self._m_iterFactoryArgs:
         listArgs.extend(self._m_iterFactoryArgs)
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

   def _create_job_instance(self, fnOnComplete, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath):
      """Returns an new abamake.job.ExternalCmdJob instance constructed with the provided arguments.
      It allows subclasses to customize the job creation.

      callable fnOnComplete
         Function to call after the job completes; it will be provided the exit code of the job.
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

      return abamake.job.ExternalCmdJob(
         fnOnComplete, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath
      )

   def create_jobs(self, mk, tgt, fnOnComplete):
      """Returns a job that, when run, results in the execution of the tool.

      The default implementation schedules a job whose command line is composed by calling
      Tool._create_job_add_flags() and Tool._create_job_add_inputs().

      abamake.Make mk
         Make instance.
      abamake.target.Target tgt
         Target that this job will build.
      callable fnOnComplete
         Function to call after the job completes; it will be provided the exit code of the job.
      abamake.job.Job return
         Job scheduled.
      """

      # Build the arguments list.
      listArgs = [self._m_sFilePath]

      self._create_job_add_flags(listArgs)

      if self._m_sOutputFilePath:
         if not mk.dry_run:
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
      # Forward fnOnComplete directly to Job. More complex Tool subclasses that require
      # multiple jobs will want to only do so with the last job.
      return self._create_job_instance(
         fnOnComplete, self._get_quiet_cmd(), dictPopenArgs, mk.log, tgt.build_log_path
      )

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, sFilePath, stTarget):
      """Checks whether the specified tool executable file is modeled by cls and that executable
      supports targeting the specified system type. returning a ToolFactory configured to
      instantiate cls.

      str sFilePath
         Path to the executable to invoke.
      abamake.platform.SystemType stTarget
         Target system type.
      abamake.tool.ToolFactory return
         Factory able to instantiate cls, or None if the executable does not exist or is not modeled
         by cls or does not target st.
      """

      return None

   @classmethod
   def _get_cmd_output(cls, iterArgs):
      """Runs the specified command and returns its combined stdout and stderr.

      iterable(str+) iterArgs
         Command line to invoke.
      tuple(str, int) return
         Output and exit code of the program.
      """

      # Make sure we have a US English environment dictionary.
      dictUSEngEnv = cls._sm_dictUSEngEnv
      if not dictUSEngEnv:
         # Copy the current environment and add to it a locale override for US English.
         dictUSEngEnv = os.environ.copy()
         dictUSEngEnv['LC_ALL'] = 'en_US.UTF-8'
         cls._sm_dictUSEngEnv = dictUSEngEnv

      try:
         proc = subprocess.Popen(
            iterArgs, env = dictUSEngEnv,
            stdout = subprocess.PIPE, stderr = subprocess.STDOUT, universal_newlines = True
         );
         sOut = proc.communicate()[0].rstrip('\r\n')
         return sOut, proc.returncode
      except (abamake.FileNotFoundErrorCompat, OSError):
         # Could not execute the program.
         return None, None

   def _get_quiet_cmd(self):
      """Returns an iterable containing the short name and relevant (input or output) files for the
      tool, to be displayed in quiet mode.

      iterable(str, str*) return
         Iterable containing the quiet command name and the output file path(s).
      """

      return self._smc_sQuietName, (self._m_sOutputFilePath or '')

   @classmethod
   def get_factory(cls, sFilePathOverride = None, stTarget = None):
      """Detects if a tool of the type of this non-leaf subclass (e.g. a C++ compiler for
      abamake.tool.CxxCompiler) exists for the specified system type, returning the corresponding
      leaf class (e.g. abamake.tool.GxxCompiler if G++ for that system type is installed).

      str sFilePathOverride
         Path to a tool’s executable that will be used instead of the default for each leaf class.
      abamake.platform.SystemType stTarget
         System type for which the tool is needed. If omitted, the returned factory will create Tool
         instances for the host platform or for whatever system type is targeted by the user-
         specified tool (TODO).
      abamake.tool.ToolFactory return
         Factory able to instantiate a abamake.tool.Tool subclass matching the tool.
      """

      if sFilePathOverride:
         # Check if any leaf class can model the specified executable.
         for clsDeriv in abamake.derived_classes(cls):
            tf = clsDeriv._get_factory_if_exe_matches_tool_and_target(sFilePathOverride, stTarget)
            if tf:
               return tf
         raise Exception('unsupported executable {} specified as {} tool{}'.format(
            sFilePathOverride, cls.__name__, ' for system type ' + str(stTarget) if stTarget else ''
         ))
      else:
         # Attempt to detect whether the tool is available by checking for a supported executable.
         for tplSupported in cls._get_supported():
            sFileName = tplSupported[0]
            for clsDeriv in tplSupported[1:]:
               tf = clsDeriv._get_factory_if_exe_matches_tool_and_target(sFileName, stTarget)
               if tf:
                  return tf
         raise Exception('unable to detect {} tool{}'.format(
            cls.__name__, ' for system type ' + str(stTarget) if stTarget else ''
         ))

   @staticmethod
   def _get_supported():
      """Returns a tuple containing tuples where the first element is a tool name to try and
      execute and the following elements are subclasses that should be used to detect whether the
      tool is installed and really is the correct tool (e.g. instead of an identically-named
      unrelated program).

      tuple(tuple(std, type+)*) return
         List of supported tool names and related subclasses.
      """

      return tuple()

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

   def __init__(self, sFilePath, iterFactoryArgs):
      """See Tool.__init__()."""

      Tool.__init__(self, sFilePath, iterFactoryArgs)

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

   @staticmethod
   def _get_supported():
      """See Tool._get_supported()."""

      return (
         ('g++',     GxxCompiler),
         ('clang++', ClangxxCompiler),
         ('c++',     GxxCompiler, ClangxxCompiler),
         ('cl.exe',  MscCompiler)
      )

   # Name suffix for intermediate object files.
   object_suffix = None

####################################################################################################
# ClangxxCompiler

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
   def _get_factory_if_exe_matches_tool_and_target(cls, sFilePath, stTarget):
      """See CxxCompiler._get_factory_if_exe_matches_tool_and_target()."""

      listArgs = [sFilePath]
      if stTarget:
         listArgs.extend(('-target', str(stTarget)))
      listArgs.append('-v')
      sOut, iRet = Tool._get_cmd_output(listArgs)
      if not sOut or iRet != 0:
         return None

      # “Apple LLVM version 6.0 (clang-600.0.56) (based on LLVM 3.5svn)”
      # “clang version 3.5.0 (tags/RELEASE_350/final)”
      # “FreeBSD clang version 3.3 (tags/RELEASE_33/final 183502) 20130610”
      match = re.search(
         r'^(?:.*? )?(?:clang|LLVM) version (?P<ver>[^ ]+)(?: .*)?$', sOut, re.MULTILINE
      )
      if not match:
         return None

      # Verify that this compiler supports the specified system type.
      match = re.search(r'^Target: (?P<target>.*)$', sOut, re.MULTILINE)
      if not match:
         return None
      try:
         stSupported = abamake.platform.SystemType.parse_tuple(match.group('target'))
      except abamake.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return None

      return ToolFactory(cls, sFilePath, stSupported, ('-target', str(stSupported)))

   object_suffix = '.o'

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

#        '-coverage',
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
   def _get_factory_if_exe_matches_tool_and_target(cls, sFilePath, stTarget):
      """See CxxCompiler._get_factory_if_exe_matches_tool_and_target()."""

      sOut, iRet = Tool._get_cmd_output((sFilePath, '--version'))
      if not sOut or iRet != 0:
         return None

      # Verify that it’s indeed G++. Note that G++ will report the name it was invoked by as its own
      # name.
      match = re.search(
         '^' + re.escape(os.path.basename(sFilePath)) + r'.*?(?P<ver>[.0-9]+)$', sOut, re.MULTILINE
      )
      if not match:
         return None

      # Verify that this compiler supports the specified system type.
      sOut, iRet = Tool._get_cmd_output((sFilePath, '-dumpmachine'))
      if not sOut or iRet != 0:
         return None
      try:
         stSupported = abamake.platform.SystemType.parse_tuple(sOut)
      except abamake.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return None

      return ToolFactory(cls, sFilePath, stSupported)

   object_suffix = '.o'

####################################################################################################
# MscCompiler

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

   def _create_job_instance(self, fnOnComplete, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath):
      """See CxxCompiler._create_job_instance()."""

      # cl.exe logs to stdout instead of stderr.
      dictPopenArgs['stderr'] = subprocess.STDOUT

      # cl.exe has the annoying habit of printing the file name we asked it to compile; create a
      # filtered logger to hide it.
      log = abamake.logging.FilteredLogger(log)
      log.add_exclusion(os.path.basename(self._m_listInputFilePaths[0]))

      return CxxCompiler._create_job_instance(
         self, fnOnComplete, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath
      )

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, sFilePath, stTarget):
      """See CxxCompiler._get_factory_if_exe_matches_tool_and_target()."""

      sOut, iRet = Tool._get_cmd_output((sFilePath, '/?'))
      # TODO: is iRet from cl.exe reliable?
      if not sOut:
         return None

      # “Microsoft (R) 32-bit C/C++ Optimizing Compiler Version 16.00.40219.01 for 80x86”
      # “Microsoft (R) C/C++ Optimizing Compiler Version 16.00.40219.01 for x64”
      # “Microsoft (R) C/C++ Optimizing Compiler Version 18.00.31101 for ARM”
      # “Microsoft (R) C/C++ Optimizing Compiler Version 18.00.31101 for x64”
      # “Microsoft (R) C/C++ Optimizing Compiler Version 18.00.31101 for x86”
      match = re.search(
         r'^Microsoft .*? Compiler Version (?P<ver>[.0-9]+) for (?P<target>\S+)$',
         sOut, re.MULTILINE
      )
      if not match:
         return None

      sTarget = match.group('target')
      if sTarget.endswith('x86'):
         stSupported = abamake.platform.SystemType('i386', None, None, 'win32')
      elif sTarget == 'x64':
         stSupported = abamake.platform.SystemType('x86_64', None, None, 'win64')
      elif sTarget == 'ARM':
         # TODO: is arm-win32 the correct system type “triplet” for Windows RT?
         stSupported = abamake.platform.SystemType('arm', None, None, 'win32')
      else:
         # Target not recognized, so report it as not supported.
         return None

      return ToolFactory(cls, sFilePath, stSupported)

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

   def __init__(self, sFilePath, iterFactoryArgs):
      """See Tool.__init__()."""

      Tool.__init__(self, sFilePath, iterFactoryArgs)

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

   @staticmethod
   def _get_supported():
      """See Tool._get_supported()."""

      return (
         ('g++',      GxxGnuLdLinker),
         ('clang++',  ClangGnuLdLinker, ClangMachOLdLinker),
         ('link.exe', MsLinker)
      )

####################################################################################################
# ClangGnuLdLinker

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
   def _get_factory_if_exe_matches_tool_and_target(cls, sFilePath, stTarget):
      """See Linker._get_factory_if_exe_matches_tool_and_target()."""

      listArgs = [sFilePath]
      if stTarget:
         listArgs.extend(('-target', str(stTarget)))
      listArgs.append('-Wl,--version')
      # This will fail if Clang can’t find an LD binary for the target system type.
      sOut, iRet = Tool._get_cmd_output(listArgs)
      if not sOut or iRet != 0:
         return None

      # Verify that Clang is really wrapping GNU ld.
      match = re.search(r'^GNU ld .*?(?P<ver>[.0-9]+)$', sOut, re.MULTILINE)
      if not match:
         return None

      return ToolFactory(cls, sFilePath, stTarget, ('-target', str(stTarget)))

####################################################################################################
# ClangMachOLdLinker

class ClangMachOLdLinker(Linker):
   """Clang++-driven Mach-O object code linker (LD)."""

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
         '-ggdb',           # Generate debug info compatible with GDB.
      ])

      # TODO: add support for os.environ['LDFLAGS'] ?

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, sFilePath, stTarget):
      """See Linker._get_factory_if_exe_matches_tool_and_target()."""

      # Mach-O ld is a lot pickier than GNU ld, and it won’t report its name if invoked with any
      # other options. This means that we first need to check whether sFilePath is Clang++, then ask
      # it for ld’s path, and finally determine whether that ld is good to use.

      # TODO: begin copy & paste from ClangxxCompiler
      listArgs = [sFilePath]
      if stTarget:
         listArgs.extend(('-target', str(stTarget)))
      listArgs.append('-v')
      sOut, iRet = Tool._get_cmd_output(listArgs)
      if not sOut or iRet != 0:
         return None

      # “Apple LLVM version 6.0 (clang-600.0.56) (based on LLVM 3.5svn)”
      # “clang version 3.5.0 (tags/RELEASE_350/final)”
      # “FreeBSD clang version 3.3 (tags/RELEASE_33/final 183502) 20130610”
      match = re.search(
         r'^(?:.*? )?(?:clang|LLVM) version (?P<ver>[^ ]+)(?: .*)?$', sOut, re.MULTILINE
      )
      if not match:
         return None

      # Verify that this compiler supports the specified system type.
      match = re.search(r'^Target: (?P<target>.*)$', sOut, re.MULTILINE)
      if not match:
         return None
      try:
         stSupported = abamake.platform.SystemType.parse_tuple(match.group('target'))
      except abamake.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return None
      # TODO: end copy & paste from ClangxxCompiler

      # Get the path to ld.
      sOut, iRet = Tool._get_cmd_output((sFilePath, '-print-prog-name=ld'))
      if not sOut or iRet != 0:
         return None
      sLdFilePath = sOut

      # Verify that it’s really Mach-O ld.
      sOut, iRet = Tool._get_cmd_output((sLdFilePath, '-v'))
      if not sOut or iRet != 0:
         return None
      # @(#)PROGRAM:ld  PROJECT:ld64-241.9
      if not sOut.startswith('@(#)PROGRAM:ld '):
         return None
      if stSupported:
         # Extract the list of supported architectures.
         # configured to support archs: armv6 armv7 arm64 i386 x86_64 x86_64h armv6m armv7m
         match = re.search(
            r'^[Cc]onfigured to support arch[^:]*:(?P<archs>(:? [-_0-9A-Za-z]+)+)$',
            sOut, re.MULTILINE
         )
         if not match:
            return None
         setArchs = set(match.group('archs')[1:].split(' '))
         # Verify that the machine architecture is supported.
         if stSupported.machine not in setArchs:
            return None

      return ToolFactory(cls, sFilePath, stSupported, ('-target', str(stSupported)))

####################################################################################################
# GxxGnuLdLinker

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

#        '-coverage',
#        '-lgcov',
      ])

      # TODO: add support for os.environ['LDFLAGS'] ?

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, sFilePath, stTarget):
      """See Linker._get_factory_if_exe_matches_tool_and_target()."""

      sOut, iRet = Tool._get_cmd_output((sFilePath, '-Wl,--version'))
      if not sOut or iRet != 0:
         return None

      # Verify that G++ is really wrapping GNU ld.
      match = re.search(r'^GNU ld .*?(?P<ver>[.0-9]+)$', sOut, re.MULTILINE)
      if not match:
         return None

      # Verify that this linker driver supports the specified system type.
      sOut, iRet = Tool._get_cmd_output((sFilePath, '-dumpmachine'))
      if not sOut or iRet != 0:
         return None
      try:
         stSupported = abamake.platform.SystemType.parse_tuple(sOut)
      except abamake.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return None

      return ToolFactory(cls, sFilePath, stSupported)

####################################################################################################
# MsLinker

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
         '/NOLOGO',              # Suppress brand banner display.
      ])

      Linker._create_job_add_flags(self, listArgs)

      sPdbFilePath = os.path.splitext(self._m_sOutputFilePath)[0] + '.pdb'
      listArgs.extend([
         '/DEBUG',               # Keep debug info.
         '/PDB:' + sPdbFilePath, # Create a program database file (PDB).
      ])

   def _create_job_instance(self, fnOnComplete, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath):
      """See Linker._create_job_instance()."""

      # link.exe logs to stdout instead of stderr.
      dictPopenArgs['stderr'] = subprocess.STDOUT

      # link.exe has the annoying habit of telling us it’s doing what we told it to; create a
      # filtered logger to hide it.
      log = abamake.logging.FilteredLogger(log)
      log.add_exclusion('   Creating library {0}.lib and object {0}.exp'.format(
         os.path.splitext(self._m_sOutputFilePath)[0]
      ))

      return Linker._create_job_instance(
         self, fnOnComplete, iterQuietCmd, dictPopenArgs, log, sStdErrFilePath
      )

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, sFilePath, stTarget):
      """See Linker._get_factory_if_exe_matches_tool_and_target()."""

      if stTarget:
         # Ensure that link.exe is able to link object files for the specified target by forcing a
         # /MACHINE argument; if the machine type is not supported, link will emit a LNK4012
         # warning.
         sMachine = stTarget.machine
         if sMachine == 'arm':
            sMachine = 'ARM'
         elif sMachine == 'x86_64':
            sMachine = 'X64'
         elif sMachine in ('i386', 'i486', 'i586', 'i686'):
            sMachine = 'X86'
         else:
            raise NotImplementedError('TODO')
         sMachine = '/MACHINE:' + sMachine
      else:
         sMachine = None

      sOut, iRet = Tool._get_cmd_output((sFilePath, sMachine or '/?'))
      # TODO: is iRet from link.exe reliable?
      if not sOut:
         return None

      # “Microsoft (R) Incremental Linker Version 10.00.40219.01”
      # “Microsoft (R) Incremental Linker Version 12.00.31101.0”
      match = re.search(r'^Microsoft .*? Linker Version (?P<ver>[.0-9]+)$', sOut, re.MULTILINE)
      if not match:
         return None

      if stTarget:
         # Check for a LNK4012 warning, as explained above.
         match = re.search(r'^LINK : warning LNK4012:', sOut, re.MULTILINE)
         if match:
            return None

      if sMachine:
         tplMachine = (sMachine, )
      else:
         tplMachine = None
      return ToolFactory(cls, sFilePath, stTarget, tplMachine)
