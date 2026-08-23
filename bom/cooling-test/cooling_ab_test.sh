#!/usr/bin/env bash
# A/B test chłodzenia CPU (9950X3D): noctua (NH-D15 G2) vs lc142 (LC1-42).
# Walltime: ~61 min (10 idle + 40 load + 10 cooldown + setup).
# Użycie: systemd-inhibit --what=sleep:idle --why="cooling A/B" ./cooling_ab_test.sh noctua [ambient°C]
set -euo pipefail
tag=${1:?użycie: cooling_ab_test.sh <noctua|lc142> [ambient°C]}
cd "$(dirname "$0")"
command -v stress-ng >/dev/null || { echo "Brak stress-ng: sudo apt install stress-ng"; exit 1; }
ambient=${2:-}
[[ -n $ambient ]] || read -rp "Temperatura otoczenia [°C]: " ambient

csv="${tag}_$(date +%Y%m%d-%H%M).csv"
slog="stressng_${tag}_$(date +%Y%m%d-%H%M).log"
echo "# tag=$tag ambient=${ambient}C cpu=9950X3D kernel=$(uname -r) date=$(date -Is)" >"$csv"
echo "epoch,phase,tctl,tccd1,tccd2,cpu_fan_rpm,vrm,mhz_avg" >>"$csv"

snap() {
  local s tctl t1 t2 fan vrm mhz
  s=$(sensors 2>/dev/null)
  tctl=$(awk '/^Tctl/ {gsub(/[+°C]/,"",$2); print $2}' <<<"$s")
  t1=$(awk  '/^Tccd1/{gsub(/[+°C]/,"",$2); print $2}' <<<"$s")
  t2=$(awk  '/^Tccd2/{gsub(/[+°C]/,"",$2); print $2}' <<<"$s")
  fan=$(awk '/^CPU_Opt/{print $2+0}' <<<"$s"); [[ ${fan:-0} -gt 0 ]] || fan=NA   # ponytail: po swapie na AIO (LC1-42) pompa siedzi na AIO_PUMP, a asus-ec-sensors eksponuje tylko CPU_Opt → RPM niedostępne; NA zamiast fałszywego 0
  vrm=$(awk '/^VRM/{gsub(/[+°C]/,"",$2); print $2}' <<<"$s")
  mhz=$(awk '/MHz/{sum+=$4; n++} END{printf "%.0f", sum/n}' /proc/cpuinfo)
  echo "$(date +%s),$1,$tctl,$t1,$t2,$fan,$vrm,$mhz" >>"$csv"
}

phase() { # phase <nazwa> <sekundy>  — próbka co 5 s
  local end=$((SECONDS + $2))
  while ((SECONDS < end)); do snap "$1"; sleep 5; done
}

echo "[1/3] idle 10 min — nie dotykaj maszyny, GPU muszą być bezczynne (vLLM OFF)"
phase idle 600

echo "[2/3] obciążenie 40 min — stress-ng matrixprod, wszystkie wątki"
stress-ng --cpu 0 --cpu-method matrixprod --metrics-brief -t 40m &>"$slog" &
sng=$!
phase load 2400
wait "$sng"

echo "[3/3] cooldown 10 min"
phase cooldown 600

echo; echo "=== PODSUMOWANIE ($tag, otoczenie ${ambient}°C) ==="
awk -F, -v amb="$ambient" '
  /^#/ || /^epoch/ {next}
  $2=="idle"     {i[++ni]=$3}
  $2=="load"     {l[++nl]=$3; m[nl]=$8; f[nl]=$6; if($3>max)max=$3; le=$1}
  $2=="cooldown" && !ct && $3<50 {ct=$1}
  END{
    s=ni-59;  if(s<1)s=1; for(k=s;k<=ni;k++){si+=i[k]; ci++}
    s=nl-119; if(s<1)s=1; for(k=s;k<=nl;k++){sl+=l[k]; sm+=m[k]; cl++; if(f[k]+0>0){sf+=f[k]; cf++}}
    printf "idle  Tctl (śr. ost. 5 min):  %.1f °C\n", si/ci
    printf "load  Tctl (śr. ost. 10 min): %.1f °C  (ΔT nad otoczeniem: %.1f K)\n", sl/cl, sl/cl-amb
    printf "load  Tctl max:               %.1f °C\n", max
    if(cf) printf "load  zegar śr.: %.0f MHz, fan śr.: %.0f RPM\n", sm/cl, sf/cf
    else   printf "load  zegar śr.: %.0f MHz, fan: NA (pompa AIO nie raportuje w sensors)\n", sm/cl
    if(ct) printf "cooldown do <50 °C:          %d s\n", ct-le; else print "cooldown: nie osiągnięto <50 °C w 10 min"
  }' "$csv"
grep -h "bogo ops" "$slog" | tail -2 || true
echo "Dane: $csv, $slog"
