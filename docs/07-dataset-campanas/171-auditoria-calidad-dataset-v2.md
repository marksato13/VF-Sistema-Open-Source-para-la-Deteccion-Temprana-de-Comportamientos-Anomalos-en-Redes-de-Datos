# Auditoría de calidad del dataset multilayer-v2

`audit_multilayer_v2.py` comprueba el contrato de 28 features, valores
faltantes, columnas constantes, vectores duplicados, etiquetas y que ningún
episodio aparezca en más de una partición. También registra la cobertura de
capas declarada por el esquema.

El reporte generado debe conservarse junto al dataset; un `gates.pass=false`
impide declarar el conjunto listo para modelado.

La auditoría actual pasa integridad, etiquetas, ausencia de faltantes y
separación de episodios. No hay vectores duplicados exactos. Sí encuentra
tres features constantes en las 93 ventanas combinadas:
`fragment_ratio_10s`, `http_status_5xx_ratio_60s` y
`tls_handshake_failure_ratio_60s`. No se eliminan después de observar los
datos. La interpretación correcta es una brecha de cobertura experimental:
la matriz normal no generó fragmentación IP, respuestas 5xx legítimas ni
handshakes TLS fallidos. Antes de congelar una versión productiva se deben
añadir escenarios controlados para esas señales o justificar formalmente su
exclusión en una revisión v2.1.
