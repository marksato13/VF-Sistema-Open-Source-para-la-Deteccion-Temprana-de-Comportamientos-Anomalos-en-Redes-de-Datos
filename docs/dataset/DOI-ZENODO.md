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
Título     v1.0.0 — dataset multilayer-v2, OCSVM congelado y motor validado
```

En la descripción, resuma lo que incluye y **las limitaciones medidas**:

> Dataset de 220 episodios y 1.373 ventanas con 28 variables L3/L4/L7 (27
> observables), modelo OCSVM congelado con umbral 1,8126 calibrado solo con
> validación, motor en tiempo real con bloqueo por nftables, y validación
> operacional sobre 58 corridas.
>
> Limitaciones declaradas: el FPR benigno de 4,71 % en laboratorio no se
> sostiene en operación, donde se midió 25,81 % y 22,97 %. El motor se atrasa
> hasta 161 s bajo carga sostenida.

**Publish release.** En unos minutos Zenodo crea el depósito y emite el DOI.

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
