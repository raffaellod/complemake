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
import platform
import shutil
import subprocess
import unittest


##############################################################################################################

class ComplemakeTest(unittest.TestCase):
   _complemake_path = os.path.abspath('src/complemake.py')
   _shared_dir = os.path.abspath('test/shared-dir')

   project_file = None

   def __init__(self, *args):
      unittest.TestCase.__init__(self, *args)

   def complemake_args(self, *args):
      all_args = [self._complemake_path, '--shared-dir', self._shared_dir]
      if self.project_file is not None:
         all_args.extend(('--project', self.project_file))
      if args:
         all_args.extend(args)
      return all_args

   def run_complemake(self, *args):
      need_shell = platform.system() == 'Windows'
      return subprocess.call(self.complemake_args(*args), cwd=self.project_path, shell=need_shell)

   def run_git(self, cwd, *args):
      all_args = ['git']
      all_args.extend(args)
      return subprocess.check_call(all_args, cwd=cwd)

   def setUp(self):
      shutil.rmtree(self._shared_dir, ignore_errors=True)
      self.run_complemake('clean')

   def tearDown(self):
      self.run_complemake('clean')
      shutil.rmtree(self._shared_dir, ignore_errors=True)

##############################################################################################################

class Exe1Test(ComplemakeTest):
   project_path = 'test/exe1'

   def runTest(self):
      self.assertEqual(self.run_complemake('build'), 0)
      self.assertEqual(self.run_complemake('exec', 'bin/exe1'), 0)

##############################################################################################################

class Exe2Test(ComplemakeTest):
   project_path = 'test/exe2'
   project_file = 'exe2.comk'

   def runTest(self):
      self.assertEqual(self.run_complemake('build'), 0)
      self.assertEqual(self.run_complemake('exec', 'bin/exe2'), 0)

##############################################################################################################

class Exe2WithGitDepTest(ComplemakeTest):
   git_dep_path = 'test/libsimple1'
   project_path = 'test/exe2'
   project_file = 'exe2-with-git-dep.comk'

   def runTest(self):
      self.assertEqual(self.run_complemake('build'), 0)
      self.assertEqual(self.run_complemake('exec', 'bin/exe2'), 0)

   def setUp(self):
      ComplemakeTest.setUp(self)
      # Create a repo for libsimple1.
      self.run_git(self.git_dep_path, 'init')
      self.run_git(self.git_dep_path, 'add', '.')
      self.run_git(self.git_dep_path, 'commit', '--quiet', '--message', 'Initial commit')
      # Create the “max” tag.
      self.run_git(self.git_dep_path, 'tag', 'max')

   def tearDown(self):
      shutil.rmtree(os.path.join(self.git_dep_path, '.git'), ignore_errors=True)
      ComplemakeTest.tearDown(self)

##############################################################################################################

if __name__ == '__main__':
   unittest.main()
