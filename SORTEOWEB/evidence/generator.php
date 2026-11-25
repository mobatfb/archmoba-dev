<?php
declare(strict_types=1);
if(!defined('SW_APP')){http_response_code(404);exit;}
function draw_ticket_svg(array $rules,int $number): string {
    $title=htmlspecialchars($rules['title'],ENT_XML1|ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');$id=htmlspecialchars($rules['raffle_id'],ENT_XML1|ENT_QUOTES,'UTF-8');$num=str_pad((string)$number,4,'0',STR_PAD_LEFT);
    return '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560" viewBox="0 0 1000 560"><rect width="1000" height="560" fill="#10294d"/><rect x="28" y="28" width="944" height="504" rx="20" fill="#fff"/><g font-family="Arial,sans-serif" text-anchor="middle" fill="#10294d"><text x="500" y="95" font-size="38" font-weight="bold">SORTEOWEB</text><text x="500" y="155" font-size="24">BOLETO PRESELECCIONADO</text><text x="500" y="285" font-size="100" font-weight="bold">'.$num.'</text><text x="500" y="340" font-size="24">'.$title.'</text><text x="500" y="400" font-size="18">ID: '.$id.'</text><text x="500" y="470" font-size="20">Resultado sujeto a las reglas de cierre publicadas</text></g></svg>';
}
function draw_zip(array $rules,int $number,string $password): string {
    if(!class_exists('ZipArchive')||!defined('ZipArchive::EM_AES_256')||!ZipArchive::isEncryptionMethodSupported(ZipArchive::EM_AES_256,true))throw new DomainException('Habilita PHP ZIP con soporte AES-256 en el hosting antes de activar.');
    $tmp=tempnam(sys_get_temp_dir(),'swe_');if($tmp===false)throw new RuntimeException('Tempfile unavailable');chmod($tmp,0600);$zip=new ZipArchive();$open=false;
    try{if($zip->open($tmp,ZipArchive::CREATE|ZipArchive::OVERWRITE)!==true)throw new RuntimeException('ZIP open failed');$open=true;
        $manifest=$rules+['winning_number'=>$number];
        foreach(['boleto.svg'=>draw_ticket_svg($rules,$number),'reglas-y-resultado.json'=>json_encode($manifest,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT)] as $name=>$bytes){if(!$zip->addFromString($name,$bytes)||!$zip->setEncryptionName($name,ZipArchive::EM_AES_256,$password))throw new RuntimeException('ZIP encryption failed');}
        if(!$zip->close())throw new RuntimeException('ZIP close failed');$open=false;$bytes=file_get_contents($tmp);if(!is_string($bytes)||strlen($bytes)<100||strlen($bytes)>1048576)throw new RuntimeException('ZIP invalid');return $bytes;
    }finally{if($open)$zip->close();@unlink($tmp);}
}
