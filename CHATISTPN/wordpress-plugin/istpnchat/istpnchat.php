<?php
/**
 * Plugin Name: ISTPNCHAT - Asistente institucional
 * Description: Chat institucional sobre carreras, admisiones, normativa y servicios del ISTPN. Respuestas con enlaces oficiales y panel de administracion.
 * Version: 2.0.2
 * Requires at least: 6.0
 * Requires PHP: 7.4
 * Author: Proyecto ISTPNCHAT
 * Text Domain: istpnchat
 */
if ( ! defined( 'ABSPATH' ) ) { exit; }

define( 'ISTPNCHAT_VERSION', '2.0.2' );
define( 'ISTPNCHAT_PATH', plugin_dir_path( __FILE__ ) );
define( 'ISTPNCHAT_URL', plugin_dir_url( __FILE__ ) );
require_once ISTPNCHAT_PATH . 'includes/class-istpnchat-knowledge.php';
require_once ISTPNCHAT_PATH . 'includes/class-istpnchat-search.php';
require_once ISTPNCHAT_PATH . 'includes/class-istpnchat-admin.php';

function istpnchat_local_defaults() {
    return array(
        'public_enabled' => 0, // Arranca en modo de prueba, solo administradores.
        'welcome' => '¡Hola! Soy ISTPNCHAT, asistente virtual del Instituto Superior Tecnológico Policía Nacional. Puedo ayudarte con carreras, admisiones, normativa y servicios del portal.',
        'accent' => '#1262ba',
        'auto_sync' => 1,
        'rate_limit' => 90, // Maximo por IP anonimizada en diez minutos.
    );
}
function istpnchat_local_settings() {
    $settings = get_option( 'istpnchat_local_settings', array() );
    return wp_parse_args( is_array( $settings ) ? $settings : array(), istpnchat_local_defaults() );
}
function istpnchat_local_schedule() {
    if ( ! wp_next_scheduled( 'istpnchat_local_sync_event' ) ) {
        wp_schedule_event( time() + HOUR_IN_SECONDS, 'hourly', 'istpnchat_local_sync_event' );
    }
}
function istpnchat_local_install() {
    if ( false === get_option( 'istpnchat_local_settings', false ) ) {
        $default = istpnchat_local_defaults();
        // Se conserva el saludo y color de versiones anteriores, nunca la clave API.
        $old = get_option( 'istpnchat_settings', array() );
        if ( is_array( $old ) ) {
            if ( ! empty( $old['welcome'] ) && is_string( $old['welcome'] ) ) { $default['welcome'] = $old['welcome']; }
            if ( ! empty( $old['accent'] ) && sanitize_hex_color( $old['accent'] ) ) { $default['accent'] = $old['accent']; }
        }
        add_option( 'istpnchat_local_settings', $default, '', false );
    }
    ISTPNCHAT_Knowledge::seed_if_empty();
    istpnchat_local_schedule();
    // Las acciones antiguas de limpieza no se necesitan en esta version sin IA.
    wp_clear_scheduled_hook( 'istpnchat_cleanup' );
    update_option( 'istpnchat_local_version', ISTPNCHAT_VERSION, false );
}
register_activation_hook( __FILE__, 'istpnchat_local_install' );
add_action( 'plugins_loaded', function() {
    if ( get_option( 'istpnchat_local_version', '' ) !== ISTPNCHAT_VERSION ) { istpnchat_local_install(); }
} );
register_deactivation_hook( __FILE__, function() { wp_clear_scheduled_hook( 'istpnchat_local_sync_event' ); } );
add_action( 'istpnchat_local_sync_event', function() {
    if ( empty( istpnchat_local_settings()['auto_sync'] ) ) { return; }
    $result = ISTPNCHAT_Knowledge::sync();
    if ( is_wp_error( $result ) ) { update_option( 'istpnchat_local_sync_error', $result->get_error_message(), false ); }
    else { delete_option( 'istpnchat_local_sync_error' ); }
} );

function istpnchat_local_visible() {
    $settings = istpnchat_local_settings();
    return ! empty( $settings['public_enabled'] ) || current_user_can( 'manage_options' );
}

add_action( 'rest_api_init', function() {
    register_rest_route( 'istpnchat/v2', '/chat', array(
        'methods' => 'POST',
        'callback' => 'istpnchat_local_rest_chat',
        'permission_callback' => function() { return istpnchat_local_visible(); },
        'args' => array(
            'pregunta' => array( 'required' => true, 'type' => 'string' ),
            'contexto' => array( 'required' => false, 'type' => 'string' ),
        ),
    ) );
} );

function istpnchat_local_rest_chat( $request ) {
    $question = $request->get_param( 'pregunta' );
    if ( ! is_string( $question ) || '' === trim( $question ) || strlen( $question ) > 2000 ) {
        return new WP_Error( 'istpnchat_invalid_question', 'Escribe una pregunta de hasta 500 caracteres.', array( 'status' => 400 ) );
    }
    if ( ! current_user_can( 'manage_options' ) ) {
        // No se conserva la IP; solo un hash irreversible de duracion temporal.
        $address = (string) ( $_SERVER['REMOTE_ADDR'] ?? 'unknown' );
        $key = 'istpnchat_rate_' . substr( hash_hmac( 'sha256', $address, wp_salt( 'auth' ) ), 0, 24 );
        $used = (int) get_transient( $key );
        if ( $used >= (int) istpnchat_local_settings()['rate_limit'] ) {
            return new WP_Error( 'istpnchat_rate_limit', 'Demasiadas consultas en este momento. Intenta nuevamente mas tarde.', array( 'status' => 429 ) );
        }
        set_transient( $key, $used + 1, 10 * MINUTE_IN_SECONDS );
    }
    $question = sanitize_text_field( $question );
    $contexto = $request->get_param( 'contexto' );
    $contexto = is_string( $contexto ) && strlen( $contexto ) <= 80 ? sanitize_text_field( $contexto ) : '';
    $payload = ISTPNCHAT_Search::answer( $question, ISTPNCHAT_Knowledge::current(), $contexto );
    $response = rest_ensure_response( $payload );
    $response->header( 'Cache-Control', 'no-store' );
    return $response;
}

function istpnchat_local_enqueue() {
    if ( ! istpnchat_local_visible() ) { return; }
    wp_enqueue_style( 'istpnchat-widget', ISTPNCHAT_URL . 'assets/widget.css', array(), ISTPNCHAT_VERSION );
    wp_enqueue_script( 'istpnchat-widget', ISTPNCHAT_URL . 'assets/widget.js', array(), ISTPNCHAT_VERSION, true );
    $s = istpnchat_local_settings();
    $config = array(
        'endpoint' => esc_url_raw( rest_url( 'istpnchat/v2/chat' ) ),
        'nonce' => is_user_logged_in() ? wp_create_nonce( 'wp_rest' ) : '',
        'welcome' => (string) $s['welcome'],
        'preview' => empty( $s['public_enabled'] ),
        'accent' => sanitize_hex_color( $s['accent'] ) ?: '#1262ba',
    );
    wp_add_inline_script( 'istpnchat-widget', 'window.ISTPNCHAT_CONFIG = ' . wp_json_encode( $config, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT ) . ';', 'before' );
}
add_action( 'wp_enqueue_scripts', 'istpnchat_local_enqueue' );

function istpnchat_local_render() {
    if ( ! istpnchat_local_visible() ) { return; }
    ?>
    <div id="istpnchat-root" class="istpnchat-root" aria-label="ISTPNCHAT">
        <button type="button" class="istpnchat-launcher" aria-label="Abrir ISTPNCHAT" aria-controls="istpnchat-panel" aria-expanded="false">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11a8 8 0 0 1-8 8H7l-4 2v-7a8 8 0 1 1 18-3Z"/><path d="M8 11h8M8 15h5"/></svg>
            <span>ISTPNCHAT</span>
        </button>
        <section id="istpnchat-panel" class="istpnchat-panel" role="dialog" aria-modal="false" aria-label="Chat institucional ISTPN" hidden>
            <header class="istpnchat-header">
                <span class="istpnchat-avatar" aria-hidden="true">IST</span>
                <span class="istpnchat-heading"><strong>ISTPNCHAT</strong><small>Asistente institucional del ISTPN</small></span>
                <button type="button" class="istpnchat-close" aria-label="Cerrar ISTPNCHAT">&times;</button>
            </header>
            <div class="istpnchat-status">Información del portal oficial <?php if ( empty( istpnchat_local_settings()['public_enabled'] ) ) : ?><strong> · Modo de prueba</strong><?php endif; ?></div>
            <div class="istpnchat-messages" role="log" aria-live="polite" aria-relevant="additions text"></div>
            <div class="istpnchat-suggestions" aria-label="Preguntas sugeridas">
                <button type="button" data-question="¿Cuántas carreras tiene el ISTPN?">Carreras</button>
                <button type="button" data-question="¿Cuáles son las modalidades de estudio?">Modalidades</button>
                <button type="button" data-question="¿Dónde encuentro la normativa institucional?">Normativa</button>
            </div>
            <form class="istpnchat-form">
                <label for="istpnchat-input" class="istpnchat-sr-only">Escribe tu pregunta</label>
                <textarea id="istpnchat-input" rows="1" maxlength="500" placeholder="Escribe una pregunta sobre el ISTPN…" required></textarea>
                <button type="submit" class="istpnchat-send" aria-label="Enviar mensaje">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 14-8-4 16-4-7-6-1Z"/><path d="m11 13 8-9"/></svg>
                </button>
            </form>
        </section>
    </div>
    <?php
}
// El HTML debe existir antes de que se ejecute el JavaScript del pie.
add_action( 'wp_footer', 'istpnchat_local_render', 5 );

add_action( 'admin_menu', array( 'ISTPNCHAT_Admin', 'menu' ) );
add_action( 'admin_post_istpnchat_local_save', array( 'ISTPNCHAT_Admin', 'save' ) );
add_action( 'admin_post_istpnchat_local_sync', array( 'ISTPNCHAT_Admin', 'sync' ) );
