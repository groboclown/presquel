# Example project: orders

This example project maintains a purchase tracking system.  It provides simple
PHP pages for data input for the price list and customers,
for making purchases, and for reporting.

The project shows an evolution of functionality and features over time.

1. Release 1.0.  A simple price list.  Data entry and the schema to hold it.
2. Release 2.0-a.  New development after the 1.0 release to add
    support for additional record keeping on the price list.  Specifically,
    keeping track of who added the prices.  It also includes migration code
    for separating the product definition from the prices.
3. Release 1.1.  A bug fix to change the currency from a float to a numeric
    value.  This came in after development started on the Release 2.0
    branch, so this bug fix requires both a release to customers, and proper
    handling in the release 2.0 branch.
4. Release 2.0-b.  After the release of the 1.1 bug fix, the fix needed to
    be brought back into the 2.0 branch.
