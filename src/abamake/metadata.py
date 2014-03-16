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


   def __init__(self):
      """Constructor."""

      self._m_dtMTime = None


   @classmethod
   def generate(cls, sFilePath):
      """Generates a signature for the specified file.

      str sFilePath
         Path to the file for which a signature should be generated.
      make.metadata.FileSignature return
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
      make.metadata.FileSignature return
         Loaded signature.
      """

      self = cls()
      for sName, sValue in eltFile.attributes.items():
         if sName == 'mtime':
            self._m_dtMTime = datetime.strptime(sValue, '%Y-%m-%d %H:%M:%S.%f')
      return self


   def to_xml(self, doc):
      """Serializes the signature as an XML element.

      xml.dom.Document doc
         XML document to use to create any elements.
      xml.dom.Element return
         Resulting <file> element. Note that this will be lacking a “path” attribute.
      """

      eltFile = doc.createElement('file')
      eltFile.setAttribute('mtime', self._m_dtMTime.isoformat(' '))
      return eltFile



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
      dict(str: make.metadata.FileSignature) dictDepsSignatures
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


   def equals_stored(self, tssStored, log):
      """Compares self (current snapshot) with the stored snapshot for the same target, logging any
      detected differences.

      make.metadata.TargetSnapshot tssStored
         Stored snapshot.
      make.Logger log
         Log instance.
      bool return
         True if the two snapshots are equal, of False in case of any differences.
      """

      assert self._m_tgt == tssStored._m_tgt, 'comparing snapshots of different targets'

      # Check that all signatures in the current snapshot (self) match those in the stored snapshot.
      for sFilePath, fsCurr in self._m_dictDepsSignatures.items():
         fsStored = tssStored._m_dictDepsSignatures.get(sFilePath)
         if fsStored is None:
            log(
               log.HIGH,
               'metadata: {}: file {} not part of stored snapshot, rebuild needed\n',
               self._m_tgt, sFilePath
            )
            return False
         if fsCurr._m_dtMTime != fsStored._m_dtMTime:
            log(
               log.HIGH,
               'metadata: {}: changes detected in file {} (timestamp was: {}, now: {}), rebuild ' +
                  'needed\n',
               self._m_tgt, sFilePath, fsCurr._m_dtMTime, fsStored._m_dtMTime
            )
            return False

      # A change in the number of signatures should cause a rebuild because it’s a dependencies
      # change, so verify that all signatures in the stored snapshot are still in the current one
      # (self).
      for sFilePath in tssStored._m_dictDepsSignatures.keys():
         if sFilePath not in self._m_dictDepsSignatures:
            log(
               log.HIGH,
               'metadata: {}: file {} not part of current snapshot, rebuild needed\n',
               self._m_tgt, sFilePath
            )
            return False

      # No changes detected.
      log(log.HIGH, 'metadata: {}: up-to-date\n', self._m_tgt)
      return True


   def to_xml(self, doc):
      """Serializes the snapshot as an XML element.

      xml.dom.Document doc
         XML document to use to create any elements.
      xml.dom.Element return
         Resulting <target> element.
      """

      eltTarget = doc.createElement('target')

      # Store the name of the target or, lacking that, its file path.
      sTargetName = self._m_tgt.name
      if sTargetName:
         eltTarget.setAttribute('name', sTargetName)
      else:
         sTargetFilePath = self._m_tgt.file_path
         if sTargetFilePath:
            eltTarget.setAttribute('path', sTargetFilePath)

      # Serialize the signature of each dependency.
      for sFilePath, fs in self._m_dictDepsSignatures.items():
         eltFile = eltTarget.appendChild(fs.to_xml(doc))
         eltFile.setAttribute('path', sFilePath)

      return eltTarget



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
   # Output log.
   _m_log = None
   # Signature for each file (str -> FileSignature).
   _m_dictSignatures = None
   # Target snapshots as stored in the metadata file (make.target.Target -> TargetSnapshot).
   _m_dictStoredTargetSnapshots = None


   def __init__(self, mk, sFilePath):
      """Constructor. Reads metadata from the specified file.

      make.Make mk
         Make instance.
      str sFilePath
         Metadata storage file.
      """

      self._m_dictCurrTargetSnapshots = {}
      self._m_sFilePath = sFilePath
      self._m_log = mk.log
      self._m_dictSignatures = {}
      self._m_dictStoredTargetSnapshots = {}

      log = self._m_log
      try:
         doc = xml.dom.minidom.parse(sFilePath)
      except FileNotFoundError:
         # If we can’t load the persistent metadata store, start it anew.
         log(log.HIGH, 'metadata: empty or missing store: {}\n', sFilePath)
      else:
         log(log.HIGH, 'metadata: loading store: {}\n', sFilePath)
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
                     if eltTarget.nodeType != eltTarget.ELEMENT_NODE or \
                        eltTarget.nodeName != 'target' \
                     :
                        continue
                     # Allow for None because it’s possible that no such target exists – maybe it
                     # used to, but not anymore.
                     tgt = mk.get_target_by_name(eltTarget.getAttribute('name'), None) or \
                           mk.get_target_by_file_path(eltTarget.getAttribute('path'), None)
                     if tgt:
                        self._m_dictStoredTargetSnapshots[tgt] = TargetSnapshot(
                           tgt, eltTarget = eltTarget
                        )
         log(log.HIGH, 'metadata: store loaded: {}\n', sFilePath)


   def _get_curr_target_snapshot(self, tgt):
      """Returns a current snapshot for the specified target, creating one first it none such
      exists.

      make.target.Target tgt
         Target for which to return a current snapshot.
      make.metadata.TargetSnapshot return
         Current target snapshot.
      """

      tssCurr = self._m_dictCurrTargetSnapshots.get(tgt)
      if not tssCurr:
         # Generate signatures for all the target’s dependencies.
         dictDepsSignatures = {}
         for dep in tgt.get_dependencies():
            sFilePath = dep.file_path
            # See if we already have a signature for this file in the cache.
            # The cache is supposed to always be current, because when we’re asked to check for the
            # signature of a file, it means that the target for which we’re doing it is ready to be
            # built, which means that the file has already been built and won’t be again, so when we
            # cache a file signature, it won’t need to be refreshed.
            fs = self._m_dictSignatures.get(sFilePath)
            if not fs:
               # If we still haven’t read this file’s current signature, generate it now.
               fs = FileSignature.generate(sFilePath)
               # Store this signature, in case other targets also need it.
               self._m_dictSignatures[sFilePath] = fs
            dictDepsSignatures[sFilePath] = fs
         # Instantiate the current snapshot.
         tssCurr = TargetSnapshot(tgt, dictDepsSignatures = dictDepsSignatures)
         self._m_dictCurrTargetSnapshots[tgt] = tssCurr

      return tssCurr


   def has_target_snapshot_changed(self, tgt):
      """Checks if the specified target needs to be rebuilt: compares the current signature of its
      dependencies with the signatures stored in the target’s snapshot, returning True if any
      differences are detected.

      The new signatures are stored internally, and will be used to update the target’s snapshot
      once MetadataStore.update_target_snapshot() is called.

      make.target.Target tgt
         Target for which to get a new snapshot to compare with the stored one.
      bool return
         True if any files have changed since the last build, or False otherwise.
      """

      log = self._m_log

      tssStored = self._m_dictStoredTargetSnapshots.get(tgt)
      tssCurr = self._get_curr_target_snapshot(tgt)

      # If we have no stored snapshot to compare to, report the build as necessary.
      if not tssStored:
         log(log.HIGH, 'metadata: {}: no stored snapshot, build needed\n', tgt)
         return True

      # Compare current and stored snapshots.
      return not tssCurr.equals_stored(tssStored, log)


   def update_target_snapshot(self, tgt):
      """Updates the snapshot for the specified target.

      make.target.Target tgt
         Target for which to update the snapshot.
      """

      log = self._m_log
      log(log.HIGH, 'metadata: {}: updating target snapshot\n', tgt)
      self._m_dictStoredTargetSnapshots[tgt] = self._get_curr_target_snapshot(tgt)
      self._m_bDirty = True


   def write(self):
      """Stores metadata to the file from which it was loaded."""

      log = self._m_log
      if not self._m_bDirty:
         log(log.HIGH, 'metadata: no changes to write\n')
         return
      log(log.HIGH, 'metadata: writing changes to store: {}\n', self._m_sFilePath)

      # Create an empty XML document.
      doc = xml.dom.getDOMImplementation().createDocument(
         doctype       = None,
         namespaceURI  = None,
         qualifiedName = None,
      )
      eltRoot = doc.appendChild(doc.createElement('abcmk-metadata'))

      # Add the signatures section.
      eltTgtSnaps = eltRoot.appendChild(doc.createElement('target-snapshots'))
      for tss in self._m_dictCurrTargetSnapshots.values():
         eltTgtSnaps.appendChild(tss.to_xml(doc))

      # Write the document to file.
      with open(self._m_sFilePath, 'w') as fileMetadata:
         doc.writexml(fileMetadata, addindent = '   ', newl = '\n')

