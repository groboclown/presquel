<?php

/**
 * Configuration file for the example.
 *
 * You should copy this file to "site.conf.php" then setup the missing
 * arguments in the copy with your environment settings to try it out.
 */

$siteConfig = array(
    // Database configuration
    'db_config' => array(
        // Uses PDO format.
        'dsn' => '@dsn@',
        'username' => '@dbuser@',
        'password' => '@dbpassword@'
    )
);
