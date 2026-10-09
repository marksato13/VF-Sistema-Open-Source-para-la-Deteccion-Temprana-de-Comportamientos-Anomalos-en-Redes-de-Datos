# Detección temprana de anomalías en redes, con respuesta inline

Detecta tráfico anómalo con aprendizaje **no supervisado** y **responde de forma
graduada** —PERMIT, LIMIT o BLOCK— aplicando `nftables` en el host protegido a
través de un **feed firmado**. No solo avisa: degrada o corta, con caducidad
automática y sin bloqueos infinitos.

[![DOI](https://img.shields.io/badge/DOI-pendiente-lightgrey.svg)](docs/dataset/DOI-ZENODO.md)
[![Licencia](https://img.shields.io/badge/código-MIT-blue.svg)](LICENSE)

```
                 captura SPAN            decide            publica
Clientes ─┐      (espejo, sin IP)      ┌────────┐      ┌──────────────┐
          ├─► troncal ──► Sensor ──────► motor  ├──────► feed firmado │
Atacante ─┘                            └────────┘      │  (ed25519)   │
                                                       └──────┬───────┘
                                        relay (bastión)       │ pull + verifica
                                                       ┌──────▼───────┐
                      Wazuh (SIEM) ◄── alertas         │ agente en el │
                                                       │ host: nftables│──► PERMIT/LIMIT/BLOCK
                                                       └──────────────┘
```

> El sensor **observa por espejo (SPAN) y no bloquea** el tráfico copiado: **emite
> decisiones** que aplica el host protegido. El diagrama clásico «sensor → nftables»
> describe la **modalidad de laboratorio** (ver abajo), no el despliegue vigente.

---

## Qué hace

| | |
|---|---|
| **Extrae** | 31 variables de capas 2/3/4/7 por ventana e IP (extractor v3) |
| **Puntúa** | Isolation Forest **recalibrado en la red**, umbral `score_samples < −0,568892`; el modelo consume **28** variables (contrato v2) |
| **Responde** | PERMIT · LIMIT · BLOCK vía feed firmado y agente `nftables` en el host; caducidad escalonada 300 / 1800 / 3600 s, nunca ∞ |
| **Muestra** | Panel web con **TLS + login + roles** (solo lectura); modo demo aparte |

Es **no supervisado**: aprende de tráfico normal, sin ejemplos etiquetados de cada
ataque. Por eso puede señalar comportamientos que no estaban en el entrenamiento
(con los límites medidos que se indican más abajo).

---

## Dos modalidades de despliegue

| | **A — Laboratorio (histórico)** | **B — Distribuido (vigente)** |
|---|---|---|
| Sensor | En línea; enruta y bloquea con `nftables` local | Por **SPAN**, sin IP; **no** bloquea el tráfico copiado |
| Respuesta | Bloqueo local, caducidad 120 s | Feed firmado → relay → **agente en el host** → `nftables` |
| Dónde aparece | Resultados F6 (8 s mediana, 120 s) | Despliegue en Sensor1 |

Las métricas de respuesta de la modalidad A (tiempos, 120 s) **no** se trasladan a la
B: esta última se mide de punta a punta (publicador + relay + agente).

---

## Requisitos

```
Demo / herramientas:   Python 3.11 o superior · Suricata 7 u 8 · nftables · Linux
Modelo congelado:      las dependencias EXACTAS de requirements-model.txt
```

El **demo** y las **herramientas de configuración** admiten Python 3.11+. El **modelo
congelado** exige las versiones fijadas en `requirements-model.txt`: no las mezcle, o
el `joblib` puede no cargar igual.

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
sha256sum -c docs/dataset/SHA256SUMS      # desde la raíz del repositorio
```

**Si un solo hash no cuadra, pare.** Los artefactos no son los publicados y nada de lo
que salga después es comparable.

### 3 · Ajustar a su red

Edite `configs/features/` (esquema de variables) y `configs/sensor/`. Como mínimo:

```
la interfaz de captura (SPAN)     por defecto ens35/ens37, SIN IP
las redes a vigilar               HOME_NET
la lista nunca-bloquear           gateways, DNS, sensor, bastión (hoy por defecto; ver nota)
```

> Nota (punto a mejorar): la lista nunca-bloquear está hoy fijada en el código de
> `publicar_feed.py` y del agente; debe pasar a configuración por despliegue.

### 4 · Desplegar

- **Sensor (captura + motor + publicador):**
  ```bash
  sudo bash configs/sensor/install-ppi-motor.sh
  sudo systemctl enable --now ppi-motor-capture.service ppi-motor.service
  ```
- **Enforcement distribuido (relay en el bastión, agente en el host):** siga
  [`deploy/enforcement/README-INSTALAR.md`](deploy/enforcement/README-INSTALAR.md).
  El agente mantiene una tabla `nftables` **propia y aislada** (`inet cyberflow`).

### 5 · Comprobar que funciona

```bash
systemctl status ppi-motor.service                       # en el sensor
sudo nft list set inet cyberflow cyberflow_bloqueados     # en el HOST protegido
sudo nft list set inet cyberflow cyberflow_limitados      # en el HOST protegido
```

---

## Uso diario

**Ver el panel.** Acceso con TLS y login por rol:

```
https://<sensor>:8788        # p. ej. https://10.10.60.11:8788
```

Muestra salud de los servicios, el umbral leído del manifiesto —no está escrito en el
código—, las IP con acción vigente y la actividad reciente. Es de **solo lectura**: no
ejecuta ninguna acción. El rol `lector` no ve las secciones de desarrollador.

**Desbloquear una IP antes de tiempo (en el host protegido):**

```bash
sudo nft delete element inet cyberflow cyberflow_bloqueados { 10.10.20.30 }
```

**Ver qué está decidiendo el motor (en el sensor):**

```bash
journalctl -u ppi-motor.service -f
```

---

## Adaptarlo a otra red

El modelo se **recalibró con tráfico del laboratorio del Sensor1**. En otra red **el
umbral casi seguro necesita recalibrarse**: lo que allí es normal aquí puede no serlo.

```bash
python scripts/features/extract_multilayer_v3.py --help
python scripts/modeling/calibrate_multilayer_v2_v1.py --help
```

Recoja tráfico normal de **su** red, extraiga variables y recalibre. Use solo datos de
**validación** para fijar el umbral, nunca los de **prueba**.

---

## Antes de confiar en él

Limitaciones **medidas**, con su contexto (no intercambiar entre versiones):

- **El falso positivo depende del conjunto y la configuración.** El **4,45 %** es del
  Isolation Forest recalibrado sobre **test normal retenido**; el histórico F6 dio
  **22,97–25,81 %** bajo otro modelo/escenario. El FPR del **sistema completo** (con
  heurísticos y enforcement) se mide aparte. Sobre tráfico pesado, recalibre antes.
- **Detección por escenario, no global:** 69 % global (54/78 ventanas Kali), HTTP
  27/27, escaneo 27/43, DNS 0/8 (el piloto apuntó a un host que no era el resolver:
  limitación del ensayo). La cobertura 9/9 es del **stack híbrido** (modelo +
  heurísticos), no del modelo solo (6/9).
- **El motor usa un buffer incremental** (no reparsea todo el anillo de PCAP). Los
  atrasos históricos bajo carga son de la versión anterior; la actual se mide de nuevo.
- **Una de las 28 variables del modelo no es observable** en esta configuración
  (`tls_handshake_failure_ratio_60s`) y queda constante; las otras 27 varían. La capa 2
  del extractor v3 no entra al scoring.

---

## Documentación

| | |
|---|---|
| [`docs/FICHA-TECNICA-DESPLIEGUE-VIGENTE.md`](docs/FICHA-TECNICA-DESPLIEGUE-VIGENTE.md) | **Fuente de verdad** del despliegue vigente |
| [`docs/dataset/MODEL_CARD_IF_RECALIBRADO.md`](docs/dataset/MODEL_CARD_IF_RECALIBRADO.md) | Modelo operativo (IF recalibrado), alcance y límites |
| [`docs/dataset/MODEL_CARD_OCSVM.md`](docs/dataset/MODEL_CARD_OCSVM.md) | Modelo OCSVM — **histórico del laboratorio** |
| [`docs/RECONCILIACION-MANIFIESTO-MOTOR.md`](docs/RECONCILIACION-MANIFIESTO-MOTOR.md) | Qué declara cada artefacto vs. qué corre |
| [`docs/dataset/DATASHEET_MULTILAYER_V2.md`](docs/dataset/DATASHEET_MULTILAYER_V2.md) | Qué contiene el dataset y cómo se hizo |
| [`docs/dataset/DICCIONARIO_VARIABLES.md`](docs/dataset/DICCIONARIO_VARIABLES.md) | Las variables, con fórmula y unidades |
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
