<?php
/** Fuente unica de conocimiento: JSON curado en GitHub, con respaldo incluido. */
if ( ! defined( 'ABSPATH' ) ) { exit; }

final class ISTPNCHAT_Knowledge {
    const SOURCE_URL = 'https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/CHATISTPN/respuestas.json';
    const OPTION = 'istpnchat_local_knowledge';
    const META = 'istpnchat_local_kb_meta';

    public static function trusted_url( $url ) {
        if ( ! is_string( $url ) || strlen( $url ) > 2000 ) { return false; }
        $parts = wp_parse_url( $url );
        if ( ! is_array( $parts ) || strtolower( $parts['scheme'] ?? '' ) !== 'https' ) { return false; }
        if ( isset( $parts['user'] ) || isset( $parts['pass'] ) || isset( $parts['port'] ) ) { return false; }
        $host = strtolower( (string) ( $parts['host'] ?? '' ) );
        return $host === 'isupol.edu.ec' || ( strlen( $host ) > strlen( '.isupol.edu.ec' ) && substr( $host, -strlen( '.isupol.edu.ec' ) ) === '.isupol.edu.ec' );
    }

    public static function validate( $value ) {
        if ( ! is_array( $value ) || empty( $value['respuestas'] ) || ! is_array( $value['respuestas'] ) ) { return false; }
        $items = $value['respuestas'];
        if ( count( $items ) > 12000 ) { return false; }
        $unique = array();
        foreach ( $items as $item ) {
            if ( ! is_array( $item ) || empty( $item['id'] ) || ! is_string( $item['id'] ) || isset( $unique[ $item['id'] ] ) ) { return false; }
            if ( empty( $item['respuesta'] ) || ! is_string( $item['respuesta'] ) || strlen( $item['respuesta'] ) > 25000 ) { return false; }
            if ( empty( $item['preguntas'] ) || ! is_array( $item['preguntas'] ) || count( $item['preguntas'] ) > 200 ) { return false; }
            if ( empty( $item['fuente'] ) || ! self::trusted_url( $item['fuente'] ) ) { return false; }
            foreach ( $item['fuentes'] ?? array() as $url ) {
                if ( ! self::trusted_url( $url ) ) { return false; }
            }
            $unique[ $item['id'] ] = true;
        }
        return true;
    }

    public static function bundled() {
        $path = ISTPNCHAT_PATH . 'data/respuestas.json';
        if ( ! is_readable( $path ) ) { return array(); }
        $raw = file_get_contents( $path ); // phpcs:ignore WordPress.WP.AlternativeFunctions.file_get_contents_file_get_contents
        $data = json_decode( (string) $raw, true );
        return self::validate( $data ) ? $data : array();
    }

    public static function current() {
        $data = get_option( self::OPTION, null );
        if ( self::validate( $data ) ) { return $data; }
        return self::bundled();
    }

    public static function write( $data, $origin ) {
        if ( ! self::validate( $data ) ) { return new WP_Error( 'istpnchat_invalid_json', 'El JSON no contiene respuestas institucionales validas.' ); }
        $count = count( $data['respuestas'] );
        $questions = 0;
        foreach ( $data['respuestas'] as $item ) { $questions += count( $item['preguntas'] ); }
        update_option( self::OPTION, $data, false );
        $meta = array(
            'source' => $origin,
            'version' => sanitize_text_field( (string) ( $data['version'] ?? 'sin version' ) ),
            'records' => $count,
            'questions' => $questions,
            'updated' => current_time( 'mysql' ),
        );
        update_option( self::META, $meta, false );
        return $meta;
    }

    public static function seed_if_empty() {
        $current = get_option( self::OPTION, null );
        if ( self::validate( $current ) ) { return; }
        $fallback = self::bundled();
        if ( $fallback ) { self::write( $fallback, 'Respaldo incluido en el plugin' ); }
    }

    public static function sync() {
        // Nunca se consulta OpenAI ni se descarga codigo: solo un JSON publico.
        $response = wp_safe_remote_get( self::SOURCE_URL, array(
            'timeout' => 15,
            'redirection' => 2,
            'limit_response_size' => 4 * 1024 * 1024,
            'headers' => array('Accept' => 'application/json', 'User-Agent' => 'ISTPNCHAT-WordPress/2.0'),
        ) );
        if ( is_wp_error( $response ) ) { return $response; }
        if ( 200 !== (int) wp_remote_retrieve_response_code( $response ) ) {
            return new WP_Error( 'istpnchat_network', 'GitHub no respondio con HTTP 200. El respaldo existente se mantiene.' );
        }
        $body = wp_remote_retrieve_body( $response );
        if ( ! is_string( $body ) || strlen( $body ) > 4 * 1024 * 1024 ) {
            return new WP_Error( 'istpnchat_size', 'La respuesta recibida excede el tamano permitido.' );
        }
        $data = json_decode( $body, true );
        if ( ! self::validate( $data ) ) {
            return new WP_Error( 'istpnchat_format', 'El JSON de GitHub es invalido; el respaldo anterior permanece activo.' );
        }
        return self::write( $data, 'GitHub - CHATISTPN/respuestas.json' );
    }
}
