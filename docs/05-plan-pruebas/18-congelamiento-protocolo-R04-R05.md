# Congelamiento de protocolo y política de filas para R04/R05

Fecha de decisión: 4 de agosto de 2026. Alcance: F1 normal `v2`, antes de recolectar `validation` y `test`.

## Propósito

R01–R03 ya revelaron la distribución de `train`. Para evitar adaptar el experimento después de observar validation/test, este documento congela el contrato de recolección y registra cómo se tratarán ventanas y coincidencias. No implementa ni entrena todavía un modelo.

## Contrato congelado

| Elemento | Identificador |
|---|---|
| Matriz | `configs/campaigns/f1-normal-v2.json` — SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| Esquema | `configs/features/multilayer-v1.json` — SHA `9ce86147ce4d0dab3c789e10edf23f2c7cefd2106b89e493bfafcf3a5ac0e1df` |
| Generador | `scripts/f1/run-benign.sh` — SHA `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203` |
| Perfiles | 29 perfiles exactos, cinco repeticiones; R01–R03 `train`, R04 `validation`, R05 `test` |
| Iperf3 | 3.20 en Cliente y Servidor hasta cerrar R05 |
| Topología | Cliente `10.20.0.20` → Sensor `10.20.0.1/10.30.0.1` → Servidor `10.30.0.10`; administración `10.10.10.0/24` |
| Evidencia | `/srv/ppi-evidence/artifacts`, PCAP/EVE/manifest/ledger/features con gates vigentes |

También quedan congelados quietud, warm-up, settle, cooldown, aislamiento de NIC externas, NTP, rutas, servicios y controles de integridad definidos por el orquestador versionado.

No se cambia un elemento durante R04/R05. Si una corrección esencial altera features, escenarios, argumentos, topología o software que afecte comparabilidad, F1-v2 se detiene y se abre una versión nueva; no se sobrescriben campañas existentes.

## Política de filas y coincidencias

1. **Preservación:** todas las filas de campañas aceptadas permanecen en el dataset. No se eliminan automáticamente vectores idénticos.
2. **Unidad primaria:** el primer análisis siempre trata cada ventana causal emitida como unidad operativa con peso uno. Si un estimador no soporta pesos, esta rama no cambia ni bloquea; preserva la exposición temporal diseñada, aunque da más peso a episodios multiventana.
3. **Sensibilidad por episodio obligatoria:** una segunda rama hará que cada campaña aporte peso total uno, distribuyéndolo como `1 / número de filas de la campaña`. Es distinta del primario y nunca lo reemplaza silenciosamente.
4. **Implementación pendiente:** antes de entrenar la segunda rama se verificará mediante código y pruebas que el estimador elegido respete esos pesos. Si no los soporta, se definirá y probará una alternativa determinista versionada. No se inferirá soporte por la firma de una API ni se simulará.
5. **Coincidencias train:** las diecisiete coincidencias actuales se conservan y se reportan. No se atribuye causa sólo por igualdad numérica.
6. **Sensibilidad a coincidencias obligatoria:** una tercera rama de entrenamiento colapsará únicamente duplicados exactos de `train`, conservando como representante determinista la primera fila según orden de matriz, repetición, campaña y ventana. No modifica el dataset ni el resultado principal; cuantifica el efecto de multiplicidad con una decisión tomada antes de validation/test.
7. **Coincidencias futuras:** una igualdad exacta entre train, validation o test no se borra del análisis principal. Se reportarán resultados estratificados por vector visto/no visto, sin usar R05 para cambiar decisiones.
8. **Definición de visto:** un vector es visto sólo si sus catorce valores coinciden exactamente después de la normalización decimal usada por `scripts/analysis/summarize_f1_repetition.py`; tolerancia numérica cero. Compartir perfil o parámetros sin igualdad de las catorce features no cuenta como visto.
9. **Atomicidad operacional:** la matriz asigna la repetición completa a una partición. El ensamblador recompone esa partición, rechaza ID/celda incongruentes y conserva PCAP, EVE, ledger y todas las ventanas de una campaña juntos. Una igualdad numérica independiente entre particiones se diagnostica, pero no significa que el episodio haya sido dividido.
10. **Trazabilidad:** toda comparación ponderada, no ponderada, colapsada o estratificada debe declarar filas, episodios, semillas, código y commit.

La política evita dos extremos no defendibles: inflar silenciosamente episodios largos sin medir sensibilidad o deduplicar después de conocer validation/test.

## Uso de particiones

- `train` R01–R03 permite ajustar los modelos conforme al protocolo que aún debe predefinirse.
- La matriz G6 asigna R04 `validation` a selección de umbral y falsos positivos normales, mientras el diccionario G5 indica ajustar hiperparámetros y umbral sólo con train. Esa contradicción histórica debe resolverse explícitamente en el protocolo de modelado antes de ejecutar R04; no se elige una interpretación después de observar validation.
- `test` R05 se evalúa una sola vez después de congelar todas las decisiones. No se usa para elegir features, modelos, parámetros, pesos ni umbrales.
- La revisión de integridad de R04/R05 no autoriza explorar resultados del modelo fuera del protocolo.

No se encontró en el contrato F1-v2 un umbral heredado reproducible que pueda reutilizarse. Cualquier umbral o resultado del MVP es histórico y queda descartado para la evaluación final; el protocolo pendiente debe fijar desde cero su regla de selección sin consultar R05.

## Gate antes de ejecutar R04

El preflight de `F1N-DNS-VALID-10-R04` puede verificarse de forma independiente. Su ejecución queda condicionada a documentar el protocolo de modelado/selección: candidatos, preprocesamiento, semillas, rejillas, regla de umbral, métricas, sensibilidad por episodio, resolución G5↔G6 y criterio de congelamiento previo a R05.

Hasta entonces no se ejecuta R04, no se construye el dataset incompleto y no se declara desempeño.
