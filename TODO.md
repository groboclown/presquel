# TODO

This is still an early-development tool.  Here's the current todo list.


## Code generation

Add code generation automatic method creation for any index (table or column).
These exist for the read methods, but should be added for update and delete.

The generation of SQL grammars should be split from the language generators.
It would be better if templates were supported.


## Branch parent support

Currently, the system supports using a single number (v123) directory structure
to implicitly understand the parents between branches.

It would be fairly easy to automatically add parenting support for Dewey Decimal
versioning (v001.12.1333.4).  The default would have each segment be ordered,
and the lowest segment's parent would be the lower number in that segment
(v001.12 would have v001.11 as a parent).  For the next higher segment,
(v001.12 as highest number in the v001. segment, then there's v002), its parent
would be the last segment under the parent branches (v001.12).

In the cases where the numbering is non-standard, or is truly hairy, the
`_manifest.yaml` file can override the default ordering by explicitly declaring
the parent.

A root-level `_manifest.yaml` file could add support for mapping files to their
branch.  For this, the code could supply a regular expression that matches
the ordered parts, like this (the default):

    (?:v|\.)(\d+)

Then the Python code would find all the parts with:

    import re
    parts = re.findall(manifest_pattern, filename)

where `filename` is the name of each file, starting after the base directory.
It should have some smarts to detect if the parts are all numbers (and should
be parsed as numbers, so that '9' is ordered before '12').


## SQL Change

Currently, only the schema definition and language extensions is supported.
The meat of the tool is for supporting "easy" change definition and automatic
sql generation, which has yet to be done.

First, the tool needs the definition and refinement for the syntax that
describes how the schema changed.  Then actual development can follow.

It would be best for the code to support only direct schema definition.
If upgrades need help for non-trivial upgrades, then sections should be
dedicated for declaring a parent version (or versions) and the actions that
need to run.  This definition, though, is very non-trivial, as there's all
kinds of edge cases that can pop up.

(In progress)


## File Format Support

Only yaml is supported right now.  We can add XML and JSon parsers fairly
trivially.


## Documentation

Nearly all the docs are empty.


## Target Platform Support

Need support for other sql platforms than just MySql.
PostGres, Oracle, and Sql Server are all good contenders.

Also, additional languages are in need of generation beyond just PHP.


## Error reporting

The parser, sql generator, and code generators incorrectly throw exceptions,
rather than collecting problems and reporting them in a nice way to the user.
Changing the code around so that error reporting is more user-friendly will
go a long way to making a better tool.
