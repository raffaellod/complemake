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
import unittest

import yaml.generator as yg


####################################################################################################

# (cd src && python -m unittest yaml/generator_test.py)
# @unittest.skip

g_sDoc = '%YAML 1.2\n---'

class ScalarLocalTagsTest(unittest.TestCase):
   def runTest(self):
      class ScalarLocalTagTest1(object):
         def __init__(self, i):
            self._m_i = i

         def __yaml__(self, yg):
            yg.write_scalar('!test_tag', '<{}>'.format(self._m_i))

      t1 = ScalarLocalTagTest1(1)
      t2 = ScalarLocalTagTest1(2)

      self.assertEqual(
         yg.generate_string(t1),
         g_sDoc + ' !test_tag <1>\n'
      )
      self.assertEqual(
         yg.generate_string([t1]),
         g_sDoc + ' \n- !test_tag <1>\n\n'
      )
      self.assertEqual(
         yg.generate_string([t1, t2]),
         g_sDoc + ' \n- !test_tag <1>\n- !test_tag <2>\n\n'
      )
      self.assertEqual(
         yg.generate_string({t1: t2}),
         g_sDoc + ' \n!test_tag <1>: !test_tag <2>\n\n'
      )

class MapsTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yg.generate_string({}), g_sDoc + ' !!map\n\n')
      self.assertEqual(yg.generate_string({1: 2}), g_sDoc + ' \n1: 2\n\n')
      self.assertEqual(yg.generate_string({'a': 'b'}), g_sDoc + ' \na: b\n\n')
      self.assertEqual(yg.generate_string({1: 'a', 2: 'b'}), g_sDoc + ' \n1: a\n2: b\n\n')

class ScalarsTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yg.generate_string(None), g_sDoc + ' !!null\n')
      self.assertEqual(yg.generate_string(0), g_sDoc + ' 0\n')
      self.assertEqual(yg.generate_string('a'), g_sDoc + ' a\n')

      dt = datetime.datetime.now()
      self.assertEqual(yg.generate_string(dt), g_sDoc + ' ' + dt.isoformat() + '\n')

class SequencesTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yg.generate_string([]), g_sDoc + ' !!seq\n\n')
      self.assertEqual(yg.generate_string([0]), g_sDoc + ' \n- 0\n\n')
      self.assertEqual(yg.generate_string(['a']), g_sDoc + ' \n- a\n\n')
