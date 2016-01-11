#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013-2016 Raffaello D. Di Napoli
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

"""Metadata management classes."""

import datetime
import os
import sys
import yaml
import yaml.generator
import yaml.parser

import abamake.target

if sys.hexversion >= 0x03000000:
   basestring = str


####################################################################################################

class MetadataParser(yaml.parser.Parser):
   """Parser of Abamake’s metadata YAML files."""

   def __init__(self, mk):
      """Constructor.

      abamake.make.Make mk
         Make instance to make accessible via self.mk .
      """

      yaml.parser.Parser.__init__(self)

      self._m_mk = mk

   def _get_mk(self):
      return self._m_mk

   mk = property(_get_mk, doc = """Returns the Make instance that’s running the parser.""")

####################################################################################################

# MetadataStore.get_signatures() modes.
ASSUME_NEW   = 1
UPDATE_CACHE = 2
USE_CACHE    = 3

@MetadataParser.local_tag('abamake/metadata/file-signature', yaml.Kind.MAPPING)
class FileSignature(object):
   """Signature metadata for a single file."""

   __slots__ = (
      # Path to the file this signature is about.
      '_m_sFilePath',
      # Date/time of the file’s last modification.
      '_m_dtMTime',
   )

   def __init__(self, *iterArgs):
      """Constructor.

      abamake.metadata.MetadataParser mp
         Parser instantiating the object.
      dict(object: object) dictYaml
         Parsed YAML object to be used to construct the new instance.

      - OR -

      str sFilePath
         Path to the file this signature is about.
      """

      if isinstance(iterArgs[0], MetadataParser):
         mp, dictYaml = iterArgs
      else:
         dictYaml = None
         sFilePath, = iterArgs

      if dictYaml:
         oPath = dictYaml.get('path')
         if not isinstance(oPath, basestring):
            mp.raise_parsing_error('missing or invalid “path” attribute')
         self._m_sFilePath = oPath

         oMTime = dictYaml.get('mtime')
         if not isinstance(oMTime, datetime.datetime):
            mp.raise_parsing_error('missing or invalid “mtime” attribute')
         self._m_dtMTime = oMTime
      else:
         self._m_sFilePath = sFilePath
         self._m_dtMTime = None

   def __yaml__(self, yg):
      """TODO: comment."""

      yg.write_mapping_begin('!abamake/metadata/file-signature')
      yg.produce_from_object('path')
      yg.produce_from_object(self._m_sFilePath)
      yg.produce_from_object('mtime')
      yg.produce_from_object(self._m_dtMTime)
      yg.write_mapping_end()

   @classmethod
   def fake_new(cls, sFilePath):
      """Generates a fake signature that no real file can ever match.

      str sFilePath
         Path to the file associated to the signature.
      abamake.metadata.FileSignature return
         Generated signature.
      """

      self = cls(sFilePath)
      self._m_dtMTime = 0xffffffff
      return self

   @classmethod
   def generate(cls, sFilePath):
      """Generates a signature for the specified file.

      str sFilePath
         Path to the file for which a signature should be generated.
      abamake.metadata.FileSignature return
         Generated signature.
      """

      self = cls(sFilePath)
      self._m_dtMTime = datetime.datetime.fromtimestamp(os.path.getmtime(sFilePath))
      return self

####################################################################################################

@MetadataParser.local_tag('abamake/metadata/target-snapshot', yaml.Kind.MAPPING)
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

   def __init__(self, *iterArgs):
      """Constructor.

      abamake.metadata.MetadataParser mp
         Parser instantiating the object.
      dict(object: object) dictYaml
         Parsed YAML object to be used to construct the new instance.

      - OR -

      abamake.metadata.MetadataStore mds
         MetadataStore instance.
      abamake.target.Target tgt
         Target to collect signatures for from the file system.
      """

      if isinstance(iterArgs[0], MetadataParser):
         mp, dictYaml = iterArgs
      else:
         dictYaml = None
         mds, tgt = iterArgs

      self._m_dictInputSigs = {}
      self._m_dictOutputSigs = {}

      if dictYaml:
         mk = mp.mk

         # Allow for None to be returned by mk.get_*_target() because it’s possible that no such
         # target exists – maybe it used to, but not anymore.
         sName = dictYaml.get('name')
         sPath = dictYaml.get('path')
         if sName:
            self._m_tgt = mk.get_named_target(sName, None)
         elif sPath:
            self._m_tgt = mk.get_file_target(sPath, None)
         else:
            mp.raise_parsing_error('expected one attribute of “name” or “path”')
         if not self._m_tgt:
            # The condition above will make the MetadataStore ignore this signature.
            return

         oInputs = dictYaml.get('inputs')
         if oInputs:
            if not isinstance(oInputs, list):
               mp.raise_parsing_error('attribute “inputs” must be a sequence')
            for i, o in enumerate(oInputs):
               if not isinstance(o, FileSignature):
                  mp.raise_parsing_error((
                     'elements of the “inputs” attribute must be of type ' +
                     '!abamake/metadata/file-signature, but element [{}] is not'
                  ).format(i))
               self._m_dictInputSigs[o._m_sFilePath] = o

         oOutputs = dictYaml.get('outputs')
         if oOutputs:
            if not isinstance(oOutputs, list):
               mp.raise_parsing_error('attribute “outputs” must be a sequence')
            for i, o in enumerate(oOutputs):
               if not isinstance(o, FileSignature):
                  mp.raise_parsing_error((
                     'elements of the “outputs” attribute must be of type ' +
                     '!abamake/metadata/file-signature, but element [{}] is not'
                  ).format(i))
               self._m_dictOutputSigs[o._m_sFilePath] = o
      else:
         self._m_tgt = tgt
         # Collect signatures for all the target’s dependencies’ generated files (inputs).
         for dep in tgt.get_dependencies():
            mds.get_signatures(dep.get_generated_files(), self._m_dictInputSigs, USE_CACHE)
         # Collect signatures for all the target’s generated files (outputs).
         if isinstance(tgt, abamake.target.FileTarget):
            mds.get_signatures(tgt.get_generated_files(), self._m_dictOutputSigs, USE_CACHE)

   def __yaml__(self, yg):
      """TODO: comment."""

      tgt = self._m_tgt
      yg.write_mapping_begin('!abamake/metadata/target-snapshot')

      # Store the name of the target if named, or its file path otherwise.
      if isinstance(tgt, abamake.target.NamedTargetMixIn):
         yg.produce_from_object('name')
         yg.produce_from_object(tgt.name)
      else:
         yg.produce_from_object('path')
         yg.produce_from_object(tgt.file_path)

      # Serialize the signature of each input.
      yg.produce_from_object('inputs')
      yg.produce_from_object(self._m_dictInputSigs.values())

      # Serialize the signature of each output.
      yg.produce_from_object('outputs')
      yg.produce_from_object(self._m_dictOutputSigs.values())

      yg.write_mapping_end()

   def equals_stored(self, tssStored, log):
      """Compares self (current snapshot) with the stored snapshot for the same target, logging any
      detected differences.

      abamake.metadata.TargetSnapshot tssStored
         Stored snapshot.
      abamake.Logger log
         Log instance.
      bool return
         True if the two snapshots are equal, of False in case of any differences.
      """

      tgt = self._m_tgt
      assert tgt == tssStored._m_tgt, 'comparing snapshots of different targets'

      for bInputs, dictStored, dictCurr in \
         (True,  tssStored._m_dictInputSigs,  self._m_dictInputSigs ), \
         (False, tssStored._m_dictOutputSigs, self._m_dictOutputSigs) \
      :
         # Check that all signatures in the current snapshot (self) match those in the stored
         # snapshot.
         for sFilePath, fsCurr in dictCurr.items():
            if not fsCurr:
               if bInputs:
                  log(log.HIGH, 'metadata: {}: missing input {}, build will fail', tgt, sFilePath)
               else:
                  log(log.HIGH, 'metadata: {}: missing output {}, rebuild needed', tgt, sFilePath)
               return False
            fsStored = dictStored.get(sFilePath)
            if not fsStored:
               log(
                  log.HIGH,
                  'metadata: {}: file {} not part of stored snapshot, rebuild needed',
                  tgt, sFilePath
               )
               return False
            if fsCurr._m_dtMTime != fsStored._m_dtMTime:
               log(
                  log.HIGH,
                  'metadata: {}: changes detected in file {} (mtime was: {}, now: {}), rebuild ' + \
                     'needed',
                  tgt, sFilePath, fsStored._m_dtMTime, fsCurr._m_dtMTime
               )
               return False

         # A change in the number of signatures should cause a rebuild because it’s a change in
         # inputs (dependencies) or outputs, so verify that all signatures in the stored snapshot
         # are also in the current one (self).
         for sFilePath in dictStored.keys():
            if sFilePath not in dictCurr:
               log(
                  log.HIGH,
                  'metadata: {}: file {} not part of current snapshot, rebuild needed',
                  tgt, sFilePath
               )
               return False

      # No changes detected.
      log(log.HIGH, 'metadata: {}: up-to-date', tgt)
      return True

   def update(self, mds, bDryRun):
      """Updates the snapshot.

      abamake.metadata.MetadataStore mds
         MetadataStore instance.
      bool bDryRun
         True if “dry run” mode is active, or False otherwise.
      """

      if isinstance(self._m_tgt, abamake.target.FileTarget):
         # Recreate signatures for all the target’s generated files (outputs).
         mds.get_signatures(
            self._m_tgt.get_generated_files(), self._m_dictOutputSigs,
            ASSUME_NEW if bDryRun else UPDATE_CACHE
         )

####################################################################################################

@MetadataParser.local_tag('abamake/metadata/store', yaml.Kind.MAPPING)
class MetadataStore(object):
   """Handles storage and retrieval of file metadata."""

   # Freshly-read target snapshots (abamake.target.Target -> TargetSnapshot).
   _m_dictCurrTargetSnapshots = None
   # True if any changes occurred, which means that the metadata file should be updated.
   _m_bDirty = None
   # Persistent storage file path.
   _m_sFilePath = None
   # Output log.
   _m_log = None
   # Signature for each file (str -> FileSignature).
   _m_dictSignatures = None
   # Target snapshots as stored in the metadata file (abamake.target.Target -> TargetSnapshot).
   _m_dictStoredTargetSnapshots = None

   def __init__(self, *iterArgs):
      """Constructor. Reads metadata from the specified file.

      abamake.metadata.MetadataParser mp
         Parser instantiating the object.
      dict(object: object) dictYaml
         Parsed YAML object to be used to construct the new instance.

      - OR -

      abamake.Make mk
         Make instance.
      str sFilePath
         Metadata storage file.
      """

      if isinstance(iterArgs[0], MetadataParser):
         mp, dictYaml = iterArgs
         mk = mp.mk
         sFilePath = mp.source_name
      else:
         dictYaml = None
         mk, sFilePath = iterArgs

      self._m_dictCurrTargetSnapshots = {}
      self._m_bDirty = False
      self._m_sFilePath = sFilePath
      self._m_log = mk.log
      self._m_dictSignatures = {}
      self._m_dictStoredTargetSnapshots = {}

      log = self._m_log
      if dictYaml:
         log(log.HIGH, 'metadata: loading store: {}', self._m_sFilePath)
         oTargetSnapshots = dictYaml.get('target-snapshots')
         if not isinstance(oTargetSnapshots, list):
            mp.raise_parsing_error('attribute “target-snapshots” must be a sequence')
         for i, o in enumerate(oTargetSnapshots):
            if not isinstance(o, TargetSnapshot):
               mp.raise_parsing_error((
                  'elements of the “target-snapshots” attribute must be of type ' +
                  '!abamake/metadata/target-snapshot, but element [{}] is not'
               ).format(i))
            # If None, this TargetSnapshot should not be used because its target is gone.
            if o._m_tgt:
               self._m_dictStoredTargetSnapshots[o._m_tgt] = o
         log(log.HIGH, 'metadata: store loaded: {}', self._m_sFilePath)
      else:
         log(log.HIGH, 'metadata: empty or missing store: {}', self._m_sFilePath)

   def __yaml__(self, yg):
      """TODO: comment."""

      yg.write_mapping_begin('!abamake/metadata/store')
      yg.produce_from_object('target-snapshots')
      yg.produce_from_object(self._m_dictStoredTargetSnapshots.values())
      yg.write_mapping_end()

   def get_signatures(self, iterFilePaths, dictOut, iMode):
      """Retrieves the signatures for the specified file paths and stores them in the provided
      dictionary.

      If iterFilePaths enumerates output files (which may not exist yet), signatures will be cached
      because we know that the target will call MetadataStore.update_target_snapshot() before its
      dependencies will attempt to generate a snapshot for themselves, so the signatures for this
      target’s outputs (i.e. its dependents’ inputs) will be updated before being used again.

      If iterFilePaths enumerates inputs files (dependencies of a target), signatures will be cached
      because the files must’ve already been built, or we wouldn’t be trying to generate a snapshot
      for a target dependent on them yet. The only case in which files may not exist is if we’re
      running in “dry run” mode, which causes no files to be created or modified.

      iterable(str*) iterFilePaths
         Enumerates file paths.
      dict(str: abamake.metadata.FileSignature) dictOut
         Dictionary in which every signature will be stored, even if None.
      int iMode
         If ASSUME_NEW, the signature will be unconditionally updated to a fictional value that
         cannot be matched by a real file. If UPDATE_CACHE, the signatures cache will not be read,
         but newly-read signatures will be written to it. Otherwise, signatures will first be looked
         up in the cache, and stored in it only if missing.
      """

      for sFilePath in iterFilePaths:
         if iMode == USE_CACHE:
            # See if we already have a signature for this file in the cache.
            fs = self._m_dictSignatures.get(sFilePath)
         else:
            # Don’t use the cache.
            fs = None
         if not fs:
            if iMode == ASSUME_NEW:
               fs = FileSignature.fake_new(sFilePath)
            else:
               # Need to read this file’s signature.
               try:
                  fs = FileSignature.generate(sFilePath)
               except (abamake.FileNotFoundErrorCompat, OSError):
                  fs = None
            # Cache this signature.
            self._m_dictSignatures[sFilePath] = fs
         # Return this signature.
         dictOut[sFilePath] = fs

   def _get_curr_target_snapshot(self, tgt):
      """Returns a current snapshot for the specified target, creating one first it none such
      exists.

      abamake.target.Target tgt
         Target for which to return a current snapshot.
      abamake.metadata.TargetSnapshot return
         Current target snapshot.
      """

      tssCurr = self._m_dictCurrTargetSnapshots.get(tgt)
      if not tssCurr:
         # Instantiate the current snapshot.
         tssCurr = TargetSnapshot(self, tgt)
         self._m_dictCurrTargetSnapshots[tgt] = tssCurr

      return tssCurr

   def has_target_snapshot_changed(self, tgt):
      """Checks if the specified target needs to be rebuilt: compares the current signature of its
      dependencies with the signatures stored in the target’s snapshot, returning True if any
      differences are detected.

      The new signatures are stored internally, and will be used to update the target’s snapshot
      once MetadataStore.update_target_snapshot() is called.

      abamake.target.Target tgt
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

   def update_target_snapshot(self, tgt, bDryRun):
      """Updates the snapshot for the specified target.

      abamake.target.Target tgt
         Target for which to update the snapshot.
      bool bDryRun
         True if “dry run” mode is active, or False otherwise.
      """

      log = self._m_log
      log(log.HIGH, 'metadata: {}: updating target snapshot', tgt)

      tssCurr = self._get_curr_target_snapshot(tgt)
      tssCurr.update(self, bDryRun)
      self._m_dictStoredTargetSnapshots[tgt] = tssCurr
      if not bDryRun:
         self._m_bDirty = True

   def write(self):
      """Stores metadata to the file from which it was loaded."""

      log = self._m_log
      if not self._m_bDirty:
         log(log.HIGH, 'metadata: no changes to write')
         return
      log(log.HIGH, 'metadata: writing changes to store: {}', self._m_sFilePath)

      yaml.generator.generate_file(self._m_sFilePath, self)

      # Now that everything went well, update the internal state to look like we just read the file
      # we just wrote to.
      self._m_dictCurrTargetSnapshots = {}
      self._m_dictSignatures = {}
      self._m_bDirty = False
