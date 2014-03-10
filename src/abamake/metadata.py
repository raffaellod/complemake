#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013, 2014
# Raffaello D. Di Napoli
#
# This file is part of Application-Building Components (henceforth referred to as ABC).
#
# ABC is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ABC is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with ABC. If not, see
# <http://www.gnu.org/licenses/>.
#---------------------------------------------------------------------------------------------------

"""Metadata management classes."""

from datetime import datetime
import os
import xml.dom
import xml.dom.minidom



####################################################################################################
# FileMetadata

class FileMetadata(object):
   """Metadata for a single file."""

   __slots__ = (
      # Date/time of the file’s last modification.
      '_m_dtMTime',
   )


   def __init__(self, sFilePath):
      """Constructor.

      str sFilePath
         Path to the file of which to collect metadata.
      """

      self._m_dtMTime = datetime.fromtimestamp(os.path.getmtime(sFilePath))


   def __getstate__(self):
      return {
         'mtime': self._m_dtMTime.isoformat(' '),
      }


   def __setstate__(self, dictState):
      for sName, sValue in dictState.items():
         if sName == 'mtime':
            self._m_dtMTime = datetime.strptime(sValue, '%Y-%m-%d %H:%M:%S.%f')


   def __eq__(self, other):
      return self._m_dtMTime == other._m_dtMTime


   def __ne__(self, other):
      return not self.__eq__(other)



####################################################################################################
# FileMetadataPair

class FileMetadataPair(object):
   """Stores Handles storage and retrieval of file metadata."""

   __slots__ = (
      # Stored file metadata, or None if the file’s metadata was never collected.
      'stored',
      # Current file metadata, or None if the file’s metadata has not yet been refreshed.
      'current',
   )


   def __init__(self):
      self.stored = None
      self.current = None



####################################################################################################
# MetadataStore

class MetadataStore(object):
   """Handles storage and retrieval of file metadata."""

   # Metadata for each file (str -> FileMetadata).
   _m_bDirty = False
   # Persistent storage file path.
   _m_sFilePath = None
   # Metadata for each file (str -> FileMetadata).
   _m_dictMetadataPairs = None


   def __init__(self, sFilePath):
      """Constructor. Loads metadata from the specified file.

      str sFilePath
         Metadata storage file.
      """

      self._m_sFilePath = sFilePath
      self._m_dictMetadataPairs = {}
      try:
         with xml.dom.minidom.parse(sFilePath) as doc:
            doc.documentElement.normalize()
            for eltFile in doc.documentElement.childNodes:
               # Skip unimportant nodes.
               if eltFile.nodeType != eltFile.ELEMENT_NODE or eltFile.nodeName != 'file':
                  continue
               # Parse this <file> element into the “stored” FileMetadata member of a new
               # FileMetadataPair instance.
               fmdp = FileMetadataPair()
               fmdp.stored = FileMetadata.__new__(FileMetadata)
               fmdp.stored.__setstate__(eltFile.attributes)
               self._m_dictMetadataPairs[eltFile.getAttribute('path')] = fmdp
      except FileNotFoundError:
         # If we can’t load the persistent metadata store, start it over.
         pass


   def __bool__(self):
      return bool(self._m_dictMetadataPairs)


   def file_changed(self, sFilePath):
      """Compares the metadata stored for the specified file against the file’s current metadata.

      str sFilePath
         Path to the file of which to compare metadata.
      bool return
         True if the file is determined to have changed, or False otherwise.
      """

      fmdp = self._m_dictMetadataPairs.get(sFilePath)
      # If we have no metadata to compare, report the file as changed.
      if fmdp is None or fmdp.stored is None:
         return True
      # If we still haven’t read the file’s current metadata, retrieve it now.
      if fmdp.current is None:
         try:
            fmdp.current = FileMetadata(sFilePath)
         except FileNotFoundError:
            # If the file doesn’t exist (anymore), consider it changed.
            return True

      # Compare stored vs. current metadata.
      return fmdp.current != fmdp.stored


   def update(self, sFilePath):
      """Creates or updates metadata for the specified file.

      str sFilePath
         Path to the file of which to update metadata.
      """

      fmdp = self._m_dictMetadataPairs.get(sFilePath)
      # Make sure the metadata pair is in the dictionary.
      if fmdp is None:
         fmdp = FileMetadataPair()
         self._m_dictMetadataPairs[sFilePath] = fmdp
      # Always re-read the file metadata because if we obtained it during scheduling, the file might
      # have been regenerated now that jobs have been run.
      fmdp.current = FileMetadata(sFilePath)
      # Replace the stored metadata.
      fmdp.stored = fmdp.current
      self._m_bDirty = True


   def write(self):
      """Stores metadata to the file from which it was loaded."""

      if not self._m_bDirty:
         return

      # Create an empty XML document.
      doc = xml.dom.getDOMImplementation().createDocument(
         doctype       = None,
         namespaceURI  = None,
         qualifiedName = None,
      )
      eltRoot = doc.appendChild(doc.createElement('metadata'))
      # Add metadata for each file.
      for sFilePath, fmdp in self._m_dictMetadataPairs.items():
         eltFile = eltRoot.appendChild(doc.createElement('file'))
         eltFile.setAttribute('path', sFilePath)
         # Add the metadata as attributes for this <file> element.
         for sName, oValue in fmdp.stored.__getstate__().items():
            eltFile.setAttribute(sName, str(oValue))
      # Write the document to file.
      os.makedirs(os.path.dirname(self._m_sFilePath), 0o755, True)
      with open(self._m_sFilePath, 'w') as fileMetadata:
         doc.writexml(fileMetadata, addindent = '   ', newl = '\n')

