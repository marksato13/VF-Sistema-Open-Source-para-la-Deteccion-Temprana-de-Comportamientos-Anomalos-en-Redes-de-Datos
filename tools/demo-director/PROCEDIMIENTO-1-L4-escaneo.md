# Escenario 1 · Escaneo de puertos (L4 · Transporte)

Procedimiento de la demo, en orden. Medido el 3-nov-2026 en la corrida 9.
Evidencia completa (comandos y salidas tal cual): `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\evidencias\20261103-0634-corrida9\EVIDENCIA.md`

- **IP seguida:** `10.10.20.30` → servidor `10.10.30.10` (srv-dmz)
- **Director:** `python director.py 05` (con `--auto` no hay que pulsar Enter)
- **Se espera:** BLOCK con caducidad, aplicado por el servidor
- **Qué decir:** «Primer paso de casi cualquier intrusión: descubrir puertos abiertos. Modelo y regla coinciden: BLOCK con caducidad; corta el servidor, no el sensor.»

## Antes de empezar

1. Herdr abierto en el espacio **CYBERFLOW DEMO**, con las 5 consolas: ORIGEN, SENSOR1, SRV-DMZ, BASTIÓN y DIRECTOR. Si falta, desde la consola DIRECTOR ejecuta `python montar.py`.
2. En Chrome, abre el panel `https://vm-gestion.tail83bf9c.ts.net:8788/#s-escenario`, pulsa **Ctrl+F5** y luego **Preparar demo**. Espera «Listo para la demo» con los 6 checks en verde.

## Paso a paso

Cada comando lo escribe el director en su consola de Herdr; tú hablas y vas al panel. Si lo haces a mano, ejecuta cada comando en la consola indicada.

### 1. Chrome

`[LAPTOP navegador]` → lo haces tú (sesión iniciada en el panel): **Panel · Escenario en vivo → «Preparar demo»**

- **Qué hace / qué dice:** Libera la Kali (.30) y el cliente (.21) en srv-dmz y comprueba 6 puntos: «Listo para la demo».
- **GUI en paralelo:** #s-escenario · 6 checks en verde

### 2. DIRECTOR

`[LAPTOP PowerShell]` → lo ejecutas tú en la consola DIRECTOR de Herdr

```bash
python director.py 05 --auto
```

- **Qué hace / qué dice:** Arranca el guion: escribe cada comando en su consola de Herdr y pide cada captura de la GUI.
- **GUI en paralelo:** —

### 3. SENSOR1

`[SENSOR1 m4rk]` → lo ejecuta el director en la consola SENSOR1 de Herdr

```bash
~/cf-demo/mira-motor.sh 10.10.20.30
```

- **Qué hace / qué dice:** Motor en vivo: una línea por ventana de 10 s (hora, acción, score frente al umbral, regla).
- **GUI en paralelo:** «Ventanas de la IP»

### 4. SRV-DMZ

`[SRV-DMZ adminsrvdmz]` → lo ejecuta el director en la consola SRV-DMZ de Herdr

```bash
~/cf-demo/mira-agente.sh 10.10.20.30
```

- **Qué hace / qué dice:** Servidor por dentro, cada 2 s: agente, feed recibido, orden para la IP y nftables. Dice: «sin regla (pasa libre)».
- **GUI en paralelo:** paso 5 «Host»

### 5. ORIGEN

`[KALI adminatacante]` → lo ejecuta el director en la consola ORIGEN de Herdr

```bash
ANTES: nmap -n -Pn --max-retries 0 --host-timeout 8s -p80,443 10.10.30.10
```

- **Qué hace / qué dice:** Dice: 80/tcp open · 443/tcp open (el servidor contesta).
- **GUI en paralelo:** — (solo CLI)

### 6. Chrome

`[LAPTOP navegador]` → lo haces tú (sesión iniciada en el panel): **Tarjeta «Escaneo de puertos» → Iniciar seguimiento de 10.10.20.30**

- **Qué hace / qué dice:** Arranca el reloj y la barra guiada de 5 pasos.
- **GUI en paralelo:** barra · 1 Ataque

### 7. ORIGEN

`[KALI adminatacante]` → lo ejecuta el director en la consola ORIGEN de Herdr

```bash
nmap -sT -T4 --max-retries 1 -p 1-3000 --open 10.10.30.10
```

- **Qué hace / qué dice:** ATAQUE: 3000 puertos TCP a ritmo agresivo (-sT connect, -T4, --open solo abiertos). Tarda ~22 s.
- **GUI en paralelo:** barra · 1 Ataque (reloj)

### 8. SENSOR1

`[SENSOR1 m4rk]` → lo ejecuta el director en la consola SENSOR1 de Herdr: **(mira-motor.sh sigue abierto)**

- **Qué hace / qué dice:** Aparece BLOCK · modelo + port_scan (6010 intentos/30 s a 3001 puertos, 0 % completados; score −0,630 < −0,569).
- **GUI en paralelo:** 2 Actividad → 3 Decisiones → 4 Respuestas

### 9. SRV-DMZ

`[SRV-DMZ adminsrvdmz]` → lo ejecuta el director en la consola SRV-DMZ de Herdr

```bash
~/cf-demo/en-firewall.sh 10.10.20.30
```

- **Qué hace / qué dice:** Consulta los sets de nftables. Dice: «BLOCK».
- **GUI en paralelo:** 5 Host · acuse de srv-dmz

### 10. ORIGEN

`[KALI adminatacante]` → lo ejecuta el director en la consola ORIGEN de Herdr

```bash
CON la regla: nmap -n -Pn --max-retries 0 --host-timeout 8s -p80,443 10.10.30.10
```

- **Qué hace / qué dice:** Dice: 80/tcp filtered · 443/tcp filtered: el servidor ya no le contesta.
- **GUI en paralelo:** — (solo CLI)

### 11. SRV-DMZ

`[SRV-DMZ adminsrvdmz]` → lo ejecuta el director en la consola SRV-DMZ de Herdr

```bash
~/cf-demo/desbloquear.sh 10.10.20.30
```

- **Qué hace / qué dice:** Revisión humana. Dice: «antes = BLOCK» → «tras liberar = NO».
- **GUI en paralelo:** paso 5 «liberada por revisión humana»

### 12. ORIGEN

`[KALI adminatacante]` → lo ejecuta el director en la consola ORIGEN de Herdr

```bash
DESPUÉS: nmap -n -Pn --max-retries 0 --host-timeout 8s -p80,443 10.10.30.10
```

- **Qué hace / qué dice:** Dice: 80/tcp open · 443/tcp open otra vez.
- **GUI en paralelo:** — (solo CLI)

### 13. BASTIÓN

`[BASTIÓN gadmin]` → lo ejecuta el director en la consola BASTIÓN de Herdr

```bash
~/cf-demo/comparar-suricata.sh 10.10.20.30 <inicio> <fin>
```

- **Qué hace / qué dice:** Suricata 7 + ET Open: 6 alertas (ET SCAN 1521/1433 y STREAM). CyberFlow: 4 ventanas con acción, BLOCK aplicado 06:36:35.
- **GUI en paralelo:** #s-comparacion · tarjeta

## Resultado medido

| | |
|---|---|
| Respuesta | BLOCK · modelo + regla port_scan |
| Detección | +00:40 desde el inicio del ataque |
| Publicación en el feed firmado | +00:45 |
| Aplicada en nftables de srv-dmz | +00:53 |
| Caducidad / nota | caduca sola (07:36) · reincidencia nivel 3 |
| Prueba en la CLI | nmap 80/443:  open → filtered → open |
| Frente a Suricata | Suricata: 6 alertas (solo puertos 1521 y 1433); CyberFlow: ve el escaneo entero y responde |

## Recorrido de la GUI

**actividad** · `#s-actividad`

![05-actividad](evidencias/20261103-0634-corrida9/capturas/05-actividad.png)

**aplicacion** · `#s-escenario · paso 5`

![05-aplicacion](evidencias/20261103-0634-corrida9/capturas/05-aplicacion.png)

**decisiones** · `#s-decisiones`

![05-decisiones](evidencias/20261103-0634-corrida9/capturas/05-decisiones.png)

**inicio** · `#s-escenario`

![05-inicio](evidencias/20261103-0634-corrida9/capturas/05-inicio.png)

**liberacion** · `#s-escenario · paso 5`

![05-liberacion](evidencias/20261103-0634-corrida9/capturas/05-liberacion.png)

**respuestas** · `#s-bloqueos`

![05-respuestas](evidencias/20261103-0634-corrida9/capturas/05-respuestas.png)

**suricata** · `#s-comparacion`

![05-suricata](evidencias/20261103-0634-corrida9/capturas/05-suricata.png)

## Si algo sale distinto

- **La IP ya aparece en el firewall antes de empezar:** pulsa **Preparar demo** otra vez, o ejecuta `~/cf-demo/desbloquear.sh 10.10.20.30` en SRV-DMZ.
- **La barra se queda en «Actividad»:** el motor registra cada ventana de 10 s con unos segundos de retraso; espera hasta 60 s antes de repetir.
- **Aparece un LIMIT de 10.10.10.20 (DNS):** es infraestructura protegida. Se registra pero nunca se aplica, y el panel ya no lo cuenta como alerta (commit 0cc1125).
