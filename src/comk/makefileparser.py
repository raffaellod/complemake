#!/usr/bin/python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2013-2016 Raffaello D. Di Napoli
#
# This file is part of Complemake.
#
# Complemake is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Complemake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Complemake. If not,
# see <http://www.gnu.org/licenses/>.
#---------------------------------------------------------------------------------------------------

"""Makefile parser and top-level YAML class mapping."""

import yaml.parser


####################################################################################################

class MakefileParser(yaml.parser.Parser):
   """Parser of YAML Complemake files."""

   def __init__(self, mk):
      """Constructor.

      comk.make.Make mk
         Make instance to make accessible via self.mk .
      """

      yaml.parser.Parser.__init__(self)

      self._m_mk = mk

   def _get_mk(self):
      return self._m_mk

   mk = property(_get_mk, doc = """Returns the Make instance that’s running the parser.""")
