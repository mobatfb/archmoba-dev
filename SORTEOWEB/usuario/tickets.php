<?php
declare(strict_types=1);
if(!defined('SW_APP')||!SW_PUBLIC){http_response_code(404);exit;}
// Bound each request to at most 1000 tickets, even for million-ticket raffles.
const SW_TICKET_PAGE_SIZE=1000;
function ticket_number_label(int $n): string {return str_pad((string)$n,4,'0',STR_PAD_LEFT);}
function ticket_snapshot(mixed $id,mixed $page,mixed $jump=null,?int $uid=null): array {
    if(!valid_id($id))throw new DomainException('Sorteo no encontrado.');
    return tx(function()use($id,$page,$jump,$uid){
        $r=one("SELECT id,title,total,price_cents,status,participation_mode,close_mode,participation_limit,closes_at,draw_version FROM raffles WHERE id=?",[$id]);
        if(!$r)throw new DomainException('Sorteo no encontrado.');
        $total=max(0,(int)$r['total']);$pages=max(1,(int)ceil($total/SW_TICKET_PAGE_SIZE));
        $page=filter_var($page,FILTER_VALIDATE_INT,['options'=>['min_range'=>1,'max_range'=>$pages]])?:1;
        if(is_string($jump)&&preg_match('/^[0-9]{1,7}$/D',$jump)){$n=(int)$jump;if($n>=1&&$n<=$total)$page=intdiv($n-1,SW_TICKET_PAGE_SIZE)+1;}
        $start=($page-1)*SW_TICKET_PAGE_SIZE+1;$end=min($total,$start+SW_TICKET_PAGE_SIZE-1);
        $shared=$r['participation_mode']==='compartido';$capped=$r['close_mode']==='capacidad';$capacity=$capped?(int)$r['participation_limit']:($shared?null:$total);
        $counts=one("SELECT COUNT(*) AS occupied,COALESCE(SUM(payment='pagado'),0) AS paid,COUNT(DISTINCT number) AS distinct_numbers FROM participants WHERE raffle_id=? AND number BETWEEN 1 AND ?",[$id,$total]);
        $occupied=(int)($counts['occupied']??0);$paid=(int)($counts['paid']??0);$available=$capacity===null?null:max(0,$capacity-$occupied);
        $blocked=[];$buyers=[];
        foreach(all("SELECT number,COUNT(*) AS n,SUM(payment='pagado') AS paid,MAX(CASE WHEN user_id=? THEN 1 ELSE 0 END) AS mine FROM participants WHERE raffle_id=? AND number BETWEEN ? AND ? GROUP BY number",[$uid??0,$id,$start,$end]) as $p){$n=(int)$p['number'];$buyers[$n]=(int)$p['paid'];$blocked[$n]=$shared?((int)$p['mine']?'mine':((int)$p['paid']?'shared':'free')):((int)$p['paid']?'sold':'pending');}
        $active=$r['status']==='activo'&&!draw_due($r,$paid)&&($r['closes_at']===null||(int)$r['closes_at']>time());
        return ['id'=>$id,'title'=>$r['title'],'active'=>$active,'total'=>$total,'price'=>(int)$r['price_cents'],'price_label'=>money($r['price_cents']),'page'=>$page,'pages'=>$pages,'start'=>$start,'end'=>$end,'paid'=>$paid,'pending'=>$occupied-$paid,'available'=>$available,'capacity'=>$capacity,'shared'=>$shared,'has_evidence'=>(int)$r['draw_version']===1,'distinct'=>(int)$counts['distinct_numbers'],'close_label'=>draw_close_label($r),'blocked'=>(object)$blocked,'buyers'=>(object)$buyers];
    });
}
function ticket_status_response(?array $u): never {
    header('Content-Type: application/json; charset=UTF-8');
    header('Cache-Control: no-store, private');
    $code=200;
    try{
        if(($_SERVER['REQUEST_METHOD']??'')!=='GET'){$code=405;$data=['error'=>'Método no permitido.'];}
        elseif(!$u||!profile_complete($u)){$code=401;$data=['error'=>'Vuelve a iniciar sesión.'];}
        else{
            session_write_close();
            $data=ticket_snapshot($_GET['id']??null,$_GET['p']??1,null,(int)$u['id']);
            if(!$data['active']){$code=409;$data=['error'=>'Este sorteo ya no está activo.'];}
            else unset($data['title'],$data['id']);
        }
    }catch(DomainException $e){$code=404;$data=['error'=>'Sorteo no encontrado.'];}
    catch(Throwable $e){error_log('SORTEOWEB tickets: '.get_class($e).' '.$e->getCode());$code=503;$data=['error'=>'No se pudo actualizar la disponibilidad.'];}
    http_response_code($code);echo json_encode($data,JSON_INVALID_UTF8_SUBSTITUTE|JSON_THROW_ON_ERROR);exit;
}
