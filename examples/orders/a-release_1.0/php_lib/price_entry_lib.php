<?php


require_once __DIR__.'/../php_dbo/Price.php';

class PriceEntry {
    public static function savePrice($db, $sku, $price) {
        if (! is_string($sku) || strlen($sku) <= 0) {
            return array(False, 'sku must be a string', null, null);
        }
        $price = floatval($price);
        $ret = PriceEntry::checkError(
            Dbo\Price::$INSTANCE->create($db, $sku, $price),
            "Invalid SKU or Price");
        return $ret;
    }


    public static function checkError($returned, $message) {
        if ($returned["haserror"]) {
            $backtrace = 'Database access error (' . $returned["errorcode"] . ' ' .
                 $returned["error"] . '):';
            foreach (debug_backtrace() as $stack) {
                $args = array();
                foreach ($stack['args'] as $arg) {
                    $args[] = print_r($stack['args'], TRUE);
                }
                $backtrace .= "\n    " . $stack['function'] .
                     '(' . implode(', ', $args) .
                     ') [' . $stack['file'] .
                     ' @ ' . $stack['line'] . ']';
            }
            error_log($backtrace);
            return array(False, $message, null, null);
        }
        return array(True, null, $returned['result'], $returned['rowcount']);
    }
}
