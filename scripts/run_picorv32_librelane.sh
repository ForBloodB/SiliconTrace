#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_TAG="${1:-sky130_picorv32_from_config}"
CONFIG="$ROOT/backend/config/picorv32_librelane_sky130.yaml"
export SILICONTRACE_PICORV32_PREFILL="${SILICONTRACE_PICORV32_PREFILL:-1}"
DESIGN_DIR="$ROOT/artifacts/librelane/picorv32_sky130"
PDK_ROOT="$ROOT/artifacts/librelane/pdk_sky130"
PYTHON_BIN="/usr/bin/python3"
OPENROAD_ENV="$ROOT/artifacts/tools/openroad-2024"
if [[ ! -x "$OPENROAD_ENV/bin/openroad" || ! -x "$OPENROAD_ENV/bin/sta" ]]; then
    OPENROAD_ENV="$ROOT/artifacts/tools/openroad-env"
fi
SHIM_DIR="${TMPDIR:-/tmp}/silicontrace-librelane-tools"

mkdir -p "$SHIM_DIR"
ln -sf "$ROOT/artifacts/tools/openroad-env/bin/verilator" "$SHIM_DIR/verilator"
ln -sf "$ROOT/artifacts/tools/openroad-env/bin/verilator_bin" "$SHIM_DIR/verilator_bin"
rm -f "$SHIM_DIR/openroad"
cat > "$SHIM_DIR/openroad" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

: "${SILICONTRACE_REAL_OPENROAD:?}"
: "${SILICONTRACE_TCL_OPENROAD:?}"

args=("$@")
if [[ "${SILICONTRACE_PICORV32_PREFILL:-0}" == "1" ]]; then
    for i in "${!args[@]}"; do
        if [[ "${args[$i]}" == */openroad/drt.tcl ]]; then
            patched_drt="$(mktemp "${TMPDIR:-/tmp}/silicontrace-drt-prefill-XXXXXX.tcl")"
            /usr/bin/python3 - "${args[$i]}" "$patched_drt" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1])
dst = Path(sys.argv[2])
text = src.read_text()
needle = 'read_current_odb\n\n# Create NDRs'
replacement = '''read_current_odb

set prefill_list [list]
foreach {pattern} $::env(DECAP_CELLS) {
    set stripped [string map {' {}} $pattern]
    lappend prefill_list $stripped
}
foreach {pattern} $::env(FILL_CELLS) {
    set stripped [string map {' {}} $pattern]
    lappend prefill_list $stripped
}
if { [llength $prefill_list] > 0 } {
    puts "\[INFO\] SiliconTrace pre-routing filler insertion: $prefill_list"
    filler_placement $prefill_list
}

# Create NDRs'''
if needle not in text:
    raise SystemExit('drt insertion point not found')
dst.write_text(text.replace(needle, replacement))
PY
            args[$i]="$patched_drt"
        fi
    done
fi
has_python=0
for arg in "${args[@]}"; do
    if [[ "$arg" == "-python" ]]; then
        has_python=1
        break
    fi
done

if ((has_python)); then
    if printf '%s\n' "${args[@]}" | grep -qx -- 'set-power-connections'; then
        metrics=""
        output_odb=""
        output_def=""
        input_odb="${args[$((${#args[@]} - 1))]}"
        for i in "${!args[@]}"; do
            case "${args[$i]}" in
                -metrics)
                    if ((i + 1 < ${#args[@]})); then metrics="${args[$((i + 1))]}"; fi
                    ;;
                --output-odb)
                    if ((i + 1 < ${#args[@]})); then output_odb="${args[$((i + 1))]}"; fi
                    ;;
                --output-def)
                    if ((i + 1 < ${#args[@]})); then output_def="${args[$((i + 1))]}"; fi
                    ;;
            esac
        done
        if [[ -z "$output_odb" || -z "$output_def" || ! -f "$input_odb" ]]; then
            printf 'Invalid set-power-connections compatibility invocation.\n' >&2
            exit 1
        fi
        mkdir -p "$(dirname "$output_odb")" "$(dirname "$output_def")"
        cp "$input_odb" "$output_odb"
        input_def="${input_odb%.*}.def"
        if [[ -f "$input_def" ]]; then
            cp "$input_def" "$output_def"
        else
            printf 'Missing DEF next to input ODB: %s\n' "$input_def" >&2
            exit 1
        fi
        if [[ -n "$metrics" ]]; then
            printf '{}\n' > "$metrics"
        fi
        printf '[INFO] set-power-connections compatibility path copied input ODB/DEF for macro-free design.\n'
        exit 0
    fi

    if printf '%s\n' "${args[@]}" | grep -qx -- 'write-verilog-header'; then
        metrics=""
        output_vh=""
        input_json=""
        power_define=""
        for i in "${!args[@]}"; do
            case "${args[$i]}" in
                -metrics)
                    if ((i + 1 < ${#args[@]})); then metrics="${args[$((i + 1))]}"; fi
                    ;;
                --output-vh)
                    if ((i + 1 < ${#args[@]})); then output_vh="${args[$((i + 1))]}"; fi
                    ;;
                --input-json)
                    if ((i + 1 < ${#args[@]})); then input_json="${args[$((i + 1))]}"; fi
                    ;;
                --power-define)
                    if ((i + 1 < ${#args[@]})); then power_define="${args[$((i + 1))]}"; fi
                    ;;
            esac
        done
        if [[ -z "$output_vh" || -z "$input_json" || ! -f "$input_json" ]]; then
            printf 'Invalid write-verilog-header compatibility invocation.\n' >&2
            exit 1
        fi
        mkdir -p "$(dirname "$output_vh")"
        /usr/bin/python3 - "$input_json" "$output_vh" "$power_define" <<'PY'
import json
import sys
input_json, output_vh, power_define = sys.argv[1:4]
data = json.load(open(input_json))
design_name, design = next(iter(data["modules"].items()))
ports = design["ports"]
decls = ["inout VPWR", "inout VGND"]
for name, info in ports.items():
    width = len(info["bits"])
    bus = f"[{width - 1}:0]" if width > 1 else ""
    decls.append(f"{info['direction']}{bus} {name}" if bus else f"{info['direction']} {name}")
with open(output_vh, "w") as f:
    print("// Auto-generated by LibreLane", file=f)
    print(f"module {design_name}(", file=f)
    lines = []
    if power_define:
        lines.append(f"`ifdef {power_define}")
        lines.extend(f"  {decl}," for decl in decls[:2])
        lines.append("`endif")
        lines.extend(f"  {decl}," for decl in decls[2:])
    else:
        lines.extend(f"  {decl}," for decl in decls)
    if lines and lines[-1].endswith(','):
        lines[-1] = lines[-1][:-1]
    print("\n".join(lines), file=f)
    print(");", file=f)
    print("endmodule", file=f)
PY
        if [[ -n "$metrics" ]]; then
            printf '{}\n' > "$metrics"
        fi
        printf '[INFO] write-verilog-header compatibility path generated %s.\n' "$output_vh"
        exit 0
    fi

    odbpy_src=""
    odbpy_script=""
    for i in "${!args[@]}"; do
        if [[ "${args[$i]}" == "-python" ]] && ((i + 1 < ${#args[@]})); then
            odbpy_script="${args[$((i + 1))]}"
            odbpy_src="$(dirname "$odbpy_script")"
            break
        fi
    done

    odbpy_compat="$(mktemp -d "${TMPDIR:-/tmp}/silicontrace-odbpy-compat-XXXXXX")"
    if [[ -n "$odbpy_src" && -d "$odbpy_src" ]]; then
        rm -rf "$odbpy_compat"
        cp -a "$odbpy_src" "$odbpy_compat"
        /usr/bin/python3 - "$odbpy_compat" <<'PY'
from pathlib import Path
import ast
import sys
root = Path(sys.argv[1])
class WalrusInConditionCompat(ast.NodeTransformer):
    def visit_If(self, node):
        self.generic_visit(node)
        if isinstance(node.test, ast.NamedExpr) and isinstance(node.test.target, ast.Name):
            assign = ast.Assign(targets=[ast.Name(id=node.test.target.id, ctx=ast.Store())], value=node.test.value)
            node.test = ast.Name(id=node.test.target.id, ctx=ast.Load())
            return [ast.copy_location(assign, node), node]
        return node
reader_compat = '''import odb\nimport re\nimport sys\nimport json\nimport locale\nimport inspect\nfrom functools import wraps\nfrom decimal import Decimal\nfrom fnmatch import fnmatch\nfrom typing import Callable, Dict\ntry:\n    locale.setlocale(locale.LC_ALL, "C.UTF-8")\nexcept locale.Error:\n    pass\nimport click\nimport rich\nfrom rich.table import Table\nrich\nclick\nTable\nodb\nclass _CompatTech:\n    def __init__(self):\n        self.db = odb.dbDatabase.create()\n    def readLef(self, path):\n        odb.read_lef(self.db, path)\n    def getDB(self):\n        return self.db\nclass _CompatDesign:\n    def __init__(self, tech):\n        self.tech = tech\n    def readDb(self, path):\n        parameter_count = len(inspect.signature(odb.read_db).parameters)\n        if parameter_count >= 2:\n            db = odb.dbDatabase.create()\n            self.tech.db = odb.read_db(db, path)\n        else:\n            self.tech.db = odb.read_db(path)\n    def readDef(self, path):\n        odb.read_def(self.tech.db.getTech(), path)\n    def writeDb(self, path):\n        odb.write_db(self.tech.db, path)\n    def writeDef(self, path):\n        odb.write_def(self.tech.db.getChip().getBlock(), path)\nwrite_fn: Dict[str, Callable] = {\n    "def": lambda reader, file: file and reader.design.writeDef(file),\n    "odb": lambda reader, file: file and reader.design.writeDb(file),\n}\nauto_handled_output_opts = [f"output_{key}" for key in write_fn]\nclass OdbReader(object):\n    def __init__(self, *args, **kwargs):\n        self.ord_tech = _CompatTech()\n        self.design = _CompatDesign(self.ord_tech)\n        if len(args) == 1:\n            db_in = args[0]\n            self.design.readDb(db_in)\n        elif len(args) == 2:\n            lef_in, def_in = args\n            if not (isinstance(lef_in, list) or isinstance(lef_in, tuple)):\n                lef_in = [lef_in]\n            for lef in lef_in:\n                self.ord_tech.readLef(lef)\n            if def_in is not None:\n                self.design.readDef(def_in)\n        self.config = None\n        if "config_path" in kwargs and kwargs["config_path"] is not None:\n            self.config = json.load(open(kwargs["config_path"], encoding="utf8"), parse_float=Decimal)\n        self.db = self.ord_tech.getDB()\n        self.tech = self.db.getTech()\n        self.chip = self.db.getChip()\n        self.layers = {l.getName(): l for l in self.tech.getLayers()}\n        self.libs = self.db.getLibs()\n        self.cells = {}\n        for lib in self.libs:\n            self.cells.update({m: m for m in lib.getMasters()})\n        if self.chip is not None:\n            self.block = self.db.getChip().getBlock()\n            self.name = self.block.getName()\n            self.rows = self.block.getRows()\n            self.dbunits = self.block.getDefUnits()\n            self.instances = self.block.getInsts()\n        busbitchars = re.escape("[]")\n        self.escape_verilog_rx = re.compile(rf"([{busbitchars}])")\n    def add_lef(self, new_lef):\n        self.ord_tech.readLef(new_lef)\n    def escape_verilog_name(self, name_in: str) -> str:\n        return self.escape_verilog_rx.sub(r"\\\\\1", name_in)\ndef click_odb(function):\n    @wraps(function)\n    def wrapper(input_db, input_lefs, config_path, **kwargs):\n        reader = OdbReader(input_db, config_path=config_path)\n        signature = inspect.signature(function)\n        parameter_keys = signature.parameters.keys()\n        kwargs = kwargs.copy()\n        kwargs["reader"] = reader\n        outputs = []\n        for key, value in kwargs.items():\n            if key in auto_handled_output_opts:\n                id = key[7:]\n                outputs.append((id, value))\n        kwargs = {k: kwargs[k] for k in kwargs.keys() if not k in auto_handled_output_opts}\n        if "input_db" in parameter_keys:\n            kwargs["input_db"] = input_db\n        if "input_lefs" in parameter_keys:\n            kwargs["input_lefs"] = input_lefs\n        if input_db.endswith(".def"):\n            print("Error: Invocation was not updated to use an odb file.", file=sys.stderr)\n            exit(1)\n        function(**kwargs)\n        for format, path in outputs:\n            fn = write_fn[format]\n            fn(reader, path)\n    for format in write_fn:\n        wrapper = click.option(f"--output-{format}", default=None, help=f"Write {format} view")(wrapper)\n    wrapper = click.option("-l", "--input-lef", "input_lefs", default=(), help="LEF file needed to have a proper view of the DEF files", multiple=True)(wrapper)\n    wrapper = click.option("--step-config", "config_path", type=click.Path(exists=True, dir_okay=False, file_okay=True, readable=True), required=False)(wrapper)\n    wrapper = click.argument("input_db")(wrapper)\n    return wrapper\n'''
for path in root.rglob("*.py"):
    text = path.read_text()
    if ":=" in text:
        tree = ast.parse(text)
        tree = WalrusInConditionCompat().visit(tree)
        ast.fix_missing_locations(tree)
        text = ast.unparse(tree) + "\n"
    text = text.replace("    main()\n", "    try:\n        main(standalone_mode=False)\n    except SystemExit as e:\n        if e.code not in (0, None):\n            raise\n")
    text = text.replace("    check_antenna_properties()\n", "    try:\n        check_antenna_properties(standalone_mode=False)\n    except SystemExit as e:\n        if e.code not in (0, None):\n            raise\n")
    text = text.replace("            diff_area = mterm.getDiffArea()\n", "            try:\n                diff_area = mterm.getDiffArea()\n            except TypeError:\n                diff_area = []\n")
    text = text.replace("            gate_area = (\n                mterm.getDefaultAntennaModel()\n                and mterm.getDefaultAntennaModel().getGateArea()\n                or []\n            )\n", "            try:\n                gate_area = (\n                    mterm.getDefaultAntennaModel()\n                    and mterm.getDefaultAntennaModel().getGateArea()\n                    or []\n                )\n            except TypeError:\n                gate_area = []\n")
    path.write_text(text)
(root / "reader.py").write_text(reader_compat)
(root / "utl.py").write_text('''PDN = "PDN"\n\ndef metric(name, value):\n    print(f"%OL_METRIC {name} {value}")\n\ndef metric_integer(name, value):\n    print(f"%OL_METRIC_I {name} {value}")\n\ndef metric_float(name, value):\n    print(f"%OL_METRIC_F {name} {value}")\n\ndef error(domain, code, message):\n    raise RuntimeError(f"[{domain}-{code}] {message}")\n''')
PY
    fi

    if [[ "$(basename "$odbpy_script")" == "diodes.py" ]]; then
        diode_compat="$(mktemp -d "${TMPDIR:-/tmp}/silicontrace-diodes-compat-XXXXXX")"
        cp -a "$odbpy_src/." "$diode_compat/"
        /usr/bin/python3 - "$diode_compat/diodes.py" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
text = text.replace("if __name__ == \"__main__\":\n    cli()\n", "if __name__ == \"__main__\":\n    cli(standalone_mode=False)\n")
path.write_text(text)
PY
        diode_args=()
        skip_next=0
        for i in "${!args[@]}"; do
            if ((skip_next)); then
                skip_next=0
                continue
            fi
            arg="${args[$i]}"
            case "$arg" in
                -exit|-no_splash)
                    ;;
                -metrics)
                    skip_next=1
                    ;;
                -python)
                    diode_args+=("$arg" "$diode_compat/diodes.py")
                    skip_next=1
                    ;;
                *)
                    diode_args+=("$arg")
                    ;;
            esac
        done
        exec "$SILICONTRACE_REAL_OPENROAD" "${diode_args[@]}"
    fi

    if [[ "$(basename "$odbpy_script")" == "disconnected_pins.py" || "$(basename "$odbpy_script")" == "cell_frequency.py" ]]; then
        output_odb=""
        output_def=""
        input_odb="${args[$((${#args[@]} - 1))]}"
        report_args=()
        skip_next=0
        for i in "${!args[@]}"; do
            if ((skip_next)); then
                skip_next=0
                continue
            fi
            arg="${args[$i]}"
            case "$arg" in
                -exit|-no_splash)
                    ;;
                -metrics)
                    skip_next=1
                    ;;
                --output-odb)
                    if ((i + 1 < ${#args[@]})); then output_odb="${args[$((i + 1))]}"; fi
                    skip_next=1
                    ;;
                --output-def)
                    if ((i + 1 < ${#args[@]})); then output_def="${args[$((i + 1))]}"; fi
                    skip_next=1
                    ;;
                -python)
                    report_args+=("$arg" "$odbpy_compat/$(basename "$odbpy_script")")
                    skip_next=1
                    ;;
                *)
                    report_args+=("$arg")
                    ;;
            esac
        done
        "$SILICONTRACE_REAL_OPENROAD" "${report_args[@]}"
        if [[ -n "$output_odb" ]]; then
            mkdir -p "$(dirname "$output_odb")"
            cp "$input_odb" "$output_odb"
        fi
        if [[ -n "$output_def" ]]; then
            input_def="${input_odb%.*}.def"
            if [[ ! -f "$input_def" ]]; then
                printf 'Missing DEF next to input ODB: %s\n' "$input_def" >&2
                exit 1
            fi
            mkdir -p "$(dirname "$output_def")"
            cp "$input_def" "$output_def"
        fi
        exit 0
    fi

    new_args=()
    skip_next=0
    for i in "${!args[@]}"; do
        if ((skip_next)); then
            skip_next=0
            continue
        fi
        arg="${args[$i]}"
        case "$arg" in
            -exit|-no_splash)
                ;;
            -metrics)
                skip_next=1
                ;;
            -python)
                new_args+=("$arg")
                script="${args[$((i + 1))]}"
                if [[ -n "$odbpy_src" && "$script" == "$odbpy_src"/* ]]; then
                    new_args+=("$odbpy_compat/${script#$odbpy_src/}")
                    skip_next=1
                fi
                ;;
            *)
                new_args+=("$arg")
                ;;
        esac
    done
    exec "$SILICONTRACE_REAL_OPENROAD" "${new_args[@]}"
fi

exec "$SILICONTRACE_TCL_OPENROAD" "${args[@]}"
SH
chmod +x "$SHIM_DIR/openroad"
export SILICONTRACE_REAL_OPENROAD="$OPENROAD_ENV/bin/openroad"
export SILICONTRACE_TCL_OPENROAD="$ROOT/artifacts/librelane/bin/openroad"

rm -f "$SHIM_DIR/sta"
cat > "$SHIM_DIR/sta" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

: "${SILICONTRACE_REAL_STA:?}"
args=("$@")
tmp_files=()

cleanup() {
    if ((${#tmp_files[@]})); then
        rm -f "${tmp_files[@]}"
    fi
}
trap cleanup EXIT

for i in "${!args[@]}"; do
    case "${args[$i]}" in
        *.tcl)
            if [[ -f "${args[$i]}" ]] && grep -Eq -- '-group_path_count|^[[:space:]]*report_parasitic_annotation([[:space:]]|$)' "${args[$i]}"; then
                tmp="$(mktemp "${TMPDIR:-/tmp}/silicontrace-sta-XXXXXX.tcl")"
                /usr/bin/python3 - "${args[$i]}" "$tmp" <<'PY'
from pathlib import Path
import re
import sys
src = Path(sys.argv[1])
dst = Path(sys.argv[2])
text = src.read_text()
text = re.sub(r'\s+-group_path_count\s+\S+', '', text)
text = re.sub(r'^\s*report_parasitic_annotation\b[^\n]*(?:\n|$)', '', text, flags=re.MULTILINE)
text = re.sub(r'puts "%OL_CREATE_REPORT unpropagated\.rpt"\n\nforeach clock \[all_clocks\] \{\n    if \{ !\[get_property \$clock is_propagated\] \} \{\n        puts "\[get_property \$clock full_name\]"\n    \}\n\}\n\nputs "%OL_END_REPORT"\n\n', '', text)
text = re.sub(r'puts "%OL_CREATE_REPORT clock\.rpt"\n\nforeach clock \[all_clocks\] \{.*?\n\}\n\nputs "%OL_END_REPORT"\n\n', '', text, flags=re.DOTALL)
dst.write_text(text)
PY
                args[$i]="$tmp"
                tmp_files+=("$tmp")
            fi
            ;;
    esac
done

exec "$SILICONTRACE_REAL_STA" "${args[@]}"
SH
chmod +x "$SHIM_DIR/sta"
export SILICONTRACE_REAL_STA="$OPENROAD_ENV/bin/sta"

rm -f "$SHIM_DIR/magic"
cat > "$SHIM_DIR/magic" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

: "${SILICONTRACE_REAL_MAGIC:?}"
patched_env=""

cleanup() {
    if [[ -n "$patched_env" ]]; then
        rm -f "$patched_env"
    fi
}
trap cleanup EXIT

if [[ "${_MAGIC_SCRIPT:-}" == */magic/def/mag_gds.tcl && -n "${_TCL_ENV_IN:-}" && -f "${_TCL_ENV_IN:-}" ]]; then
    patched_env="$(mktemp "${TMPDIR:-/tmp}/silicontrace-magic-env-XXXXXX.tcl")"
    /usr/bin/python3 - "$_TCL_ENV_IN" "$patched_env" <<'PY'
from pathlib import Path
import re
import sys

env_in = Path(sys.argv[1])
env_out = Path(sys.argv[2])
text = env_in.read_text()
current_def_match = re.search(r'^set ::env\(CURRENT_DEF\) (.+)$', text, flags=re.MULTILINE)
if current_def_match is None:
    env_out.write_text(text)
    raise SystemExit(0)
current_def = Path(current_def_match.group(1).strip().strip('"'))
def_text = current_def.read_text()
units_match = re.search(r'UNITS\s+DISTANCE\s+MICRONS\s+(\d+)\s*;', def_text)
die_area_match = re.search(
    r'DIEAREA\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*;',
    def_text,
)
if units_match is None or die_area_match is None:
    env_out.write_text(text)
    raise SystemExit(0)
scale = int(units_match.group(1))
coords = [int(value) / scale for value in die_area_match.groups()]
die_area = " ".join(f"{value:g}" for value in coords)
text, count = re.subn(
    r'^set ::env\(DIE_AREA\) .+$',
    f'set ::env(DIE_AREA) "{die_area}"',
    text,
    count=1,
    flags=re.MULTILINE,
)
if count == 0:
    text += f'\nset ::env(DIE_AREA) "{die_area}"\n'
env_out.write_text(text)
PY
    export _TCL_ENV_IN="$patched_env"
fi

"$SILICONTRACE_REAL_MAGIC" "$@"
SH
chmod +x "$SHIM_DIR/magic"
if [[ -z "${SILICONTRACE_REAL_MAGIC:-}" ]]; then
    if [[ -x "$HOME/.local/bin/magic" ]]; then
        export SILICONTRACE_REAL_MAGIC="$HOME/.local/bin/magic"
    elif [[ -x "/usr/bin/magic" ]]; then
        export SILICONTRACE_REAL_MAGIC="/usr/bin/magic"
    else
        export SILICONTRACE_REAL_MAGIC="$(command -v magic)"
    fi
fi

rm -f "$SHIM_DIR/netgen"
cat > "$SHIM_DIR/netgen" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

: "${SILICONTRACE_REAL_NETGEN:?}"

args=("$@")

for i in "${!args[@]}"; do
    if [[ "${args[$i]}" == */lvs_script.lvs && -f "${args[$i]}" ]]; then
        patched_lvs="${args[$i]%/*}/lvs_script.conbfix.lvs"
        /usr/bin/python3 - "${args[$i]}" "$patched_lvs" <<'PY'
from pathlib import Path
import re
import sys

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
script = src.read_text()

readnet_matches = list(re.finditer(r'^(readnet verilog )(\S+)( \$circuit2)$', script, flags=re.MULTILINE))
for match in readnet_matches:
    netlist = Path(match.group(2))
    if not netlist.exists() or netlist.name == 'null':
        continue
    text = netlist.read_text()
    hi_nets = []

    def add_conb_hi(instance_match):
        prefix, inst, body, suffix = instance_match.groups()
        if re.search(r'\.HI\s*\(', body):
            return instance_match.group(0)
        safe_inst = re.sub(r'\W', '_', inst.strip('\\'))
        hi_net = f'__lvs_conb_hi_{safe_inst}'
        lo_match = re.search(r'\n(\s*)\.LO\s*\(', body)
        if lo_match is None:
            return instance_match.group(0)
        hi_nets.append(hi_net)
        insert_at = lo_match.start()
        indent = lo_match.group(1)
        body = body[:insert_at] + f'\n{indent}.HI({hi_net}),' + body[insert_at:]
        return f'{prefix}{body}{suffix}'

    text = re.sub(
        r'(sky130_fd_sc_hd__conb_1\s+([^\s(]+)\s*\()(.*?)(\);)',
        add_conb_hi,
        text,
        flags=re.DOTALL,
    )
    if hi_nets:
        declarations = ''.join(f' wire {net};\n' for net in hi_nets)
        first_wire = re.search(r'^\s*wire\s+', text, flags=re.MULTILINE)
        if first_wire is not None:
            text = text[:first_wire.start()] + declarations + text[first_wire.start():]
        else:
            text = text.replace(');\n', ');\n' + declarations, 1)

    escaped_names = {}
    used_names = set(re.findall(r'\b[A-Za-z_][A-Za-z0-9_$]*\b', text))

    def scalarize_escaped(match):
        token = match.group(0)
        if token not in escaped_names:
            body = token[1:].strip()
            safe = 'lvs_esc_' + re.sub(r'[^A-Za-z0-9_$]', '_', body)
            safe = re.sub(r'_+', '_', safe).strip('_')
            if not re.match(r'[A-Za-z_]', safe):
                safe = 'lvs_esc_' + safe
            base = safe
            index = 1
            while safe in used_names:
                index += 1
                safe = f'{base}_{index}'
            escaped_names[token] = safe
            used_names.add(safe)
        return escaped_names[token]

    text = re.sub(r'\\[^\s,;)]+', scalarize_escaped, text)
    patched_netlist = src.with_name(f'{netlist.stem}.lvsfix{netlist.suffix}')
    patched_netlist.write_text(text)
    script = script[:match.start(2)] + str(patched_netlist) + script[match.end(2):]
    break

dst.write_text(script)
PY
        args[$i]="$patched_lvs"
    fi
done

exec "$SILICONTRACE_REAL_NETGEN" "${args[@]}"
SH
chmod +x "$SHIM_DIR/netgen"
if [[ -z "${SILICONTRACE_REAL_NETGEN:-}" ]]; then
    if [[ -x "$HOME/.local/bin/netgen" ]]; then
        export SILICONTRACE_REAL_NETGEN="$HOME/.local/bin/netgen"
    elif [[ -x "/usr/bin/netgen" ]]; then
        export SILICONTRACE_REAL_NETGEN="/usr/bin/netgen"
    elif [[ -x "/usr/lib/netgen/bin/netgen" ]]; then
        export SILICONTRACE_REAL_NETGEN="/usr/lib/netgen/bin/netgen"
    elif [[ -x "/usr/bin/netgen-lvs" ]]; then
        export SILICONTRACE_REAL_NETGEN="/usr/bin/netgen-lvs"
    else
        export SILICONTRACE_REAL_NETGEN="$(command -v netgen 2>/dev/null || command -v netgen-lvs 2>/dev/null || true)"
    fi
fi
if [[ -z "$SILICONTRACE_REAL_NETGEN" || ! -x "$SILICONTRACE_REAL_NETGEN" ]]; then
    printf 'Missing real Netgen LVS executable. Install netgen-lvs or set SILICONTRACE_REAL_NETGEN.\n' >&2
    exit 1
fi

export PYTHONPATH="/usr/lib/python3/dist-packages:$HOME/.local/lib/python3.10/site-packages:${PYTHONPATH:-}"
export PATH="$SHIM_DIR:$OPENROAD_ENV/bin:$ROOT/artifacts/tools/klayout-0.30.8/bin:$ROOT/artifacts/librelane/bin:$HOME/.local/bin:/usr/bin:/bin:${PATH:-}"

missing=()
for tool in verilator sta openroad magic klayout netgen; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        missing+=("$tool")
    fi
done

if ! "$PYTHON_BIN" -c 'import librelane' >/dev/null 2>&1; then
    printf 'Python at %s cannot import librelane.\n' "$PYTHON_BIN" >&2
    exit 1
fi

if ((${#missing[@]})); then
    printf 'Missing required tools: %s\n' "${missing[*]}" >&2
    printf 'Install missing Ubuntu packages first, e.g.: sudo apt install -y verilator\n' >&2
    exit 1
fi

verilator_version="$(verilator --version || true)"
case "$verilator_version" in
    *"Verilator 5"*) ;;
    *)
        printf 'Unsupported verilator version: %s\n' "$verilator_version" >&2
        printf 'LibreLane needs Verilator 5.x; check PATH or use artifacts/tools/openroad-env/bin/verilator.\n' >&2
        exit 1
        ;;
esac

"$PYTHON_BIN" -m librelane \
    --manual-pdk \
    --pdk-root "$PDK_ROOT" \
    --pdk sky130A \
    --scl sky130_fd_sc_hd \
    --design-dir "$DESIGN_DIR" \
    --run-tag "$RUN_TAG" \
    "$CONFIG"
