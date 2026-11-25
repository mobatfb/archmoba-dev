<?php
declare(strict_types=1);
if (!defined('SW_APP')) { http_response_code(404); exit; }
const SW_VERSION = '1.2.0';
require __DIR__.'/core/session.php';
require __DIR__.'/core/database.php';
require __DIR__.'/core/helpers.php';
