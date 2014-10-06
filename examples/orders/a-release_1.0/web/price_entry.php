<html>
    <head>
        <title>Price Entry</title>
    </head>
    <body>
    
<?php

if (array_key_exists("action", $_POST) && $_POST["action"] == "save" &&
        array_key_exists("sku", $_POST) && array_key_exists("sku", $_POST)) {
    require_once __DIR__.'/../php_lib/setup.php';
    require_once __DIR__.'/../php_lib/price_entry_lib.php';

    $sku = $_POST["sku"];
    $price = $_POST["price"];

    $res = PriceEntry::savePrice($db, $sku, $price);
    if ($res[0]) {
?>
        <p><em>
            Added <?= $sku ?> = <?= $price ?>
        </em></p>
<?php
    } else {
?>
        <p><strong>
            ERROR: bad sku (<?= $sku ?>) or price (<?= $price ?>)
        </strong></p>
<?php
    }
}
?>


    <form action="price_entry.php" method="POST">
        <input type="hidden" name="action" value="save">

        <label for="sku">Product SKU: </label>
            <input id="sku" type="text" name="sku">

        <br>
        <label for="price">Price: </label>
            <input id="price" type="text" name="price">

        <br>
        <input type="submit" value="Commit">
    </form>
    </body>
</html>
