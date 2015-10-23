#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2015 Raffaello D. Di Napoli
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

"""Test cases for the YAML parser."""

import textwrap
import unittest

import abamake.yaml as yaml


####################################################################################################

# (cd src && python -m unittest abamake/yaml.py)

class MapTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
      ''')), {'a': 'b'})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
          b
      ''')), {'a': 'b'})

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a:
         b
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:b
         c: d
         e :f
         g : h
      ''')), {'a': 'b', 'c': 'd', 'e': 'f', 'g': 'h'})

class PrologTest(unittest.TestCase):
   def runTest(self):
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         a
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         a: b
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
      ''')), None)

class SequenceTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
      ''')), ['a'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - b
      ''')), ['a', 'b'])

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         -b
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
          - b
      ''')), ['a - b'])

class StringTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a
      ''')), 'a')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a
          b
      ''')), 'a b')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a
         b
      ''')), 'a b')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a
          b
      ''')), 'a b')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a
         b
      ''')), 'a b')

class QuotedStringTest(unittest.TestCase):
   def runTest(self):
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         'a
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         "a
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a'
      ''')), 'a\'')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a"
      ''')), 'a"')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a'b
      ''')), 'a\'b')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a"b
      ''')), 'a"b')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a
         "
      ''')), 'a "')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a
         "b"
      ''')), 'a "b"')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         'a'
      ''')), 'a')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         "a"
      ''')), 'a')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         " a"
      ''')), ' a')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         "a "
      ''')), 'a ')

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         "a"b
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         "a"
         b
      '''))

class QuotedMultilineStringTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         "
         a"
      ''')), ' a')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         "a
         "
      ''')), 'a ')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         "
         a
         "
      ''')), ' a ')
