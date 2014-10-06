<?php
require_once __DIR__.'/../conf/site.conf.php';
require_once __DIR__.'/dbo_parent.php';

$db = new PDO($siteConfig['db_config']['dsn'],
        $siteConfig['db_config']['username'],
        $siteConfig['db_config']['password']);

// We handle the exceptions ourselves, to allow for more flexible
// error handling.  It does mean that the code needs to be more
// careful, so that it can identify the errors.
//$conn->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

