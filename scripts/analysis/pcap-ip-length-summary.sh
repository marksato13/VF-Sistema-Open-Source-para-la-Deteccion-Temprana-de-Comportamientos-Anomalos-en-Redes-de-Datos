#!/usr/bin/env bash
set -euo pipefail

if (( $# < 1 )); then
  echo "Uso: $0 ARCHIVO.pcap [ARCHIVO2.pcap ...]" >&2
  exit 2
fi

for pcap_file in "$@"; do
  [[ -r "$pcap_file" ]] || {
    echo "ERROR: PCAP no legible: $pcap_file" >&2
    exit 1
  }
done

export LC_ALL=C
{
  for pcap_file in "$@"; do
    tcpdump -nn -v -r "$pcap_file" 2>/dev/null || exit 1
  done
} |
  sed -n 's/^.*proto [^,]*, length \([0-9][0-9]*\)).*$/\1/p' |
  awk '
    {
      total++
      sum += $1
      if ($1 < 500) {
        small++
      } else if ($1 <= 1500) {
        target++
      } else {
        large++
      }
      if ($1 == 1500) mtu++
      if ($1 > max) max=$1
    }
    END {
      target_pct = (total > 0 ? (target / total) * 100 : 0)
      average = (total > 0 ? sum / total : 0)
      printf "{\n"
      printf "  \"schema_version\": 1,\n"
      printf "  \"length_scope\": \"IPv4 total length\",\n"
      printf "  \"total_ipv4_packets\": %d,\n", total
      printf "  \"small_lt_500\": %d,\n", small
      printf "  \"target_500_1500\": %d,\n", target
      printf "  \"large_gt_1500\": %d,\n", large
      printf "  \"exactly_1500\": %d,\n", mtu
      printf "  \"target_percentage\": %.4f,\n", target_pct
      printf "  \"average_ip_length\": %.2f,\n", average
      printf "  \"maximum_ip_length\": %d\n", max
      printf "}\n"
    }
  '
