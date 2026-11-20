"""Prepara una prueba aislada de Suricata sin modificar /etc ni arrancar el servicio."""

import hashlib
import socket
import tarfile
from pathlib import Path


HOME = Path.home()
ARCHIVE = HOME / "et-open-20261002.tar.gz"
TRIAL = HOME / "suricata-compare-trial-20261002"
EXPECTED_ARCHIVE = "3facf0eaed30caf56d2eba43d96ccd2b79dcc851c8d6be4c822e67b4120a7355"
EXPECTED_RULES = "7b674459975dd56af2d03363b27df4ad6ff53e724e3c04ff65913701ddd5f4e9"


def digest(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"Configuracion inesperada: {old[:70]}")
    return text.replace(old, new, 1)


def main() -> None:
    if socket.gethostname() != "suricata-comparator":
        raise ValueError("Host inesperado")
    raw_archive = ARCHIVE.read_bytes()
    if digest(raw_archive) != EXPECTED_ARCHIVE:
        raise ValueError("SHA-256 del bundle de reglas incorrecto")
    if TRIAL.exists():
        raise ValueError(f"No sobrescribir directorio existente: {TRIAL}")

    with tarfile.open(ARCHIVE, "r:gz") as archive:
        expected = {
            "et-open-20261002",
            "et-open-20261002/suricata.rules",
            "et-open-20261002/classification.config",
        }
        if {member.name for member in archive.getmembers()} != expected:
            raise ValueError("Contenido inesperado en el tarball")
        if not archive.getmember("et-open-20261002").isdir():
            raise ValueError("El directorio del tarball no es un directorio")
        if not all(archive.getmember(name).isfile() for name in expected if name != "et-open-20261002"):
            raise ValueError("El tarball contiene enlaces u otros tipos de archivo")
        rules = archive.extractfile("et-open-20261002/suricata.rules").read()
        classes = archive.extractfile("et-open-20261002/classification.config").read()
    if digest(rules) != EXPECTED_RULES:
        raise ValueError("SHA-256 de las reglas incorrecto")

    yaml = Path("/etc/suricata/suricata.yaml").read_text()
    yaml = replace_once(
        yaml,
        'HOME_NET: "[192.168.0.0/16,10.0.0.0/8,172.16.0.0/12]"',
        'HOME_NET: "[10.10.30.0/24]"',
    )
    yaml = replace_once(yaml, "af-packet:\n  - interface: eth0", "af-packet:\n  - interface: ens37")
    yaml = replace_once(
        yaml,
        "default-rule-path: /var/lib/suricata/rules",
        f"default-rule-path: {TRIAL}",
    )
    yaml = replace_once(
        yaml,
        "classification-file: /etc/suricata/classification.config",
        f"classification-file: {TRIAL / 'classification.config'}",
    )
    if "rule-files:\n  - suricata.rules" not in yaml:
        raise ValueError("Lista de reglas inesperada")

    TRIAL.mkdir(mode=0o700)
    (TRIAL / "logs").mkdir()
    (TRIAL / "suricata.rules").write_bytes(rules)
    (TRIAL / "classification.config").write_bytes(classes)
    (TRIAL / "suricata.yaml").write_text(yaml)
    print(f"Prueba lista: {TRIAL}")
    print(f"suricata.rules sha256={EXPECTED_RULES}")
    print(f"suricata.yaml sha256={digest(yaml.encode())}")
    print("Solo prueba; no se modificaron los archivos de /etc ni se arranco el servicio.")


if __name__ == "__main__":
    main()
