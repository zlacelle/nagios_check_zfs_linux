# Changelog

Documenting major changes for nagios_check_zfs_linux. For detailed information, see commits.

## [2.0] - 2020-12-12

### Features

* Switching to Python3 support only.
* Adding CodeQL security analysis to project
* Adding explicit CHANGELOG and SECURITY
* Adding more to README concerning sudo command
* Adding Python3 version checking to ensure relatively new Python3 version. Currently 3.5 is required (used by Ubuntu 16.04 LTS)
* Checking for existence of files before running
* Better handling of printouts and exceptions

### Bug Fixes

* Fixed deprecation warning on warn vs warning (deprecated since Python 3.3+)
* Fixed bug with "is" vs "==" checks

## [1.4] - 2020-05-11

### Features

* Adding support for deduplication and compression ratios

### Bug Fixes

* Fixing Python variable scoping issue

## [1.3] - 2020-04-08

### Features

* Adding an selinux enforcement file example
* Informing users how to add "just enough permissions" to visudo instead of giving the full root permissions
* Switching from print statements to using the Python logging library

### Bug Fixes

* Fixed bug with fragmentation output

## [1.2] - 2018-09-08

### Features
* Testing on CentOS 7
* Better error handling with exceptions

### Bug Fixes

* Fixing float converted from other locales
* Always check to make sure we're running as root
* Fixing bug where zpool can't run when result is higher criticality than capacity/fragmentation
