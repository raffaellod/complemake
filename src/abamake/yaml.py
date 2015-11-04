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

"""YAML parser."""

import io
import os
import re


####################################################################################################

def parse_file(sFilePath):
   """Loads and parses a YAML file.

   str sFilePath
      Path to the YAML file.
   object return
      Python object corresponding to the contents of the file.
   """

   with io.open(sFilePath, 'rt') as fileYaml:
      yp = YamlParser(sFilePath, fileYaml)
      return yp()

def parse_string(s):
   """Loads and parses a string containing YAML.

   str s
      YAML source.
   object return
      Python object corresponding to the contents of the string.
   """

   yp = YamlParser('<string>', iter(s.splitlines(True)))
   return yp()

####################################################################################################

class SyntaxError(Exception):
   """Indicates a syntactical or semantical error in a YAML source."""

   pass

####################################################################################################

class YamlParser(object):
   """YAML parser. Only accepts a small subset of YAML 1.2 (sequences, maps, strings, comments)."""

   _smc_reComment = re.compile(r'[\t ]*#.*$')
   _smc_reHorizontalWs = re.compile(r'[\t ]*$')
   _smc_reIndent = re.compile(r'^[\t ]*')
   _smc_reMapKey = re.compile(r'^(?P<key>[^:]+?) *: *')
   _smc_reSequenceDash = re.compile(r'-(?: +|$)')

   def __init__(self, sSourceName, iterLines):
      """Constructor.

      str sSourceName
         Name of the source for use in diagnostic messages.
      iterator(str) iterLines
         Object that yields YAML lines.
      """

      self._m_iContainerIndent = 0
      self._m_iLine = 0
      self._m_sLine = None
      self._m_iLineIndent = 0
      self._m_iterLines = iterLines
      self._m_iScalarWrapMinIndent = 0
      self._m_sSourceName = sSourceName

   def __call__(self):
      self.find_and_consume_doc_start()
      if not self.next_line():
         return None
      o = self.consume_object(False)
      if self._m_sLine is not None:
         raise self.parsing_error('invalid token')
      return o

   def consume_map(self):
      iOldContainerIndent = self._m_iContainerIndent
      iOldScalarWrapMinIndent = self._m_iScalarWrapMinIndent
      self._m_iContainerIndent += 1
      self._m_iScalarWrapMinIndent = self._m_iContainerIndent
      dictRet = {}
      while True:
         match = self._smc_reMapKey.match(self._m_sLine)
         if not match:
            raise self.parsing_error('map key expected')
         # Grab the key and strip off the whole matched string.
         sKey = match.group('key')
         self._m_sLine = self._m_sLine[len(match.group()):]

         # Parse whatever is left; this may span multiple lines.
         # TODO: reject non-explicit sequences or maps.
         dictRet[sKey] = self.consume_object(True)

         # consume_*() functions always quit after reading one last line, so check if we’re still in
         # the map.
         if self._m_sLine is None or self._m_iLineIndent < iOldContainerIndent:
            # No next line, or the next line is not part of the map.
            break
      self._m_iScalarWrapMinIndent = iOldScalarWrapMinIndent
      self._m_iContainerIndent = iOldContainerIndent
      return dictRet

   def consume_object(self, bAfterMapKey):
      """Dispatches a call to any of the other consume_*() functions, after inspecting the current
      line.

      bool bAfterMapKey
         True if a map key was read from the current line, or False otherwise.
      object return
         Read object.
      """

      if len(self._m_sLine) == 0:
         # The current container left no characters on the current line, so read another one.
         self.next_line()
         bWrapped = True
         bAfterMapKey = False
      else:
         bWrapped = False

      if self._m_sLine.startswith('"') or self._m_sLine.startswith('\''):
         return self.consume_quoted_string()
      match = self._smc_reSequenceDash.match(self._m_sLine)
      if match:
         if bAfterMapKey:
            raise self.parsing_error('sequence element not expected in map value context')
         # Restart parsing this line as a sequence.
         return self.consume_sequence(match)
      elif ':' in self._m_sLine:
         if bAfterMapKey:
            raise self.parsing_error('map key not expected in map value context')
         if bWrapped and self._m_iLineIndent < self._m_iContainerIndent:
            # This line is returning to the containing map’s indent, so this line does not contain a
            # value for the map but a new key.
            return None
         # Restart parsing this line as a map.
         return self.consume_map()
      else:
         # Not a sequence and not a map, this line must contain a scalar.
         if bWrapped and self._m_iLineIndent < self._m_iScalarWrapMinIndent:
            raise self.parsing_error('insufficient indentation for scalar starting on a new line')
         return self.consume_scalar()

   def consume_scalar(self):
      """Consumes a scalar.

      str return
         Raw scalar value.
      """

      sRet = self._m_sLine
      while self.next_line() and self._m_iLineIndent >= self._m_iScalarWrapMinIndent:
         if ':' in self._m_sLine:
            raise self.parsing_error('map key not expected in scalar context')
         sRet += ' ' + self._m_sLine
      return sRet

   def consume_quoted_string(self):
      """Consumes a quoted string.

      str return
         String value.
      """

      sQuote = self._m_sLine[0]
      ichEndQuote = self._m_sLine.find(sQuote, len(sQuote))
      if ichEndQuote > 0:
         # The quoted string is on a single line; verify that nothing follows it.
         if not self._smc_reHorizontalWs.match(self._m_sLine, ichEndQuote + len(sQuote)):
            raise self.parsing_error('unexpected characters after string end quote')
         sRet = self._m_sLine[len(sQuote):ichEndQuote]
      else:
         # The string spans multiple lines; go find its end.
         sRet = self._m_sLine[len(sQuote):]
         while self.next_line():
            sRet += ' '
            ichEndQuote = self._m_sLine.find(sQuote)
            if ichEndQuote >= 0:
               # Found the end of the string; consume it and verify that nothing follows it.
               if not self._smc_reHorizontalWs.match(self._m_sLine, ichEndQuote + len(sQuote)):
                  raise self.parsing_error('unexpected characters after string end quote')
               sRet += self._m_sLine[0:ichEndQuote]
               break
            sRet += self._m_sLine
         else:
            raise self.parsing_error('unexpected end of input while looking for string end quote')
      # Advance one line to consume what we’re returning.
      self.next_line()
      return sRet

   def consume_sequence(self, match):
      """Consumes a sequence.

      re.Match match
         Matched sequence element start characters.
      list(object) return
         Sequence value.
      """

      iOldContainerIndent = self._m_iContainerIndent
      iOldScalarWrapMinIndent = self._m_iScalarWrapMinIndent
      listRet = []
      while True:
         # Strip the “- ” prefix and any following whitespace.
         cchMatched = len(match.group())
         self._m_sLine = self._m_sLine[cchMatched:]
         # The indentation of the sequence element includes the dash match.
         self._m_iContainerIndent = self._m_iLineIndent + cchMatched
         self._m_iScalarWrapMinIndent = iOldContainerIndent + 1

         # Parse whatever is left; this may span multiple lines.
         listRet.append(self.consume_object(False))

         # consume_*() functions always quit after reading one last line, so check if we’re still in
         # the sequence.
         if self._m_sLine is None or self._m_iLineIndent < iOldContainerIndent:
            break
            # No next line, or the next line is not part of the sequence.
         match = self._smc_reSequenceDash.match(self._m_sLine)
         if not match:
            # The next line is not a sequence element.
            break
         if self._m_iLineIndent > iOldContainerIndent:
            raise self.parsing_error('excessive indentation for sequence element')
      self._m_iContainerIndent = iOldContainerIndent
      self._m_iScalarWrapMinIndent = iOldScalarWrapMinIndent
      return listRet

   def find_and_consume_doc_start(self):
      """Consumes and validates the start of the YAML document."""

      self.next_line()
      if self._m_sLine != '%YAML 1.2':
         raise self.parsing_error('expected %YAML directive')
      if not self.next_line():
         raise self.parsing_error('missing document start')
      if self._m_sLine != '---':
         raise self.parsing_error('unexpected directive')

   def next_line(self):
      """Attempts to read a new line from the YAML document, making it available as self._m_sLine
      after stripping from it any indentation, the length of which is stored in self._m_iLineIndent.

      bool return
         True if a new line was read, of False otherwise.
      """

      while True:
         self._m_iLine += 1
         sLine = next(self._m_iterLines, None)
         if sLine is None:
            # EOF has no indentation.
            self._m_iLineIndent = 0
         else:
            # Strip the trailing line terminator.
            sLine = sLine.rstrip('\n\r')
            # Strip trailing comments.
            # TODO: make this not peek inside quoted strings.
            sLine = self._smc_reComment.sub('', sLine)
            # If nothing’s left, move on to the next line; otherwise return True to consume it.
            if not sLine:
               continue
            # Determine the indentation of the line.
            self._m_iLineIndent = len(self._smc_reIndent.match(sLine).group())
            sLine = sLine[self._m_iLineIndent:]
         self._m_sLine = sLine
         return sLine is not None

   def parsing_error(self, sMessage):
      return SyntaxError('{}:{}: {}, found: “{}”'.format(
         self._m_sSourceName, self._m_iLine, sMessage, self._m_sLine
      ))
