"""
API 管理页面 — 足球 API 配置、测试、增删
"""

import streamlit as st
import requests
import pandas as pd

API_BASE = "http://localhost:8000/api/admin"


def render():
    st.markdown('<div class="section-title">⚙️ 足球 API 管理</div>', unsafe_allow_html=True)
    st.caption("在此管理您使用的足球数据 API。仅支持足球相关 API（如 football-data.org, FIFA ranking 等）。添加后可在下方测试连接状态。")

    # ── 刷新函数 ──
    def load_apis():
        try:
            resp = requests.get(f"{API_BASE}/apis", timeout=5)
            if resp.status_code == 200:
                return resp.json().get("apis", [])
        except Exception:
            pass
        return []

    # ── 添加新 API ──
    with st.expander("➕ 添加新 API", expanded=False):
        with st.form("add_api_form"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("API 名称", placeholder="如 Football-Data.org")
                url = st.text_input("API URL", placeholder="https://api.football-data.org/v4/")
            with c2:
                api_key = st.text_input("API Key", placeholder="可选", type="password")
                description = st.text_input("描述", placeholder="简要说明")
            submitted = st.form_submit_button("✅ 添加", type="primary", use_container_width=True)
            if submitted and name and url:
                try:
                    resp = requests.post(f"{API_BASE}/apis", json={
                        "name": name, "url": url, "api_key": api_key or "",
                        "description": description or "",
                    }, timeout=5)
                    if resp.status_code == 200:
                        st.success(f"✅ {name} 添加成功")
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "添加失败"))
                except Exception as e:
                    st.error(f"请求失败: {e}")

    # ── API 列表 ──
    st.markdown("---")
    apis = load_apis()

    if not apis:
        st.info("暂无已配置的 API，请点击上方「➕ 添加新 API」")
    else:
        for api in apis:
            api_id = api.get("id", "")
            status = api.get("status", "unknown")
            color = {"online": "🟢", "offline": "🔴", "unknown": "⚪"}.get(status, "⚪")

            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            with col1:
                st.markdown(f"**{color} {api.get('name', api_id)}**")
                st.caption(api.get("url", "")[:60])
            with col2:
                st.caption(f"Key: {api.get('api_key', '')}")
                last = api.get("last_checked")
                if last:
                    st.caption(f"检测: {last[:16]}")
            with col3:
                if st.button("🔍 测试", key=f"test_{api_id}"):
                    with st.spinner("测试中..."):
                        try:
                            r = requests.post(f"{API_BASE}/apis/test/{api_id}", timeout=15)
                            if r.status_code == 200:
                                data = r.json()
                                st.toast(f"{data.get('status', '?')} - HTTP {data.get('status_code', '?')}")
                                st.rerun()
                            else:
                                st.error("测试失败")
                        except Exception as e:
                            st.error(f"请求失败: {e}")
            with col4:
                if st.button("🗑️", key=f"del_{api_id}", help="删除此 API"):
                    try:
                        r = requests.delete(f"{API_BASE}/apis/{api_id}", timeout=5)
                        if r.status_code == 200:
                            st.success("已删除")
                            st.rerun()
                    except Exception as e:
                        st.error(str(e))

    # ── 图例 ──
    st.markdown("---")
    st.caption("🟢 = 正常 | 🔴 = 不可用 | ⚪ = 未检测")
    st.caption("所有 API 仅用于获取足球赛事数据，不会用于其他用途。")
