# -*- coding: utf-8 -*-
"""HTTP 路由层（契约 §2）。

约定：每个模块暴露模块级 `router = APIRouter(prefix=..., tags=[...])`；
`app/main.py` 会自动发现并统一挂到 `/api` 前缀下，**此处不再重复写 `/api`**。
本层只做参数绑定、调用服务、组装响应；不写业务规则、不写 SQL。
"""
