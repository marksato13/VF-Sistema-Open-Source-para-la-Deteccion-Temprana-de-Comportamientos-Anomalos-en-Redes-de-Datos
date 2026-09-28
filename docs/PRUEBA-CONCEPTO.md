# Prueba de concepto — detección temprana de anomalías

Ensayo funcional del 2026-09-27 en la red de Franco's SAC. **No es la medición
definitiva de la tesis** (para eso falta la semana completa con los servicios
reales montados); es la prueba de que la cadena entrena → detecta → responde
funciona de punta a punta, con cifras honestas y sus límites declarados.

## Montaje

- **Un sensor** (10.10.60.11) sobre un espejo SPAN del troncal del cortafuegos.
  Observa, no está en el camino del tráfico.
- **31 variables** por entidad y ventana (10 s): 9 red, 8 transporte, 11
  aplicación, 3 enlace. El motor puntúa las 28 clásicas; las 3 de capa 2 se
  acumulan.
- **Tráfico legítimo**: una VM con seis perfiles (10.10.20.21-.26) contra el
  servidor 10.10.30.10.
- **Ataques**: una Kali (10.10.20.30) contra el mismo servidor.

## Método

Captura (tcpdump + Suricata) → extracción de variables → **partición sin fuga
temporal** (bandas de guarda de 60 s) → entrenamiento (IsolationForest sobre
tráfico limpio, **umbral congelado en validación antes de evaluar**) → se puntúan
las ventanas de ataque con ese modelo congelado, sin reajustar nada.

Base limpia: ~91 000 filas / ~18 h. FPR sobre el conjunto de prueba (limpio):
**~9 %** frente al 5 % objetivo — se desvía porque son datos de fin de semana,
poco variados. Es el argumento para la semana completa.

## Resultados de detección

Modelo entrenado solo con tráfico limpio, umbral congelado antes de ver los
ataques:

| Ataque | Ventanas detectadas | Variables que lo delataron |
|---|---|---|
| Escaneo de puertos (nmap) | **79 %** | syn_rate_10s, flow_attempt_rate_10s |
| Escaneo web (nikto)       | **87 %** | http_request_rate_60s, http_error_ratio_60s |
| Fuerza bruta / flood HTTP | **87 %** | http_request_rate_60s, syn_rate_10s |
| ARP spoofing (capa 2)     | **0 %**  | unique_src_mac_30s (sube, pero poco) |

Los tres ataques volumétricos se detectan bien y **las variables correctas son
las que se disparan** en cada caso.

## Hallazgo: la capa 2 no se detecta con el modelo global

El ARP spoofing no se detectó, pero **el sensor sí lo vio**: `unique_src_mac_30s`
de la puerta de enlace subió de 0 a 1 durante el ataque. La señal es real; el
problema es que una variable a z≈1 sobre 31 se diluye en un Isolation Forest
global. Conclusión, y es un resultado, no un fallo: **los ataques volumétricos
van con ML no supervisado; la suplantación va con una regla determinista**
(`unique_src_mac ≥ 2` → bandera roja). Las variables de capa 2 ya habilitan esa
regla; conectarla es trabajo futuro.

## Correcciones encontradas por medir, no por leer

- **DNS**: el extractor comparaba `dns.type` contra `request`/`response`;
  Suricata emite `query`/`answer`. Tres variables de DNS estaban a cero en todos
  los datasets, incluido el del modelo publicado. Corregido y verificado:
  `dns_query_rate_60s` pasó de 0 a 3090/5416 ventanas con valor.
- **Deduplicación del espejo**: `tcp_retransmission_ratio_10s` medía copias del
  SPAN como retransmisiones (0,1488 → 0,0000 tras deduplicar).

## Respuesta (bloqueo)

El responder lleva la decisión a un iptables que sí está en el camino (el del
servidor, o pfSense). Lleva un **interlock de calibración**: no aplica bloqueo
si el modelo no está calibrado en esta red. Comprobado contra el registro real:
con el umbral actual (de otra red) el responder marcaría 9 entidades —incluida
la Kali, pero también los seis clientes legítimos y el servidor—, así que
bloquear ahora sería una denegación de servicio autoinfligida. El corte se
habilita tras recalibrar.

## Límites declarados

- Cifras de **prueba de concepto**, no publicables: FPR 9 % por régimen de fin
  de semana; falta la semana completa con Wazuh (VLAN 60) y AAA (VLAN 40).
- Cobertura **parcial**: el espejo ve 8 de las 14 VLAN; el este-oeste
  intra-VLAN no se ve.
- El corte real de tráfico está construido y probado en seco, pero **no
  desplegado**: necesita acceso root al host que aplica.

## Trabajo futuro

Semana completa con los servicios reales montados · un modelo/umbral por zona ·
la regla determinista de capa 2 · integración de la respuesta con pfSense.
