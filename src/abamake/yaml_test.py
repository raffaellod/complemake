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

import math
import textwrap
import unittest

import abamake.yaml as yaml


####################################################################################################

# (cd src && python -m unittest abamake/yaml.py)

class ComplexTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c:

            d:
               e: f
               g: h
               i:
               -  j
            k: "
         a"
            l: 'm'
      ''')), {'a': 'b', 'c': {'d': {'e': 'f', 'g': 'h', 'i': ['j']}, 'k': ' a', 'l': 'm'}})

class MapTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:b
      ''')), 'a:b')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
      ''')), {'a': 'b'})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a :b
      ''')), 'a :b')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a : b
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
         a:
          b
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
         a:b
         c: d
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c :d
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c : d
      ''')), {'a': 'b', 'c': 'd'})

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: b: c
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
          c
      ''')), {'a': 'b c'})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
           c
      ''')), {'a': 'b c'})

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: b:
          c
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: b:
           c
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
         b: c
      ''')), {'a': None, 'b': 'c'})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
          b: c
      ''')), {'a': {'b': 'c'}})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
           b: c
      ''')), {'a': {'b': 'c'}})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
          b: c
         d: e
      ''')), {'a': {'b': 'c'}, 'd': 'e'})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
           b: c
         d: e
      ''')), {'a': {'b': 'c'}, 'd': 'e'})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
          b: c
          d: e
      ''')), {'a': {'b': 'c', 'd': 'e'}})

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a:
          b: c
           d: e
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
           b: c
           d: e
      ''')), {'a': {'b': 'c', 'd': 'e'}})

class MapInSequenceTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a: b
      ''')), [{'a': 'b'}])

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         - a: b
         c
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         - a: b
          c
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         - a: b
           c
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a: b
            c
      ''')), [{'a': 'b c'}])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a: b
         - c
      ''')), [{'a': 'b'}, 'c'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a: b
           c: d
      ''')), [{'a': 'b', 'c': 'd'}])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a: b
         - c: d
      ''')), [{'a': 'b'}, {'c': 'd'}])

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
         -a
      ''')), '-a')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
      ''')), ['a'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         -a
         - b
      ''')), '-a - b')

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

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
           - b
      ''')), ['a - b'])

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
          - a
         - b
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - b
      ''')), ['a', 'b'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
          - b
         - c
      ''')), ['a - b', 'c'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
           - b
         - c
      ''')), ['a - b', 'c'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - b
          - c
      ''')), ['a', 'b - c'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - b
           - c
      ''')), ['a', 'b - c'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - - a
      ''')), [['a']])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - - a
         - b
      ''')), [['a'], 'b'])

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         - - a
          - b
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - - a
           - b
      ''')), [['a', 'b']])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         -
          - a
         - b
      ''')), [['a'], 'b'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         -
           - a
         - b
      ''')), [['a'], 'b'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         -
          - a
          - b
      ''')), [['a', 'b']])

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         -
           - a
          - b
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         -
          - a
         -
          - b
      ''')), [['a'], ['b']])

class SequenceInMapTest(unittest.TestCase):
   def runTest(self):
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: -
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: - b
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: - b
         c
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: - b
          c
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: - b
           c
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: - b
            c
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
         - b
      ''')), {'a': ['b']})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
          - b
      ''')), {'a': ['b']})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
         - b
         - c
      ''')), {'a': ['b', 'c']})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a:
         - b
         c:
         - d
      ''')), {'a': ['b'], 'c': ['d']})

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

class ImplicitlyTypedScalarTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - null
         - Null
         - NULL
         - nULL
         - NUll
      ''')), [None, None, None, 'nULL', 'NUll'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - true
         - True
         - TRUE
         - tRUE
         - TRue
      ''')), [True, True, True, 'tRUE', 'TRue'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - false
         - False
         - FALSE
         - fALSE
         - FAlse
      ''')), [False, False, False, 'fALSE', 'FAlse'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - 15
         - 0o15
         - 0x15
         - a15
         - Oo15
         - 0a15
      ''')), [15, 0o15, 0x15, 'a15', 'Oo15', '0a15'])

      fPosInf = float('+Inf')
      fNegInf = float('+Inf')
      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - .inf
         - .Inf
         - .INF
         - .iNF
         - .INf
         - +.inf
         - +.Inf
         - +.INF
         - +.iNF
         - +.INf
         #- -.inf
         #- -.Inf
         #- -.INF
         #- -.iNF
         #- -.INf
         - inf
         - Inf
         - INF
         - iNF
         - INf
      ''')), [
         fPosInf, fPosInf, fPosInf,  '.iNF',  '.INf',
         fPosInf, fPosInf, fPosInf, '+.iNF', '+.INf',
         #fNegInf, fNegInf, fNegInf, '-.iNF', '-.INf',
           'inf',   'Inf',   'INF',   'iNF',   'INf',
      ])

      def check_nan(o, bNaN):
         if bNaN:
            return not isinstance(o, float)
         else:
            return math.isnan(o)

      self.assertTrue(math.isnan(yaml.parse_string('%YAML 1.2\n---\n.nan')))
      self.assertTrue(math.isnan(yaml.parse_string('%YAML 1.2\n---\n.NaN')))
      self.assertTrue(math.isnan(yaml.parse_string('%YAML 1.2\n---\n.NAN')))
      self.assertFalse(isinstance(yaml.parse_string('%YAML 1.2\n---\n.nAN'), float))
      self.assertFalse(isinstance(yaml.parse_string('%YAML 1.2\n---\n.NAn'), float))
      self.assertFalse(isinstance(yaml.parse_string('%YAML 1.2\n---\nnan'), float))
      self.assertFalse(isinstance(yaml.parse_string('%YAML 1.2\n---\nNAN'), float))
      self.assertFalse(isinstance(yaml.parse_string('%YAML 1.2\n---\nNAN'), float))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - 1.
         - 1.0
         - 1.1
         - .0
         - .1
         - 1.1e0
         - 1.1e1
         - 1.1e+1
         - 1.1e-1
         - +1.
         - -1.0
         - +1.1
         - -.0
         - +.1
      ''')), [1., 1.0, 1.1, .0, .1, 1.1e0, 1.1e1, 1.1e+1, 1.1e-1, +1., -1.0, +1.1, -.0, +.1])
