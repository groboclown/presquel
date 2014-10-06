# Future Features

With the centralized schema definition and code extensions, there are many
possibilities for features this tool can provide:


## Schema Import

Take an existing schema in a database, and import it into these files.

First steps will probably take the approach of using another existing tool's
output (such as SchemaCrawler) and convert its output into the Presquel
format.

This can be taken a step further by extending the `migrateNextVersion` tool
to automatically generate an initial set of files which includes the
basic upgrade information.


## New Input Validation Targets

Beyond the SQL and DBO input validations, additional code generators can be
written for JavaScript and other client-side applications that need to check
the validity of the data before sending it to the server.  This usually means
code replication between the different layers of code, and having this be
generated from a single source can help.


## Support for Version Tables

Eventually, it would be nice to have tools that can run the schema upgrade
as necessary, rather than requiring the end-user to supply that code.  To
support this, the tool should have a way to query and store the schema version.

To keep this system flexible, it should probably be put into the
`_manifest.yaml` file, like this:

    manifest:
    - version table:
        query: SELECT Version FROM VERSION
        insert: "INSERT INTO VERSION (Product, Version, When) VALUES (
            'Presquel`, {version}, NOW())" 
