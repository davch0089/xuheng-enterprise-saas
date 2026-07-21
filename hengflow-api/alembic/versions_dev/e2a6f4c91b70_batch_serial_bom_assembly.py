"""Batch lifecycle and BOM assembly.

Revision ID: e2a6f4c91b70
Revises: d18b620a4f35
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "e2a6f4c91b70"
down_revision = "d18b620a4f35"
branch_labels = None
depends_on = None
OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def base():
    """Return common table columns."""

    return [sa.Column("id", sa.Integer(), primary_key=True), sa.Column("create_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False), sa.Column("update_datetime", sa.DateTime(), server_default=sa.func.now(), nullable=False), sa.Column("delete_datetime", sa.DateTime()), sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.false())]


def upgrade():
    """Create serial lifecycle, BOM and assembly order structures."""

    op.create_table("erp_inventory_serial_movement", *base(),
        sa.Column("serial_id", sa.Integer(), nullable=False), sa.Column("stock_movement_id", sa.Integer(), nullable=False),
        sa.Column("serial_no", sa.String(120), nullable=False), sa.Column("movement_type", sa.String(40), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False), sa.Column("source_id", sa.Integer(), nullable=False), sa.Column("source_no", sa.String(60)),
        sa.Column("from_status", sa.String(20)), sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("from_warehouse_id", sa.Integer()), sa.Column("to_warehouse_id", sa.Integer()),
        sa.Column("from_batch_no", sa.String(80)), sa.Column("to_batch_no", sa.String(80)),
        sa.Column("occurred_at", sa.DateTime(), nullable=False), sa.Column("operator_id", sa.Integer()),
        sa.ForeignKeyConstraint(["serial_id"], ["erp_inventory_serial.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["stock_movement_id"], ["erp_inventory_ledger.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["from_warehouse_id"], ["erp_warehouse.id"]), sa.ForeignKeyConstraint(["to_warehouse_id"], ["erp_warehouse.id"]),
        sa.UniqueConstraint("serial_id", "stock_movement_id", name="uq_erp_serial_movement"), comment="序列号生命周期流水", **OPTIONS)
    op.create_index("ix_erp_serial_movement_serial", "erp_inventory_serial_movement", ["serial_id"])
    op.create_index("ix_erp_serial_movement_stock", "erp_inventory_serial_movement", ["stock_movement_id"])
    op.create_index("ix_erp_serial_movement_no", "erp_inventory_serial_movement", ["serial_no"])
    op.create_index("ix_erp_serial_movement_time", "erp_inventory_serial_movement", ["occurred_at"])

    op.create_table("erp_bill_of_material", *base(),
        sa.Column("code", sa.String(50), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False), sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("output_quantity", sa.DECIMAL(20,6), nullable=False, server_default="1"), sa.Column("version", sa.String(30), nullable=False, server_default="1.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("remark", sa.Text()),
        sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]), sa.ForeignKeyConstraint(["unit_id"], ["erp_unit.id"]),
        sa.UniqueConstraint("code", name="uq_erp_bom_code"), sa.UniqueConstraint("product_id", "version", name="uq_erp_bom_product_version"), comment="简化物料清单", **OPTIONS)
    op.create_table("erp_bill_of_material_line", *base(),
        sa.Column("bom_id", sa.Integer(), nullable=False), sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("component_product_id", sa.Integer(), nullable=False), sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("unit_to_base_rate", sa.DECIMAL(20,8), nullable=False), sa.Column("quantity", sa.DECIMAL(20,6), nullable=False),
        sa.Column("base_quantity", sa.DECIMAL(20,6), nullable=False), sa.Column("loss_rate", sa.DECIMAL(10,4), nullable=False, server_default="0"), sa.Column("remark", sa.String(500)),
        sa.ForeignKeyConstraint(["bom_id"], ["erp_bill_of_material.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["component_product_id"], ["erp_product.id"]), sa.ForeignKeyConstraint(["unit_id"], ["erp_unit.id"]),
        sa.UniqueConstraint("bom_id", "component_product_id", name="uq_erp_bom_component"), comment="BOM子件", **OPTIONS)

    op.create_table("erp_assembly_order", *base(),
        sa.Column("order_no", sa.String(50), nullable=False), sa.Column("business_date", sa.Date(), nullable=False), sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("bom_id", sa.Integer(), nullable=False), sa.Column("warehouse_id", sa.Integer(), nullable=False), sa.Column("employee_id", sa.Integer()),
        sa.Column("quantity", sa.DECIMAL(20,6), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_component_cost", sa.DECIMAL(20,4), nullable=False, server_default="0"), sa.Column("finished_cost", sa.DECIMAL(20,4), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text()), sa.Column("created_by_id", sa.Integer()), sa.Column("approved_by_id", sa.Integer()), sa.Column("approved_at", sa.DateTime()), sa.Column("posting_version", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["bom_id"], ["erp_bill_of_material.id"]), sa.ForeignKeyConstraint(["warehouse_id"], ["erp_warehouse.id"]), sa.ForeignKeyConstraint(["employee_id"], ["erp_employee.id"]),
        sa.UniqueConstraint("order_no", name="uq_erp_assembly_order_no"), comment="组装拆卸工单", **OPTIONS)
    op.create_table("erp_assembly_order_line", *base(),
        sa.Column("order_id", sa.Integer(), nullable=False), sa.Column("line_no", sa.Integer(), nullable=False), sa.Column("line_role", sa.String(20), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False), sa.Column("unit_id", sa.Integer(), nullable=False), sa.Column("unit_to_base_rate", sa.DECIMAL(20,8), nullable=False),
        sa.Column("quantity", sa.DECIMAL(20,6), nullable=False), sa.Column("base_quantity", sa.DECIMAL(20,6), nullable=False), sa.Column("actual_cost", sa.DECIMAL(20,4), nullable=False, server_default="0"),
        sa.Column("batch_no", sa.String(80)), sa.Column("production_date", sa.Date()), sa.Column("expiry_date", sa.Date()), sa.Column("serial_numbers", sa.Text()), sa.Column("remark", sa.String(500)),
        sa.ForeignKeyConstraint(["order_id"], ["erp_assembly_order.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["product_id"], ["erp_product.id"]), sa.ForeignKeyConstraint(["unit_id"], ["erp_unit.id"]),
        sa.UniqueConstraint("order_id", "line_no", name="uq_erp_assembly_order_line_no"), comment="组装拆卸工单明细", **OPTIONS)
    install_menus()


def install_menus():
    """Install BOM and assembly pages with button permissions."""

    bind=op.get_bind(); root=bind.execute(sa.text("SELECT id FROM vadmin_auth_menu WHERE path='/erp' AND is_delete=0 LIMIT 1")).scalar()
    if not root: return
    menu=sa.table("vadmin_auth_menu", *[sa.column(x, sa.String if x in {"title","icon","redirect","component","path","menu_type","perms"} else sa.Integer if x in {"order","parent_id"} else sa.Boolean) for x in ("title","icon","redirect","component","path","disabled","hidden","order","menu_type","parent_id","perms","noCache","breadcrumb","affix","noTagsView","canTo","alwaysShow","is_delete")])
    def add(title,parent,kind,order,perms,path=None,component=None,icon=None):
        """Insert one menu row."""
        return bind.execute(menu.insert().values(title=title,icon=icon,redirect=None,component=component,path=path,disabled=False,hidden=False,order=order,menu_type=kind,parent_id=parent,perms=perms,noCache=False,breadcrumb=True,affix=False,noTagsView=False,canTo=False,alwaysShow=False,is_delete=False)).lastrowid
    for title,code,path,component,order in (("物料清单","bom","boms","views/Erp/Inventory/Bom",24),("组装拆卸","assembly","assembly-orders","views/Erp/Inventory/Assembly",25)):
        page=add(title,root,"1",order,f"erp.inventory.{code}.list",path,component,"ep:setting")
        for i,action in enumerate(("view","create","update","delete","approve","unapprove")):
            add(action,page,"2",i,f"erp.inventory.{code}.{action}")


def downgrade():
    """Remove F11/F12 menus and tables."""

    op.get_bind().execute(sa.text("DELETE FROM vadmin_auth_menu WHERE perms LIKE 'erp.inventory.bom.%' OR perms LIKE 'erp.inventory.assembly.%'"))
    for table in ("erp_assembly_order_line","erp_assembly_order","erp_bill_of_material_line","erp_bill_of_material","erp_inventory_serial_movement"):
        op.drop_table(table)
