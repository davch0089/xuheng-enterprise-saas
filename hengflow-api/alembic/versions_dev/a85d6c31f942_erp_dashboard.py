"""Convert the smart screen to an ERP operating dashboard.

Revision ID: a85d6c31f942
Revises: f74c5b20e831
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "a85d6c31f942"
down_revision = "f74c5b20e831"
branch_labels = None
depends_on = None


def upgrade():
    """更新智慧大屏菜单名称并赋予 ERP 驾驶舱查看权限。"""

    op.execute(
        sa.text(
            "UPDATE vadmin_auth_menu "
            "SET title='ERP经营驾驶舱', perms='erp.dashboard.view' "
            "WHERE component='views/Vadmin/Screen/Air/Air' AND is_delete=0"
        )
    )


def downgrade():
    """恢复原空气监测菜单名称并移除 ERP 数据权限。"""

    op.execute(
        sa.text(
            "UPDATE vadmin_auth_menu "
            "SET title='空气监测', perms=NULL "
            "WHERE component='views/Vadmin/Screen/Air/Air' AND is_delete=0"
        )
    )
