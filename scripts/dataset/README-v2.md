# Dataset v2

`extract_campaign_v2.sh` valida una campaña cerrada y convierte su PCAP/EVE
en `multilayer-v2.csv`. `build_multilayer_v2_dataset.py` combina sólo filas
elegibles y exige un mapa explícito `campaign_id → train|validation|test`.
Cada campaña es un `episode_id`; si un episodio aparece en más de una
partición, el ensamblador falla. El pipeline v1 permanece separado.

Ejemplo de mapa:

```json
{"F2N-DNS-MULTI-10-R01":"train","F2N-DNS-MULTI-10-R04":"validation","F2N-DNS-MULTI-10-R05":"test"}
```
