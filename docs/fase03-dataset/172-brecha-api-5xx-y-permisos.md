# Brecha de cobertura HTTP 5xx

La campaña de calibración `CAL-G7-API-5XX-R01` se ejecutó fuera del dataset y
se excluyó por `purpose=calibration`. La evidencia PCAP/EVE fue íntegra, pero
el escenario terminó con código 1 porque el Cliente recibió `404` para
`GET /api/error`, aunque el contrato local esperaba `500`.

La causa comprobada es una divergencia de despliegue: el servicio remoto
`/usr/local/lib/ppi-api/ppi-api.py` sólo implementa `/api/health`,
`/api/profile`, `/api/login`, PUT y DELETE; no tiene la ruta `/api/error`.
`useransible` puede leer el servicio, pero su sudoers actual sólo permite
reiniciar la VM, no instalar/modificar archivos bajo `/usr/local` ni reiniciar
`ppi-api`.

No se incorpora esta campaña al dataset. Para cubrir de forma válida
`http_status_5xx_ratio_60s` se requiere una ventana administrativa autorizada
para desplegar una ruta 500 controlada, reiniciar el servicio y repetir una
calibración excluida antes de añadir cualquier episodio a una futura v2.1.

## Corrección y calibración posterior

Se habilitó temporalmente el permiso mínimo para `useransible`, se desplegó el
archivo versionado y se reinició `ppi-api`. La ruta respondió `500` y la
calibración `CAL-G7-API-5XX-R02` terminó con evidencia completa, código 0 y
extracción v2 válida. La ventana midió
`http_status_5xx_ratio_60s=0.15`. Al ser calibración, permanece excluida del
dataset normal; sirve como evidencia para incorporar un perfil legítimo 5xx
en una futura matriz v2.1.
