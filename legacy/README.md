# legacy · 历史版本

这里是**已不维护**的早期实现，只作历史保留，不参与现役代码与测试。

## desktop/v5.py

最早的桌面版（Tkinter GUI）：图片展示、数据网格、导出报告、恋爱冷静期弹窗，判定沿用旧的「算法比率 × AI 评分」口径，与网页版（0–100 分）不可直接比较。

```bash
pip install pandas openpyxl xlrd openai httpx pillow pygame
python legacy/desktop/v5.py
```

它从 `assets/pictures/`、`assets/music/` 取配图与配乐，从 `docs/reference/` 读理论文本；这些文件缺失时程序仍能启动。

> 现役实现是 `backend/` + `frontend/` 的 Web 版，新功能都只加在那边。若不再需要本目录，直接删除即可（`git rm -r legacy/`）。
