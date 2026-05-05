# 环境与 Git 协作规范

本文档是本项目的统一环境和 Git 使用规范。三名成员必须遵守同一套规则，避免出现“我电脑能跑，你电脑不能跑”“代码互相覆盖”“结果无法复现”的问题。

---

## 一、环境规范

### 1. Python 版本

项目统一使用 Python 3.12。

项目根目录中的 `.python-version` 用于固定 Python 版本，目前应为：

```text
3.12
```

检查命令：

```powershell
Get-Content .python-version
uv run python --version
```

只要 `uv run python --version` 能正常显示 Python 版本，就说明环境基本成功。

### 2. 环境管理

项目统一使用 uv 管理环境。

不要每个人自己乱用 `pip install` 安装依赖。项目依赖以这两个文件为准：

```text
pyproject.toml
uv.lock
```

每个人 clone 仓库后，在项目根目录运行：

```powershell
uv sync
uv run python --version
```

以后运行脚本也尽量使用：

```powershell
uv run python src/xxx.py
```

不要直接使用系统 Python 跑项目脚本。

### 3. 虚拟环境和密钥

| 文件或目录 | 是否提交 | 说明 |
| :--- | :---: | :--- |
| `.venv/` | 否 | uv 自动生成的本地虚拟环境 |
| `.env` | 否 | 存放 API Key 等私密信息 |
| `.env.example` | 是 | 说明需要哪些环境变量，不能写真实 Key |
| `pyproject.toml` | 是 | 项目依赖声明 |
| `uv.lock` | 是 | 锁定依赖版本，保证环境一致 |
| `.python-version` | 是 | 固定 Python 版本 |

### 4. 新增依赖的规则

如果确实需要新增依赖，统一使用：

```powershell
uv add package_name
```

如果是只用于测试、格式检查的开发依赖，使用：

```powershell
uv add --dev package_name
```

新增依赖后必须提交：

```text
pyproject.toml
uv.lock
```

不要只在自己电脑安装，不提交锁文件。

---

## 二、Git 规范

### 1. 基本原则

1. GitHub 仓库是唯一同步来源。
2. 不用微信、QQ、网盘互传代码。
3. 不各自新建项目目录单独开发。
4. `main` 分支只放稳定版本。
5. 每个人做任务时新建自己的 `feature` 分支。
6. 合并到 `main` 前必须发 Pull Request。

### 2. 每天开始工作前

每天开始写代码或改数据前，先同步最新 `main`：

```powershell
git switch main
git pull origin main
```

然后新建或切换自己的任务分支。

### 3. 新建任务分支

示例：

```powershell
git switch main
git pull origin main
git switch -c feature/testset-data
```

分支命名建议：

| 类型 | 示例 |
| :--- | :--- |
| 数据任务 | `feature/testset-data` |
| 文档任务 | `docs/update-guidelines` |
| 功能任务 | `feature/ingest-parser` |
| 修复任务 | `fix/chunk-id-bug` |
| 评测任务 | `eval/recall-metric` |

### 4. 提交代码

做完一小块功能后提交：

```powershell
git status
git add .
git commit -m "data: add initial testset"
git push -u origin feature/testset-data
```

然后在 GitHub 上发 Pull Request，至少让另一个人检查后再合并到 `main`。

### 5. 不要提交的内容

这些内容不能提交到 GitHub：

```text
.venv/
.env
__pycache__/
*.pyc
临时日志
大体积无关文件
个人电脑路径配置
```

如果不确定能不能提交，先问组长。

---

## 三、提交信息规范

提交信息尽量使用下面格式：

```text
类型: 简短说明
```

常用类型：

| 类型 | 用途 | 示例 |
| :--- | :--- | :--- |
| `docs` | 文档 | `docs: update team roles` |
| `data` | 数据、测试集 | `data: add initial testset` |
| `feat` | 新功能 | `feat: add document parser` |
| `fix` | 修复问题 | `fix: fix chunk id bug` |
| `config` | 配置 | `config: add c0 naive config` |
| `eval` | 评测 | `eval: add recall metric` |
| `demo` | Demo | `demo: add gradio interface` |
| `refactor` | 重构 | `refactor: split retrieval module` |

好的提交信息：

```text
feat: add pdf parser
data: add 20 initial questions
eval: compute recall at 5
docs: add git workflow
```

不推荐：

```text
update
改了一下
finally
111
```

---

## 四、Pull Request 检查清单

发 Pull Request 前自查：

- [ ] 分支基于最新 `main`。
- [ ] 代码能运行。
- [ ] 没有提交 `.env`、`.venv/`、缓存和临时文件。
- [ ] 如果新增依赖，已经更新 `pyproject.toml` 和 `uv.lock`。
- [ ] 如果新增数据，放在正确目录。
- [ ] 如果新增实验结果，说明结果来源。
- [ ] PR 描述写清楚改了什么、如何验证。

PR 描述模板：

```text
## 本次修改

- 

## 验证方式

- 

## 可能影响

- 
```
