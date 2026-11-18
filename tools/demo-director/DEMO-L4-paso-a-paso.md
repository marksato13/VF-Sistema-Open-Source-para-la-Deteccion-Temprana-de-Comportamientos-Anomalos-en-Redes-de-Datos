# Demo L4 · Escaneo de puertos, paso a paso (GUI + CLI + guion)

Corrida de referencia: **corrida 6, 3-nov-2026 03:45–03:52**, ejecutada en Herdr («CYBERFLOW DEMO»).
Capturas: `evidencias\20261103-0345-corrida6\capturas\` · registro completo con las 5 consolas: `evidencias\20261103-0345-corrida6\EVIDENCIA.md`.

| Hito | Hora | Desde el ataque |
|---|---|---|
| Ataque (nmap 3000 puertos) | 03:46:11 | 0 s |
| Detección: regla `port_scan` + modelo → BLOCK | 03:46:43 | +31 s |
| Publicación en el feed firmado | 03:46:50 | +38 s |
| Aplicado en nftables de srv-dmz | 03:47:05 | +49 s |
| Liberación por un humano | 03:48:45 | — |
| Suricata (53 013 firmas) sobre el mismo tráfico | 03:50:41 | 14 alertas, ninguna respuesta |

**Dónde está cada cosa**

- Panel web: Chrome · `https://vm-gestion.tail83bf9c.ts.net:8788/#s-escenario` (el Sensor1 es `10.10.60.11:8788`).
- Consolas: Herdr, espacio **CYBERFLOW DEMO** (`wQ`): ORIGEN · KALI, SENSOR1, SRV-DMZ, BASTIÓN · Suricata y DIRECTOR.
- Lanzar solo L4: `[LAPTOP PowerShell]` en `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\` → `python director.py 05` (Enter = siguiente paso) o `python director.py 05 --auto`.

---

## Paso 0 · Dejar todo listo (botón «Preparar demo»)

**GUI:** `#s-escenario` → botón **Preparar demo**. Hay que esperar ≈ 30 s a que salga «Listo para la demo» con 6 checks:

1. Motor en vivo.
2. Feed firmado al día.
3. Petición dentro del feed firmado.
4. Agente de srv-dmz activo.
5. 10.10.20.30 sin regla.
6. 10.10.20.21 sin regla.

![Preparar](evidencias/20261103-0345-corrida6/capturas/00-preparar.png)

**Qué pasa por debajo:**

1. El panel deja una petición en `sensor1:~/feed/peticiones/preparar.json`.
2. El publicador la mete **dentro del feed firmado**.
3. El relay del bastión la lleva a srv-dmz.
4. El agente verifica la firma y libera las dos IP una sola vez.

No hace falta ni SSH ni sudo. **Se pulsa antes de cada escenario.**

**Qué decir:** «Antes de empezar dejo el laboratorio limpio. Este botón no toca el firewall directamente: pide la liberación por el mismo canal firmado que usan los bloqueos, y el panel me confirma que el servidor ya no tiene reglas para la Kali.»

---

## Paso 1 · Presentar el escenario

**GUI:** `#s-escenario` → tarjeta **L4 · Escaneo de puertos**.

**Qué decir:** «Primer paso de casi cualquier intrusión: descubrir qué puertos están abiertos. La Kali (10.10.20.30) va a probar 3000 puertos TCP del servidor de la DMZ (10.10.30.10).»

## Paso 2 · Abrir las consolas (CLI)

| Consola Herdr | Máquina | Comando | Qué enseña |
|---|---|---|---|
| SENSOR1 | `[SENSOR1 m4rk]` | `~/cf-demo/mira-motor.sh 10.10.20.30` | una línea por ventana de 10 s: hora, acción, score, umbral, modelo, regla |
| SRV-DMZ | `[SRV-DMZ adminsrvdmz]` | `~/cf-demo/mira-agente.sh 10.10.20.30` | orden recibida, firewall nftables y última pasada del agente |

Salida de partida en SRV-DMZ:

```text
orden del sensor : ninguna para esta IP
FIREWALL nftables: tabla cyberflow activa · 10.10.20.30 sin regla (pasa libre)
```

**Qué decir:** «A la izquierda, el motor del sensor; abajo, el propio servidor protegido. Ahora mismo la Kali no tiene ninguna regla.»

## Paso 3 · ANTES: el servidor contesta

**CLI:** consola ORIGEN · KALI, `[KALI adminatacante]` → `nmap -n -Pn --max-retries 0 --host-timeout 8s -p80,443 10.10.30.10`

```text
80/tcp  open  http
443/tcp open  https
```

**Qué decir:** «Línea base: la web del servidor responde, 80 y 443 *open*.»

## Paso 4 · Iniciar el seguimiento y lanzar el ataque

**GUI:** la tarjeta → **Iniciar seguimiento** de 10.10.20.30. Abajo aparece la barra guiada con 5 pasos: Ataque → Actividad → Decisiones → Respuestas → Host (CLI).

![Inicio](evidencias/20261103-0345-corrida6/capturas/05-inicio.png)

**CLI:** ORIGEN · KALI → `nmap -sT -T4 --max-retries 1 -p 1-3000 --open 10.10.30.10`. Las opciones:

- `-sT`: conexión TCP completa, sin root.
- `-T4`: ritmo agresivo.
- `--max-retries 1`: un solo reintento.
- `-p 1-3000`: los puertos 1–3000.
- `--open`: lista solo los abiertos.

**Qué decir:** «Lanzo el escaneo. El reloj de la barra cuenta desde ahora.»

## Paso 5 · Detección (+31 s) → Actividad

**CLI (SENSOR1):** aparece la ventana anómala.

```text
03:46:43 PERMIT -0.56 -0.57 normal
03:46:43  BLOCK -0.62 -0.57 ANÓMALO port_scan 2238 intentos/30s a 1138 puertos distintos
```

**GUI:** barra guiada → **2 Actividad** (`#s-actividad`). 10.10.20.30 sale arriba en «Entidades con señales», con BLOCK.

![Actividad](evidencias/20261103-0345-corrida6/capturas/05-actividad.png)

**Qué decir:** «En 31 segundos coinciden la regla y el modelo. La regla ve 2238 intentos a 1138 puertos distintos en 30 s, sin casi ninguna conexión completa. El modelo da −0,62, por debajo del umbral de −0,57.»

## Paso 6 · Decisiones

**GUI:** barra guiada → **3 Decisiones** (`#s-decisiones`, filtrada por la IP). Hay dos filas BLOCK, «Modelo + regla», con el motivo, el score frente al umbral y los paquetes. «Ver detalle» abre la ventana completa.

![Decisiones](evidencias/20261103-0345-corrida6/capturas/05-decisiones.png)

**Qué decir:** «Cada decisión es explicable: qué variable disparó, el score del modelo y su umbral. Si solo hubiera saltado el modelo, CyberFlow exige una anomalía clara y sostenida (3 ventanas en 2 minutos) antes de actuar. Así evito falsos positivos.»

## Paso 7 · Publicación (+38 s) → Respuestas

**GUI:** barra guiada → **4 Respuestas** (`#s-bloqueos`). La fila 10.10.20.30 muestra BLOCK, reincidencia nivel 3, caducidad 04:47:48 y las etiquetas «registrada · publicada · srv-dmz: BLOCK aplicado».

![Respuestas](evidencias/20261103-0345-corrida6/capturas/05-respuestas.png)

**Qué decir:** «El sensor no toca el servidor. Publica una orden firmada con caducidad: el bloqueo se retira solo. Como esta IP reincide, sube de nivel.»

> Si en esta tabla aparece otra IP con LIMIT y «srv-dmz: no se aplica (fuera de alcance)», el motor lo decidió pero el servidor no lo aplica: no es tráfico que llegue a la DMZ.

## Paso 8 · Aplicación en el host (+49 s)

**GUI:** barra guiada → **5 Host (CLI)**. Los 5 pasos del seguimiento quedan llenos, y el quinto, «Aplicación en el host», lo confirma el acuse de srv-dmz.

![Aplicación](evidencias/20261103-0345-corrida6/capturas/05-aplicacion.png)

**CLI (SRV-DMZ):**

```text
FIREWALL nftables:  10.10.20.30 BLOQUEADA (drop total) · se quita sola en 3591 s
última pasada del agente: aplicado · aplica BLOCK · errores 0
```

`[SRV-DMZ adminsrvdmz]` → `~/cf-demo/en-firewall.sh 10.10.20.30` → `BLOCK`

**Qué decir:** «El agente del servidor trajo el feed, comprobó la firma y metió la IP en nftables: 49 s desde el primer paquete del ataque.»

## Paso 9 · CON la regla: el servidor ya no contesta

**CLI (ORIGEN · KALI):** `nmap -n -Pn --max-retries 0 --host-timeout 8s -p80,443 10.10.30.10`

```text
80/tcp  filtered http
443/tcp filtered https
```

**Qué decir:** «La misma prueba de antes: ahora *filtered*. El firewall descarta todo lo que viene de la Kali.»

## Paso 10 · Revisión humana: liberar

**CLI (SRV-DMZ):** `~/cf-demo/desbloquear.sh 10.10.20.30`

```text
antes de liberar : 10.10.20.30 en el firewall = BLOCK
tras liberar     : 10.10.20.30 en el firewall = NO
```

**GUI:** `#s-escenario`. El paso 5 dice «srv-dmz: sin regla, liberada por revisión humana. Las ventanas tardías del mismo episodio no la vuelven a poner.»

![Liberación](evidencias/20261103-0345-corrida6/capturas/05-liberacion.png)

**CLI (ORIGEN · KALI):** el mismo nmap → `80/tcp open · 443/tcp open`.

**Qué decir:** «Un humano siempre puede deshacerlo. La liberación se respeta durante el resto del episodio; solo un ataque nuevo vuelve a bloquear.»

## Paso 11 · Cierre: frente a Suricata

**CLI (BASTIÓN · Suricata):** `[BASTIÓN gadmin]` → `~/cf-demo/comparar-suricata.sh 10.10.20.30 03:46:10 03:48:10`. Hace cuatro cosas:

1. Recorta del anillo PCAP los 6533 paquetes del ataque.
2. Los pasa a la VM de Suricata (10.10.60.13).
3. Corre `suricata -r` con ET Open, 53 013 firmas.
4. Lo compara con CyberFlow.

**GUI:** `#s-comparacion`, la primera tarjeta.

![Suricata](evidencias/20261103-0345-corrida6/capturas/05-suricata.png)

| | Suricata 7 + ET Open | CyberFlow |
|---|---|---|
| Lo ve | 14 alertas, 4 firmas. 10 son de flujo TCP (`SURICATA STREAM … invalid ack`) y 4 son `ET SCAN` (Oracle 1521 y MSSQL 1433) | 4 de 13 ventanas con acción, BLOCK por modelo + port_scan |
| Responde | no: solo genera alertas | sí: BLOCK aplicado en srv-dmz a las 03:47:05 |

**Qué decir:** «Los dos lo ven. Suricata necesita firmas y solo alerta. CyberFlow lo detecta por comportamiento y además responde, con caducidad y con revisión humana.»

---

## Guion corto (para leer de corrido, ≈ 2 min)

1. «Primer paso de casi cualquier intrusión: descubrir puertos abiertos.»
2. «Antes del ataque la web responde: *open*.»
3. «Lanzo 3000 puertos TCP desde la Kali.»
4. «En 31 s coinciden regla y modelo: muchos puertos distintos y casi ninguna conexión completa.»
5. «Cada decisión dice por qué: variable, score y umbral.»
6. «El sensor publica una orden firmada con caducidad; el servidor la aplica a los 49 s.»
7. «Ahora el servidor no le contesta: *filtered*.»
8. «Un humano la libera y vuelve a *open*.»
9. «Suricata, con 53 013 firmas, da 14 alertas y no responde; CyberFlow bloqueó.»
