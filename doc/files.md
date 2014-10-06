# Schema Definition File Organization

The schema definition files all live in subdirectories off of a single parent
directory.

Each of the directories under the root represents a *branch* of the schema.


## Reasoning for the copy rather than change storage

This tool stores the branches in their complete form, rather than as a list of
changes.  This complete copy takes up more disk space and creates file clutter
that can grow quite large.  Why did this tool take this approach?

We believe that it's better to see the entire schema as a whole, rather than
split up into incremental changes.  It makes for a better understanding of the
database from the source of the schema, rather than having to look at the
schema at the database to see the whole picture.

The files keep changes from the previous version, which can help with release
preparations.  Assuming the previous release handled the database upgrade
correctly, you don't need to worry about what it did.  You only need to inspect
the changes from the previous branch.  This also allows the tool to help you
with the inspection - it can identify if a part of the schema was changed
without providing how it should change.
