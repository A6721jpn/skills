---
description: Stage all changes, commit, and push to the remote repository
---

このワークフローは、現在のすべての変更をステージングし、コミットし、リモートリポジトリへ送信します。

// turbo-all

1. すべての変更をステージ（add）します
```powershell
git add .
```

2. 変更をコミットします
```powershell
git commit -m "Update project structure and implementation"
```

3. リモートへ送信（push）します
```powershell
git push origin main
```
