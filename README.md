# Detección temprana de anomalías en redes, con bloqueo en línea

Detecta tráfico anómalo con aprendizaje **no supervisado** y **bloquea la IP
ofensora** por `nftables` en el propio router, con expiración automática de
120 segundos. No solo avisa: corta.

[![DOI](https://img.shields.io/badge/DOI-pendiente-lightgrey.svg)](docs/dataset/DOI-ZENODO.md)
[![Licencia](https://img.shields.io/badge/código-MIT-blue.svg)](LICENSE)

```
Cliente ─┐
          ├─► Sensor (Suricata + motor) ─► Servidor protegido
Atacante ─┘        │
                   └─► nftables: bloquea 120 s
```

---

## Qué hace

| | |
|---|---|
| **Extrae** | 28 variables de capas 3, 4 y 7 por ventana temporal e IP |
| **Puntúa** | One-Class SVM congelado, `nu = 0,05`, umbral `1,8126` |
| **Bloquea** | `nftables` en el router, expiración nativa de 120 s |
| **Muestra** | Panel web de solo lectura en `127.0.0.1:8788` |

Es **no supervisado**: aprende de tráfico normal, sin necesitar ejemplos
etiquetados de cada ataque. Por eso detecta comportamientos que no estaban en
el entrenamiento.

---

## Requisitos

```
Python 3.11 o superior · Suricata 7 u 8 · nftables
Linux con reenvío IP en el equipo que hace de router
```

Para el laboratorio completo hace falta además un hipervisor. Sin él puede
usar el motor sobre una máquina que ya enrute tráfico.

---

## Puesta en marcha

### 1 · Instalar

```bash
git clone <este-repositorio> && cd <carpeta>
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-model.txt
```

### 2 · Comprobar que los artefactos son los publicados

```bash
sha256sum -c docs/dataset/SHA256SUMS
```

Desde la **raíz** del repositorio: las rutas del archivo son relativas a ella.

**Si un solo hash no cuadra, pare.** Los artefactos no son los publicados y
nada de lo que salga después es comparable.

### 3 · Ajustar a su red

Edite `configs/features/multilayer-v2.json` y los archivos de
`configs/sensor/`. Como mínimo cambie:

```
la interfaz de captura            (por defecto ens35)
las redes a vigilar               HOME_NET
la interfaz de reenvío            para el bloqueo con nftables
```

### 4 · Desplegar

Con Ansible, si tiene varias máquinas:

```bash
ansible-playbook ansible/playbooks/00-validar-controlador.yml
ansible-playbook ansible/playbooks/01-comprobar-conectividad.yml
ansible-playbook ansible/playbooks/05-ajustar-captura-suricata.yml
```

O a mano, en el equipo que hace de router:

```bash
sudo bash configs/sensor/install-ppi-motor.sh
sudo systemctl enable --now ppi-motor-capture.service ppi-motor.service
```

### 5 · Comprobar que funciona

```bash
systemctl status ppi-motor.service
sudo nft list set inet ppi_enforce bloqueadas
```

---

## Uso diario

**Ver el panel.** Escucha solo en loopback; desde otra máquina, por túnel SSH:

```bash
ssh -L 8788:127.0.0.1:8788 usuario@sensor
# y abra http://127.0.0.1:8788
```

Muestra salud de los servicios, el umbral leído del manifiesto —no está
escrito en el código—, las IP bloqueadas en vivo y la actividad reciente. Es
de **solo lectura**: no ejecuta ninguna acción.

**Desbloquear una IP antes de tiempo:**

```bash
sudo nft delete element inet ppi_enforce bloqueadas { 10.20.0.20 }
```

**Ver qué está decidiendo el motor:**

```bash
journalctl -u ppi-motor.service -f
```

---

## Adaptarlo a otra red

El modelo está entrenado con tráfico de un laboratorio concreto. En otra red
**el umbral casi seguro necesita recalibrarse**: lo que allí es normal aquí
puede no serlo.

```bash
python scripts/features/extract_multilayer_v2.py --help
python scripts/modeling/calibrate_multilayer_v2_v1.py --help
```

Recoja tráfico normal de **su** red, extraiga variables y recalibre. Use solo
datos de validación para fijar el umbral, nunca los de prueba.

---

## Antes de confiar en él

Tres limitaciones **medidas**, no estimadas:

**El falso positivo sube mucho en operación.** En laboratorio es del 4,71 %;
en campaña real se midió **25,81 %** y **22,97 %**. Un `iperf` legítimo a 200
Mbit/s llegó a bloquear al cliente. Si va a usarlo sobre tráfico pesado,
recalibre antes.

**Se atrasa bajo carga sostenida**, hasta 161 s, porque reparsea el anillo de
PCAP completo en cada ciclo.

**Una de las 28 variables no es observable** en esta configuración y queda
constante. Las otras 27 tienen variación.

---

## Documentación

| | |
|---|---|
| [`docs/dataset/DATASHEET_MULTILAYER_V2.md`](docs/dataset/DATASHEET_MULTILAYER_V2.md) | Qué contiene el dataset y cómo se hizo |
| [`docs/dataset/DICCIONARIO_VARIABLES.md`](docs/dataset/DICCIONARIO_VARIABLES.md) | Las 28 variables, con fórmula y unidades |
| [`docs/dataset/MODEL_CARD_OCSVM.md`](docs/dataset/MODEL_CARD_OCSVM.md) | El modelo, su alcance y sus límites |
| [`docs/dataset/SYSTEM_CARD_MOTOR.md`](docs/dataset/SYSTEM_CARD_MOTOR.md) | El motor en producción |
| [`REPLICACION.md`](REPLICACION.md) | Qué se reproduce y qué no |
| [`CITATION.cff`](CITATION.cff) | Cómo citarlo |

---

## Licencias

**Código: MIT.** **Datos y documentación: ver [`LICENSE-DATA`](LICENSE-DATA).**

## Autores

Rubén Mark Salazar Tocas · Uziel Elias Sauñe Fernandez
Universidad Peruana Unión — E.P. de Ingeniería de Sistemas

Asesores: Ing. Nemias Saboya Ríos · Ing. Fernando Manuel Asin Gómez
