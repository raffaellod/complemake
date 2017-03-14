# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2016-2017 Raffaello D. Di Napoli
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

"""Test cases for the YAML generator."""

import datetime
import unittest

import yaml.generator as yg


##############################################################################################################

DOC_START = '%YAML 1.2\n---'

class ScalarLocalTagsTest(unittest.TestCase):
   def runTest(self):
      class ScalarLocalTagTest1(object):
         def __init__(self, i):
            self._i = i

         def __yaml__(self, yg):
            yg.write_scalar('!test_tag', '<{}>'.format(self._i))

      t1 = ScalarLocalTagTest1(1)
      t2 = ScalarLocalTagTest1(2)

      self.assertEqual(yg.generate_string(t1), DOC_START + ' !test_tag <1>\n')
      self.assertEqual(yg.generate_string([t1]), DOC_START + ' \n- !test_tag <1>\n\n')
      self.assertEqual(yg.generate_string([t1, t2]), DOC_START + ' \n- !test_tag <1>\n- !test_tag <2>\n\n')
      self.assertEqual(yg.generate_string({t1: t2}), DOC_START + ' \n!test_tag <1>: !test_tag <2>\n\n')

class MapsTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yg.generate_string({}), DOC_START + ' \n\n')
      self.assertEqual(yg.generate_string({1: 2}), DOC_START + ' \n1: 2\n\n')
      self.assertEqual(yg.generate_string({'a': 'b'}), DOC_START + ' \na: b\n\n')
      self.assertEqual(yg.generate_string({1: 'a', 2: 'b'}), DOC_START + ' \n1: a\n2: b\n\n')

class ScalarsTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yg.generate_string(None), DOC_START + ' !!null\n')
      self.assertEqual(yg.generate_string(0), DOC_START + ' 0\n')
      self.assertEqual(yg.generate_string('a'), DOC_START + ' a\n')

      dt = datetime.datetime.now()
      self.assertEqual(yg.generate_string(dt), DOC_START + ' ' + dt.isoformat() + '\n')

class SequencesTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yg.generate_string([]), DOC_START + ' \n\n')
      self.assertEqual(yg.generate_string([0]), DOC_START + ' \n- 0\n\n')
      self.assertEqual(yg.generate_string(['a']), DOC_START + ' \n- a\n\n')
