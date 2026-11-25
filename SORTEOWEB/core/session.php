<?php
declare(strict_types=1);
if (!defined('SW_APP')) { http_response_code(404); exit; }
date_default_timezone_set('America/Guayaquil');
$https = (!empty($_SERVER['HTTPS']) && strtolower((string)$_SERVER['HTTPS']) !== 'off') || ($_SERVER['SERVER_PORT'] ?? '') === '443';
$local = in_array($_SERVER['REMOTE_ADDR'] ?? '', ['127.0.0.1','::1'], true) && in_array(strtolower(parse_url('http://'.($_SERVER['HTTP_HOST']??''),PHP_URL_HOST)??''),['localhost','127.0.0.1','[::1]'],true);
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'");
header('Cache-Control: no-store');
ini_set('session.use_strict_mode','1');
ini_set('session.use_only_cookies','1');
session_name(defined('SW_PUBLIC') && SW_PUBLIC ? 'sorteoweb_public' : 'sorteoweb_session');
session_set_cookie_params(['lifetime'=>0,'path'=>rtrim(dirname($_SERVER['SCRIPT_NAME']??'/'),'/\\').'/','secure'=>$https,'httponly'=>true,'samesite'=>(defined('SW_PUBLIC')&&SW_PUBLIC?'Lax':'Strict')]);
session_start();
