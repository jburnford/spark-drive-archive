#!/bin/bash
#SBATCH --account=def-jic823_gpu
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=/scratch/jic823/open_empire_ocr/logs/%x_%A_%a.out
#
# Open Empire (Tier 1 open dictionaries & botany) -> Chandra 2 on Narval.
# Sized for short 2-3h backfill chunks even with low fairshare.
# One array task = one bundle file (bundles/<BUNDLE_SET>/<N>.tsv: tag, rel_pdf, pages, 0-based range).
# Reuses /project/def-jic823/{canada50/containers/vllm.sif,hf_cache,ceylon_ocr/{venv,chandra_ceylon.py,check_ceylon.py}} (read-only).
set -uo pipefail
BASE=/scratch/jic823/open_empire_ocr; OUT=$BASE/out; PDFS=$BASE/pdfs
CODE=/project/def-jic823/ceylon_ocr
SIF=/project/def-jic823/canada50/containers/vllm.sif; HF_CACHE=/project/def-jic823/hf_cache; MODEL=datalab-to/chandra-ocr-2
MAX_OUT=16000; MAX_MODEL_LEN=40000; PAR=${PAR:-4}
CHANDRA_FLAGS=(--include-headers-footers --paginate_output --max-output-tokens $MAX_OUT --no-images --no-html)
CONFIG="chandra ${CHANDRA_FLAGS[*]} | vllm --max-model-len $MAX_MODEL_LEN"
module load apptainer/1.3.5 python/3.11 2>/dev/null
BUNDLE=$BASE/bundles/${BUNDLE_SET:-main}/${SLURM_ARRAY_TASK_ID:-1}.tsv
[ -f "$BUNDLE" ] || { echo "no bundle $BUNDLE"; exit 1; }
mkdir -p "$OUT/_failed" "$BASE/logs" "$BASE/tmp"/{home,triton,flashinfer,inductor,xdg}
[ -f "$OUT/RUN_CONFIG" ] || echo "$CONFIG" > "$OUT/RUN_CONFIG"
[ "$(cat $OUT/RUN_CONFIG)" = "$CONFIG" ] || { echo "REFUSING: RUN_CONFIG differs"; exit 1; }
echo "[job] $(hostname) bundle=$BUNDLE pieces=$(wc -l < $BUNDLE) pages=$(awk -F'\t' '{s+=$3} END{print s}' $BUNDLE) config: $CONFIG"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
export APPTAINER_TMPDIR=$BASE/tmp
PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
SLOG=$BASE/logs/vllm-${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID:-1}.log
apptainer exec --nv --home "$BASE/tmp/home:/home/$USER" --bind "$HF_CACHE:/root/.cache/huggingface" --bind "$BASE:$BASE" \
    --env HF_HOME=/root/.cache/huggingface --env HF_HUB_OFFLINE=1 --env TRITON_CACHE_DIR=$BASE/tmp/triton \
    --env FLASHINFER_WORKSPACE_BASE=$BASE/tmp/flashinfer --env TORCHINDUCTOR_CACHE_DIR=$BASE/tmp/inductor --env XDG_CACHE_HOME=$BASE/tmp/xdg \
    "$SIF" vllm serve "$MODEL" --host 127.0.0.1 --port "$PORT" --served-model-name chandra --dtype bfloat16 \
    --max-model-len $MAX_MODEL_LEN --max-num-seqs 24 --max-num-batched-tokens 16384 --gpu-memory-utilization 0.90 \
    --enable-prefix-caching --trust-remote-code --mm-processor-kwargs '{"min_pixels":3136,"max_pixels":6291456}' > "$SLOG" 2>&1 &
VLLM_PID=$!; trap 'kill $VLLM_PID 2>/dev/null; wait $VLLM_PID 2>/dev/null' EXIT INT TERM
for i in $(seq 1 180); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/v1/models)" = 200 ] && { echo "[job] server ready after $((i*10))s"; break; }
    kill -0 $VLLM_PID 2>/dev/null || { echo "[job] SERVER DIED"; tail -40 "$SLOG"; exit 1; }
    sleep 10
done
source $CODE/venv/bin/activate
export VLLM_API_BASE=http://127.0.0.1:$PORT/v1 VLLM_MODEL_NAME=chandra VLLM_API_KEY=EMPTY OUT PDFS MAX_OUT CODE
piece() {  # tag rel pages range
    local tag=$1 rel=$2 pages=$3 range=$4 dest=$OUT/$1
    python3 $CODE/check_ceylon.py "$dest" "$pages" $MAX_OUT >/dev/null 2>&1 && { echo "[skip] $tag"; return 0; }
    [ -d "$dest" ] && mv "$dest" "$OUT/_failed/$tag.$(date +%s)"
    mkdir -p "$dest"; local t0=$(date +%s)
    local cmd=(python3 $CODE/chandra_ceylon.py "$PDFS/$rel" "$dest" --method vllm --max-workers 8 --batch-size 32 "${CHANDRA_FLAGS[@]}")
    [ -n "$range" ] && cmd+=(--page-range "$range")
    "${cmd[@]}" > "$dest.log" 2>&1; local rc=$?
    local res; res=$(python3 $CODE/check_ceylon.py "$dest" "$pages" $MAX_OUT 2>&1); local vrc=$?
    echo -e "$res\t$(( $(date +%s)-t0 ))s\trc=$rc" >> $OUT/_validation.tsv
    if [ $rc -eq 0 ] && [ $vrc -eq 0 ]; then echo "[ok] $tag $pages pp $(( $(date +%s)-t0 ))s"; mv "$dest.log" "$dest/"; else echo "[FAIL] $tag rc=$rc $res"; mv "$dest" "$OUT/_failed/$tag.$(date +%s)"; mv "$dest.log" "$OUT/_failed/"; fi
}
export -f piece; export CHANDRA_FLAGS_STR="${CHANDRA_FLAGS[*]}"
piece_wrap() { CHANDRA_FLAGS=($CHANDRA_FLAGS_STR); piece "$@"; }; export -f piece_wrap
T0=$(date +%s)
awk -F'\t' '{printf "%s\0%s\0%s\0%s\0", $1,$2,$3,$4}' "$BUNDLE" | xargs -0 -n4 -P $PAR bash -c 'piece_wrap "$@"' _
echo "[job] DONE bundle in $(( ($(date +%s)-T0)/60 )) min"
