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

import collections
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
      return yp.run()

def parse_string(s):
   """Loads and parses a string containing YAML.

   str s
      YAML source.
   object return
      Python object corresponding to the contents of the string.
   """

   yp = YamlParser('<string>', iter(s.splitlines(True)))
   return yp.run()

####################################################################################################

class SyntaxError(Exception):
   """Indicates a syntactical or semantical error in a YAML source."""

   pass

####################################################################################################

class YamlParser(object):
   """YAML parser. Only accepts a small subset of YAML 1.2 (sequences, maps, strings, comments)."""

   # Matches a comment.
   _smc_reComment = re.compile(r'[\t ]*#.*$')
   # Matchers and convertors for stock scalar types (see YAML 1.2 § 10.3.2. “Tag Resolution”).
   _smc_reDefaultTypes = (
      (re.compile(r'^(~|NULL|[Nn]ull)?$'),                       None),
      (re.compile(r'^(TRUE|[Tt]rue)$'),                          True),
      (re.compile(r'^(FALSE|[Ff]alse)$'),                        False),
      (re.compile(r'^[-+]?\d+$'),                                lambda s: int(s, 10)),
      (re.compile(r'^0o[0-7]+$'),                                lambda s: int(s,  8)),
      (re.compile(r'^0x[0-9A-Fa-f]+$'),                          lambda s: int(s, 16)),
      (re.compile(r'^[-+]?\.(INF|[Ii]nf)$'),                     float('Inf')),
      (re.compile(r'^\.(N[Aa]N|nan)$'),                          float('NaN')),
      (re.compile(r'^[-+]?(\.\d+|\d+(\.\d*)?)([Ee][-+]?\d+)?$'), float),
   )
   # Matches trailing horizontal whitespace.
   _smc_reHorizontalWs = re.compile(r'[\t ]*$')
   # Matches leading horizontal whitespace.
   _smc_reIndent = re.compile(r'^[\t ]*')
   # Matches a map key and the whitespace around it.
   _smc_reMapKey = re.compile(r'^(?P<key>[^:]+?) *:(?: +|$)')
   # Matches a sequence element start.
   _smc_reSequenceDash = re.compile(r'-(?: +|$)')

   def __init__(self, sSourceName, iterLines):
      """Constructor.

      str sSourceName
         Name of the source for use in diagnostic messages.
      iterator(str) iterLines
         Object that yields YAML lines.
      """

      self._m_iLine = 0
      self._m_sLine = None
      self._m_iLineIndent = 0
      self._m_iterLines = iterLines
      self._m_iMapMinIndent = 0
      self._m_iScalarWrapMinIndent = 0
      self._m_iSequenceMinIndent = 0
      self._m_sSourceName = sSourceName

   def consume_map_implicit(self, match):
      """Consumes a map.

      re.Match match
         Matched first key.
      dict(str: object) return
         Parsed map.
      """

      iOldMapMinIndent        = self._m_iMapMinIndent
      iOldScalarWrapMinIndent = self._m_iScalarWrapMinIndent
      iOldSequenceMinIndent   = self._m_iSequenceMinIndent

      iIndent = self._m_iLineIndent
      self._m_iMapMinIndent        = iIndent + 1
      self._m_iScalarWrapMinIndent = iIndent + 1
      self._m_iSequenceMinIndent   = iIndent

      dictRet = {}
      while True:
         # Grab the key and strip off the whole matched string.
         sKey = match.group('key')
         self._m_sLine = self._m_sLine[len(match.group()):]

         # Parse whatever is left; this may span multiple lines.
         # TODO: reject non-explicit sequences or maps.
         dictRet[sKey] = self.consume_object(True)

         # consume_*() functions always quit after reading one last line, so check if we’re still in
         # the map.
         if self._m_sLine is None or self._m_iLineIndent < iIndent:
            # No next line, or the next line is not part of the map.
            break
         match = self._smc_reMapKey.match(self._m_sLine)
         if not match:
            raise self.parsing_error('map key expected')

      self._m_iMapMinIndent        = iOldMapMinIndent
      self._m_iScalarWrapMinIndent = iOldScalarWrapMinIndent
      self._m_iSequenceMinIndent   = iOldSequenceMinIndent
      return dictRet

   def consume_object(self, bAfterMapKey):
      """Dispatches a call to any of the other consume_*() functions, after inspecting the current
      line.

      bool bAfterMapKey
         True if a map key was read from the current line, or False otherwise.
      object return
         Parsed object.
      """

      if len(self._m_sLine) == 0:
         # The current container left no characters on the current line, so read another one.
         self.next_line()
         bWrapped = True
         bAfterMapKey = False
      else:
         bWrapped = False

      if not bWrapped and (self._m_sLine.startswith('"') or self._m_sLine.startswith('\'')):
         return self.consume_string_explicit()

      if not bWrapped or self._m_iLineIndent >= self._m_iSequenceMinIndent:
         match = self._smc_reSequenceDash.match(self._m_sLine)
         if match:
            if bAfterMapKey:
               raise self.parsing_error('sequence element not expected in map value context')
            # Continue parsing this line as a sequence.
            return self.consume_sequence_implicit(match)

      if not bWrapped or self._m_iLineIndent >= self._m_iMapMinIndent:
         match = self._smc_reMapKey.match(self._m_sLine)
         if match:
            if bAfterMapKey:
               raise self.parsing_error('map key not expected in map value context')
            # Continue parsing this line as a map.
            return self.consume_map_implicit(match)

      if not bWrapped or self._m_iLineIndent >= self._m_iScalarWrapMinIndent:
         return self.consume_scalar()

      # The input was an empty line and the indentation of the next line was incompatible with any
      # of the options above.
      return None

   def consume_scalar(self):
      """Consumes a scalar.

      object return
         Parsed scalar, converted to the appropriate type.
      """

      sRet = self._m_sLine
      bMultiline = False
      while self.next_line() and self._m_iLineIndent >= self._m_iScalarWrapMinIndent:
         if ':' in self._m_sLine:
            raise self.parsing_error('map key not expected in scalar context')
         sRet += ' ' + self._m_sLine
         bMultiline = True
      if not bMultiline:
         # Compare consumed string against one of the matchers for stock scalar types.
         for reMatcher, oConvertor in self._smc_reDefaultTypes:
            if reMatcher.match(sRet):
               if isinstance(oConvertor, collections.Callable):
                  return oConvertor(sRet)
               else:
                  return oConvertor
      # It’s a string.
      return sRet

   def consume_string_explicit(self):
      """Consumes an explicit (quoted) string.

      str return
         Parsed string.
      """

      sQuote = self._m_sLine[0]
      ichEndQuote = self._m_sLine.find(sQuote, len(sQuote))
      if ichEndQuote > 0:
         sRet = ''
      else:
         # The string spans multiple lines; go find its end.
         sRet = self._m_sLine[len(sQuote):]
         while self.next_line():
            sRet += ' '
            ichEndQuote = self._m_sLine.find(sQuote)
            if ichEndQuote >= 0:
               break
            sRet += self._m_sLine
         else:
            raise self.parsing_error('unexpected end of input while looking for string end quote')
      # Verify that nothing follows the closing quote.
      if not self._smc_reHorizontalWs.match(self._m_sLine, ichEndQuote + len(sQuote)):
         raise self.parsing_error('unexpected characters after string end quote')
      # Consume what we’re returning.
      sRet += self._m_sLine[0 if sRet else len(sQuote):ichEndQuote]
      self.next_line()
      return sRet

   def consume_sequence_implicit(self, match):
      """Consumes a sequence.

      re.Match match
         Matched sequence element start characters.
      list(object) return
         Parsed sequence.
      """

      iOldMapMinIndent        = self._m_iMapMinIndent
      iOldScalarWrapMinIndent = self._m_iScalarWrapMinIndent
      iOldSequenceMinIndent   = self._m_iSequenceMinIndent

      iIndent = self._m_iLineIndent
      self._m_iScalarWrapMinIndent = iIndent + 1

      listRet = []
      while True:
         # Strip the “- ” prefix and any following whitespace.
         cchMatched = len(match.group())
         self._m_sLine = self._m_sLine[cchMatched:]
         # The indentation of the sequence element includes the dash match.
         self._m_iLineIndent       += cchMatched
         self._m_iMapMinIndent      = iIndent + cchMatched
         self._m_iSequenceMinIndent = iIndent + cchMatched

         # Parse whatever is left; this may span multiple lines.
         listRet.append(self.consume_object(False))

         # consume_*() functions always quit after reading one last line, so check if we’re still in
         # the sequence.
         if self._m_sLine is None or self._m_iLineIndent < iIndent:
            break
            # No next line, or the next line is not part of the sequence.
         match = self._smc_reSequenceDash.match(self._m_sLine)
         if not match:
            # The next line is not a sequence element.
            break
         if self._m_iLineIndent > iIndent:
            raise self.parsing_error('excessive indentation for sequence element')

      self._m_iMapMinIndent        = iOldMapMinIndent
      self._m_iScalarWrapMinIndent = iOldScalarWrapMinIndent
      self._m_iSequenceMinIndent   = iOldSequenceMinIndent
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

   def run(self):
      """Parses the source set upon construction.

      object return
         Top-level parsed object.
      """

      self.find_and_consume_doc_start()
      if not self.next_line():
         # Nothing follows the prolog.
         return None
      o = self.consume_object(False)
      # Verify that there’s nothing left to parse.
      if self._m_sLine is not None:
         raise self.parsing_error('invalid token')
      return o
