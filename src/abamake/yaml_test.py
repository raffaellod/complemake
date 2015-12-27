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

# (cd src && python -m unittest abamake/yaml_test.py)
# @unittest.skip

class ComplexTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: true
         c:

            d:
               e:
               g: h
               i:
               -  1
               - ~
            k: "
         a"
            l: 'm'
      ''')), {'a': True, 'c': {'d': {'e': None, 'g': 'h', 'i': [1, None]}, 'k': ' a', 'l': 'm'}})

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
         - 1.e
         - 1.0e
         - 1.1e
         - e.0
         - .1e
         - 1.1e0e
         - 1.1ee1
         - 1.1e+1e
         - e1.1e-1
         - +1.e
         - e-1.0
         - +1.1e
         - -.e
         - +e.1
      ''')), [
         1., 1.0, 1.1, .0, .1, 1.1e0, 1.1e1, 1.1e+1, 1.1e-1, +1., -1.0, +1.1, -.0, +.1,
         '1.e', '1.0e', '1.1e', 'e.0', '.1e', '1.1e0e', '1.1ee1', '1.1e+1e', 'e1.1e-1', '+1.e',
         'e-1.0', '+1.1e', '-.e', '+e.1',
      ])

class LocalTagTest(unittest.TestCase):
   def runTest(self):
      yp = yaml.YamlParser()
      yp.register_local_tag(
         'test_str',
         lambda yp, oContext, sKey, o:
            '<' + (o if isinstance(o, str) else '') + '>'
      )
      yp.register_local_tag(
         'test_map',
         lambda yp, oContext, sKey, o:
            o.get('k') if isinstance(o, dict) else None
      )

      self.assertRaises(yaml.SyntaxError, yp.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !test_unk
      '''))

      self.assertEqual(yp.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !test_str
      ''')), '<>')

      self.assertEqual(yp.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !test_str
         a
      ''')), '<a>')

      self.assertEqual(yp.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !test_str a
      ''')), '<a>')

      self.assertEqual(yp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         !test_str
      ''')), '<>')

      self.assertEqual(yp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         !test_str a
      ''')), '<a>')

      self.assertRaises(yaml.SyntaxError, yp.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - !test_unk b
         - c
      '''))

      self.assertEqual(yp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - !test_str b
         - c
      ''')), ['a', '<b>', 'c'])

      self.assertEqual(yp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - !test_map
           k: b
         - c
      ''')), ['a', 'b', 'c'])

      self.assertRaises(yaml.SyntaxError, yp.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c: !test_unk d
         e: f
      '''))

      self.assertEqual(yp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c: !test_str d
         e: f
      ''')), {'a': 'b', 'c': '<d>', 'e': 'f'})

      self.assertEqual(yp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c: !test_map
           k: d
         e: f
      ''')), {'a': 'b', 'c': 'd', 'e': 'f'})

class MappingInSequenceTest(unittest.TestCase):
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

class MappingTest(unittest.TestCase):
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

class PrologTest(unittest.TestCase):
   def runTest(self):
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, '')
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, 'a')
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, '- a')
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, 'a: b')
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, '%YAML 1.2')
      self.assertEqual(yaml.parse_string('%YAML 1.2\n---'), None)
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, '%YAML 1.2\n---a')
      self.assertEqual(yaml.parse_string('%YAML 1.2\n--- a'), 'a')
      self.assertEqual(yaml.parse_string('%YAML 1.2\n---  a'), 'a')
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, '%YAML 1.2\n--- - a')
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, '%YAML 1.2\n--- a: b')

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

class SequenceInMappingTest(unittest.TestCase):
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

class TagContextTest(unittest.TestCase):
   def runTest(self):
      def parse_test_tag(yp, oContext, sKey, o):
         oContext[0] = o['a']
         return o
      listContext = [1]

      yp = yaml.YamlParser()
      yp.set_tag_context(listContext)
      yp.register_local_tag('test', parse_test_tag)
      self.assertEqual(yp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         !test
          a: 2
      ''')), {'a': 2})
      self.assertEqual([2], listContext)
