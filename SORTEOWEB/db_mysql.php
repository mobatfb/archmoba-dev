<?php
declare(strict_types=1);

function mysql_connection(): PDO {
    static $pdo = null;
    if ($pdo instanceof PDO) return $pdo;
    $c = require __DIR__.'/config.php';
    if (!in_array('mysql', PDO::getAvailableDrivers(), true)) {
        throw new RuntimeException('Habilita la extension pdo_mysql de PHP.');
    }
    $dsn = 'mysql:host='.$c['host'].';port='.$c['port'].';dbname='.$c['database'].';charset=utf8mb4';
    $pdo = new PDO($dsn, $c['user'], $c['password'], [
        PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES=>false,
        PDO::ATTR_STRINGIFY_FETCHES=>false,
    ]);
    $pdo->exec("SET time_zone = '+00:00'");
    return $pdo;
}
function mysql_time(?string $s): ?string {
    if ($s === null) return null;
    $t = strtotime($s);
    if ($t === false) throw new RuntimeException('Fecha invalida.');
    return gmdate('Y-m-d H:i:s', $t);
}
function app_time(?string $s): ?string {
    return $s === null ? null : date('c', strtotime($s.' UTC'));
}
function mysql_load(PDO $pdo): array {
    $d = empty_data();
    foreach ($pdo->query('SELECT * FROM raffles') as $r) {
        $r['total'] = (int)$r['total']; $r['price_cents'] = (int)$r['price_cents'];
        foreach (['created_at','updated_at','finalized_at'] as $k) $r[$k] = app_time($r[$k]);
        $r['photos'] = [null,null,null];
        $d['raffles'][$r['id']] = $r;
    }
    foreach ($pdo->query('SELECT raffle_id, slot, filename FROM raffle_photos') as $p) {
        $d['raffles'][$p['raffle_id']]['photos'][(int)$p['slot']-1] = $p['filename'];
    }
    foreach ($pdo->query('SELECT * FROM participants') as $p) {
        $p['number'] = (int)$p['number'];
        foreach (['created_at','updated_at'] as $k) $p[$k] = app_time($p[$k]);
        $d['participants'][$p['id']] = $p;
    }
    return $d;
}
function mysql_exec(PDO $pdo, string $sql, array $params): void {
    $pdo->prepare($sql)->execute($params);
}
function mysql_audit(PDO $pdo, string $entity, string $id, string $action, ?array $old, ?array $new): void {
    // No guardar datos personales ni codigos de reclamo en la bitacora.
    $details=[];
    foreach (['status','payment','number','total','price_cents','type'] as $k) {
        if (($old[$k]??null) !== ($new[$k]??null)) $details[$k]=['before'=>$old[$k]??null,'after'=>$new[$k]??null];
    }
    mysql_exec($pdo, 'INSERT INTO audit_events (entity_type,entity_id,action,details) VALUES (?,?,?,?)',
        [$entity,$id,$action,json_encode($details, JSON_THROW_ON_ERROR)]);
}
function mysql_save(PDO $pdo, array $before, array $after): void {
    // Primero borrar hijos, luego padres; crear padres antes de hijos.
    foreach (array_diff_key($before['participants'],$after['participants']) as $id=>$p) {
        mysql_exec($pdo,'DELETE FROM participants WHERE id=?',[$id]);
        mysql_audit($pdo,'participant',$id,'delete',$p,null);
    }
    foreach (array_diff_key($before['raffles'],$after['raffles']) as $id=>$r) {
        mysql_exec($pdo,'DELETE FROM raffles WHERE id=?',[$id]);
        mysql_audit($pdo,'raffle',$id,'delete',$r,null);
    }
    foreach ($after['raffles'] as $id=>$r) {
        $old=$before['raffles'][$id]??null;
        if ($old !== null && $r == $old) continue;
        $values=[$r['title'],$r['description'],$r['type'],$r['total'],$r['price_cents'],$r['status'],mysql_time($r['created_at']),mysql_time($r['updated_at']),mysql_time($r['finalized_at']),$id];
        if ($old === null) {
            mysql_exec($pdo,'INSERT INTO raffles (title,description,type,total,price_cents,status,created_at,updated_at,finalized_at,id) VALUES (?,?,?,?,?,?,?,?,?,?)',$values);
        } else {
            mysql_exec($pdo,'UPDATE raffles SET title=?,description=?,type=?,total=?,price_cents=?,status=?,created_at=?,updated_at=?,finalized_at=? WHERE id=?',$values);
        }
        if ($old === null || $r['photos'] !== $old['photos']) {
            mysql_exec($pdo,'DELETE FROM raffle_photos WHERE raffle_id=?',[$id]);
            foreach ($r['photos'] as $slot=>$name) {
                if ($name !== null) mysql_exec($pdo,'INSERT INTO raffle_photos (raffle_id,slot,filename) VALUES (?,?,?)',[$id,$slot+1,$name]);
            }
        }
        mysql_audit($pdo,'raffle',$id,$old===null?'create':'update',$old,$r);
    }
    foreach ($after['participants'] as $id=>$p) {
        $old=$before['participants'][$id]??null;
        if ($old !== null && $p == $old) continue;
        $values=[$p['raffle_id'],$p['name'],$p['email'],$p['phone'],$p['number'],$p['payment'],mysql_time($p['created_at']),mysql_time($p['updated_at']),$id];
        if ($old===null) mysql_exec($pdo,'INSERT INTO participants (raffle_id,name,email,phone,number,payment,created_at,updated_at,id) VALUES (?,?,?,?,?,?,?,?,?)',$values);
        else mysql_exec($pdo,'UPDATE participants SET raffle_id=?,name=?,email=?,phone=?,number=?,payment=?,created_at=?,updated_at=? WHERE id=?',$values);
        mysql_audit($pdo,'participant',$id,$old===null?'create':'update',$old,$p);
    }
}
function db(callable $fn, bool $write = false): mixed {
    store_init();
    $pdo = mysql_connection();
    // Lectura consistente y serializacion de las escrituras del panel local.
    $pdo->exec('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');
    $pdo->beginTransaction();
    try {
        if ($write && $pdo->query('SELECT id FROM app_lock WHERE id=1 FOR UPDATE')->fetchColumn() === false) {
            throw new RuntimeException('Falta el registro app_lock. Importa el SQL.');
        }
        $data = mysql_load($pdo);
        $before = $data;
        $result = $fn($data);
        if ($write) mysql_save($pdo, $before, $data);
        $pdo->commit();
        return $result;
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        throw $e;
    }
}
