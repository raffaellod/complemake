#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2015-2016 Raffaello D. Di Napoli
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

import datetime
import math
import sys
import textwrap
import unittest

import abamake.yaml as yaml

if sys.hexversion >= 0x03000000:
   basestring = str


####################################################################################################

# (cd src && python -m unittest abamake/yaml_test.py)
# @unittest.skip

class BuiltinTagsTest(unittest.TestCase):
   def runTest(self):
      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !!unk
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !!str
      ''')), '')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !!str
         a
      ''')), 'a')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !!str a
      ''')), 'a')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         !!str
      ''')), '')

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         !!str a
      ''')), 'a')

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - !!unk b
         - c
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - !!str b
         - c
      ''')), ['a', 'b', 'c'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - !!map
           k: b
         - c
      ''')), ['a', {'k': 'b'}, 'c'])

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c: !!unk d
         e: f
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c: !!str d
         e: f
      ''')), {'a': 'b', 'c': 'd', 'e': 'f'})

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c: !!map
           k: d
         e: f
      ''')), {'a': 'b', 'c': {'k': 'd'}, 'e': 'f'})

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

class ExplicitlyTypedScalarTest(unittest.TestCase):
   def runTest(self):
      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - !!null
         - !!null a
      ''')), [None, None])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - !!bool true
         - !!bool false
      ''')), [True, False])

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !!bool a
      '''))

      self.assertRaises(yaml.TagKindMismatchError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !!bool
         - a
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - !!int 1
         - !!int 0x10
      ''')), [1, 16])

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !!int
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !!int a
      '''))

      self.assertRaises(yaml.TagKindMismatchError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !!int
         - a
      '''))

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - !!float .1
         - !!float 1e1
      ''')), [0.1, 10])

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !!float
      '''))

      self.assertRaises(yaml.SyntaxError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !!float a
      '''))

      self.assertRaises(yaml.TagKindMismatchError, yaml.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !!float
         - a
      '''))

class ImplicitlyTypedScalarTest(unittest.TestCase):
   def runTest(self):
      self.maxDiff = None

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - null
         - Null
         - NULL
         - nULL
         - NUll
         - "null"
      ''')), [None, None, None, 'nULL', 'NUll', 'null'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - true
         - True
         - TRUE
         - tRUE
         - TRue
         - 'true'
      ''')), [True, True, True, 'tRUE', 'TRue', 'true'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - false
         - False
         - FALSE
         - fALSE
         - FAlse
         - "false"
      ''')), [False, False, False, 'fALSE', 'FAlse', 'false'])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - 15
         - 0o15
         - 0x15
         - a15
         - Oo15
         - 0a15
         - '15'
      ''')), [15, 0o15, 0x15, 'a15', 'Oo15', '0a15', '15'])

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
         - "1."
      ''')), [
         1., 1.0, 1.1, .0, .1, 1.1e0, 1.1e1, 1.1e+1, 1.1e-1, +1., -1.0, +1.1, -.0, +.1,
         '1.e', '1.0e', '1.1e', 'e.0', '.1e', '1.1e0e', '1.1ee1', '1.1e+1e', 'e1.1e-1', '+1.e',
         'e-1.0', '+1.1e', '-.e', '+e.1', '1.',
      ])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - 1992
         - 1992-
         - 1991-07-1
         - 1991-07-19
         - 1991:07-19
         -  991-07-19
      ''')), [
         1992,
         '1992-',
         '1991-07-1',
         datetime.date(year = 1991, month = 7, day = 19),
         '1991:07-19',
         '991-07-19',
      ])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - 1991-07-19T
         - 1991-07-19T1
         - 1991-07-19T13:07:5
         - 1991-07-19T13:07:51
         - 1991-07-19 13:07:51
         - 1991-07-19  13:07:51
         -  991-07-19T13:07:51
         - 1991-07:19T13:07:51
         - 1991-07-19Y13:07:51
         - 1991-07-19T13-07:51
      ''')), [
         '1991-07-19T',
         '1991-07-19T1',
         '1991-07-19T13:07:5',
         datetime.datetime(year = 1991, month = 7, day = 19, hour = 13, minute = 7, second = 51),
         datetime.datetime(year = 1991, month = 7, day = 19, hour = 13, minute = 7, second = 51),
         datetime.datetime(year = 1991, month = 7, day = 19, hour = 13, minute = 7, second = 51),
         '991-07-19T13:07:51',
         '1991-07:19T13:07:51',
         '1991-07-19Y13:07:51',
         '1991-07-19T13-07:51',
      ])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - 1991-07-19T13:07:51.
         - 1991-07-19T13:07:51.1
         - 1991-07-19T13:07:51.12
         - 1991-07-19T13:07:51.123
         - 1991-07-19T13:07:51.1234
         - 1991-07-19T13:07:51.12345
         - 1991-07-19T13:07:51.123456
         - 1991-07-19T13:07:51.1234567
         - 1991-07-19T13:07:51.12345678
         - 1991-07-19T13:07:51.01
         - 1991-07-19T13:07:51.0000001
      ''')), [
         '1991-07-19T13:07:51.',
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 100000
         ),
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 120000
         ),
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 123000
         ),
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 123400
         ),
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 123450
         ),
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 123456
         ),
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 123456
         ),
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 123456
         ),
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 10000
         ),
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 0
         ),
      ])

      self.assertEqual(yaml.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - 1991-07-19T13:07:51x
         - 1991-07-19T13:07:51Z
         - 1991-07-19T13:07:51+3
         - 1991-07-19T13:07:51+03:1
         - 1991-07-19T13:07:51+03:15
         - 1991-07-19T13:07:51.123456Y
         - 1991-07-19T13:07:51.123456Z
         - 1991-07-19T13:07:51.123456-11:30
      ''')), [
         '1991-07-19T13:07:51x',
         datetime.datetime(
            year = 1991, month = 7, day = 19, hour = 13, minute = 7, second = 51,
            tzinfo = yaml.TimestampTZInfo('UTC', 0, 0)
         ),
         datetime.datetime(
            year = 1991, month = 7, day = 19, hour = 13, minute = 7, second = 51,
            tzinfo = yaml.TimestampTZInfo('+3', 3, 0)
         ),
         '1991-07-19T13:07:51+03:1',
         datetime.datetime(
            year = 1991, month = 7, day = 19, hour = 13, minute = 7, second = 51,
            tzinfo = yaml.TimestampTZInfo('+03:15', 3, 15)
         ),
         '1991-07-19T13:07:51.123456Y',
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 123456,
            tzinfo = yaml.TimestampTZInfo('UTC', 0, 0)
         ),
         datetime.datetime(
            year = 1991, month = 7, day = 19,
            hour = 13, minute = 7, second = 51, microsecond = 123456,
            tzinfo = yaml.TimestampTZInfo('-11:30', -11, 30)
         ),
      ])

class LocalTagsTest(unittest.TestCase):
   def runTest(self):
      class LocalTagsTestParser(yaml.Parser):
         pass

      LocalTagsTestParser.register_local_tag(
         'test_str', yaml.Kind.SCALAR, lambda yp, sYaml: '<' + sYaml + '>'
      )
      LocalTagsTestParser.register_local_tag(
         'test_map', yaml.Kind.MAPPING, lambda yp, dictYaml: dictYaml.get('k')
      )

      self.assertRaises(
         yaml.DuplicateTagError, LocalTagsTestParser.register_local_tag, 'test_map', None, None
      )

      tp = LocalTagsTestParser()

      self.assertRaises(yaml.SyntaxError, tp.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !test_unk
      '''))

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !test_str
      ''')), '<>')

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !test_str
         a
      ''')), '<a>')

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !test_str a
      ''')), '<a>')

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         !test_str
      ''')), '<>')

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         !test_str a
      ''')), '<a>')

      self.assertRaises(yaml.SyntaxError, tp.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - !test_unk b
         - c
      '''))

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - !test_str b
         - c
      ''')), ['a', '<b>', 'c'])

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - a
         - !test_map
           k: b
         - c
      ''')), ['a', 'b', 'c'])

      self.assertRaises(yaml.SyntaxError, tp.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c: !test_unk d
         e: f
      '''))

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c: !test_str d
         e: f
      ''')), {'a': 'b', 'c': '<d>', 'e': 'f'})

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         a: b
         c: !test_map
           k: d
         e: f
      ''')), {'a': 'b', 'c': 'd', 'e': 'f'})

class LocalTagsInDifferentSubclassesTest(unittest.TestCase):
   def runTest(self):
      class LocalTagsInDifferentSubclassesTestParser1(yaml.Parser):
         pass

      @LocalTagsInDifferentSubclassesTestParser1.local_tag('same_tag', yaml.Kind.SCALAR)
      class LocalTag1(object):
         def __init__(self, yp, sYaml):
            pass

      class LocalTagsInDifferentSubclassesTestParser2(yaml.Parser):
         pass

      @LocalTagsInDifferentSubclassesTestParser2.local_tag('same_tag', yaml.Kind.SCALAR)
      class LocalTag2(object):
         def __init__(self, yp, sYaml):
            pass

      tp1 = LocalTagsInDifferentSubclassesTestParser1()
      tp2 = LocalTagsInDifferentSubclassesTestParser2()

      sYaml = '%YAML 1.2\n--- !same_tag'
      self.assertIsInstance(tp1.parse_string(sYaml), LocalTag1)
      self.assertIsInstance(tp2.parse_string(sYaml), LocalTag2)

class LocalTagsWithMandatoryMappingKeyTest(unittest.TestCase):
   def runTest(self):
      class LocalTagsWithMandatoryMappingKeyTestParser(yaml.Parser):
         pass

      @LocalTagsWithMandatoryMappingKeyTestParser.local_tag('just_a_map', yaml.Kind.MAPPING)
      def just_a_map(yp, sYaml):
         yp.get_current_mapping_key(str)
         return sYaml

      @LocalTagsWithMandatoryMappingKeyTestParser.local_tag('need_str_key', yaml.Kind.SCALAR)
      def need_str_key(yp, sYaml):
         yp.get_current_mapping_key(str)
         return sYaml

      @LocalTagsWithMandatoryMappingKeyTestParser.local_tag('okay_with_no_key', yaml.Kind.SCALAR)
      def okay_with_no_key(yp, sYaml):
         yp.get_current_mapping_key(str, None)
         return sYaml

      tp = LocalTagsWithMandatoryMappingKeyTestParser()

      self.assertRaises(yaml.MappingKeyError, tp.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         !need_str_key a
      '''))

      self.assertRaises(yaml.MappingKeyError, tp.parse_string, textwrap.dedent('''
         %YAML 1.2
         ---
         - !need_str_key a
      '''))

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         k: !need_str_key a
      ''')), {'k': 'a'})

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         k1: !just_a_map
           k2: a
      ''')), {'k1': {'k2': 'a'}})

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         !okay_with_no_key a
      ''')), 'a')

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         - !okay_with_no_key a
      ''')), ['a'])

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         ---
         k: !okay_with_no_key a
      ''')), {'k': 'a'})

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

class TagKindValidationTest(unittest.TestCase):
   def runTest(self):
      class TagKindValidationTestParser(yaml.Parser):
         pass

      TagKindValidationTestParser.register_local_tag(
         'test_map', yaml.Kind.MAPPING, lambda yp, dictYaml: dictYaml
      )
      TagKindValidationTestParser.register_local_tag(
         'test_str', yaml.Kind.SCALAR, lambda yp, sYaml: sYaml
      )

      tp = TagKindValidationTestParser()

      self.assertRaises(yaml.TagKindMismatchError, tp.parse_string, '%YAML 1.2\n---\n!!map')
      self.assertRaises(yaml.TagKindMismatchError, tp.parse_string, '%YAML 1.2\n---\n!!map a')

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !!map
         a: b
      ''')), {'a': 'b'})

      self.assertRaises(yaml.TagKindMismatchError, tp.parse_string, '%YAML 1.2\n---\n!!seq')
      self.assertRaises(yaml.TagKindMismatchError, tp.parse_string, '%YAML 1.2\n---\n!!seq a')

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !!seq
         - a
      ''')), ['a'])

      self.assertEqual(tp.parse_string('%YAML 1.2\n---\n!!str'), '')
      self.assertEqual(tp.parse_string('%YAML 1.2\n---\n!!str a'), 'a')

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !!str
         a
      ''')), 'a')

      self.assertRaises(yaml.TagKindMismatchError, tp.parse_string, '%YAML 1.2\n---\n!test_map')
      self.assertRaises(yaml.TagKindMismatchError, tp.parse_string, '%YAML 1.2\n---\n!test_map a')

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !test_map
         a: b
      ''')), {'a': 'b'})

      self.assertEqual(tp.parse_string('%YAML 1.2\n---\n!test_str'), '')
      self.assertEqual(tp.parse_string('%YAML 1.2\n---\n!test_str a'), 'a')

      self.assertEqual(tp.parse_string(textwrap.dedent('''
         %YAML 1.2
         --- !test_str
         a
      ''')), 'a')
