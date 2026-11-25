<?php
declare(strict_types=1);
define('SW_APP',true);
// Preserve existing administrative links and private photo requests.
$adminRoute=isset($_GET['admin']) || isset($_GET['page']) || isset($_GET['photo']);
define('SW_PUBLIC',!$adminRoute);
require __DIR__.'/app.php';
if ($adminRoute) { require __DIR__.'/admin/dispatch.php'; exit; }
require __DIR__.'/core/public.php';
require __DIR__.'/landing/header.php';
require __DIR__.'/landing/footer.php';
require __DIR__.'/auth/dispatch.php';
