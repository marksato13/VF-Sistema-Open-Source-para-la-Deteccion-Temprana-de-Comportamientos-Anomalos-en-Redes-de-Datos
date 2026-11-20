set -u
# Reconstruye la particion de la nota L (29-sep) y la verifica contra el hash que
# ensayo-if-v2.json -el paquete del que salio el modelo desplegado- dejo anotado.
# Solo lee el dataset y escribe en artifacts/aprendizaje/base/. No toca el modelo.
cd ~/cyberflow
B=artifacts/aprendizaje/base
mkdir -p "$B"
.venv/bin/python - <<'EOF'
import csv
N = 337980                      # filas elegibles de la nota L
src = "artifacts/linea-base/multilayer-v3.csv"
dst = "artifacts/aprendizaje/base/linea-base-nota-L.csv"
with open(src, newline="", encoding="utf-8") as f, open(dst, "w", newline="", encoding="utf-8") as g:
    r = csv.reader(f); w = csv.writer(g)
    cab = next(r); w.writerow(cab)
    i = cab.index("eligible_training"); n = 0
    for fila in r:
        if fila[i].lower() == "true":
            w.writerow(fila); n += 1
            if n == N:
                break
print("filas elegibles copiadas:", n)
EOF
.venv/bin/python scripts/dataset/particionar_linea_base.py --solo-elegibles \
  --entrada "$B/linea-base-nota-L.csv" --salida "$B/particionado-nota-L.csv" \
  --informe "$B/particion-nota-L.json" | python3 -c "import json,sys; t=sys.stdin.read(); d=json.loads(t[:t.rindex('}')+1]); print('reparto', d['reparto'], 'guarda', d['descartadas_por_guarda'], 'fuga', d['fuga_temporal'])"
OBT=$(sha256sum "$B/particionado-nota-L.csv" | cut -d' ' -f1)
ESP=$(python3 -c "import json;print(json.load(open('artifacts/preliminar/ensayo-if-v2.json'))['entrada_sha256'])")
echo "obtenido: $OBT"; echo "esperado: $ESP"
[ "$OBT" = "$ESP" ] && echo "IDENTICA a la de la nota L" || echo "DISTINTA"
