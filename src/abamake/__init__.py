#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013-2016 Raffaello D. Di Napoli
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

"""This module contains the implementation of Abamake (short for “Abaclade Make”).

This file contains Abamake and other core classes.

See [DOC:6931 Abamake] for more information.
"""

"""DOC:6931 Abamake

Abamake (short for “Abaclade Make”) was created to satisfy these requirements:

•  Cross-platform enough to no longer need to separately maintain a GNU makefile and a Visual Studio
   solution and projects to build Abaclade; this is especially important when thinking of Abaclade
   as a framework that should simplify building projects with/on top of it;

•  Allow a single makefile per project (this was just impossible with MSBuild);

•  Simplified syntax for a very shallow learning curve, just like Abaclade itself aims to be easier
   to use than other C++ frameworks;

•  Minimal-to-no build instructions required in each makefile, and no toolchain-specific commands/
   flags (this was getting difficult with GNU make);

•  Implicit definition of intermediate targets, so that each makefile needs only mention sources and
   outputs (this had already been achieved via Makefile.inc for GNU make, and was not required for
   MSBuild);

•  Trivial test declaration and execution (this had been implemented in both GNU make and MSBuild,
   but at the cost of a lot of made-up conventions);

•  Integration with abc::testing framework (this had already been accomplished for GNU make, but was
   still only planned for MSBuild);

•  Default parallel building of independent targets;

•  Command-line options generally compatible with GNU make, to be immediately usable by GNU make
   users.


Abamake loads an Abamakefile (short for “Abamake makefile”, a fairly simple XML file; see [DOC:5581
Abamakefiles]), creating a list of named and unnamed (file path-only) targets; these are then
scheduled for build, and the resulting build is started, proceeding in the necessary order.

Most targets are built using external commands (e.g. a C++ compiler); see [DOC:6821 Abamake ‒
Execution of external commands] for more information. Multiple non-dependent external commands are
executed in parallel, depending on the multiprocessing capability of the host system and command-
line options used.

TODO: link to documentation for abc::testing support in Abamake.
"""

import os
import sys

FileNotFoundErrorCompat = getattr(__builtins__, 'FileNotFoundError', IOError)
if sys.hexversion >= 0x03000000:
   basestring = str


####################################################################################################

def derived_classes(clsBase):
   """Iterates over all the classes that derive directly or indirectly from the specified one.

   This is probably rather slow, so it should not be abused.

   type clsBase
      Base class.
   type yield
      Class derived from clsBase.
   """

   setYielded = set()
   listClassesToScan = [clsBase]
   while listClassesToScan:
      # Iterate over the direct subclasses of the first class to scan.
      for clsDeriv in listClassesToScan.pop().__subclasses__():
         if clsDeriv not in setYielded:
            # We haven’t met or yielded this class before.
            yield clsDeriv
            setYielded.add(clsDeriv)
            listClassesToScan.append(clsDeriv)

def makedirs(sPath):
   """Implementation of os.makedirs(exists_ok = True) for both Python 2.7 and 3.x.

   str sPath
      Full path to the directory that should exist.
   """

   try:
      os.makedirs(sPath)
   except OSError:
      if not os.path.isdir(sPath):
         raise
