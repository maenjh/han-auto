# Homebrew 설치 (macOS / Linux)

`han-auto`는 이 저장소에 포함된 Homebrew formula(`Formula/han-auto.rb`)로 설치할 수 있습니다.
저장소를 tap으로 추가한 뒤 설치합니다.

```bash
brew tap maenjh/han-auto https://github.com/maenjh/han-auto
brew install maenjh/han-auto/han-auto

han-auto --help
```

tap 없이 한 번에 설치하려면:

```bash
brew install https://raw.githubusercontent.com/maenjh/han-auto/master/Formula/han-auto.rb
```

개발 중인 최신 master를 설치하려면:

```bash
brew install --HEAD maenjh/han-auto/han-auto
```

업그레이드 / 제거:

```bash
brew update && brew upgrade maenjh/han-auto/han-auto
brew uninstall han-auto
brew untap maenjh/han-auto
```

## 빌드 방식과 의존성

formula는 한컴오피스가 필요 없는 기능을 그대로 제공합니다. 소스 tarball(릴리스 태그)에서
독립 가상환경을 만들어 Python 의존성을 함께 설치합니다.

- `depends_on "python@3.12"` — formula 전용 Python으로 격리 설치합니다.
- `depends_on "rust" => :build` — `pydantic-core`를 소스에서 빌드합니다.
- `depends_on "libyaml"` — `PyYAML`의 C 확장을 빌드합니다.

설치 후 `han-auto` 명령이 PATH에 등록됩니다.

## 포함되지 않는 것 (선택 기능)

formula는 무거운 C 확장을 기본 설치에서 제외해 빌드를 가볍고 안정적으로 유지합니다.
다음 기능은 별도 설치가 필요합니다.

| 기능 | 필요 패키지 | 설치 방법 |
|------|-------------|-----------|
| 로고 이미지 삽입(`--logo`) | Pillow | `pipx install 'han-auto[logo]'` 또는 아래 참고 |
| MCP 서버(`han-auto-mcp`) | mcp | `pipx install 'han-auto[mcp]'` (자세한 건 [docs/mcp.md](mcp.md)) |

로고·MCP까지 한 번에 쓰려면 Homebrew formula 대신 `pipx`/`uv`로 extra와 함께 설치하는 것을 권장합니다.

```bash
pipx install 'han-auto[logo,mcp]'
# 또는
uv tool install 'han-auto[logo,mcp]'   # PyPI 게시 후
```

> `.hwp` → `.hwpx` 변환은 첫 실행 시 Java(JDK)를 자동 내려받습니다(루트 README 참고). 이는 formula 설치와 무관하게 런타임에 처리됩니다.

## 유지보수: 새 버전 릴리스하기

새 버전을 배포할 때 formula를 갱신하는 절차입니다.

1. `pyproject.toml`의 `version`을 올리고 커밋·push.
2. 태그를 만들고 push: `git tag -a vX.Y.Z -m "han-auto X.Y.Z" && git push origin vX.Y.Z`.
3. 소스 tarball sha256 계산:
   ```bash
   curl -sL https://github.com/maenjh/han-auto/archive/refs/tags/vX.Y.Z.tar.gz | shasum -a 256
   ```
4. 의존성 `resource` 스탠자 재생성(런타임 의존성이 바뀐 경우):
   ```bash
   uv venv /tmp/hanbase && uv pip install --python /tmp/hanbase .
   uv run python - <<'PY'
   import json, subprocess, urllib.request
   out = subprocess.run(["uv","pip","freeze","--python","/tmp/hanbase"],capture_output=True,text=True).stdout
   for line in sorted(out.splitlines(), key=str.lower):
       if "==" not in line: continue
       name, ver = line.split("==", 1)
       if name.lower().replace("_","-") == "han-auto": continue
       data = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{ver}/json"))
       f = next(u for u in data["urls"] if u["packagetype"]=="sdist" and u["filename"].endswith(".tar.gz"))
       print(f'  resource "{name}" do\n    url "{f["url"]}"\n    sha256 "{f["digests"]["sha256"]}"\n  end\n')
   PY
   ```
5. `Formula/han-auto.rb`의 `url`/`sha256`/`resource`를 갱신하고 검증:
   ```bash
   brew style Formula/han-auto.rb
   brew install --build-from-source --formula "$(pwd)/Formula/han-auto.rb"
   ```
6. 커밋·push. tap 사용자는 `brew update && brew upgrade`로 받습니다.
