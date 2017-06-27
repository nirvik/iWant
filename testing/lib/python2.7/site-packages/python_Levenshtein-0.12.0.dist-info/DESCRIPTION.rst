.. contents ::

Introduction
------------

The Levenshtein Python C extension module contains functions for fast
computation of

* Levenshtein (edit) distance, and edit operations

* string similarity

* approximate median strings, and generally string averaging

* string sequence and set similarity

It supports both normal and Unicode strings.

Python 2.2 or newer is required; Python 3 is supported.

StringMatcher.py is an example SequenceMatcher-like class built on the top of
Levenshtein.  It misses some SequenceMatcher's functionality, and has some
extra OTOH.

Levenshtein.c can be used as a pure C library, too.  You only have to define
NO_PYTHON preprocessor symbol (-DNO_PYTHON) when compiling it.  The
functionality is similar to that of the Python extension.  No separate docs
are provided yet, RTFS.  But they are not interchangeable:

* C functions exported when compiling with -DNO_PYTHON (see Levenshtein.h)
  are not exported when compiling as a Python extension (and vice versa)

* Unicode character type used with -DNO_PYTHON is wchar_t, Python extension
  uses Py_UNICODE, they may be the same but don't count on it

Documentation
--------------

gendoc.sh generates HTML API documentation,
you probably want a selfcontained instead of includable version, so run
in ``./gendoc.sh --selfcontained``.  It needs Levenshtein already installed
and genextdoc.py.

License
-----------

Levenshtein can be copied and/or modified under the terms of GNU General
Public License, see the file COPYING for full license text.

History
-------

This package was long missing from PyPi and available as source checkout only.
We needed to restore this package for `Go Mobile for Plone <http://webandmobile.mfabrik.com>`_
and `Pywurfl <http://celljam.net/>`_ projects which depend on this.

Source code
-----------

* http://github.com/ztane/python-Levenshtein/

Documentation
-------------

* `Documentation for the current version <https://rawgit.com/ztane/python-Levenshtein/master/docs/Levenshtein.html>`_

Authors
-------

* Maintainer: `Antti Haapala <antti@haapala.name>`

* Python 3 compatibility: Esa Määttä

* Jonatas CD: Fixed documentation generation

* Previous maintainer: `Mikko Ohtamaa <http://opensourcehacker.com>`_

* Original code: David Necas (Yeti) <yeti at physics.muni.cz>

============
 Changelog
============

0.12.0
------

* Fixed a bug in StringMatcher.StringMatcher.get_matching_blocks /
  extract_editops for Python 3; now allow only `str` editops on
  both Python 2 and Python 3, for simpler and working code.

* Added documentation in the source distribution and in GIT

* Fixed the package layout: renamed the .so/.dll to _levenshtein,
  and made it reside inside a package, along with the StringMatcher
  class.

* Fixed spelling errors.

0.11.2
------

* Fixed a bug in setup.py: installation would fail on Python 3 if the locale
  did not specify UTF-8 charset (Felix Yan).

* Added COPYING, StringMatcher.py, gendoc.sh and NEWS in MANIFEST.in, as they
  were missing from source distributions.

0.11.1
------

* Added Levenshtein.h to MANIFEST.in

0.11.0
------

* Python 3 support, maintainership passed to Antti Haapala

0.10.1 - 0.10.2
---------------

* Made python-Lehvenstein Git compatible and use setuptools for PyPi upload

* Created HISTORY.txt and made README reST compatible


