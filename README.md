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
| **Extrae** | 28 variables de capas 3, 4 y 7 por ventana temporal e IP — **27 efectivas y 1 no observable** |
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
La versión exacta importa: ver docs/INSTALACION.md, anexo B
Linux con reenvío IP en el equipo que hace de router
```

Para el laboratorio completo hace falta además un hipervisor. Sin él puede
usar el motor sobre una máquina que ya enrute tráfico.

---

## Puesta en marcha

Desde un clon recién hecho, cuatro comandos:

```bash
git clone https://github.com/marksato13/VF-Sistema-Open-Source-para-la-Deteccion-Temprana-de-Comportamientos-Anomalos-en-Redes-de-Datos.git cyberflow
cd cyberflow
cp configs/cyberflow.toml configs/cyberflow.local.toml
$EDITOR configs/cyberflow.local.toml
```

En el fichero, lo mínimo: la **interfaz de captura**, la **red a vigilar**, el
**usuario**, la **raíz** del repositorio y el **modo** (`observacion` o
`bloqueo`). Todo lo demás tiene valor por omisión.

```bash
sudo bash scripts/setup/instalar.sh --comprobar   # diagnostica, no toca nada
sudo bash scripts/setup/instalar.sh               # instala y arranca
```

`--comprobar` es un diagnóstico completo antes de tocar la máquina: requisitos,
validez de la configuración, si la interfaz de captura existe, si su MAC es la
esperada, si **está recibiendo tráfico de verdad**, si Suricata apunta a ella y
si `eve.json` crece. Si algo falla, dice qué y dónde mirar. El instalador se
niega a continuar mientras quede un fallo.

Después crea el entorno de Python, **comprueba que el modelo carga**, genera las
unidades de systemd desde su configuración, las arranca y verifica que el motor
está decidiendo.

> **Los artefactos publicados.** Antes de fiarse de una cifra:
> ```bash
> sha256sum -c docs/dataset/SHA256SUMS
> ```
> Desde la raíz del repositorio. **Si un solo hash no cuadra, pare.**

> **Elija el modo antes de instalar.** `bloqueo` solo tiene sentido si esta
> máquina está **en el camino** del tráfico. Con un espejo SPAN observa pero no
> enruta: `nftables` ahí solo afecta a la propia máquina, y no daría ningún
> error. El instalador lo comprueba mirando `ip_forward`.

Para redes sin salida a Internet, o si el espejo aún no llega al sensor, la
guía larga está en [`docs/INSTALACION.md`](docs/INSTALACION.md).

### Comprobar que sigue funcionando

```bash
sudo bash scripts/setup/instalar.sh --comprobar
systemctl is-active cyberflow-capture-nic ppi-motor-capture ppi-motor suricata
tail -f logs/motor_decision.log
```

En modo bloqueo, además: `sudo nft list set inet ppi_enforce bloqueadas`

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
en campaña real se midió **25,81 %** y **22,97 %**. Y en un despliegue sobre
una **red distinta sin recalibrar**, el **92,4 %** — marcando como anómalas las
interfaces del propio cortafuegos emitiendo sus anuncios CARP, sin ningún
ataque en curso. Un `iperf` legítimo a 200 Mbit/s llegó a bloquear al cliente.

> El umbral publicado está calibrado para un laboratorio concreto. **En otra
> red hay que recalibrar antes de creerse una sola alerta.**

**Se atrasa bajo carga sostenida**, hasta 161 s, porque reparsea el anillo de
PCAP completo en cada ciclo.

**Una de las 28 variables no es observable** en esta configuración y queda
constante. Las otras 27 tienen variación.

---

## Documentación

**Para ponerlo en marcha y usarlo:**

| | |
|---|---|
| [`docs/INSTALACION.md`](docs/INSTALACION.md) | Guía de instalación de principio a fin, con las trampas reales |
| [`docs/GUIA-USUARIO.md`](docs/GUIA-USUARIO.md) | Uso diario, qué no ve, y resolución de problemas |
| [`docs/CONFIGURACION.md`](docs/CONFIGURACION.md) | Referencia de `cyberflow.toml`, opción por opción |

**Para entender qué hay dentro:**

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
