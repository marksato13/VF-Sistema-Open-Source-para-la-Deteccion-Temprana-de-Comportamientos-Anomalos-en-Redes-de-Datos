# Revisión Claude — canario TCP REFUSED 5 F1

Fecha: 23 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial del resumen técnico, sin acceso operativo ni edición.

## Dictamen inicial

Claude emitió **ACEPTAR CONDICIONADO**. Consideró válido incluir rechazos legítimos para reducir falsos positivos cuando aparezcan RST o SYN sin SYN/ACK. Confirmó coherencia entre cinco SYN, cinco RST/ACK, cero pérdidas, features L4 y ausencia esperada de eventos L7.

La condición fue verificar si `unique_dst_port_ratio_30s=0.2` era compatible con el contrato G5.

## Cierre reproducible

La condición pasó:

- diccionario G5: `puertos destino únicos / intentos TCP+UDP`;
- extractor: `len({target_port}) / len(transport_attempts30)`;
- episodio: un puerto destino / cinco intentos = `1/5=0.2`;
- la prueba sintética cubre la misma implementación.

No se debe confundir los cinco puertos efímeros **de origen** con puertos destino. Tras recibir la fórmula y el conteo, Claude emitió **ACEPTAR**.

## Correcciones a la revisión

Se corrigieron estas afirmaciones de Claude antes de documentar el resultado:

1. Los cinco puertos efímeros pertenecen a un solo origen `10.20.0.20`; no hay orígenes diversos.
2. El generador sí introduce `sleep 0.5`; los SYN observados se separaron aproximadamente 0.61 s.
3. El ensamblador real quedó en 17 aceptadas y 128 faltantes, no 16/129.
4. El siguiente perfil de la matriz es `TCP-50M/R01`; no existe `TCP-RST-RCVD-5` en la matriz vigente.

## Límites aceptados

- dos ventanas del mismo episodio no son repeticiones independientes;
- una IP y un puerto cerrado no representan diversidad horizontal o vertical;
- cinco rechazos de baja frecuencia no caracterizan un escaneo;
- la ausencia de eventos de aplicación es esperada porque el RST ocurre en L4;
- una fase posterior debe demostrar separación frente a anomalías de mayor tasa y diversidad.

Dictamen final: **ACEPTAR CON LIMITACIONES**.
