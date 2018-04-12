# How to Extend the Code Generator

TODO this needs to be written out, once the code gen section is
rewritten.

## What it Should Be

There should be 2 sections for the code generator: sql grammar variant,
and source code generator.  The two should be independent, so that writing
one sql grammar can be used everywhere.

It would be even better if these can use template files, to eliminate as
much coding as possible.
