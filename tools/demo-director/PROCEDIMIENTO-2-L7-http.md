# Escenario 2 · Abuso HTTP (flood) (L7 · Aplicación)

Procedimiento de la demo, en orden. Medido el 3-nov-2026 en la corrida 10.
Evidencia completa (comandos y salidas tal cual): `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\evidencias\20261103-0643-corrida10\EVIDENCIA.md`

- **IP seguida:** `10.10.20.30` → servidor `10.10.30.10` (srv-dmz)
- **Director:** `python director.py 03` (con `--auto` no hay que pulsar Enter)
- **Se espera:** LIMIT con caducidad, aplicado por el servidor
- **Qué decir:** «Cada petición es válida; lo anómalo es la tasa. LIMIT frena esa IP, no la corta.»

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
python director.py 03 --auto
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

`[LAPTOP navegador]` → lo haces tú (sesión iniciada en el panel): **Tarjeta «Abuso HTTP (flood)» → Iniciar seguimiento de 10.10.20.30**

- **Qué hace / qué dice:** Arranca el reloj y la barra guiada de 5 pasos.
- **GUI en paralelo:** barra · 1 Ataque

### 7. ORIGEN

`[KALI adminatacante]` → lo ejecuta el director en la consola ORIGEN de Herdr

```bash
seq 1 250 | xargs -P10 -I{} curl -s -o /dev/null -w '%{http_code} ' http://10.10.30.10/
```

- **Qué hace / qué dice:** ATAQUE: 250 peticiones web con 10 procesos en paralelo. Dice: 200 200 200… (cada petición es válida).
- **GUI en paralelo:** barra · 1 Ataque (reloj)

### 8. SENSOR1

`[SENSOR1 m4rk]` → lo ejecuta el director en la consola SENSOR1 de Herdr: **(mira-motor.sh sigue abierto)**

- **Qué hace / qué dice:** Aparece LIMIT · modelo + http_abuse (486 peticiones/60 s, sin patrón de fuerza bruta; score −0,642).
- **GUI en paralelo:** 2 Actividad → 3 Decisiones → 4 Respuestas

### 9. SRV-DMZ

`[SRV-DMZ adminsrvdmz]` → lo ejecuta el director en la consola SRV-DMZ de Herdr

```bash
~/cf-demo/en-firewall.sh 10.10.20.30
```

- **Qué hace / qué dice:** Consulta los sets de nftables. Dice: «LIMIT».
- **GUI en paralelo:** 5 Host · acuse de srv-dmz

### 10. ORIGEN

`[KALI adminatacante]` → lo ejecuta el director en la consola ORIGEN de Herdr

```bash
CON la regla: ping -q -c 150 -i 0.004 10.10.30.10 | tail -2
```

- **Qué hace / qué dice:** Dice: 35 % packet loss: LIMIT deja pasar 100 paquetes/s (frena, no corta).
- **GUI en paralelo:** — (solo CLI)

### 11. SRV-DMZ

`[SRV-DMZ adminsrvdmz]` → lo ejecuta el director en la consola SRV-DMZ de Herdr

```bash
~/cf-demo/desbloquear.sh 10.10.20.30
```

- **Qué hace / qué dice:** Revisión humana. Dice: «antes = LIMIT» → «tras liberar = NO».
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

- **Qué hace / qué dice:** Suricata: 44 alertas, ninguna firma de ataque (solo STREAM). CyberFlow: 6 ventanas LIMIT, aplicado 06:45:04.
- **GUI en paralelo:** #s-comparacion · tarjeta

## Resultado medido

| | |
|---|---|
| Respuesta | LIMIT · modelo + regla http_abuse |
| Detección | +00:25 desde el inicio del ataque |
| Publicación en el feed firmado | +00:31 |
| Aplicada en nftables de srv-dmz | +00:39 |
| Caducidad / nota | caduca sola (06:49) · reincidencia nivel 3 |
| Prueba en la CLI | ping a 250/s:  0 % → 35 % → 0 % de pérdida |
| Frente a Suricata | Suricata: 44 alertas, ninguna de ataque; CyberFlow: lo identifica y frena la tasa |

## Recorrido de la GUI

**actividad** · `#s-actividad`

![03-actividad](evidencias/20261103-0643-corrida10/capturas/03-actividad.png)

**aplicacion** · `#s-escenario · paso 5`

![03-aplicacion](evidencias/20261103-0643-corrida10/capturas/03-aplicacion.png)

**decisiones** · `#s-decisiones`

![03-decisiones](evidencias/20261103-0643-corrida10/capturas/03-decisiones.png)

**inicio** · `#s-escenario`

![03-inicio](evidencias/20261103-0643-corrida10/capturas/03-inicio.png)

**liberacion** · `#s-escenario · paso 5`

![03-liberacion](evidencias/20261103-0643-corrida10/capturas/03-liberacion.png)

**respuestas** · `#s-bloqueos`

![03-respuestas](evidencias/20261103-0643-corrida10/capturas/03-respuestas.png)

**suricata** · `#s-comparacion`

![03-suricata](evidencias/20261103-0643-corrida10/capturas/03-suricata.png)

## Si algo sale distinto

- **La IP ya aparece en el firewall antes de empezar:** pulsa **Preparar demo** otra vez, o ejecuta `~/cf-demo/desbloquear.sh 10.10.20.30` en SRV-DMZ.
- **La barra se queda en «Actividad»:** el motor registra cada ventana de 10 s con unos segundos de retraso; espera hasta 60 s antes de repetir.
- **Aparece un LIMIT de 10.10.10.20 (DNS):** es infraestructura protegida. Se registra pero nunca se aplica, y el panel ya no lo cuenta como alerta (commit 0cc1125).
