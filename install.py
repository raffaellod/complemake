#!/usr/bin/env python
# -*- coding: utf-8; mode: python; tab-width: 3; indent-tabs-mode: nil -*-
#
# Copyright 2017 Raffaello D. Di Napoli
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

"""Installs Complemake."""

from __future__ import print_function

import argparse
import io
import os
import platform
import sys

##############################################################################################################

def main(args):
   """Implementation of __main__.

   iterable(str*) args
      Command-line arguments.
   int return
      Command return status.
   """

   argparser = argparse.ArgumentParser(add_help=False)
   if platform.system() == 'Windows':
      # TODO: pick a different directory; putting things in C:\Windows is very sloppy!
      default_dst = os.environ['WINDIR']
   else:
      default_dst = '/usr/local/bin'
   argparser.add_argument(
      '--dest', metavar='DESTINATION', default=default_dst,
      help='Installation destination folder.'
   )
   argparser.add_argument(
      '--dev', action='store_true',
      help='Developer mode: install symlinks to files in the repo, rather than copying files to the ' +
           'installation destination.'
   )
   argparser.add_argument(
      '--help', action='help',
      help='Show this informative message and exit.'
   )
   args = argparser.parse_args()

   if args.dev:
      complemake_src_dir = os.getcwd()
      print('Installing to: {}'.format(args.dest))
      if platform.system() == 'Windows':
         complemake_dst_script = os.path.join(args.dest, 'complemake.cmd')
         with io.open(complemake_dst_script, 'w', encoding='utf-8') as cmd_script:
            # Replacements in these lines could use some escaping, but for now they’re okay.
            for line in \
               '@echo off && setlocal', \
               'set COMPLEMAKE_DIR="{}"'.format(complemake_src_dir), \
               '"%COMPLEMAKE_DIR%\src\complemake.py" %*' \
            :
               print(line, file=cmd_script)
      else:
         complemake_dst_link = os.path.join(args.dest, 'complemake')
         try:
            os.unlink(complemake_dst_link)
         except OSError:
            pass
         os.symlink(os.path.join(complemake_src_dir, 'src', 'complemake.py'), complemake_dst_link)
   else:
      # TODO: install by copying elsewhere.
      print('Non-dev installing not yet implemented, sorry! Please use --dev for now.')
      return 1
   return 0

if __name__ == '__main__':
   sys.exit(main(sys.argv))
