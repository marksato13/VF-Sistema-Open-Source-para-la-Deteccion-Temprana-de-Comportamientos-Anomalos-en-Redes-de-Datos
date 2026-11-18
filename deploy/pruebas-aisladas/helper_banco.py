#!/usr/bin/env python3
"""SOLO banco aislado: ejecuta cf_nft_helper.main con OTRO fichero de perfil.

El helper de produccion lee siempre /etc/cyberflow/nft-helper.perfil (constante, sin
argumentos ni variables de entorno). En el banco hace falta probar los dos perfiles en
el mismo contenedor, asi que este envoltorio pasa la ruta del fichero de perfil. Las
mismas comprobaciones de seguridad se aplican a ese fichero (root, sin escritura de
grupo/otros, ni en el fichero ni en su directorio). NO se instala en ningun host.

Uso: helper_banco.py <ruta_fichero_perfil>   (peticion JSON por stdin)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "enforce"))
import cf_nft_helper  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('{"ok": false, "rechazo": "uso: helper_banco.py <fichero_perfil>"}')
        sys.exit(2)
    sys.exit(cf_nft_helper.main(argv=[sys.argv[0]], ruta_perfil=sys.argv[1]))
