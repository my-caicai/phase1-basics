# Git使用笔记
## 1. 分支管理
- 创建分支：`git checkout -b feature/d4-clean`
- 切换分支：`git checkout main`
- 合并分支：`git merge feature/d4-clean`
## 2. 冲突处理
- 冲突场景：合并分支时，README.md文件出现冲突
- 解决方法：手动编辑文件，保留主分支和新分支的有效内容，然后`git add`+`git commit`
## 3. 常用命令
- 查看提交历史：`git log --oneline`
- 查看状态：`git status`
- 提交：`git add . && git commit -m "feat: 完成D4数据清洗"`