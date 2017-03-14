# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013-2017 Raffaello D. Di Napoli
#
# This file is part of Complemake.
#
# Complemake is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# Complemake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along with Complemake. If not, see
# <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------------------------------------

"""Metadata management classes."""

import datetime
import os
import sys
import yaml
import yaml.generator
import yaml.parser

import comk.dependency
import comk.target

if sys.hexversion >= 0x03000000:
   basestring = str


##############################################################################################################

class MetadataParser(yaml.parser.Parser):
   """Parser of Complemake’s metadata YAML files."""

   def __init__(self, core):
      """Constructor.

      comk.core.Core core
         Core instance to make accessible via self.core .
      """

      yaml.parser.Parser.__init__(self)

      self._core = core

   def _get_core(self):
      return self._core

   core = property(_get_core, doc="""Returns the Core instance that’s running the parser.""")

##############################################################################################################

# MetadataStore.get_signatures() modes.
ASSUME_NEW   = 1
UPDATE_CACHE = 2
USE_CACHE    = 3

@MetadataParser.local_tag('complemake/metadata/file-signature', yaml.Kind.MAPPING)
class FileSignature(object):
   """Signature metadata for a single file."""

   __slots__ = (
      # Path to the file this signature is about.
      '_file_path',
      # Date/time of the file’s last modification.
      '_mtime',
   )

   def __init__(self, *args):
      """Constructor.

      comk.metadata.MetadataParser parser
         Parser instantiating the object.
      dict(object: object) parsed
         Parsed YAML object to be used to construct the new instance.

      - OR -

      str file_path
         Path to the file this signature is about.
      """

      if isinstance(args[0], MetadataParser):
         parser, parsed = args
      else:
         parsed = None
         file_path, = args

      if parsed:
         path = parsed.get('path')
         if not isinstance(path, basestring):
            parser.raise_parsing_error('missing or invalid “path” attribute')
         self._file_path = path

         mtime = parsed.get('mtime')
         if not isinstance(mtime, datetime.datetime):
            parser.raise_parsing_error('missing or invalid “mtime” attribute')
         self._mtime = mtime
      else:
         self._file_path = file_path
         self._mtime = None

   def __yaml__(self, yg):
      """TODO: comment."""

      yg.write_mapping_begin('!complemake/metadata/file-signature')
      yg.produce_from_object('path')
      yg.produce_from_object(self._file_path)
      yg.produce_from_object('mtime')
      yg.produce_from_object(self._mtime)
      yg.write_mapping_end()

   @classmethod
   def fake_new(cls, file_path):
      """Generates a fake signature that no real file can ever match.

      str file_path
         Path to the file associated to the signature.
      comk.metadata.FileSignature return
         Generated signature.
      """

      self = cls(file_path)
      self._mtime = 0xffffffff
      return self

   @classmethod
   def generate(cls, file_path, inproject_file_path):
      """Generates a signature for the specified file.

      str file_path
         Path to the file for which a signature should be generated.
      str inproject_file_path
         Path to the file from the project path.
      comk.metadata.FileSignature return
         Generated signature.
      """

      self = cls(file_path)
      self._mtime = datetime.datetime.fromtimestamp(int(os.path.getmtime(inproject_file_path)))
      return self

##############################################################################################################

@MetadataParser.local_tag('complemake/metadata/target-snapshot', yaml.Kind.MAPPING)
class TargetSnapshot(object):
   """Captures information about a target at a specific time. Used to detect changes that should trigger a
   rebuild.
   """

   __slots__ = (
      # Signature of each input (dependency) of this target.
      '_input_signatures',
      # Signature of each output (generated file) of this target.
      '_output_signatures',
      # Target.
      '_target',
   )

   def __init__(self, *args):
      """Constructor.

      comk.metadata.MetadataParser parser
         Parser instantiating the object.
      dict(object: object) parsed
         Parsed YAML object to be used to construct the new instance.

      - OR -

      comk.metadata.MetadataStore mds
         MetadataStore instance.
      comk.target.Target target
         Target to collect signatures for from the file system.
      """

      if isinstance(args[0], MetadataParser):
         parser, parsed = args
      else:
         parsed = None
         mds, target = args

      self._input_signatures = {}
      self._output_signatures = {}

      if parsed:
         core = parser.core

         # Allow for None to be returned by core.get_*_target() because it’s possible that no such target
         # exists – maybe it used to, but not anymore.
         name = parsed.get('name')
         path = parsed.get('path')
         if name:
            self._target = core.get_named_target(name, None)
         elif path:
            self._target = core.get_file_target(path, None)
         else:
            parser.raise_parsing_error('expected one attribute of “name” or “path”')
         if not self._target:
            # The condition above will make the MetadataStore ignore this signature.
            return

         inputs = parsed.get('inputs')
         if inputs:
            if not isinstance(inputs, list):
               parser.raise_parsing_error('attribute “inputs” must be a sequence')
            for i, o in enumerate(inputs):
               if not isinstance(o, FileSignature):
                  parser.raise_parsing_error((
                     'elements of the “inputs” attribute must be of type !complemake/metadata/file-' +
                     'signature, but element [{}] is not'
                  ).format(i))
               self._input_signatures[o._file_path] = o

         outputs = parsed.get('outputs')
         if outputs:
            if not isinstance(outputs, list):
               parser.raise_parsing_error('attribute “outputs” must be a sequence')
            for i, o in enumerate(outputs):
               if not isinstance(o, FileSignature):
                  parser.raise_parsing_error((
                     'elements of the “outputs” attribute must be of type !complemake/metadata/file-' +
                     'signature, but element [{}] is not'
                  ).format(i))
               self._output_signatures[o._file_path] = o
      else:
         self._target = target
         # TODO: improve this hacky way of getting a Core instance.
         core = target._core()
         # Collect signatures for all the target’s dependencies’ generated files (inputs).
         for dep in target.get_dependencies():
            if isinstance(dep, comk.dependency.FileDependencyMixIn):
               mds.get_signatures(dep.get_generated_files(), self._input_signatures, USE_CACHE, core)
         # Collect signatures for all the target’s generated files (outputs).
         if isinstance(target, comk.target.FileTarget):
            mds.get_signatures(target.get_generated_files(), self._output_signatures, USE_CACHE, core)

   def __yaml__(self, yg):
      """TODO: comment."""

      target = self._target
      yg.write_mapping_begin('!complemake/metadata/target-snapshot')

      # Store the name of the target if named, or its file path otherwise.
      if isinstance(target, comk.target.NamedTargetMixIn):
         yg.produce_from_object('name')
         yg.produce_from_object(target.name)
      else:
         yg.produce_from_object('path')
         yg.produce_from_object(target.file_path)

      # Serialize the signature of each input.
      yg.produce_from_object('inputs')
      yg.produce_from_object(self._input_signatures.values())

      # Serialize the signature of each output.
      yg.produce_from_object('outputs')
      yg.produce_from_object(self._output_signatures.values())

      yg.write_mapping_end()

   def equals_stored(self, stored_target_snapshots, log):
      """Compares self (current snapshot) with the stored snapshot for the same target, logging any detected
      differences.

      comk.metadata.TargetSnapshot stored_target_snapshots
         Stored snapshot.
      comk.Logger log
         Log instance.
      bool return
         True if the two snapshots are equal, of False in case of any differences.
      """

      target = self._target
      assert target == stored_target_snapshots._target, 'comparing snapshots of different targets'

      for is_inputs, stored_signatures, curr_signatures in \
         (True,  stored_target_snapshots._input_signatures,  self._input_signatures ), \
         (False, stored_target_snapshots._output_signatures, self._output_signatures) \
      :
         # Check that all signatures in the current snapshot (self) match those in the stored snapshot.
         for file_path, curr_signature in curr_signatures.items():
            if not curr_signature:
               if is_inputs:
                  log(log.HIGH, 'metadata: {}: missing input {}, build will fail', target, file_path)
               else:
                  log(log.HIGH, 'metadata: {}: missing output {}, rebuild needed', target, file_path)
               return False
            stored_signature = stored_signatures.get(file_path)
            if not stored_signature:
               log(
                  log.HIGH,
                  'metadata: {}: file {} not part of stored snapshot, rebuild needed',
                  target, file_path
               )
               return False
            if curr_signature._mtime != stored_signature._mtime:
               log(
                  log.HIGH,
                  'metadata: {}: changes detected in file {} (mtime was: {}, now: {}), rebuild needed',
                  target, file_path, stored_signature._mtime, curr_signature._mtime
               )
               return False

         # A change in the number of signatures should cause a rebuild because it’s a change in inputs
         # (dependencies) or outputs, so verify that all signatures in the stored snapshot are also in the
         # current one (self).
         for file_path in stored_signatures.keys():
            if file_path not in curr_signatures:
               log(
                  log.HIGH,
                  'metadata: {}: file {} not part of current snapshot, rebuild needed',
                  target, file_path
               )
               return False

      # No changes detected.
      log(log.HIGH, 'metadata: {}: up-to-date', target)
      return True

   def update(self, mds, dry_run):
      """Updates the snapshot.

      comk.metadata.MetadataStore mds
         MetadataStore instance.
      bool dry_run
         True if “dry run” mode is active, or False otherwise.
      """

      if isinstance(self._target, comk.target.FileTarget):
         # TODO: improve this hacky way of getting a Core instance.
         core = self._target._core()
         # Recreate signatures for all the target’s generated files (outputs).
         mds.get_signatures(
            self._target.get_generated_files(), self._output_signatures,
            ASSUME_NEW if dry_run else UPDATE_CACHE, core
         )

##############################################################################################################

@MetadataParser.local_tag('complemake/metadata/store', yaml.Kind.MAPPING)
class MetadataStore(object):
   """Handles storage and retrieval of file metadata."""

   # Freshly-read target snapshots (comk.target.Target -> TargetSnapshot).
   _curr_target_snapshots = None
   # True if any changes occurred, which means that the metadata file should be updated.
   _dirty = None
   # Persistent storage file path.
   _file_path = None
   # Output log.
   _log = None
   # Signature for each file (str -> FileSignature).
   _signatures = None
   # Target snapshots as stored in the metadata file (comk.target.Target -> TargetSnapshot).
   _stored_target_snapshots = None

   def __init__(self, *args):
      """Constructor. Reads metadata from the specified file.

      comk.metadata.MetadataParser parser
         Parser instantiating the object.
      dict(object: object) parsed
         Parsed YAML object to be used to construct the new instance.

      - OR -

      comk.Core core
         Core instance.
      str file_path
         Metadata storage file.
      """

      if isinstance(args[0], MetadataParser):
         parser, parsed = args
         core = parser.core
         file_path = parser.source_name
      else:
         parsed = None
         core, file_path = args

      self._curr_target_snapshots = {}
      self._dirty = False
      self._file_path = file_path
      self._log = core.log
      self._signatures = {}
      self._stored_target_snapshots = {}

      log = self._log
      if parsed:
         log(log.HIGH, 'metadata: loading store: {}', self._file_path)
         target_snapshots = parsed.get('target-snapshots')
         if not isinstance(target_snapshots, list):
            parser.raise_parsing_error('attribute “target-snapshots” must be a sequence')
         for i, o in enumerate(target_snapshots):
            if not isinstance(o, TargetSnapshot):
               parser.raise_parsing_error((
                  'elements of the “target-snapshots” attribute must be of type ' +
                  '!complemake/metadata/target-snapshot, but element [{}] is not'
               ).format(i))
            # If None, this TargetSnapshot should not be used because its target is gone.
            if o._target:
               self._stored_target_snapshots[o._target] = o
         log(log.HIGH, 'metadata: store loaded: {}', self._file_path)
      else:
         log(log.HIGH, 'metadata: empty or missing store: {}', self._file_path)

   def __yaml__(self, yg):
      """TODO: comment."""

      yg.write_mapping_begin('!complemake/metadata/store')
      yg.produce_from_object('target-snapshots')
      yg.produce_from_object(self._stored_target_snapshots.values())
      yg.write_mapping_end()

   def get_signatures(self, file_paths, out, mode, core):
      """Retrieves the signatures for the specified file paths and stores them in the provided dictionary.

      If file_paths enumerates output files (which may not exist yet), signatures will be cached because we
      know that the target will call MetadataStore.update_target_snapshot() before its dependencies will
      attempt to generate a snapshot for themselves, so the signatures for this target’s outputs (i.e. its
      dependents’ inputs) will be updated before being used again.

      If file_paths enumerates inputs files (dependencies of a target), signatures will be cached because the
      files must’ve already been built, or we wouldn’t be trying to generate a snapshot for a target dependent
      on them yet. The only case in which files may not exist is if we’re running in “dry run” mode, which
      causes no files to be created or modified.

      iterable(str*) file_paths
         Enumerates file paths.
      dict(str: comk.metadata.FileSignature) out
         Dictionary in which every signature will be stored, even if None.
      int mode
         If ASSUME_NEW, the signature will be unconditionally updated to a fictional value that cannot be
         matched by a real file. If UPDATE_CACHE, the signatures cache will not be read, but newly-read
         signatures will be written to it. Otherwise, signatures will first be looked up in the cache, and
         stored in it only if missing.
      comk.core.Core core
         Core instance.
      """

      for file_path in file_paths:
         if mode == USE_CACHE:
            # See if we already have a signature for this file in the cache.
            fs = self._signatures.get(file_path)
         else:
            # Don’t use the cache.
            fs = None
         if not fs:
            if mode == ASSUME_NEW:
               fs = FileSignature.fake_new(file_path)
            else:
               # Need to read this file’s signature.
               try:
                  fs = FileSignature.generate(file_path, core.inproject_path(file_path))
               except (comk.FileNotFoundErrorCompat, OSError):
                  fs = None
            # Cache this signature.
            self._signatures[file_path] = fs
         # Return this signature.
         out[file_path] = fs

   def _get_curr_target_snapshot(self, target):
      """Returns a current snapshot for the specified target, creating one first it none such exists.

      comk.target.Target target
         Target for which to return a current snapshot.
      comk.metadata.TargetSnapshot return
         Current target snapshot.
      """

      curr_target_snapshots = self._curr_target_snapshots.get(target)
      if not curr_target_snapshots:
         # Instantiate the current snapshot.
         curr_target_snapshots = TargetSnapshot(self, target)
         self._curr_target_snapshots[target] = curr_target_snapshots

      return curr_target_snapshots

   def has_target_snapshot_changed(self, target):
      """Checks if the specified target needs to be rebuilt: compares the current signature of its
      dependencies with the signatures stored in the target’s snapshot, returning True if any differences are
      detected.

      The new signatures are stored internally, and will be used to update the target’s snapshot once
      MetadataStore.update_target_snapshot() is called.

      comk.target.Target target
         Target for which to get a new snapshot to compare with the stored one.
      bool return
         True if any files have changed since the last build, or False otherwise.
      """

      log = self._log

      stored_target_snapshots = self._stored_target_snapshots.get(target)
      curr_target_snapshots = self._get_curr_target_snapshot(target)

      # If we have no stored snapshot to compare to, report the build as necessary.
      if not stored_target_snapshots:
         log(log.HIGH, 'metadata: {}: no stored snapshot, build needed', target)
         return True

      # Compare current and stored snapshots.
      return not curr_target_snapshots.equals_stored(stored_target_snapshots, log)

   def update_target_snapshot(self, target, dry_run):
      """Updates the snapshot for the specified target.

      comk.target.Target target
         Target for which to update the snapshot.
      bool dry_run
         True if “dry run” mode is active, or False otherwise.
      """

      log = self._log
      log(log.HIGH, 'metadata: {}: updating target snapshot', target)

      curr_target_snapshots = self._get_curr_target_snapshot(target)
      curr_target_snapshots.update(self, dry_run)
      self._stored_target_snapshots[target] = curr_target_snapshots
      if not dry_run:
         self._dirty = True

   def write(self):
      """Stores metadata to the file from which it was loaded."""

      log = self._log
      if not self._dirty:
         log(log.HIGH, 'metadata: no changes to write')
         return
      log(log.HIGH, 'metadata: writing changes to store: {}', self._file_path)

      yaml.generator.generate_file(self._file_path, self)

      # Now that everything went well, update the internal state to look like we just read the file
      # we just wrote to.
      self._curr_target_snapshots = {}
      self._signatures = {}
      self._dirty = False
