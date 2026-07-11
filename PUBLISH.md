# Publicação no PyPI

Guia para publicar o **browser-mcp-server** no [PyPI](https://pypi.org/).

---

## Pré-requisitos

- Python 3.11+
- Conta no [PyPI](https://pypi.org/account/register/)
- Token de API do PyPI (recomendado) ou usuário/senha
- `twine` e `build` instalados:

```bash
pip install build twine
```

---

## Passo a passo

### 1. Atualizar a versão

Edite a versão em dois lugares:

| Arquivo | Campo |
|---------|-------|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `src/browser_mcp/__init__.py` | `__version__ = "X.Y.Z"` |

Seguir [Semantic Versioning](https://semver.org/):
- **PATCH** (`0.1.1`): bug fixes
- **MINOR** (`0.2.0`): novas features (backward-compatible)
- **MAJOR** (`1.0.0`): breaking changes

### 2. Limpar builds anteriores

```bash
rm -rf dist/
```

### 3. Gerar os artefatos de distribuição

```bash
python -m build
```

Isso cria:
- `dist/browser_mcp_server-X.Y.Z.tar.gz` — source distribution (sdist)
- `dist/browser_mcp_server-X.Y.Z-py3-none-any.whl` — wheel

### 4. Verificar os artefatos

```bash
twine check dist/*
```

Deve exibir `Passed` sem erros.

### 5. Fazer upload para TestPyPI (opcional, recomendado)

Use o [TestPyPI](https://test.pypi.org/) para validar antes do lançamento oficial:

```bash
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

Instale a partir do TestPyPI para testar:

```bash
pip install --index-url https://test.pypi.org/simple/ browser-mcp-server
```

### 6. Publicar no PyPI (oficial)

```bash
twine upload dist/*
```

Será solicitado:
- **Username**: `__token__` (recomendado)
- **Password**: seu token PyPI (ex: `pypi-xxxxxxxx`)

Ou use um arquivo `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 7. Verificar a publicação

- Acesse https://pypi.org/project/browser-mcp-server/
- Instale com pip:

```bash
pip install browser-mcp-server
```

---

## Automação via GitHub Actions

O repositório pode incluir um workflow de CI/CD. Exemplo de `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

permissions:
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

Configuração necessária:
1. No GitHub, vá em Settings → Secrets and variables → Actions
2. Adicione `PYPI_API_TOKEN` com seu token PyPI
3. No workflow acima, use `pypa/gh-action-pypi-publish` com `password: ${{ secrets.PYPI_API_TOKEN }}`

> ⚠️ **Importante**: Nunca commite tokens ou senhas no repositório.

---

## Checklist pré-publicação

- [ ] Versão atualizada no `pyproject.toml` e `__init__.py`
- [ ] `CHANGELOG.md` ou release notes atualizados
- [ ] `README.md` revisado e atualizado
- [ ] `LICENSE` presente (MIT)
- [ ] Build funciona: `python -m build`
- [ ] `twine check dist/*` passa sem erros
- [ ] Tag git criada: `git tag vX.Y.Z && git push origin vX.Y.Z`
- [ ] TestPyPI validado (opcional)
- [ ] Publicado no PyPI oficial
