#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2016 Raffaello D. Di Napoli
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

"""Test cases for the YAML generator."""

import datetime
import math
import sys
import textwrap
import unittest

import yaml as y
import yaml.generator as yg


####################################################################################################

# (cd src && python -m unittest yaml/generator_test.py)
# @unittest.skip

g_sDoc = '%YAML 1.2\n---'

class ScalarsTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yg.generate_string(None), g_sDoc + ' !!null\n')
      self.assertEqual(yg.generate_string(0), g_sDoc + ' !!int 0\n')
      self.assertEqual(yg.generate_string('a'), g_sDoc + ' a\n')

class SequencesTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yg.generate_string([]), g_sDoc + ' !!seq\n')
      self.assertEqual(yg.generate_string([0]), g_sDoc + ' !!seq\n- !!int 0\n')
      self.assertEqual(yg.generate_string(['a']), g_sDoc + ' !!seq\n- a\n')
