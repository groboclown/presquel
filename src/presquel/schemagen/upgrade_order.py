"""
Looks at the upgrade operations for an entire set of upgrades, and decides on
the correct ordering for the operations.

This creates a dependency tree that then has a topo sort run on it.

Use the "affects" and "depends" to help construct the proper ordering.

This requires correct construction of operations along with their ordering.
That is, if an upgrade changes the kind of index on a column, there should be
an implicit removal of the index, and the creation of the new index would
require a "depends" on the new removal operation.  The database implementation
would need to add this kind of logic, depending on how the database platform
handles these kinds of operations.
"""




