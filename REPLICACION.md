# Cómo replicar este trabajo

Qué se puede reproducir con lo publicado, qué no, y por qué. Escrito para
alguien que no tiene acceso a nuestro laboratorio.

---

## Lo que sí se reproduce con lo que hay aquí

| Se reproduce | Con qué | Comprobación |
|---|---|---|
| **Las cifras del modelo congelado** | `artifacts/dataset/*.csv` + `artifacts/model/ocsvm_scaled.joblib` | Reevaluar da **13/276** y **158/179** exactos |
| **La extracción de variables** | `scripts/features/extract_multilayer_v2.py` | Mismo PCAP → mismas 28 columnas |
| **El determinismo del pipeline** | `scripts/modeling/` | 10 ajustes → **mismo SHA-256** |
| **La ablación por capas** | `scripts/modeling/experiments/ablacion_multicapa.py` | 66,5 % → 88,8 %, p < 0,001 |
| **La integridad de todo** | `docs/dataset/SHA256SUMS` | `sha256sum -c` |

```bash
git clone <este repositorio> && cd <carpeta>
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-model.txt
cd docs/dataset && sha256sum -c SHA256SUMS
```

Si un solo hash no cuadra, **pare**: los artefactos no son los publicados y
nada de lo que salga después es comparable.

---

## Lo que NO se reproduce, y hay que decirlo

**El laboratorio.** Son cinco máquinas virtuales sobre VMware ESXi con tres
redes aisladas. Los playbooks de `ansible/` lo levantan, pero necesita el
hipervisor. Sin él puede leer la configuración, no ejecutarla.

**Los PCAP y el `eve.json` completos.** No se publican: pesan demasiado y
contienen tráfico del laboratorio sin sanear. Lo que sí se publica es el
**dataset derivado**, que es lo que alimenta al modelo.

**Las campañas.** Se documentan una a una en `docs/fase03-dataset/` —182
documentos con manifiesto, contadores y hashes— pero volver a ejecutarlas
exige el laboratorio.

Esto no es una laguna: es la diferencia entre **reproducibilidad** —mismos
datos y mismo código dan el mismo resultado, y eso sí se puede comprobar— y
**replicabilidad** —datos nuevos con el mismo método dan resultados
consistentes—, que exige montar un laboratorio equivalente.

---

## Lo que debe saber antes de usar estos resultados

Tres limitaciones medidas, no estimadas:

**El falso positivo de laboratorio no se sostiene en operación.** El FPR
benigno es **4,71 %** offline y se midió **25,81 %** y **22,97 %** en campaña
real. Un `iperf-tcp 200M` legítimo, en aislamiento, produjo un falso positivo
genuino que bloqueó al cliente. Los scores del tráfico pesado se apiñan en el
margen del umbral.

**El motor se atrasa bajo carga sostenida**, hasta 161 s, porque reparsea el
anillo de PCAP completo en cada ciclo.

**Una de las 28 variables no es observable.**
`tls_handshake_failure_ratio_60s` es constante en todo el dataset. Las otras
27 tienen variación.

Y una consideración de método: el modelo se eligió por desempeño empírico
medido sobre una evaluación bloqueada de un solo paso. El manifiesto registra
`ocsvm_scaled` con `role = sensitivity_or_comparator` mientras la política
declara principal a `if_primary_weighted`: **el artefacto congelado contradice
su política registrada**, y así consta.

---

## Composición del dataset

```
220 episodios normales · 1.373 ventanas
    entrenamiento 824 · validación 273 · prueba 276
179 ventanas anómalas
    161 originadas en Kali · 18 heredadas, reportadas por separado
```

Partición **disjunta por episodio**: ningún episodio se reparte entre
particiones, y los gates lo comprueban. El umbral se calibró **solo con
validación** (`alpha = 0,05`, `k = 13`), nunca con prueba.

---

## Dónde está cada cosa

| | |
|---|---|
| Datasheet del dataset | `docs/dataset/DATASHEET_MULTILAYER_V2.md` |
| Model card | `docs/dataset/MODEL_CARD_OCSVM.md` |
| System card del motor | `docs/dataset/SYSTEM_CARD_MOTOR.md` |
| Diccionario de las 28 variables | `docs/fase02-features-multicapa/03-diccionario-multicapa-v2.md` |
| Modelo congelado y su manifiesto | `artifacts/model/` |
| Validación operacional | `docs/fase07-validacion-final/02-resultados-f6.md` |
| Limitaciones abiertas | `docs/07-mejoras-futuras/01-debilidades-y-mejoras.md` |

---

## Licencias

**Código: MIT** (`LICENSE`). **Datos y documentación: ver `LICENSE-DATA`.**
Son distintas a propósito.

## Cómo citar

`CITATION.cff`, en la raíz. GitHub lo lee y ofrece la cita ya formateada en el
botón «Cite this repository».
