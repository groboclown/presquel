# Changelog for presquel

## 0.2.0

**::Overview::**

Includes improvements for upgrade support.  Backwards incompatible changes to
the data model.

**::Details::**

* Constraint types can no longer just be any text.  They must be in the list
  of known constraint types.
* Major overhaul to the version support to better allow for finding and using
  parent versions.
* Incompatible changes to the invocation of `genBaseSql.py`.  It now allows
  for multiple input directories, and specifying the versions to generate.



## 0.1.0

**::Overview::**

Initial branch from the [webriffs](https://github.com/groboclown/webriffs)
project.


**::Details::**

* Imported from webriffs.
* Included support for creating triggers that validate input.
* Support for upgrade added (in progress).
