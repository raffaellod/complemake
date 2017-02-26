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

"""This module contains the implementation of Complemake.

This file contains Complemake and other core classes.

See [DOC:6931 Complemake] for more information.
"""

"""DOC:6931 Complemake

Complemake was created to satisfy these requirements:

•  Cross-platform enough to no longer need to separately maintain a GNU makefile and a Visual Studio solution
   and projects to build Abaclade; this is especially important when thinking of Abaclade as a framework that
   should simplify building projects with/on top of it;

•  Allow a single file per project (this was just impossible with MSBuild);

•  Simplified syntax for a very shallow learning curve, just like Abaclade itself aims to be easier to use
   than other C++ frameworks;

•  Minimal-to-no build instructions required in each project, and no toolchain-specific commands/flags (this
   was getting difficult with GNU make);

•  Implicit definition of intermediate targets, so that each project needs only mention sources and outputs
   (this had already been achieved via Makefile.inc for GNU make, and was not required for MSBuild);

•  Trivial test declaration and execution (this had been implemented in both GNU make and MSBuild, but at the
   cost of a lot of made-up conventions);

•  Integration with abc::testing framework (this had already been accomplished for GNU make, but was still
   only planned for MSBuild);

•  Default parallel building of independent targets;

•  Command-line options generally compatible with GNU make, to be immediately usable by GNU make users.

Complemake loads a Complemake file (a YAML file), creating a list of named and unnamed (file path-only)
targets; these are then scheduled for build, and the resulting build is started, proceeding in the necessary
order.

Most targets are built using external commands (e.g. a C++ compiler); see [DOC:6821 Complemake ‒ Execution of
external commands] for more information. Multiple non-dependent external commands are executed in parallel,
depending on the multiprocessing capability of the host system and command-line options used.

TODO: link to documentation for abc::testing support in Complemake.
"""

import os
import sys

FileNotFoundErrorCompat = getattr(__builtins__, 'FileNotFoundError', IOError)
if sys.hexversion >= 0x03000000:
   basestring = str


##############################################################################################################

def derived_classes(base_cls):
   """Iterates over all the classes that derive directly or indirectly from the specified one.

   This is probably rather slow, so it should not be abused.

   type base_cls
      Base class.
   type yield
      Class derived from base_cls.
   """

   yielded = set()
   classes_to_scan = [base_cls]
   while classes_to_scan:
      # Iterate over the direct subclasses of the first class to scan.
      for derived_cls in classes_to_scan.pop().__subclasses__():
         if derived_cls not in yielded:
            # We haven’t met or yielded this class before.
            yield derived_cls
            yielded.add(derived_cls)
            classes_to_scan.append(derived_cls)

def makedirs(path):
   """Implementation of os.makedirs(exists_ok=True) for both Python 2.7 and 3.x.

   str path
      Full path to the directory that should exist.
   """

   try:
      os.makedirs(path)
   except OSError:
      if not os.path.isdir(path):
         raise
