# Banco de pruebas aislado (Etapa 2): Debian 13 como DC1/srv-dmz, sin red del laboratorio.
# Imagen cyberflow-etapa2-banco:2 (añade git: lo usa la fixture de tests/test_f1_dataset_builder.py).
FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends nftables iproute2 openssl python3 python3-pytest python3-numpy python3-sklearn python3-joblib dnsutils procps sudo ca-certificates git && rm -rf /var/lib/apt/lists/*
WORKDIR /repo
