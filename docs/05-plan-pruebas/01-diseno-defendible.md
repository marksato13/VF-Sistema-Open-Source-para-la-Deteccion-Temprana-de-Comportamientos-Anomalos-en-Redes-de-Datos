# Diseño defendible de escenarios y dataset

## Fundamento

El diseño sigue la recomendación de NIST de establecer una línea base de flujos y comunicaciones normales antes de detectar anomalías ([NIST SP 800-82r3](https://csrc.nist.gov/pubs/sp/800/82/r3/final)). La captura se conservará en EVE JSON, que Suricata define como salida estructurada para alertas, flujos y protocolos ([documentación EVE](https://docs.suricata.io/en/suricata-7.0.15/output/eve/eve-json-output.html)).

Para representar amenazas reconocibles se emplean categorías de MITRE ATT&CK, sin ejecutar técnicas fuera del laboratorio: Network Service Scanning, Password Guessing y Network Denial of Service ([T1046](https://attack.mitre.org/techniques/T1046/), [T1110.001](https://attack.mitre.org/techniques/T1110/001/), [T1498](https://attack.mitre.org/techniques/T1498/)).

## Reestructuración de campañas

### F0 — control y calibración

DNS, NTP, ICMP, SSH y HTTP de baja intensidad. Sirve para comprobar timestamps, rutas, sensores y ausencia de pérdida antes de producir datos.

### F1 — normalidad representativa (entrenamiento)

Cliente genera navegación HTTP, descargas de 500 MB, transferencias SSH/SFTP, `iperf3` TCP/UDP a varios bitrates, consultas DNS y sesiones concurrentes. Se registran ventanas de 10 s, 30 s y 60 s. Debe incluir tamaños de paquete entre 500 y 1500 bytes y variación de IP/puerto sin ataques.

### F2 — normalidad límite (validación)

Repite F1 con picos legítimos: 2, 4 y 8 descargas concurrentes; `iperf3` al 25 %, 50 %, 75 % y máximo seguro; UDP con pérdida controlada. Se etiqueta como `benign_stress`, no como ataque.

### F3 — anomalías por capa

| Capa | Escenarios | Variables que deben emerger |
|---|---|---|
| L3 | barrido de hosts/puertos desde Kali y variación de origen | IPs únicas, ratio de destinos, entropía de destinos, TTL |
| L4 | SYN burst limitado, UDP burst y puertos no usados | frecuencia SYN, SYN/ACK, RST, ratio de flags, puertos únicos |
| L7 | intentos SSH fallidos en servicio de laboratorio, HTTP paths inexistentes y consultas DNS anómalas | fallos de login, códigos HTTP, frecuencia DNS, longitud/entropía de URI |

Cada escenario tendrá intensidad baja/media/alta y duración fija; se detendrá si afecta la disponibilidad del servidor.

### F4 — mixto y generalización

Cliente ejecuta F2 mientras Kali ejecuta una sola anomalía F3. Esta fase evalúa si el modelo separa congestión legítima de comportamiento hostil.

## Dataset y reentrenamiento

Se guardan PCAP/EVE, manifiesto, hashes, timestamps, configuración y etiqueta por ventana. La división será por sesión y fecha (60 % entrenamiento, 20 % validación, 20 % prueba), evitando que paquetes de una misma sesión aparezcan en particiones distintas. Isolation Forest se ajustará solo con F1; F2 mide robustez y F3/F4 miden detección. Después se compararán las 14 features originales contra el conjunto ampliado mediante ablación L3/L4/L7, F1-score, tasa de falsos positivos y tasa de detección.

## Reglas de seguridad

Solo se usan las IP de esta topología, sin spoofing, explotación destructiva ni ataques hacia Internet. Se conserva una ventana de recuperación y se documenta cualquier reinicio o cambio de configuración.

## Puertas de decisión y reestructuración

Las fases son una hipótesis de trabajo, no una secuencia inmutable. Cada una tiene una puerta de decisión:

| Puerta | Evidencia requerida | Acción si no cumple |
|---|---|---|
| G0 | NTP, rutas y aislamiento correctos | detener; corregir infraestructura y repetir F0 |
| G1 | F0 sin pérdida ni eventos inexplicables | depurar Suricata, firewall o servicio antes de F1 |
| G2 | F1 cubre protocolos, tamaños 500–1500 bytes y variación legítima | ampliar escenarios normales antes de entrenar |
| G3 | F2 mantiene disponibilidad y pérdida dentro del umbral definido | reducir bitrate/concurrencia o ampliar recursos; no ejecutar F3 |
| G4 | F3 produce etiquetas y evidencia EVE correlacionable | ajustar una técnica por vez y repetir; no mezclar ataques |
| G5 | F4 separa congestión legítima de anomalía | revisar features, ventanas y particiones antes de publicar métricas |

Se puede dividir una fase, repetirla o introducir una fase intermedia de calibración cuando la evidencia lo exija. El producto final debe reportar tanto los resultados favorables como los límites, repeticiones y escenarios descartados.
