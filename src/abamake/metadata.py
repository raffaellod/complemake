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
import weakref
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


   def __init__(self):
      """Constructor."""

      self._m_dtMTime = None


   @classmethod
   def generate(cls, sFilePath):
      """Generates a signature for the specified file.

      str sFilePath
         Path to the file for which a signature should be generated.
      FileSignature return
         Generated signature.
      """

      self = cls()
      self._m_dtMTime = datetime.fromtimestamp(os.path.getmtime(sFilePath))
      return self


   @classmethod
   def parse(cls, eltFile):
      """Loads a signature from the specified <file> element.

      xml.dom.Element eltFile
         <file> element to parse.
      FileSignature return
         Loaded signature.
      """

      self = cls()
      for sName, sValue in eltFile.attributes.items():
         if sName == 'mtime':
            self._m_dtMTime = datetime.strptime(sValue, '%Y-%m-%d %H:%M:%S.%f')
      return self


   def save(self, eltFile):
      """Saves the signature as attributes for the specified XML element.

      xml.dom.Element eltFile
         <file> element on which to set metadata attributes.
      """

      eltFile.setAttribute('mtime', self._m_dtMTime.isoformat(' '))


   def __eq__(self, other):
      return self._m_dtMTime == other._m_dtMTime


   def __ne__(self, other):
      return not self.__eq__(other)



####################################################################################################
# TargetSnapshot

class TargetSnapshot(object):
   """Captures information about a target at a specific time. Used to detect changes that should
   trigger a rebuild.
   """

   __slots__ = (
      # Signature of each dependency of this target.
      '_m_dictDepsSignatures',
      # Target.
      '_m_tgt',
   )


   def __init__(self, tgt, dictDepsSignatures = None, eltTarget = None):
      """Constructor.

      make.target.Target tgt
         Target.
      dict(str, FileSignature) dictDepsSignatures
         File paths associated to their signature; one for each dependency of the target.
      xml.dom.Element eltTarget
         XML Element to parse to load the target dependencies’ signatures.
      """

      self._m_tgt = tgt
      if eltTarget:
         self._m_dictDepsSignatures = {}
         # Parse the contents of the <target-snapshot> element.
         for eltFile in eltTarget.childNodes:
            if eltFile.nodeType != eltFile.ELEMENT_NODE or eltFile.nodeName != 'file':
               continue
            # Parse this <file> into a FileSignature and store that as a dependency signature.
            self._m_dictDepsSignatures[eltFile.getAttribute('path')] = FileSignature.parse(eltFile)
      elif dictDepsSignatures:
         self._m_dictDepsSignatures = dictDepsSignatures


   def __eq__(self, other):
      return self._m_tgt == other._m_tgt and \
             self._m_dictDepsSignatures == other._m_dictDepsSignatures


   def __ne__(self, other):
      return not self.__eq__(other)



####################################################################################################
# MetadataStore

class MetadataStore(object):
   """Handles storage and retrieval of file metadata."""

   # Freshly-read target snapshots (make.target.Target -> TargetSnapshot).
   _m_dictCurrTargetSnapshots = None
   # True if any changes occurred, which means that the metadata file should be updated.
   _m_bDirty = False
   # Persistent storage file path.
   _m_sFilePath = None
   # Weak reference to the owning make.Make instance.
   _m_mk = None
   # Signature for each file (str -> FileSignature).
   _m_dictSignatures = None
   # Target snapshots as stored in the metadata file (make.target.Target -> TargetSnapshot).
   _m_dictStoredTargetSnapshots = None


   def __init__(self, mk):
      """Constructor.

      make.Make mk
         Make instance.
      """

      self._m_dictCurrTargetSnapshots = {}
      self._m_mk = weakref.ref(mk)
      self._m_dictSignatures = {}
      self._m_dictStoredTargetSnapshots = {}


   def compare_target_snapshot(self, tgt, iterDepsFilePaths):
      """Checks if the specified target needs to be rebuilt: compares the current signature of the
      dependency files in iterDepsFilePaths with the signature stored in the target’s snapshot,
      returning True if any differences are detected.

      The new signatures are stored internally, and will be used to update the target’s snapshot
      once MetadataStore.update_target_snapshot() is called.

      make.target.Target tgt
         Target for which to get a new snapshot to compare with the stored one.
      iter(str*) iterDepsFilePaths
         File path of each dependency for tgt.
      bool return
         True if any files have changed since the last build, or False otherwise.
      """

      tssStored = self._m_dictStoredTargetSnapshots.get(tgt)
      tssCurr = self._m_dictCurrTargetSnapshots.get(tgt)

      if not tssCurr:
         # Generate signatures for all the specified dependencies.
         dictDepsSignatures = {}
         for sFilePath in iterDepsFilePaths:
            fs = self._m_dictSignatures.get(sFilePath)
            if not fs:
               # If we still haven’t read this file’s current signature, generate it now.
               fs = FileSignature.generate(sFilePath)
               # Store this signature, in case other targets also need it.
               self._m_dictSignatures[sFilePath] = fs
            dictDepsSignatures[sFilePath] = fs
         # Instantiate the current snapshot.
         tssCurr = TargetSnapshot(
            tgt, dictDepsSignatures = dictDepsSignatures
         )
         self._m_dictCurrTargetSnapshots[tgt] = tssCurr

      # If we have no stored snapshot to compare to, report the build as necessary.
      if not tssStored:
         return True

      # Compare current and stored snapshots.
      if tssCurr != tssStored:
         if self._m_mk().verbosity >= self._m_mk().VERBOSITY_HIGH:
            sys.stdout.write(
               'metadata: {} needs to be (re)built\n'.format(tgt.name or tgt.file_path)
            )
         return True
      else:
         if self._m_mk().verbosity >= self._m_mk().VERBOSITY_HIGH:
            sys.stdout.write('metadata: {} is up-to-date\n'.format(tgt.name or tgt.file_path))
         return False


   def read(self, sFilePath):
      """Reads metadata from the specified file.

      str sFilePath
         Metadata storage file.
      bool return
         True if the file was successfully loaded, or False if the metadata was not read; in the
         latter case, the store will remain empty, but it will memorize its file path.
      """

      self._m_sFilePath = sFilePath
      try:
         doc = xml.dom.minidom.parse(sFilePath)
      except FileNotFoundError:
         # If we can’t load the persistent metadata store, start it anew.
         return False

      mk = self._m_mk()
      # Parse the metadata.
      doc.documentElement.normalize()
      with doc.documentElement as eltRoot:
         for eltTop in eltRoot.childNodes:
            # Skip unimportant nodes.
            if eltTop.nodeType != eltTop.ELEMENT_NODE:
               continue
            if eltTop.nodeName == 'target-snapshots':
               # Parse all target snapshots.
               for eltTarget in eltTop.childNodes:
                  # Skip unimportant nodes.
                  if eltTarget.nodeType != eltTarget.ELEMENT_NODE or eltTarget.nodeName != 'target':
                     continue
                  sFilePath = eltTarget.getAttribute('path')
                  sName = eltTarget.getAttribute('name')
                  # It’s possible that no such target exists. Maybe it did in the past, but not now.
                  tgt = mk.get_target_by_name(sName, None) or \
                        mk.get_target_by_file_path(sFilePath, None)
                  if tgt:
                     self._m_dictStoredTargetSnapshots[tgt] = TargetSnapshot(
                        tgt, eltTarget = eltTarget
                     )
      return True


   def update_target_snapshot(self, tgt):
      """Updates the snapshot for the specified target.

      make.target.Target tgt
         Target for which to update the snapshot.
      """

      if self._m_mk().verbosity >= self._m_mk().VERBOSITY_HIGH:
         sys.stdout.write(
            'metadata: updating target snapshot: {}\n'.format(tgt.name or tgt.file_path)
         )
      self._m_dictStoredTargetSnapshots[tgt] = self._m_dictCurrTargetSnapshots[tgt]
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
      eltRoot = doc.appendChild(doc.createElement('abcmk-metadata'))

      # Add the signatures section.
      eltTgtSnaps = eltRoot.appendChild(doc.createElement('target-snapshots'))
      for tgt, tgtsnap in self._m_dictCurrTargetSnapshots.items():
         eltTarget = eltTgtSnaps.appendChild(doc.createElement('target'))
         if tgt.name:
            eltTarget.setAttribute('name', tgt.name)
         elif tgt.file_path:
            eltTarget.setAttribute('path', tgt.file_path)
         for sFilePath, fsig in tgtsnap._m_dictDepsSignatures.items():
            eltFile = eltTarget.appendChild(doc.createElement('file'))
            eltFile.setAttribute('path', sFilePath)
            fsig.save(eltFile)

      # Write the document to file.
      with open(self._m_sFilePath, 'w') as fileMetadata:
         doc.writexml(fileMetadata, addindent = '   ', newl = '\n')

