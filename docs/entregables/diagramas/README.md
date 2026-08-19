# Diagramas editables (draw.io)

Fuentes editables de los diagramas del PPI y del resto de entregables. A diferencia de `../graficas/` —que son figuras **generadas por script** desde los datos y no deben editarse a mano— estos diagramas son **conceptuales y se dibujan**: topología, arquitectura, flujos, metodología.

| | `../graficas/` | `diagramas/` (esta carpeta) |
|---|---|---|
| Qué contiene | Curvas, histogramas, matrices | Topologías, arquitecturas, flujos |
| Origen | Generadas con matplotlib desde artefactos reales | Dibujadas a mano en draw.io |
| Se editan | No — se regeneran con el script | Sí — abriendo el `.drawio` |
| Si cambia un dato | Se vuelve a ejecutar el script | Se edita el diagrama |

## Diagramas disponibles

| Archivo | Contenido | Usado en |
|---|---|---|
| `topologia-laboratorio.drawio` | Las 5 VM, las tres redes segregadas, el Sensor como punto de decisión y el camino del bloqueo | PPI · informes |

## Cómo editarlos

**Opción recomendada — sin instalar nada:** abrir [app.diagrams.net](https://app.diagrams.net), *Archivo → Abrir desde → Dispositivo*, y seleccionar el `.drawio`.

**Con la aplicación de escritorio:** [draw.io Desktop](https://github.com/jgraph/drawio-desktop/releases), que permite trabajar sin conexión.

**En VS Code:** extensión *Draw.io Integration* (`hediet.vscode-drawio`), que abre el `.drawio` directamente en el editor.

## Convenciones

Para que los diagramas nuevos se vean como una familia y no como piezas sueltas:

**Paleta** — la misma de las gráficas y los informes:

| Uso | Color |
|---|---|
| Acento / Sensor / componentes propios | `#0F8A7D` |
| Correcto · tráfico legítimo | `#15803D` |
| Error · ataque · bloqueo | `#B91C1C` |
| Advertencia · nota | `#B45309` |
| Texto principal | `#131B2E` |
| Texto secundario · elementos neutros | `#5B6B8C` |
| Fondo de zona | `#EEF1F8` |
| Borde de zona | `#C3CCDF` |

**Iconos** — usar la librería **networks** que ya trae draw.io (`shape=mxgraph.networks.*`): `pc`, `server`, `firewall`, `router`, `switch`, `cloud`. Evitar mezclarla con otras familias de iconos en un mismo diagrama.

**Tipografía** — 20 pt para el título, 12 pt para subtítulos y nombres de zona, 10–11 pt para etiquetas.

**Estructura** — título arriba a la izquierda con una línea de subtítulo que explique qué muestra el diagrama; zonas de red como contenedores redondeados; una nota al pie cuando haya una limitación o condición que declarar.

## Formato de guardado

Guardar siempre como **`.drawio` sin comprimir** (*Archivo → Propiedades → Comprimido: No*). El XML queda legible y Git puede mostrar diferencias reales entre versiones; comprimido, cada cambio aparece como un bloque binario ilegible.

## Exportar para usar en los documentos

Los diagramas exportados van a `exportados/`:

- **Para Word y PDF** → PNG a **300 dpi** (*Archivo → Exportar como → PNG*, marcar *Selección solamente* y subir el zoom hasta 300 dpi).
- **Para Markdown y GitHub** → PNG también; el `.svg` se ve mejor pero GitHub no siempre lo renderiza dentro de tablas.

Mantener el mismo nombre base que el fuente: `topologia-laboratorio.drawio` → `exportados/topologia-laboratorio.png`.

## Diagramas pendientes de dibujar

Candidatos que aportarían al PPI y a la sustentación:

- **Arquitectura del sistema en capas** — de la captura al bloqueo, mostrando qué componente hace qué.
- **Flujo de decisión del motor** — las dos rutas al veredicto y el heurístico L7 (existe como figura generada, pero una versión editable permitiría adaptarla a la diapositiva).
- **Metodología por fases** — F0 a F7, con lo que entrega cada fase a la siguiente.
- **Pipeline de datos** — de la captura PCAP/EVE a las 28 variables y de ahí al modelo.
