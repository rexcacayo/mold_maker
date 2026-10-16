# SPDX-FileCopyrightText: 2026 Ricardo Lugaresi
# SPDX-License-Identifier: GPL-3.0-or-later

"""Moldes a partir de cualquier pieza.

RIGIDO: un bloque con la pieza vaciada dentro, partido en dos mitades por la sección más ancha,
        con llaves de centrado, bebedero y respiraderos. Para verter resina o escayola.
SILICONA: caja (paredes + base) alrededor de la pieza, que queda sujeta sobre un soporte que luego
        será el bebedero del molde de silicona. Dice cuánta silicona hace falta.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import common

AXES = {'X': Vector((1, 0, 0)), 'Y': Vector((0, 1, 0)), 'Z': Vector((0, 0, 1))}
SILICONE_DENSITY = 1.1          # g/ml aproximado (siliconas de moldes)


def _verts_world(context, obj):
    bm = common.world_bmesh(context, obj)
    try:
        return np.array([tuple(v.co) for v in bm.verts]), abs(bm.calc_volume(signed=True))
    finally:
        bm.free()


def box_bmesh(lo, hi):
    lo, hi = Vector(lo), Vector(hi)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=hi - lo, verts=bm.verts)
    bmesh.ops.translate(bm, vec=(lo + hi) / 2, verts=bm.verts)
    return bm


def _box(name, lo, hi, col):
    bm = box_bmesh(lo, hi)
    try:
        return common.new_object(bm, name, col)
    finally:
        bm.free()


def _add_cone(bm, base_center, axis, r_base, r_top, height, segments=48):
    """Añade un cono (o cilindro) cerrado a un bmesh existente."""
    axis = Vector(axis).normalized()
    q = axis.to_track_quat('Z', 'Y')
    # giro de media división: así ningún vértice cae justo en el plano de partición
    m = (Matrix.Translation(Vector(base_center) + axis * (height / 2)) @ q.to_matrix().to_4x4()
         @ Matrix.Rotation(math.pi / segments, 4, 'Z'))
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=segments,
                          radius1=r_base, radius2=r_top, depth=height, matrix=m)


def _cone(name, base_center, axis, r_base, r_top, height, col, segments=48):
    bm = bmesh.new()
    q = Vector(axis).normalized().to_track_quat('Z', 'Y')
    m = Matrix.Translation(Vector(base_center) + Vector(axis).normalized() * (height / 2)) @ q.to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=segments,
                          radius1=r_base, radius2=r_top, depth=height, matrix=m)
    try:
        return common.new_object(bm, name, col)
    finally:
        bm.free()


# --------------------------------------------------------------------------- partición
def auto_axis(V):
    """Eje normal a la partición: el de menor tamaño (la pieza se abre «de cara»)."""
    ext = V.max(0) - V.min(0)
    return 'XYZ'[int(np.argmin(ext))]


def widest_level(V, axis, bins=60):
    """Altura (a lo largo del eje) donde la pieza es más ancha: por ahí se parte el molde."""
    k = 'XYZ'.index(axis)
    t = V[:, k]
    lo, hi = float(t.min()), float(t.max())
    if hi - lo < 1e-12:
        return lo
    others = [i for i in range(3) if i != k]
    edges = np.linspace(lo, hi, bins + 1)
    mids, areas = [], []
    for a, b in zip(edges[1:-2], edges[2:-1]):      # sin los extremos
        sel = (t >= a) & (t < b)
        if sel.sum() < 3:
            continue
        P = V[sel][:, others]
        mids.append((a + b) / 2); areas.append(float(np.prod(P.max(0) - P.min(0))))
    if not areas:
        return (lo + hi) / 2
    areas, mids = np.array(areas), np.array(mids)
    top = mids[areas >= areas.max() * 0.97]          # meseta de máximos: se parte por su centro
    return float((top.min() + top.max()) / 2)


def _in_plane_axes(axis):
    return [a for a in 'XYZ' if a != axis]


# --------------------------------------------------------------------------- molde rígido
def rigid_mold(context, model, axis='AUTO', offset_mm=0.0, wall_mm=8.0, sprue_mm=6.0, vent_mm=2.0,
               key_mm=4.0, clearance_mm=0.2, vents=2, unit='AUTO', explode=True):
    common.require_solid(context, model)
    code, scale = common.resolve_unit(context.scene, unit, model)
    col = common._collection_of(model, context)
    V, vol = _verts_world(context, model)
    if axis == 'AUTO':
        axis = auto_axis(V)
    n = AXES[axis]
    k = 'XYZ'.index(axis)
    # un pelín fuera de la altura exacta: así el plano no pasa justo por filas de vértices (booleanas limpias)
    level = widest_level(V, axis) + offset_mm / scale + 0.0137 / scale
    lo, hi = V.min(0), V.max(0)
    if not (lo[k] < level < hi[k]):
        raise common.AddonError('La partición queda fuera de la pieza: baja el desplazamiento.')
    wall = wall_mm / scale
    blo, bhi = lo - wall, hi + wall
    co = Vector((0, 0, 0)); co[k] = level
    # «arriba» al verter: la dirección del plano en la que la pieza es más larga (el molde de pie)
    a1, a2 = _in_plane_axes(axis)
    i1, i2 = 'XYZ'.index(a1), 'XYZ'.index(a2)
    up_axis = 'Z' if 'Z' in (a1, a2) else (a1 if (hi[i1] - lo[i1]) >= (hi[i2] - lo[i2]) else a2)
    up = AXES[up_axis]
    iu = 'XYZ'.index(up_axis)
    side_axis = a2 if up_axis == a1 else a1
    isd = 'XYZ'.index(side_axis)
    created = []
    try:
        block = _box(model.name + '_bloque', blo, bhi, col); created.append(block)
        cav = model.copy(); cav.data = model.data.copy(); cav.name = model.name + '_cavidad'
        col.objects.link(cav); created.append(cav)
        common.boolean(context, block, cav)
        created.remove(cav); common.remove_objects([cav])
        loops, u, v = common._section_loops(context, model, co, n)
        pts = np.vstack([[tuple(co + u * float(x) + v * float(y)) for x, y in lp] for lp in loops])
        a = common._half(context, block, co, n, False, model.name + '_molde_A', col); created.append(a)
        b = common._half(context, block, co, n, True, model.name + '_molde_B', col); created.append(b)
        created.remove(block); common.remove_objects([block])

        # bebedero y respiraderos: desde lo más alto de la sección hasta fuera del bloque
        channels = []
        top = float(bhi[iu]) + 1.0 / scale
        order = np.argsort(-pts[:, iu])
        channels.append((pts[order[0]], sprue_mm / 2 / scale))      # bebedero: lo más alto
        span = float(hi[isd] - lo[isd])
        min_gap = max(span / 6, 2.5 * sprue_mm / scale)
        # respiraderos: primero los «techos» donde se queda el aire (máximos locales de cada contorno)
        cands = []
        for lp in loops:
            W = np.array([tuple(co + u * float(x) + v * float(y)) for x, y in lp])
            h = W[:, iu]
            win = max(2, len(W) // 30)
            for j in range(len(W)):
                nb = h[[(j + d) % len(W) for d in range(-win, win + 1)]]
                if h[j] >= nb.max() - 1e-9:
                    cands.append(W[j])
        cands = sorted(cands, key=lambda q: -q[iu])
        hmin = float(pts[:, iu].min())
        tall = [pts[j] for j in order if pts[j][iu] >= hmin + 0.6 * (float(pts[:, iu].max()) - hmin)]
        for pool in (cands, tall):
            for q in pool:
                if len(channels) > vents:
                    break
                if all(abs(q[isd] - c[0][isd]) > min_gap for c in channels):
                    channels.append((q, vent_mm / 2 / scale))
        # todo en pocas booleanas (cada una deja astillas; muchas seguidas acaban fallando)
        cut_a, cut_b, pegs = bmesh.new(), bmesh.new(), bmesh.new()
        for p, r in channels:
            start = Vector(p) - up * (r * 1.5)
            length = top - start[iu]
            for target in (cut_a, cut_b):
                _add_cone(target, start, up, r, r, length, 32)

        # llaves de centrado en las 4 esquinas de la cara de partición (cono en A, hueco en B)
        rk = key_mm / 2 / scale
        c = clearance_mm / scale
        inset = wall / 2
        keys = 0
        for s1 in (blo[i1] + inset, bhi[i1] - inset):
            for s2 in (blo[i2] + inset, bhi[i2] - inset):
                pos = Vector((0, 0, 0)); pos[k] = level; pos[i1] = s1; pos[i2] = s2
                if any(abs(pos[isd] - pp[isd]) < rk + r + 1.0 / scale and pos[iu] > pp[iu] for pp, r in channels):
                    continue
                base = pos - n * (0.5 / scale)
                _add_cone(pegs, base, n, rk, rk * 0.6, rk * 1.4 + 0.5 / scale, 40)
                _add_cone(cut_b, base, n, rk + c, rk * 0.6 + c, rk * 1.4 + c + 0.5 / scale, 40)
                keys += 1
        for bm_, name, target, op in ((cut_b, 'Cortes_B', b, 'DIFFERENCE'), (cut_a, 'Cortes_A', a, 'DIFFERENCE'),
                                      (pegs, 'Llaves', a, 'UNION')):
            if not bm_.verts:
                bm_.free(); continue
            tmp = common.new_object(bm_, name + '_temporal', col); bm_.free()
            created.append(tmp)
            common.boolean(context, target, tmp, op)
            created.remove(tmp); common.remove_objects([tmp])
        if explode:
            b.location = b.location + n * (wall * 1.5)
        for o in (a, b):
            o[common.UNIT_PROP] = code
            o['molde_de'] = model.name
        common._finish(context, model, [a, b])
        model.hide_set(False)        # la pieza sigue a la vista, para comparar
    except Exception:
        common.remove_objects(created)
        raise
    ml = vol * scale ** 3 / 1000.0
    return (f'Molde rígido en 2 mitades (partición {axis}), {keys} llaves, bebedero Ø{sprue_mm:g} mm y '
            f'{len(channels) - 1} respiradero(s). Hacen falta unos {ml:.0f} ml de resina o escayola.')


# --------------------------------------------------------------------------- caja para silicona
def silicone_box(context, model, margin_mm=8.0, wall_mm=2.4, base_mm=3.0, sprue_mm=8.0, gap_mm=8.0,
                 clearance_mm=0.3, unit='AUTO'):
    common.require_solid(context, model)
    code, scale = common.resolve_unit(context.scene, unit, model)
    col = common._collection_of(model, context)
    V, vol = _verts_world(context, model)
    lo, hi = V.min(0), V.max(0)
    m, w, bt, gap, c = (x / scale for x in (margin_mm, wall_mm, base_mm, gap_mm, clearance_mm))
    rs = sprue_mm / 2 / scale
    floor = lo[2] - gap                         # cara de arriba de la base
    inner_lo = np.array([lo[0] - m, lo[1] - m, floor])
    inner_hi = np.array([hi[0] + m, hi[1] + m, hi[2] + m])
    created = []
    try:
        # paredes: tubo rectangular
        walls = _box(model.name + '_caja', inner_lo - [w, w, 0], inner_hi + [w, w, 0], col); created.append(walls)
        hollow = _box('Hueco_temporal', inner_lo - [0, 0, 1], inner_hi + [0, 0, 1], col); created.append(hollow)
        common.boolean(context, walls, hollow)
        created.remove(hollow); common.remove_objects([hollow])
        # base con ranura donde encajan las paredes
        extra = w + 2 / scale
        base = _box(model.name + '_base', inner_lo - [extra, extra, bt], [inner_hi[0] + extra, inner_hi[1] + extra, floor], col)
        created.append(base)
        groove = _box('Ranura_temporal', inner_lo - [w + c, w + c, 1.0 / scale], [inner_hi[0] + w + c, inner_hi[1] + w + c, floor + 1.0 / scale], col)
        core = _box('Nucleo_temporal', inner_lo + [c, c, -2.0 / scale], [inner_hi[0] - c, inner_hi[1] - c, floor + 2.0 / scale], col)
        created += [groove, core]
        common.boolean(context, groove, core)
        common.boolean(context, base, groove)
        for o in (groove, core):
            created.remove(o)
        common.remove_objects([groove, core])
        # soporte = bebedero: cono desde la base hasta el punto más bajo de la pieza
        low = V[np.argmin(V[:, 2])]
        overlap = min(1.0 / scale, (hi[2] - lo[2]) * 0.05)
        height = (low[2] + overlap) - floor
        sprue = _cone('Soporte_temporal', Vector((low[0], low[1], floor - 0.5 / scale)), Vector((0, 0, 1)),
                      rs * 1.4, rs, height + 0.5 / scale, col)
        created.append(sprue)
        common.boolean(context, base, sprue, 'UNION')
        created.remove(sprue); common.remove_objects([sprue])
        for o in (walls, base):
            o[common.UNIT_PROP] = code
            o['molde_de'] = model.name
        for o in context.selected_objects:
            o.select_set(False)
        for o in (walls, base):
            o.select_set(True)
        context.view_layer.objects.active = walls
    except Exception:
        common.remove_objects(created)
        raise
    inner = float(np.prod(inner_hi - inner_lo))
    sprue_vol = math.pi * height * (rs ** 2 + rs * rs * 1.4 + (rs * 1.4) ** 2) / 3
    ml = max(0.0, inner - vol - sprue_vol) * scale ** 3 / 1000.0
    return (f'Caja para silicona: paredes + base con soporte. Pega la pieza sobre el soporte, monta la caja '
            f'y vierte unos {ml:.0f} ml de silicona (≈{ml * SILICONE_DENSITY:.0f} g).')
