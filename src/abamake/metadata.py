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
# FileSignature

class FileSignature(object):
   """Signature metadata for a single file."""

   __slots__ = (
      # Date/time of the file’s last modification.
      '_m_dtMTime',
   )


   def __init__(self, sFilePath):
      """Constructor.

      str sFilePath
         Path to the file for which a signature should be generated.
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
# FileSignaturesPair

class FileSignaturesPair(object):
   """Handles storage and retrieval of file signatures."""

   __slots__ = (
      # Stored file signature, or None if the file’s signature was never collected.
      'stored',
      # Current file signature, or None if the file’s signature has not yet been refreshed.
      'current',
   )


   def __init__(self):
      self.stored = None
      self.current = None



####################################################################################################
# MetadataStore

class MetadataStore(object):
   """Handles storage and retrieval of file metadata."""

   # True if any changes occurred, which means that the metadata file should be updated.
   _m_bDirty = False
   # Persistent storage file path.
   _m_sFilePath = None
   # Signature for each file (str -> FileSignaturesPair).
   _m_dictSigPairs = None


   def file_changed(self, sFilePath):
      """Compares the signature stored for the specified file against the file’s current signature.

      str sFilePath
         Path to the file of which to compare signatures.
      bool return
         True if the file is determined to have changed, or False otherwise.
      """

      fsigp = self._m_dictSigPairs.get(sFilePath)
      # If we have no stored signature to compare to, report the file as changed.
      if fsigp is None or fsigp.stored is None:
         return True
      # If we still haven’t read the file’s current signature, generate one now.
      if fsigp.current is None:
         try:
            fsigp.current = FileSignature(sFilePath)
         except FileNotFoundError:
            # If the file doesn’t exist (anymore), consider it changed.
            return True

      # Compare stored vs. current signature.
      return fsigp.current != fsigp.stored


   def read(self, sFilePath):
      """Reads metadata from the specified file.

      str sFilePath
         Metadata storage file.
      bool return
         True if the file was successfully loaded, or False if the metadata was not read; in the
         latter case, the store will remain empty, but it will memorize its file path.
      """

      self._m_sFilePath = sFilePath
      self._m_dictSigPairs = {}
      try:
         doc = xml.dom.minidom.parse(sFilePath)
      except FileNotFoundError:
         # If we can’t load the persistent metadata store, start it anew.
         return False

      # Parse the metadata.
      doc.documentElement.normalize()
      with doc.documentElement as eltRoot:
         for eltTop in eltRoot.childNodes:
            # Skip unimportant nodes.
            if eltTop.nodeType != eltTop.ELEMENT_NODE:
               continue
            if eltTop.nodeName == 'signatures':
               for eltFile in eltTop.childNodes:
                  # Skip unimportant nodes.
                  if eltFile.nodeType != eltFile.ELEMENT_NODE or eltFile.nodeName != 'file':
                     continue
                  # Parse this <file> element into the “stored” FileSignature member of a new
                  # FileSignaturesPair instance.
                  fsigp = FileSignaturesPair()
                  fsigp.stored = FileSignature.__new__(FileSignature)
                  fsigp.stored.__setstate__(eltFile.attributes)
                  self._m_dictSigPairs[eltFile.getAttribute('path')] = fsigp
      return True


   def update_file_signature(self, sFilePath):
      """Creates or updates the signature for the specified file.

      str sFilePath
         Path to the file the signature of which should be updated.
      """

      fsigp = self._m_dictSigPairs.get(sFilePath)
      # Make sure the signature pair is in the dictionary.
      if fsigp is None:
         fsigp = FileSignaturesPair()
         self._m_dictSigPairs[sFilePath] = fsigp
      # Always re-read the file signature because if we obtained it during scheduling, the file may
      # have been regenerated now that jobs have been run.
      fsigp.current = FileSignature(sFilePath)
      # Replace the stored signature.
      fsigp.stored = fsigp.current
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

      # Add the signatures section.
      eltSigs = eltRoot.appendChild(doc.createElement('signatures'))
      for sFilePath, fsigp in self._m_dictSigPairs.items():
         eltFile = eltSigs.appendChild(doc.createElement('file'))
         eltFile.setAttribute('path', sFilePath)
         # Add the metadata as attributes for this <file> element.
         for sName, oValue in fsigp.stored.__getstate__().items():
            eltFile.setAttribute(sName, str(oValue))

      # Write the document to file.
      with open(self._m_sFilePath, 'w') as fileMetadata:
         doc.writexml(fileMetadata, addindent = '   ', newl = '\n')

