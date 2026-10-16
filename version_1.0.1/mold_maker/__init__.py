# SPDX-FileCopyrightText: 2026 Ricardo Lugaresi
# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {'name': 'Mold Maker', 'author': 'Ricardo Lugaresi', 'version': (1, 0, 1),
           'blender': (4, 2, 0), 'location': 'Vista 3D > N > Mold Maker',
           'description': 'Crea moldes imprimibles de cualquier pieza: molde rígido de 2 mitades o caja para silicona. Todo en modo Objeto',
           'category': 'Object'}

import bpy

from . import common, mold

KIND_ITEMS = [('RIGID', 'Rígido', 'Molde impreso de 2 mitades para verter resina o escayola directamente'),
              ('SILICONE', 'Silicona', 'Caja impresa con la pieza dentro: viertes silicona y sacas un molde flexible')]
AXIS_ITEMS = [('AUTO', 'Auto', 'Se abre por la cara más ancha de la pieza'),
              ('X', 'X', ''), ('Y', 'Y', ''), ('Z', 'Z', '')]


class MoldProps(bpy.types.PropertyGroup):
    model_unit: bpy.props.EnumProperty(name='Unidades', items=common.UNIT_ITEMS, default='AUTO')
    kind: bpy.props.EnumProperty(name='Molde', items=KIND_ITEMS, default='SILICONE')
    # rígido
    axis: bpy.props.EnumProperty(name='Partición', items=AXIS_ITEMS, default='AUTO')
    offset: bpy.props.FloatProperty(name='Subir/bajar partición (mm)', default=0.0, min=-500, max=500, precision=1)
    wall: bpy.props.FloatProperty(name='Pared (mm)', default=8.0, min=2, max=50, precision=1)
    sprue: bpy.props.FloatProperty(name='Bebedero Ø (mm)', default=6.0, min=2, max=30, precision=1)
    vent: bpy.props.FloatProperty(name='Respiradero Ø (mm)', default=2.0, min=1, max=10, precision=1)
    vents: bpy.props.IntProperty(name='Respiraderos', default=2, min=0, max=6)
    key: bpy.props.FloatProperty(name='Llaves Ø (mm)', default=5.0, min=2, max=20, precision=1)
    explode: bpy.props.BoolProperty(name='Separar las mitades para verlas', default=True)
    # silicona
    margin: bpy.props.FloatProperty(name='Silicona alrededor (mm)', default=8.0, min=3, max=40, precision=1)
    box_wall: bpy.props.FloatProperty(name='Pared de la caja (mm)', default=2.4, min=1.2, max=10, precision=1)
    gap: bpy.props.FloatProperty(name='Altura del soporte (mm)', default=8.0, min=3, max=40, precision=1)
    sil_sprue: bpy.props.FloatProperty(name='Soporte Ø (mm)', default=8.0, min=3, max=30, precision=1)
    clearance: bpy.props.FloatProperty(name='Holgura (mm)', default=0.25, min=0.05, max=1, precision=2)
    show_fine: bpy.props.BoolProperty(name='Ajustes', default=False)
    done: bpy.props.StringProperty(default='')
    export_folder: bpy.props.StringProperty(name='Carpeta', default='//Moldes', subtype='DIR_PATH')
    scope: bpy.props.EnumProperty(name='Exportar', items=common.SCOPE_ITEMS, default='SELECTED')


def _model(context):
    obj = context.active_object
    if obj is not None and obj.type == 'MESH' and not obj.get('showcase') and not obj.get('molde_de'):
        return obj
    for obj in context.selected_objects:
        if obj.type == 'MESH' and not obj.get('showcase') and not obj.get('molde_de'):
            return obj
    return None


class OBJECT_OT_mold_create(bpy.types.Operator):
    """Crea el molde de la pieza seleccionada. La pieza no se modifica"""
    bl_idname = 'object.mold_create'; bl_label = 'Crear molde'; bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return common.poll_object_mode(cls, context)

    def execute(self, context):
        p = context.scene.mold_props
        model = _model(context)
        if model is None:
            self.report({'ERROR'}, 'Selecciona la pieza (una malla) de la que quieres el molde.')
            return {'CANCELLED'}
        try:
            if p.kind == 'RIGID':
                msg = mold.rigid_mold(context, model, p.axis, p.offset, p.wall, p.sprue, p.vent, p.key,
                                      p.clearance, p.vents, p.model_unit, p.explode)
            else:
                msg = mold.silicone_box(context, model, p.margin, p.box_wall, 3.0, p.sil_sprue, p.gap,
                                        p.clearance, p.model_unit)
        except common.AddonError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        p.done = msg
        self.report({'INFO'}, msg + ' Ctrl+Z para probar otros ajustes.')
        return {'FINISHED'}


class OBJECT_OT_mold_export(bpy.types.Operator):
    """Exporta las piezas del molde a STL en milímetros"""
    bl_idname = 'object.mold_export'; bl_label = 'Exportar STL'

    @classmethod
    def poll(cls, context):
        return common.poll_object_mode(cls, context)

    def execute(self, context):
        p = context.scene.mold_props
        try:
            files = common.export_meshes(context, p.export_folder, p.scope, p.model_unit)
        except (common.AddonError, OSError) as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        where = files[0].parent if files else common.export_folder(p.export_folder)
        self.report({'INFO'}, f'{len(files)} STL exportados en mm en {where}'); return {'FINISHED'}


def _wrap(layout, text, width=38):
    col = layout.column(align=True); col.scale_y = .8
    line = ''
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            col.label(text=line); line = word
        else:
            line = (line + ' ' + word).strip()
    if line:
        col.label(text=line)


class VIEW3D_PT_mold(bpy.types.Panel):
    bl_label = 'Mold Maker'; bl_idname = 'VIEW3D_PT_mold'; bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = 'Mold Maker'

    def draw(self, context):
        layout = self.layout; p = context.scene.mold_props
        layout.use_property_split = True; layout.use_property_decorate = False
        if common.draw_mode_warning(layout, context):
            return
        box = layout.box()
        box.label(text='1 · Pieza', icon='MESH_DATA')
        model = _model(context)
        if model is None:
            row = box.row(); row.alert = True
            row.label(text='Selecciona la pieza', icon='ERROR')
        else:
            code, mm = common.resolve_unit(context.scene, p.model_unit, model)
            d = [x * mm for x in model.dimensions]
            box.label(text=model.name, icon='OBJECT_DATA')
            box.label(text=f'{d[0]:.0f} × {d[1]:.0f} × {d[2]:.0f} mm')
        box = layout.box()
        box.label(text='2 · Tipo de molde', icon='MOD_SOLIDIFY')
        row = box.row(); row.use_property_split = False
        row.prop(p, 'kind', expand=True)
        if p.kind == 'RIGID':
            _wrap(box, 'Dos mitades con la pieza vaciada dentro. Se cierran con llaves y se vierte por el bebedero.')
            box.prop(p, 'axis')
        else:
            _wrap(box, 'Caja y base con soporte. Pegas la pieza al soporte, montas la caja y viertes la silicona.')
        fine = box.column()
        fine.prop(p, 'show_fine', icon='TRIA_DOWN' if p.show_fine else 'TRIA_RIGHT', emboss=False)
        if p.show_fine:
            if p.kind == 'RIGID':
                for k in ('offset', 'wall', 'sprue', 'vents', 'vent', 'key', 'clearance', 'explode'):
                    fine.prop(p, k)
            else:
                for k in ('margin', 'box_wall', 'gap', 'sil_sprue', 'clearance'):
                    fine.prop(p, k)
            fine.prop(p, 'model_unit')
        col = layout.column(); col.scale_y = 1.6
        col.operator('object.mold_create', icon='MOD_BOOLEAN')
        if p.done:
            _wrap(layout, p.done)
        box = layout.box()
        box.label(text='3 · Exportar STL', icon='EXPORT')
        row = box.row(); row.use_property_split = False
        row.prop(p, 'scope', expand=True)
        box.prop(p, 'export_folder')
        box.operator('object.mold_export', icon='EXPORT')


classes = (MoldProps, OBJECT_OT_mold_create, OBJECT_OT_mold_export, VIEW3D_PT_mold)


def register():
    common.register_classes(classes, 'mold_props', MoldProps)


def unregister():
    common.unregister_classes(classes, 'mold_props')
