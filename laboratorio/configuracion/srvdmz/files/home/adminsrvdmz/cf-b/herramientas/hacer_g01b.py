#!/usr/bin/env python3
"""Deriva guiones/g01b_lanzar_bateria_b.sh del g01 v4 firmado de A con sustituciones exactas (cada una debe aplicarse una vez).
Uso: hacer_g01b.py <g01_lanzar_bateria_e4.sh> <salida>. rc 0 si todas las sustituciones se aplicaron."""
import sys

SUST = [
    # cabecera
    ("# [BASTIÓN gadmin] ETAPA4 g01 v4 (2026-11-09) —", "# [BASTIÓN gadmin] CAMPAÑA B g01b (derivado de g01 v4 de A; fase 4c) —"),
    # X2 -> P1: la vigilancia de srv-dmz de B tolera restricción SOLO sobre la Kali
    ('ESR="python3 -I ~/cf-e4/paquete/deploy/etapa4/srvdmz/estado_sombra.py --alcance completo --respaldo ~/respaldos-etapa4/$RSRV"',
     'ESR="python3 -I ~/cf-b/herramientas/d5_episodio.py srv-estado"   # B: rc 0 solo Kali/nada, 1 = P1 (otra IP), 2 = ilegible'),
    ('echo "## sombra (srv-dmz): estado_sombra.py --alcance completo"', 'echo "## srv-dmz (B): srv-estado (P1: ninguna restricción sobre IP distinta de la Kali)"'),
    ('PARAR: srv-dmz con indicios de aplicación (X2): revertir (PROCEDIMIENTO §7)', 'PARAR: restricción sobre una IP distinta de la Kali (P1): revertir (b_revertir_srvdmz.sh)'),
    ('PARAR: estado de srv-dmz DESCONOCIDO (lectura fallida): no se presume sombra', 'PARAR: estado de srv-dmz DESCONOCIDO (lectura fallida)'),
    ('  3) echo "PARAR: srv-dmz sin aplicación pero no conforme (v2 inactivo o v1 activo/habilitado)"; exit 2 ;;\n', '  3) echo "PARAR: srv-dmz no conforme"; exit 2 ;;\n'),
    # compuerta D5 entre el vigía y la Kali
    ('mkdir -p "$B/vigia"; chmod 0700 "$B/vigia"', 'mkdir -p "$B/vigia" "$B/compuerta"; chmod 0700 "$B/vigia"'),
    ('  --ssh-kali "ssh $CTL -o ConnectTimeout=10 kali" --orden-kali "$OK_"',
     '  --ssh-kali "python3 -I $HOME/cf-b/herramientas/compuerta_b.py filtro --dir $B/compuerta -- ssh $CTL -o ConnectTimeout=10 kali" --orden-kali "$OK_"'),
    # permiso ligado al episodio (cambio mínimo del generador, demostrado en el arnés de integración)
    ('compuerta_b.py filtro --dir $B/compuerta -- ssh', 'compuerta_b.py filtro --por-episodio --dir $B/compuerta -- ssh'),
    ('python3 -u \\$KS/generar_campana.py --config', 'python3 -u \\$KS/generar_campana_b.py --permiso-por-episodio --config'),
    # vigía B: misma lógica y reglas que el 2026-11-06.1 firmado, con la excepción de X3 acotada al NTP de la Kali
    ('echo "  vigía 2026-11-06.1 verificado en bastión y sensor1: $VGH"',
     'echo "  vigía 2026-11-06.1 verificado en bastión y sensor1: $VGH"\n'
     'VBH=a4b64381fc54313f   # vigia_4c_b.py (hacer_vigia_b.py): solo cambia X3 para el NTP de la Kali\n'
     '[ "$(sha256sum "$VG/vigia_4c_b.py" 2>/dev/null | cut -c1-16)" = "$VBH" ] || { echo "PARAR: vigia_4c_b.py del BASTIÓN ausente o con hash distinto"; exit 2; }\n'
     'S1B=$(ssh -n -o BatchMode=yes sensor1 \'sha256sum ~/cf-e4/vigia-20261106/vigia_4c_b.py 2>/dev/null | cut -c1-16\')\n'
     '[ "$S1B" = "$VBH" ] || { echo "PARAR: vigia_4c_b.py del SENSOR1 ausente o con hash distinto (\'$S1B\')"; exit 2; }\n'
     'echo "  vigía B (excepción NTP acotada) verificado en bastión y sensor1: $VBH"'),
    ('vigia-20261106/vigia_4c.py sensor', 'vigia-20261106/vigia_4c_b.py sensor'),
    ('--origen 10.10.20.30 --journalctl', '--origen 10.10.20.30 --ntp-permitido 200.25.3.17 --journalctl'),
    ("{ echo 'PARAR: ya hay un generador'; exit 2; }\" || exit 2",
     "{ echo 'PARAR: ya hay un generador'; exit 2; }\n"
     "S=\\$(timedatectl show-timesync -p ServerAddress --value 2>/dev/null); echo servidor_NTP_de_la_Kali=\\$S\n"
     "[ \"\\$S\" = 200.25.3.17 ] || { echo 'PARAR: el servidor NTP de la Kali no es 200.25.3.17 (la excepción de X3 no lo cubriría)'; exit 2; }\" || exit 2"),
    # proceso de puerta antes del vigía
    ('setsid nohup python3 -I "$VG/vigia_4c.py" bucle',
     'setsid nohup python3 -I "$HOME/cf-b/herramientas/compuerta_b.py" puerta --dir "$B/compuerta" \\\n'
     '  --ssh-sensor "ssh -n -o BatchMode=yes sensor1" --ssh-srv "ssh -n -o BatchMode=yes srvdmz" \\\n'
     '  > "$B/compuerta/puerta.stdout" 2> "$B/compuerta/puerta.stderr" < /dev/null &\n'
     'echo $! > "$B/compuerta/puerta.pid"\n'
     'setsid nohup python3 -I "$VG/vigia_4c.py" bucle'),
    ('"$VG/vigia_4c.py" bucle', '"$VG/vigia_4c_b.py" bucle'),
    ('echo "## lanzado $(date -u +%FT%T.%3NZ); el canal', 'echo "  compuerta D5 PID $(cat "$B/compuerta/puerta.pid")"\necho "## lanzado $(date -u +%FT%T.%3NZ); el canal'),
]


def main(origen, salida):
    t = open(origen, encoding="utf-8").read()
    mal = []
    for a, b in SUST:
        if t.count(a) != 1:
            mal.append((t.count(a), a[:70]))
        t = t.replace(a, b, 1)
    open(salida, "w", encoding="utf-8", newline="\n").write(t)
    print("sustituciones: %d, fallidas: %s" % (len(SUST), mal or "ninguna"))
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
