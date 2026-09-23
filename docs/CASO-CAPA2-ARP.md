# Caso medido: una máquina que solo la capa 2 ve

Evidencia de por qué `arp_request_rate_10s` justifica su sitio. No es un
ejemplo construido: es una máquina real de la red de producción, medida el
2026-09-23 desde el espejo SPAN del sensor.

## Qué se observó

```
MAC de origen   00:0c:29:09:6a:de      (OUI 00:0c:29 = VMware)
Dirección       10.10.20.53            VLAN 20 (USUARIOS)
Nombre          m4rk-VMware20-1        (concesión DHCP activa en pfSense)
Puerto del conmutador   Gi1/0/23       el troncal del cortafuegos
```

Dos mediciones separadas por unas tres horas, sobre ~900 s de anillo cada una:

| | 1ª medición | 2ª medición |
|---|---|---|
| Peticiones ARP | 709 en 916 s | 660 en 899 s |
| Tasa | 0,77 /s | 0,73 /s |
| Respuestas ARP propias | 0 | 0 |
| Destinos distintos | 2 | 2 |
| Paquetes IP suyos | **0** | **0** |

Pregunta siempre por las mismas dos direcciones, repartidas casi por igual:
`10.10.10.20` y `10.10.10.21` — los dos controladores de dominio, que están en
la **VLAN 10**. Separación entre tramas: mínimo 1,011 s, mediana 1,024 s. Un
reintento de un segundo, sostenido.

## Por qué es una anomalía real y no ruido

Un equipo de la VLAN 20 **no debe** hacer ARP por una dirección de la VLAN 10:
lo que está fuera de su subred va a la pasarela `10.10.20.1`. Preguntar por ARP
directamente significa que su pila cree que los controladores están en su
propio segmento.

El ámbito DHCP de pfSense para la VLAN 20 es correcto —`netmask 255.255.255.0`,
`option routers 10.10.20.1`— así que la causa no es lo que entrega el servidor.
La misma MAC tiene una concesión anterior en `10.10.10.50`: **la máquina estuvo
en la VLAN 10 y se movió a la 20**, y conserva de aquello algo que hace que
`10.10.10.0/24` le parezca local.

Como los controladores están de verdad en otra VLAN, nadie responderá nunca.
Es un bucle indefinido, y por eso no hay ni un paquete IP suyo: sin resolver,
no llega a enviar nada.

## Lo que esto demuestra

Las 28 variables de `multilayer-v2` puntúan esa máquina como **silencio
absoluto**: `packet_count_10s = 0` en todas sus ventanas, porque no emite ni un
paquete IP que el espejo pueda atribuirle. Para el modelo congelado, esa
entidad no existe.

En capa 2 sí existe, y con una firma clara: 0,7 peticiones ARP por segundo, a
dos destinos fijos, durante horas.

**No hace falta fabricar el caso de uso.** Estaba ocurriendo antes de
escribirlo, y se reproduce en dos minutos: basta dejar una dirección estática
de otra VLAN en una máquina que se mueve de segmento.

## Límite honesto de esta observación

Que no se vean respuestas ARP no lo prueba por sí solo: el espejo tiene origen
en los troncales del cortafuegos, y las respuestas ARP son unidifusión — solo
llegan las dirigidas a él. Lo que sí es concluyente es que una difusión emitida
en la VLAN 20 no puede ser contestada por un equipo de la VLAN 10.

## Consecuencia para la línea base

Mientras esa máquina siga emitiendo, **contamina el entrenamiento**: el modelo
aprendería 0,7 peticiones/s como el valor normal de `arp_request_rate_10s` y
perdería justo la sensibilidad que justifica la variable. Hay que apagarla o
corregirla antes de las 72 h, después de conservar esta medición.
