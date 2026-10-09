# Cómo obtener el DOI en Zenodo

Cierra la parte de replicabilidad que hoy sigue en «parcial» por no tener un
identificador citable. Es gratis y son tres pasos.

## 1 · Entrar

`https://zenodo.org` → **Log in** → **Log in with GitHub**. Autoriza el acceso.

## 2 · Activar el repositorio

`https://zenodo.org/account/settings/github/`

Busque en la lista:

```
VF-Sistema-Open-Source-para-la-Deteccion-Temprana-de-Comportamientos-Anomalos-en-Redes-de-Datos
```

Ponga el interruptor en **ON**. Si no aparece, pulse **Sync now**: Zenodo solo
lista repositorios **públicos**.

## 3 · Publicar una versión

En GitHub: **Releases** → **Create a new release**.

```
Tag        v1.0.0
Título     v1.0.0 — dataset multilayer-v2, modelo de laboratorio y motor con respuesta graduada
```

En la descripción, resuma lo que incluye y **las limitaciones medidas** (es la misma
que trae `.zenodo.json`):

> Dataset de 220 episodios y 1.373 ventanas con 28 variables L3/L4/L7 (27
> observables); modelo de laboratorio OCSVM (histórico, umbral 1,8126 calibrado solo
> con validación) con su protocolo de reproducción; model card del modelo desplegado
> (Isolation Forest recalibrado en la red, no publicado: se publican su hash y la
> verificación de su umbral); motor en tiempo real con respuesta PERMIT/LIMIT/BLOCK
> por feed firmado; y validación operacional histórica F6 sobre 58 corridas.
>
> Limitaciones declaradas: el FPR de 4,45 % del modelo desplegado es sobre tráfico
> normal retenido, no el del sistema completo; en F6 el modelo de laboratorio pasó de
> 4,71 % a 25,81 % y 22,97 %. La detección depende del escenario (DNS 0/8 con el
> modelo solo).

**Publish release.** En unos minutos Zenodo crea el depósito y emite el DOI.

> Los metadatos (título, autores, descripción con las limitaciones, licencia,
> palabras clave) **ya vienen pre-rellenados** en `.zenodo.json`, en la raíz del
> repositorio: Zenodo lo lee solo al publicar la versión. No hay que teclearlos a
> mano. Revísalos si quieres y ajusta la descripción del release si procede.

---

## Después

**Añada el DOI a `CITATION.cff`**, como campo `doi:` al mismo nivel que
`version`. Y ponga la insignia en el `README.md`:

```markdown
[![DOI](https://zenodo.org/badge/DOI/<su-doi>.svg)](https://doi.org/<su-doi>)
```

**Cítelo en el artículo de IJIES**, en la sección de disponibilidad de datos.
Es la diferencia entre decir «el código está en GitHub» y dar una referencia
permanente que un revisor puede seguir dentro de diez años.

## Dos cosas que conviene saber

**Zenodo emite dos DOI.** Uno de *concepto*, que apunta siempre a la última
versión, y uno por versión. **En el artículo cite el de la versión**: es el que
corresponde a los resultados que publica.

**Una versión publicada no se puede borrar.** Es lo que la hace citable.
Revise el contenido antes de pulsar, sobre todo que no haya quedado ningún
secreto: `stack/bin/ppi-secrets --todo` desde el repositorio de orquestación.
