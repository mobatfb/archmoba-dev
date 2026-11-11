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

    /**
     * Resuelve referencias breves al tema anterior sin enviar mensajes a terceros.
     * El contexto recibido del cliente es solo un ID, validado contra la base oficial.
     */
    private static function follow_up_careers( $question, $context_id, $records ) {
        $norm = self::normalize( $question );
        $is_other = (bool) preg_match( '/\b(otra|otras|otro|otros|demas|restantes)\b/', $norm );
        if ( ! $is_other || str_word_count( $norm ) > 12 ) { return null; }
        // No se debe aplicar el seguimiento a temas distintos de la oferta academica.
        $allowed = array( 'oferta', 'numero-carreras-istpn', 'carreras-presencial', 'carreras-online', 'carreras-hibridas' );
        $previous = self::match_id( $records, $context_id );
        if ( ! $previous || ( strpos( $context_id, 'carrera-' ) !== 0 && ! in_array( $context_id, $allowed, true ) ) ) { return null; }

        // Estos ID son los de las ocho fichas individuales, no los de grupos o sumarios.
        $ids = array(
            'carrera-acondicionamiento', 'carrera-analisis', 'carrera-ciberdelito',
            'carrera-criminalistica', 'carrera-financieros', 'carrera-transito',
            'carrera-procesamiento', 'carrera-seguridad',
        );
        $found = array();
        foreach ( $ids as $id ) {
            if ( $id === $context_id ) { continue; }
            $record = self::match_id( $records, $id );
            if ( ! $record || ! ISTPNCHAT_Knowledge::trusted_url( $record['fuente'] ?? '' ) ) { continue; }
            $name = preg_replace( '/^Carrera de /u', '', trim( (string) ( $record['titulo'] ?? '' ) ) );
            if ( ! $name ) { continue; }
            $detail = (string) ( $record['respuesta'] ?? '' );
            $mode = '';
            if ( preg_match( '/modalidad\s*[,;:]?\s*(Presencial|En l[ií]nea|H[ií]brida)/iu', $detail, $match ) ) {
                $mode = trim( $match[1] );
            }
            $found[] = array( 'nombre' => $name, 'modalidad' => $mode, 'url' => $record['fuente'] );
        }
        if ( ! $found ) { return null; }
        $is_one = $context_id !== 'oferta' && $context_id !== 'numero-carreras-istpn' && strpos( $context_id, 'carrera-' ) === 0;
        $intro = $is_one ? 'Además de ' . preg_replace( '/^Carrera de /u', '', $previous['titulo'] ?? 'la anterior' ) . ', el ISTPN publica estas otras ' . count( $found ) . ' carreras:' : 'Estas son las carreras que el ISTPN publica en su portal:';
        $lines = array( $intro, '' );
        $sources = array();
        foreach ( $found as $i => $course ) {
            $lines[] = ( $i + 1 ) . '. ' . $course['nombre'] . ( $course['modalidad'] ? ' (' . $course['modalidad'] . ')' : '' );
            $sources[] = array( 'titulo' => $course['nombre'], 'url' => $course['url'] );
        }
        $lines[] = '';
        $lines[] = 'Selecciona cualquiera de sus enlaces para conocer más. La oferta publicada no confirma que las inscripciones estén abiertas.';
        return array( 'respuesta' => implode( "\n", $lines ), 'fuentes' => $sources, 'modo' => 'seguimiento', 'tema' => 'Oferta académica', 'contexto' => 'oferta' );
    }

    private static function short_career_reference( $question, $context_id, $records ) {
        if ( strpos( $context_id, 'carrera-' ) !== 0 ) { return null; }
        $record = self::match_id( $records, $context_id );
        if ( ! $record || ! ISTPNCHAT_Knowledge::trusted_url( $record['fuente'] ?? '' ) ) { return null; }
        $norm = self::normalize( $question );
        if ( str_word_count( $norm ) > 9 ) { return null; }
        // Ej.: despues de Criminalistica: «¿Y cuanto dura?» o «¿Y su modalidad?».
        if ( ! preg_match( '/\b(dura|duracion|anos|tiempo|creditos|modalidad|presencial|virtual|hibrida|titulo|titulacion)\b/', $norm ) ) { return null; }
        if ( preg_match( '/\b(carrera|criminalistica|ciberdelito|analisis|financieros|seguridad|transito|acondicionamiento|procesamiento)\b/', $norm ) ) { return null; }
        $name = preg_replace( '/^Carrera de /u', '', (string) ( $record['titulo'] ?? 'Carrera' ) );
        return array( 'respuesta' => 'Sobre ' . $name . ': ' . (string) $record['respuesta'],
            'fuentes' => array( array( 'titulo' => $name, 'url' => $record['fuente'] ) ),
            'modo' => 'seguimiento', 'tema' => 'Oferta académica', 'contexto' => $context_id );
    }

    public static function answer( $question, $data, $context_id = '' ) {
        $question = trim( (string) $question );
        if ( strlen( $question ) > 3000 ) { $question = substr( $question, 0, 3000 ); }
        if ( '' === $question ) { return array( 'respuesta' => 'Escribe una pregunta sobre el ISTPN.', 'fuentes' => array(), 'modo' => 'local' ); }
        if ( self::out_of_scope( $question ) ) { return array( 'respuesta' => 'Soy ISTPNCHAT. Solo atiendo consultas sobre la informacion institucional publicada en el portal del ISTPN.', 'fuentes' => array(), 'modo' => 'rechazo' ); }
        if ( in_array( self::normalize( $question ), array( 'hola','buenas','buenos dias','buenas tardes','saludos','hey','gracias' ), true ) ) {
            return array( 'respuesta' => '¡Hola! Soy ISTPNCHAT. Puedes consultarme sobre carreras, modalidades, admisiones, normativa, noticias y servicios del ISTPN.', 'fuentes' => array(), 'modo' => 'local' );
        }
        $records = is_array( $data ) ? ( $data['respuestas'] ?? array() ) : array();
        if ( ! is_array( $records ) || ! $records ) { return array( 'respuesta' => 'La base institucional no esta disponible. Intentalo nuevamente.', 'fuentes' => array(), 'modo' => 'sin_datos' ); }
        // El usuario puede decir «otras» sin repetir «carreras» ni «Criminalística».
        // Solo se utiliza el ID de la ultima respuesta, nunca texto arbitrario del cliente.
        $context_id = is_string( $context_id ) && strlen( $context_id ) <= 80 && preg_match( '/^[a-z0-9-]+$/', $context_id ) ? $context_id : '';
        if ( $context_id ) {
            $follow = self::follow_up_careers( $question, $context_id, $records );
            if ( null !== $follow ) { return $follow; }
            $follow = self::short_career_reference( $question, $context_id, $records );
            if ( null !== $follow ) { return $follow; }
        }
        if ( preg_match( '/^(?:y )?(?:las |los )?(?:otra|otras|otro|otros|demas|restantes)(?: carreras| opciones)?$/', self::normalize( $question ) ) ) {
            return array( 'respuesta' => '¿Te refieres a otras carreras del ISTPN? Pregúntame por las carreras disponibles o consulta primero una carrera en particular.', 'fuentes' => array(), 'modo' => 'aclaracion' );
        }
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
        return array( 'respuesta' => $body, 'fuentes' => $sources, 'modo' => 'local', 'tema' => (string) ( $item['tema'] ?? '' ), 'contexto' => (string) ( $item['id'] ?? '' ) );
    }
}
