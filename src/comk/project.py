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

"""Project parser and top-level YAML class mapping."""

import yaml
import yaml.parser


##############################################################################################################

class Error(Exception):
   """Indicates a semantical error in a project."""

   pass

##############################################################################################################

class DependencyCycleError(Error):
   """Raised when a project specifies dependencies among targets in a way that creates circular dependencies,
   an unsolvable situation.
   """

   _targets = None

   def __init__(self, message, targets, *args):
      """See Error.__init__().

      str message
         Exception message.
      iterable(comk.target.Target) targets
         Targets that create a cycle in the dependency graph.
      iterable(object*) args
         Other arguments.
      """

      # Don’t pass targets to the superclass’ constructor, so its __str__() won’t display it.
      Error.__init__(self, message, *args)

      self._targets = targets

   def __str__(self):
      import comk.target

      # Show the regular exception description line followed by the targets in the cycle, one per line.
      s = Error.__str__(self) + '\n' + '\n'.join('  ' + str(target) for target in self._targets)
      return s

##############################################################################################################

class TargetReferenceError(Error):
   """Raised when a reference to a target can’t be resolved."""

   pass

##############################################################################################################

class Parser(yaml.parser.Parser):
   """Parser of Complemake projects."""

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

@Parser.local_tag('complemake/project', yaml.Kind.MAPPING)
class Project(object):
   """Stores the attributes of a YAML complemake/project object."""

   def __init__(self, parser, parsed):
      """Constructor.

      comk.project.Parser parser
         Parser instantiating the object.
      object parsed
         Parsed YAML object to be used to construct the new instance.
      """

      import comk.dependency
      import comk.target

      deps = parsed.get('deps')
      if deps:
         if not isinstance(deps, list):
            parser.raise_parsing_error('attribute “deps” must be a sequence')
         for i, o in enumerate(deps):
            if not isinstance(o, comk.dependency.ExternalProjectDependency):
               parser.raise_parsing_error((
                  'elements of the “deps” attribute must be of type !complemake/dep/*, but element [{}] ' +
                  'is not'
               ).format(i))

      targets = parsed.get('targets')
      if not targets or not isinstance(targets, list):
         parser.raise_parsing_error('attribute “targets” must be a non-empty sequence')
      for i, o in enumerate(targets):
         if not isinstance(o, comk.target.Target):
            parser.raise_parsing_error((
               'elements of the “targets” attribute must be of type !complemake/target/*, but element [{}] ' +
               'is not'
            ).format(i))
