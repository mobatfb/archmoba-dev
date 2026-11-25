<?php
declare(strict_types=1);
if (!defined('SW_APP')) { http_response_code(404); exit; }
function h(mixed $v): string { return htmlspecialchars((string)$v, ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
function token(): string { return $_SESSION['csrf']??=bin2hex(random_bytes(32)); }
function csrf(): string { return '<input type="hidden" name="csrf" value="'.h(token()).'">'; }
function field(string $key,int $max,bool $required=true): string { $v=$_POST[$key]??'';if(!is_string($v))throw new DomainException('Campo inválido.');$v=trim($v);if(($required&&$v==='')||strlen($v)>$max)throw new DomainException('Revisa los campos y sus longitudes.');return $v; }
function money(int|string|null $c): string { return '$'.number_format(((int)$c)/100,2,',','.'); }
function state_name(string $s): string { return ['borrador'=>'Borrador','activo'=>'Activo','finalizado'=>'Finalizado','pendiente'=>'Pendiente','pagado'=>'Pagado'][$s]??$s; }
function valid_id(mixed $id): bool { return is_string($id) && preg_match('/^[a-f0-9]{24}$/D',$id)===1; }
