#!/usr/bin/env python3
"""Summarize iEDA early-router congestion CSVs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


LAYERS = ("li1", "met1", "met2", "met3", "met4", "met5")


@dataclass(frozen=True)
class GCell:
    x: int
    y: int
    llx: int
    lly: int
    urx: int
    ury: int

    @property
    def center_um(self) -> tuple[float, float]:
        return (self.llx + self.urx) / 2000, (self.lly + self.ury) / 2000


@dataclass(frozen=True)
class Hotspot:
    overflow: int
    demand: int
    supply: int
    gcell: GCell
    layer_overflow: dict[str, int]


def read_matrix(path: Path) -> list[list[int]]:
    matrix: list[list[int]] = []
    with path.open() as file:
        for line in file:
            row = [int(value) for value in line.strip().split(",") if value != ""]
            if row:
                matrix.append(row)
    return matrix


def read_gcells(path: Path) -> dict[tuple[int, int], GCell]:
    gcells: dict[tuple[int, int], GCell] = {}
    with path.open() as file:
        for line in file:
            fields = [int(value) for value in line.strip().split(",")]
            if len(fields) != 6:
                continue
            x, y, llx, lly, urx, ury = fields
            gcells[(x, y)] = GCell(x, y, llx, lly, urx, ury)
    return gcells


def value_at(matrix: list[list[int]], x: int, y: int) -> int:
    row = len(matrix) - 1 - y
    if row < 0 or row >= len(matrix):
        return 0
    if x < 0 or x >= len(matrix[row]):
        return 0
    return matrix[row][x]


def read_required_matrix(er_dir: Path, name: str) -> list[list[int]]:
    path = er_dir / name
    if not path.exists():
        raise SystemExit(f"missing {path}")
    return read_matrix(path)


def load_hotspots(er_dir: Path) -> list[Hotspot]:
    gcells = read_gcells(er_dir / "gcell.info")
    overflow = read_required_matrix(er_dir, "overflow_map_planar.csv")
    demand = read_required_matrix(er_dir, "net_map_planar.csv")
    supply = read_required_matrix(er_dir, "supply_map_planar.csv")
    layer_maps = {
        layer: read_matrix(path)
        for layer in LAYERS
        if (path := er_dir / f"overflow_map_{layer}.csv").exists()
    }

    hotspots: list[Hotspot] = []
    y_size = len(overflow)
    for row_idx, row in enumerate(overflow):
        y = y_size - 1 - row_idx
        for x, value in enumerate(row):
            if not value:
                continue
            gcell = gcells.get((x, y))
            if gcell is None:
                continue
            layer_overflow = {
                layer: value_at(matrix, x, y)
                for layer, matrix in layer_maps.items()
                if value_at(matrix, x, y)
            }
            hotspots.append(
                Hotspot(
                    overflow=value,
                    demand=value_at(demand, x, y),
                    supply=value_at(supply, x, y),
                    gcell=gcell,
                    layer_overflow=layer_overflow,
                )
            )
    hotspots.sort(key=lambda item: item.overflow, reverse=True)
    return hotspots


def format_layers(layer_overflow: dict[str, int]) -> str:
    if not layer_overflow:
        return "-"
    return ",".join(f"{layer}:{value}" for layer, value in layer_overflow.items())


def print_hotspots(hotspots: list[Hotspot], top_count: int) -> None:
    total_overflow = sum(item.overflow for item in hotspots)
    print("Early-router congestion summary")
    print(f"nonzero_bins={len(hotspots)} total_overflow={total_overflow}")
    if not hotspots:
        return
    print("")
    print(f"Top {min(top_count, len(hotspots))} planar overflow bins:")
    print("rank overflow demand supply grid_x grid_y center_um layer_overflow")
    for rank, hotspot in enumerate(hotspots[:top_count], start=1):
        center_x, center_y = hotspot.gcell.center_um
        print(
            f"{rank:>4} {hotspot.overflow:>8} {hotspot.demand:>6} {hotspot.supply:>6} "
            f"{hotspot.gcell.x:>6} {hotspot.gcell.y:>6} "
            f"({center_x:.2f},{center_y:.2f}) {format_layers(hotspot.layer_overflow)}"
        )


def parse_probe(raw: str) -> tuple[float, float]:
    try:
        x_raw, y_raw = raw.split(",", 1)
        return float(x_raw), float(y_raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("probe must be X_UM,Y_UM") from exc


def print_probe_windows(hotspots: list[Hotspot], probes: list[tuple[float, float]], radius_um: float, local_top: int) -> None:
    if not probes:
        return
    print("")
    print(f"Probe windows (radius={radius_um:.2f}um):")
    for probe_x, probe_y in probes:
        window = []
        for hotspot in hotspots:
            center_x, center_y = hotspot.gcell.center_um
            if abs(center_x - probe_x) <= radius_um and abs(center_y - probe_y) <= radius_um:
                window.append(hotspot)
        total = sum(item.overflow for item in window)
        max_overflow = window[0].overflow if window else 0
        print(f"probe=({probe_x:.2f},{probe_y:.2f}) bins={len(window)} total_overflow={total} max_overflow={max_overflow}")
        for hotspot in window[:local_top]:
            center_x, center_y = hotspot.gcell.center_um
            print(
                f"  overflow={hotspot.overflow} demand={hotspot.demand} supply={hotspot.supply} "
                f"grid=({hotspot.gcell.x},{hotspot.gcell.y}) center=({center_x:.2f},{center_y:.2f}) "
                f"layers={format_layers(hotspot.layer_overflow)}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("er_dir", type=Path, help="early_router temp directory")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--probe", action="append", type=parse_probe, default=[], help="probe center in um as X,Y")
    parser.add_argument("--radius-um", type=float, default=8.0)
    parser.add_argument("--local-top", type=int, default=5)
    args = parser.parse_args()

    hotspots = load_hotspots(args.er_dir)
    print_hotspots(hotspots, args.top)
    print_probe_windows(hotspots, args.probe, args.radius_um, args.local_top)


if __name__ == "__main__":
    main()
