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

import make.target



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


   def to_xml(self, doc, sEltName):
      """Serializes the signature as an XML element.

      xml.dom.Document doc
         XML document to use to create any elements.
      str sEltName
         Name of the base element to create.
      xml.dom.Element return
         Resulting XML element. Note that this will be lacking a “path” attribute.
      """

      eltFile = doc.createElement(sEltName)
      eltFile.setAttribute('mtime', self._m_dtMTime.isoformat(' '))
      return eltFile



####################################################################################################
# TargetSnapshot

class TargetSnapshot(object):
   """Captures information about a target at a specific time. Used to detect changes that should
   trigger a rebuild.
   """

   __slots__ = (
      # Signature of each input (dependency) of this target.
      '_m_dictInputSigs',
      # Signature of each output (generated file) of this target.
      '_m_dictOutputSigs',
      # Target.
      '_m_tgt',
   )


   def __init__(self, tgt, eltTarget = None, dictInputSigs = None, dictOutputSigs = None):
      """Constructor.

      make.target.Target tgt
         Target.
      xml.dom.Element eltTarget
         XML Element to parse to load the target dependencies’ signatures.
      dict(str: make.metadata.FileSignature) dictInputSigs
         File paths associated to their signature; one for each input (dependency) of the target.
      dict(str: make.metadata.FileSignature) dictOutputSigs
         File paths associated to their signature; one for each output (generated file) of the
         target.
      """

      self._m_tgt = tgt
      if eltTarget:
         self._m_dictInputSigs = {}
         self._m_dictOutputSigs = {}
         # Parse the contents of the <target-snapshot> element.
         for eltFile in eltTarget.childNodes:
            if eltFile.nodeType != eltFile.ELEMENT_NODE:
               continue
            # Select to which dictionary we should add this signature.
            if eltFile.nodeName == 'input':
               dictSigs = self._m_dictInputSigs
            elif eltFile.nodeName == 'output':
               dictSigs = self._m_dictOutputSigs
            else:
               continue
            # Parse this element into a FileSignature and store that as a dependency signature.
            dictSigs[eltFile.getAttribute('path')] = FileSignature.parse(eltFile)
      elif dictInputSigs:
         self._m_dictInputSigs = dictInputSigs
         self._m_dictOutputSigs = dictOutputSigs


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
      for sFilePath, fsCurr in self._m_dictInputSigs.items():
         if not fsCurr:
            log(log.HIGH, 'metadata: {}: missing input {}, build will fail', self._m_tgt, sFilePath)
            return False
         fsStored = tssStored._m_dictInputSigs.get(sFilePath)
         if not fsStored:
            log(
               log.HIGH,
               'metadata: {}: file {} not part of stored snapshot, rebuild needed',
               self._m_tgt, sFilePath
            )
            return False
         if fsCurr._m_dtMTime != fsStored._m_dtMTime:
            log(
               log.HIGH,
               'metadata: {}: changes detected in file {} (timestamp was: {}, now: {}), rebuild ' +
                  'needed',
               self._m_tgt, sFilePath, fsStored._m_dtMTime, fsCurr._m_dtMTime
            )
            return False
      for sFilePath, fsCurr in self._m_dictOutputSigs.items():
         if not fsCurr:
            log(log.HIGH, 'metadata: {}: missing output {}, rebuild needed', self._m_tgt, sFilePath)
            return False
         fsStored = tssStored._m_dictOutputSigs.get(sFilePath)
         if not fsStored:
            log(
               log.HIGH,
               'metadata: {}: file {} not part of stored snapshot, rebuild needed',
               self._m_tgt, sFilePath
            )
            return False
         if fsCurr._m_dtMTime != fsStored._m_dtMTime:
            log(
               log.HIGH,
               'metadata: {}: changes detected in file {} (timestamp was: {}, now: {}), rebuild ' +
                  'needed',
               self._m_tgt, sFilePath, fsStored._m_dtMTime, fsCurr._m_dtMTime
            )
            return False

      # A change in the number of signatures should cause a rebuild because it’s a dependencies
      # change, so verify that all signatures in the stored snapshot are still in the current one
      # (self).
      for sFilePath in tssStored._m_dictInputSigs.keys():
         if sFilePath not in self._m_dictInputSigs:
            log(
               log.HIGH,
               'metadata: {}: file {} not part of current snapshot, rebuild needed',
               self._m_tgt, sFilePath
            )
            return False
      for sFilePath in tssStored._m_dictOutputSigs.keys():
         if sFilePath not in self._m_dictOutputSigs:
            log(
               log.HIGH,
               'metadata: {}: file {} not part of current snapshot, rebuild needed',
               self._m_tgt, sFilePath
            )
            return False

      # No changes detected.
      log(log.HIGH, 'metadata: {}: up-to-date', self._m_tgt)
      return True


   def to_xml(self, doc):
      """Serializes the snapshot as an XML element.

      xml.dom.Document doc
         XML document to use to create any elements.
      xml.dom.Element return
         Resulting <target> element.
      """

      tgt = self._m_tgt
      eltTarget = doc.createElement('target')

      # Store the name of the target if named, or its file path otherwise.
      if isinstance(tgt, make.target.NamedTargetMixIn):
         eltTarget.setAttribute('name', tgt.name)
      else:
         eltTarget.setAttribute('path', tgt.file_path)

      # Serialize the signature of each input (dependency).
      for sFilePath, fs in self._m_dictInputSigs.items():
         eltFile = eltTarget.appendChild(fs.to_xml(doc, 'input'))
         eltFile.setAttribute('path', sFilePath)

      # Serialize the signature of each output (generated file).
      for sFilePath, fs in self._m_dictOutputSigs.items():
         eltFile = eltTarget.appendChild(fs.to_xml(doc, 'output'))
         eltFile.setAttribute('path', sFilePath)

      return eltTarget



####################################################################################################
# MetadataStore

class MetadataStore(object):
   """Handles storage and retrieval of file metadata."""

   # Freshly-read target snapshots (make.target.Target -> TargetSnapshot).
   _m_dictCurrTargetSnapshots = None
   # True if any changes occurred, which means that the metadata file should be updated.
   _m_bDirty = None
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
      self._m_bDirty = False
      self._m_sFilePath = sFilePath
      self._m_log = mk.log
      self._m_dictSignatures = {}
      self._m_dictStoredTargetSnapshots = {}

      log = self._m_log
      try:
         doc = xml.dom.minidom.parse(sFilePath)
      except FileNotFoundError:
         # If we can’t load the persistent metadata store, start it anew.
         log(log.HIGH, 'metadata: empty or missing store: {}', sFilePath)
      else:
         log(log.HIGH, 'metadata: loading store: {}', sFilePath)
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
                     tgt = mk.get_named_target(eltTarget.getAttribute('name'), None) or \
                           mk.get_file_target(eltTarget.getAttribute('path'), None)
                     if tgt:
                        self._m_dictStoredTargetSnapshots[tgt] = TargetSnapshot(
                           tgt, eltTarget = eltTarget
                        )
         log(log.HIGH, 'metadata: store loaded: {}', sFilePath)


   def _collect_signatures(self, iterFilePaths, dictOut, bForceCacheUpdate = False):
      """Retrieves the signatures for the specified file paths and stores them in the provided
      dictionary.

      If iterFilePaths enumerates output files that may not exist yet, signatures are cached because
      we know that the target will call MetadataStore.update_target_snapshot() before its
      dependencies will attempt to generate a snapshot for themselves, so the signatures for this
      target’s outputs (i.e. its dependents’ inputs) will be updated before being used again.

      If iterFilePaths enumerates inputs files (dependencies of a target), signatures are cached
      because the files must’ve already been built, or we wouldn’t be trying to generate a snapshot
      for a target dependent on them yet. The only case in which files may not exist is if we’re
      running in “dry run” mode, which causes no files to be created or modified.

      iterable(str*) iterFilePaths
         Enumerates file paths.
      dict(str: make.metadata.FileSignature) dictOut
         Dictionary in which every signature will be stored, even if None.
      bool bForceCacheUpdate
         If True, the signatures cache will not be read, but newly-read signatures will be written
         to it. If False, signatures will first be looked up in the cache, and stored in it only if
         missing.
      """

      for sFilePath in iterFilePaths:
         if bForceCacheUpdate:
            # Don’t use the cache.
            fs = None
         else:
            # See if we already have a signature for this file in the cache.
            fs = self._m_dictSignatures.get(sFilePath)
         if not fs:
            # Need to read this file’s signature.
            try:
               fs = FileSignature.generate(sFilePath)
            except FileNotFoundError:
               fs = None
            # Cache this signature.
            self._m_dictSignatures[sFilePath] = fs
         # Return this signature.
         dictOut[sFilePath] = fs


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
         # Collect signatures for all the target’s dependencies’ generated files (inputs).
         dictInputSigs = {}
         for dep in tgt.get_dependencies():
            self._collect_signatures(dep.get_generated_files(), dictInputSigs)
         # Collect signatures for all the target’s generated files (outputs).
         dictOutputSigs = {}
         if isinstance(tgt, make.target.FileTarget):
            self._collect_signatures(tgt.get_generated_files(), dictOutputSigs)
         # Instantiate the current snapshot.
         tssCurr = TargetSnapshot(
            tgt, dictInputSigs = dictInputSigs, dictOutputSigs = dictOutputSigs
         )
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
         log(log.HIGH, 'metadata: {}: no stored snapshot, build needed', tgt)
         return True

      # Compare current and stored snapshots.
      return not tssCurr.equals_stored(tssStored, log)


   def update_target_snapshot(self, tgt):
      """Updates the snapshot for the specified target.

      make.target.Target tgt
         Target for which to update the snapshot.
      """

      log = self._m_log
      log(log.HIGH, 'metadata: {}: updating target snapshot', tgt)

      tssCurr = self._get_curr_target_snapshot(tgt)
      if isinstance(tgt, make.target.FileTarget):
         # Recreate signatures for all the target’s generated files (outputs).
         self._collect_signatures(
            tgt.get_generated_files(), tssCurr._m_dictOutputSigs, bForceCacheUpdate = True
         )
      self._m_dictStoredTargetSnapshots[tgt] = tssCurr
      self._m_bDirty = True


   def write(self):
      """Stores metadata to the file from which it was loaded."""

      log = self._m_log
      if not self._m_bDirty:
         log(log.HIGH, 'metadata: no changes to write')
         return
      log(log.HIGH, 'metadata: writing changes to store: {}', self._m_sFilePath)

      # Create an empty XML document.
      doc = xml.dom.getDOMImplementation().createDocument(
         doctype       = None,
         namespaceURI  = None,
         qualifiedName = None,
      )
      eltRoot = doc.appendChild(doc.createElement('abcmk-metadata'))

      # Add the stored target snapshots to their section.
      eltTgtSnaps = eltRoot.appendChild(doc.createElement('target-snapshots'))
      for tss in self._m_dictStoredTargetSnapshots.values():
         eltTgtSnaps.appendChild(tss.to_xml(doc))

      # Write the document to file.
      with open(self._m_sFilePath, 'w') as fileMetadata:
         doc.writexml(fileMetadata, addindent = '   ', newl = '\n')

      # Now that everything went well, update the internal state to look like we just read the file
      # we just wrote to.
      self._m_dictCurrTargetSnapshots = {}
      self._m_dictSignatures = {}
      self._m_bDirty = False

