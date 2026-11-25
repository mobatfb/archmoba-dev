<?php
/** Pagina accesible si el navegador no admite la ventana flotante. */
require_once __DIR__ . '/../../lib/funciones.php';
require_once __DIR__ . '/../../lib/foto_perfil_privada.php';
exigirLogin();
$actual = usuarioActual();
if (empty($_SESSION['csrf_perfil_foto'])) $_SESSION['csrf_perfil_foto'] = bin2hex(random_bytes(32));
$tituloPagina = 'Mi perfil';
$subtituloPagina = 'Datos de tu cuenta y foto privada.';
$ya = sgaPerfilFotoExiste($actual);
require __DIR__ . '/../../partials/header.php';
?>
<section class="card" style="max-width:650px">
  <h2>Datos personales</h2>
  <p><strong>Apellidos:</strong> <?=e($actual['apellidos']??'')?></p>
  <p><strong>Nombres:</strong> <?=e($actual['nombres']??'')?></p>
  <p><strong>C&eacute;dula:</strong> <?=e($actual['cedula']??'')?></p>
  <p><strong>Correo:</strong> <?=e($actual['correo']??'')?></p>
  <p><strong>Avatar:</strong>
  <?php if($ya):?><img style="width:60px;height:60px;object-fit:cover;border-radius:50%;vertical-align:middle" src="<?=e(url('modulos/perfil/foto.php'))?>" alt="Foto de perfil">
  <?php else:?><?=e(sgaPerfilIniciales($actual))?><?php endif;?></p>
  <h3>Cambiar foto</h3>
  <p class="mini-note">La imagen se convierte a PNG de 120 &times; 120 p&iacute;xeles, se guarda con tu c&eacute;dula y requiere iniciar sesi&oacute;n para visualizarla.</p>
  <form method="post" action="<?=e(url('modulos/perfil/guardar_foto.php'))?>" enctype="multipart/form-data" style="max-width:470px;display:grid;gap:11px">
    <input type="hidden" name="csrf" value="<?=e($_SESSION['csrf_perfil_foto'])?>">
    <input type="hidden" name="retorno" value="<?=e(url('modulos/perfil/index.php'))?>">
    <input type="hidden" name="accion" value="guardar">
    <label>Foto JPG, PNG, GIF o WebP (m&aacute;ximo 5 MB)
      <input type="file" name="foto" accept="image/jpeg,image/png,image/webp,image/gif" required></label>
    <button type="submit" class="btn btn-primary">Guardar foto</button>
  </form>
  <?php if($ya):?>
  <form method="post" action="<?=e(url('modulos/perfil/guardar_foto.php'))?>" style="margin-top:12px">
    <input type="hidden" name="csrf" value="<?=e($_SESSION['csrf_perfil_foto'])?>">
    <input type="hidden" name="retorno" value="<?=e(url('modulos/perfil/index.php'))?>">
    <input type="hidden" name="accion" value="eliminar">
    <button type="submit" class="btn btn-secondary">Eliminar foto y mostrar iniciales</button>
  </form>
  <?php endif;?>
  <p style="margin-top:20px"><a class="btn btn-secondary" href="<?=e(url('modulos/perfil/cambiar_clave.php'))?>">Cambiar contrase&ntilde;a</a></p>
</section>
<?php require __DIR__ . '/../../partials/footer.php'; ?>
