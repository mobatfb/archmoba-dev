<?php
declare(strict_types=1);
if (!defined('SW_APP')) { http_response_code(404); exit; }
function db(): PDO {
    static $pdo;
    if (!$pdo) {
        $c=require (is_file(dirname(__DIR__).'/config.local.php')?dirname(__DIR__).'/config.local.php':dirname(__DIR__).'/config.php');
        $pdo=new PDO('mysql:host='.$c['host'].';port='.$c['port'].';dbname='.$c['database'].';charset=utf8mb4',$c['user'],$c['password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_EMULATE_PREPARES=>false]);
    }
    return $pdo;
}
function query(string $sql,array $params=[]): PDOStatement { $s=db()->prepare($sql);$s->execute($params);return $s; }
function one(string $sql,array $params=[]): ?array { return query($sql,$params)->fetch()?:null; }
function all(string $sql,array $params=[]): array { return query($sql,$params)->fetchAll(); }
function tx(callable $f): mixed { $d=db();$d->beginTransaction();try{$v=$f();$d->commit();return $v;}catch(Throwable $e){if($d->inTransaction())$d->rollBack();throw $e;} }
