---
name: ppi-release-readiness
description: "Audita si una entrega, versión o publicación del PPI está lista: coherencia documental, pruebas, hashes, licencias, secretos, reproducibilidad y límites. Publicar solo con autorización explícita."
---

# Preparación de entrega

Lee primero `docs/agent-context/ppi-data-science-context.md` desde la raíz del repositorio.

## Checklist

1. Sincroniza referencias remotas de forma no destructiva y revisa cambios
   propios y ajenos.
2. Ejecuta suite, auditoría del dataset, verificación SHA-256 y generadores en
   modo reproducible.
3. Busca cifras contradictorias, rutas rotas, documentos generados obsoletos y
   afirmaciones planificadas como obtenidas.
4. Comprueba licencias, cita, contacto, privacidad, archivos grandes, pickles y
   ausencia de secretos.
5. Verifica que datasheet, model card, system card, PPI y README describan la
   misma versión y sus limitaciones.
6. Revisa CI, tags, rama protegida y release cuando el acceso lo permita; no
   infieras su estado si la consulta falla.
7. Antes de publicar, muestra diff y archivos exactos. No uses `git add .` ni
   publiques en `main` sin autorización expresa.

## Salida

Dictamen listo/no listo, bloqueos, riesgos y comandos ejecutados. Commit, push,
PR o release requieren alcance explícito del usuario.
