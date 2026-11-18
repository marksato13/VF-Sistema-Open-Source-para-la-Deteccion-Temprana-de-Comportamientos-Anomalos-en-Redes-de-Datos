# CyberFlow · guion de la demo (sustentación)

Versión 3-nov-2026 · medido en las corridas 3, 4 y 5 · evidencias en `evidencias\`

**Idea en una frase.** El sensor ve una copia del tráfico, decide con modelo y reglas, y publica una orden firmada con caducidad. El servidor protegido la aplica en su propio firewall, y un humano puede deshacerla con un comando.

---

## 0. Antes de empezar (5 min)

| # | Qué | Dónde | Quién |
|---|---|---|---|
| 1 | Abrir Herdr, espacio **CYBERFLOW DEMO**. Si no existe: `python montar.py` | `[LAPTOP PowerShell]` en `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\` | tú |
| 2 | Iniciar sesión en el panel y pulsar **Ctrl+F5** | Chrome · `https://vm-gestion.tail83bf9c.ts.net:8788/#s-escenario` | tú (contraseña) |
| 3 | Pulsar **Preparar demo** (arriba de las tarjetas) y esperar «Listo para la demo» con los 6 checks en verde (≈ 30 s). Libera la Kali (.30) y el cliente (.21) en srv-dmz por el feed firmado. **Repetirlo antes de cada escenario.** | Chrome · `#s-escenario` | tú |
| 3b | (Opcional, para enseñarlo en CLI) la Kali parte limpia: responde `NO` | panel SRV-DMZ: `~/cf-demo/en-firewall.sh 10.10.20.30` | tú o el director |

**Procedimiento de cada escenario, en orden de demo** (consola, comando, qué dice la CLI, GUI en paralelo y capturas; corridas 8-12 del 3-nov):

1. `PROCEDIMIENTO-1-L4-escaneo.md` · `python director.py 05` → BLOCK
2. `PROCEDIMIENTO-2-L7-http.md` · `python director.py 03` → LIMIT
3. `PROCEDIMIENTO-3-L3-icmp.md` · `python director.py 01` → BLOCK
4. `PROCEDIMIENTO-4-L7-dga.md` · `python director.py 02` → LIMIT
5. `PROCEDIMIENTO-5-legitimo.md` · `python director.py 04` → PERMIT

Las mismas diapositivas están en la presentación `CyberFlow-validacion-tecnica-Canva.pptx`, de la diapositiva 10 a la 21.

El recorrido de L4 completo, con capturas, consolas y qué decir en cada paso: `DEMO-L4-paso-a-paso.md`.

Las consolas de Herdr:

```
┌ ORIGEN (Kali / clientes) ┬ SENSOR1 (motor) ───────┐
├ SRV-DMZ (servidor)        ┴ BASTIÓN (Suricata) ────┤
└ DIRECTOR (guion paso a paso: Enter = siguiente) ───┘
```

El director escribe cada comando en la consola que toca. Tú hablas y vas al panel web. Arranca con `python director.py demo`, o `python director.py demo --auto` si no quieres pulsar Enter.

## 1. El recorrido, igual en cada escenario

Al pulsar **Iniciar** en *Escenario en vivo* aparece abajo una **barra guiada de 5 pasos**. Cada paso lleva el botón *Siguiente →*, que abre la sección del panel y resalta la fila de la IP.

| Paso | Consola (Herdr) | Panel web | Qué se defiende |
|---|---|---|---|
| 1 Ataque | ORIGEN: el director lanza el comando | `#s-escenario` · reloj en marcha | tráfico real, no simulado en el panel |
| 2 Actividad | SENSOR1: `mira-motor.sh IP` (una línea cada 10 s) | `#s-actividad` · la IP sube con su acción | el sensor ve una copia (espejo), no está en el camino |
| 3 Decisiones | SENSOR1 | `#s-decisiones` (filtrada) · fuente y motivo | **quién** lo detecta: modelo, regla o ambos |
| 4 Respuestas | — | `#s-bloqueos` · orden, detector, caducidad | la orden caduca sola; nunca es indefinida |
| 5 Host (CLI) | SRV-DMZ: `en-firewall.sh IP` → `BLOCK`/`LIMIT` | `#s-escenario` · paso 5 con el acuse del host | quien corta es el servidor, no el sensor |

Después vienen, solo en la consola: la prueba **con** la regla, la liberación humana `desbloquear.sh IP`, la prueba **después** y la comparación con Suricata (BASTIÓN).

## 2. Escenarios, en orden de demo

### 2.1 L4 · Escaneo de puertos (el más fuerte)

- **Decir:** «Primer paso de casi cualquier intrusión: descubrir puertos abiertos.»
- **Comando (Kali):** `nmap -sT -T4 --max-retries 1 -p 1-3000 --open 10.10.30.10`
- **Resultado (corrida 3):**
  - BLOCK por **modelo y regla `port_scan`**: 3492 intentos en 30 s contra 1762 puertos distintos, 0 % completados.
  - Tiempos: detección +00:45 · publicación +00:50 · aplicada en srv-dmz +00:57.
- **Prueba del firewall (corrida 4):** `80/443 open` → `filtered` → tras liberar, `open`. El host responde `NO`.
- **Suricata:** 4 alertas (ET SCAN, solo los puertos 1521 y 1433). CyberFlow ve el escaneo entero y responde.

### 2.2 L7 · Abuso HTTP (flood)

- **Decir:** «Cada petición es válida; lo anómalo es la tasa.»
- **Comando (Kali):** `seq 1 250 | xargs -P10 -I{} curl -s -o /dev/null -w '%{http_code} ' http://10.10.30.10/`
- **Resultado (corrida 3):**
  - LIMIT por la regla `http_abuse` (482 eventos HTTP en 60 s), confirmada por el modelo.
  - Tiempos: detección +00:22 · publicación +00:26 · aplicada +00:35.
- **Prueba (corrida 5):** 0 % de pérdida → con la regla, 35 % (LIMIT deja 100 paquetes/s) → tras liberar, 0 %.
- **Suricata:** 109 alertas, **ninguna firma de ataque**: solo eventos de flujo (STREAM) e informativos (ET INFO). CyberFlow sí lo identifica y responde.

### 2.3 L3 · Inundación ICMP (modelo y regla de capa 3)

- **Decir:** «El modelo ve el volumen anómalo y la regla de capa 3 lo confirma: el servidor lo corta.»
- **Comando (Kali):** `for k in 1 2 3 4; do ping -q -i 0.002 -s 1200 -w 60 10.10.30.10 >/dev/null & done; wait`
- **Resultado (corrida 7, 3-nov 04:46, política A + regla `icmp_flood`):**
  - BLOCK por **modelo y regla `icmp_flood`**: 832 → 3998 paquetes/s, 100 % ICMP; score −0,62/−0,63 frente al umbral −0,569.
  - Tiempos: detección +00:30 · publicación +00:33 · aplicada +00:44.
  - Ping: 0 % de pérdida → 100 % con el BLOCK → 0 % tras liberar.
  - Evidencia: `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\evidencias\20261103-0445-corrida7\EVIDENCIA.md`
- **Corrida 3 (antes de la política A):** el mismo ataque lo frenó solo el modelo con un LIMIT (+00:43 / +00:45 / +00:54).
- **Suricata:** **424 960 alertas** (una por ping, firmas GPL ICMP PING). CyberFlow lo resume en 4 ventanas y responde.

### 2.4 Legítimo · Cliente intenso (sin falsos positivos)

- **Decir:** «Uso intenso no es ataque. Aquí CyberFlow NO debe actuar.»
- **Comando (VM clientes, IP .21):** `for i in $(seq 1 60); do curl -s -o /dev/null --interface 10.10.20.21 http://10.10.30.10/; sleep 2; done`
- **Resultado (corrida 3):**
  - Panel: *todo PERMIT* en los 5 pasos; la IP no aparece entre las entidades con señales.
  - Estado verificado: 15 ventanas, 0 con acción, 0 anomalías marginales, fuera del feed; `en-firewall.sh` → `NO`.
- **Suricata:** 35 alertas (de flujo e informativas) que alguien tendría que revisar. CyberFlow: 0 de 23 ventanas.

### 2.5 Cierre · CyberFlow frente a Suricata (`#s-comparacion`)

- Las 4 tarjetas de la demo, cada una con su evidencia: `suricata:~/cf-demo/cmp-…/log/fast.log` y `sensor1:~/feed/comparaciones/cmp-….json`.
- **Cómo se hizo, en 4 pasos:** recortar el PCAP del espejo (IP + intervalo) → copiarlo a la VM Suricata 10.10.60.13 → `suricata -r` con las 53 013 firmas ET Open → contar las ventanas de CyberFlow del mismo intervalo y el acuse del host.
- La batería medida antes (N=3 por familia) está plegada debajo, en *Medición previa*.

## 3. Preguntas probables y respuesta corta

| Pregunta | Respuesta | Evidencia |
|---|---|---|
| ¿Por qué no bloqueó al cliente legítimo? | Las reglas exigen patrones de ataque (puertos distintos, tasa por minuto, paquetes ICMP por segundo). **El modelo avisa, la regla confirma y actúa:** una anomalía solo del modelo queda «para revisión humana» y no se publica. | Corrida 8 (3-nov 04:48): 12 ventanas, 0 con acción. |
| ¿Y si el modelo ve algo que ninguna regla cubre? | Queda registrado y visible como «anomalía sostenida · para revisión humana». Se decidió así con datos: en 9 h, perfiles legítimos intensos (.22, .24, .26) llegaron hasta 0,107 bajo el umbral y la Kali solo a 0,078; ningún margen los separaba, así que actuar con el modelo solo daba falsos positivos. | `publicar_feed.py` (`MODELO_SOLO_ACTUA = False`); respaldo del estado anterior: etiqueta git `antes-politica-AC-2026-11-03` |
| ¿Cómo se fijó el umbral de `icmp_flood`? | Con 3 119 148 ventanas reales: lo legítimo con mucho ICMP llega a 43,6 paquetes/s; el flood de la demo a 318–3998. Umbral 200 paquetes/s con ≥ 80 % ICMP. | `heuristicos.py` v2026-11-03.2, `test_heuristico_icmp.py` |
| ¿Antes no había falsos positivos? | Sí, y se corrigieron con datos: (1) `port_scan` confundía ráfagas web con escaneos (ahora exige ≥20 % de puertos distintos); (2) `http_abuse` contaba doble por el espejo (umbral 200 eventos = 100 peticiones reales); (3) el modelo actuaba con una sola ventana marginal. | `heuristicos.py` v2026-11-03.1, `publicar_feed.py`, pruebas `test_port_scan_rafaga_web.py` y `test_publicar_feed.py` |
| ¿Y si se equivoca? | La orden caduca sola, y `desbloquear.sh IP` la quita al instante. La cola tardía del mismo episodio no la vuelve a poner. | Corrida 4: `open` → `filtered` → `open` |
| ¿Por qué el sensor no bloquea él mismo? | Es pasivo (copia por espejo); solo publica un feed firmado. Cada host verifica la firma y decide con su alcance (`alcance.json`). | paso 5 · acuse del host |
| ¿Suricata no hace lo mismo? | Suricata detecta por firmas y solo alerta. En HTTP no tiene firma de ataque; en ICMP genera 424 960 alertas. CyberFlow detecta comportamiento y responde. | `#s-comparacion` |
| ¿Cuánto tarda? | De 22 a 45 s en detectar y menos de 1 min en aplicar. El motor trabaja con ventanas de 10 s y las registra con retraso. | tabla de la sección 2 |

## 4. Rutas

| Qué | Ruta |
|---|---|
| Este guion | `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\GUION-DEMO.md` |
| Evidencia corrida 3 (4 escenarios, 25 capturas) | `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\evidencias\20261103-0214-corrida3\EVIDENCIA.md` |
| Capturas corrida 3 | `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\evidencias\20261103-0214-corrida3\capturas\` |
| Verificación de la liberación (L4) | `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\evidencias\20261103-0244-corrida4\EVIDENCIA.md` |
| Director y escenarios | `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\director.py` · `...\generar_escenarios.py` · `...\escenarios\` |
| Comparador Suricata | `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\remoto\bastion\comparar-suricata.sh` (instalado en `bastion:~/cf-demo/`) |
| Resúmenes de comparación (los lee el panel) | `sensor1:~/feed/comparaciones/cmp-*.json` · fast.log en `suricata:~/cf-demo/cmp-*/log/` |
| Código del producto | `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\producto-as-deployed\` (rama `as-deployed-sensor-20261006`) |

## 5. Verificaciones posteriores a la corrida 3

- **Corrida 4 (L4):** tras la liberación, la cola tardía del motor se absorbe (`agente_enforce.py`). Antes / con / después = `open` / `filtered` / `open`.
- **Corrida 5 (HTTP):** LIMIT en +00:23 / +00:31 / +00:40; ping 0 % → 35 % → 0 % tras liberar; el host responde `NO`. Evidencia: `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\evidencias\20261103-0249-corrida5\EVIDENCIA.md`
