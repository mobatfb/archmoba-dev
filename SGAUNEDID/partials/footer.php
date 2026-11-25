</main></div>
<?php
if (empty($_SESSION['csrf_cambiar_clave'])) $_SESSION['csrf_cambiar_clave'] = bin2hex(random_bytes(32));
$sgaReabrirClave = !empty($_SESSION['sga_reabrir_cambio_clave']);
unset($_SESSION['sga_reabrir_cambio_clave']);
$sgaRetornoClave = (string)($_SERVER['REQUEST_URI'] ?? url('dashboard.php'));
?>
<?php
require_once __DIR__ . '/../lib/foto_perfil_privada.php';
if (empty($_SESSION['csrf_perfil_foto'])) $_SESSION['csrf_perfil_foto']=bin2hex(random_bytes(32));
$sgaPerfilReabrir=!empty($_SESSION['sga_reabrir_perfil']);
$sgaPerfilFeedback=$_SESSION['sga_perfil_feedback']??null;
unset($_SESSION['sga_perfil_feedback']);
unset($_SESSION['sga_reabrir_perfil']);
$sgaPerfilRetorno=(string)($_SERVER['REQUEST_URI']??url('dashboard.php'));
$sgaPerfilUsuario=usuarioActual();
$sgaPerfilNombre=trim((string)($sgaPerfilUsuario['apellidos']??'').' '.(string)($sgaPerfilUsuario['nombres']??''));
$sgaPerfilImagen=sgaPerfilFotoExiste($sgaPerfilUsuario);
$sgaPerfilInicialesTexto=sgaPerfilIniciales($sgaPerfilUsuario);
$sgaPerfilFotoVersion=0;
if($sgaPerfilImagen){$pr=sgaPerfilRutaFoto($sgaPerfilUsuario);$sgaPerfilFotoVersion=$pr?(int)@filemtime($pr):0;}
?>
<dialog id="sga-perfil-dialog" class="sga-perfil-dialog" data-reopen="<?=$sgaPerfilReabrir?'1':'0'?>" aria-labelledby="sga-perfil-titulo">
  <div class="sga-perfil-cabecera">
    <div><h2 id="sga-perfil-titulo">Mi perfil</h2><p>Consulta tu cuenta y administra tu foto y contrase&ntilde;a.</p></div>
    <button type="button" class="sga-perfil-cerrar" id="sga-perfil-cerrar" aria-label="Cerrar ventana">&times;</button>
  </div>
  <div class="sga-perfil-contenido">
    <?php if(is_array($sgaPerfilFeedback)):?>
    <div class="sga-perfil-mensaje <?=e($sgaPerfilFeedback['tipo']==='success'?'success':'error')?>" role="status"><?=e($sgaPerfilFeedback['mensaje']??'')?></div>
    <?php endif;?>
    <div class="sga-perfil-identidad">
      <div class="sga-perfil-avatar sga-perfil-avatar--grande" aria-label="Avatar personal">
        <?php if($sgaPerfilImagen):?><img src="<?=e(url('modulos/perfil/foto.php').'?v='.$sgaPerfilFotoVersion)?>" alt="Foto de perfil actual" draggable="false"><?php else:?><?=e($sgaPerfilInicialesTexto)?><?php endif;?>
      </div>
      <div class="sga-perfil-persona">
        <strong><?=e($sgaPerfilNombre)?></strong>
        <span><b>C&eacute;dula:</b> <?=e($sgaPerfilUsuario['cedula']??'')?></span>
        <span><b>Correo:</b> <?=e($sgaPerfilUsuario['correo']?:'No registrado')?></span>
        <span><b>Rol activo:</b> <?=e(ucfirst(rolOperativoActual()?:'Usuario'))?></span>
      </div>
    </div>
    <div class="sga-perfil-seccion">
      <div class="sga-perfil-seccion-cabecera"><h3>Foto de perfil</h3><span>PNG &middot; 120 &times; 120 px</span></div>
      <p>Solo visible dentro del sistema con la sesi&oacute;n iniciada. Se guarda en una carpeta privada del servidor, no en la base de datos.</p>
      <form method="post" action="<?=e(url('modulos/perfil/guardar_foto.php'))?>" enctype="multipart/form-data" class="sga-perfil-subir-form" id="sga-perfil-subir-form">
        <input type="hidden" name="csrf" value="<?=e($_SESSION['csrf_perfil_foto'])?>">
        <input type="hidden" name="retorno" value="<?=e($sgaPerfilRetorno)?>">
        <input type="hidden" name="accion" value="guardar">
        <label for="sga-perfil-foto-archivo">Seleccionar imagen (JPG, PNG, WebP o GIF, hasta 5 MB)
          <input id="sga-perfil-foto-archivo" type="file" name="foto" accept="image/jpeg,image/png,image/webp,image/gif" required>
        </label>
        <button type="submit" class="btn btn-primary">Guardar foto</button>
      </form>
      <?php if($sgaPerfilImagen):?>
      <form method="post" action="<?=e(url('modulos/perfil/guardar_foto.php'))?>" class="sga-perfil-borrar-form" id="sga-perfil-borrar-form">
        <input type="hidden" name="csrf" value="<?=e($_SESSION['csrf_perfil_foto'])?>">
        <input type="hidden" name="retorno" value="<?=e($sgaPerfilRetorno)?>">
        <input type="hidden" name="accion" value="eliminar">
        <button type="submit" class="btn btn-secondary">Eliminar foto y usar iniciales</button>
      </form>
      <?php else:?><small class="sga-perfil-estado">No tienes foto; se muestran tus iniciales.</small><?php endif;?>
    </div>
    <div class="sga-perfil-pie">
      <a id="sga-password-open" class="btn btn-secondary" href="<?=e(url('modulos/perfil/cambiar_clave.php'))?>" aria-haspopup="dialog" aria-controls="sga-password-dialog">Cambiar contrase&ntilde;a</a>
      <button type="button" class="btn btn-primary" id="sga-perfil-listo">Cerrar</button>
    </div>
  </div>
</dialog>
<script src="<?=e(url('assets/js/sga_perfil.js'))?>?v=1634"></script>
<style>
/* V1.6.35: botones para mostrar u ocultar cada contrasena del flotante. */
.sga-password-dialog .sga-password-grupo{display:grid;gap:6px;min-width:0}
.sga-password-dialog .sga-password-campo{position:relative;min-width:0}
.sga-password-dialog .sga-password-campo > input{display:block;width:100%;padding-right:51px}
.sga-password-dialog .sga-password-ojo{
  position:absolute;right:5px;top:50%;transform:translateY(-50%);
  display:inline-flex;align-items:center;justify-content:center;
  width:37px;height:35px;min-height:0;margin:0;padding:0;
  border:1px solid transparent;border-radius:8px;background:transparent;
  color:#49688d;cursor:pointer;line-height:1;z-index:1;
}
.sga-password-dialog .sga-password-ojo:hover{background:#edf4fc;color:#124b91}
.sga-password-dialog .sga-password-ojo:focus-visible{
  outline:2px solid #2576c8;outline-offset:1px;background:#edf4fc;
}
.sga-password-dialog .sga-password-ojo svg{width:20px;height:20px;display:block;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.sga-password-dialog .sga-password-ojo[aria-pressed="false"] .sga-password-ojo-tachado{display:none}
</style>
<dialog id="sga-password-dialog" class="sga-password-dialog" aria-labelledby="sga-password-title" aria-describedby="sga-password-description">
  <div class="sga-password-head">
    <div>
      <h2 id="sga-password-title">Cambiar contraseña</h2>
      <p id="sga-password-description">Actualiza tu contraseña personal para ingresar al SGA UNEDID.</p>
    </div>
    <button class="sga-password-close" type="button" id="sga-password-close" aria-label="Cerrar ventana">&times;</button>
  </div>
  <form class="sga-password-form" id="sga-password-form" method="post" action="<?=e(url('modulos/perfil/cambiar_clave.php'))?>" autocomplete="off">
    <input type="hidden" name="csrf" value="<?=e($_SESSION['csrf_cambiar_clave'])?>">
    <input type="hidden" name="retorno" value="<?=e($sgaRetornoClave)?>">
    <div class="sga-password-grupo">
      <label for="sga-password-current">Contraseña actual</label>
      <div class="sga-password-campo">
        <input type="password" name="clave_actual" id="sga-password-current" autocomplete="current-password" required maxlength="128">
        <button type="button" class="sga-password-ojo" data-sga-password-campo="sga-password-current" data-sga-password-nombre="contraseña actual"
          aria-controls="sga-password-current" aria-label="Mostrar contraseña actual" aria-pressed="false" title="Mostrar contraseña actual">
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z"/>
            <circle cx="12" cy="12" r="3"/>
            <path class="sga-password-ojo-tachado" d="M3 3l18 18"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="sga-password-grupo">
      <label for="sga-password-new">Nueva contraseña</label>
      <div class="sga-password-campo">
        <input type="password" name="clave_nueva" id="sga-password-new" autocomplete="new-password" required minlength="8" maxlength="72">
        <button type="button" class="sga-password-ojo" data-sga-password-campo="sga-password-new" data-sga-password-nombre="nueva contraseña"
          aria-controls="sga-password-new" aria-label="Mostrar nueva contraseña" aria-pressed="false" title="Mostrar nueva contraseña">
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z"/>
            <circle cx="12" cy="12" r="3"/>
            <path class="sga-password-ojo-tachado" d="M3 3l18 18"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="sga-password-grupo">
      <label for="sga-password-confirm">Confirmar nueva contraseña</label>
      <div class="sga-password-campo">
        <input type="password" name="clave_confirmacion" id="sga-password-confirm" autocomplete="new-password" required minlength="8" maxlength="72">
        <button type="button" class="sga-password-ojo" data-sga-password-campo="sga-password-confirm" data-sga-password-nombre="confirmación de contraseña"
          aria-controls="sga-password-confirm" aria-label="Mostrar confirmación de contraseña" aria-pressed="false" title="Mostrar confirmación de contraseña">
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z"/>
            <circle cx="12" cy="12" r="3"/>
            <path class="sga-password-ojo-tachado" d="M3 3l18 18"/>
          </svg>
        </button>
      </div>
    </div>
    <p class="sga-password-hint">Utiliza al menos 8 caracteres y una contraseña diferente de la actual. No la compartas.</p>
    <div class="sga-password-actions">
      <button type="button" class="btn btn-secondary" id="sga-password-cancel">Cancelar</button>
      <button type="submit" class="btn btn-primary">Guardar contraseña</button>
    </div>
  </form>
</dialog>
<script>
// Modal nativo accesible y alternativa de pagina completa cuando no hay JavaScript.
(() => {
  const dialog = document.getElementById('sga-password-dialog');
  const trigger = document.getElementById('sga-password-open');
  const form = document.getElementById('sga-password-form');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  // Cada ojito controla unicamente su propio campo, sin alterar su valor.
  const botonesOjo = [...dialog.querySelectorAll('.sga-password-ojo')];
  function cambiarVisibilidad(boton, mostrar) {
    const campo = document.getElementById(boton.dataset.sgaPasswordCampo);
    if (!campo) return;
    campo.type = mostrar ? 'text' : 'password';
    boton.setAttribute('aria-pressed', mostrar ? 'true' : 'false');
    const accion = mostrar ? 'Ocultar ' : 'Mostrar ';
    const descripcion = accion + (boton.dataset.sgaPasswordNombre || 'contraseña');
    boton.setAttribute('aria-label', descripcion);
    boton.title = descripcion;
  }
  botonesOjo.forEach((boton) => {
    boton.addEventListener('click', () => {
      const campo = document.getElementById(boton.dataset.sgaPasswordCampo);
      if (campo) cambiarVisibilidad(boton, campo.type === 'password');
    });
  });
  function abrirClave(){
    document.documentElement.classList.remove('sga-menu-open');
    const menuTrigger = document.getElementById('sga-menu-open');
    if (menuTrigger) menuTrigger.setAttribute('aria-expanded', 'false');
    if (!dialog.open) dialog.showModal();
    const actual = document.getElementById('sga-password-current');
    if (actual) actual.focus();
  }
  trigger?.addEventListener('click', (e) => {e.preventDefault(); abrirClave();});
  for (const id of ['sga-password-close','sga-password-cancel']) {
    document.getElementById(id)?.addEventListener('click', () => dialog.close());
  }
  dialog.addEventListener('close', () => {
    // Al cerrar se borran los valores y se vuelven a ocultar todas las claves.
    if (form) form.reset();
    botonesOjo.forEach((boton) => cambiarVisibilidad(boton, false));
  });
  if (<?= $sgaReabrirClave ? "true" : "false" ?>) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', abrirClave, {once:true});
    else abrirClave();
  }
})();
</script>
<script>
document.querySelectorAll('.alert-close').forEach(b=>b.addEventListener('click',()=>b.closest('.alert')?.remove()));
document.querySelectorAll('[data-confirm]').forEach(b=>b.addEventListener('click',e=>{if(!confirm(b.dataset.confirm))e.preventDefault();}));
// Un indicador discreto evita dobles envios sin alterar valores POST de los botones.
document.addEventListener('submit',function(e){
  const f=e.target;
  if(!(f instanceof HTMLFormElement)||f.method.toLowerCase()!=='post')return;
  const b=e.submitter;
  if(!b || b.disabled || e.defaultPrevented)return;
  b.classList.add('is-submitting');b.setAttribute('aria-busy','true');
  window.requestAnimationFrame(function(){b.disabled=true;});
},true);
</script>
<script src="<?=e(url('assets/js/responsive.js'))?>?v=<?=(int)filemtime(__DIR__.'/../assets/js/responsive.js')?>"></script>
</body></html>
