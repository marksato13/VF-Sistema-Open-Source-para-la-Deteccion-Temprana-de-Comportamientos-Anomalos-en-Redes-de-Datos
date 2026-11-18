# Escenario 5 · Cliente legítimo intenso (L7 · Aplicación)

Procedimiento de la demo, en orden. Medido el 3-nov-2026 en la corrida 8 (capturas GUI: corrida 3).
Evidencia completa (comandos y salidas tal cual): `C:\Users\markp\Desktop\PY-MEGATRON\PY - PERSONAL\TESIS\CYBERFLOW\demo-director\evidencias\20261103-0448-corrida8\EVIDENCIA.md`

- **IP seguida:** `10.10.20.21` → servidor `10.10.30.10` (srv-dmz)
- **Director:** `python director.py 04` (con `--auto` no hay que pulsar Enter)
- **Se espera:** PERMIT en todo: ninguna acción
- **Qué decir:** «Uso intenso no es ataque. Aquí CyberFlow no debe actuar, y no actúa.»

## Antes de empezar

1. Herdr abierto en el espacio **CYBERFLOW DEMO**, con las 5 consolas: ORIGEN, SENSOR1, SRV-DMZ, BASTIÓN y DIRECTOR. Si falta, desde la consola DIRECTOR ejecuta `python montar.py`.
2. En Chrome, abre el panel `https://vm-gestion.tail83bf9c.ts.net:8788/#s-escenario`, pulsa **Ctrl+F5** y luego **Preparar demo**. Espera «Listo para la demo» con los 6 checks en verde.

## Paso a paso

Cada comando lo escribe el director en su consola de Herdr; tú hablas y vas al panel. Si lo haces a mano, ejecuta cada comando en la consola indicada.

### 1. Chrome

`[LAPTOP navegador]` → lo haces tú (sesión iniciada en el panel): **Panel · Escenario en vivo → «Preparar demo»**

- **Qué hace / qué dice:** Libera la Kali y el cliente y comprueba 6 puntos: «Listo para la demo».
- **GUI en paralelo:** #s-escenario · 6 checks

### 2. DIRECTOR

`[LAPTOP PowerShell]` → lo ejecutas tú en la consola DIRECTOR de Herdr

```bash
python director.py 04 --auto
```

- **Qué hace / qué dice:** Arranca el guion del escenario legítimo.
- **GUI en paralelo:** —

### 3. SENSOR1

`[SENSOR1 m4rk]` → lo ejecuta el director en la consola SENSOR1 de Herdr

```bash
~/cf-demo/mira-motor.sh 10.10.20.21
```

- **Qué hace / qué dice:** Una línea por ventana. Dice: PERMIT · score −0,50 / −0,52 (normal).
- **GUI en paralelo:** «Ventanas de la IP»

### 4. SRV-DMZ

`[SRV-DMZ adminsrvdmz]` → lo ejecuta el director en la consola SRV-DMZ de Herdr

```bash
~/cf-demo/mira-agente.sh 10.10.20.21
```

- **Qué hace / qué dice:** Dice: «sin regla (pasa libre)».
- **GUI en paralelo:** paso 5 «Host»

### 5. ORIGEN

`[CLIENTES adminclientes]` → lo ejecuta el director en la consola ORIGEN de Herdr

```bash
ANTES: curl -s -o /dev/null -m 4 -w 'HTTP %{http_code} en %{time_total}s\n' --interface 10.10.20.21 http://10.10.30.10/
```

- **Qué hace / qué dice:** Dice: HTTP 200 en 0,002 s.
- **GUI en paralelo:** — (solo CLI)

### 6. Chrome

`[LAPTOP navegador]` → lo haces tú (sesión iniciada en el panel): **Tarjeta «Cliente legítimo intenso» → Iniciar seguimiento de 10.10.20.21**

- **Qué hace / qué dice:** Reloj y barra guiada.
- **GUI en paralelo:** barra · 1 Ataque

### 7. ORIGEN

`[CLIENTES adminclientes]` → lo ejecuta el director en la consola ORIGEN de Herdr

```bash
for i in $(seq 1 60); do curl -s -o /dev/null --interface 10.10.20.21 http://10.10.30.10/; printf .; sleep 2; done; echo fin
```

- **Qué hace / qué dice:** CARGA: 60 páginas, una cada 2 s, durante 2 minutos: uso intenso pero humano.
- **GUI en paralelo:** barra · 1 (reloj)

### 8. SENSOR1

`[SENSOR1 m4rk]` → lo ejecuta el director en la consola SENSOR1 de Herdr: **(mira-motor.sh sigue abierto)**

- **Qué hace / qué dice:** Todo PERMIT: 12 ventanas, 0 con acción. Las 9 marginales del modelo quedan sin acción.
- **GUI en paralelo:** 2 Actividad → 3 Decisiones: todo PERMIT

### 9. SRV-DMZ

`[SRV-DMZ adminsrvdmz]` → lo ejecuta el director en la consola SRV-DMZ de Herdr

```bash
~/cf-demo/en-firewall.sh 10.10.20.21
```

- **Qué hace / qué dice:** Dice: «NO»: la IP no está en el firewall.
- **GUI en paralelo:** 5 Host: sin regla

### 10. ORIGEN

`[CLIENTES adminclientes]` → lo ejecuta el director en la consola ORIGEN de Herdr

```bash
DESPUÉS: curl -s -o /dev/null -m 4 -w 'HTTP %{http_code} en %{time_total}s\n' --interface 10.10.20.21 http://10.10.30.10/
```

- **Qué hace / qué dice:** Dice: HTTP 200 en 0,002 s: el cliente sigue atendido.
- **GUI en paralelo:** — (solo CLI)

### 11. BASTIÓN

`[BASTIÓN gadmin]` → lo ejecuta el director en la consola BASTIÓN de Herdr

```bash
~/cf-demo/comparar-suricata.sh 10.10.20.21 <inicio> <fin>
```

- **Qué hace / qué dice:** Corrida 3: Suricata 35 alertas (flujo/informativas) que alguien revisaría. CyberFlow: 0 de 23 ventanas.
- **GUI en paralelo:** #s-comparacion

## Resultado medido

| | |
|---|---|
| Respuesta | PERMIT · 12 ventanas, 0 con acción |
| Caducidad / nota | 9 anomalías marginales del modelo: sin acción |
| Prueba en la CLI | curl:  HTTP 200 antes y después · en-firewall = NO |
| Frente a Suricata | Suricata: 35 alertas de flujo/informativas; CyberFlow: 0 acciones (no molesta al usuario) |

## Recorrido de la GUI

**actividad** · `#s-actividad`

![04-actividad](evidencias/20261103-0214-corrida3/capturas/04-actividad.png)

**decisiones** · `#s-decisiones`

![04-decisiones](evidencias/20261103-0214-corrida3/capturas/04-decisiones.png)

**inicio** · `#s-escenario`

![04-inicio](evidencias/20261103-0214-corrida3/capturas/04-inicio.png)

**suricata** · `#s-comparacion`

![04-suricata](evidencias/20261103-0214-corrida3/capturas/04-suricata.png)

> Las capturas de la GUI de este escenario son de la corrida 3 (antes de la política A); el resultado fue el mismo: todo PERMIT. La corrida 8 confirmó 12 ventanas y 0 acciones.

## Si algo sale distinto

- **La IP ya aparece en el firewall antes de empezar:** pulsa **Preparar demo** otra vez, o ejecuta `~/cf-demo/desbloquear.sh 10.10.20.21` en SRV-DMZ.
- **La barra se queda en «Actividad»:** el motor registra cada ventana de 10 s con unos segundos de retraso; espera hasta 60 s antes de repetir.
- **Aparece un LIMIT de 10.10.10.20 (DNS):** es infraestructura protegida. Se registra pero nunca se aplica, y el panel ya no lo cuenta como alerta (commit 0cc1125).
