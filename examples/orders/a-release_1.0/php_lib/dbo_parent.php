<?php

namespace Dbo;

class DboParent {
   private $problems = array();


    /**
     * Adds a validation problem, that will be reported on the next call to
     * validate().
     */
    protected function addValidationError(string $name, string $problem) {
        $problems[$name] = $problem;
    }

    protected function ensure($bool, $arg) {
        if (! $bool) {
            addValidationError($arg, 'invalid format');
            return false;
        }
        return true;
    }

    protected function finalCheck($bool) {
        if (sizeof($this->problems) > 0) {
            throw new ValidationException($this->problems);
        }
        return true;
    }

    protected function insertFailed($table, $data) {
        throw new ValidationException(array($table => 'fails to meet constraints'));
    }
}
