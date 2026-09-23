"""Las tres features de capa 2 y la garantía de que v3 no altera a v2."""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import socket
import struct
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/features/extract_multilayer_v3.py"
SPEC = importlib.util.spec_from_file_location("extract_multilayer_v3", MODULE_PATH)
assert SPEC and SPEC.loader
extractor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = extractor
SPEC.loader.exec_module(extractor)

v2 = extractor.v2

RED = ipaddress.ip_network("10.10.0.0/16")
MAC_CLIENTE = "aa:bb:cc:00:00:21"
MAC_OTRA = "aa:bb:cc:99:99:99"
MAC_FIREWALL = "00:50:56:00:00:01"
CLIENTE = "10.10.20.21"
SERVIDOR = "10.10.30.10"


def mac_bytes(mac: str) -> bytes:
    return bytes.fromhex(mac.replace(":", ""))


def trama(destino: str, origen: str, vlan: int, ethertype: int, carga: bytes) -> bytes:
    cabecera = mac_bytes(destino) + mac_bytes(origen)
    if vlan:
        cabecera += struct.pack("!HHH", 0x8100, vlan, ethertype)
    else:
        cabecera += struct.pack("!H", ethertype)
    return cabecera + carga


def arp(mac_emisor: str, ip_emisor: str, ip_destino: str, opcode: int = 1,
        hw_len: int = 6, proto_len: int = 4) -> bytes:
    return (
        struct.pack("!HHBBH", 1, 0x0800, hw_len, proto_len, opcode)
        + mac_bytes(mac_emisor)
        + socket.inet_aton(ip_emisor)
        + b"\x00" * 6
        + socket.inet_aton(ip_destino)
    )


def tcp(puerto_origen: int, puerto_destino: int, banderas: int, seq: int = 1) -> bytes:
    return struct.pack(
        "!HHIIBBHHH", puerto_origen, puerto_destino, seq, 0, 0x50, banderas, 8192, 0, 0
    )


def ipv4(origen: str, destino: str, transporte: bytes, protocolo: int = 6,
         ip_id: int = 1, ttl: int = 64) -> bytes:
    total = 20 + len(transporte)
    cabecera = struct.pack(
        "!BBHHHBBH4s4s", 0x45, 0, total, ip_id, 0x4000, ttl, protocolo, 0,
        socket.inet_aton(origen), socket.inet_aton(destino),
    )
    return cabecera + transporte


def escribir_pcap(ruta: Path, tramas: list[tuple[float, bytes]]) -> None:
    with ruta.open("wb") as handle:
        handle.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for marca, cuerpo in tramas:
            segundos = int(marca)
            micros = round((marca - segundos) * 1_000_000)
            handle.write(struct.pack("<IIII", segundos, micros, len(cuerpo), len(cuerpo)))
            handle.write(cuerpo)


def iso(marca: float) -> str:
    return datetime.fromtimestamp(marca, timezone.utc).isoformat()


class ParseoDeTramas(unittest.TestCase):
    def test_peticion_arp_etiquetada(self) -> None:
        cuerpo = trama("ff:ff:ff:ff:ff:ff", MAC_CLIENTE, 20, 0x0806,
                       arp(MAC_CLIENTE, CLIENTE, "10.10.20.99"))
        obs = extractor.parse_ethernet_l2(100.0, cuerpo)
        assert obs is not None
        self.assertEqual(obs.vlan, 20)
        self.assertEqual(obs.src_mac, MAC_CLIENTE)
        self.assertEqual(obs.sender_ip, CLIENTE)
        self.assertTrue(obs.arp_request)

    def test_respuesta_arp_no_cuenta_como_peticion(self) -> None:
        cuerpo = trama(MAC_FIREWALL, MAC_CLIENTE, 20, 0x0806,
                       arp(MAC_CLIENTE, CLIENTE, "10.10.20.1", opcode=2))
        obs = extractor.parse_ethernet_l2(100.0, cuerpo)
        assert obs is not None
        self.assertFalse(obs.arp_request)

    def test_ipv4_sin_etiqueta_da_vlan_cero(self) -> None:
        cuerpo = trama(MAC_FIREWALL, MAC_CLIENTE, 0, 0x0800,
                       ipv4(CLIENTE, SERVIDOR, tcp(1234, 80, 0x02)))
        obs = extractor.parse_ethernet_l2(100.0, cuerpo)
        assert obs is not None
        self.assertEqual(obs.vlan, 0)
        self.assertEqual(obs.sender_ip, CLIENTE)
        self.assertFalse(obs.arp_request)

    def test_qinq_se_queda_con_la_etiqueta_exterior(self) -> None:
        interior = struct.pack("!HHH", 0x8100, 30, 0x0800) + ipv4(
            CLIENTE, SERVIDOR, tcp(1234, 80, 0x02)
        )
        cuerpo = mac_bytes(MAC_FIREWALL) + mac_bytes(MAC_CLIENTE) + struct.pack(
            "!HH", 0x88A8, 20
        ) + interior
        obs = extractor.parse_ethernet_l2(100.0, cuerpo)
        assert obs is not None
        self.assertEqual(obs.vlan, 20)

    def test_ethertype_desconocido_se_descarta(self) -> None:
        cuerpo = trama(MAC_FIREWALL, MAC_CLIENTE, 20, 0x86DD, b"\x00" * 40)
        self.assertIsNone(extractor.parse_ethernet_l2(100.0, cuerpo))

    def test_arp_con_longitudes_raras_se_descarta(self) -> None:
        cuerpo = trama("ff:ff:ff:ff:ff:ff", MAC_CLIENTE, 20, 0x0806,
                       arp(MAC_CLIENTE, CLIENTE, "10.10.20.99", hw_len=8))
        self.assertIsNone(extractor.parse_ethernet_l2(100.0, cuerpo))


class VlanNativa(unittest.TestCase):
    def _obs(self, vlan: int, mac: str = MAC_CLIENTE) -> extractor.L2Observation:
        return extractor.L2Observation(0.0, vlan, mac, CLIENTE, False)

    def test_gana_la_mas_frecuente(self) -> None:
        obs = [self._obs(20), self._obs(20), self._obs(30)]
        self.assertEqual(extractor.native_vlans(obs)[CLIENTE], 20)

    def test_empate_se_resuelve_por_la_etiqueta_mas_baja(self) -> None:
        # Sin esta regla el resultado dependería del orden de lectura de los
        # ficheros del anillo, que no está garantizado.
        obs = [self._obs(30), self._obs(20)]
        self.assertEqual(extractor.native_vlans(obs)[CLIENTE], 20)

    def test_la_mac_del_cortafuegos_no_decide_la_vlan_de_un_servidor(self) -> None:
        # Las dos copias del espejo empatan, y el desempate por etiqueta baja
        # le daría al servidor de la VLAN 30 la VLAN 20 del cliente. La MAC
        # del cortafuegos aparece en las dos VLAN; la del servidor, en una.
        servidor = "10.10.30.10"
        obs = [
            extractor.L2Observation(1.0, 30, "00:aa:00:00:00:30", servidor, False),
            extractor.L2Observation(1.1, 20, MAC_FIREWALL, servidor, False),
            extractor.L2Observation(2.0, 30, "00:aa:00:00:00:30", servidor, False),
            extractor.L2Observation(2.1, 20, MAC_FIREWALL, servidor, False),
            # Lo que delata al cortafuegos: la misma MAC emitiendo en otra VLAN.
            extractor.L2Observation(3.0, 30, MAC_FIREWALL, CLIENTE, False),
        ]
        self.assertIn(MAC_FIREWALL, extractor.forwarding_macs(obs))
        self.assertEqual(extractor.native_vlans(obs)[servidor], 30)

    def test_seis_alias_sobre_una_mac_no_son_un_reenviador(self) -> None:
        # La VM de clientes lleva .21-.26 sobre una sola MAC. Si el criterio
        # fuera "MAC con muchas IP" en vez de "MAC en varias VLAN", se la
        # tomaría por un enrutador y perdería su VLAN nativa.
        obs = [
            extractor.L2Observation(float(i), 20, MAC_CLIENTE, f"10.10.20.{21 + i}", False)
            for i in range(6)
        ]
        self.assertEqual(extractor.forwarding_macs(obs), set())
        self.assertEqual(extractor.native_vlans(obs)["10.10.20.23"], 20)


class CambiosDeVinculo(unittest.TestCase):
    def _serie(self, macs: list[str]) -> list[extractor.L2Observation]:
        return [
            extractor.L2Observation(float(i), 20, mac, CLIENTE, False)
            for i, mac in enumerate(macs)
        ]

    def test_una_sola_mac_no_cambia(self) -> None:
        self.assertEqual(extractor.binding_changes(self._serie([MAC_CLIENTE] * 5)), 0)

    def test_un_relevo_cuenta_uno(self) -> None:
        self.assertEqual(
            extractor.binding_changes(self._serie([MAC_CLIENTE, MAC_CLIENTE, MAC_OTRA])), 1
        )

    def test_ida_y_vuelta_cuenta_dos(self) -> None:
        # A-B-A es un parpadeo, no una migración: dos transiciones, no una.
        self.assertEqual(
            extractor.binding_changes(self._serie([MAC_CLIENTE, MAC_OTRA, MAC_CLIENTE])), 2
        )


class FeaturesDeCapa2(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.directorio = Path(self.tempdir.name)
        self.eve = self.directorio / "eve.json"
        self.eve.write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _filas(self, tramas: list[tuple[float, bytes]]) -> list[dict]:
        pcap = self.directorio / "captura.pcap"
        escribir_pcap(pcap, tramas)
        paquetes = v2.load_packet_observations([pcap], RED)
        apps = v2.load_app_observations(self.eve, RED)
        l2 = extractor.load_l2_observations([pcap], RED)
        return extractor.build_rows("prueba", paquetes, apps, l2)

    def test_barrido_arp_produce_tasa_y_fila_sin_trafico_ip(self) -> None:
        # Un barrido de la propia VLAN no cruza el enrutador: las 28 features
        # de v2 no lo ven. Esta es la razón de ser de la capa 2.
        # De 1000,5 a 1010,0: la ventana es (fin-10, fin], así que el extremo
        # superior entra y las 20 peticiones caen en la misma ventana.
        tramas = [
            (1000.5 + i * 0.5, trama("ff:ff:ff:ff:ff:ff", MAC_CLIENTE, 20, 0x0806,
                                     arp(MAC_CLIENTE, CLIENTE, f"10.10.20.{i + 1}")))
            for i in range(20)
        ]
        filas = self._filas(tramas)
        objetivo = [f for f in filas if f["entity_ip"] == CLIENTE
                    and f["window_end_utc"] == iso(1010.0)]
        self.assertEqual(len(objetivo), 1)
        fila = objetivo[0]
        self.assertEqual(fila["arp_request_count_10s"], 20)
        self.assertAlmostEqual(fila["arp_request_rate_10s"], 2.0)
        self.assertEqual(fila["native_vlan"], 20)
        # La fila existe aunque no haya un solo paquete IP atribuido.
        self.assertEqual(fila["packet_count_10s"], 0)
        self.assertAlmostEqual(fila["packet_rate_10s"], 0.0)

    def test_la_copia_del_cortafuegos_no_infla_las_mac(self) -> None:
        # El espejo captura en los dos sentidos: el mismo paquete aparece al
        # entrar al cortafuegos (VLAN 20, MAC real) y al salir hacia la VLAN de
        # destino (VLAN 30, MAC del cortafuegos, misma IP de origen). Sin
        # anclar la entidad a su VLAN nativa, unique_src_mac_30s valdría 2 para
        # todo el tráfico normal entre VLAN y no distinguiría nada.
        tramas: list[tuple[float, bytes]] = []
        for i in range(6):
            momento = 1000.0 + i
            carga = ipv4(CLIENTE, SERVIDOR, tcp(40000 + i, 80, 0x02))
            tramas.append((momento, trama(MAC_FIREWALL, MAC_CLIENTE, 20, 0x0800, carga)))
            tramas.append((momento + 0.001,
                           trama(MAC_OTRA, MAC_FIREWALL, 30, 0x0800, carga)))
        filas = self._filas(tramas)
        fila = next(f for f in filas if f["entity_ip"] == CLIENTE
                    and f["window_end_utc"] == iso(1010.0))
        self.assertEqual(fila["native_vlan"], 20)
        self.assertAlmostEqual(fila["unique_src_mac_30s"], 1.0)
        self.assertAlmostEqual(fila["mac_ip_binding_changes_60s"], 0.0)

    def test_suplantacion_mueve_las_dos_variables(self) -> None:
        tramas: list[tuple[float, bytes]] = []
        for i in range(6):
            mac = MAC_CLIENTE if i % 2 == 0 else MAC_OTRA
            tramas.append((1000.0 + i,
                           trama(MAC_FIREWALL, mac, 20, 0x0800,
                                 ipv4(CLIENTE, SERVIDOR, tcp(40000 + i, 80, 0x02)))))
        filas = self._filas(tramas)
        fila = next(f for f in filas if f["entity_ip"] == CLIENTE
                    and f["window_end_utc"] == iso(1010.0))
        self.assertAlmostEqual(fila["unique_src_mac_30s"], 2.0)
        self.assertAlmostEqual(fila["mac_ip_binding_changes_60s"], 5.0)

    def test_carp_no_vuelve_a_entrar_por_la_puerta_de_la_capa_2(self) -> None:
        # La exclusión de CARP y pfsync bajó las entidades falsas del 87,1 % al
        # 47,0 %. Si la pasada de capa 2 no la respeta, cada interfaz VLAN del
        # cortafuegos reaparece como entidad y se deshace esa corrección.
        pcap = self.directorio / "captura.pcap"
        carp = trama("01:00:5e:00:00:12", MAC_FIREWALL, 20, 0x0800,
                     ipv4("10.10.20.2", "224.0.0.18", b"\x00" * 20, protocolo=112))
        normal = trama(MAC_FIREWALL, MAC_CLIENTE, 20, 0x0800,
                       ipv4(CLIENTE, SERVIDOR, tcp(1234, 80, 0x02)))
        escribir_pcap(pcap, [(1000.5, carp), (1001.0, normal)])

        sin_filtro = extractor.load_l2_observations([pcap], RED)
        self.assertIn("10.10.20.2", {o.sender_ip for o in sin_filtro})

        con_filtro = extractor.load_l2_observations([pcap], RED, frozenset({112, 240}))
        self.assertNotIn("10.10.20.2", {o.sender_ip for o in con_filtro})
        self.assertIn(CLIENTE, {o.sender_ip for o in con_filtro})

    def test_la_trama_arp_sobrevive_al_filtro_de_protocolos(self) -> None:
        # ARP no tiene protocolo IP: se marca -1 y no puede coincidir con 112.
        pcap = self.directorio / "arp.pcap"
        escribir_pcap(pcap, [(1000.5, trama("ff:ff:ff:ff:ff:ff", MAC_CLIENTE, 20, 0x0806,
                                            arp(MAC_CLIENTE, CLIENTE, "10.10.20.9")))])
        obs = extractor.load_l2_observations([pcap], RED, frozenset({112, 240}))
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].protocol, -1)
        self.assertTrue(obs[0].arp_request)

    def test_fuera_del_rango_de_entidades_no_se_atribuye(self) -> None:
        tramas = [(1000.0, trama("ff:ff:ff:ff:ff:ff", MAC_OTRA, 20, 0x0806,
                                 arp(MAC_OTRA, "192.168.1.5", "10.10.20.1")))]
        self.assertEqual(self._filas(tramas), [])


class DeduplicacionDelEspejo(unittest.TestCase):
    """Las dos formas en que el espejo enseña la misma trama dos veces."""

    def _ctx(self, tramas: list[tuple[float, bytes]]) -> list:
        salida = []
        for marca, cuerpo in tramas:
            c = extractor.parse_con_contexto(marca, cuerpo)
            if c is not None:
                salida.append(c)
        return salida

    def _entre_vlan(self, ip_id: int, t0: float) -> list[tuple[float, bytes]]:
        # Entra al cortafuegos por la VLAN 20 con TTL 64 y sale por la 30 con 63.
        entrada = trama(MAC_FIREWALL, MAC_CLIENTE, 20, 0x0800,
                        ipv4(CLIENTE, SERVIDOR, tcp(1234, 80, 0x18, seq=7),
                             ip_id=ip_id, ttl=64))
        salida = trama(MAC_OTRA, MAC_FIREWALL, 30, 0x0800,
                       ipv4(CLIENTE, SERVIDOR, tcp(1234, 80, 0x18, seq=7),
                            ip_id=ip_id, ttl=63))
        return [(t0, entrada), (t0 + 0.0001, salida)]

    def test_copia_entre_vlan_se_va_y_queda_la_de_mayor_ttl(self) -> None:
        conservados, fuera = extractor.deduplicar_espejo(self._ctx(self._entre_vlan(1, 100.0)))
        self.assertEqual(fuera, 1)
        self.assertEqual(len(conservados), 1)
        self.assertEqual(conservados[0].ttl, 64)

    def test_da_igual_el_orden_de_llegada(self) -> None:
        tramas = self._entre_vlan(1, 100.0)
        conservados, fuera = extractor.deduplicar_espejo(self._ctx(list(reversed(tramas))))
        self.assertEqual(fuera, 1)
        self.assertEqual(conservados[0].ttl, 64)

    def test_difusion_vista_en_los_dos_troncales(self) -> None:
        # Identica byte a byte: misma VLAN, mismo TTL, mismas MAC.
        cuerpo = trama("01:00:5e:7f:ff:fa", MAC_CLIENTE, 10, 0x0800,
                       ipv4(CLIENTE, "239.255.255.250", b"\x00" * 8,
                            protocolo=17, ip_id=555, ttl=1))
        conservados, fuera = extractor.deduplicar_espejo(
            self._ctx([(100.0, cuerpo), (100.00004, cuerpo)])
        )
        self.assertEqual(fuera, 1)
        self.assertEqual(len(conservados), 1)

    def test_dos_paquetes_distintos_de_una_rafaga_no_se_funden(self) -> None:
        # Medido en el espejo: los anuncios SSDP salen en rafagas con ip_id
        # consecutivos y 25 us de separacion. Sin el ip_id en la clave, la
        # deduplicacion se comeria trafico legitimo.
        uno = trama("01:00:5e:7f:ff:fa", MAC_CLIENTE, 10, 0x0800,
                    ipv4(CLIENTE, "239.255.255.250", b"\x00" * 8,
                         protocolo=17, ip_id=24560, ttl=1))
        dos = trama("01:00:5e:7f:ff:fa", MAC_CLIENTE, 10, 0x0800,
                    ipv4(CLIENTE, "239.255.255.250", b"\x00" * 8,
                         protocolo=17, ip_id=24561, ttl=1))
        conservados, fuera = extractor.deduplicar_espejo(
            self._ctx([(100.0, uno), (100.000025, dos)])
        )
        self.assertEqual(fuera, 0)
        self.assertEqual(len(conservados), 2)

    def test_una_retransmision_de_verdad_sobrevive(self) -> None:
        # Mismo seq, pero otro ip_id y 300 ms despues: el RTO minimo de TCP es
        # 200 ms, muy por encima de la ventana de 5 ms.
        primero = trama(MAC_FIREWALL, MAC_CLIENTE, 20, 0x0800,
                        ipv4(CLIENTE, SERVIDOR, tcp(1234, 80, 0x18, seq=7),
                             ip_id=10, ttl=64))
        reenvio = trama(MAC_FIREWALL, MAC_CLIENTE, 20, 0x0800,
                        ipv4(CLIENTE, SERVIDOR, tcp(1234, 80, 0x18, seq=7),
                             ip_id=11, ttl=64))
        conservados, fuera = extractor.deduplicar_espejo(
            self._ctx([(100.0, primero), (100.3, reenvio)])
        )
        self.assertEqual(fuera, 0)
        self.assertEqual(len(conservados), 2)

    def test_el_contexto_lee_vlan_e_ip_id_sin_tocar_v2(self) -> None:
        cuerpo = trama(MAC_FIREWALL, MAC_CLIENTE, 30, 0x0800,
                       ipv4(CLIENTE, SERVIDOR, tcp(1234, 80, 0x02),
                            ip_id=4242, ttl=57))
        c = extractor.parse_con_contexto(100.0, cuerpo)
        assert c is not None
        self.assertEqual(c.vlan, 30)
        self.assertEqual(c.ip_id, 4242)
        self.assertEqual(c.packet.ttl, 57)
        # El paquete es exactamente el que devuelve el parser congelado.
        self.assertEqual(c.packet, v2.parse_ethernet_ipv4(100.0, cuerpo))


class ContratoDelEsquema(unittest.TestCase):
    def setUp(self) -> None:
        self.esquema = REPO_ROOT / "configs/features/multilayer-v3.json"

    def test_el_esquema_publicado_valida(self) -> None:
        extractor.validate_schema(self.esquema)

    def test_treinta_y_una_features_y_las_28_primeras_son_las_de_v2(self) -> None:
        self.assertEqual(len(extractor.FEATURE_NAMES), 31)
        self.assertEqual(extractor.FEATURE_NAMES[:28], v2.FEATURE_NAMES)
        self.assertEqual(
            extractor.FEATURE_NAMES[28:],
            ("arp_request_rate_10s", "unique_src_mac_30s", "mac_ip_binding_changes_60s"),
        )

    def test_las_nuevas_declaran_capa_L2(self) -> None:
        esquema = json.loads(self.esquema.read_text(encoding="utf-8"))
        nuevas = [f for f in esquema["features"] if f["order"] > 28]
        self.assertEqual([f["layer"] for f in nuevas], ["L2", "L2", "L2"])
        for feature in nuevas:
            self.assertIn("definition", feature)

    def test_un_esquema_con_28_features_es_rechazado(self) -> None:
        with self.assertRaises(ValueError):
            extractor.validate_schema(REPO_ROOT / "configs/features/multilayer-v2.json")


class NoAlteraAV2(unittest.TestCase):
    """La garantía que sostiene la reproducción del modelo publicado."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.directorio = Path(self.tempdir.name)
        self.eve = self.directorio / "eve.json"
        self.eve.write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_las_28_columnas_son_identicas_a_ejecutar_v2_a_solas(self) -> None:
        tramas: list[tuple[float, bytes]] = []
        for i in range(30):
            momento = 1000.0 + i * 0.7
            tramas.append((momento, trama(MAC_FIREWALL, MAC_CLIENTE, 20, 0x0800,
                                          ipv4(CLIENTE, SERVIDOR,
                                               tcp(40000 + i, 80, 0x02, seq=i)))))
            tramas.append((momento + 0.05, trama(MAC_CLIENTE, MAC_FIREWALL, 20, 0x0800,
                                                 ipv4(SERVIDOR, CLIENTE,
                                                      tcp(80, 40000 + i, 0x12, seq=i)))))
        # Y un barrido ARP que solo v3 puede ver, para que las filas no coincidan
        # por casualidad de tener exactamente el mismo conjunto de entidades.
        for i in range(5):
            tramas.append((1005.0 + i, trama("ff:ff:ff:ff:ff:ff", MAC_OTRA, 20, 0x0806,
                                             arp(MAC_OTRA, "10.10.20.77",
                                                 f"10.10.20.{i + 1}"))))

        pcap = self.directorio / "captura.pcap"
        escribir_pcap(pcap, tramas)
        paquetes = v2.load_packet_observations([pcap], RED)
        apps = v2.load_app_observations(self.eve, RED)
        l2 = extractor.load_l2_observations([pcap], RED)

        filas_v2 = v2.build_rows("prueba", paquetes, apps)
        filas_v3 = extractor.build_rows("prueba", paquetes, apps, l2)

        self.assertTrue(filas_v2)
        indice = {(f["entity_ip"], f["window_end_utc"]): f for f in filas_v3}
        for fila in filas_v2:
            clave = (fila["entity_ip"], fila["window_end_utc"])
            self.assertIn(clave, indice)
            for columna in v2.METADATA_COLUMNS + v2.FEATURE_NAMES:
                self.assertEqual(indice[clave][columna], fila[columna],
                                 f"la columna {columna} cambió en {clave}")

        # Y v3 aporta filas que v2 no podía emitir.
        solo_l2 = [f for f in filas_v3 if f["entity_ip"] == "10.10.20.77"]
        self.assertTrue(solo_l2)
        self.assertEqual({f["entity_ip"] for f in filas_v2} & {"10.10.20.77"}, set())

    def test_el_csv_lleva_las_columnas_nuevas_al_final(self) -> None:
        salida = self.directorio / "salida.csv"
        extractor.write_csv(
            [dict.fromkeys(extractor.METADATA_COLUMNS + extractor.FEATURE_NAMES, 0)],
            salida,
        )
        cabecera = salida.read_text(encoding="utf-8").splitlines()[0].split(",")
        self.assertEqual(tuple(cabecera[-3:]), extractor.FEATURE_NAMES_L2)
        self.assertEqual(
            tuple(cabecera[: len(v2.METADATA_COLUMNS)]), v2.METADATA_COLUMNS
        )


if __name__ == "__main__":
    unittest.main()
