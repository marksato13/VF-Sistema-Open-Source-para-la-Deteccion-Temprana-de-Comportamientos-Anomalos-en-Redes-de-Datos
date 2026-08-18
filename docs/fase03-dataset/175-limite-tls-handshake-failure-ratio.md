# Límite metodológico encontrado en `tls_handshake_failure_ratio_60s` (Tarea 4)

- **Fecha:** 2026-08-14
- **Autor:** Claude, investigación directa (no vía Codex) sobre el laboratorio real. No se abrió ninguna campaña oficial ni de calibración — todo lo descrito aquí son sondas manuales de diagnóstico, sin capturar PCAP/ledger formal.
- **Estado:** **NO RESUELTO — requiere decisión de diseño, no más reintentos técnicos.**

## Objetivo original

Cerrar la brecha de `tls_handshake_failure_ratio_60s` (constante en 0.0 en todo el dataset v2), generando una conexión TLS que Suricata registre como evento `tls` en EVE **sin** el campo `version` resuelto — la condición que `extract_multilayer_v2.py` (línea ~452: `tls_incomplete = not bool(tls_version)`) usa para contar un "fallo de handshake".

## Lo que se intentó y se descartó

**1) Downgrade de protocolo (TLS 1.0/1.1).** `openssl s_client -tls1` y `-tls1_1` fallan **localmente en el cliente** (`OpenSSL 3.5.5`) con `no protocols available` — el ClientHello nunca se construye ni se envía. No llega a la red, Suricata no ve nada. Confirmado por la config real del servidor (`configs/server/nginx-ppi.conf`): `ssl_protocols TLSv1.2 TLSv1.3;` — coherente con que un cliente moderno rechace ofrecer versiones no soportadas.

**2) Cifrado forzado incompatible (`-cipher "eNULL:@SECLEVEL=0"`).** Este sí llegó a la red: el ClientHello se envió y el servidor respondió con una alerta TLS real (`SSL alert number 40`, *handshake_failure*) en vez de un `ServerHello`. Verificado en EVE — Suricata **sí generó un evento `tls`**, pero con `"version": "TLS 1.2"` presente:
```json
{"event_type":"tls","src_ip":"10.20.0.20","dest_ip":"10.30.0.10","tls":{"version":"TLS 1.2","ja3":{...},"ja4":"..."}}
```
Esto indica que Suricata obtiene `tls.version` a partir del propio **ClientHello** (probablemente del campo `legacy_version` del registro TLS o de la extensión `supported_versions`), no del `ServerHello`. El hallazgo del docstring del extractor ("Suricata sólo emite el evento tras cierto avance del handshake") es cierto para la *emisión* del evento, pero no implica que `version` dependa de completar el handshake — ya está resuelto con solo el ClientHello.

**3) Paquete deliberadamente truncado (3 bytes de un header TLS de 5).** Se envió únicamente `\x16\x03\x01` (tipo *handshake* + versión de registro) y se cerró la conexión sin completar el ClientHello. Resultado en EVE: **no se generó ningún evento `tls`**, solo un evento `flow` con `app_proto: tls` (Suricata detectó heurísticamente que *parece* TLS, pero no logró un ClientHello completo para emitir el evento dedicado).

## Conclusión

Existe una brecha estructural entre dos estados observados:

- ClientHello **completo** (aunque el servidor lo rechace después) → evento `tls` con `version` **siempre presente**.
- ClientHello **incompleto** → **ningún** evento `tls`, solo `flow`.

No se encontró, con tráfico de cliente controlado y legítimo, ningún punto intermedio real que produzca un evento `tls` con `version` ausente. Es plausible que esa condición solo ocurra ante corrupción de red genuina (paquetes reordenados, fragmentación real que corta un ClientHello a la mitad, pérdida parcial) — algo que no se debe simular artificialmente como "tráfico de calibración legítimo", porque dejaría de representar un fallo de aplicación/protocolo y pasaría a representar degradación de red, un fenómeno distinto.

## Lo que no se hizo (a propósito)

- No se probaron técnicas más agresivas (inyección de bytes malformados dentro de un ClientHello por lo demás válido, explotar bugs de parseo de Suricata) porque cruzan la línea de "tráfico benigno de diagnóstico" hacia algo más parecido a fuzzing/explotación, fuera del alcance de una calibración de dataset normal.
- No se abrió ninguna campaña oficial de captura (PCAP/EVE/ledger) porque ninguna de las tres sondas produjo la señal buscada — abrir campaña sin evidencia de que el escenario funciona habría sido evidencia desperdiciada, igual que con los intentos fallidos de Codex en la Tarea 3.
- No se modificó `scripts/f1/run-benign.sh` ni ningún otro script — no hay código de escenario `tls-handshake-fail` que agregar todavía, porque no existe una técnica confirmada que producir.

## Opciones para decidir (requieren tu criterio, no las decido yo solo)

1. **Redefinir la feature.** En vez de "`tls` sin `version`", usar una señal distinta y sí alcanzable — por ejemplo, contar eventos `alert`/`anomaly` de Suricata asociados a un flujo TLS (el `SSL alert number 40` sí quedó registrado en alguna forma observable por Suricata, aunque no vía `event_type=tls`; habría que confirmar si aparece como `event_type=alert` con detalles TLS). Esto cambiaría la fórmula documentada en `configs/features/multilayer-v2.json` y requeriría actualizar el extractor y sus tests.
2. **Aceptar la brecha como limitación permanente.** Documentar que `tls_handshake_failure_ratio_60s`, tal como está definida, es estructuralmente casi imposible de poblar con tráfico benigno controlado en este laboratorio, y dejarla como feature de soporte teórico/futuro sin datos, sin bloquear el resto del trabajo.
3. **Investigar más a fondo el comportamiento de Suricata** (leer su código fuente o documentación oficial sobre cuándo exactamente resuelve `tls.version`) antes de descartar la Opción 1 — quizás haya una condición muy específica (por ejemplo, alertas TLS 1.3 con `HelloRetryRequest`, o una negociación que sí deja el campo vacío) que no se probó aquí.

No tomo esta decisión unilateralmente porque cambia la definición de una de las 28 features oficiales del esquema — es una decisión de diseño metodológico, no una ejecución de tarea.
