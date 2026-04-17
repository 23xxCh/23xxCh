# Contributing to H2Track

感谢您有兴趣为 H2Track 做出贡献！

## 开发环境设置

### 前置条件

- ROS 2 Humble
- Python 3.10+
- GADEN 气体仿真环境

### 安装步骤

1. 克隆仓库：
```bash
git clone https://github.com/your-repo/h2track-xian.git
cd h2track-xian
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 构建工作空间：
```bash
source /opt/ros/humble/setup.bash
colcon build
```

## 代码规范

### Python 代码风格

- 遵循 PEP 8 规范
- 使用 type hints
- 文档字符串使用 Google 风格

### 代码格式化

```bash
# 使用 ruff 格式化
ruff format src/

# 类型检查
mypy src/
```

## 提交规范

使用 Conventional Commits 格式：

- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档更新
- `test:` 测试相关
- `refactor:` 重构
- `chore:` 构建/工具变更

示例：
```
feat(tracking): add adaptive step size for surge-cast
```

## 测试要求

### 运行测试

```bash
source install/setup.bash
pytest src/h2track_tracking/test/ -v
```

### 测试覆盖率

- 新功能必须包含测试
- 测试覆盖率要求 ≥ 70%

## Pull Request 流程

1. Fork 仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m "feat: your feature"`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

### PR 检查清单

- [ ] 代码通过所有测试
- [ ] 代码覆盖率达标
- [ ] 文档已更新
- [ ] 提交信息符合规范

## 问题报告

请使用 GitHub Issues 报告问题，包含：

- 问题描述
- 复现步骤
- 预期行为
- 实际行为
- 环境信息

## 联系方式

如有问题，请开 Issue 或联系维护者。

---

感谢您的贡献！🙏
