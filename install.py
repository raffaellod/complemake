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
   argparser.add_argument(
      '--dest', metavar='DESTINATION', default='/usr/local/bin',
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
      complemake_dst_file = os.path.join(args.dest, 'complemake')
      print('Installing to: {}'.format(args.dest))
      try:
         os.unlink(complemake_dst_file)
      except OSError:
         pass
      if platform.system() == 'Windows':
         with io.open(complemake_dst_file, 'w', encoding='utf-16le', universal_newlines=True) as cmd_script:
            cmd_script.write_line('@echo off && setlocal')
            # This could use some escaping, but for now it’s okay.
            cmd_script.write_line('set COMPLEMAKE_DIR="{}"'.format(complemake_src_dir))
            cmd_script.write_line('"%COMPLEMAKE_DIR%\src\complemake.py" %*')
      else:
         os.symlink(os.path.join(complemake_src_dir, 'src', 'complemake.py'), complemake_dst_file)
   else:
      # TODO: install by copying elsewhere.
      print('Non-dev installing not yet implemented, sorry!')
      return 1
   return 0

if __name__ == '__main__':
   sys.exit(main(sys.argv))
