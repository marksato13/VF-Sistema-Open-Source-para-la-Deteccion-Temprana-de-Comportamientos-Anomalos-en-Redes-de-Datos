set -u
cd ~/cyberflow
PY=$(systemctl show -p ExecStart --value ppi-dashboard | grep -o 'path=[^ ;]*' | head -1 | cut -d= -f2)
echo "python del panel: $PY"
"$PY" - <<'EOF'
import sys
sys.path.insert(0, "scripts/engine")
import dashboard as d
e = d.estado_aprendizaje(None)
print("disponible:", e["disponible"], "| toml:", e.get("toml"), "| activo:", e["politica"]["activo"],
      "| registro integro:", e["registro_integro"], "| oro:", bool(e["oro"]), "| lotes:", len(e["lotes"]))
h = d.html_por_rol(d.HTML, "admin"); l = d.html_por_rol(d.HTML, "lector")
print("admin recibe la seccion:", 'id="s-aprendizaje"' in h, "| lector:", 'id="s-aprendizaje"' in l)
print("/api/aprendizaje solo admin:", "/api/aprendizaje" in d.RUTAS_ADMIN)
EOF
