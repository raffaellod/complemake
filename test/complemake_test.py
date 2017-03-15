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

   def __init__(self, *args):
      unittest.TestCase.__init__(self, *args)

   @staticmethod
   def exe(name):
      if platform.system() == 'Windows':
         return name + '.exe'
      else:
         return name

   @staticmethod
   def env_path_separator():
      if platform.system() == 'Windows':
         return ';'
      else:
         return ':'

   def run_built_exe(self, exe_path):
      # Build an environment dictionary that includes the path to each dependency’s lib output folder.
      env = os.environ.copy()
      all_args = (self._complemake_path, '--shared-dir', self._shared_dir, 'query', '--exec-env')
      for line in subprocess.check_output(
         all_args, cwd=self.project_path, universal_newlines=True
      ).splitlines():
         name, value = line.split('=', maxsplit=1)
         if 'PATH' in name and name in env:
            # Assume that *PATH* variables must be augmented, not overwritten.
            env[name] = env.get(name) + self.env_path_separator() + value
         else:
            # Just overwrite the value.
            env[name] = value

      return subprocess.call((os.path.abspath(exe_path)), cwd=self.project_path, env=env)

   def run_complemake(self, *args):
      all_args = [self._complemake_path, '--shared-dir', self._shared_dir]
      all_args.extend(args)
      return subprocess.call(all_args, cwd=self.project_path)

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
      exe1_path = os.path.join(self.project_path, self.exe('bin/exe1'))
      self.assertEqual(self.run_built_exe(exe1_path), 0)

##############################################################################################################

class Exe2Test(ComplemakeTest):
   project_path = 'test/exe2'

   def runTest(self):
      self.assertEqual(self.run_complemake('build'), 0)
      exe2_path = os.path.join(self.project_path, self.exe('bin/exe2'))
      self.assertEqual(self.run_built_exe(exe2_path), 0)

##############################################################################################################

if __name__ == '__main__':
   unittest.main()
