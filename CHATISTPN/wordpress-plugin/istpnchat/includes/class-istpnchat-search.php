<?php
/** Busqueda local determinista sobre respuestas.json. Ninguna llamada de IA. */
if ( ! defined( 'ABSPATH' ) ) { exit; }

final class ISTPNCHAT_Search {
    private static $stop = array();
    private static $aliases = array(
        'carreras' => 'carrera', 'cursos' => 'curso', 'estudios' => 'estudio',
        'modalidades' => 'modalidad', 'requisitos' => 'requisito',
        'inscripciones' => 'inscripcion', 'admisiones' => 'admision',
        'reglamentos' => 'reglamento', 'noticias' => 'noticia',
        'documentos' => 'documento', 'estudiantes' => 'estudiante',
        'graduados' => 'graduado', 'matriculas' => 'matricula',
        'telefonos' => 'telefono', 'tramites' => 'tramite',
        'docentes' => 'docente', 'calificaciones' => 'calificacion',
        'hibridas' => 'hibrida', 'virtuales' => 'virtual',
    );

    public static function normalize( $str ) {
        $str = strtolower( remove_accents( (string) $str ) );
        $str = preg_replace( '/[^a-z0-9 ]+/', ' ', $str );
        return trim( preg_replace( '/\s+/', ' ', (string) $str ) );
    }

    public static function tokens( $str ) {
        if ( ! self::$stop ) {
            self::$stop = array_fill_keys( explode( ' ', 'a al algo algunas algunos ante como con cual cuales cuando de del desde donde el ella ellas ellos en entre era es esa esas ese esos esta estas este estos hacia hay la las le les lo los mas me mi mis muy no o para pero por porque que quien quienes se sea ser si sin sobre son su sus te tiene tienen tu un una unas unos y ya puedo podrian quiero saber necesito dime favor informacion instituto istpn isupol chat' ), true );
        }
        $out = array();
        foreach ( explode( ' ', self::normalize( $str ) ) as $w ) {
            if ( strlen( $w ) <= 2 || isset( self::$stop[ $w ] ) ) { continue; }
            $w = self::$aliases[ $w ] ?? $w;
            $out[ $w ] = true;
        }
        return $out;
    }

    public static function out_of_scope( $q ) {
        $q = self::normalize( $q );
        foreach ( array(
            '/\b(olvida|ignora) (tus|las|todas|anteriores) (reglas|instrucciones)/',
            '/\b(actua como|eres ahora|nuevo rol|system prompt|developer prompt)/',
            '/\b(genera|crea|escribe|hazme|programa|desarrolla)\b.{0,50}\b(codigo|script|python|javascript|java|php|programa informatico|aplicacion movil|software)\b/',
            '/\b(receta|horoscopo|apuestas|pelicula|futbol mundial)\b/',
        ) as $pattern ) {
            if ( preg_match( $pattern, $q ) ) { return true; }
        }
        return false;
    }

    private static function match_id( $records, $id ) {
        foreach ( $records as $r ) { if ( ( $r['id'] ?? '' ) === $id ) { return $r; } }
        return null;
    }

    public static function search( $q, $records ) {
        $norm = self::normalize( $q );
        $words = self::tokens( $q );
        if ( ! $words ) { return array(); }
        // Preguntas numericas requieren una respuesta que contenga la cantidad.
        if ( preg_match( '/\b(cuantas|cuantos|numero|total|cantidad)\b/', $norm ) && preg_match( '/\b(carrera|carreras)\b/', $norm ) ) {
            $id = 'numero-carreras-istpn';
            if ( preg_match( '/\b(presencial|presenciales)\b/', $norm ) && ! preg_match( '/\b(hibrid|linea|virtual)/', $norm ) ) { $id = 'carreras-presencial'; }
            if ( preg_match( '/\b(virtual|virtuales|linea|online)\b/', $norm ) && ! preg_match( '/\b(hibrid|presencial)/', $norm ) ) { $id = 'carreras-online'; }
            if ( preg_match( '/\b(hibrida|hibridas|hibrido|hibridos)\b/', $norm ) && ! preg_match( '/\b(presencial|linea|virtual)/', $norm ) ) { $id = 'carreras-hibridas'; }
            $chosen = self::match_id( $records, $id );
            if ( $chosen ) { return array( array( 99.0, $chosen ) ); }
        }
        $docs = array(); $df = array(); $total = max( 1, count( $records ) );
        foreach ( $records as $item ) {
            $parts = implode( ' ', (array) ( $item['preguntas'] ?? array() ) ) . ' ' . (string) ( $item['titulo'] ?? '' ) . ' ';
            $parts .= implode( ' ', (array) ( $item['etiquetas'] ?? array() ) ) . ' ' . substr( (string) ( $item['respuesta'] ?? '' ), 0, 1500 );
            $terms = self::tokens( $parts );
            $docs[] = $terms;
            foreach ( $terms as $word => $_ ) { $df[ $word ] = ( $df[ $word ] ?? 0 ) + 1; }
        }
        $scored = array(); $q_count = count( $words );
        foreach ( $records as $i => $item ) {
            $terms = $docs[ $i ]; $common = array_intersect_key( $words, $terms );
            if ( ! $common ) { continue; }
            $common_count = count( $common );
            $weight = 0;
            foreach ( $common as $word => $_ ) { $weight += 1.0 + min( 2.0, pow( $total / ( 1 + ( $df[ $word ] ?? 1 ) ), .35 ) ); }
            $coverage = $common_count / $q_count;
            $score = $weight / max( 2.2, pow( $q_count, .55 ) ) + $coverage * 2.6;
            $score += count( array_intersect_key( $words, self::tokens( $item['titulo'] ?? '' ) ) ) * .65;
            foreach ( $item['preguntas'] ?? array() as $question ) {
                $pn = self::normalize( $question );
                if ( $norm === $pn ) { $score += 40.0; break; }
                $qt = self::tokens( $question );
                $share = count( array_intersect_key( $words, $qt ) );
                if ( $share >= 2 ) { $score += $share / max( $q_count, count( $qt ), 1 ) * 3.2; }
                if ( strlen( $norm ) > 9 && strpos( $pn, $norm ) !== false ) { $score += 6.0; }
            }
            if ( ( $item['origen'] ?? '' ) === 'verificado' ) { $score += .6; }
            if ( strpos( (string) ( $item['alcance_verificacion'] ?? '' ), 'titulo_y_enlace' ) === 0 && ! preg_match( '/\b(donde|descargar|consultar|documento|reglamento|resolucion|normativa|manual|oficio)\b/', $norm ) ) { $score -= 5; }
            if ( $q_count === 1 ) { $score -= .25; }
            if ( $score >= ( $q_count <= 1 ? 3.1 : 4.0 ) && ( $coverage >= .5 || $common_count >= 2 ) ) {
                $scored[] = array( $score, $item );
            }
        }
        usort( $scored, function( $a, $b ) {
            if ( $a[0] === $b[0] ) { return strcmp( (string) $a[1]['id'], (string) $b[1]['id'] ); }
            return $a[0] > $b[0] ? -1 : 1;
        } );
        return array_slice( $scored, 0, 4 );
    }

    private static function source_titles( $records ) {
        $map = array();
        foreach ( $records as $record ) {
            $url = $record['fuente'] ?? '';
            $title = trim( (string) ( $record['titulo'] ?? '' ) );
            if ( ! ISTPNCHAT_Knowledge::trusted_url( $url ) || ! $title ) { continue; }
            if ( ! isset( $map[ $url ] ) || strpos( (string) ( $record['id'] ?? '' ), 'carrera-' ) === 0 ) {
                $map[ $url ] = preg_replace( '/^Carrera de /u', '', $title );
            }
        }
        return $map;
    }

    public static function answer( $question, $data ) {
        $question = trim( (string) $question );
        if ( strlen( $question ) > 3000 ) { $question = substr( $question, 0, 3000 ); }
        if ( '' === $question ) { return array( 'respuesta' => 'Escribe una pregunta sobre el ISTPN.', 'fuentes' => array(), 'modo' => 'local' ); }
        if ( self::out_of_scope( $question ) ) { return array( 'respuesta' => 'Soy ISTPNCHAT. Solo atiendo consultas sobre la informacion institucional publicada en el portal del ISTPN.', 'fuentes' => array(), 'modo' => 'rechazo' ); }
        if ( in_array( self::normalize( $question ), array( 'hola','buenas','buenos dias','buenas tardes','saludos','hey','gracias' ), true ) ) {
            return array( 'respuesta' => '¡Hola! Soy ISTPNCHAT. Puedes consultarme sobre carreras, modalidades, admisiones, normativa, noticias y servicios del ISTPN.', 'fuentes' => array(), 'modo' => 'local' );
        }
        $records = is_array( $data ) ? ( $data['respuestas'] ?? array() ) : array();
        if ( ! is_array( $records ) || ! $records ) { return array( 'respuesta' => 'La base institucional no esta disponible. Intentalo nuevamente.', 'fuentes' => array(), 'modo' => 'sin_datos' ); }
        $matches = self::search( $question, $records );
        if ( ! $matches ) { return array(
            'respuesta' => 'No encontre informacion suficiente en la base institucional. Puedes consultar el portal oficial del ISTPN.',
            'fuentes' => array( array( 'titulo' => 'Portal del ISTPN', 'url' => 'https://home.isupol.edu.ec/' ) ),
            'modo' => 'sin_resultado',
        ); }
        $best = $matches[0][0]; $item = $matches[0][1];
        $body = (string) $item['respuesta'];
        if ( ! empty( $item['historico'] ) ) { $body .= "\n\nAviso: publicacion historica. Verifica si existe una convocatoria o actualizacion vigente."; }
        // Preguntas sobre subgrupos de carreras muestran ademas el numero.
        $qnorm = self::normalize( $question );
        if ( preg_match( '/\b(cuantas|cuantos|numero|cantidad|total)\b/', $qnorm ) ) {
            if ( ( $item['id'] ?? '' ) === 'carreras-presencial' ) { $body = "Son 2 carreras presenciales.\n\n" . $body; }
            if ( ( $item['id'] ?? '' ) === 'carreras-online' ) { $body = "Son 4 carreras en linea.\n\n" . $body; }
            if ( ( $item['id'] ?? '' ) === 'carreras-hibridas' ) { $body = "Son 2 carreras hibridas.\n\n" . $body; }
        }
        $titles = self::source_titles( $records );
        $sources = array(); $seen = array();
        $append = function( $record ) use ( &$sources, &$seen, $titles ) {
            $urls = $record['fuentes'] ?? array();
            if ( ! $urls && ! empty( $record['fuente'] ) ) { $urls = array( $record['fuente'] ); }
            foreach ( (array) $urls as $url ) {
                if ( ! ISTPNCHAT_Knowledge::trusted_url( $url ) || isset( $seen[ $url ] ) ) { continue; }
                $labels = $record['titulos_fuentes'] ?? array();
                $label = is_array( $labels ) && ! empty( $labels[ $url ] ) ? $labels[ $url ] : ( $titles[ $url ] ?? ( $record['titulo'] ?? 'Fuente institucional' ) );
                $sources[] = array( 'titulo' => (string) $label, 'url' => $url );
                $seen[ $url ] = true;
                if ( count( $sources ) >= 12 ) { break; }
            }
        };
        $append( $item );
        if ( count( $sources ) < 3 ) {
            foreach ( array_slice( $matches, 1 ) as $other ) {
                if ( $other[0] < $best * .85 ) { continue; }
                $append( $other[1] );
                if ( count( $sources ) >= 3 ) { break; }
            }
        }
        return array( 'respuesta' => $body, 'fuentes' => $sources, 'modo' => 'local', 'tema' => (string) ( $item['tema'] ?? '' ) );
    }
}
