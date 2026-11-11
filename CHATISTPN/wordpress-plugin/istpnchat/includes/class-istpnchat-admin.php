<?php
/** Panel de administracion y prueba, sin dependencia de jQuery ni IA. */
if ( ! defined( 'ABSPATH' ) ) { exit; }

final class ISTPNCHAT_Admin {
    public static function menu() {
        add_menu_page( 'ISTPNCHAT', 'ISTPNCHAT', 'manage_options', 'istpnchat', array( __CLASS__, 'page' ), 'dashicons-format-chat', 58 );
    }
    public static function save() {
        if ( ! current_user_can( 'manage_options' ) ) { wp_die( 'Acceso denegado.' ); }
        check_admin_referer( 'istpnchat_local_save' );
        $greeting = sanitize_textarea_field( wp_unslash( $_POST['welcome'] ?? '' ) );
        if ( '' === trim( $greeting ) ) { $greeting = istpnchat_local_defaults()['welcome']; }
        $settings = array(
            'public_enabled' => empty( $_POST['public_enabled'] ) ? 0 : 1,
            'auto_sync' => empty( $_POST['auto_sync'] ) ? 0 : 1,
            'welcome' => substr( $greeting, 0, 900 ),
            'accent' => sanitize_hex_color( wp_unslash( $_POST['accent'] ?? '' ) ) ?: '#1262ba',
            'rate_limit' => max( 20, min( 500, absint( $_POST['rate_limit'] ?? 90 ) ) ),
        );
        update_option( 'istpnchat_local_settings', $settings, false );
        wp_safe_redirect( admin_url( 'admin.php?page=istpnchat&saved=1' ) );
        exit;
    }
    public static function sync() {
        if ( ! current_user_can( 'manage_options' ) ) { wp_die( 'Acceso denegado.' ); }
        check_admin_referer( 'istpnchat_local_sync' );
        $result = ISTPNCHAT_Knowledge::sync();
        if ( is_wp_error( $result ) ) {
            update_option( 'istpnchat_local_sync_error', $result->get_error_message(), false );
            wp_safe_redirect( admin_url( 'admin.php?page=istpnchat&sync=error' ) );
        } else {
            delete_option( 'istpnchat_local_sync_error' );
            wp_safe_redirect( admin_url( 'admin.php?page=istpnchat&sync=ok' ) );
        }
        exit;
    }
    public static function page() {
        if ( ! current_user_can( 'manage_options' ) ) { return; }
        $settings = istpnchat_local_settings();
        $data = ISTPNCHAT_Knowledge::current();
        $meta = get_option( ISTPNCHAT_Knowledge::META, array() );
        $trial = null; $trial_q = '';
        if ( isset( $_POST['istpnchat_trial'] ) ) {
            check_admin_referer( 'istpnchat_local_test' );
            $trial_q = sanitize_text_field( wp_unslash( $_POST['test_question'] ?? '' ) );
            if ( $trial_q ) { $trial = ISTPNCHAT_Search::answer( $trial_q, $data ); }
        }
        ?>
        <div class="wrap" style="max-width:1040px">
            <h1>ISTPNCHAT <small style="font-size:13px;color:#64748b">v<?php echo esc_html( ISTPNCHAT_VERSION ); ?> · Sin API de pago</small></h1>
            <p>Asistente institucional que responde <strong>exclusivamente</strong> con la base <code>CHATISTPN/respuestas.json</code> del repositorio GitHub. No utiliza OpenAI, Cloudflare Workers AI ni servicios de IA externos.</p>
            <?php if ( isset( $_GET['saved'] ) ) : ?><div class="notice notice-success is-dismissible"><p>Configuración guardada.</p></div><?php endif; ?>
            <?php if ( isset( $_GET['sync'] ) && 'ok' === $_GET['sync'] ) : ?><div class="notice notice-success is-dismissible"><p>Base de respuestas sincronizada desde GitHub.</p></div><?php endif; ?>
            <?php if ( isset( $_GET['sync'] ) && 'error' === $_GET['sync'] ) : ?><div class="notice notice-warning"><p>No se pudo sincronizar GitHub. <strong>Se mantiene la base anterior.</strong> <?php echo esc_html( (string) get_option( 'istpnchat_local_sync_error', '' ) ); ?></p></div><?php endif; ?>
            <div style="background:#fff;border:1px solid #dcdcde;padding:17px 20px;margin:20px 0;border-radius:9px">
                <h2 style="margin-top:0">Base de conocimientos</h2>
                <p><strong><?php echo esc_html( number_format_i18n( count( $data['respuestas'] ?? array() ) ) ); ?> respuestas</strong> ·
                   <strong><?php echo esc_html( number_format_i18n( $meta['questions'] ?? 964 ) ); ?> preguntas alternativas</strong> ·
                   Versión JSON: <strong><?php echo esc_html( (string) ( $data['version'] ?? 'sin versión' ) ); ?></strong></p>
                <p>Origen: <?php echo esc_html( (string) ( $meta['source'] ?? 'Respaldo incluido' ) ); ?> · Última carga: <?php echo esc_html( (string) ( $meta['updated'] ?? 'No registrada' ) ); ?> (hora del sitio).</p>
                <p><a href="https://github.com/mobatfb/archmoba-dev/blob/main/CHATISTPN/respuestas.json" target="_blank" rel="noopener noreferrer">Ver JSON en GitHub</a></p>
                <?php $err = get_option( 'istpnchat_local_sync_error', '' ); if ( $err ) : ?><p style="color:#b45309">Último problema de sincronización: <?php echo esc_html( (string) $err ); ?></p><?php endif; ?>
                <form action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>" method="post">
                    <input type="hidden" name="action" value="istpnchat_local_sync"/>
                    <?php wp_nonce_field( 'istpnchat_local_sync' ); ?>
                    <?php submit_button( 'Actualizar respuestas desde GitHub', 'secondary', 'submit', false ); ?>
                </form>
                <p class="description">La sincronización automática se ejecuta cada hora cuando WordPress procesa tareas programadas; no consulta GitHub por cada visitante. Si falla, usa la última copia válida.</p>
            </div>
            <div style="background:#fff;border:1px solid #dcdcde;padding:17px 20px;margin-bottom:20px;border-radius:9px">
                <h2 style="margin-top:0">Configuración y publicación</h2>
                <form action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>" method="post">
                    <input type="hidden" name="action" value="istpnchat_local_save"/>
                    <?php wp_nonce_field( 'istpnchat_local_save' ); ?>
                    <table class="form-table" role="presentation">
                        <tr><th scope="row">Visibilidad del chat</th><td>
                            <label><input type="checkbox" name="public_enabled" value="1" <?php checked( ! empty( $settings['public_enabled'] ) ); ?> /> Mostrar a todos los visitantes</label>
                            <p class="description">Desmarcado: solo lo verán administradores autenticados, para realizar pruebas.</p>
                        </td></tr>
                        <tr><th scope="row">Actualizar automáticamente</th><td>
                            <label><input type="checkbox" name="auto_sync" value="1" <?php checked( ! empty( $settings['auto_sync'] ) ); ?> /> Leer actualizaciones del JSON en GitHub</label>
                        </td></tr>
                        <tr><th scope="row"><label for="istpnchat-welcome">Mensaje de bienvenida</label></th><td>
                            <textarea id="istpnchat-welcome" name="welcome" rows="3" class="large-text" maxlength="900"><?php echo esc_textarea( $settings['welcome'] ); ?></textarea>
                        </td></tr>
                        <tr><th scope="row"><label for="istpnchat-accent">Color principal</label></th><td>
                            <input type="color" id="istpnchat-accent" name="accent" value="<?php echo esc_attr( sanitize_hex_color( $settings['accent'] ) ?: '#1262ba' ); ?>" />
                        </td></tr>
                        <tr><th scope="row"><label for="istpnchat-rate">Consultas por visitante</label></th><td>
                            <input type="number" id="istpnchat-rate" name="rate_limit" min="20" max="500" value="<?php echo esc_attr( $settings['rate_limit'] ); ?>" /> cada 10 minutos
                            <p class="description">Control básico de abuso; puede afectar conexiones compartidas.</p>
                        </td></tr>
                    </table>
                    <?php submit_button( 'Guardar configuración' ); ?>
                </form>
            </div>
            <div style="background:#fff;border:1px solid #dcdcde;padding:17px 20px;margin-bottom:20px;border-radius:9px">
                <h2 style="margin-top:0">Probar una pregunta sin gastar tokens</h2>
                <form method="post" action="<?php echo esc_url( admin_url( 'admin.php?page=istpnchat' ) ); ?>">
                    <?php wp_nonce_field( 'istpnchat_local_test' ); ?>
                    <input type="hidden" name="istpnchat_trial" value="1" />
                    <input type="text" name="test_question" style="width:min(720px,100%)" maxlength="500" value="<?php echo esc_attr( $trial_q ?: '¿Cuántas carreras tiene el ISTPN?' ); ?>" />
                    <?php submit_button( 'Probar respuesta', 'secondary', 'submit', false ); ?>
                </form>
                <?php if ( $trial ) : ?>
                    <div style="margin-top:17px;padding:14px;background:#eef4fc;white-space:pre-wrap;line-height:1.6"><?php echo esc_html( $trial['respuesta'] ); ?></div>
                    <?php if ( ! empty( $trial['fuentes'] ) ) : ?>
                        <p><strong>Enlaces de la respuesta</strong></p>
                        <ol><?php foreach ( $trial['fuentes'] as $link ) : ?>
                            <li><a href="<?php echo esc_url( $link['url'] ); ?>" target="_blank" rel="noopener noreferrer"><?php echo esc_html( $link['titulo'] ); ?></a></li>
                        <?php endforeach; ?></ol>
                    <?php endif; ?>
                <?php endif; ?>
            </div>
            <p class="description"><strong>Nota:</strong> esta versión es un buscador institucional conversacional, no un modelo generativo. No puede garantizar que toda la web o todos los PDF hayan sido revisados. No almacena conversaciones.</p>
        </div>
        <?php
    }
}
