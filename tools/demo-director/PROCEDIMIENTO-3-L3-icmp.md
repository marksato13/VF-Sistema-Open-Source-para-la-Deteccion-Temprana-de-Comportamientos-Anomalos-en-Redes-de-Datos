# Escenario 3 · Inundación ICMP (L3 · Red)

> **HISTÓRICO — no describe el sistema actual.** Este BLOCK se midió el 3-nov con la
> política A+C (motor `4ea1c68`), revertida esa misma noche (`ca66db5`). El motor vivo
> desde entonces (`ec78ca5`, α 0,01) **no tiene regla ICMP**: un flood queda en ALERT del
> modelo y el ping sigue pasando. Ver `deploy/laboratorio-2026-11-18/`.

Procedimiento de la demo, en orden. Medido el 3-nov-2026 en la corrida 11.
Evidencia completa (comandos y salidas tal cual): `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\evidencias\20261103-0649-corrida11\EVIDENCIA.md`

- **IP seguida:** `10.10.20.30` → servidor `10.10.30.10` (srv-dmz)
- **Director:** `python director.py 01` (con `--auto` no hay que pulsar Enter)
- **Se espera:** BLOCK con caducidad, aplicado por el servidor
- **Qué decir:** «El modelo ve el volumen anómalo y la regla de capa 3 lo confirma: el servidor lo corta.»

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
python director.py 01 --auto
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
ANTES: ping -q -c 150 -i 0.004 10.10.30.10 | tail -2
```

- **Qué hace / qué dice:** 150 pings a 250/s. Dice: 0 % packet loss.
- **GUI en paralelo:** — (solo CLI)

### 6. Chrome

`[LAPTOP navegador]` → lo haces tú (sesión iniciada en el panel): **Tarjeta «Inundación ICMP» → Iniciar seguimiento de 10.10.20.30**

- **Qué hace / qué dice:** Arranca el reloj y la barra guiada de 5 pasos.
- **GUI en paralelo:** barra · 1 Ataque

### 7. ORIGEN

`[KALI adminatacante]` → lo ejecuta el director en la consola ORIGEN de Herdr

```bash
for k in 1 2 3 4; do ping -q -i 0.002 -s 1200 -w 60 10.10.30.10 >/dev/null & done; wait
```

- **Qué hace / qué dice:** ATAQUE: 4 pings en paralelo durante 60 s, unos 2000 paquetes/s de 1200 bytes (sin sudo).
- **GUI en paralelo:** barra · 1 Ataque (reloj)

### 8. SENSOR1

`[SENSOR1 m4rk]` → lo ejecuta el director en la consola SENSOR1 de Herdr: **(mira-motor.sh sigue abierto)**

- **Qué hace / qué dice:** Aparece BLOCK · modelo + icmp_flood (2628 paquetes/s, 100 % ICMP; score −0,634 < −0,569).
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
CON la regla: ping -q -c 150 -i 0.004 10.10.30.10 | tail -2
```

- **Qué hace / qué dice:** Dice: 100 % packet loss: el servidor ya no le responde.
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
DESPUÉS: ping -q -c 150 -i 0.004 10.10.30.10 | tail -2
```

- **Qué hace / qué dice:** Dice: 0 % packet loss.
- **GUI en paralelo:** — (solo CLI)

### 13. BASTIÓN

`[BASTIÓN gadmin]` → lo ejecuta el director en la consola BASTIÓN de Herdr

```bash
~/cf-demo/comparar-suricata.sh 10.10.20.30 <inicio> <fin>
```

- **Qué hace / qué dice:** Suricata: 308 324 alertas (una por ping, GPL ICMP PING). CyberFlow: 6 ventanas BLOCK, aplicado 06:51:04.
- **GUI en paralelo:** #s-comparacion · tarjeta

## Resultado medido

| | |
|---|---|
| Respuesta | BLOCK · modelo + regla icmp_flood |
| Detección | +00:27 desde el inicio del ataque |
| Publicación en el feed firmado | ≤ +00:35 |
| Aplicada en nftables de srv-dmz | +00:35 |
| Caducidad / nota | caduca sola (07:51) · reincidencia nivel 3 |
| Prueba en la CLI | ping a 250/s:  0 % → 100 % → 0 % de pérdida |
| Frente a Suricata | Suricata: 308 324 alertas (una por paquete); CyberFlow: 6 ventanas y una sola respuesta |

## Recorrido de la GUI

**actividad** · `#s-actividad`

![01-actividad](evidencias/20261103-0649-corrida11/capturas/01-actividad.png)

**aplicacion** · `#s-escenario · paso 5`

![01-aplicacion](evidencias/20261103-0649-corrida11/capturas/01-aplicacion.png)

**decisiones** · `#s-decisiones`

![01-decisiones](evidencias/20261103-0649-corrida11/capturas/01-decisiones.png)

**inicio** · `#s-escenario`

![01-inicio](evidencias/20261103-0649-corrida11/capturas/01-inicio.png)

**liberacion** · `#s-escenario · paso 5`

![01-liberacion](evidencias/20261103-0649-corrida11/capturas/01-liberacion.png)

**respuestas** · `#s-bloqueos`

![01-respuestas](evidencias/20261103-0649-corrida11/capturas/01-respuestas.png)

**suricata** · `#s-comparacion`

![01-suricata](evidencias/20261103-0649-corrida11/capturas/01-suricata.png)

## Si algo sale distinto

- **La IP ya aparece en el firewall antes de empezar:** pulsa **Preparar demo** otra vez, o ejecuta `~/cf-demo/desbloquear.sh 10.10.20.30` en SRV-DMZ.
- **La barra se queda en «Actividad»:** el motor registra cada ventana de 10 s con unos segundos de retraso; espera hasta 60 s antes de repetir.
- **Aparece un LIMIT de 10.10.10.20 (DNS):** es infraestructura protegida. Se registra pero nunca se aplica, y el panel ya no lo cuenta como alerta (commit 0cc1125).
