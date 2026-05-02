#!/usr/bin/env python3
"""Export a reproducible KiCad project from the SiliconTrace demo assets."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_NAME = "picorv32_test_board"
TEMPLATE_DIR = PROJECT_ROOT / "kicad" / "test_board"
SYMBOL_SRC = PROJECT_ROOT / "kicad" / "symbols" / "picorv32.kicad_sym"
FOOTPRINT_SRC = PROJECT_ROOT / "kicad" / "footprints" / "QFN-48_7x7mm_P0.5mm.kicad_mod"
BACKEND_DIR = PROJECT_ROOT / "artifacts" / "backend"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, data: str) -> None:
    path.write_text(data, encoding="utf-8")


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"missing required KiCad source file: {path}")


def normalize_project_text(data: str, design_top: str) -> str:
    title = f"{design_top} Generated Test Board"
    data = data.replace("PicoRV32 RISC-V Test Board", title)
    data = data.replace("SKY130 PicoRV32 Implementation", f"SKY130 {design_top} backend export")
    return data


def normalize_qfn_power_pads(board_text: str) -> str:
    qfn_start = board_text.find('(footprint "kicad:QFN-48_7x7mm_P0.5mm"')
    if qfn_start < 0:
        return board_text

    qfn_end = board_text.find("\n  (footprint ", qfn_start + 1)
    if qfn_end < 0:
        qfn_end = len(board_text)

    qfn_text = board_text[qfn_start:qfn_end]
    net_by_pad = {
        "25": '(net 0 "")',
        "26": '(net 0 "")',
        "27": '(net 2 "+3V3")',
        "28": '(net 1 "GND")',
    }
    lines = []
    for line in qfn_text.splitlines():
        pad_match = re.search(r'\(pad\s+"([^"]+)"', line)
        if pad_match and pad_match.group(1) in net_by_pad:
            line = re.sub(r'\(net\s+\d+\s+"[^"]*"\)', net_by_pad[pad_match.group(1)], line)
        lines.append(line)

    return board_text[:qfn_start] + "\n".join(lines) + board_text[qfn_end:]


def extract_sexpr(text: str, start: int) -> tuple[str, int]:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start:index + 1], index + 1
    raise ValueError("unterminated KiCad s-expression")


def extract_embedded_symbol_libraries(schematic_text: str) -> dict[str, list[str]]:
    start = schematic_text.find("(lib_symbols")
    if start < 0:
        return {}

    lib_symbols, _ = extract_sexpr(schematic_text, start)
    grouped: dict[str, list[str]] = {}
    cursor = 0
    while True:
        match = re.search(r"\n\s+\(symbol\s+\"([^\"]+)\"", lib_symbols[cursor:])
        if not match:
            break
        symbol_start = cursor + match.start()
        symbol_start = lib_symbols.find("(symbol", symbol_start)
        symbol_expr, symbol_end = extract_sexpr(lib_symbols, symbol_start)
        full_name = re.search(r'\(symbol\s+"([^"]+)"', symbol_expr).group(1)
        if ":" in full_name:
            lib_name, symbol_name = full_name.split(":", 1)
        else:
            lib_name, symbol_name = "kicad", full_name
        symbol_expr = re.sub(r'\(symbol\s+"[^"]+"', f'(symbol "{symbol_name}"', symbol_expr, count=1)
        grouped.setdefault(lib_name, []).append(symbol_expr)
        cursor = symbol_end
    return grouped


def parse_symbol_pins(symbol_text: str) -> list[dict[str, str]]:
    pin_re = re.compile(
        r"\(pin\s+(\S+)\s+\S+\s+\(at[^\n]*?\).*?"
        r"\(name\s+\"([^\"]+)\".*?"
        r"\(number\s+\"([^\"]+)\"",
        re.DOTALL,
    )
    pins = []
    for match in pin_re.finditer(symbol_text):
        direction, name, number = match.groups()
        width = "1"
        bus_match = re.search(r"\[(\d+):(\d+)\]", name)
        if bus_match:
            hi, lo = [int(v) for v in bus_match.groups()]
            width = str(abs(hi - lo) + 1)
        pins.append(
            {
                "pin_number": number,
                "symbol_pin": name,
                "direction": direction,
                "width": width,
                "backend_port": re.sub(r"\[[^\]]+\]", "", name),
            }
        )
    return sorted(pins, key=lambda item: int(item["pin_number"]))


def parse_board_pad_nets(board_text: str) -> dict[str, str]:
    footprint_marker = '(footprint "kicad:QFN-48_7x7mm_P0.5mm"'
    start = board_text.find(footprint_marker)
    if start >= 0:
        next_footprint = board_text.find('\n  (footprint ', start + len(footprint_marker))
        board_text = board_text[start:] if next_footprint < 0 else board_text[start:next_footprint]

    pad_nets = {}
    for line in board_text.splitlines():
        pad_match = re.search(r'\(pad\s+"([^"]+)"', line)
        net_match = re.search(r'\(net\s+\d+\s+"([^"]*)"\)', line)
        if pad_match and net_match:
            pad_nets[pad_match.group(1)] = net_match.group(1)
    return pad_nets


def net_name_for_pin(pin: dict[str, str]) -> str:
    if pin["symbol_pin"] == "VDD":
        return "+3V3"
    if pin["symbol_pin"] == "VSS":
        return "GND"
    return pin["backend_port"].upper()


def build_pad_nets(pins: list[dict[str, str]]) -> tuple[dict[str, str], dict[str, int]]:
    pad_nets = {}
    for pin in pins:
        pad_nets[pin["pin_number"]] = net_name_for_pin(pin)

    ordered_nets = ["GND", "+3V3"]
    for pin in pins:
        net_name = net_name_for_pin(pin)
        if net_name not in ordered_nets:
            ordered_nets.append(net_name)

    return pad_nets, {net_name: index + 1 for index, net_name in enumerate(ordered_nets)}


def render_qfn_footprint(pad_nets: dict[str, str], net_ids: dict[str, int]) -> str:
    module_text = read_text(FOOTPRINT_SRC)
    rendered = ['  (footprint "kicad:QFN-48_7x7mm_P0.5mm" (layer "F.Cu")']
    rendered.append('    (tstamp "dddddddd-0001-0001-0001-000000000001")')
    rendered.append("    (at 20 15)")

    for raw_line in module_text.splitlines()[1:]:
        line = raw_line
        if "(layer F.SilkS)" in line and line.lstrip().startswith("(fp_line"):
            continue
        line = re.sub(r"\(fp_text reference \S+", '(fp_text reference "U1"', line)
        line = re.sub(r"\(fp_text value \S+", '(fp_text value "PicoRV32"', line)
        pad_match = re.search(r'\(pad\s+"([^"]+)"', line)
        if pad_match:
            pad_number = pad_match.group(1)
            net_name = pad_nets.get(pad_number, "")
            if net_name:
                line = re.sub(r"\)$", f' (net {net_ids[net_name]} "{net_name}"))', line)
        rendered.append(f"  {line}")
    return "\n".join(rendered)


def render_library_footprint() -> str:
    lines = []
    for line in read_text(FOOTPRINT_SRC).splitlines():
        if "(layer F.SilkS)" in line and line.lstrip().startswith("(fp_line"):
            continue
        lines.append(line)
    return "\n".join(lines) + "\n"


def render_minimal_pcb(project_name: str, design_top: str, pins: list[dict[str, str]]) -> str:
    pad_nets, net_ids = build_pad_nets(pins)
    net_lines = ['  (net 0 "")']
    for net_name, net_id in sorted(net_ids.items(), key=lambda item: item[1]):
        net_lines.append(f'  (net {net_id} "{net_name}")')

    return (
        "(kicad_pcb (version 20230121) (generator silicontrace_kicad_export)\n\n"
        "  (general\n"
        "    (thickness 1.6)\n"
        "  )\n\n"
        '  (paper "A4")\n\n'
        "  (title_block\n"
        f'    (title "{design_top} Generated Test Board")\n'
        f'    (date "{datetime.now().date().isoformat()}")\n'
        '    (rev "1.0")\n'
        f'    (comment 1 "Generated from {project_name}")\n'
        '    (comment 2 "Minimal QFN-48 breakout skeleton")\n'
        "  )\n\n"
        "  (layers\n"
        '    (0 "F.Cu" signal)\n'
        '    (1 "In1.Cu" signal)\n'
        '    (2 "In2.Cu" signal)\n'
        '    (31 "B.Cu" signal)\n'
        '    (32 "B.Adhes" user "B.Adhesive")\n'
        '    (33 "F.Adhes" user "F.Adhesive")\n'
        '    (34 "B.Paste" user)\n'
        '    (35 "F.Paste" user)\n'
        '    (36 "B.SilkS" user "B.Silkscreen")\n'
        '    (37 "F.SilkS" user "F.Silkscreen")\n'
        '    (38 "B.Mask" user "B.Mask")\n'
        '    (39 "F.Mask" user "F.Mask")\n'
        '    (40 "Dwgs.User" user "User.Drawings")\n'
        '    (41 "Cmts.User" user "User.Comments")\n'
        '    (42 "Eco1.User" user "User.Eco1")\n'
        '    (43 "Eco2.User" user "User.Eco2")\n'
        '    (44 "Edge.Cuts" user)\n'
        '    (45 "Margin" user)\n'
        '    (46 "B.CrtYd" user "B.Courtyard")\n'
        '    (47 "F.CrtYd" user "F.Courtyard")\n'
        '    (48 "B.Fab" user "B.Fabrication")\n'
        '    (49 "F.Fab" user "F.Fabrication")\n'
        "  )\n\n"
        "  (setup\n"
        "    (pad_to_mask_clearance 0.05)\n"
        "    (allow_soldermask_bridges_in_footprints no)\n"
        "  )\n\n"
        + "\n".join(net_lines)
        + "\n\n"
        '  (gr_rect (start 0 0) (end 40 30) (layer "Edge.Cuts") (width 0.1) '
        '(tstamp "bbbbbbbb-0001-0001-0001-000000000001"))\n\n'
        + render_qfn_footprint(pad_nets, net_ids)
        + "\n)\n"
    )


def write_pin_map(path: Path, pins: list[dict[str, str]], pad_nets: dict[str, str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "pin_number",
                "symbol_pin",
                "backend_port",
                "direction",
                "width",
                "pcb_net",
            ],
        )
        writer.writeheader()
        for pin in pins:
            row = dict(pin)
            row["pcb_net"] = pad_nets.get(pin["pin_number"], "")
            writer.writerow(row)


def route_status() -> dict[str, str]:
    status_path = BACKEND_DIR / "rt" / "route_status.txt"
    if not status_path.is_file():
        return {"status": "missing", "detail": "route_status.txt not found"}

    status: dict[str, str] = {}
    for line in read_text(status_path).splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            status[key.strip()] = value.strip()
    return status or {"status": "unknown"}


def copy_project_templates(output_dir: Path, project_name: str, design_top: str, pins: list[dict[str, str]]) -> None:
    source_map = {
        "test_board.kicad_pro": f"{project_name}.kicad_pro",
        "test_board.kicad_sch": f"{project_name}.kicad_sch",
        "test_board.kicad_pcb": f"{project_name}.kicad_pcb",
    }

    for src_name, dst_name in source_map.items():
        src = TEMPLATE_DIR / src_name
        require_file(src)
        if src_name.endswith(".kicad_pcb"):
            data = render_minimal_pcb(project_name, design_top, pins)
        else:
            data = normalize_project_text(read_text(src), design_top)
        write_text(output_dir / dst_name, data)


def write_symbol_libraries(output_dir: Path, schematic_text: str) -> list[str]:
    grouped = extract_embedded_symbol_libraries(schematic_text)
    if not grouped:
        shutil.copy2(SYMBOL_SRC, output_dir / "symbols" / SYMBOL_SRC.name)
        return ["kicad"]

    lib_names = []
    for lib_name, symbol_exprs in grouped.items():
        lib_names.append(lib_name)
        write_text(
            output_dir / "symbols" / f"{lib_name}.kicad_sym",
            "(kicad_symbol_lib (version 20230121) (generator silicontrace_kicad_export)\n"
            + "\n".join(symbol_exprs)
            + "\n)\n",
        )
    return lib_names


def write_library_tables(output_dir: Path, symbol_libs: list[str]) -> None:
    symbol_entries = []
    for lib_name in symbol_libs:
        symbol_entries.append(
            f'  (lib (name "{lib_name}") (type "KiCad") '
            f'(uri "${{KIPRJMOD}}/symbols/{lib_name}.kicad_sym") '
            '(options "") (descr "SiliconTrace generated symbols"))'
        )
    write_text(
        output_dir / "sym-lib-table",
        '(sym_lib_table\n'
        '  (version 7)\n'
        + "\n".join(symbol_entries)
        + "\n"
        ')\n',
    )
    write_text(
        output_dir / "fp-lib-table",
        '(fp_lib_table\n'
        '  (version 7)\n'
        '  (lib (name "kicad") (type "KiCad") '
        '(uri "${KIPRJMOD}/footprints.pretty") '
        '(options "") (descr "SiliconTrace generated footprints"))\n'
        ')\n',
    )


def export_kicad(output_dir: Path, project_name: str, design_top: str) -> dict[str, object]:
    require_file(SYMBOL_SRC)
    require_file(FOOTPRINT_SRC)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    symbols_dir = output_dir / "symbols"
    footprints_dir = output_dir / "footprints.pretty"
    symbols_dir.mkdir()
    footprints_dir.mkdir()

    symbol_text = read_text(SYMBOL_SRC)
    pins = parse_symbol_pins(symbol_text)
    template_schematic_text = read_text(TEMPLATE_DIR / "test_board.kicad_sch")

    copy_project_templates(output_dir, project_name, design_top, pins)
    symbol_libs = write_symbol_libraries(output_dir, template_schematic_text)
    write_text(footprints_dir / FOOTPRINT_SRC.name, render_library_footprint())
    write_library_tables(output_dir, symbol_libs)

    board_text = read_text(output_dir / f"{project_name}.kicad_pcb")
    pad_nets = parse_board_pad_nets(board_text)
    write_pin_map(output_dir / "pin_map.csv", pins, pad_nets)

    manifest = {
        "project": project_name,
        "design_top": design_top,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "route_status": route_status(),
        "files": {
            "project": f"{project_name}.kicad_pro",
            "schematic": f"{project_name}.kicad_sch",
            "pcb": f"{project_name}.kicad_pcb",
            "symbols": [f"symbols/{lib_name}.kicad_sym" for lib_name in symbol_libs],
            "footprint": f"footprints.pretty/{FOOTPRINT_SRC.name}",
            "pin_map": "pin_map.csv",
        },
    }
    write_text(output_dir / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    write_text(
        output_dir / "README.md",
        "# SiliconTrace KiCad Export\n\n"
        f"Generated project: `{project_name}`\n\n"
        "Open the schematic or PCB with KiCad from this directory. "
        "The project includes local symbol and footprint tables, so it does not "
        "depend on global KiCad library configuration.\n\n"
        "- `pin_map.csv` maps PicoRV32 symbol pins to PCB nets.\n"
        "- `manifest.json` records backend route status and generated files.\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--project-name")
    parser.add_argument("--design-top", default=os.environ.get("DESIGN_TOP", "picorv32"))
    args = parser.parse_args()

    project_name = args.project_name or (DEFAULT_PROJECT_NAME if args.design_top == "picorv32" else f"{args.design_top}_test_board")
    output_dir = args.output_dir or PROJECT_ROOT / "artifacts" / "kicad" / project_name

    manifest = export_kicad(output_dir, project_name, args.design_top)
    print(f"KiCad project exported: {output_dir}")
    for label, rel_path in manifest["files"].items():
        if isinstance(rel_path, list):
            for item in rel_path:
                print(f"  {label}: {output_dir / item}")
        else:
            print(f"  {label}: {output_dir / rel_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
