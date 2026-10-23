"""Los eventos DNS se leen con la forma que Suricata produce de verdad.

**Como se rompio.** El extractor comparaba ``dns.type`` contra "request" y
"response". Suricata emite "query" y "answer". Las tres variables de DNS
-``dns_query_rate_60s``, ``unique_dns_name_ratio_60s`` y
``dns_nxdomain_ratio_60s``- salieron a cero en todos los datasets construidos
hasta ahora, incluido aquel con el que se entreno el modelo publicado.

**Por que nadie lo vio.** Las pruebas que ya existian construian sus eventos con
"request" y "response": comprobaban lo que el parser suponia. Pasaban en verde
mientras el sistema no media nada.

**Por eso este fichero es distinto.** Los eventos de abajo estan copiados tal
cual de ``/var/log/suricata/eve.json`` del sensor, con su ``version: 2``, su
``rcode`` y sus ``authorities``. Si el formato cambia con una version futura de
Suricata, estas pruebas fallan; si se escribieran a mano, volverian a pasar
mientras la medicion vuelve a ser cero.
"""

from __future__ import annotations

import importlib.util
import ipaddress
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "extract_multilayer_v2", REPO / "scripts/features/extract_multilayer_v2.py")
assert SPEC and SPEC.loader
v2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = v2
SPEC.loader.exec_module(v2)

RED = ipaddress.ip_network("10.10.0.0/16")

# Copiados literalmente del sensor (24-sep-2026). No reescribir a mano.
CONSULTA = (
    '{"timestamp":"2026-09-24T21:15:51.133027+0000","flow_id":2250822248552362,'
    '"in_iface":"ens37","event_type":"dns","vlan":[10],"src_ip":"10.10.20.56",'
    '"src_port":49670,"dest_ip":"10.10.10.20","dest_port":53,"proto":"TCP",'
    '"pkt_src":"wire/pcap","dns":{"type":"query","id":37962,'
    '"rrname":"www.bing.com","rrtype":"A","tx_id":0,"opcode":0}}'
)
RESPUESTA_NXDOMAIN = (
    '{"timestamp":"2026-09-24T20:30:12.337551+0000","flow_id":1167185319803227,'
    '"in_iface":"ens37","event_type":"dns","vlan":[10],"src_ip":"10.10.10.20",'
    '"src_port":46804,"dest_ip":"10.10.10.1","dest_port":53,"proto":"UDP",'
    '"pkt_src":"wire/pcap","dns":{"version":2,"type":"answer","id":13846,'
    '"flags":"8183","qr":true,"rd":true,"ra":true,"opcode":0,'
    '"rrname":"intranet.francos-sac.com","rrtype":"A","rcode":"NXDOMAIN",'
    '"authorities":[{"rrname":"com","rrtype":"SOA","ttl":631,'
    '"soa":{"mname":"a.gtld-servers.net","rname":"nstld.verisign-grs.com",'
    '"serial":1790281529,"refresh":1800,"retry":900,"expire":604800,'
    '"minimum":900}}]}}'
)
RESPUESTA_NOERROR = RESPUESTA_NXDOMAIN.replace('"NXDOMAIN"', '"NOERROR"')


class EventosRealesDeSuricata(unittest.TestCase):
    def cargar(self, *lineas: str):
        with tempfile.TemporaryDirectory() as tmp:
            eve = Path(tmp) / "eve.json"
            eve.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
            return v2.load_app_observations(eve, RED)

    def test_una_consulta_real_produce_observacion(self):
        obs = self.cargar(CONSULTA)
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].kind, "dns_query")
        self.assertEqual(obs[0].entity_ip, "10.10.20.56")
        self.assertEqual(obs[0].dns_name, "www.bing.com")

    def test_una_respuesta_nxdomain_real_produce_observacion(self):
        obs = self.cargar(RESPUESTA_NXDOMAIN)
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].kind, "dns_nxdomain")
        # A src_ip, no a dest_ip: Suricata registra la respuesta con las
        # direcciones del FLUJO, asi que src sigue siendo quien pregunto. En el
        # evento real de arriba, 10.10.10.20 pregunto a 10.10.10.1 y recibio
        # NXDOMAIN; apuntarselo a 10.10.10.1 seria culpar al servidor.
        self.assertEqual(obs[0].entity_ip, "10.10.10.20")

    def test_consulta_y_respuesta_caen_en_la_MISMA_entidad(self):
        # Es la condicion para que dns_nxdomain_ratio_60s pueda valer algo: si
        # el numerador y el denominador se reparten entre dos entidades, el
        # ratio sale cero en las dos. Asi estaba: los 567 NXDOMAIN de la
        # muestra real caian en una entidad con cero consultas.
        consulta = CONSULTA.replace('"src_ip":"10.10.20.56"', '"src_ip":"10.10.10.20"') \
                           .replace('"dest_ip":"10.10.10.20"', '"dest_ip":"10.10.10.1"')
        obs = self.cargar(consulta, RESPUESTA_NXDOMAIN)
        self.assertEqual({o.entity_ip for o in obs}, {"10.10.10.20"})
        self.assertEqual({o.kind for o in obs}, {"dns_query", "dns_nxdomain"})

    def test_una_respuesta_correcta_no_cuenta_como_nxdomain(self):
        self.assertEqual(self.cargar(RESPUESTA_NOERROR), [])

    def test_los_nombres_antiguos_ya_no_se_aceptan(self):
        # "request"/"response" no los emite Suricata: aceptarlos manteria viva
        # la ficcion que causo el fallo. Si alguien los reintroduce, esta
        # prueba lo dice.
        falso = CONSULTA.replace('"type":"query"', '"type":"request"')
        self.assertEqual(self.cargar(falso), [])
        self.assertNotIn("request", v2._DNS_CONSULTA)
        self.assertNotIn("response", v2._DNS_RESPUESTA)


class LasTresVariablesDejanDeSerCero(unittest.TestCase):
    """Sin esto, el arreglo podria deshacerse sin que ninguna prueba chillara."""

    def test_el_dataset_recoge_dns(self):
        with tempfile.TemporaryDirectory() as tmp:
            eve = Path(tmp) / "eve.json"
            lineas = []
            for i in range(30):
                lineas.append(CONSULTA.replace("21:15:51.133027", "21:15:%02d.000000" % (10 + i))
                                      .replace("www.bing.com", "host%d.ejemplo.com" % i))
            eve.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
            apps = v2.load_app_observations(eve, RED)

        self.assertEqual(len(apps), 30)
        filas = v2.build_rows("prueba", [], apps)
        self.assertTrue(filas)
        # La consulta esta en el dataset: al menos una ventana con ritmo > 0.
        ritmos = [f["dns_query_rate_60s"] for f in filas]
        self.assertGreater(max(ritmos), 0.0,
                           "dns_query_rate_60s sigue a cero: el arreglo no llego")
        nombres = [f["unique_dns_name_ratio_60s"] for f in filas]
        self.assertGreater(max(nombres), 0.0,
                           "unique_dns_name_ratio_60s sigue a cero")


if __name__ == "__main__":
    unittest.main()
