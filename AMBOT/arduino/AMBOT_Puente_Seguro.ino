/*
 * ARCHMOBA AMBOT - Puente Arduino inicial SEGURO (USB serial 115200).
 * No define pines ni acciona motores: faltan placa, drivers y sensores reales.
 * Responde a PING, STOP y publica telemetria sin sensores calibrados.
 * Python RECHAZA activar motores cuando distancia/bateria son -1.
 * Un firmware futuro con motores DEBE implementar watchdog, parada fisica
 * independiente, limites de corriente, movimiento acotado y anticolision.
 */
unsigned long lastTelemetry = 0;
const unsigned long PERIOD_MS = 250;
char lineBuffer[64];
byte used = 0;
void stopAllMotors() {
  // Bloqueo intencional: no hay pines de control asignados.
}
void setup() {
  Serial.begin(115200);
  stopAllMotors();
}
void printTelemetry() {
  Serial.println(F("{\"ready\":true,\"distance_cm\":-1,\"battery_pct\":-1,\"touch\":false}"));
}
void acceptLine() {
  lineBuffer[used] = '\0';
  if (strcmp(lineBuffer,"STOP")==0) {
    stopAllMotors();
    Serial.println(F("{\"ready\":true,\"distance_cm\":-1,\"battery_pct\":-1}"));
  } else if (strcmp(lineBuffer,"PING")==0) {
    printTelemetry();
  } else {
    // Se IGNORAN todas las ordenes MOVE por seguridad hasta construir
    // un controlador especifico al modelo de Arduino y motores.
    stopAllMotors();
  }
  used=0;
}
void loop() {
  while (Serial.available()) {
    char ch=(char)Serial.read();
    if (ch=='\n') {
      acceptLine();
    } else if (ch!='\r' && used<sizeof(lineBuffer)-1) {
      lineBuffer[used++]=ch;
    } else if (used>=sizeof(lineBuffer)-1) {
      used=0;
      stopAllMotors();
    }
  }
  const unsigned long now=millis();
  if (now-lastTelemetry>=PERIOD_MS) {
    lastTelemetry=now;
    printTelemetry();
  }
}
