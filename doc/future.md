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

