# Cambio de modelo de acceso: root permanente para useransible (fase de desarrollo)

- **Fecha:** 2026-08-18
- **Decisión de:** el usuario (dueño del laboratorio), explícita e informada.
- **Aplica a:** las cuatro VMs del laboratorio (Sensor, Servidor, Kali, Cliente).
- **Estado:** aplicado y verificado en las cuatro VMs (`sudo -n true` confirmado exitoso en 10.10.10.20/30/40/50 el mismo día).

## Qué cambió

Hasta este punto, el modelo de acceso documentado y validado era: `useransible`
sin sudo general, con únicamente los helpers estrechos ya versionados
(`ppi-suricata-metrics`, `ppi-pcap-control`, `ppi-enforce`) autorizados vía
sudoers, y cualquier operación fuera de eso requería una concesión de acceso
root **temporal** (clave SSH agregada y revocada en cada uso, documentado en
cada despliegue de `docs/fase05-motor-tiempo-real/` y `docs/fase06-dashboard/`).

A partir de esta fecha, `useransible` tiene sudo sin restricción
(`ALL=(ALL) NOPASSWD: ALL`) y **permanente** en las cuatro VMs, reemplazando
el ciclo de concesión/revocación por cada cambio.

## Por qué (la razón real, no una excusa)

El ciclo de acceso temporal —agregar una llave, ejecutar el cambio, verificar,
revocar, confirmar la revocación— añadía fricción real y repetida en cada
iteración de la fase de desarrollo activo (motor, enforcement, dashboard),
donde los cambios de infraestructura eran frecuentes. Se le explicó
directamente al usuario, antes de esta decisión, la tensión que esto genera:

> Este mismo repositorio documentó y validó como evidencia de seguridad que
> **la prueba negativa con `/usr/bin/id` falla en las cuatro VMs** bajo el
> modelo anterior (`docs/fase00-infraestructura/`). Root permanente e
> irrestricto contradice esa evidencia mientras esté vigente — si un jurado
> pregunta quién tiene acceso root permanente a los sistemas, la respuesta
> pasa a ser "un agente de IA, sin restricción, todo el tiempo", lo cual
> debilita la narrativa de aislamiento que el proyecto defiende.

El usuario confirmó explícitamente que quiere proceder así de todas formas,
priorizando velocidad de iteración durante el desarrollo activo sobre
mantener esa evidencia vigente en este momento.

## Qué significa esto para la evidencia ya registrada

- `docs/fase00-infraestructura/` y las menciones en `CLAUDE.md` sobre
  "`useransible` no dispone de sudo general" describen el **modelo de acceso
  original, validado en su momento** — siguen siendo un hecho histórico
  cierto sobre esa fecha, no se reescriben ni se ocultan.
- Este documento deja constancia expresa de que el modelo cambió, cuándo, y por
  decisión de quién — para que no haya una contradicción silenciosa entre lo
  que el repositorio afirma sobre permisos y lo que realmente hay desplegado.

## Recomendación para el cierre del proyecto

Antes de considerar el sistema "cerrado" para la defensa final, se recomienda
**volver al modelo de sudoers estrecho** (revocar `ALL=(ALL) NOPASSWD: ALL`,
dejar únicamente los helpers versionados ya usados en producción:
`ppi-suricata-metrics`, `ppi-pcap-control`, `ppi-enforce`, y los reinicios de
servicio que realmente hagan falta) para que la evidencia de aislamiento
vuelva a ser cierta en el momento de la defensa. Esta recomendación queda
registrada aquí; ejecutarla es una decisión del usuario cuando decida que el
desarrollo activo terminó.
