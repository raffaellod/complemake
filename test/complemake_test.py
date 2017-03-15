#!/usr/bin/env python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2017 Raffaello D. Di Napoli
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

"""Runs Complemake through a series of test projects."""

import os
import shutil
import subprocess
import unittest


##############################################################################################################

class ComplemakeTest(unittest.TestCase):
   _complemake_path = os.path.abspath('src/complemake.py')
   _shared_dir = os.path.abspath('test/shared-dir')

   def __init__(self, *args):
      unittest.TestCase.__init__(self, *args)

   def tearDown(self):
      self.run_complemake('clean')
      shutil.rmtree(self._shared_dir, ignore_errors=True)

   def run_complemake(self, *args):
      old_cwd = os.getcwd()
      os.chdir(self.project_path)
      try:
         all_args = [self._complemake_path, '--shared-dir', self._shared_dir]
         all_args.extend(args)
         return subprocess.call(all_args)
      finally:
         os.chdir(old_cwd)

   def setUp(self):
      shutil.rmtree(self._shared_dir, ignore_errors=True)
      self.run_complemake('clean')

##############################################################################################################

class Exe1Test(ComplemakeTest):
   project_path = 'test/exe1'

   def runTest(self):
      self.assertEqual(self.run_complemake('build'), 0)

##############################################################################################################

class Exe2Test(ComplemakeTest):
   project_path = 'test/exe2'

   def runTest(self):
      self.assertEqual(self.run_complemake('build'), 0)

##############################################################################################################

if __name__ == '__main__':
   unittest.main()
