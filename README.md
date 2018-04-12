# presquel

This tool allows for automation around version controlled changes to a database
schema, as well as controlling the software API interaction with the database.

This keeps all the information regarding the database as centralized as
possible, allows for the database architects to have better control over:

* defining the database structure, with database server peculiarities maintained
  in the same file;
* controls how developers can interact with the database through the software;
* migrating the database between versions.


## Who's It For

Presquel is developed for projects that have a database schema as a product,
but can require packaging an upgrade to update the database schema and data.

If the product requires supporting multiple database vendors, then Presquel can
manage the peculiarities of each, and even help provide a single software API
by generating the boilerplate database software interface for each database
type.


## How It Helps

Keeping the state visible at the "head" revision for each version means that
it's easier to deal with messy versioning.  Traditional sql migration tools
assume that the database evolves linearly.  However, from a product perspective,
versions are branches that interleave.  Adding this complex version history
into a single file can make unreadable and unmaintainable code.

Additionally, because the tool constructs an object representation of the
database schema, it can construct low-level database interaction code
automatically, by utilizing the extended meta-data information that's located
with the schema definition.  This allows for keeping all database actions
and usages without needing to search through code.

This tool was heavily influenced by [Liquibase](http://www.liquibase.org).
However, Liquibase solves the problem of incremental updates to a live database,
whereas this tool manages the problem of product versions of databases.



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


## Code Generation

As this is a Python library, you can create new tools based on the API to load
the schema.  This can allow for generating low-level boilerplate code to
interact with the database, allowing you to focus on the more important
business logic code.

This kind of code generation can eliminate the construction of sql within
normal code, allowing the business logic code to have compiler-time safety
in the case of schema changes.  It can also enable the generation of test
mock objects for database interaction, which adds code-level type safety even
in languages that are not type safe (e.g. php).

Some people object to this kind of automated code generation, because it can
easily lead to inefficient queries or overly complicated meta-data.  While I
think that this can be true, it can be mitigated by placing that delicate
query into a view - this allows the DBA to own, in one place, the schema and
the efficient queries for that schema.

## An Example

We'll go through an example application whose features morph over time.  It's
not production grade, by any means, but it's enough to give an idea of how the
tool can help.

_NOTE: this example shows a work flow that includes future functionality.  It
is expected that this example works before v1 is released._


### A Price List Schema


For this exampled we'll be working with a simple price list, where there
will be a product list, and prices for those products.

Let's start with the tables that have no dependencies.  First off, the PRODUCT
table.  This is stored in a file located at `schema/v000/00_product.yaml`.
The "v000" indicates that this is the first revision of the schema, and the
`00_product` means that this should run before other tables that might have
dependencies on it.  The `schema` is just some directory where the schema files
are stored, but the other parts are important - the `v000` is how the tools
discover the version order of the schema, and the `00` allows for sorting the
files by name to order how they are processed.

    table:
        tableName: PRODUCT
        columns:
            - column:
                name: Product_Id
                type: int
                autoIncrement: true
                constraints:
                    - constraint:
                        type: not null
                    - constraint:
                        type: primary key
                        name: Product_Id_Key
            - column:
                name: Category
                type: nvarchar(1000)
                constraints:
                    - constraint:
                        type: not null
            - column:
                name: Manufacturer
                type: nvarchar(1000)
                constraints:
                    - constraint:
                        type: not null
            - column:
                name: Name
                type: nvarchar(1000)
                constraints:
                    - constraint:
                        type: not null
            - column:
                name: Sku
                type: nvarchar(1000)
                constraints:
                    - constraint:
                        type: not null
                    - constraint
                        type: unique index
                        name: Sku_IDX
        constraints:
            - constraint:
                type: unique index
                columns: Manufacturer, Name

This defines a basic product definition table, with an auto-generated
primary key column `Product_Id`.  We also require that the to columns
`Manufacturer` and `Name` must be unique across the table, which implicitly
tells the code generators to create a function that will allow
for querying on these two columns together.

Then we define the `PRICE_LIST` table in the file
`schema/v000/10_price_list.yaml`.

    table:
        tableName: PRICE_LIST
        columns:
            - column:
                name: Price_List_Id
                type: int
                autoIncrement: true
                constraints:
                    - constraint:
                        type: not null
                    - constraint:
                        type: primary key
                        name: Product_Id_Key
            - column:
                name: Product_Id
                type: int
                constraints:
                    - constraint:
                        type: no update
                    - constraint:
                        type: not null
                    - constraint:
                        type: foreign key
                        name: Price_List__Product_Id_FK
                        table: PRODUCT
                        column: Product_Id
                        pull: always
                    - constraint:
                        type: no update
            - column:
                name: Price
                type: float
                constraints:
                    - constraint:
                        type: not null
            - column:
                name: Starts_On
                type: timestamp
                constraints:
                    - constraint:
                        type: not null
            - column:
                name: Ends_On
                type: timestamp
                constraints:
                    - constraint:
                        type: nullable
        - constraints:
            type: restrict value
            syntax: native
            platforms: mysql
            name: Price_List_Unique_Date_Range
            sql: "(SELECT COUNT(*) FROM PRICE_LIST
                WHERE Product_Id = {Product_Id}
                AND (TIMESTAMPDIFF(SECOND, {Starts_On}, Starts_On) >= 0
                  AND TIMESTAMPDIFF(SECOND, {Starts_On}, Ends_On) <= 0))
                OR (TIMESTAMPDIFF(SECOND, {Ends_On}, Starts_On) >= 0
                  AND TIMESTAMPDIFF(SECOND, {Ends_On}, Ends_On) <= 0)
                OR (TIMESTAMPDIFF(SECOND, {Starts_On}, Starts_On) <= 0
                  AND TIMESTAMPDIFF(SECOND, {Ends_On}, Ends_On) >= 0)
                ) <= 0"

This defines the `PRICE_LIST` table, which associates a product (here,
a foreign key into the `PRODUCT` table) with a price.  It can contain multiple
products, but none of those products can have overlapping date ranges.  The
generated sql will create a trigger that prevents the updated or inserted
value from having this condition.

Once the schema has finalized, and the product begins release candidate testing,
the code is branched into a "v1" tree.  Development starts up on the current
master branch for new features, while the "v1" tree is hardened for release.
The development team should then run the `migrateNextVersion.py` utility to
begin the schema updates separate from the release candidate branch.  This
copies the directory `schema/v000` into `schema/v001`.


### Adding Purchase Orders



### Release Candidate Bug Fix

During the development of the purchase orders, someone realizes that storing
prices as "float" causes rounding issues when analysis is run on large sets
of data.  Before the "v1" can be released, the `PRICE_LIST` table must have its
`Price` data type changed from `float` to `currency`.

However, work has already started on the next version.  So, some work needs to
be done to allow for this change to happen.  The upgrade will now need to
introduce a Dewey Decimal numbering system for a minor patch by running the
`migrateNextVersion.py` on `schema/v000` into `schema/v000.001`, and change
the file `schema/v000.001/10_price_list.yaml` to have this column definition:

    - column:
        name: Price
        type: currency
        constraints:
            - constraint:
                type: not null
            - change:
                type: value type

By adding a Dewey Decimal numbering, the tools no longer have a reference
of what to use for the parent version of `v001`.  A manifest file needs to be
introduced to tell the tool more information.  The developers add the file
`schema/v001/_manifest.yaml`:

    manifest:
        parent: v000.001

Then update the file `schema/v001/10_price_list.yaml` to have the column as:

    - column:
        name: Price
        type: currency
        constraints:
            - constraint:
                type: not null

No change section is necessary, because the parent version includes the change.

Now, this approach has its downsides.  It means that even these micro versions
have a complete copy of the schema.  This means it's more difficult to add
minor changes to a schema an incrementally update a database.  However, this
tool is designed for programs which deploy the same upgrade code to different
sites; in this model, the incremental approach is only done during development,
and shouldn't be recorded in the schema definition.  _TODO this aside
belongs in another section._



### Making the Price List Multi-Currency

At this point in the development cycle, someone discovers that a user just might
want to sell things in different countries, and the product needs to support
that.


## Best Practices

### Versioning





## TODO

This is still an early-development tool.  There's stil lots of work to be
done.  See the [TODO list](TODO.md) for details.


## Syntax

The tool can process XML, JSon, and YAML file formats.  For the examples here,
I'll use YAML.

_FIXME add definite syntax declaration._


## License

![CC-0 License](http://i.creativecommons.org/p/zero/1.0/88x31.png "CC-0 License")

Released under the [CC-0 License](http://creativecommons.org/about/cc0).


## References

* [Wikipedia - Schema migration](http://en.wikipedia.org/wiki/Schema_migration)
* [Liquibase](http://www.liquibase.org)
