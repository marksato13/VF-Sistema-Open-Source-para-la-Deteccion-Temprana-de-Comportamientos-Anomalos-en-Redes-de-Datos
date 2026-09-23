# Laboratorio

**Esto no es el producto.** Es el aparato experimental: genera el tráfico de
fondo sobre el que se recalibra el modelo, y vive aquí por la misma razón que
`scripts/kali/` — sin él, las cifras publicadas no se pueden reproducir.

| Fichero | Dónde corre | Qué hace |
|---|---|---|
| `servidor_lab.py` | servidor de la DMZ | HTTP y HTTPS con errores controlados: 401, 404, 500 y respuestas lentas |
| `clientes_lab.py` | equipos de la VLAN de usuarios | Seis perfiles de comportamiento, uno por IP |
| `BANCO-DE-PRUEBAS.md` | — | Qué máquinas hacen falta, con qué recursos, en qué VLAN y por qué |

## Por qué está hecho así

**Una IP por perfil.** El motor puntúa por IP: cada alias es una entidad
distinta para el modelo.

**Llegadas exponenciales, no temporizadores.** Con un intervalo fijo el modelo
aprende un metrónomo y marca como anomalía cualquier variación normal.

**Curva diaria** con pausa de comida, noche y fin de semana. Sin variación
diaria no se puede demostrar que el modelo *tolera* la variación normal.

**Fallos a propósito**: puertos cerrados, descargas abandonadas a mitad, 401,
404, 500 y NXDOMAIN. Sin ellos `syn_completion_ratio_10s`, `rst_ratio_10s`,
`http_auth_failure_ratio_60s` y `dns_nxdomain_ratio_60s` no tienen varianza:
en una red donde todo funciona siempre, esas columnas son constantes.

Solo biblioteca estándar: las máquinas del laboratorio pueden no tener salida
a Internet para instalar paquetes.

## Uso

```bash
python3 servidor_lab.py --direccion 10.10.30.10 --puerto 80
python3 servidor_lab.py --direccion 10.10.30.10 --puerto 443 --cert cert.pem --clave clave.pem

python3 clientes_lab.py --listar-perfiles
python3 clientes_lab.py --perfil ofimatica --origen 10.10.20.21 --servidor 10.10.30.10 --dns 10.10.10.20
python3 clientes_lab.py --perfil ofimatica --servidor 10.10.30.10 --una-vuelta
```

`--una-vuelta` ejecuta una acción de cada tipo y sale: sirve para comprobar
que todas funcionan antes de dejarlo tres días corriendo.

## Perfiles

| Perfil | Ritmo | Qué caracteriza |
|---|---|---|
| `ofimatica` | 3 s | Navegación ligera, DNS, algún 401 y 404 |
| `navegacion` | 1,5 s | Mucho HTTPS, descargas medianas, NXDOMAIN, abandonos |
| `descargas` | 8 s | Transferencias grandes: mueve tamaño de paquete y proporción tx/rx |
| `aplicacion` | 2 s | API: POST, 500 y respuestas lentas |
| `ligero` | 12 s | Poca actividad, sobre todo DNS e ICMP |
| `erratico` | 5 s | Ráfagas y silencios; ensancha la distribución de la línea base |
