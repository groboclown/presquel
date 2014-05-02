SQL Migration
=============

This tool allows for automation around version controlled changes to a database
schema.

The tool allows for describing the current state of the database schema, and
inserting into that description the operations necessary to migrate from the
previous version to the current state.

This tool is heavily influenced by [Liquibase](http://www.liquibase.org).


## How It's Different

This tool is designed for generating files that will manage an upgrade, rather
than inspecting the current state of a database to modify it.  This allows for
the generation of files that can be independently reviewed and versioned, as
well as deployment of the files where direct access to the database with the
given tools is not possible.

Some tools describe only the changes performed to the schema, which makes
understanding the current schema from the source files difficult.  This SQL
Migration tool takes the opposite approach, where the files for one revision
all describe the schema as it should be seen, and includes change operations
to migrate old versions to the current.  It makes for a bit of duplication
in the files (it has both the current schema and the changes to get to the
current schema), but tools are provided to make this process easier to manage.

As this is a Python library, you can create new tools based on the API to load
the schema.  This can allow for aiding in the generation of code to interact
with the database objects.


## References

(Wikipedia - Schema migration)[http://en.wikipedia.org/wiki/Schema_migration]
