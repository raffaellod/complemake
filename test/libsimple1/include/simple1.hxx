/* -*- coding: utf-8; mode: c++; tab-width: 3; indent-tabs-mode: nil -*-

Copyright 2017 Raffaello D. Di Napoli

This file is part of Complemake.

Complemake is free software: you can redistribute it and/or modify it under the terms of the GNU General
Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Complemake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License along with Complemake. If not, see
<http://www.gnu.org/licenses/>.
------------------------------------------------------------------------------------------------------------*/

#ifdef COMPLEMAKE_BUILD_SIMPLE1
   #ifdef _WIN32
      #if defined(_MSC_VER) || defined(__clang__)
         #define SIMPLE1_SYM __declspec(dllimport)
      #elif defined(__GNUC__)
         #define SIMPLE1_SYM __attribute__((dllimport))
      #endif
   #else
      #if defined(__clang__) || defined(__GNUC__)
         #define SIMPLE1_SYM __attribute__((visibility("default")))
      #endif
   #endif
#else
   #ifdef _WIN32
      #if defined(_MSC_VER) || defined(__clang__)
         #define SIMPLE1_SYM __declspec(dllexport)
      #elif defined(__GNUC__)
         #define SIMPLE1_SYM __attribute__((dllexport))
      #endif
   #else
      #if defined(__clang__) || defined(__GNUC__)
         #define SIMPLE1_SYM __attribute__((visibility("default")))
      #endif
   #endif
#endif

int SIMPLE1_SYM simple1_function(int arg);
