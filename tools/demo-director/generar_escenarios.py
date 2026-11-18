"""Genera escenarios/NN-*/escenario.yaml siguiendo el recorrido guiado del panel (3-nov):

  ATAQUE (consola ORIGEN) → ACTIVIDAD (la IP aparece; clic) → DECISIONES (quién y por qué)
  → RESPUESTAS (orden firmada con caducidad) → HOST (consola SRV-DMZ: la IP en nftables)
  → pruebas antes / con / después → liberación humana → Suricata con evidencia.

El caso legítimo (04) sigue el mismo recorrido pero su hito es «sin_accion»: debe quedar en PERMIT.

Campos de cada paso:
  explica        lo que se dice (corto)
  procedimiento  qué hace el comando, opción por opción (va al .md de evidencia)
  gui            dónde se ve ESE paso en el panel web (sección #s-…)
  captura        el director pide una captura del panel en este paso

Uso: python generar_escenarios.py
"""
from pathlib import Path

import yaml

AQUI = Path(__file__).resolve().parent
SRV = "10.10.30.10"

PING_PROC = ("`ping -q` solo imprime el resumen; `-c 150` 150 paquetes ICMP; `-i 0.004` uno cada 4 ms (250/s, más "
             "que los 100/s que deja pasar LIMIT); `| tail -2` las dos líneas del resumen. Sin regla = 0 % de pérdida; "
             "LIMIT = se pierde lo que pasa de 100/s; BLOCK = 100 %.")
NMAP_VERIF_PROC = ("`-n` sin DNS; `-Pn` sin ping previo; `--max-retries 0 --host-timeout 8s` una sonda y se rinde en "
                   "8 s; `-p80,443` solo web. «open» = el servidor contesta; «filtered» = el firewall lo descarta.")
CURL_VERIF = "curl -s -o /dev/null -m 4 -w 'HTTP %{http_code} en %{time_total}s\\n' --interface 10.10.20.21 http://10.10.30.10/"


def prueba(ip_origen=None):
    extra = " -I %s" % ip_origen if ip_origen else ""
    return "ping -q -c 150 -i 0.004%s %s | tail -2" % (extra, SRV)


def comunes_inicio(ip, intro, tarjeta, verif, verif_espera, verif_explica, verif_proc, esperado_antes):
    return [
        {"tipo": "decir", "texto": intro, "gui": "#s-escenario · tarjeta «%s»" % tarjeta},
        {"tipo": "ejecutar", "panel": "sensor", "comando": "~/cf-demo/mira-motor.sh {ip}",
         "explica": "SENSOR1: el motor en vivo para %s, una línea por ventana de 10 s." % ip,
         "procedimiento": "Lee la cola de ~/cyberflow/logs/motor_decision.log (solo lectura) y muestra por ventana: "
                          "hora, score frente al umbral, decisión y, si salta, la regla con su motivo.",
         "gui": "#s-escenario · «Ventanas de la IP»"},
        {"tipo": "ejecutar", "panel": "srvdmz", "comando": "~/cf-demo/mira-agente.sh {ip}",
         "explica": "SRV-DMZ: el servidor protegido por dentro: agente activo, orden recibida y su firewall.",
         "procedimiento": "Cada 2 s: temporizador ppi-enforce-agent, feed firmado recibido, orden para la IP, "
                          "liberación humana y los sets de nftables `inet cyberflow` (solo lectura).",
         "gui": "#s-escenario · paso 5 «Host»"},
        {"tipo": "ejecutar", "panel": "origen", "comando": verif, "espera": verif_espera,
         "explica": "ANTES: %s. %s" % (verif_explica, esperado_antes), "procedimiento": verif_proc,
         "gui": "— solo CLI: la prueba la hace el origen"},
        {"tipo": "panel", "ruta": "#s-escenario · tarjeta «%s» → Iniciar seguimiento de %s" % (tarjeta, ip),
         "explica": "En el panel: Iniciar. Aparece la barra guiada abajo con los 5 pasos.",
         "gui": "#s-escenario + barra guiada (paso 1 Ataque)", "captura": "inicio"},
    ]


def escenario(titulo, capa, tipo, ip, origen, tarjeta, panel_id, intro, ataque, explica_ataque, proc_ataque,
              det_txt, cierre, max_det=150, verif=None, verif_explica=None, verif_espera="packet loss",
              verif_proc=None, esperado_antes="Debe salir 0 % de pérdida.",
              esperado_con="BLOCK = 100 % de pérdida; LIMIT = solo pasan 100 paquetes/s.",
              esperado_despues="vuelve a 0 % de pérdida."):
    verif = verif or prueba(ip if origen == "clientes" else None)
    verif_explica = verif_explica or "150 pings a 250/s al servidor"
    verif_proc = verif_proc or PING_PROC
    pasos = comunes_inicio(ip, intro, tarjeta, verif, verif_espera, verif_explica, verif_proc, esperado_antes) + [
        {"tipo": "ataque", "panel": "origen", "comando": ataque, "explica": explica_ataque,
         "procedimiento": proc_ataque, "gui": "barra guiada · 1 Ataque (reloj en marcha)"},
        {"tipo": "esperar", "hito": "deteccion", "max": max_det, "explica": det_txt,
         "gui": "barra guiada · 2 Actividad"},
        {"tipo": "panel", "ruta": "#s-actividad · fila de %s (resaltada) → clic" % ip,
         "explica": "ACTIVIDAD: la IP sube entre las entidades con su acción. Clic en ella.",
         "gui": "#s-actividad · tabla de entidades", "captura": "actividad"},
        {"tipo": "panel", "ruta": "#s-decisiones · filtrada por %s" % ip,
         "explica": "DECISIONES: ventana por ventana, quién lo detecta (modelo, regla o ambos) y por qué.",
         "gui": "#s-decisiones (filtro = la IP)", "captura": "decisiones"},
        {"tipo": "esperar", "hito": "publicacion", "max": 60,
         "explica": "El sensor publica la orden en el feed firmado, con caducidad. No toca el servidor.",
         "gui": "barra guiada · 4 Respuestas"},
        {"tipo": "panel", "ruta": "#s-bloqueos · fila de %s" % ip,
         "explica": "RESPUESTAS: la orden publicada, su detector y cuándo caduca.",
         "gui": "#s-bloqueos", "captura": "respuestas"},
        {"tipo": "esperar", "hito": "aplicacion", "max": 60,
         "explica": "El agente de srv-dmz trae el feed, verifica la firma y pone la IP en nftables.",
         "gui": "barra guiada · 5 Host (acuse de srv-dmz)", "captura": "aplicacion"},
        {"tipo": "ejecutar", "panel": "srvdmz", "si": "aplicada", "comando": "~/cf-demo/en-firewall.sh {ip}",
         "espera": "", "explica": "HOST (CLI): la IP está en el set de nftables del servidor.",
         "procedimiento": "Consulta los sets `bloqueadas` y `limitadas` de la tabla `inet cyberflow` (solo lectura). "
                          "Imprime BLOCK, LIMIT o NO.",
         "gui": "barra guiada · 5 Host"},
        {"tipo": "ejecutar", "panel": "origen", "si": "aplicada", "comando": verif, "espera": verif_espera,
         "explica": "CON la regla: " + esperado_con, "procedimiento": verif_proc, "gui": "— solo CLI"},
        {"tipo": "ejecutar", "panel": "srvdmz", "si": "aplicada", "comando": "~/cf-demo/desbloquear.sh {ip}",
         "espera": "tras liberar",
         "explica": "Revisión humana: un comando en el servidor libera la IP.",
         "procedimiento": "Llama al agente con `--liberar IP`: quita la IP de los dos sets y anota la liberación "
                          "(por detector) con 120 s de gracia para la cola del mismo episodio. Una orden nueva sí se "
                          "aplica.",
         "gui": "#s-escenario · paso 5 «liberada por revisión humana»", "captura": "liberacion"},
        {"tipo": "ejecutar", "panel": "origen", "si": "aplicada", "comando": verif, "espera": verif_espera,
         "explica": "DESPUÉS de liberar: " + esperado_despues, "procedimiento": verif_proc, "gui": "— solo CLI"},
        {"tipo": "comparar",
         "explica": "El mismo tráfico frente a Suricata 7 + ET Open (53 013 firmas). Suricata alerta; CyberFlow "
                    "decide y responde.",
         "procedimiento": "comparar-suricata.sh: (1) recorta del anillo PCAP del sensor la IP y el intervalo del "
                          "ataque; (2) lo copia a la VM 10.10.60.13; (3) `suricata -r` con todas las firmas; "
                          "(4) cuenta las ventanas de CyberFlow del mismo intervalo y el acuse del host. Deja "
                          "fast.log en la VM y el resumen en sensor1:~/feed/comparaciones/.",
         "gui": "#s-comparacion · tarjeta de esta comparación", "captura": "suricata"},
        {"tipo": "decir", "texto": cierre, "gui": "barra guiada · 5/5 en verde"},
    ]
    return {"titulo": titulo, "capa": capa, "tipo": tipo, "ip": ip, "origen": origen, "tarjeta_panel": tarjeta,
            "panel_id": panel_id, "pasos": pasos}


def legitimo():
    ip, tarjeta = "10.10.20.21", "Cliente legítimo intenso"
    verif = CURL_VERIF
    proc_v = ("`-m 4` se rinde a los 4 s; `-w` imprime el código HTTP y el tiempo; `--interface` sale con la IP del "
              "cliente. HTTP 200 = el servidor le atiende.")
    pasos = comunes_inicio(ip, "Un usuario legítimo que usa mucho la web. No es un ataque: CyberFlow NO debe actuar.",
                           tarjeta, verif, "HTTP", "una petición web desde el cliente", proc_v,
                           "Debe salir HTTP 200.") + [
        {"tipo": "ataque", "panel": "origen",
         "comando": "for i in $(seq 1 60); do curl -s -o /dev/null --interface 10.10.20.21 http://10.10.30.10/; "
                    "printf .; sleep 2; done; echo fin",
         "explica": "60 páginas, una cada 2 s, durante 2 minutos: uso intenso pero humano.",
         "procedimiento": "`for … seq 1 60` repite 60 veces; `curl -s -o /dev/null` pide la página y la descarta; "
                          "`--interface 10.10.20.21` sale con la IP del cliente; `sleep 2` una cada 2 s; `printf .` "
                          "un punto por petición.",
         "gui": "barra guiada · 1 Tráfico (reloj en marcha)"},
        {"tipo": "esperar", "hito": "sin_accion", "max": 130,
         "explica": "Dos minutos observando: la IP debe seguir en PERMIT, fuera del feed y del firewall.",
         "gui": "barra guiada · pasos en verde «sin acción»"},
        {"tipo": "panel", "ruta": "#s-actividad · fila de %s (PERMIT)" % ip,
         "explica": "ACTIVIDAD: la IP aparece con tráfico, pero sin acción.",
         "gui": "#s-actividad", "captura": "actividad"},
        {"tipo": "panel", "ruta": "#s-decisiones · filtrada por %s" % ip,
         "explica": "DECISIONES: ventanas PERMIT; si el modelo duda, queda como «marginal · sin acción».",
         "gui": "#s-decisiones (filtro = la IP)", "captura": "decisiones"},
        {"tipo": "ejecutar", "panel": "srvdmz", "comando": "~/cf-demo/en-firewall.sh {ip}", "espera": "",
         "explica": "HOST (CLI): la IP NO está en el firewall.",
         "procedimiento": "Consulta los sets de `inet cyberflow` (solo lectura). Debe imprimir NO.",
         "gui": "barra guiada · 5 Host"},
        {"tipo": "ejecutar", "panel": "origen", "comando": verif, "espera": "HTTP",
         "explica": "El cliente sigue atendido: HTTP 200.", "procedimiento": proc_v, "gui": "— solo CLI"},
        {"tipo": "comparar",
         "explica": "El mismo tráfico frente a Suricata: ¿algún IDS lo habría marcado?",
         "procedimiento": "comparar-suricata.sh con el intervalo del tráfico del cliente (mismo método que en los "
                          "ataques).",
         "gui": "#s-comparacion · tarjeta del cliente legítimo", "captura": "suricata"},
        {"tipo": "decir",
         "texto": "Uso intenso no es ataque: ni regla ni modelo sostenido. Así se evitan falsos positivos.",
         "gui": "#s-escenario · tarjeta en verde «PERMIT»"},
    ]
    return {"titulo": "Legítimo · Cliente intenso (debe quedar en PERMIT)", "capa": "L7 · Aplicación",
            "tipo": "tráfico legítimo", "ip": ip, "origen": "clientes", "tarjeta_panel": tarjeta, "panel_id": "fp",
            "pasos": pasos}


HTTP_PROC = ("`seq 1 250` 250 números; `xargs -P10` 10 curl a la vez; `curl -s -o /dev/null -w '%{http_code} '` "
             "descarta la página e imprime el código (200 = petición válida). Lo anómalo es la tasa.")

ESC = {
    "01-L3-icmp": escenario(
        "L3 · Inundación ICMP", "L3 · Red", "ataque", "10.10.20.30", "kali", "Inundación ICMP", "l3",
        "Capa de red: un torrente de ICMP, sin puertos ni aplicación. Lo ven la regla icmp_flood y el modelo.",
        "for k in 1 2 3 4; do ping -q -i 0.002 -s 1200 -w 60 10.10.30.10 >/dev/null & done; wait; echo fin",
        "4 pings en paralelo durante 60 s: unos 2000 paquetes/s.",
        "`for k in 1 2 3 4 … & done; wait` 4 ping en paralelo; `-i 0.002` uno cada 2 ms (mínimo sin root); "
        "`-s 1200` paquetes de 1200 bytes; `-w 60` dura 60 s. ≈ 2000 paquetes/s, ≈ 19 Mbit/s.",
        "Regla icmp_flood (≥ 200 paquetes/s casi todo ICMP) y modelo coinciden: BLOCK.",
        "El modelo ve el volumen anómalo y la regla lo confirma: el host lo corta.", max_det=120),
    "02-L7-dga": escenario(
        "L7 · DNS de alta entropía (DGA)", "L7 · Aplicación", "ataque", "10.10.20.30", "kali",
        "DNS de alta entropía (DGA)", "l7dns",
        "Malware que busca su servidor de control con nombres aleatorios (DGA).",
        "for i in $(seq 1 80); do r=$(head -c6 /dev/urandom | od -An -tx1 | tr -d ' \\n'); "
        "dig +short ${r}.francos-sac.com @10.10.10.20 >/dev/null 2>&1; printf .; sleep 0.5; done; echo",
        "80 consultas a nombres aleatorios, una cada medio segundo.",
        "`head -c6 /dev/urandom | od | tr` 12 hex al azar; `dig +short <azar>.francos-sac.com @10.10.10.20` al DNS "
        "del laboratorio (NXDOMAIN); 80 veces, una cada 0,5 s.",
        "La regla de entropía DNS lo marca.", "Modelo y reglas se complementan."),
    "03-L7-http": escenario(
        "L7 · Abuso HTTP (flood)", "L7 · Aplicación", "ataque", "10.10.20.30", "kali", "Abuso HTTP (flood)", "l7",
        "Capa de aplicación: cientos de peticiones válidas en segundos, como un bot. Lo anómalo es la tasa.",
        "seq 1 250 | xargs -P10 -I{} curl -s -o /dev/null -w '%{http_code} ' http://10.10.30.10/ ; echo",
        "250 peticiones con 10 procesos en paralelo.", HTTP_PROC,
        "La regla http_abuse (≥100 peticiones reales/min de una IP) lo marca: LIMIT.",
        "Respuesta proporcional: LIMIT temporal, no corte total; un humano puede liberarlo."),
    "04-legitimo": legitimo(),
    "05-L4-escaneo": escenario(
        "L4 · Escaneo de puertos", "L4 · Transporte", "ataque", "10.10.20.30", "kali", "Escaneo de puertos", "l4",
        "Capa de transporte: prueba miles de puertos TCP para ver cuáles están abiertos. Primer paso de una intrusión.",
        "nmap -sT -T4 --max-retries 1 -p 1-3000 --open 10.10.30.10",
        "3000 puertos TCP a ritmo agresivo. El sensor ve una copia del tráfico (espejo).",
        "`-sT` TCP connect (sin root); `-T4` agresivo; `--max-retries 1` un reintento; `-p 1-3000` puertos 1–3000; "
        "`--open` solo lista los abiertos.",
        "Regla port_scan (muchos puertos distintos) y modelo coinciden: BLOCK.",
        "Detección más fuerte: modelo y regla. BLOCK con caducidad; corta el host, no el sensor.",
        max_det=180, verif="nmap -n -Pn --max-retries 0 --host-timeout 8s -p80,443 10.10.30.10",
        verif_explica="nmap a los puertos 80 y 443", verif_proc=NMAP_VERIF_PROC,
        verif_espera="Nmap done", esperado_antes="80 y 443 deben salir «open».",
        esperado_con="80 y 443 salen «filtered»: el servidor ya no le contesta.",
        esperado_despues="vuelve a «open»."),
}

viejo = AQUI / "escenarios" / "04-falso-positivo"
if viejo.exists():
    for f in viejo.iterdir():
        f.unlink()
    viejo.rmdir()
for carpeta, e in ESC.items():
    d = AQUI / "escenarios" / carpeta
    d.mkdir(parents=True, exist_ok=True)
    (d / "escenario.yaml").write_text(yaml.safe_dump(e, allow_unicode=True, sort_keys=False, width=110),
                                      encoding="utf-8", newline="\n")
    print(carpeta, len(e["pasos"]), "pasos")
