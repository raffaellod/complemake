**Complemake** – the build tool your project was missing.

## 1. Introduction

Complemake is a build utility for software (currently C++-only) projects, featuring:

*  Built-in dependency resolution and building;
*  Parallel execution of all build tasks;
*  Multiple platform compatibility: currently Linux, Windows, OS X and FreeBSD;
*  Easy sub-command-style invocation, like Git and Mercurial;
*  Simple and concise YAML-based project syntax: minimal instructions required in each project, and no
   toolchain-specific commands/flags;
*  Integration with [Lofty](https://github.com/raffaellod/lofty)’s Testing framework, providing a smooth
   automated testing experience;
*  No GNU Autotools.


## 2. Getting Complemake

Complemake is [available on GitHub](https://github.com/raffaellod/complemake); to download it, just clone the
repository:

```
git clone https://github.com/raffaellod/complemake.git
cd complemake
```

The default branch, `master`, is where all development occurs. See § _4. Versioning and branching_ for more
information on available branches.

### 2.1. Building

Since Complemake is entirely written in Python, it doesn’t need to be built.

### 2.2. Installing

This will install a symlink (POSIX) or a cmd script (Windows) to run `complemake.py` as just `complemake`:

```
install.py --dev
```

## 3. Using Complemake

In order to use Complemake, create a `.comk` project (a fairly simple YAML 1.2 file) defining a list of
targets. Here’s a minimal example:

```
%YAML 1.2
--- !complemake/project
brief: Just a Complemake project.
targets:
   - !complemake/target/exe
      name: myexe
      brief: My Executable
      sources:
      -  src/main.cxx
```

**TODO**: document file format completely! More examples available as tests (`/test`).

Complemake should be run from the directory containing the project file. You don’t need to specifiy which
project file to use if the directory only contains one (otherwise you can use `--project`):

```
complemake build
```

When running, Complemake will build the targets in the project and create outputs in the `bin` and `lib`
folders (this is configurable via flags). For the example above, the `build` command will generate `bin/myexe`
(or `bin\myexe.exe` under Windows).

To clean up the output files, run:

```
complemake clean
```

Run `complemake --help` to see a guide to all command-line arguments.


## 4. Versioning and branching

Complemake uses semantical versioning, with releases named `vX.Y.Z` where _X_ is the major version, _Y_ is the
minor version, and _Z_ is the revision.

While the major number is 0, changes to the minor indicate breaking changes, while the revision is incremented
for non-breaking changes such as bug fixes and minor improvements.
The only git branch is `master`, and each release is a tag along `master`’s history.
There are no maintenance releases.

Version 1.0.0 will indicate the first production-grade release, and the meaning of the versioning schema will
shift accordingly: the major number will indicate breaking changes, the minor non-breaking changes (e.g. for
maintenance releases), and the revision will be incremented for bug fixes and other minor improvements.
The main git branch will remanin `master`, but each major release will get its own branch, to support
maintenance releases independent of the `master` branch.


## 5. Compatibility

Complemake is in full development, so the compatibility can and will change over time (hopefully expanding).

Supported build systems:

*  GNU toolchain
   *  GCC 4.7 to 5.2
   *  binutils 2.20 or later

*  Microsoft Visual Studio 2010-2013 (Visual C++ 10-12 / MSC 16-18)

*  Clang + GNU LD
   *  Clang 3.5
   *  binutils 2.20 or later

*  Apple SDK for OS X 10.10 Yosemite and 10.9 Mavericks (included in Xcode 6)

Supported operating systems:

*  GNU/Linux 2.6 or later
*  Microsoft Windows XP (5.1) or later
*  FreeBSD 10 or later
*  OS X 10.9 Mavericks or later

Complemake requires Python 2.7 or 3.2 or later to be installed on the build host system.

Future plans include removal of the dependency on Python.


## 6. Past, present and future

### 6.1. Some history

Complemake is a spin-off of [Lofty](https://github.com/raffaellod/lofty); its creation became a necessity as
the number of fixes to the different build systems in use (the traditional make utility and MSBuild) started
becoming excessive:

*  The syntax of traditional makefiles is one of a kind, and often that’s the case for its replacements as
   well; while this is also true for Complemake, the syntax for the latter is rather simplified and often only
   offers one easy way to reach the desired result;

*  Traditional makefiles require toolchain-specific commands/flags to be hard-coded in the target build rules;

*  MSBuild requires and produces too many files, creating confusion;

*  Traditional makefiles require quite some tooling to generate build rules for intermediate targets;

*  No way of parallelizing the build by default, and many steps had to be sequential anyway.


### 6.2. Current status of Complemake

Though not yet as complete as it should be, Complemake is the recommended utility to build projects using
Lofty.

Requirements currently satisfied by Complemake:

*  Cross-platform enough to no longer need to separately maintain a GNU makefile and a Visual Studio solution
   and projects to build Lofty;

*  Implicit definition of intermediate targets, so that each project only needs to state explicitly sources
   and outputs (this had already been achieved via a Makefile “include” for GNU make, and was not required for
   MSBuild);

*  Trivial test declaration and execution (this had been implemented in both GNU make and MSBuild, but at the
   cost of a lot of delicate tooling);

*  Integration with `lofty::testing` framework (this had already been accomplished for GNU make);

*  Default parallel building of independent targets.


### 6.3. Project goals

Complemake has met or is targeting these goals:

1. Offer a fast way of setting up C++ projects using Lofty;

2. Use all available resources for builds;

3. Fully automate the testing of all targets built;

4. Provide dependency resolution and building;

5. Allow export Complemake projects to simple shell scripts, to enable quick building of projects by
   non-developers as a one-time operation.

All future development will be geared towards getting closer to accomplishing these objectives.




--------------------------------------------------------------------------------------------------------------
Copyright 2010-2017 Raffaello D. Di Napoli

This file is part of Complemake.

Complemake is free software: you can redistribute it and/or modify it under the terms of the GNU General
Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Complemake is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License along with Complemake. If not, see
http://www.gnu.org/licenses/ .
