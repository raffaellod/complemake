#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013-2017 Raffaello D. Di Napoli
#
# This file is part of Complemake.
#
# Complemake is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# Complemake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along with Complemake. If not, see
# <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------------------------------------

"""Classes implementing different build tools, such as C++ compilers, providing an abstract interface to the
very different implementations.
"""

import os
import re
import shlex
import subprocess

import comk
import comk.job
import comk.logging
import comk.version


##############################################################################################################

class AbstractFlag(object):
   """Declares a unique abstract tool flag."""

   def __str__(self):
      """Returns the member name, in the containing class, of the abstract flag.

      Implemented by searching for self in every comk.tool.Tool-derived class, and returning the corresponding
      member name when found.

      str return
         Flag name.
      """

      attr = self._get_self_in_class(Tool)
      if attr:
         return attr
      for cls in comk.derived_classes(Tool):
         attr = self._get_self_in_class(cls)
         if attr:
            return attr
      return '(UNKNOWN)'

   def _get_self_in_class(self, cls):
      """Searches for self among the members of the specified class, returning the corresponding attribute
      name if found.

      type cls
         Class to search.
      str return
         Fully-qualified attribute name if self is a member of cls, or None otherwise.
      """

      for attr in cls.__dict__:
         if getattr(cls, attr) is self:
            return '{}.{}'.format(cls.__name__, attr)
      return None

##############################################################################################################

class ToolFactory(object):
   """Creates and configures Tool instances."""

   # List of additional arguments, typically stemming from the target system type.
   _args = None
   # Name by which the tool shall be invoked.
   _file_path = None
   # Tool subclass that the factory will instantiate.
   _product_cls = None
   # Target system type.
   _target_system_type = None
   # Tool version.
   _ver = None

   def __init__(self, product_cls, file_path, target_system_type, ver, args = None):
      """Constructor.

      type product_cls
         Class to instantiate.
      str file_path
         Path to the tool’s executable.
      comk.platform.SystemType target_system_type
         Target system type.
      comk.version.Version ver
         Version of the tool.
      iterable(str*) args
         Optional list of additional arguments to be provided to the tool.
      """

      self._args = args
      self._file_path = file_path
      self._product_cls = product_cls
      self._target_system_type = target_system_type
      self._ver = ver

   def __call__(self):
      """Instantiates the target Tool subclass.

      comk.tool.Tool return
         New tool instance.
      """

      return self._product_cls(self._file_path, self._ver, self._args)

##############################################################################################################

class Tool(object):
   """Abstract tool."""

   # Abstract tool flags (*FLAG_*).
   _abstract_flags = None
   # Additional arguments provided by a ToolFactory.
   _factory_args = None
   # Name by which the tool’s executable can be invoked.
   _file_path = None
   # Files to be processed by the tool.
   _input_file_paths = None
   # See Tool.output_file_path.
   _output_file_path = None
   # Short name of the tool, to be displayed in quiet mode. If None, the tool file name will be
   # displayed.
   _quiet_mode_name = None
   # Environment block (dictionary) modified to force programs to display output in US English.
   _en_us_env = None
   # Version.
   _ver = None

   # Specifies an output file path. Must be in str.format() syntax and include a replacement “path” with the
   # intuitive meaning.
   FLAG_OUTPUT_PATH_FORMAT = AbstractFlag()

   def __init__(self, file_path, ver, factory_args):
      """Constructor.

      str file_path
         Path to the tool’s executable.
      iterable(str*) factory_args
         Additional command-line arguments, as stored in the ToolFactory that instantiated the Tool.
      """

      self._abstract_flags = set()
      self._factory_args = factory_args
      self._file_path = file_path
      self._input_file_paths = []
      self._output_file_path = None
      self._ver = ver

   def add_flags(self, *args):
      """Adds abstract flags (*FLAG_*) to the tool’s command line. The most derived specialization will take
      care of translating each flag into a command-line argument understood by a specific tool implementation
      (e.g. GCC).

      iterable(comk.tool.AbstractFlag*) *args
         Flags to turn on.
      """

      for flag in args:
         self._abstract_flags.add(flag)

   def add_input(self, input_file_path):
      """Adds an input file to the tool input set. Duplicates are not discarded.

      str input_file_path
         Path to the input file.
      """

      self._input_file_paths.append(input_file_path)

   def _create_job_add_flags(self, args):
      """Builds the flags portion of the tool’s command line.

      The default implementation applies the flags added with Tool.add_flags() after translating them using
      Tool._translate_abstract_flag().

      list(str*) args
         Arguments list.
      """

      # Add the arguments provided via ToolFactory.
      if self._factory_args:
         args.extend(self._factory_args)
      # Add any additional abstract flags, translating them to arguments understood by GCC.
      if self._abstract_flags:
         for flag in self._abstract_flags:
            args.append(self._translate_abstract_flag(flag))

   @staticmethod
   def _create_job_add_flags_from_env_overrides(env_var_name, args):
      """Adds to the tool’s command line the contents of an environment variable containing override values.

      str env_var_name
         Name of the environment variable to append to args.
      list(str*) args
         Arguments list.
      """

      env_var_value = os.environ.get(env_var_name)
      if env_var_value:
         args.extend(shlex.split(env_var_value))

   def _create_job_add_inputs(self, args):
      """Builds the input files portion of the tool’s command line.

      The default implementation adds the input file paths at the end of args.

      list(str*) args
         Arguments list.
      """

      # Add the source file paths, if any.
      if self._input_file_paths:
         args.extend(self._input_file_paths)

   def _create_job_instance(self, on_complete_fn, quiet_cmd, popen_args, log, stderr_file_path):
      """Returns an new comk.job.ExternalCmdJob instance constructed with the provided arguments. It allows
      subclasses to customize the job creation.

      callable on_complete_fn
         Function to call after the job completes; it will be provided the exit code of the job.
      iterable(str, str*) quiet_cmd
         See quiet_cmd argument in comk.job.ExternalCmdJob.__init__().
      dict(str: object) popen_args
         See popen_args argument in comk.job.ExternalCmdJob.__init__().
      comk.logging.Logger log
         See log argument in comk.job.ExternalCmdJob.__init__().
      str stderr_file_path
         See stderr_file_path argument in comk.job.ExternalCmdJob.__init__().
      comk.job.ExternalCmdJob return
         Newly instantiated job.
      """

      return comk.job.ExternalCmdJob(on_complete_fn, quiet_cmd, popen_args, log, stderr_file_path)

   def create_jobs(self, mk, target, on_complete_fn):
      """Returns a job that, when run, results in the execution of the tool.

      The default implementation schedules a job whose command line is composed by calling
      Tool._create_job_add_flags() and Tool._create_job_add_inputs().

      comk.Make mk
         Make instance.
      comk.target.Target target
         Target that this job will build.
      callable on_complete_fn
         Function to call after the job completes; it will be provided the exit code of the job.
      comk.job.Job return
         Job scheduled.
      """

      # Build the arguments list.
      args = [self._file_path]

      self._create_job_add_flags(args)
      type(self)._create_job_add_flags_from_env_overrides(args)

      if self._output_file_path:
         if not mk.dry_run:
            # Make sure that the output directory exists.
            comk.makedirs(os.path.dirname(self._output_file_path))
         # Get the compiler-specific command-line argument to specify an output file path.
         format = self._translate_abstract_flag(self.FLAG_OUTPUT_PATH_FORMAT)
         # Add the output file path.
         args.append(format.format(path = self._output_file_path))

      self._create_job_add_inputs(args)

      popen_args = {
         'args': args,
      }
      # Forward on_complete_fn directly to Job. More complex Tool subclasses that require multiple jobs will
      # want to only do so with the last job.
      return self._create_job_instance(
         on_complete_fn, self._get_quiet_cmd(), popen_args, mk.log, target.build_log_path
      )

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, file_path, target_system_type):
      """Checks whether the specified tool executable file is modeled by cls and that executable supports
      targeting the specified system type. returning a ToolFactory configured to instantiate cls.

      str file_path
         Path to the executable to invoke.
      comk.platform.SystemType target_system_type
         Target system type.
      comk.tool.ToolFactory return
         Factory able to instantiate cls, or None if the executable does not exist or is not modeled by cls or
         does not target the target_system_type.
      """

      return None

   @classmethod
   def _get_cmd_output(cls, args):
      """Runs the specified command and returns its combined stdout and stderr.

      iterable(str+) args
         Command line to invoke.
      tuple(str, int) return
         Output and exit code of the program.
      """

      # Make sure we have a US English environment dictionary.
      en_us_env = cls._en_us_env
      if not en_us_env:
         # Copy the current environment and add to it a locale override for US English.
         en_us_env = os.environ.copy()
         en_us_env['LC_ALL'] = 'en_US.UTF-8'
         cls._en_us_env = en_us_env

      try:
         proc = subprocess.Popen(
            args, env=en_us_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
         );
         out = proc.communicate()[0].rstrip('\r\n')
         return out, proc.returncode
      except (comk.FileNotFoundErrorCompat, OSError):
         # Could not execute the program.
         return None, None

   def _get_quiet_cmd(self):
      """Returns an iterable containing the short name and relevant (input or output) files for the tool, to
      be displayed in quiet mode.

      iterable(str, str*) return
         Iterable containing the quiet command name and the output file path(s).
      """

      return self._quiet_mode_name, (self._output_file_path or '')

   @classmethod
   def get_factory(cls, file_path_override = None, target_system_type = None):
      """Detects if a tool of the type of this non-leaf subclass (e.g. a C++ compiler for
      comk.tool.CxxCompiler) exists for the specified system type, returning the corresponding leaf class
      (e.g. comk.tool.GxxCompiler if G++ for that system type is installed).

      str file_path_override
         Path to a tool’s executable that will be used instead of the default for each leaf class.
      comk.platform.SystemType target_system_type
         System type for which the tool is needed. If omitted, the returned factory will create Tool instances
         for the host platform or for whatever system type is targeted by the user-specified tool (TODO).
      comk.tool.ToolFactory return
         Factory able to instantiate a comk.tool.Tool subclass matching the tool.
      """

      if file_path_override:
         # Check if any leaf class can model the specified executable.
         for derived_cls in comk.derived_classes(cls):
            tool_factory = derived_cls._get_factory_if_exe_matches_tool_and_target(
               file_path_override, target_system_type
            )
            if tool_factory:
               return tool_factory
         raise Exception('unsupported executable {} specified as {} tool{}'.format(
            file_path_override, cls.__name__,
            ' for system type ' + str(target_system_type) if target_system_type else ''
         ))
      else:
         # Attempt to detect whether the tool is available by checking for a supported executable.
         for supported in cls._get_supported():
            file_name = supported[0]
            for derived_cls in supported[1:]:
               tool_factory = derived_cls._get_factory_if_exe_matches_tool_and_target(
                  file_name, target_system_type
               )
               if tool_factory:
                  return tool_factory
         raise Exception('unable to detect {} tool{}'.format(
            cls.__name__, ' for system type ' + str(target_system_type) if target_system_type else ''
         ))

   @staticmethod
   def _get_supported():
      """Returns a tuple containing tuples where the first element is a tool name to try and execute and the
      following elements are subclasses that should be used to detect whether the tool is installed and really
      is the correct tool (e.g. instead of an identically-named unrelated program).

      tuple(tuple(std, type+)*) return
         List of supported tool names and related subclasses.
      """

      return tuple()

   def _set_output_file_path(self, output_file_path):
      self._output_file_path = output_file_path

   output_file_path = property(fset=_set_output_file_path, doc="""
      Path to the output file to be generated by this tool.
   """)

   def _translate_abstract_flag(self, flag):
      """Translates an abstract flag (*FLAG_*) into a command-line argument specific to the tool
      implementation using a class-specific _abstact_to_impl_flags dictionary.

      comk.tool.AbstractFlag flag
         Abstract flag.
      str return
         Corresponding command-line argument.
      """

      flag_s = type(self)._abstact_to_impl_flags.get(flag)
      if flag_s is None:
         raise NotImplementedError(
            'class {} must define a mapping for abstract flag {}'.format(type(self).__name__, flag)
         )
      return flag_s

##############################################################################################################

class CxxCompiler(Tool):
   """Abstract C++ compiler."""

   # Additional include directories.
   _include_dirs = None
   # Macros defined via command-line arguments.
   _macros = None
   # See Tool._quiet_mode_name.
   _quiet_mode_name = 'C++'

   # Forces the compiler to only run the source file through the preprocessor.
   CFLAG_PREPROCESS_ONLY = AbstractFlag()
   # Causes the compiler to generate code suitable for a dynamic library.
   CFLAG_DYNLIB = AbstractFlag()
   # Defines a preprocessor macro. Must be in str.format() syntax and include replacements “name” and
   # “expansion”, each with its respective intuitive meaning.
   CFLAG_DEFINE_FORMAT = AbstractFlag()
   # Adds a directory to the include search path. Must be in str.format() syntax and include a replacement
   # “dir” with the intuitive meaning.
   CFLAG_ADD_INCLUDE_DIR_FORMAT = AbstractFlag()

   def __init__(self, file_path, ver, factory_args):
      """See Tool.__init__()."""

      Tool.__init__(self, file_path, ver, factory_args)

      self._include_dirs = []
      self._macros = {}

   def add_include_dir(self, include_dir_path):
      """Adds an include directory to the compiler’s command line.

      str include_dir_path
         Path to the include directory to add.
      """

      self._include_dirs.append(include_dir_path)

   def add_macro(self, name, expansion = ''):
      """Adds a macro definition to the compiler’s command line.

      str name
         Name of the macro.
      str expansion
         Expansion (value) of the macro.
      """

      self._macros[name] = expansion

   def _create_job_add_flags(self, args):
      """See Tool._create_job_add_flags()."""

      # TODO: remove hard-coded dirs.
      self.add_include_dir('include')

      Tool._create_job_add_flags(self, args)

      # Add any preprocessor macros.
      if self._macros:
         # Get the compiler-specific command-line argument to define a macro.
         format = self._translate_abstract_flag(self.CFLAG_DEFINE_FORMAT)
         for name, expansion in self._macros.items():
            args.append(format.format(name=name, expansion=expansion))

      # Add any additional include directories.
      if self._include_dirs:
         # Get the compiler-specific command-line argument to add an include directory.
         format = self._translate_abstract_flag(self.CFLAG_ADD_INCLUDE_DIR_FORMAT)
         for dir in self._include_dirs:
            args.append(format.format(dir=dir))

   @staticmethod
   def _create_job_add_flags_from_env_overrides(args):
      """Adds to the tool’s command line the contents of the CXXFLAGS environment variable.

      list(str*) args
         Arguments list.
      """

      Tool._create_job_add_flags_from_env_overrides('CXXFLAGS', args)

   def _get_quiet_cmd(self):
      """See Tool._get_quiet_cmd(). This override substitutes the output file path with the inputs, to show
      the source file path instead of the intermediate one.
      """

      quiet_cmd = Tool._get_quiet_cmd(self)

      return [quiet_cmd[0]] + self._input_file_paths

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

##############################################################################################################

class ClangxxCompiler(CxxCompiler):
   """Clang C++ compiler."""

   # Mapping table between abstract (*FLAG_*) flags
   _abstact_to_impl_flags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT            : '-o{path}',
      CxxCompiler.CFLAG_ADD_INCLUDE_DIR_FORMAT: '-I{dir}',
      CxxCompiler.CFLAG_DEFINE_FORMAT         : '-D{name}={expansion}',
      CxxCompiler.CFLAG_DYNLIB                : '-fPIC',
      CxxCompiler.CFLAG_PREPROCESS_ONLY       : '-E',
   }

   # See CxxCompiler.object_suffix.
   def _create_job_add_flags(self, args):
      """See CxxCompiler._create_job_add_flags()."""

      args.extend([
         '-c',                         # Compile without linking.
         '-std=c++11',                 # Select C++11 language standard.
         '-fvisibility=hidden',        # Set default ELF symbol visibility to “hidden”.
         '-fdiagnostics-color=always', # Show messages in color. Needed since we pipe stdout.
      ])

      CxxCompiler._create_job_add_flags(self, args)

      args.extend([
         '-ggdb',                  # Generate debug info compatible with GDB.
         '-O0',                    # Disable code optimization.
         '-DDEBUG=1',              # Enable debug code.
      ])
      args.extend([
         '-Wall',                  # Enable more warnings.
         '-Wextra',                # Enable extra warnings not enabled by -Wall.
         '-pedantic',              # Issue all the warnings demanded by strict ISO C++.
         '-Wconversion',           # Warn for implicit conversions that may alter a value.
         '-Wmissing-declarations', # Warn if a global function is defined without a previous declaration.
         '-Wpacked',               # Warn if a struct has “packed” attribute but that has no effect on its
                                   # layout or size.
         '-Wshadow',               # Warn when a local symbol shadows another symbol.
         '-Wsign-conversion',      # Warn for implicit conversions that may change the sign of an integer
                                   # value.
         '-Wundef',                # Warn if an undefined identifier is evaluated in “#if”.
      ])

      # TODO: add support for os.environ['CFLAGS'] and other vars ?

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, file_path, target_system_type):
      """See CxxCompiler._get_factory_if_exe_matches_tool_and_target()."""

      args = [file_path]
      if target_system_type:
         args.extend(('-target', str(target_system_type)))
      args.append('-v')
      out, ret = Tool._get_cmd_output(args)
      if not out or ret != 0:
         return None

      # “Apple LLVM version 6.0 (clang-600.0.56) (based on LLVM 3.5svn)”
      # “clang version 3.5.0 (tags/RELEASE_350/final)”
      # “FreeBSD clang version 3.3 (tags/RELEASE_33/final 183502) 20130610”
      match = re.search(r'^(?:.*? )?(?:clang|LLVM) version (?P<ver>[^ ]+)(?: .*)?$', out, re.MULTILINE)
      if not match:
         return None

      ver = comk.version.Version.parse(match.group('ver'))

      # Verify that this compiler supports the specified system type.
      match = re.search(r'^Target: (?P<target>.*)$', out, re.MULTILINE)
      if not match:
         return None
      try:
         supported_system_type = comk.platform.SystemType.parse_tuple(match.group('target'))
      except comk.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return None

      return ToolFactory(cls, file_path, supported_system_type, ver, ('-target', str(supported_system_type)))

   object_suffix = '.o'

##############################################################################################################

class GxxCompiler(CxxCompiler):
   """GNU C++ compiler (G++)."""

   # Mapping table between abstract (*FLAG_*) flags
   _abstact_to_impl_flags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT            : '-o{path}',
      CxxCompiler.CFLAG_ADD_INCLUDE_DIR_FORMAT: '-I{dir}',
      CxxCompiler.CFLAG_DEFINE_FORMAT         : '-D{name}={expansion}',
      CxxCompiler.CFLAG_DYNLIB                : '-fPIC',
      CxxCompiler.CFLAG_PREPROCESS_ONLY       : '-E',
   }

   # See CxxCompiler.object_suffix.
   def _create_job_add_flags(self, args):
      """See CxxCompiler._create_job_add_flags()."""

      args.extend([
         '-pipe',                  # Use pipes instead of temporary files.
         '-c',                     # Compile without linking.
         '-std=c++11',             # Select C++11 language standard.
         '-fnon-call-exceptions',  # Allow trapping instructions to throw exceptions.
         '-fvisibility=hidden',    # Set default ELF symbol visibility to “hidden”.
      ])
      if self._ver and self._ver >= comk.version.Version(4, 9):
         args.extend([
            '-fdiagnostics-color=always', # Show messages in color. Needed since we pipe stdout.
         ])

      CxxCompiler._create_job_add_flags(self, args)

      args.extend([
         '-ggdb',                  # Generate debug info compatible with GDB.
         '-O0',                    # Disable code optimization.
         '-DDEBUG=1',              # Enable debug code.

#        '-coverage',
      ])
      args.extend([
         '-Wall',                  # Enable more warnings.
         '-Wextra',                # Enable extra warnings not enabled by -Wall.
         '-pedantic',              # Issue all the warnings demanded by strict ISO C++.
         '-Wconversion',           # Warn for implicit conversions that may alter a value.
         '-Wlogical-op',           # Warn about suspicious uses of logical operators in expressions.
         '-Wmissing-declarations', # Warn if a global function is defined without a previous declaration.
         '-Wpacked',               # Warn if a struct has “packed” attribute but that has no effect on its
                                   # layout or size.
         '-Wshadow',               # Warn when a local symbol shadows another symbol.
         '-Wsign-conversion',      # Warn for implicit conversions that may change the sign of an integer
                                   # value.
         '-Wundef',                # Warn if an undefined identifier is evaluated in “#if”.
      ])

      # TODO: add support for os.environ['CFLAGS'] and other vars ?

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, file_path, target_system_type):
      """See CxxCompiler._get_factory_if_exe_matches_tool_and_target()."""

      out, ret = Tool._get_cmd_output((file_path, '--version'))
      if not out or ret != 0:
         return None

      # Verify that it’s indeed G++. Note that G++ will report the name it was invoked by as its own name.
      match = re.search(
         '^' + re.escape(os.path.basename(file_path)) + r'.*?(?P<ver>[.0-9]+)$', out, re.MULTILINE
      )
      if not match:
         return None

      ver = comk.version.Version.parse(match.group('ver'))

      # Verify that this compiler supports the specified system type.
      out, ret = Tool._get_cmd_output((file_path, '-dumpmachine'))
      if not out or ret != 0:
         return None
      try:
         supported_system_type = comk.platform.SystemType.parse_tuple(out)
      except comk.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return None

      return ToolFactory(cls, file_path, supported_system_type, ver)

   object_suffix = '.o'

##############################################################################################################

class MscCompiler(CxxCompiler):
   """Microsoft C/C++ compiler (MSC).

   For a list of recognized command-line arguments, see <http://msdn.microsoft.com/en-us/library/
   fwkeyyhe%28v=vs.100%29.aspx>.
   """

   # Mapping table between abstract (*FLAG_*) flags
   _abstact_to_impl_flags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT            : '/Fo{path}',
      CxxCompiler.CFLAG_ADD_INCLUDE_DIR_FORMAT: '/I{dir}',
      CxxCompiler.CFLAG_DEFINE_FORMAT         : '/D{name}={expansion}',
      CxxCompiler.CFLAG_DYNLIB                : '/LD',
      CxxCompiler.CFLAG_PREPROCESS_ONLY       : '/P',
   }

   def _create_job_add_flags(self, args):
      """See CxxCompiler._create_job_add_flags()."""

      args.extend([
         '/c',         # Compile without linking.
         '/EHa',       # Allow catching synchronous (C++) and asynchronous (SEH) exceptions.
#        '/MD',        # Use the multithreaded runtime DLL.
         '/MDd',       # Use the multithreaded debug runtime DLL.
         '/nologo',    # Suppress brand banner display.
         '/TP',        # Force all sources to be compiled as C++.
      ])

      CxxCompiler._create_job_add_flags(self, args)

      if CxxCompiler.CFLAG_PREPROCESS_ONLY in self._abstract_flags:
         args.extend([
            '/Fi' + self._output_file_path, # cl.exe requires a separate argument to specify the preprocessed
                       # output file path.
            '/wd4668', # Suppress “'macro' is not defined as a preprocessor macro, replacing with '0' for
                       # '#if/#elif'”. Somehow cl.exe /P will ignore a supposedly equivalent #pragma in a
                       # header file. This occurs in MS-provided header files.
         ])

      args.extend([
         '/DDEBUG=1',  # Enable debug code.
         '/Od',        # Disable code optimization.
         '/Z7',        # Generate debug info for PDB, stored in the .obj file.
      ])
      args.extend([
         '/Wall',      # Enable all warnings.
      ])

   def _create_job_instance(self, on_complete_fn, quiet_cmd, popen_args, log, stderr_file_path):
      """See CxxCompiler._create_job_instance()."""

      # cl.exe logs to stdout instead of stderr.
      popen_args['stderr'] = subprocess.STDOUT

      # cl.exe has the annoying habit of printing the file name we asked it to compile; create a filtered
      # logger to hide it.
      log = comk.logging.FilteredLogger(log)
      log.add_exclusion(os.path.basename(self._input_file_paths[0]))

      return CxxCompiler._create_job_instance(
         self, on_complete_fn, quiet_cmd, popen_args, log, stderr_file_path
      )

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, file_path, target_system_type):
      """See CxxCompiler._get_factory_if_exe_matches_tool_and_target()."""

      out, ret = Tool._get_cmd_output((file_path, '/?'))
      # TODO: is ret from cl.exe reliable?
      if not out:
         return None

      # “Microsoft (R) 32-bit C/C++ Optimizing Compiler Version 16.00.40219.01 for 80x86”
      # “Microsoft (R) C/C++ Optimizing Compiler Version 16.00.40219.01 for x64”
      # “Microsoft (R) C/C++ Optimizing Compiler Version 18.00.31101 for ARM”
      # “Microsoft (R) C/C++ Optimizing Compiler Version 18.00.31101 for x64”
      # “Microsoft (R) C/C++ Optimizing Compiler Version 18.00.31101 for x86”
      match = re.search(
         r'^Microsoft .*? Compiler Version (?P<ver>[.0-9]+) for (?P<target>\S+)$', out, re.MULTILINE
      )
      if not match:
         return None

      ver = comk.version.Version.parse(match.group('ver'))

      target = match.group('target')
      if target.endswith('x86'):
         supported_system_type = comk.platform.SystemType('i386', None, None, 'win32')
      elif target == 'x64':
         supported_system_type = comk.platform.SystemType('x86_64', None, None, 'win64')
      elif target == 'ARM':
         # TODO: is arm-win32 the correct system type “triplet” for Windows RT?
         supported_system_type = comk.platform.SystemType('arm', None, None, 'win32')
      else:
         # Target not recognized, so report it as not supported.
         return None

      return ToolFactory(cls, file_path, supported_system_type, ver)

   # See CxxCompiler.object_suffix.
   object_suffix = '.obj'

##############################################################################################################

class Linker(Tool):
   """Abstract object code linker."""

   # Additional libraries to link to.
   _input_libs = None
   # Directories to be included in the library search path.
   _lib_paths = None
   # See Tool._quiet_mode_name.
   _quiet_mode_name = 'LINK'

   # Tells the linker to generate a dynamic library instead of a stand-alone executable.
   LDFLAG_DYNLIB = AbstractFlag()
   # Adds a directory to the library search path. Must be in str.format() syntax and include a replacement
   # “dir” with the intuitive meaning.
   LDFLAG_ADD_LIB_DIR_FORMAT = AbstractFlag()
   # Adds a library to link to. Must be in str.format() syntax and include a replacement “lib” with the
   # intuitive meaning.
   LDFLAG_ADD_LIB_FORMAT = AbstractFlag()

   def __init__(self, file_path, ver, factory_args):
      """See Tool.__init__()."""

      Tool.__init__(self, file_path, ver, factory_args)

      self._input_libs = []
      self._lib_paths = []

   def add_input_lib(self, input_lib_file_path):
      """Appends a library to the linker’s command line.

      str input_lib_file_path
         Path to the input library file.
      """

      self._input_libs.append(input_lib_file_path)

   def add_lib_path(self, lib_path):
      """Appends a directory to the library search path.

      str lib_path
         Path to the library directory to add.
      """

      self._lib_paths.append(lib_path)

   def _create_job_add_inputs(self, args):
      """See Tool._create_job_add_inputs()."""

      Tool._create_job_add_inputs(self, args)

      # Add the library search directories.
      if self._lib_paths:
         # Get the compiler-specific command-line argument to add a library directory.
         format = self._translate_abstract_flag(self.LDFLAG_ADD_LIB_DIR_FORMAT)
         for dir in self._lib_paths:
            args.append(format.format(dir=dir))
      # Add the libraries.
      if self._input_libs:
         # Get the compiler-specific command-line argument to add a library.
         format = self._translate_abstract_flag(self.LDFLAG_ADD_LIB_FORMAT)
         for lib in self._input_libs:
            args.append(format.format(lib=lib))

   @staticmethod
   def _create_job_add_flags_from_env_overrides(args):
      """Adds to the tool’s command line the contents of the LDFLAGS environment variable.

      list(str*) args
         Arguments list.
      """

      Tool._create_job_add_flags_from_env_overrides('LDFLAGS', args)

   @staticmethod
   def _get_supported():
      """See Tool._get_supported()."""

      return (
         ('g++',      GxxGnuLdLinker),
         ('clang++',  ClangGnuLdLinker, ClangMachOLdLinker),
         ('link.exe', MsLinker)
      )

##############################################################################################################

class ClangGnuLdLinker(Linker):
   """Clang-driven GNU object code linker (LD)."""

   # Mapping table between abstract (*FLAG_*) flags
   _abstact_to_impl_flags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT    : '-o{path}',
      Linker.LDFLAG_ADD_LIB_DIR_FORMAT: '-L{dir}',
      Linker.LDFLAG_ADD_LIB_FORMAT    : '-l{lib}',
      Linker.LDFLAG_DYNLIB            : '-shared',
   }

   def _create_job_add_flags(self, args):
      """See Linker._create_job_add_flags()."""

      Linker._create_job_add_flags(self, args)

      args.extend([
         '-Wl,--as-needed', # Only link to libraries containing symbols actually used.
      ])
      args.extend([
         '-ggdb',           # Generate debug info compatible with GDB.
      ])

      # TODO: add support for os.environ['LDFLAGS'] ?

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, file_path, target_system_type):
      """See Linker._get_factory_if_exe_matches_tool_and_target()."""

      args = [file_path]
      if target_system_type:
         args.extend(('-target', str(target_system_type)))
      args.append('-Wl,--version')
      # This will fail if Clang can’t find an LD binary for the target system type.
      out, ret = Tool._get_cmd_output(args)
      if not out or ret != 0:
         return None

      # Verify that Clang is really wrapping GNU ld.
      match = re.search(r'^GNU ld .*?(?P<ver>[.0-9]+)$', out, re.MULTILINE)
      if not match:
         return None

      ver = comk.version.Version.parse(match.group('ver'))

      return ToolFactory(cls, file_path, target_system_type, ver, ('-target', str(target_system_type)))

##############################################################################################################

class ClangMachOLdLinker(Linker):
   """Clang++-driven Mach-O object code linker (LD)."""

   # Mapping table between abstract (*FLAG_*) flags
   _abstact_to_impl_flags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT    : '-o{path}',
      Linker.LDFLAG_ADD_LIB_DIR_FORMAT: '-L{dir}',
      Linker.LDFLAG_ADD_LIB_FORMAT    : '-l{lib}',
      Linker.LDFLAG_DYNLIB            : '-shared',
   }

   def _create_job_add_flags(self, args):
      """See Linker._create_job_add_flags()."""

      Linker._create_job_add_flags(self, args)

      args.extend([
         '-ggdb',           # Generate debug info compatible with GDB.
      ])

      # TODO: add support for os.environ['LDFLAGS'] ?

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, file_path, target_system_type):
      """See Linker._get_factory_if_exe_matches_tool_and_target()."""

      # Mach-O ld is a lot pickier than GNU ld, and it won’t report its name if invoked with any other
      # options. This means that we first need to check whether file_path is Clang++, then ask it for ld’s
      # path, and finally determine whether that ld is good to use.

      # TODO: begin copy & paste from ClangxxCompiler
      args = [file_path]
      if target_system_type:
         args.extend(('-target', str(target_system_type)))
      args.append('-v')
      out, ret = Tool._get_cmd_output(args)
      if not out or ret != 0:
         return None

      # “Apple LLVM version 6.0 (clang-600.0.56) (based on LLVM 3.5svn)”
      # “clang version 3.5.0 (tags/RELEASE_350/final)”
      # “FreeBSD clang version 3.3 (tags/RELEASE_33/final 183502) 20130610”
      match = re.search(r'^(?:.*? )?(?:clang|LLVM) version (?P<ver>[^ ]+)(?: .*)?$', out, re.MULTILINE)
      if not match:
         return None

      ver = comk.version.Version.parse(match.group('ver'))

      # Verify that this compiler supports the specified system type.
      match = re.search(r'^Target: (?P<target>.*)$', out, re.MULTILINE)
      if not match:
         return None
      try:
         supported_system_type = comk.platform.SystemType.parse_tuple(match.group('target'))
      except comk.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return None
      # TODO: end copy & paste from ClangxxCompiler

      # Get the path to ld.
      out, ret = Tool._get_cmd_output((file_path, '-print-prog-name=ld'))
      if not out or ret != 0:
         return None
      ld_file_path = out

      # Verify that it’s really Mach-O ld.
      out, ret = Tool._get_cmd_output((ld_file_path, '-v'))
      if not out or ret != 0:
         return None
      # @(#)PROGRAM:ld  PROJECT:ld64-241.9
      if not out.startswith('@(#)PROGRAM:ld '):
         return None
      if supported_system_type:
         # Extract the list of supported architectures.
         # configured to support archs: armv6 armv7 arm64 i386 x86_64 x86_64h armv6m armv7m
         match = re.search(
            r'^[Cc]onfigured to support arch[^:]*:(?P<archs>(:? [-_0-9A-Za-z]+)+)$', out, re.MULTILINE
         )
         if not match:
            return None
         archs = set(match.group('archs')[1:].split(' '))
         # Verify that the machine architecture is supported.
         if supported_system_type.machine not in archs:
            return None

      return ToolFactory(cls, file_path, supported_system_type, ver, ('-target', str(supported_system_type)))

##############################################################################################################

class GxxGnuLdLinker(Linker):
   """G++-driven GNU object code linker (LD)."""

   # Mapping table between abstract (*FLAG_*) flags
   _abstact_to_impl_flags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT    : '-o{path}',
      Linker.LDFLAG_ADD_LIB_DIR_FORMAT: '-L{dir}',
      Linker.LDFLAG_ADD_LIB_FORMAT    : '-l{lib}',
      Linker.LDFLAG_DYNLIB            : '-shared',
   }

   def _create_job_add_flags(self, args):
      """See Linker._create_job_add_flags()."""

      Linker._create_job_add_flags(self, args)

      args.extend([
         '-Wl,--as-needed', # Only link to libraries containing symbols actually used.
      ])
      args.extend([
         '-ggdb',           # Generate debug info compatible with GDB.

#        '-coverage',
#        '-lgcov',
      ])

      # TODO: add support for os.environ['LDFLAGS'] ?

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, file_path, target_system_type):
      """See Linker._get_factory_if_exe_matches_tool_and_target()."""

      out, ret = Tool._get_cmd_output((file_path, '-Wl,--version'))
      if not out or ret != 0:
         return None

      # Verify that G++ is really wrapping GNU ld.
      match = re.search(r'^GNU ld .*?(?P<ver>[.0-9]+)$', out, re.MULTILINE)
      if not match:
         return None

      ver = comk.version.Version.parse(match.group('ver'))

      # Verify that this linker driver supports the specified system type.
      out, ret = Tool._get_cmd_output((file_path, '-dumpmachine'))
      if not out or ret != 0:
         return None
      try:
         supported_system_type = comk.platform.SystemType.parse_tuple(out)
      except comk.platform.SystemTypeTupleError:
         # If the tuple can’t be parsed, assume it’s not supported.
         return None

      return ToolFactory(cls, file_path, supported_system_type, ver)

##############################################################################################################

class MsLinker(Linker):
   """Microsoft linker (Link).

   For a list of recognized command-line arguments, see <http://msdn.microsoft.com/en-us/library/
   y0zzbyt4%28v=vs.100%29.aspx>.
   """

   # Mapping table between abstract (*FLAG_*) flags
   _abstact_to_impl_flags = {
      Tool.FLAG_OUTPUT_PATH_FORMAT    : '/OUT:{path}',
      Linker.LDFLAG_ADD_LIB_DIR_FORMAT: '/LIBPATH:{dir}',
      Linker.LDFLAG_ADD_LIB_FORMAT    : '{lib}.lib',
      Linker.LDFLAG_DYNLIB            : '/DLL',
   }

   def _create_job_add_flags(self, args):
      """See Linker._create_job_add_flags()."""

      args.extend([
         '/NOLOGO',              # Suppress brand banner display.
      ])

      Linker._create_job_add_flags(self, args)

      pdb_file_path = os.path.splitext(self._output_file_path)[0] + '.pdb'
      args.extend([
         '/DEBUG',                # Keep debug info.
         '/PDB:' + pdb_file_path, # Create a program database file (PDB).
      ])

   def _create_job_instance(self, on_complete_fn, quiet_cmd, popen_args, log, stderr_file_path):
      """See Linker._create_job_instance()."""

      # link.exe logs to stdout instead of stderr.
      popen_args['stderr'] = subprocess.STDOUT

      # link.exe has the annoying habit of telling us it’s doing what we told it to; create a
      # filtered logger to hide it.
      log = comk.logging.FilteredLogger(log)
      log.add_exclusion('   Creating library {0}.lib and object {0}.exp'.format(
         os.path.splitext(self._output_file_path)[0]
      ))

      return Linker._create_job_instance(self, on_complete_fn, quiet_cmd, popen_args, log, stderr_file_path)

   @classmethod
   def _get_factory_if_exe_matches_tool_and_target(cls, file_path, target_system_type):
      """See Linker._get_factory_if_exe_matches_tool_and_target()."""

      if target_system_type:
         # Ensure that link.exe is able to link object files for the specified target by forcing a /MACHINE
         # argument; if the machine type is not supported, link will emit a LNK4012 warning.
         machine = target_system_type.machine
         if machine == 'arm':
            machine = 'ARM'
         elif machine == 'x86_64':
            machine = 'X64'
         elif machine in ('i386', 'i486', 'i586', 'i686'):
            machine = 'X86'
         else:
            raise NotImplementedError('TODO')
         machine = '/MACHINE:' + machine
      else:
         machine = None

      out, ret = Tool._get_cmd_output((file_path, machine or '/?'))
      # TODO: is ret from link.exe reliable?
      if not out:
         return None

      # “Microsoft (R) Incremental Linker Version 10.00.40219.01”
      # “Microsoft (R) Incremental Linker Version 12.00.31101.0”
      match = re.search(r'^Microsoft .*? Linker Version (?P<ver>[.0-9]+)$', out, re.MULTILINE)
      if not match:
         return None

      ver = comk.version.Version.parse(match.group('ver'))

      if target_system_type:
         # Check for a LNK4012 warning, as explained above.
         match = re.search(r'^LINK : warning LNK4012:', out, re.MULTILINE)
         if match:
            return None

      if machine:
         machine = (machine, )
      else:
         machine = None
      return ToolFactory(cls, file_path, target_system_type, ver, machine)
