#!/usr/bin/env python3
"""Summarize iRT DRC heatmaps for routing convergence experiments."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


LAYERS = ("li1", "met1", "met2", "met3", "met4", "met5")
STAGES = ("pin_accessor", "track_assigner", "detailed_router", "violation_reporter")


def read_matrix(path: Path) -> list[list[int]]:
    matrix: list[list[int]] = []
    with path.open() as file:
        for line in file:
            row = [int(value) for value in line.strip().split(",") if value != ""]
            if row:
                matrix.append(row)
    return matrix


def layer_from_name(path: Path) -> str | None:
    match = re.match(r"violation_map_(.+?)(?:_\d+)?\.csv$", path.name)
    if not match:
        return None
    layer = match.group(1)
    return layer if layer in LAYERS else None


def combine_max(matrices: list[list[list[int]]]) -> list[list[int]]:
    if not matrices:
        return []
    rows = max(len(matrix) for matrix in matrices)
    cols = max((len(row) for matrix in matrices for row in matrix), default=0)
    combined = [[0 for _ in range(cols)] for _ in range(rows)]
    for matrix in matrices:
        for row_idx, row in enumerate(matrix):
            for col_idx, value in enumerate(row):
                if value > combined[row_idx][col_idx]:
                    combined[row_idx][col_idx] = value
    return combined


def matrix_stats(matrix: list[list[int]]) -> dict[str, object]:
    total = 0
    nonzero = 0
    max_value = 0
    max_pos: tuple[int, int] | None = None
    for row_idx, row in enumerate(matrix):
        for col_idx, value in enumerate(row):
            total += value
            if value:
                nonzero += 1
                if value > max_value:
                    max_value = value
                    max_pos = (row_idx, col_idx)
    return {
        "rows": len(matrix),
        "cols": max((len(row) for row in matrix), default=0),
        "total": total,
        "nonzero": nonzero,
        "max_value": max_value,
        "max_pos": max_pos,
    }


def group_stage_maps(rt_dir: Path, stage: str) -> dict[str, list[list[int]]]:
    stage_dir = rt_dir / stage
    grouped: dict[str, list[list[list[int]]]] = {}
    for path in sorted(stage_dir.glob("violation_map_*.csv")):
        layer = layer_from_name(path)
        if layer is None:
            continue
        grouped.setdefault(layer, []).append(read_matrix(path))
    return {layer: combine_max(matrices) for layer, matrices in grouped.items()}


def parse_route_status(rt_dir: Path) -> list[str]:
    status_path = rt_dir / "route_status.txt"
    if not status_path.exists():
        return []
    return [line.strip() for line in status_path.read_text().splitlines() if line.strip()]


def parse_gcell_axes(rt_dir: Path) -> tuple[list[int], list[int]]:
    log_path = rt_dir / "rt.log"
    if not log_path.exists():
        return [], []

    axis: dict[str, list[int]] = {"x": [], "y": []}
    in_gcell = False
    current: str | None = None
    pattern = re.compile(r"start:(\d+)\s+step_length:(\d+)\s+step_num:(\d+)\s+end:(\d+)")
    for line in log_path.read_text(errors="replace").splitlines():
        if "printDatabase]   gcell_axis" in line:
            in_gcell = True
            continue
        if in_gcell and "printDatabase]   die" in line:
            break
        if not in_gcell:
            continue
        if "x_grid_list" in line:
            current = "x"
            continue
        if "y_grid_list" in line:
            current = "y"
            continue
        match = pattern.search(line)
        if current is None or match is None:
            continue
        start, step, step_num, end = (int(value) for value in match.groups())
        values = axis[current]
        if not values:
            values.append(start)
        for idx in range(1, step_num + 1):
            values.append(start + step * idx)
        if values[-1] != end:
            values.append(end)
    return axis["x"], axis["y"]


def coord_label(row: int, col: int, x_axis: list[int], y_axis: list[int]) -> str:
    if row + 1 < len(y_axis) and col + 1 < len(x_axis):
        x_um = ((x_axis[col] + x_axis[col + 1]) / 2) / 1000
        y_um = ((y_axis[row] + y_axis[row + 1]) / 2) / 1000
        return f"({row},{col}) center=({x_um:.2f}um,{y_um:.2f}um)"
    return f"({row},{col})"


def coord_center_um(row: int, col: int, x_axis: list[int], y_axis: list[int]) -> tuple[float, float] | None:
    if row + 1 >= len(y_axis) or col + 1 >= len(x_axis):
        return None
    x_um = ((x_axis[col] + x_axis[col + 1]) / 2) / 1000
    y_um = ((y_axis[row] + y_axis[row + 1]) / 2) / 1000
    return x_um, y_um


def top_hotspots(stage_maps: dict[str, list[list[int]]], top_count: int) -> list[tuple[int, int, int, dict[str, int]]]:
    combined: dict[tuple[int, int], dict[str, int]] = {}
    for layer, matrix in stage_maps.items():
        for row_idx, row in enumerate(matrix):
            for col_idx, value in enumerate(row):
                if value:
                    combined.setdefault((row_idx, col_idx), {})[layer] = value
    ranked = []
    for (row, col), layer_values in combined.items():
        ranked.append((sum(layer_values.values()), row, col, layer_values))
    ranked.sort(reverse=True)
    return [(row, col, total, layer_values) for total, row, col, layer_values in ranked[:top_count]]


def parse_pdn_stripes(def_path: Path) -> dict[str, list[dict[str, object]]]:
    stripes: dict[str, list[dict[str, object]]] = {"met4": [], "met5": []}
    if not def_path.exists():
        return stripes

    current_net = ""
    in_specialnets = False
    pattern = re.compile(
        r"(?:ROUTED|NEW)\s+(met[45])\s+(\d+)\s+\+\s+SHAPE\s+STRIPE\s+"
        r"\(\s+(\d+)\s+(\d+)\s+\)\s+\(\s+(\*|\d+)\s+(\*|\d+)\s+\)"
    )
    for line in def_path.read_text(errors="replace").splitlines():
        if line.startswith("SPECIALNETS"):
            in_specialnets = True
            continue
        if not in_specialnets:
            continue
        if line.startswith("END SPECIALNETS"):
            break
        if line.startswith("- "):
            parts = line.split()
            current_net = parts[1] if len(parts) > 1 else ""
            continue
        match = pattern.search(line)
        if not match:
            continue
        layer, width, x1, y1, x2, y2 = match.groups()
        if layer == "met4" and x2 == "*":
            stripes[layer].append({"net": current_net, "coord_um": int(x1) / 1000, "width_um": int(width) / 1000})
        elif layer == "met5" and y2 == "*":
            stripes[layer].append({"net": current_net, "coord_um": int(y1) / 1000, "width_um": int(width) / 1000})
    return stripes


def nearest_stripe(stripes: list[dict[str, object]], coord_um: float) -> tuple[dict[str, object], float] | None:
    if not stripes:
        return None
    stripe = min(stripes, key=lambda item: abs(float(item["coord_um"]) - coord_um))
    return stripe, abs(float(stripe["coord_um"]) - coord_um)


def stripe_edge_clearance_um(stripe: dict[str, object], coord_um: float) -> float:
    center_distance = abs(float(stripe["coord_um"]) - coord_um)
    return max(0.0, center_distance - (float(stripe["width_um"]) / 2))


def parse_route_shapes(def_path: Path) -> list[dict[str, object]]:
    shapes: list[dict[str, object]] = []
    if not def_path.exists():
        return shapes

    in_specialnets = False
    in_nets = False
    current_net = ""
    route_pattern = re.compile(r"\b(ROUTED|NEW|FIXED)\s+(\S+)\s+(.*)")
    coord_pattern = re.compile(r"\(\s+(\*|\d+)\s+(\*|\d+)\s+\)")
    for raw_line in def_path.read_text(errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("SPECIALNETS"):
            in_specialnets = True
            in_nets = False
            continue
        if line.startswith("END SPECIALNETS"):
            in_specialnets = False
            continue
        if line.startswith("NETS"):
            in_nets = True
            in_specialnets = False
            continue
        if line.startswith("END NETS"):
            in_nets = False
            continue
        if not in_specialnets and not in_nets:
            continue
        if line.startswith("- "):
            parts = line.split()
            current_net = parts[1] if len(parts) > 1 else ""
            continue

        match = route_pattern.search(line)
        if not match:
            continue
        _kind, layer, rest = match.groups()
        if layer not in LAYERS:
            continue

        coords: list[tuple[int, int]] = []
        last_x: int | None = None
        last_y: int | None = None
        for coord_match in coord_pattern.finditer(rest):
            x_raw, y_raw = coord_match.groups()
            if x_raw == "*" and last_x is None:
                continue
            if y_raw == "*" and last_y is None:
                continue
            x = last_x if x_raw == "*" else int(x_raw)
            y = last_y if y_raw == "*" else int(y_raw)
            if x is None or y is None:
                continue
            coords.append((x, y))
            last_x = x
            last_y = y

        source = "pdn" if in_specialnets else "signal"
        if len(coords) >= 2:
            x1, y1 = coords[0]
            x2, y2 = coords[-1]
            shapes.append(
                {
                    "source": source,
                    "net": current_net,
                    "layer": layer,
                    "type": "segment",
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                }
            )
        elif len(coords) == 1:
            x, y = coords[0]
            shapes.append(
                {
                    "source": source,
                    "net": current_net,
                    "layer": layer,
                    "type": "point",
                    "x1": x,
                    "y1": y,
                    "x2": x,
                    "y2": y,
                }
            )
    return shapes


def shape_intersects_window(shape: dict[str, object], center_x: int, center_y: int, half_window: int) -> bool:
    x1 = int(shape["x1"])
    y1 = int(shape["y1"])
    x2 = int(shape["x2"])
    y2 = int(shape["y2"])
    min_x = min(x1, x2)
    max_x = max(x1, x2)
    min_y = min(y1, y2)
    max_y = max(y1, y2)
    return (
        max_x >= center_x - half_window
        and min_x <= center_x + half_window
        and max_y >= center_y - half_window
        and min_y <= center_y + half_window
    )


def print_hotspot_shape_summary(
    hotspots: list[tuple[int, int, int, dict[str, int]]],
    x_axis: list[int],
    y_axis: list[int],
    def_file: str | None,
    window_um: float,
) -> None:
    if not def_file:
        return
    shapes = parse_route_shapes(Path(def_file))
    if not shapes:
        print()
        print(f"# no DEF route shapes found in {def_file}")
        return

    half_window = int(window_um * 1000)
    print()
    print("Hotspot DEF shape window summary")
    print("rank,coord,center_um,window_um,layer,pdn_segments,pdn_points,signal_segments,signal_points,top_signal_nets")
    for rank, (row, col, _total, _layer_values) in enumerate(hotspots, start=1):
        center = coord_center_um(row, col, x_axis, y_axis)
        if center is None:
            continue
        center_x = int(center[0] * 1000)
        center_y = int(center[1] * 1000)
        nearby = [shape for shape in shapes if shape_intersects_window(shape, center_x, center_y, half_window)]
        for layer in LAYERS:
            pdn_segments = 0
            pdn_points = 0
            signal_segments = 0
            signal_points = 0
            signal_net_counts: dict[str, int] = {}
            for shape in nearby:
                if shape["layer"] != layer:
                    continue
                if shape["source"] == "pdn":
                    if shape["type"] == "segment":
                        pdn_segments += 1
                    else:
                        pdn_points += 1
                else:
                    if shape["type"] == "segment":
                        signal_segments += 1
                    else:
                        signal_points += 1
                    net = str(shape["net"])
                    signal_net_counts[net] = signal_net_counts.get(net, 0) + 1
            if not (pdn_segments or pdn_points or signal_segments or signal_points):
                continue
            top_nets = sorted(signal_net_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
            top_net_label = " ".join(f"{net}:{count}" for net, count in top_nets)
            print(
                f"{rank},({row},{col}),({center[0]:.2f},{center[1]:.2f}),{window_um:.2f},{layer},"
                f"{pdn_segments},{pdn_points},{signal_segments},{signal_points},{top_net_label}"
            )


def print_hotspot_aggregate_summary(
    hotspots: list[tuple[int, int, int, dict[str, int]]],
    x_axis: list[int],
    y_axis: list[int],
    def_file: str | None,
    shape_def: str | None,
    window_um: float,
) -> None:
    if not hotspots:
        return

    print()
    print("Hotspot aggregate summary")
    print("metric,value")
    print(f"hotspot_count,{len(hotspots)}")

    if def_file:
        stripes = parse_pdn_stripes(Path(def_file))
        clearances = []
        for row, col, _total, _layer_values in hotspots:
            center = coord_center_um(row, col, x_axis, y_axis)
            if center is None:
                continue
            x_um, y_um = center
            candidate_clearances = []
            met4 = nearest_stripe(stripes["met4"], x_um)
            met5 = nearest_stripe(stripes["met5"], y_um)
            if met4:
                candidate_clearances.append(stripe_edge_clearance_um(met4[0], x_um))
            if met5:
                candidate_clearances.append(stripe_edge_clearance_um(met5[0], y_um))
            if candidate_clearances:
                clearances.append(min(candidate_clearances))
        if clearances:
            for threshold_um in (0.0, 1.0, 2.0, 4.0):
                count = sum(1 for clearance in clearances if clearance <= threshold_um)
                print(f"pdn_edge_clearance_le_{threshold_um:.1f}um,{count}")
            average = sum(clearances) / len(clearances)
            print(f"pdn_edge_clearance_avg_um,{average:.2f}")

    if not shape_def:
        return
    shapes = parse_route_shapes(Path(shape_def))
    if not shapes:
        print(f"shape_def,{shape_def}")
        print("shape_status,no_route_shapes_found")
        return

    half_window = int(window_um * 1000)
    total_counts = {"pdn_segments": 0, "pdn_points": 0, "signal_segments": 0, "signal_points": 0}
    layer_counts = {
        layer: {"pdn": 0, "signal": 0}
        for layer in LAYERS
    }
    signal_net_counts: dict[str, int] = {}
    for row, col, _total, _layer_values in hotspots:
        center = coord_center_um(row, col, x_axis, y_axis)
        if center is None:
            continue
        center_x = int(center[0] * 1000)
        center_y = int(center[1] * 1000)
        for shape in shapes:
            if not shape_intersects_window(shape, center_x, center_y, half_window):
                continue
            source = str(shape["source"])
            layer = str(shape["layer"])
            kind = str(shape["type"])
            if source == "pdn":
                key = "pdn_segments" if kind == "segment" else "pdn_points"
                total_counts[key] += 1
                if layer in layer_counts:
                    layer_counts[layer]["pdn"] += 1
            else:
                key = "signal_segments" if kind == "segment" else "signal_points"
                total_counts[key] += 1
                if layer in layer_counts:
                    layer_counts[layer]["signal"] += 1
                net = str(shape["net"])
                signal_net_counts[net] = signal_net_counts.get(net, 0) + 1

    pdn_shapes = total_counts["pdn_segments"] + total_counts["pdn_points"]
    signal_shapes = total_counts["signal_segments"] + total_counts["signal_points"]
    ratio = signal_shapes / pdn_shapes if pdn_shapes else 0.0
    print(f"shape_window_um,{window_um:.2f}")
    for key, value in total_counts.items():
        print(f"{key},{value}")
    print(f"signal_to_pdn_shape_ratio,{ratio:.2f}")
    print(f"unique_signal_nets,{len(signal_net_counts)}")
    top_nets = sorted(signal_net_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    if top_nets:
        print("top_signal_nets," + " ".join(f"{net}:{count}" for net, count in top_nets))
    print("shape_layer,layer,pdn_shapes,signal_shapes")
    for layer in LAYERS:
        counts = layer_counts[layer]
        if counts["pdn"] or counts["signal"]:
            print(f"shape_layer,{layer},{counts['pdn']},{counts['signal']}")


def parse_dr_progress(rt_dir: Path) -> list[str]:
    log_path = rt_dir / "rt.log"
    if not log_path.exists():
        return []
    progress = []
    pattern = re.compile(r"DetailedRouter\.cpp:\d+ Info routeDRBoxMap\] Routed .*")
    for line in log_path.read_text(errors="replace").splitlines():
        match = pattern.search(line)
        if match:
            progress.append(match.group(0).split("] ", 1)[-1])
    return progress


def table_cells(line: str) -> list[str]:
    marker = "printTableList]"
    if marker not in line:
        return []
    table_text = line.split(marker, 1)[1]
    if "|" not in table_text:
        return []
    return [cell.strip() for cell in table_text.split("|")[1:-1]]


def parse_int(value: str) -> int | None:
    normalized = value.replace(",", "")
    if re.match(r"^\d+$", normalized):
        return int(normalized)
    return None


def parse_violation_reporter_tables(rt_dir: Path) -> dict[str, dict[str, dict[str, int]]]:
    log_path = rt_dir / "rt.log"
    if not log_path.exists():
        return {}

    tables: dict[str, dict[str, dict[str, int]]] = {}
    section: str | None = None
    columns: list[str] = []
    for line in log_path.read_text(errors="replace").splitlines():
        cells = table_cells(line)
        if not cells:
            continue
        if cells[0] in ("within_net", "among_net"):
            section = cells[0]
            columns = []
            tables.setdefault(section, {})
            continue
        if section is None:
            continue
        if cells[0] == "routing":
            columns = cells[1:]
            continue
        if not columns or cells[0] not in (*LAYERS, "Total"):
            continue
        row: dict[str, int] = {}
        for column, value in zip(columns, cells[1:]):
            parsed_value = parse_int(value)
            if parsed_value is not None:
                row[column] = parsed_value
        if row:
            tables.setdefault(section, {})[cells[0]] = row
    return tables


def print_stage_summary(rt_dir: Path) -> None:
    print("Stage/layer violation-map totals")
    print("stage,layer,total,nonzero_cells,max_value,max_coord")
    missing_stages = []
    for stage in STAGES:
        stage_maps = group_stage_maps(rt_dir, stage)
        if not stage_maps:
            missing_stages.append(stage)
        for layer in LAYERS:
            matrix = stage_maps.get(layer)
            if matrix is None:
                continue
            stats = matrix_stats(matrix)
            max_pos = stats["max_pos"]
            coord = "" if max_pos is None else f"{max_pos[0]},{max_pos[1]}"
            print(f"{stage},{layer},{stats['total']},{stats['nonzero']},{stats['max_value']},{coord}")
    if missing_stages:
        print()
        print("Missing violation maps")
        print("stage,path")
        for stage in missing_stages:
            print(f"{stage},{rt_dir / stage / 'violation_map_*.csv'}")


def print_violation_type_summary(rt_dir: Path, include_layer_details: bool) -> None:
    tables = parse_violation_reporter_tables(rt_dir)
    if not tables:
        return

    print()
    print("ViolationReporter DRC by type")
    print("scope,layer,type,count")
    detail_layers = (*LAYERS, "Total") if include_layer_details else ("Total",)
    for scope in ("within_net", "among_net"):
        rows = tables.get(scope, {})
        for layer in detail_layers:
            type_counts = rows.get(layer)
            if not type_counts:
                continue
            for violation_type, count in type_counts.items():
                if count:
                    print(f"{scope},{layer},{violation_type},{count}")


def print_hotspot_pdn_summary(
    hotspots: list[tuple[int, int, int, dict[str, int]]],
    x_axis: list[int],
    y_axis: list[int],
    def_file: str | None,
) -> None:
    if not def_file:
        return
    stripes = parse_pdn_stripes(Path(def_file))
    if not stripes["met4"] and not stripes["met5"]:
        return

    print()
    print("Nearest PDN stripes for hotspots")
    print("rank,coord,center_um,nearest_met4_x,dx_um,nearest_met5_y,dy_um")
    for rank, (row, col, _total, _layer_values) in enumerate(hotspots, start=1):
        center = coord_center_um(row, col, x_axis, y_axis)
        if center is None:
            continue
        x_um, y_um = center
        met4 = nearest_stripe(stripes["met4"], x_um)
        met5 = nearest_stripe(stripes["met5"], y_um)
        met4_label = ""
        met5_label = ""
        dx_label = ""
        dy_label = ""
        if met4:
            stripe, dx = met4
            met4_label = f"{stripe['net']}@{float(stripe['coord_um']):.2f}"
            dx_label = f"{dx:.2f}"
        if met5:
            stripe, dy = met5
            met5_label = f"{stripe['net']}@{float(stripe['coord_um']):.2f}"
            dy_label = f"{dy:.2f}"
        print(f"{rank},({row},{col}),({x_um:.2f},{y_um:.2f}),{met4_label},{dx_label},{met5_label},{dy_label}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rt-dir", default="artifacts/backend/rt", help="Path to the iRT temp directory.")
    parser.add_argument("--top", type=int, default=20, help="Number of final hotspots to print.")
    parser.add_argument(
        "--type-details",
        action="store_true",
        help="Print ViolationReporter DRC counts for every routing layer instead of totals only.",
    )
    parser.add_argument("--def-file", help="Optional DEF file used to correlate hotspots with met4/met5 PDN stripes.")
    parser.add_argument("--shape-def", help="Optional routed DEF file used to count DEF shapes around hotspot windows.")
    parser.add_argument("--shape-window-um", type=float, default=6.0, help="Half-window size around each hotspot for --shape-def.")
    args = parser.parse_args()

    rt_dir = Path(args.rt_dir)
    if not rt_dir.exists():
        raise SystemExit(f"RT directory does not exist: {rt_dir}")

    status = parse_route_status(rt_dir)
    if status:
        print("Route status")
        for line in status:
            print(line)
        print()

    print_stage_summary(rt_dir)
    print_violation_type_summary(rt_dir, args.type_details)

    x_axis, y_axis = parse_gcell_axes(rt_dir)
    hotspot_stage = "violation_reporter"
    final_maps = group_stage_maps(rt_dir, hotspot_stage)
    if not final_maps:
        hotspot_stage = "detailed_router"
        final_maps = group_stage_maps(rt_dir, hotspot_stage)
    print()
    print(f"Top {args.top} hotspots from {hotspot_stage}")
    print("rank,coord,total,layer_breakdown")
    hotspots = top_hotspots(final_maps, args.top)
    if not hotspots:
        print(f"# no violation_map_*.csv data found for {hotspot_stage}")
    for rank, (row, col, total, layer_values) in enumerate(hotspots, start=1):
        breakdown = " ".join(f"{layer}:{layer_values[layer]}" for layer in LAYERS if layer in layer_values)
        print(f"{rank},{coord_label(row, col, x_axis, y_axis)},{total},{breakdown}")
    print_hotspot_pdn_summary(hotspots, x_axis, y_axis, args.def_file)
    print_hotspot_aggregate_summary(hotspots, x_axis, y_axis, args.def_file, args.shape_def, args.shape_window_um)
    print_hotspot_shape_summary(hotspots, x_axis, y_axis, args.shape_def, args.shape_window_um)

    progress = parse_dr_progress(rt_dir)
    if progress:
        print()
        print("DetailedRouter progress")
        for line in progress:
            print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
