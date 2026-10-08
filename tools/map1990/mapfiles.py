"""Writes every file of map/ for the rebuilt zone. Lines outside the zone are copied from vanilla unchanged; the zone
and the reshaped neighbours get new lines."""
import re
from collections import Counter, defaultdict, deque

import numpy as np
from PIL import Image
from scipy import ndimage

from .assemble import anchor_of
from .check import COASTAL_TYPES, PER_PROVINCE_TYPES, PER_STATE_COUNTS, adjacency_pairs, land_near, strait_pairs
from .common import MAP_H, px_of, stable_seed

STACK_INLAND = (0, 1, 2, 3, 4, 5, 6, 9, 10, 21, 22, 23, 24, 25, 26, 27, 38)
STACK_COASTAL_EXTRA = (19, 20)
FOUR = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
RING = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]


def fmt_building(sid, typ, x, y, z, rot, sea):
    return f"{sid};{typ};{x:.2f};{y:.2f};{z:.2f};{rot:.2f};{sea}"


def fmt_stack(pid, typ, x, y, z, rot, off):
    return f"{pid};{typ};{x:.2f};{y:.2f};{z:.2f};{rot:.2f};{off:.2f}"


def pos_of(row, col):
    """Pixel centre as the (x, z) of buildings.txt / unitstacks.txt."""
    return col + 0.5, MAP_H - row - 0.5


def bridge(path, adj, land):
    """Land-only province path: repeats and water dropped, jumps between non-neighbours replaced by the shortest land
    path (BFS over adj)."""
    path = [p for p in path if p in land]
    out = path[:1]
    for b in path[1:]:
        a = out[-1]
        if b == a:
            continue
        if b in adj.get(a, ()):
            out.append(b)
            continue
        prev, q = {a: None}, deque([a])
        while q and b not in prev:
            x = q.popleft()
            for y in adj.get(x, ()):
                if y in land and y not in prev:
                    prev[y] = x
                    q.append(y)
        if b not in prev:
            continue
        seg, x = [], b
        while x != a:
            seg.append(x)
            x = prev[x]
        out += seg[::-1]
    return out


class _Ctx:
    def __init__(self, zm, vm, states):
        self.zm, self.vm, self.states = zm, vm, states
        self.rng = np.random.default_rng(stable_seed("map1990"))
        self.state_of = {p: s for s, st in states.items() for p in st["provs"]}
        self.redo = set(zm.zone_provs) | set(zm.changed)            # provinces whose lines are regenerated
        self.gone = set(zm.pool) | self.redo                         # vanilla province ids whose old lines go
        self.objs = ndimage.find_objects(zm.ids)
        self.vobjs = ndimage.find_objects(vm.ids)
        kinds = {p: v.kind for p, v in zm.provs.items()}
        self.is_sea = np.zeros(max(zm.provs) + 1, bool)
        self.is_sea[[p for p, k in kinds.items() if k == "sea"]] = True
        self.land = {p for p, k in kinds.items() if k == "land"}
        self.vland = np.zeros(max(vm.provs) + 1, bool)
        self.vland[[p for p, v in vm.provs.items() if v.kind == "land"]] = True
        self.zone_states = {zm.unit_state[u] for u in set(zm.zone_provs.values())}

    def y(self, row, col):
        return self.vm.height[row, col] / 10.0

    def vanilla_point(self, p):
        bb = self.vobjs[p - 1]
        a = anchor_of(self.vm.ids[bb] == p)
        return a[0] + bb[0].start, a[1] + bb[1].start

    def coast_point(self, p):
        """A pixel of p next to the sea, nearest to p's anchor, and that sea province; None if p is not coastal."""
        bb = self.objs[p - 1]
        bb = tuple(slice(max(0, s.start - 1), s.stop + 1) for s in bb)
        sub = self.zm.ids[bb]
        pm = sub == p
        sea = self.is_sea[sub]
        cand = pm & ndimage.binary_dilation(sea, np.ones((3, 3), bool))       # diagonal sea counts too
        rr, cc = np.nonzero(cand)
        if not len(rr):
            return None
        ar, ac = self.zm.anchor.get(p, (rr.mean() + bb[0].start, cc.mean() + bb[1].start))
        k = int(np.argmin((rr + bb[0].start - ar) ** 2 + (cc + bb[1].start - ac) ** 2))
        r, c = rr[k], cc[k]
        for dr, dc in RING:
            if 0 <= r + dr < sub.shape[0] and 0 <= c + dc < sub.shape[1] and sea[r + dr, c + dc]:
                return (r + bb[0].start, c + bb[1].start), int(sub[r + dr, c + dc])
        return None

    def pixels(self, p):
        bb = self.objs[p - 1]
        rr, cc = np.nonzero(self.zm.ids[bb] == p)
        return rr + bb[0].start, cc + bb[1].start

    def nearest_of_state(self, sid, r, c):
        """The land pixel of state sid nearest to (r, c)."""
        best = None
        for p in self.states[sid]["provs"]:
            if p in self.land:
                rr, cc = self.pixels(p)
                d = (rr - r) ** 2 + (cc - c) ** 2
                k = int(np.argmin(d))
                if best is None or d[k] < best[0]:
                    best = (d[k], int(rr[k]), int(cc[k]))
        return best[1], best[2]


def write_all(zm, vm, states, out):
    out.mkdir(parents=True, exist_ok=True)
    ctx = _Ctx(zm, vm, states)
    _bmp(zm, out)
    _definition(zm, out)
    _regions(ctx, out)
    _buildings(ctx, out)
    _unitstacks(ctx, out)
    _railways(ctx, out)
    _supply_nodes(ctx, out)
    _adjacencies(ctx, out)


def _write(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _bmp(zm, out):
    lut = np.zeros((max(zm.provs) + 1, 3), np.uint8)
    for p, v in zm.provs.items():
        lut[p] = v.rgb
    Image.fromarray(lut[zm.ids], "RGB").save(out / "provinces.bmp")


def _definition(zm, out):
    lines = ["0;0;0;0;land;false;unknown;0"]
    for p in sorted(zm.provs):
        v = zm.provs[p]
        lines.append(f"{p};{v.rgb[0]};{v.rgb[1]};{v.rgb[2]};{v.kind};{'true' if v.coastal else 'false'};"
                     f"{v.terrain};{v.continent}")
    _write(out / "definition.csv", lines)


def _regions(ctx, out):
    zm, vm = ctx.zm, ctx.vm
    region = {p: rid for rid, r in vm.regions.items() for p in r.items if p not in zm.pool}
    region.update(zm.region_of)
    for s, st in ctx.states.items():           # a state whose provinces span regions moves into its main one
        rs = Counter(region.get(p) for p in st["provs"] if region.get(p) is not None)
        if len(rs) > 1:
            main = rs.most_common(1)[0][0]
            for p in st["provs"]:
                region[p] = main
    members = defaultdict(list)
    for p, rid in region.items():
        members[rid].append(p)
    (out / "strategicregions").mkdir(exist_ok=True)
    for rid, r in vm.regions.items():
        new = sorted(members.get(rid, []))
        if new == sorted(r.items):
            continue
        assert new, f"strategic region {rid} lost all its provinces"
        text = re.sub(r"provinces\s*=\s*\{[^}]*\}", "provinces={\n\t\t" + " ".join(map(str, new)) + " \n\t}",
                      r.text, count=1)
        (out / "strategicregions" / r.file).write_text(text, encoding="utf-8", newline="\n")


def _buildings(ctx, out):
    zm, vm, rng = ctx.zm, ctx.vm, ctx.rng
    lines, have = [], defaultdict(Counter)
    per_state = set(PER_STATE_COUNTS) | {"dockyard"}
    per_prov = set(PER_PROVINCE_TYPES) | set(COASTAL_TYPES)
    for f in vm.buildings:
        sid_v, typ = int(f[0]), f[1]
        r, c = px_of(float(f[2]), float(f[4]))
        if typ in per_prov:                     # coastal models often stand in the water: use the land beside them
            p_v = land_near(vm.ids, ctx.vland, ctx.state_of, sid_v, r, c)
            if p_v is None or p_v in ctx.gone or p_v not in ctx.state_of:
                continue
            f = [str(ctx.state_of[p_v])] + f[1:]
        elif typ in per_state:
            if sid_v in ctx.zone_states or int(zm.ids[r, c]) in zm.zone_provs or sid_v not in ctx.states:
                continue
            q = int(zm.ids[r, c])
            if q in ctx.land and ctx.state_of.get(q) != sid_v:     # its place went to a province of another state
                r, c = ctx.nearest_of_state(sid_v, r, c)
                x, z = pos_of(r, c)
                f = f[:2] + [f"{x:.2f}", f"{ctx.y(r, c):.2f}", f"{z:.2f}"] + f[5:]
        else:                                   # dams, locks, landmarks: stay where they are
            p = int(zm.ids[r, c])
            if p not in ctx.state_of:
                continue
            f = [str(ctx.state_of[p])] + f[1:]
        lines.append(";".join(f))
        have[int(f[0])][typ] += 1
    for p in sorted(ctx.redo):                   # province lines of the zone and the reshaped neighbours
        if p not in ctx.state_of:
            continue
        sid = ctx.state_of[p]
        r, c = zm.anchor[p]
        x, z = pos_of(r, c)
        for typ in PER_PROVINCE_TYPES:
            lines.append(fmt_building(sid, typ, x, ctx.y(r, c), z, rng.uniform(0, 6.28), 0))
        cp = ctx.coast_point(p) if zm.provs[p].coastal else None
        if cp:
            (r, c), sea = cp
            x, z = pos_of(r, c)
            for typ in COASTAL_TYPES:
                lines.append(fmt_building(sid, typ, x, ctx.y(r, c), z, rng.uniform(0, 6.28), sea))
    for sid in sorted(ctx.states):               # state lines: all of a zone state, the missing ones elsewhere
        need = Counter(PER_STATE_COUNTS) - have[sid]
        if sid in ctx.zone_states:
            need = Counter(PER_STATE_COUNTS)
        provs = [p for p in ctx.states[sid]["provs"] if p in ctx.land]
        main = _main_province(ctx, sid, provs)
        rr, cc = ctx.pixels(main)
        for typ, k in need.items():
            for _ in range(k):
                j = int(rng.integers(len(rr)))
                x, z = pos_of(rr[j], cc[j])
                lines.append(fmt_building(sid, typ, x, ctx.y(rr[j], cc[j]), z, rng.uniform(0, 6.28), 0))
        if sid in ctx.zone_states:
            coastal = [p for p in provs if zm.provs[p].coastal]
            cp = ctx.coast_point(max(coastal, key=lambda q: len(ctx.pixels(q)[0]))) if coastal else None
            if cp:
                (r, c), sea = cp
                x, z = pos_of(r, c)
                lines.append(fmt_building(sid, "dockyard", x, ctx.y(r, c), z, rng.uniform(0, 6.28), sea))
    # no final newline, as in vanilla: the engine reads one as an empty line with "invalid arguments count"
    (out / "buildings.txt").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _main_province(ctx, sid, provs):
    """The province of the state's biggest city, else its biggest province."""
    cities = [(c.pop, p) for c, p in ctx.zm.city_prov if p in provs]
    if cities:
        return max(cities)[1]
    return max(provs, key=lambda q: len(ctx.pixels(q)[0]))


def _unitstacks(ctx, out):
    zm, vm = ctx.zm, ctx.vm
    off = defaultdict(list)
    lines = []
    for f in vm.unitstacks:
        off[int(f[1])].append(float(f[6]))
        if int(f[0]) not in ctx.gone:
            lines.append(";".join(f))
    off = {t: float(np.median(v)) for t, v in off.items()}
    city_at = {p: (c.row, c.col) for c, p in zm.city_prov}
    for p in sorted(ctx.redo):
        ar, ac = zm.anchor[p]
        cp = ctx.coast_point(p) if zm.provs[p].coastal else None
        types = STACK_INLAND + (STACK_COASTAL_EXTRA if cp else ())
        for k, t in enumerate(types):
            if t == 38 and p in city_at:
                r, c = city_at[p]
            elif t in STACK_COASTAL_EXTRA:
                r, c = cp[0]
            else:
                dr, dc = RING[k % len(RING)]
                r, c = (ar + dr, ac + dc) if zm.ids[ar + dr, ac + dc] == p else (ar, ac)
            x, z = pos_of(r, c)
            lines.append(fmt_stack(p, t, x, ctx.y(r, c), z, 0.0, off.get(t, 0.0)))
    _write(out / "unitstacks.txt", lines)


def _adjacency(ctx):
    adj = defaultdict(set)
    for a, b in adjacency_pairs(ctx.zm.ids) | strait_pairs(ctx.vm.adjacency_lines):
        adj[a].add(b)
        adj[b].add(a)
    return adj


def _railways(ctx, out):
    zm, vm = ctx.zm, ctx.vm
    adj = _adjacency(ctx)
    lines = []
    for level, provs in vm.railways:
        if not set(provs) & ctx.gone:
            lines.append(f"{level} {len(provs)} {' '.join(map(str, provs))} ")
            continue
        pts = [ctx.vanilla_point(p) for p in provs]
        path = []
        for (r0, c0), (r1, c1) in zip(pts, pts[1:]):
            n = int(2 * max(abs(r1 - r0), abs(c1 - c0))) + 1
            for t in np.linspace(0, 1, n + 1):
                path.append(int(zm.ids[int(round(r0 + t * (r1 - r0))), int(round(c0 + t * (c1 - c0)))]))
        path = bridge(path, adj, ctx.land)
        if len(path) >= 2:
            lines.append(f"{level} {len(path)} {' '.join(map(str, path))} ")
    _write(out / "railways.txt", lines)


def _supply_nodes(ctx, out):
    zm, vm = ctx.zm, ctx.vm
    seen, lines = set(), []
    for level, p in vm.supply_nodes:
        q = p if p not in ctx.gone else int(zm.ids[ctx.vanilla_point(p)])
        if q in ctx.land and q not in seen:
            seen.add(q)
            lines.append(f"{level} {q} ")
    _write(out / "supply_nodes.txt", lines)


def _adjacencies(ctx, out):
    zm, vm = ctx.zm, ctx.vm
    lines = [vm.adjacency_lines[0]]
    for line in vm.adjacency_lines[1:]:
        f = line.split(";")
        if len(f) > 7 and f[0].lstrip("-").isdigit() and int(f[0]) >= 0:
            for i, (xi, yi) in ((0, (4, 5)), (1, (6, 7))):
                p = int(f[i])
                if p in ctx.gone:
                    if f[xi] != "-1":
                        r, c = px_of(float(f[xi]), float(f[yi]))
                    else:
                        r, c = ctx.vanilla_point(p)
                    f[i] = str(int(zm.ids[r, c]))
            line = ";".join(f)
        lines.append(line)
    _write(out / "adjacencies.csv", lines)
