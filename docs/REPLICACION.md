# Reproducibilidad y replicación

Dos cosas distintas, y conviene no mezclarlas:

- **Reproducir** = obtener **los mismos resultados** a partir de los mismos
  datos y el mismo código: el modelo congelado, su umbral y sus detecciones.
- **Replicar** = levantar **otro entorno equivalente** (un segundo sensor, otro
  laboratorio) y que el sistema funcione igual sobre tráfico nuevo.

Este documento cubre las dos. La instalación de un sensor desde cero está en
[INSTALACION.md](INSTALACION.md); aquí se asume que ya se leyó.

---

## 1 · Reproducir los resultados (el modelo y sus métricas)

El modelo **está congelado y versionado**. No hay que reentrenar para reproducir:
el artefacto y su umbral viajan en el repositorio.

| Artefacto | Dónde |
|---|---|
| Pipeline del detector activo | `artifacts/model/ocsvm_scaled.joblib` |
| Manifiesto (umbral, orden de variables, hashes, BLAS) | `artifacts/model/manifest.json` |
| Candidatos comparados (7 modelos) | `artifacts/model/candidates/*.joblib` |
| Dataset de línea base (normal/anómalo) | `artifacts/dataset/multilayer-v2-*.csv` |

### Verificar que una recalibración reproduce lo publicado

Si recalibra en otra máquina y quiere comprobar que da **lo mismo**:

```bash
python3 scripts/analysis/verificar_reproduccion.py \
    artifacts/model/manifest.json  /ruta/al/manifest-nuevo.json
```

Comprueba **dos niveles** (ver el docstring del script):

- **Funcional (siempre obligatorio):** mismo número de detecciones en los siete
  detectores y mismos umbrales (tolerancia 1e-9). Esto es lo que atrapa un fallo
  de verdad.
- **Bit a bit (solo con el mismo BLAS):** umbral y hash idénticos. OpenBLAS elige
  kernels distintos según la CPU y el último bit se mueve; si el BLAS coincide con
  el del manifiesto cualquier diferencia es un fallo, si no coincide se informa y
  no se falla.

### La versión de Python importa

El modelo se congeló con **CPython 3.14** y un scikit-learn fijado. Bajar a 3.12
**cambia el resultado** (bajo scikit-learn 1.7.2 el Isolation Forest ignora
`sample_weight` y el umbral se movió un 10 %). Los detalles y cómo instalar la
versión correcta están en **INSTALACION.md, Anexo B**. No es un capricho: es la
diferencia entre reproducir y no reproducir.

---

## 2 · Replicar el entorno (Modo 5: un segundo sensor)

«Replicación» en el sentido del Modo 5 de instalación: **un segundo sensor que
recibe la misma copia del espejo** (SPAN) que el primero. Sirve para A/B, para
alta disponibilidad de observación, o para validar en otra ventana de tráfico.

Pasos:

1. **Duplicar la copia SPAN** hacia el segundo puerto/host. En el switch, añada
   el puerto del segundo sensor como destino del mismo *monitor session* (o un
   segundo TAP). No cambia nada en el primer sensor: el espejo solo copia.
2. **Instalar el segundo sensor** siguiendo INSTALACION.md §§2–7, con **su propio**
   `configs/cyberflow.local.toml` (su interfaz, su MAC, su alcance).
3. **Usar el mismo modelo congelado** (`artifacts/model/`) para que ambos decidan
   con el mismo umbral; o recalibrar el segundo contra **su** línea base si la red
   que ve es distinta (INSTALACION.md §8).
4. **Enforcement:** decida si el segundo sensor solo observa (recomendado para no
   duplicar acciones sobre el mismo host) o si publica su propio feed. Dos
   publicadores sobre el mismo host se fusionan por IP con la acción más severa;
   si no lo quiere, deje el segundo en modo observación (sin `--enforce`).

> El panel es un servicio aparte en cada sensor; verlos a la vez no requiere nada
> especial, cada uno sirve el suyo.

---

## 3 · Replicar con Ansible (automatización del laboratorio)

El laboratorio de referencia se levanta de forma **reproducible** con los
playbooks de [`ansible/`](../ansible/). El controlador y los requisitos están en
[`ansible/README.md`](../ansible/README.md). Las credenciales **no** viven en Git;
se usa un usuario `useransible` y llaves por host.

| Playbook | Qué hace |
|---|---|
| `00-validar-controlador.yml` | Comprueba el controlador (versiones, colecciones) |
| `01-comprobar-conectividad.yml` | Alcanza cada host del inventario |
| `02-auditar-recursos.yml` | CPU/RAM/disco por host (antes de tocar nada) |
| `03-configurar-servicios-servidor.yml` | Servicios del servidor protegido |
| `04-configurar-cliente-f1.yml` | Cliente generador de tráfico legítimo |
| `05-ajustar-captura-suricata.yml` | Captura y Suricata en el sensor |
| `06-desplegar-orquestacion-campanas.yml` | Orquestación de campañas de ataque |
| `07-configurar-almacenamiento-evidencia-vm01.yml` | Almacenamiento de evidencia |
| `08-configurar-ntp-interno.yml` | NTP interno (relojes alineados, clave de reproducir ventanas) |
| `09-configurar-kali-herramientas-v2.yml` | Herramientas de ataque en la Kali |

El inventario (`ansible/inventories/lab/`) trae las IPs y hosts del laboratorio
de referencia: **sustitúyalas por las suyas** antes de ejecutar nada.

---

## 4 · Replicar la respuesta distribuida (enforcement)

El enforcement distribuido —el sensor publica un feed **firmado** y cada host lo
trae, lo verifica y aplica `nftables`— se despliega con las unidades de
[`deploy/enforcement/`](../deploy/enforcement/) y el script `relay-feed.sh`. El
procedimiento completo (claves ed25519, publicador, relay, agente, modo sombra y
*fail-safe*) está en **INSTALACION.md §9**. El `README-INSTALAR.md` de esa carpeta
resume el orden.

Propiedad clave para replicar con confianza: el sensor **no tiene credenciales**
de los hosts. Si copia este diseño a otra red, el bastión sigue siendo un relay
tonto y la única autoridad es la clave de firma, que vive solo en el sensor.

---

## Resumen

| Quiero… | Voy a… |
|---|---|
| los mismos números del informe | usar `artifacts/model/` + `verificar_reproduccion.py`, con Python 3.14 |
| un segundo sensor igual | Modo 5: duplicar el SPAN + INSTALACION §§2–7 |
| levantar el lab entero | `ansible/` (sustituyendo el inventario) |
| la respuesta distribuida en otra red | `deploy/enforcement/` + INSTALACION §9 |
