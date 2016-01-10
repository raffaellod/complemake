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

"""YAML generator."""

import datetime
import io
import re
import sys

import yaml

if sys.hexversion >= 0x03000000:
   basestring = str
   unistr = str
else:
   unistr = unicode


####################################################################################################

def generate_file(sFilePath, oRoot):
   """Generates and writes a YAML file from a Python object.

   str sFilePath
      Path to the YAML file.
   object oRoot
      Python object to be converted to YAML.
   """

   return Generator().generate_file(sFilePath, oRoot)

def generate_string(oRoot):
   """Generates a string containing YAML from a Python object.

   object oRoot
      Python object to be converted yo YAML.
   str return
      YAML source.
   """

   return Generator().generate_string(oRoot)

####################################################################################################

NO_CONTEXT            = 0
DOCUMENT_CONTEXT      = 1
SEQUENCE_CONTEXT      = 2
MAPPING_KEY_CONTEXT   = 3
MAPPING_VALUE_CONTEXT = 4

class Generator(object):
   """YAML generator. Currently limited to generating YAML that yaml.parser.Parser can recognize.

   This implementation supports local tags (!tag_name); new local tags can be added by deriving a
   generator class from yaml.Generator, and then using the decorator
   @DerivedGenerator.local_tag('tag_name') or by calling
   DerivedGenerator.register_local_tag('tag_name', convertor).
   """

   # Strings matching this don’t need to be enclosed in quotes.
   # TODO: this is too strict; find out the exact character set and fix this accordingly.
   _smc_reSafeString = re.compile('^[_A-Za-z][-_0-9A-Za-z]*$')

   def __init__(self):
      """Constructor."""

      self._reset()

   def generate_file(self, sFilePath, oRoot):
      """Generates and writes a YAML file from a Python object.

      str sFilePath
         Path to the YAML file.
      object oRoot
         Python object to be converted to YAML.
      """

      self._reset()
      self._m_fileDst = io.open(sFilePath, 'wt', encoding = 'utf-8')
      try:
         self.write_doc_start()
         self.produce_from_object(oRoot)
      finally:
         self._m_fileDst.close()
         self._m_fileDst = None

   def generate_string(self, oRoot):
      """Generates a string containing YAML from a Python object.

      object oRoot
         Python object to be converted yo YAML.
      str return
         YAML source.
      """

      self._reset()
      self._m_fileDst = io.StringIO()
      try:
         self.write_doc_start()
         self.produce_from_object(oRoot)
         s = self._m_fileDst.getvalue()
      finally:
         self._m_fileDst = None
      return s

   def new_line(self):
      self._m_fileDst.write(u'\n')
      self._m_bAtBOL = True

   def write_doc_start(self):
      """TODO: comment."""

      self._m_fileDst.write(u'%YAML 1.2')
      self.new_line()
      self._m_fileDst.write(u'---')
      self._m_bAtBOL = False

   def write_mapping_begin(self, sTag):
      """To be called by a YAML-friendly class’s __yaml__() method.

      str sTag
         YAML tag.
      """

      # TODO: validate the format of sTag.

      self._m_fileDst.write(sTag)
      self.new_line()
      self._m_iLevel += 1
      self._m_listContextStack.append(self._m_iContext)
      self._m_iContext = MAPPING_KEY_CONTEXT

   def write_mapping_end(self):
      """To be called by a YAML-friendly class’s __yaml__() method."""

      # TODO: validate self._m_iContext.
      self._m_iContext = self._m_listContextStack.pop()
      self._m_iLevel -= 1

   def write_scalar(self, sTag, sYaml):
      """Writes a scalar object. To be called by a YAML-friendly class’s __yaml__() method.

      str sTag
         YAML tag.
      str sYaml
         Object in YAML notation.
      """

      # TODO: validate the format of sTag.
      # TODO: validate that sYaml is a string.
      if sys.hexversion < 0x03000000:
         # Ensure that everything is Unicode.
         if not isinstance(sTag, unicode):
            sYaml = unicode(sTag)
         if not isinstance(sYaml, unicode):
            sYaml = unicode(sYaml)

      # TODO: possibility for a bunch of optimizations right now.

      self._m_fileDst.write(sTag)
      if sYaml:
         self._m_fileDst.write(u' ')
         self._m_fileDst.write(sYaml)

   def write_sequence_begin(self, sTag):
      """To be called by a YAML-friendly class’s __yaml__() method.

      str sTag
         YAML tag.
      """

      # TODO: validate the format of sTag.

      self._m_fileDst.write(sTag)
      self.new_line()
      self._m_iLevel += 1
      self._m_listContextStack.append(self._m_iContext)
      self._m_iContext = SEQUENCE_CONTEXT

   def write_sequence_end(self):
      """To be called by a YAML-friendly class’s __yaml__() method."""

      # TODO: validate self._m_iContext.
      self._m_iContext = self._m_listContextStack.pop()
      self._m_iLevel -= 1

   def produce_from_object(self, o):
      """Generates YAML for the specified object.

      object o
         Object to generate YAML for.
      """

      iContext = self._m_iContext
      if self._m_bAtBOL:
         if self._m_iLevel > 1:
            self._m_fileDst.write(u'  ' * (self._m_iLevel - 1))
         self._m_bAtBOL = False
      if iContext == SEQUENCE_CONTEXT:
         self._m_fileDst.write(u'- ')
      elif iContext == MAPPING_KEY_CONTEXT:
         pass
      elif iContext == MAPPING_VALUE_CONTEXT:
         self._m_fileDst.write(u': ')
      elif iContext == DOCUMENT_CONTEXT:
         self._m_fileDst.write(u' ')

      try:
         o.__yaml__(self)
         if self._m_iContext != iContext:
            # TODO: error in o.__yaml__().
            pass
      except AttributeError:
         # o does not have a __yaml__() method; look for a built-in convertor for it.
         if isinstance(o, dict):
            self.write_mapping_begin(u'!!map')
            for oKey, oValue in o.items():
               self.produce_from_object(oKey)
               self.produce_from_object(oValue)
            self.write_mapping_end()
            iContext = NO_CONTEXT
         elif isinstance(o, list):
            self.write_sequence_begin(u'!!seq')
            for oElement in o:
               self.produce_from_object(oElement)
            self.write_sequence_end()
            iContext = NO_CONTEXT
         elif isinstance(o, basestring):
            if sys.hexversion < 0x03000000 and not isinstance(o, unicode):
               sYaml = unicode(o)
            else:
               sYaml = o
            if self._smc_reSafeString.match(sYaml):
               # The string doesn’t need quotes or an explicit tag.
               self._m_fileDst.write(sYaml)
            else:
               # The string needs quotes.
               # TODO: escape characters and quotes in sYaml.
               self.write_scalar(u'!!str', u'"{}"'.format(sYaml))
         elif isinstance(o, float):
            self.write_scalar(u'!!float', unistr(o))
         elif isinstance(o, int):
            self.write_scalar(u'!!int', unistr(o))
         elif isinstance(o, bool):
            self.write_scalar(u'!!bool', u'true' if o else u'false')
         elif o is None:
            self.write_scalar(u'!!null', u'')
         else:
            raise TypeError('unsupported type: {}'.format(type(o).__name__))

      if iContext == SEQUENCE_CONTEXT:
         self.new_line()
      elif iContext == MAPPING_KEY_CONTEXT:
         self._m_iContext = MAPPING_VALUE_CONTEXT
      elif iContext == MAPPING_VALUE_CONTEXT:
         self._m_iContext = MAPPING_KEY_CONTEXT
         self.new_line()
      elif iContext == DOCUMENT_CONTEXT:
         self.new_line()

   def _reset(self):
      """Reinitializes the internal generator status."""

      self._m_bAtBOL = True
      self._m_iContext = DOCUMENT_CONTEXT
      self._m_listContextStack = []
      self._m_fileDst = None
      self._m_iLevel = 0
